"""DataUpdateCoordinator for LibreLink."""

from __future__ import annotations

from datetime import timedelta, datetime, timezone

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LibreLinkAPI, LibreLinkAPIAuthenticationError, LibreLinkAPIError, Patient
from .const import DOMAIN, LOGGER, REFRESH_RATE_MIN
from .trend_calculator import TrendCalculator

class LibreLinkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Patient]]):
    """Class to manage fetching data from the API. single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: LibreLinkAPI,
        patient_id: str,
    ) -> None:
        """Initialize."""
        self.api: LibreLinkAPI = api
        self._tracked_patients: set[str] = {patient_id}

        # One TrendCalculator per patient, so a coordinator tracking multiple
        # patients (same LibreLinkUp account).
        self.trend_calculators: dict[str, TrendCalculator] = {}
        # Trend/delta results, computed once per poll in _async_update_data
        # and read by entities - avoids recomputing (and re-logging) on
        # every property access, which HA can trigger far more than once
        # per poll (icon renders, frontend refreshes, etc.).
        self.trend_results: dict[str, dict] = {}
        self.delta_results: dict[str, dict] = {}
        # Per-patient 24-hour history for longer-term metrics (e.g., TIR)
        self.history_24h: dict[str, list] = {}

        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=REFRESH_RATE_MIN),
        )

    def register_patient(self, patient_id: str) -> None:
        """Register a new patient to track."""
        self._tracked_patients.add(patient_id)

    def unregister_patient(self, patient_id: str) -> None:
        """Unregister a patient to track."""
        self._tracked_patients.remove(patient_id)
        self.trend_calculators.pop(patient_id, None)
        self.trend_results.pop(patient_id, None)
        self.delta_results.pop(patient_id, None)
        self.history_24h.pop(patient_id, None)

    @property
    def tracked_patients(self) -> int:
        """Return the number of tracked patients."""
        return len(self._tracked_patients)

    async def _async_update_data(self):
        """Update data via library."""
        # Get the list of patients from API. Translate API-level failures into
        # what DataUpdateCoordinator expects: ConfigEntryAuthFailed triggers HA's reauth flow
        try:
            patients_list = await self.api.async_get_data()
        except LibreLinkAPIAuthenticationError as err:
            raise ConfigEntryAuthFailed("Invalid LibreLinkUp credentials") from err
        except LibreLinkAPIError as err:
            raise UpdateFailed(f"Error communicating with LibreLinkUp: {err}") from err

        # Convert to dictionary for return
        patients_dict = {patient.id: patient for patient in patients_list}

        for patient in patients_list:
            if patient.id not in self._tracked_patients:
                continue
            if not (patient.measurement and patient.measurement.value):
                continue

            # Convert timestamp to string if it's a datetime object
            timestamp = patient.measurement.timestamp
            if hasattr(timestamp, 'isoformat'):
                timestamp_str = timestamp.isoformat()
            else:
                timestamp_str = str(timestamp)

            measurement_dict = {
                "Timestamp": timestamp_str,
                "Value": patient.measurement.value,
                "TrendArrow": patient.measurement.trend
            }

            calculator = self.trend_calculators.setdefault(
                patient.id, TrendCalculator(max_history=60)
            )
            calculator.add_measurement(measurement_dict)
            LOGGER.debug(
                "Added measurement for patient %s to trend calculator. Value: %s mg/dL, Time: %s",
                patient.id, patient.measurement.value, timestamp_str
            )

            # Compute trend/delta once per poll, centrally, so entities just
            # read cached results instead of triggering calculation from
            # their own property getters.
            self.trend_results[patient.id] = calculator.calculate_trend()
            self.delta_results[patient.id] = {
                "1min": calculator.calculate_delta_1min(),
                "5min": calculator.calculate_delta_5min(),
                "15min": calculator.calculate_delta_15min(),
            }

            # Also append to per-patient 24h history
            try:
                ts = timestamp
                if isinstance(ts, str):
                    if ts.endswith("Z"):
                        ts = ts[:-1] + "+00:00"
                    parsed = datetime.fromisoformat(ts)
                elif isinstance(ts, datetime):
                    parsed = ts
                else:
                    parsed = datetime.now(timezone.utc)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
            except Exception:
                parsed = datetime.now(timezone.utc)

            patient_hist = self.history_24h.setdefault(patient.id, [])
            patient_hist.append({"timestamp": parsed, "value": patient.measurement.value})

            # Prune entries older than 24 hours
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            self.history_24h[patient.id] = [m for m in patient_hist if m["timestamp"] > cutoff]

        return patients_dict
