"""Property-based tests: random small frames, compared with a plain Python recomputation.

The example tests pin known cases. These ones look for the cases nobody thought of: ties in
any column, rows in any order, missing values anywhere, numbers stored as text, and so on.
The reference implementation below uses collections.Counter and shares no code with the
program.
"""

import contextlib
import io
import math
from collections import Counter
from datetime import datetime
from unittest import mock

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bike_investigation import (
    CITY_DATA,
    DAYS,
    MONTHS,
    get_filters,
    station_stats,
    time_stats,
    trip_duration_stats,
    user_stats,
)

MONTH_NAMES = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Few distinct values on purpose: ties and repeated values are where the bugs hide.
instants = st.one_of(
    st.sampled_from(
        [
            datetime(2017, 1, 1, 9, 7, 57),
            datetime(2017, 1, 2, 9, 7, 57),
            datetime(2017, 3, 12, 2, 30, 0),
            datetime(2017, 6, 30, 23, 59, 59),
            datetime(2017, 12, 31, 0, 0, 0),
        ]
    ),
    st.datetimes(min_value=datetime(2016, 1, 1), max_value=datetime(2018, 12, 31)).map(
        lambda instant: instant.replace(microsecond=0)
    ),
)
start_times = st.one_of(
    st.none(),
    st.sampled_from(["not a date", "06/23/2017 15:09:32", "2017-02-30 10:00:00", ""]),
    instants.map(lambda instant: instant.strftime("%Y-%m-%d %H:%M:%S")),
    instants.map(lambda instant: instant.strftime("%d/%m/%Y %H:%M:%S")),
)
durations = st.one_of(
    st.none(),
    st.integers(min_value=-5, max_value=5000),
    st.floats(min_value=-10, max_value=1e7, allow_nan=False),
    st.sampled_from([float("nan"), float("inf"), float("-inf"), "abc", "12", "7.5", ""]),
)
stations = st.sampled_from(["A", "B", "C", None])
birth_years = st.one_of(
    st.none(),
    st.integers(min_value=1880, max_value=2020),
    st.sampled_from([1990.0, 1990.5, float("nan"), float("inf"), "1985", "unknown"]),
)
rows = st.fixed_dictionaries(
    {
        "Start Time": start_times,
        "Trip Duration": durations,
        "Start Station": stations,
        "End Station": stations,
        "User Type": st.sampled_from(["Subscriber", "Customer", None]),
        "Gender": st.sampled_from(["Male", "Female", None]),
        "Birth Year": birth_years,
    }
)


def quiet(function, *args):
    """Call a function of the program without its printed report."""
    with contextlib.redirect_stdout(io.StringIO()):
        return function(*args)


def modes(values):
    """Reference: every most frequent value, sorted."""
    counts = Counter(values)
    highest = max(counts.values(), default=0)
    return sorted(value for value, count in counts.items() if count == highest)


def as_number(value):
    """Reference: the float behind a cell, or None when it is missing or not a number."""
    try:
        return None if value is None else float(value)
    except ValueError:
        return None


def read_instant(text):
    """Reference: a timestamp in one of the two accepted layouts, else None."""
    for layout in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text or "", layout)
        except ValueError:
            continue
    return None


