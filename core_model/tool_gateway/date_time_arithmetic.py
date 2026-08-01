"""Phase 20 Step 20 -- deterministic date/time arithmetic.

Only ISO-8601 (`YYYY-MM-DD`) dates are accepted for calendar-date
math -- a locale-ambiguous form like `01/02/2026` (January 2 or
February 1?) is rejected as `ambiguous_date_format` rather than
guessed. Calendar-date-only operations never need a timezone (Step
20's own "timezone-free duration calculation" scope); an input that
also carries a time-of-day component is timezone-sensitive and
requires an explicit UTC offset or `Z` suffix, or is rejected as
`timezone_required`. No live "current time" is ever returned -- every
operation is anchored to caller-supplied dates only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

MAX_DAY_DELTA = 366_000  # ~1000 years, bounds "huge date range" abuse

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AMBIGUOUS_LOCALE_DATE_RE = re.compile(r"^\d{1,2}[/.]\d{1,2}[/.]\d{2,4}$")
_HAS_TIME_COMPONENT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
_TIMEZONE_SUFFIX_RE = re.compile(r"(Z|[+-]\d{2}:\d{2})$")


class DateArithmeticError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class DateResult:
    operation: str
    inputs: dict[str, str | int]
    result_date: str | None
    result_days: int | None


def _parse_iso_date(value: str) -> date:
    value = value.strip()
    if _HAS_TIME_COMPONENT_RE.match(value):
        if not _TIMEZONE_SUFFIX_RE.search(value):
            raise DateArithmeticError("timezone_required")
        value = value.split("T", 1)[0]
    if _AMBIGUOUS_LOCALE_DATE_RE.match(value):
        raise DateArithmeticError("ambiguous_date_format")
    if not _ISO_DATE_RE.match(value):
        raise DateArithmeticError("invalid_date_format")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise DateArithmeticError("invalid_date") from exc


def add_days(iso_date: str, days: int) -> DateResult:
    if abs(days) > MAX_DAY_DELTA:
        raise DateArithmeticError("range_too_large")
    base = _parse_iso_date(iso_date)
    try:
        result = base + timedelta(days=days)
    except OverflowError as exc:
        raise DateArithmeticError("range_too_large") from exc
    return DateResult(
        operation="add_days",
        inputs={"date": iso_date, "days": days},
        result_date=result.isoformat(),
        result_days=None,
    )


def add_weeks(iso_date: str, weeks: int) -> DateResult:
    if abs(weeks) * 7 > MAX_DAY_DELTA:
        raise DateArithmeticError("range_too_large")
    result = add_days(iso_date, weeks * 7)
    return DateResult(
        operation="add_weeks",
        inputs={"date": iso_date, "weeks": weeks},
        result_date=result.result_date,
        result_days=None,
    )


def date_difference(iso_date_a: str, iso_date_b: str) -> DateResult:
    date_a = _parse_iso_date(iso_date_a)
    date_b = _parse_iso_date(iso_date_b)
    delta_days = (date_b - date_a).days
    if abs(delta_days) > MAX_DAY_DELTA:
        raise DateArithmeticError("range_too_large")
    return DateResult(
        operation="date_difference",
        inputs={"date_a": iso_date_a, "date_b": iso_date_b},
        result_date=None,
        result_days=delta_days,
    )


__all__ = ["DateArithmeticError", "DateResult", "add_days", "add_weeks", "date_difference"]
