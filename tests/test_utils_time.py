from datetime import date, time as time_t

from utils.time import iso_from_date_time, to_iso_minutes_string


def test_iso_from_date_time_minute_precision():
    d = date(2026, 2, 1)
    t = time_t(13, 45, 59)
    assert iso_from_date_time(d, t) == "2026-02-01T13:45"


def test_to_iso_minutes_string_parses_and_rounds_to_minutes():
    assert to_iso_minutes_string("2026-02-01 13:45:59") == "2026-02-01T13:45"
    assert to_iso_minutes_string("2026-02-01T00:00:00Z") == "2026-02-01T00:00"


def test_to_iso_minutes_string_unparseable_returns_original():
    assert to_iso_minutes_string("n/a") == "n/a"

