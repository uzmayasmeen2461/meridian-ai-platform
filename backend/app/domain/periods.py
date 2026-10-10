import re
from dataclasses import dataclass
from datetime import date, timedelta


DATA_WINDOW_END = date(2026, 9, 28)
PERIOD_PATTERN = re.compile(r"^(last_7_days|last_30_days|\d{4}-W\d{2}|\d{4}-\d{2})$")


@dataclass(frozen=True)
class PeriodRange:
    label: str
    start: date
    end_exclusive: date


def parse_period(value: str) -> PeriodRange:
    if not PERIOD_PATTERN.match(value):
        raise ValueError("Unsupported period format.")

    if value == "last_7_days":
        return PeriodRange(value, DATA_WINDOW_END - timedelta(days=7), DATA_WINDOW_END)
    if value == "last_30_days":
        return PeriodRange(value, DATA_WINDOW_END - timedelta(days=30), DATA_WINDOW_END)
    if "-W" in value:
        year_text, week_text = value.split("-W", 1)
        try:
            start = date.fromisocalendar(int(year_text), int(week_text), 1)
        except ValueError as exc:
            raise ValueError("Unsupported ISO week.") from exc
        return PeriodRange(value, start, start + timedelta(days=7))

    year_text, month_text = value.split("-", 1)
    year = int(year_text)
    month = int(month_text)
    if month < 1 or month > 12:
        raise ValueError("Unsupported month.")
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return PeriodRange(value, start, end)


def iso_week_start(value: date) -> date:
    return value - timedelta(days=value.isoweekday() - 1)
