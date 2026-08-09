"""Sensor platform for LibreLink."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.recorder import get_instance, history as recorder_history
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
import homeassistant.util.dt as dt_util

from .const import (
    ATTRIBUTION,
    CONF_PATIENT_ID,
    DOMAIN,
    GLUCOSE_TREND_ICON,
    GLUCOSE_TREND_MESSAGE,
    GLUCOSE_VALUE_ICON,
    NAME,
    VERSION,
)
from .coordinator import LibreLinkDataUpdateCoordinator
from .units import UNITS_OF_MEASUREMENT, UnitOfMeasurement, mgdl_to_mmoll

import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.data[CONF_USERNAME]]

    # If custom unit of measurement is selectid it is initialized, otherwise MG/DL is used
    unit = {u.unit_of_measurement: u for u in UNITS_OF_MEASUREMENT}.get(
        config_entry.data[CONF_UNIT_OF_MEASUREMENT]
    )
    pid = config_entry.data[CONF_PATIENT_ID]

    # For each patients, new Device base on patients and
    # using an index as we need to keep the coordinator in the @property to get updates from coordinator
    # we create an array of entities then create entities.

    sensors = [
        MeasurementSensor(coordinator, pid, unit),
        TimeInRangeSensor(coordinator, pid, unit),
        TrendSensor(coordinator, pid),
        TrendArrowSensor(coordinator, pid),
        ApplicationTimestampSensor(coordinator, pid),
        ExpirationTimestampSensor(coordinator, pid),
        LastMeasurementTimestampSensor(coordinator, pid),
        RateOfChangeSensor(coordinator, pid, unit),
        Delta1MinSensor(coordinator, pid, unit),
        Delta5MinSensor(coordinator, pid, unit),
        Delta15MinSensor(coordinator, pid, unit),
    ]

    async_add_entities(sensors)



class LibreLinkSensorBase(CoordinatorEntity[LibreLinkDataUpdateCoordinator]):
    """LibreLink Sensor base class."""

    def __init__(self, coordinator: LibreLinkDataUpdateCoordinator, pid: str) -> None:
        """Initialize the device class."""
        super().__init__(coordinator)

        self.id = pid

    @property
    def device_info(self):
        """Return the device info of the sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._data.id)},
            name=self._data.name,
            model=VERSION,
            manufacturer=NAME,
        )

    @property
    def attribution(self):
        """Return the attribution for this entity."""
        return ATTRIBUTION

    @property
    def has_entity_name(self):
        """Return if the entity has a name."""
        return True

    @property
    def _data(self):
        return self.coordinator.data[self.id]

    @property
    def _trend_info(self) -> dict:
        """Return this patient's cached trend result.

        Computed once per coordinator poll (see coordinator._async_update_data)
        rather than here, so multiple property reads per poll (icon, state,
        attributes) don't each recompute - or re-log staleness - separately.
        """
        return self.coordinator.trend_results.get(self.id) or {}

    def _delta_info(self, window: str) -> dict:
        """Return this patient's cached delta result for a given window (1min/5min/15min)."""
        return self.coordinator.delta_results.get(self.id, {}).get(window, {})

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._data.id} {self.name}".replace(" ", "_").lower()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {}


class LibreLinkSensor(LibreLinkSensorBase, SensorEntity):
    """LibreLink Sensor class."""

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return GLUCOSE_VALUE_ICON

