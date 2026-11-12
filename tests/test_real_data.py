"""Integration tests on the official files (300,000 trips per city).

The program is compared with a reference that shares no code with it and does not use
pandas: the file is read with the csv module and counted row by row with collections.Counter.
Both must agree on every statistic, for the whole file and for filtered selections.

These tests need the official data (python scripts/fetch_data.py) and are skipped without it.
"""

import contextlib
import csv
import functools
import importlib.util
import io
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

from bike_investigation import (
    CITY_DATA,
    DAYS,
    MONTHS,
    load_data,
    station_stats,
    time_stats,
    trip_duration_stats,
    user_stats,
)

pytestmark = pytest.mark.realdata

MONTH_NAMES = ["january", "february", "march", "april", "may", "june"]
DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

SELECTIONS = [
    ("all", "all"),
    *((month, "all") for month in MONTHS),
    *(("all", day) for day in DAYS),
    ("june", "friday"),
    ("january", "sunday"),
    ("march", "sunday"),  # holds 12 March 2017, the day the clocks moved forward
]


@functools.cache
def read_rows(path):
    """Reference reader: one dictionary per trip, with the same cleaning rules as the program."""
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            start = datetime.fromisoformat(record["Start Time"])
            birth_year = record.get("Birth Year") or None
            rows.append(
                {
                    "month": start.month,
                    "weekday": start.weekday(),
                    "hour": start.hour,
                    "duration": float(record["Trip Duration"]),
                    "start": " ".join(record["Start Station"].split()),
                    "end": " ".join(record["End Station"].split()),
                    "user_type": record["User Type"] or None,
                    "gender": (record["Gender"] or None) if "Gender" in record else "absent",
                    "birth_year": float(birth_year) if birth_year else None,
                    "has_birth_year": "Birth Year" in record,
                }
            )
    return rows


def modes(values):
    counts = Counter(values)
    highest = max(counts.values(), default=0)
    return sorted(value for value, count in counts.items() if count == highest)


def tally(values):
    counts = Counter(value for value in values if value is not None)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def expected_results(rows, month, day):
    """Reference results for one selection."""
    if month != "all":
        rows = [row for row in rows if row["month"] == MONTH_NAMES.index(month) + 1]
    if day != "all":
        rows = [row for row in rows if row["weekday"] == DAY_NAMES.index(day)]
    durations = [row["duration"] for row in rows if 0 <= row["duration"] < math.inf]
    years = [int(row["birth_year"]) for row in rows if row["birth_year"] is not None]
    has_details = rows[0]["has_birth_year"]
    return {
        "rows": len(rows),
        "time": {
            "mostCommonMonth": [MONTH_NAMES[m - 1] for m in modes(row["month"] for row in rows)],
            "mostCommonDayOfWeek": [DAY_NAMES[d] for d in modes(row["weekday"] for row in rows)],
            "mostCommonStartHour": modes(row["hour"] for row in rows),
        },
        "station": {
            "mostCommonStartStation": modes(row["start"] for row in rows),
            "mostCommonEndStation": modes(row["end"] for row in rows),
            "mostCommonTrip": modes((row["start"], row["end"]) for row in rows),
        },
        "duration": {
            "totalTravelTime": math.fsum(durations),
            "meanTravelTime": math.fsum(durations) / len(durations),
        },
        "user": {
            "userTypeCounts": tally(row["user_type"] for row in rows),
            "genderCounts": tally(row["gender"] for row in rows) if has_details else None,
            "earliestBirthYear": min(years, default=None),
            "mostRecentBirthYear": max(years, default=None),
            "mostCommonBirthYear": modes(years) if years else [],
        },
    }


def quiet(function, df):
    with contextlib.redirect_stdout(io.StringIO()):
        return function(df)


def test_the_files_are_the_official_ones(official_data):
    """Same SHA-256 as the archive of the fulll repository at the pinned commit."""
    spec = importlib.util.spec_from_file_location(
        "fetch_data", Path(__file__).parent.parent / "scripts" / "fetch_data.py"
    )
    fetch_data = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetch_data)
    assert fetch_data.in_place()


@pytest.mark.parametrize("city", CITY_DATA)
def test_every_trip_is_loaded(official_data, city):
    df = load_data(city, "all", "all")
    assert len(df) == 300_000
    assert df["Start Time"].notna().all()
    assert df["Start Time"].dt.year.eq(2017).all()
    assert set(df["Start Time"].dt.month) == {1, 2, 3, 4, 5, 6}


@pytest.mark.parametrize("city", CITY_DATA)
@pytest.mark.parametrize(("month", "day"), SELECTIONS, ids="/".join)
def test_program_and_reference_agree(official_data, city, month, day):
    expected = expected_results(read_rows(official_data / CITY_DATA[city]), month, day)

    df = load_data(city, month, day)

    assert len(df) == expected["rows"]
    assert quiet(time_stats, df) == expected["time"]
    assert quiet(station_stats, df) == expected["station"]
    assert quiet(trip_duration_stats, df) == pytest.approx(expected["duration"], rel=1e-12)
    actual_user = quiet(user_stats, df)
    assert actual_user == expected["user"]
    assert list(actual_user["userTypeCounts"].items()) == list(
        expected["user"]["userTypeCounts"].items()
    )


@pytest.mark.parametrize("city", CITY_DATA)
def test_month_and_day_selections_partition_the_file(official_data, city):
    assert sum(len(load_data(city, month, "all")) for month in MONTHS) == 300_000
    assert sum(len(load_data(city, "all", day)) for day in DAYS) == 300_000
