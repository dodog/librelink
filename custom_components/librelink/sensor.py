"""Sensor platform for LibreLink."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

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
from .units import UNITS_OF_MEASUREMENT, UnitOfMeasurement

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
        self._calculated_trend = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Trend"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            if hasattr(self.coordinator, 'trend_calculator') and self.coordinator.trend_calculator:
                
                if self._data.measurement and self._data.measurement.value:
                    # Convert timestamp to string for trend calculator
                    timestamp = self._data.measurement.timestamp
                    if hasattr(timestamp, 'isoformat'):
                        timestamp_str = timestamp.isoformat()
                    else:
                        timestamp_str = str(timestamp)
                    
                    measurement_data = {
                        "Timestamp": timestamp_str,
                        "Value": self._data.measurement.value,
                        "TrendArrow": self._data.measurement.trend
                    }
                    
                    self.coordinator.trend_calculator.add_measurement(measurement_data)
                    trend_info = self.coordinator.trend_calculator.calculate_trend()
                    self._calculated_trend = trend_info
                    
                    _LOGGER.debug("Calculated trend info: %s", trend_info)
                    
                    if trend_info.get("calculated", False):
                        result = trend_info["description"]
                        return result
                    else:
                        # Even if not calculated, the calculator might have a fallback
                        result = trend_info.get("description", "Unknown")
                        return result
        except Exception as e:
            _LOGGER.error("Enhanced trend calculation failed: %s", e, exc_info=True)
            # Fall through to server trend
        
        # FALLBACK: Use server trend only if enhanced calculation failed
        if measurement := self._data.measurement:
            if trend := measurement.trend:
                result = self._convert_trend(trend)
                return result

        return "Unknown"

    @property
    def icon(self):
        """Return the icon for the frontend based on enhanced trend calculation."""
        # Use trend calculator data for icon, not the original trend icon
        if self._calculated_trend:
            trend_category = self._calculated_trend.get("trend", "UNKNOWN").upper()
            
            # Map the trend calculator categories to Material Design Icons
            # This matches what trend_calculator._trend_to_arrow() returns
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
        
        # Fallback if calculation hasn't run yet
        return "mdi:help-circle-outline"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # Start with parent attributes
        attrs = super().extra_state_attributes
        
        # Add enhanced info if available
        if self._calculated_trend:
            attrs.update({
                "trend_calculated": self._calculated_trend.get("calculated", False),
                "trend_rate_mgdl_per_min": round(self._calculated_trend.get("rate", 0.0), 4),
                "trend_rate_mmoll_per_min": round(self._calculated_trend.get("rate", 0.0) * 0.0555, 4),
                "trend_arrow": self._calculated_trend.get("arrow", "→"),
                "trend_category": self._calculated_trend.get("trend", "UNKNOWN"),
                "history_count": self._calculated_trend.get("history_count", 0),
                "data_is_fresh": self._calculated_trend.get("data_is_fresh", False),
                "minutes_since_last": round(self._calculated_trend.get("minutes_since_last", 999), 1)
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
        self._calculated_trend = None

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
        if hasattr(self.coordinator, 'trend_calculator') and self.coordinator.trend_calculator:
            trend_info = self.coordinator.trend_calculator.calculate_trend()
            self._calculated_trend = trend_info
            rate = trend_info.get("rate", 0.0)
            
            # Check for the special "stale data" trend
            if trend_info.get("trend") == "STALE_DATA":
                # Return None or a special value. Home Assistant will show "Unavailable"
                return None
            
            # Convert rate based on selected unit
            if self.unit.unit_of_measurement == "mmol/L":
                converted_rate = rate * 0.0555
                return round(converted_rate, 2)
            
            return round(rate, 2)
        
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # Start with parent attributes
        attrs = super().extra_state_attributes
        
        # Only add trend info if we have calculated trend data
        if self._calculated_trend is not None:
            attrs.update({
                "trend_category": self._calculated_trend.get("trend"),
                "trend_description": self._calculated_trend.get("description"),
                "trend_arrow": self._calculated_trend.get("arrow"),
                "history_count": self._calculated_trend.get("history_count")
            })
        
        return attrs

# Delta for 1min, 5min, 15min
class Delta1MinSensor(RateOfChangeSensor):
    """1-minute Delta sensor."""

    def __init__(self, coordinator, patient_id, unit):
        """Initialize the sensor."""
        super().__init__(coordinator, patient_id, unit)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Delta 1min"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.unit.unit_of_measurement  

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if hasattr(self.coordinator, 'trend_calculator') and self.coordinator.trend_calculator:
            # 1. Check the main trend result for stale data
            trend_info = self.coordinator.trend_calculator.calculate_trend()
            if trend_info.get("trend") == "STALE_DATA":
                return None
            
            # 2. Get the specific delta result
            delta_result = self.coordinator.trend_calculator.calculate_delta_1min()
            
            # 3. Check if a suitable measurement was actually found for the 1-min window
            if not delta_result.get("found", False):
                return None
            
            delta_mgdl = delta_result.get("delta_value", 0.0)
            
            # Convert to selected unit
            if self.unit.unit_of_measurement == "mmol/L":
                delta = delta_mgdl * 0.0555
            else:
                delta = delta_mgdl
            
            return round(delta, 2)
        
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # Start with parent attributes
        attrs = super().extra_state_attributes
        
        if hasattr(self.coordinator, 'trend_calculator') and self.coordinator.trend_calculator:
            result = self.coordinator.trend_calculator.calculate_delta_1min()
            attrs.update({
                "delta_raw_mgdl": round(result.get("delta_value", 0.0), 2),
                "time_window_min": round(result.get("time_diff", 0.0), 2),
                "measurement_found": result.get("found", False),
                "note": result.get("note", "")
            })
        
        return attrs

class Delta5MinSensor(Delta1MinSensor):
    """5-minute Delta sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Delta 5min"
    
    @property
    def native_unit_of_measurement(self):
        return self.unit.unit_of_measurement  

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if hasattr(self.coordinator, 'trend_calculator') and self.coordinator.trend_calculator:
            # 1. Check the main trend result for stale data
            trend_info = self.coordinator.trend_calculator.calculate_trend()
            if trend_info.get("trend") == "STALE_DATA":
                return None
            
            # 2. Get the specific delta result
            delta_result = self.coordinator.trend_calculator.calculate_delta_5min()
            
            # 3. Check if a suitable measurement was actually found for the 5-min window
            if not delta_result.get("found", False):
                return None
            
            delta_mgdl = delta_result.get("delta_value", 0.0)
            
            # Convert to selected unit
            if self.unit.unit_of_measurement == "mmol/L":
                delta = delta_mgdl * 0.0555
            else:
                delta = delta_mgdl
            
            return round(delta, 2)
        
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # Start with parent attributes
        attrs = super().extra_state_attributes
        
        if hasattr(self.coordinator, 'trend_calculator') and self.coordinator.trend_calculator:
            result = self.coordinator.trend_calculator.calculate_delta_5min()
            attrs.update({
                "delta_raw_mgdl": round(result.get("delta_value", 0.0), 2),
                "time_window_min": round(result.get("time_diff", 0.0), 2),
                "measurement_found": result.get("found", False),
                "note": result.get("note", "")
            })
        
        return attrs