# Better trend sensor v1.3
class TrendSensor(LibreLinkSensor):
    """Trend sensor."""

    def __init__(self, coordinator, patient_id):
        """Initialize the sensor."""
        super().__init__(coordinator, patient_id)
        self._attr_icon = "mdi:trending-up"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Trend"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        trend_info = self._trend_info
        if trend_info:
            return trend_info.get("description", "Unknown")

        # No cached trend yet (e.g. right after startup, before the
        # coordinator's first poll populates it) - fall back to the
        # server-provided trend arrow.
        if measurement := self._data.measurement:
            if trend := measurement.trend:
                return self._convert_trend(trend)

        return "Unknown"

    @property
    def icon(self):
        """Return the icon for the frontend based on enhanced trend calculation."""
        trend_category = self._trend_info.get("trend", "UNKNOWN").upper()

        # Map the trend calculator categories to Material Design Icons
        icon_mapping = {
            "FALLING_FAST": "mdi:arrow-down-bold",      # ↓
            "FALLING": "mdi:arrow-bottom-right",        # ↘
            "STABLE": "mdi:arrow-right",                # →
            "RISING": "mdi:arrow-top-right",            # ↗
            "RISING_FAST": "mdi:arrow-up-bold",         # ↑
            "STALE_DATA": "mdi:clock-alert-outline",    # Clock with alert for stale data
            "UNKNOWN": "mdi:help-circle-outline",       # Question mark for unknown
        }

        return icon_mapping.get(trend_category, "mdi:help-circle-outline")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = super().extra_state_attributes

        trend_info = self._trend_info
        if trend_info:
            attrs.update({
                "trend_calculated": trend_info.get("calculated", False),
                "trend_rate_mgdl_per_min": round(trend_info.get("rate", 0.0), 4),
                "trend_rate_mmoll_per_min": round(mgdl_to_mmoll(trend_info.get("rate", 0.0)), 4),
                "trend_arrow": trend_info.get("arrow", "→"),
                "trend_category": trend_info.get("trend", "UNKNOWN"),
                "history_count": trend_info.get("history_count", 0),
                "data_is_fresh": trend_info.get("data_is_fresh", False),
                "minutes_since_last": round(trend_info.get("minutes_since_last", 999), 1)
            })

        return attrs

    def _convert_trend(self, trend):
        """Convert the trend value to a readable string."""
        if trend is None:
            return "Unknown"
        
        # If it's already a string from our calculator
        if isinstance(trend, str):
            trend_map = {
                "FALLING_FAST": "Falling fast",
                "FALLING": "Falling",
                "STABLE": "Stable",
                "RISING": "Rising",
                "RISING_FAST": "Rising fast",
            }
            return trend_map.get(str(trend).upper(), "Unknown")
        
        # If it's an integer from the server
        if isinstance(trend, int):
            trend_map = {
                1: "Falling fast",
                2: "Falling",
                3: "Stable",
                4: "Rising", 
                5: "Rising fast"
            }
            return trend_map.get(trend, "Unknown")
        
        return "Unknown"

# Better trend calculation v1.3 (sensor for rate of change)
class RateOfChangeSensor(LibreLinkSensor):
    """Rate of Change."""

    def __init__(self, coordinator, patient_id, unit):
        """Initialize the sensor."""
        super().__init__(coordinator, patient_id)
        self._attr_icon = "mdi:speedometer"
        self.unit = unit  # Store the selected unit

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Rate of Change"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement based on selected unit."""
        if self.unit.unit_of_measurement == "mmol/L":
            return "mmol/L per min"
        return "mg/dL per min"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        trend_info = self._trend_info

        # No cached trend yet, or data is stale - Home Assistant shows "Unavailable".
        if not trend_info or trend_info.get("trend") == "STALE_DATA":
            return None

        rate = trend_info.get("rate", 0.0)
        return round(self.unit.from_mg_per_dl(rate), 2)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = super().extra_state_attributes

        trend_info = self._trend_info
        if trend_info:
            attrs.update({
                "trend_category": trend_info.get("trend"),
                "trend_description": trend_info.get("description"),
                "trend_arrow": trend_info.get("arrow"),
                "history_count": trend_info.get("history_count")
            })

        return attrs

# Delta for 1min, 5min, 15min
class Delta1MinSensor(RateOfChangeSensor):
    """N-minute Delta sensor base class.

    Subclasses only need to override `_window`/`_label` - see
    Delta5MinSensor/Delta15MinSensor below.
    """

    _window = "1min"
    _label = "Delta 1min"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._label

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.unit.unit_of_measurement

    @property
    def native_value(self):
        """Return the state of the sensor."""
        trend_info = self._trend_info
        if not trend_info or trend_info.get("trend") == "STALE_DATA":
            return None

        delta_result = self._delta_info(self._window)
        if not delta_result.get("found", False):
            return None

        delta_mgdl = delta_result.get("delta_value", 0.0)
        return round(self.unit.from_mg_per_dl(delta_mgdl), 2)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = super().extra_state_attributes

        result = self._delta_info(self._window)
        attrs.update({
            "delta_raw_mgdl": round(result.get("delta_value", 0.0), 2),
            "time_window_min": round(result.get("time_diff", 0.0), 2),
            "measurement_found": result.get("found", False),
            "note": result.get("note", "")
        })

        return attrs

class Delta5MinSensor(Delta1MinSensor):
    """5-minute Delta sensor."""

    _window = "5min"
    _label = "Delta 5min"

class Delta15MinSensor(Delta1MinSensor):
    """15-minute Delta sensor."""

    _window = "15min"
    _label = "Delta 15min"

