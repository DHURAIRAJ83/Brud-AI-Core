"""Phase 20 Step 19 -- deterministic unit conversion.

Explicit unit allowlists only -- an unrecognized unit is `invalid_unit`,
never silently guessed. `ton`/`gallon`/`cup` are genuinely ambiguous
(their common definitions differ by 10-20%+ across locales/standards)
and are rejected as `ambiguous_unit` unless the caller specifies an
explicit qualified form (`metric_ton`/`us_ton`/`uk_ton`,
`gallon_us`/`gallon_uk`, `cup_us`/`cup_metric`) -- this tool never
silently assumes a financially material unit. `mile` is treated as the
international statute mile (`nautical_mile` is a distinct, explicit
unit token for the rare case that needs it) -- documented judgment
call: virtually every general-purpose conversion tool treats bare
"mile" this way, and no common definition of "mile" differs
materially enough to justify surprising ordinary users with a
clarification prompt for it the way `ton`/`gallon`/`cup` warrant.
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.tool_gateway import UNIT_CATEGORIES

MAX_CONVERSION_MAGNITUDE = 1e15


class UnitConversionError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ConversionResult:
    value: float
    source_unit: str
    target_unit: str
    result: float
    conversion_formula: str
    category: str


_AMBIGUOUS_UNITS = frozenset({"ton", "tons", "gallon", "gallons", "cup", "cups"})

_LENGTH_TO_METERS = {
    "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
    "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0, "kilometre": 1000.0,
    "kilometres": 1000.0,
    "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
    "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
    "mile": 1609.344, "miles": 1609.344,
    "nautical_mile": 1852.0, "nautical_miles": 1852.0,
    "yard": 0.9144, "yards": 0.9144,
    "foot": 0.3048, "feet": 0.3048, "ft": 0.3048,
    "inch": 0.0254, "inches": 0.0254, "in": 0.0254,
}
_MASS_TO_KG = {
    "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "mg": 0.000001, "milligram": 0.000001, "milligrams": 0.000001,
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237, "pounds": 0.45359237,
    "oz": 0.028349523125, "ounce": 0.028349523125, "ounces": 0.028349523125,
    "metric_ton": 1000.0, "metric_tons": 1000.0, "tonne": 1000.0, "tonnes": 1000.0,
    "us_ton": 907.18474, "uk_ton": 1016.0469088,
}
_VOLUME_TO_LITERS = {
    "l": 1.0, "liter": 1.0, "liters": 1.0, "litre": 1.0, "litres": 1.0,
    "ml": 0.001, "milliliter": 0.001, "milliliters": 0.001, "millilitre": 0.001,
    "gallon_us": 3.785411784, "gallon_uk": 4.54609,
    "cup_us": 0.2365882365, "cup_metric": 0.25,
}
_TIME_TO_SECONDS = {
    "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
    "min": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "day": 86400.0, "days": 86400.0,
    "week": 604800.0, "weeks": 604800.0,
}
_AREA_TO_SQMETERS = {
    "sqm": 1.0, "m2": 1.0, "square_meter": 1.0, "square_meters": 1.0,
    "sqkm": 1_000_000.0, "km2": 1_000_000.0,
    "hectare": 10_000.0, "hectares": 10_000.0,
    "acre": 4046.8564224, "acres": 4046.8564224,
    "sqft": 0.09290304, "ft2": 0.09290304, "square_foot": 0.09290304,
    "sqmile": 2_589_988.110336, "square_mile": 2_589_988.110336,
}
_SPEED_TO_MPS = {
    "mps": 1.0, "m/s": 1.0, "meters_per_second": 1.0,
    "kmh": 0.2777777778, "km/h": 0.2777777778, "kph": 0.2777777778,
    "mph": 0.44704, "miles_per_hour": 0.44704,
}
_DATA_SIZE_TO_BYTES = {
    "b": 1.0, "byte": 1.0, "bytes": 1.0,
    "kb": 1000.0, "kib": 1024.0,
    "mb": 1000.0**2, "mib": 1024.0**2,
    "gb": 1000.0**3, "gib": 1024.0**3,
    "tb": 1000.0**4, "tib": 1024.0**4,
}
_TEMPERATURE_ALIASES = {
    "c": "c", "celsius": "c",
    "f": "f", "fahrenheit": "f",
    "k": "k", "kelvin": "k",
}

_TABLE_BY_CATEGORY: dict[str, dict[str, float]] = {
    "length": _LENGTH_TO_METERS,
    "mass": _MASS_TO_KG,
    "volume": _VOLUME_TO_LITERS,
    "time": _TIME_TO_SECONDS,
    "area": _AREA_TO_SQMETERS,
    "speed": _SPEED_TO_MPS,
    "data_size": _DATA_SIZE_TO_BYTES,
}


def _normalize_unit(unit: str) -> str:
    return unit.strip().lower().replace(" ", "_")


def _category_of(unit_key: str) -> str | None:
    if unit_key in _TEMPERATURE_ALIASES:
        return "temperature"
    for category, table in _TABLE_BY_CATEGORY.items():
        if unit_key in table:
            return category
    return None


def _convert_temperature(value: float, source_key: str, target_key: str) -> float:
    source = _TEMPERATURE_ALIASES[source_key]
    target = _TEMPERATURE_ALIASES[target_key]
    if source == "c":
        celsius = value
    elif source == "f":
        celsius = (value - 32.0) * 5.0 / 9.0
    else:
        celsius = value - 273.15
    if target == "c":
        return celsius
    if target == "f":
        return celsius * 9.0 / 5.0 + 32.0
    return celsius + 273.15


def convert(value: float, source_unit: str, target_unit: str) -> ConversionResult:
    if abs(value) > MAX_CONVERSION_MAGNITUDE:
        raise UnitConversionError("value_out_of_range")

    source_key = _normalize_unit(source_unit)
    target_key = _normalize_unit(target_unit)

    if source_key in _AMBIGUOUS_UNITS or target_key in _AMBIGUOUS_UNITS:
        raise UnitConversionError("ambiguous_unit")

    source_category = _category_of(source_key)
    target_category = _category_of(target_key)
    if source_category is None or target_category is None:
        raise UnitConversionError("invalid_unit")
    if source_category != target_category:
        raise UnitConversionError("mismatched_unit_categories")

    assert source_category in UNIT_CATEGORIES or source_category == "temperature"

    if source_category == "temperature":
        result = _convert_temperature(value, source_key, target_key)
        formula = f"{source_key}_to_{target_key}"
    else:
        table = _TABLE_BY_CATEGORY[source_category]
        base_value = value * table[source_key]
        result = base_value / table[target_key]
        formula = f"value * {table[source_key]} / {table[target_key]}"

    return ConversionResult(
        value=value,
        source_unit=source_key,
        target_unit=target_key,
        result=result,
        conversion_formula=formula,
        category=source_category,
    )


__all__ = ["ConversionResult", "UnitConversionError", "convert"]