def expected_results(records):
    """Reference results for a list of row dictionaries."""
    if not records:
        return {
            "time": {"mostCommonMonth": [], "mostCommonDayOfWeek": [], "mostCommonStartHour": []},
            "station": {
                "mostCommonStartStation": [],
                "mostCommonEndStation": [],
                "mostCommonTrip": [],
            },
            "duration": {"totalTravelTime": None, "meanTravelTime": None},
            "user": {
                "userTypeCounts": None,
                "genderCounts": None,
                "earliestBirthYear": None,
                "mostRecentBirthYear": None,
                "mostCommonBirthYear": [],
            },
        }

    instants_read = [read_instant(record["Start Time"]) for record in records]
    instants_read = [instant for instant in instants_read if instant is not None]
    usable = [as_number(record["Trip Duration"]) for record in records]
    usable = [value for value in usable if value is not None and 0 <= value < math.inf]
    years = [as_number(record["Birth Year"]) for record in records]
    years = [
        int(year) for year in years if year is not None and math.isfinite(year) and year % 1 == 0
    ]

    def counts(column):
        tally = Counter(record[column] for record in records if record[column] is not None)
        return dict(sorted(tally.items(), key=lambda item: (-item[1], item[0])))

    def station_modes(column):
        return modes(record[column] for record in records if record[column] is not None)

    return {
        "time": {
            "mostCommonMonth": [MONTH_NAMES[m - 1] for m in modes(i.month for i in instants_read)],
            "mostCommonDayOfWeek": [
                DAY_NAMES[d] for d in modes(i.weekday() for i in instants_read)
            ],
            "mostCommonStartHour": modes(i.hour for i in instants_read),
        },
        "station": {
            "mostCommonStartStation": station_modes("Start Station"),
            "mostCommonEndStation": station_modes("End Station"),
            "mostCommonTrip": modes(
                (record["Start Station"], record["End Station"])
                for record in records
                if record["Start Station"] is not None and record["End Station"] is not None
            ),
        },
        "duration": {
            "totalTravelTime": math.fsum(usable) if usable else None,
            "meanTravelTime": math.fsum(usable) / len(usable) if usable else None,
        },
        "user": {
            "userTypeCounts": counts("User Type"),
            "genderCounts": counts("Gender"),
            "earliestBirthYear": min(years, default=None),
            "mostRecentBirthYear": max(years, default=None),
            "mostCommonBirthYear": modes(years) if years else [],
        },
    }


def actual_results(df):
    return {
        "time": quiet(time_stats, df),
        "station": quiet(station_stats, df),
        "duration": quiet(trip_duration_stats, df),
        "user": quiet(user_stats, df),
    }


def assert_same_results(actual, expected):
    assert actual["time"] == expected["time"]
    assert actual["station"] == expected["station"]
    assert set(actual["duration"]) == set(expected["duration"])
    for key, value in expected["duration"].items():
        if value is None:
            assert actual["duration"][key] is None
        else:  # the reference sums with math.fsum, pandas with pairwise additions
            assert actual["duration"][key] == pytest.approx(value, rel=1e-9, abs=1e-9)
    assert actual["user"] == expected["user"]
    for key in ("userTypeCounts", "genderCounts"):  # same order too: count, then name
        if expected["user"][key] is not None:
            assert list(actual["user"][key].items()) == list(expected["user"][key].items())


@settings(max_examples=300, deadline=None)
@given(records=st.lists(rows, max_size=25), order=st.randoms(use_true_random=False))
def test_statistics_agree_with_the_reference_whatever_the_rows_and_their_order(records, order):
    expected = expected_results(records)

    assert_same_results(actual_results(pd.DataFrame(records)), expected)

    shuffled = list(records)
    order.shuffle(shuffled)
    assert_same_results(actual_results(pd.DataFrame(shuffled)), expected)


def first_valid(script, choices):
    """Reference for the question loop: skip answers until one is a valid choice."""
    while True:
        answer = " ".join(script.pop(0).split()).casefold()
        if answer in choices:
            return answer


noise = st.lists(st.text(max_size=15), max_size=5)


@settings(max_examples=200, deadline=None)
@given(
    before_city=noise,
    before_month=noise,
    before_day=noise,
    city=st.sampled_from(list(CITY_DATA)),
    month=st.sampled_from(["all", *MONTHS]),
    day=st.sampled_from(["all", *DAYS]),
)
def test_get_filters_never_fails_on_arbitrary_text(
    before_city, before_month, before_day, city, month, day
):
    script = [*before_city, city, *before_month, month, *before_day, day]
    remaining = list(script)
    expected = (
        first_valid(remaining, tuple(CITY_DATA)),
        first_valid(remaining, ("all", *MONTHS)),
        first_valid(remaining, ("all", *DAYS)),
    )

    # Answers past the script raise StopIteration: the test fails if a question is asked too many.
    with mock.patch("builtins.input", side_effect=script):
        assert quiet(get_filters) == expected