# Trend Arrow sensor
class TrendArrowSensor(LibreLinkSensor):
    """Trend Arrow sensor."""

    def __init__(self, coordinator, patient_id):
        """Initialize the sensor."""
        super().__init__(coordinator, patient_id)
        self._attr_icon = "mdi:arrow-up-down"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Glucose Trend Arrow"

    @property
    def native_value(self):
        """Return the state of the sensor (the arrow character)."""
        trend_info = self._trend_info
        if trend_info:
            return trend_info.get("arrow", "→")

        # No cached trend yet - fall back to the server-provided trend arrow.
        if measurement := self._data.measurement:
            if trend := measurement.trend:
                if isinstance(trend, int):
                    arrow_map = {
                        1: "↓",   # Falling fast
                        2: "↘",   # Falling
                        3: "→",   # Stable
                        4: "↗",   # Rising
                        5: "↑",   # Rising fast
                    }
                    return arrow_map.get(trend, "→")
                elif isinstance(trend, str):
                    trend_map = {
                        "FALLING_FAST": "↓",
                        "FALLING": "↘",
                        "STABLE": "→",
                        "RISING": "↗",
                        "RISING_FAST": "↑",
                    }
                    return trend_map.get(str(trend).upper(), "→")

        return "→"  # Default arrow

    @property
    def icon(self):
        """Return the icon for the frontend based on enhanced trend calculation."""
        trend_category = self._trend_info.get("trend", "UNKNOWN").upper()

        icon_mapping = {
            "FALLING_FAST": "mdi:arrow-down-bold",      # ↓
            "FALLING": "mdi:arrow-bottom-right",        # ↘
            "STABLE": "mdi:arrow-right",                # →
            "RISING": "mdi:arrow-top-right",            # ↗
            "RISING_FAST": "mdi:arrow-up-bold",         # ↑
            "STALE_DATA": "mdi:clock-alert-outline",    # Clock with alert for stale data
            "UNKNOWN": "mdi:help-circle-outline",       # Question mark for unknown
        }

        return icon_mapping.get(trend_category, "mdi:help-circle-outline")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = super().extra_state_attributes

        trend_info = self._trend_info
        if trend_info:
            attrs.update({
                "trend_description": trend_info.get("description", "Unknown"),
                "trend_category": trend_info.get("trend", "UNKNOWN"),
                "trend_rate_mmoll_per_min": round(mgdl_to_mmoll(trend_info.get("rate", 0.0)), 4),
            })

        return attrs

class MeasurementSensor(LibreLinkSensor):
    """Glucose Measurement Sensor class."""

    def __init__(
        self,
        coordinator: LibreLinkDataUpdateCoordinator,
        pid: str,
        unit: UnitOfMeasurement,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator, pid)
        self.unit = unit

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Measurement"

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return self.unit.from_mg_per_dl(self._data.measurement.value)

    @property
    def suggested_display_precision(self):
        """Return the suggested precision of the sensor."""
        return self.unit.suggested_display_precision

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self.unit.unit_of_measurement

    @property
    def native_unit_of_measurement(self):
        """Return the native unit of measurement of the sensor (used internally by
        SensorEntity to validate against device_class's allowed units).
        """
        return self.unit.unit_of_measurement

    @property
    def icon(self):
        """Return the icon for the frontend."""
        trend_category = self._trend_info.get("trend", "UNKNOWN").upper()

        if trend_category != "UNKNOWN":
            icon_mapping = {
                "FALLING_FAST": "mdi:arrow-down-bold",
                "FALLING": "mdi:arrow-bottom-right",
                "STABLE": "mdi:arrow-right",
                "RISING": "mdi:arrow-top-right",
                "RISING_FAST": "mdi:arrow-up-bold",
                "STALE_DATA": "mdi:clock-alert-outline",
            }
            return icon_mapping.get(trend_category, "mdi:help-circle-outline")

        # No cached trend yet - fall back to the original server-provided trend icon.
        if measurement := self._data.measurement:
            if trend := measurement.trend:
                return GLUCOSE_TREND_ICON.get(trend, GLUCOSE_VALUE_ICON)

        return GLUCOSE_VALUE_ICON