class Delta15MinSensor(Delta1MinSensor):
    """15-minute Delta sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Delta 15min"

    @property
    def native_unit_of_measurement(self):
        return self.unit.unit_of_measurement  

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if hasattr(self.coordinator, 'trend_calculator') and self.coordinator.trend_calculator:
            # 1. Check the main trend result for stale data
            trend_info = self.coordinator.trend_calculator.calculate_trend()
            if trend_info.get("trend") == "STALE_DATA":
                return None
            
            # 2. Get the specific delta result
            delta_result = self.coordinator.trend_calculator.calculate_delta_15min()
            
            # 3. Check if a suitable measurement was actually found for the 15-min window
            if not delta_result.get("found", False):
                return None
            
            delta_mgdl = delta_result.get("delta_value", 0.0)
            
            # Convert to selected unit
            if self.unit.unit_of_measurement == "mmol/L":
                delta = delta_mgdl * 0.0555
            else:
                delta = delta_mgdl
            
            return round(delta, 2)
        
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        # Start with parent attributes
        attrs = super().extra_state_attributes
        
        if hasattr(self.coordinator, 'trend_calculator') and self.coordinator.trend_calculator:
            result = self.coordinator.trend_calculator.calculate_delta_15min()
            attrs.update({
                "delta_raw_mgdl": round(result.get("delta_value", 0.0), 2),
                "time_window_min": round(result.get("time_diff", 0.0), 2),
                "measurement_found": result.get("found", False),
                "note": result.get("note", "")
            })
        
        return attrs

# Trend Arrow sensor
class TrendArrowSensor(LibreLinkSensor):
    """Trend Arrow sensor."""

    def __init__(self, coordinator, patient_id):
        """Initialize the sensor."""
        super().__init__(coordinator, patient_id)
        self._attr_icon = "mdi:arrow-up-down"
        self._calculated_trend = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Glucose Trend Arrow"

    @property
    def native_value(self):
        """Return the state of the sensor (the arrow character)."""
        try:
            if hasattr(self.coordinator, 'trend_calculator') and self.coordinator.trend_calculator:
                if self._data.measurement and self._data.measurement.value:
                    # Add measurement to calculator
                    timestamp = self._data.measurement.timestamp
                    if hasattr(timestamp, 'isoformat'):
                        timestamp_str = timestamp.isoformat()
                    else:
                        timestamp_str = str(timestamp)
                    
                    measurement_data = {
                        "Timestamp": timestamp_str,
                        "Value": self._data.measurement.value,
                        "TrendArrow": self._data.measurement.trend
                    }
                    
                    self.coordinator.trend_calculator.add_measurement(measurement_data)
                    trend_info = self.coordinator.trend_calculator.calculate_trend()
                    self._calculated_trend = trend_info
                    
                    # Return the arrow character
                    return trend_info.get("arrow", "→")
        except Exception as e:
            _LOGGER.debug("Trend arrow calculation failed: %s", e)
        
        # Fallback to server trend
        if measurement := self._data.measurement:
            if trend := measurement.trend:
                # Convert server trend to arrow
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
                    # If server provides string trend
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
        # Use trend calculator data for icon, not the original GLUCOSE_TREND_ICON
        if self._calculated_trend:
            trend_category = self._calculated_trend.get("trend", "UNKNOWN").upper()
            
            # Map the trend calculator categories to Material Design Icons
            # This matches what trend_calculator._trend_to_arrow() returns
            icon_mapping = {
                "FALLING_FAST": "mdi:arrow-down-bold",      # ↓
                "FALLING": "mdi:arrow-bottom-right",                # ↘
                "STABLE": "mdi:arrow-right",                # →
                "RISING": "mdi:arrow-top-right",                   # ↗
                "RISING_FAST": "mdi:arrow-up-bold",         # ↑
                "STALE_DATA": "mdi:clock-alert-outline",    # Clock with alert for stale data
                "UNKNOWN": "mdi:help-circle-outline",       # Question mark for unknown
            }
            
            return icon_mapping.get(trend_category, "mdi:help-circle-outline")
        
        # Fallback if calculation hasn't run yet
        return "mdi:help-circle-outline"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = super().extra_state_attributes
        
        if self._calculated_trend:
            attrs.update({
                "trend_description": self._calculated_trend.get("description", "Unknown"),
                "trend_category": self._calculated_trend.get("trend", "UNKNOWN"),
                "trend_rate_mmoll_per_min": round(self._calculated_trend.get("rate", 0.0) * 0.0555, 4),
            })
        
        return attrs

    async def async_update(self):
        """Update the arrow based on latest trend calculation."""
        # This empty method triggers the coordinator to update this sensor
        # The actual calculation happens in native_value property
        pass

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
        self._calculated_trend = None  # Add this for enhanced trend

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return SensorStateClass.MEASUREMENT

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
    def icon(self):
        """Return the icon for the frontend."""
        # Get trend info from calculator (same as EnhancedTrendSensor)
        try:
            if hasattr(self.coordinator, 'trend_calculator') and self.coordinator.trend_calculator:
                if self._data.measurement and self._data.measurement.value:
                    # Convert timestamp to string for trend calculator
                    timestamp = self._data.measurement.timestamp
                    if hasattr(timestamp, 'isoformat'):
                        timestamp_str = timestamp.isoformat()
                    else:
                        timestamp_str = str(timestamp)
                    
                    measurement_data = {
                        "Timestamp": timestamp_str,
                        "Value": self._data.measurement.value,
                        "TrendArrow": self._data.measurement.trend
                    }
                    
                    self.coordinator.trend_calculator.add_measurement(measurement_data)
                    trend_info = self.coordinator.trend_calculator.calculate_trend()
                    self._calculated_trend = trend_info
                    
                    # Use enhanced trend icon mapping
                    trend_category = trend_info.get("trend", "UNKNOWN").upper()
                    icon_mapping = {
                        "FALLING_FAST": "mdi:arrow-down-bold",
                        "FALLING": "mdi:arrow-bottom-right",
                        "STABLE": "mdi:arrow-right",
                        "RISING": "mdi:arrow-top-right",
                        "RISING_FAST": "mdi:arrow-up-bold",
                        "STALE_DATA": "mdi:clock-alert-outline",
                        "UNKNOWN": "mdi:help-circle-outline",
                    }
                    
                    return icon_mapping.get(trend_category, "mdi:help-circle-outline")
        except Exception as e:
            _LOGGER.debug("Enhanced icon calculation failed for MeasurementSensor: %s", e)
        
        # Fallback to original trend icon
        if measurement := self._data.measurement:
            if trend := measurement.trend:
                return GLUCOSE_TREND_ICON.get(trend, GLUCOSE_VALUE_ICON)
        
        return GLUCOSE_VALUE_ICON

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
