"""Units of measurement for LibreLink integration."""
from collections.abc import Callable
from dataclasses import dataclass

MGDL_PER_MMOLL = 18


def mgdl_to_mmoll(value: float) -> float:
    """Convert a mg/dL value (or rate) to mmol/L."""
    return value / MGDL_PER_MMOLL


def mmoll_to_mgdl(value: float) -> float:
    """Convert a mmol/L value (or rate) to mg/dL."""
    return value * MGDL_PER_MMOLL


@dataclass
class UnitOfMeasurement:
    """Unit of measurement for LibreLink integration."""

    unit_of_measurement: str
    suggested_display_precision: int
    from_mg_per_dl: Callable[[float], float]
    to_mg_per_dl: Callable[[float], float]


UNITS_OF_MEASUREMENT = (
    UnitOfMeasurement(
        unit_of_measurement="mg/dL",
        suggested_display_precision=0,
        from_mg_per_dl=lambda x: x,
        to_mg_per_dl=lambda x: x,
    ),
    UnitOfMeasurement(
        unit_of_measurement="mmol/L",
        suggested_display_precision=1,
        from_mg_per_dl=mgdl_to_mmoll,
        to_mg_per_dl=mmoll_to_mgdl,
    ),
)