class TimeInRangeSensor(LibreLinkSensor):
    """Time In Range (24h) sensor."""

    def __init__(self, coordinator, patient_id, unit: UnitOfMeasurement):
        super().__init__(coordinator, patient_id)
        self.unit = unit

    async def async_added_to_hass(self):
        """Rebuild the 24h buffer from HA's recorder so a restart doesn't lose TIR history."""
        await super().async_added_to_hass()
        try:
            await self._async_seed_from_recorder()
        except Exception as e:
            # Never let a recorder hiccup block sensor setup - TIR will just
            # rebuild live over the next 24h instead.
            _LOGGER.debug(
                "Could not seed Time In Range history from recorder for patient %s: %s",
                self.id, e
            )

    async def _async_seed_from_recorder(self):
        """Pull the last 24h of the Measurement sensor's recorded states.

        This lets Time In Range survive a Home Assistant restart / integration
        reload, instead of starting from an empty in-memory buffer. Recorder
        data is merged with anything the coordinator has already polled live
        since startup, rather than overwriting it.
        """
        registry = er.async_get(self.hass)
        measurement_unique_id = f"{self.id} Measurement".replace(" ", "_").lower()
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, measurement_unique_id)

        if entity_id is None:
            _LOGGER.debug(
                "No recorded Measurement entity found yet for patient %s; "
                "Time In Range will rebuild live over the next 24h",
                self.id,
            )
            return

        start_time = dt_util.utcnow() - timedelta(hours=24)

        states_by_entity = await get_instance(self.hass).async_add_executor_job(
            recorder_history.state_changes_during_period,
            self.hass,
            start_time,
            None,
            entity_id,
        )

        recovered = []
        for state in states_by_entity.get(entity_id, []):
            if state.state in (None, "unknown", "unavailable"):
                continue
            try:
                displayed_value = float(state.state)
            except (ValueError, TypeError):
                continue
            # Recorder stores whatever unit was selected/displayed; convert
            # back to mg/dL to match target.low/high and history_24h.
            value_mgdl = self.unit.to_mg_per_dl(displayed_value)
            recovered.append({"timestamp": state.last_changed, "value": value_mgdl})

        if not recovered:
            return

        recovered.sort(key=lambda m: m["timestamp"])

        existing = self.coordinator.history_24h.get(self.id, [])
        if existing:
            # Keep recorder entries only where they don't overlap what's
            # already been polled live since this reload/restart.
            earliest_live = existing[0]["timestamp"]
            recovered = [m for m in recovered if m["timestamp"] < earliest_live]

        merged = recovered + existing
        cutoff = dt_util.utcnow() - timedelta(hours=24)
        merged = [m for m in merged if m["timestamp"] > cutoff]

        self.coordinator.history_24h[self.id] = merged
        _LOGGER.info(
            "Seeded Time In Range history for patient %s with %d measurements from recorder "
            "(now covering %d total)",
            self.id, len(recovered), len(merged)
        )

    @property
    def name(self):
        return "Time In Range (24h)"

    @property
    def native_unit_of_measurement(self):
        return "%"

    def _tir_stats(self):
        """Compute TIR stats once, shared by native_value and extra_state_attributes."""
        history = self.coordinator.history_24h.get(self.id, [])
        total = len(history)

        try:
            low = self._data.target.low
            high = self._data.target.high
        except Exception:
            low = high = None

        in_range = None
        if total and low is not None:
            in_range = sum(
                1 for m in history
                if m.get("value") is not None and low <= m["value"] <= high
            )

        return {
            "history": history,
            "total": total,
            "low": low,
            "high": high,
            "in_range": in_range,
        }

    @property
    def native_value(self):
        stats = self._tir_stats()
        if not stats["total"] or stats["in_range"] is None:
            return None
        return round((stats["in_range"] / stats["total"]) * 100.0, 2)

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        stats = self._tir_stats()
        history = stats["history"]

        attrs.update({"total_measurements": stats["total"]})

        if stats["low"] is not None:
            attrs.update({
                "target_low_mgdl": stats["low"],
                "target_high_mgdl": stats["high"],
            })

        if stats["total"]:
            attrs.update({
                "in_range_count": stats["in_range"],
                "start_time": history[0]["timestamp"].isoformat() if history[0].get("timestamp") else None,
                "end_time": history[-1]["timestamp"].isoformat() if history[-1].get("timestamp") else None,
            })

        return attrs

class TimestampSensor(LibreLinkSensor):
    """Timestamp Sensor class."""

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.TIMESTAMP

class ApplicationTimestampSensor(TimestampSensor):
    """Sensor Days Sensor class."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Application Timestamp"

    @property
    def available(self):
        """Return if the sensor data are available."""
        return self._data.device.application_timestamp is not None

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return self._data.device.application_timestamp

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the librelink sensor."""
        attrs = super().extra_state_attributes
        attrs.update({
            "Patient ID": self._data.id,
            "Patient": self._data.name,
        })
        if self.available:
            attrs.update({
                "Serial number": self._data.device.serial_number,
                "Activation date": self._data.device.application_timestamp,
                "Sensor product type": self._data.device.product_type,
                "Sensor lifespan days": self._data.device.sensor_lifespan,
                "Sensor plus model": self._data.device.is_plus_sensor,
            })
        return attrs

class ExpirationTimestampSensor(ApplicationTimestampSensor):
    """Sensor Days Sensor class."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Expiration Timestamp"

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return self._data.device.expiration_timestamp

class LastMeasurementTimestampSensor(TimestampSensor):
    """Sensor Delay Sensor class."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Last Measurement Timestamp"

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return self._data.measurement.timestamp
