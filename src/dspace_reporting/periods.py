"""Resolve reporting periods from configuration values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
YEAR_RE = re.compile(r"^\d{4}$")


@dataclass(frozen=True, order=True)
class YearMonth:
    year: int
    month: int

    @classmethod
    def parse(cls, value: str | int) -> "YearMonth":
        text = str(value).strip()
        if YEAR_RE.match(text):
            return cls(int(text), 1)
        if MONTH_RE.match(text):
            year, month = text.split("-")
            return cls(int(year), int(month))
        raise ValueError(f"Invalid period value {value!r}. Use YYYY or YYYY-MM.")

    @classmethod
    def from_date(cls, value: date) -> "YearMonth":
        return cls(value.year, value.month)

    def previous(self) -> "YearMonth":
        if self.month == 1:
            return YearMonth(self.year - 1, 12)
        return YearMonth(self.year, self.month - 1)

    def next(self) -> "YearMonth":
        if self.month == 12:
            return YearMonth(self.year + 1, 1)
        return YearMonth(self.year, self.month + 1)

    @property
    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def label(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def resolve_months(
    start: str | int | None,
    end: str | int | None,
    today: date | None = None,
    future_start_policy: str = "current_year",
) -> list[str]:
    """Return month labels from start through end, excluding current/future month.

    If ``end`` is omitted, the last month is the month before ``today``.
    If ``start`` is omitted, January of ``today.year`` is used.
    """

    today = today or date.today()
    latest_allowed = YearMonth.from_date(today).previous()

    if start is None:
        start_month = YearMonth(today.year, 1)
    else:
        start_month = YearMonth.parse(start)

    if start_month > latest_allowed:
        if future_start_policy == "current_year":
            start_month = YearMonth(today.year, 1)
        elif future_start_policy == "error":
            raise ValueError(
                f"Start period {start_month.label} is after latest complete month "
                f"{latest_allowed.label}."
            )
        else:
            raise ValueError(
                "future_start_policy must be either 'current_year' or 'error'."
            )

    end_month = YearMonth.parse(end) if end is not None else latest_allowed
    if end_month > latest_allowed:
        end_month = latest_allowed

    if start_month > end_month:
        return []

    months: list[str] = []
    current = start_month
    while current <= end_month:
        months.append(current.label)
        current = current.next()
    return months


def reference_month_date(reference_month: str) -> str:
    """Return the first day of a YYYY-MM label as an ISO date string."""

    return YearMonth.parse(reference_month).first_day.isoformat()

