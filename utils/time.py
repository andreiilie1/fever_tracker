from __future__ import annotations

from datetime import date, datetime, time as time_t

import pandas as pd


def iso_from_date_time(d: date, t: time_t) -> str:
    """
    Compose a local naive datetime from date + time and return ISO string
    with minute precision, e.g. '2026-02-01T13:45'.
    """
    dt = datetime.combine(d, t)
    return dt.isoformat(timespec="minutes")


def to_iso_minutes_string(s: str) -> str:
    """
    Parse arbitrary datetime-like string via pandas and reformat to
    'YYYY-MM-DDTHH:MM'. If parsing fails, return original string.
    """
    try:
        dt = pd.to_datetime(s)
    except Exception:
        return str(s)
    return dt.strftime("%Y-%m-%dT%H:%M")

