"""DataUpdateCoordinator for LibreLink."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import LibreLinkAPI, Patient
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
        
        # Initialize the trend calculator
        self.trend_calculator = TrendCalculator(max_history=60)  # Store up to 60 measurements

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

    @property
    def tracked_patients(self) -> int:
        """Return the number of tracked patients."""
        return len(self._tracked_patients)

    async def _async_update_data(self):
        """Update data via library."""
        # Get the list of patients from API
        patients_list = await self.api.async_get_data()
        
        # Convert to dictionary for return
        patients_dict = {patient.id: patient for patient in patients_list}
        
        # Feed measurements to trend calculator
        if hasattr(self, 'trend_calculator') and self.trend_calculator:
            for patient in patients_list:
                if patient.id in self._tracked_patients:
                    if patient.measurement and patient.measurement.value:
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
                        self.trend_calculator.add_measurement(measurement_dict)
                        LOGGER.debug(
                            "Added measurement for patient %s to trend calculator. Value: %s mg/dL, Time: %s",
                            patient.id, patient.measurement.value, timestamp_str
                        )
        
        return patients_dict