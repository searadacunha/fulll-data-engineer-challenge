"""End-to-end results on the synthetic files: load_data() followed by the four statistics.

Every expected figure was computed by hand from the rows of tests/data. For chicago.csv:

    id   start (2017)       weekday  dur.  from        to          user        gender  born
    101  01-02 08:05:10     Mon       600  Alpha St    Bravo Ave   Subscriber  Male    1990
    102  01-09 08:30:00     Mon       900  Alpha St    Bravo Ave   Subscriber  Female  1985
    103  01-02 17:45:00     Mon       300  Bravo Ave   Alpha St    Customer
    104  02-07 17:10:00     Tue       450  Bravo Ave   Alpha St    Subscriber  Male    1990
    105  02-07 08:55:00     Tue      1200  Charlie Sq  Delta Rd    Subscriber  Male    1962
    106  03-01 12:00:00     Wed      1500  Charlie Sq  Delta Rd    Subscriber  Female  1985
    107  03-08 12:30:00     Wed        60  Charlie Sq  Delta Rd    Customer
    108  05-01 08:00:00     Mon      3600  Alpha St    Charlie Sq  Subscriber  Male    1990
    109  06-30 23:59:59     Fri      1800  Alpha St    Alpha St    Subscriber  Female  1899
    110  06-05 17:00:00     Mon       240  Delta Rd    Bravo Ave   Customer
    111  01-08 09:15:00     Sun       350  Delta Rd    Bravo Ave   Dependent   Male    2001

The set is built so that shortcuts give a wrong answer: the busiest start station (Alpha St)
and the busiest end station (Bravo Ave) do not form the busiest trip (Charlie Sq to Delta Rd,
3 trips), and Alpha/Bravo would win with 4 trips if the direction were ignored.
"""

import pytest

from bike_investigation import (
    load_data,
    station_stats,
    time_stats,
    trip_duration_stats,
    user_stats,
)

pytestmark = pytest.mark.usefixtures("synthetic_data")

CASES = {
    ("chicago", "all", "all"): {
        "time": {
            "mostCommonMonth": ["january"],  # 4 trips, against 2 in February, March and June
            "mostCommonDayOfWeek": ["monday"],  # 5 trips
            "mostCommonStartHour": [8],  # 4 trips, against 3 at 17:00
        },
        "station": {
            "mostCommonStartStation": ["Alpha St"],  # 4, Charlie Sq 3
            "mostCommonEndStation": ["Bravo Ave"],  # 4, Alpha St and Delta Rd 3
            "mostCommonTrip": [("Charlie Sq", "Delta Rd")],  # 3
        },
        "duration": {"totalTravelTime": 11000.0, "meanTravelTime": 1000.0},  # 11 trips
        "user": {
            "userTypeCounts": {"Subscriber": 7, "Customer": 3, "Dependent": 1},
            "genderCounts": {"Male": 5, "Female": 3},  # 3 customers without gender
            "earliestBirthYear": 1899,
            "mostRecentBirthYear": 2001,
            "mostCommonBirthYear": [1990],  # 3 times, 1985 twice
        },
    },
    ("chicago", "january", "all"): {  # rows 101, 102, 103 and 111
        "time": {
            "mostCommonMonth": ["january"],
            "mostCommonDayOfWeek": ["monday"],
            "mostCommonStartHour": [8],
        },
        "station": {
            "mostCommonStartStation": ["Alpha St"],
            "mostCommonEndStation": ["Bravo Ave"],
            "mostCommonTrip": [("Alpha St", "Bravo Ave")],
        },
        "duration": {"totalTravelTime": 2150.0, "meanTravelTime": 537.5},
        "user": {
            "userTypeCounts": {"Subscriber": 2, "Customer": 1, "Dependent": 1},
            "genderCounts": {"Male": 2, "Female": 1},
            "earliestBirthYear": 1985,
            "mostRecentBirthYear": 2001,
            "mostCommonBirthYear": [1985, 1990, 2001],  # one each
        },
    },
    ("chicago", "february", "all"): {  # rows 104 and 105: everything ties
        "time": {
            "mostCommonMonth": ["february"],
            "mostCommonDayOfWeek": ["tuesday"],
            "mostCommonStartHour": [8, 17],
        },
        "station": {
            "mostCommonStartStation": ["Bravo Ave", "Charlie Sq"],
            "mostCommonEndStation": ["Alpha St", "Delta Rd"],
            "mostCommonTrip": [("Bravo Ave", "Alpha St"), ("Charlie Sq", "Delta Rd")],
        },
        "duration": {"totalTravelTime": 1650.0, "meanTravelTime": 825.0},
        "user": {
            "userTypeCounts": {"Subscriber": 2},
            "genderCounts": {"Male": 2},
            "earliestBirthYear": 1962,
            "mostRecentBirthYear": 1990,
            "mostCommonBirthYear": [1962, 1990],
        },
    },
    ("chicago", "all", "monday"): {  # rows 101, 102, 103, 108 and 110
        "time": {
            "mostCommonMonth": ["january"],
            "mostCommonDayOfWeek": ["monday"],
            "mostCommonStartHour": [8],
        },
        "station": {
            "mostCommonStartStation": ["Alpha St"],
            "mostCommonEndStation": ["Bravo Ave"],
            "mostCommonTrip": [("Alpha St", "Bravo Ave")],
        },
        "duration": {"totalTravelTime": 5640.0, "meanTravelTime": 1128.0},
        "user": {
            "userTypeCounts": {"Subscriber": 3, "Customer": 2},
            "genderCounts": {"Male": 2, "Female": 1},
            "earliestBirthYear": 1985,
            "mostRecentBirthYear": 1990,
            "mostCommonBirthYear": [1990],
        },
    },
    ("chicago", "june", "friday"): {  # row 109 alone, a trip back to its start station
        "time": {
            "mostCommonMonth": ["june"],
            "mostCommonDayOfWeek": ["friday"],
            "mostCommonStartHour": [23],
        },
        "station": {
            "mostCommonStartStation": ["Alpha St"],
            "mostCommonEndStation": ["Alpha St"],
            "mostCommonTrip": [("Alpha St", "Alpha St")],
        },
        "duration": {"totalTravelTime": 1800.0, "meanTravelTime": 1800.0},
        "user": {
            "userTypeCounts": {"Subscriber": 1},
            "genderCounts": {"Female": 1},
            "earliestBirthYear": 1899,
            "mostRecentBirthYear": 1899,
            "mostCommonBirthYear": [1899],
        },
    },
    # washington.csv: 4 trips, durations 60.5 + 120.25 + 300.0 + 19.25, no user details.
    ("washington", "all", "all"): {
        "time": {
            "mostCommonMonth": ["april"],
            "mostCommonDayOfWeek": ["monday"],
            "mostCommonStartHour": [7],
        },
        "station": {
            "mostCommonStartStation": ["Echo Circle"],
            "mostCommonEndStation": ["Echo Circle", "Foxtrot Plaza"],
            "mostCommonTrip": [("Echo Circle", "Foxtrot Plaza")],
        },
        "duration": {"totalTravelTime": 500.0, "meanTravelTime": 125.0},
        "user": {
            "userTypeCounts": {"Subscriber": 3, "Customer": 1},
            "genderCounts": None,
            "earliestBirthYear": None,
            "mostRecentBirthYear": None,
            "mostCommonBirthYear": [],
        },
    },
    # new_york_city.csv: 7 rows with the defects listed in test_dirty_rows_are_counted.
    ("new york city", "all", "all"): {
        "time": {  # 4 readable start times: two Thursdays of May at 09:xx, two Fridays of June
            "mostCommonMonth": ["may", "june"],
            "mostCommonDayOfWeek": ["thursday", "friday"],
            "mostCommonStartHour": [9, 15],
        },
        "station": {
            "mostCommonStartStation": ["Wood St & Hubbard St"],  # 4 against 3
            "mostCommonEndStation": ["Damen Ave & Chicago Ave", "Wood St & Hubbard St"],  # 3 each
            "mostCommonTrip": [("Wood St & Hubbard St", "Damen Ave & Chicago Ave")],  # 3
        },
        "duration": {"totalTravelTime": 1521.0, "meanTravelTime": 380.25},  # 321, 600, 600, 0
        "user": {
            "userTypeCounts": {"Subscriber": 4, "Customer": 2},
            "genderCounts": {"Male": 4, "Female": 2},
            "earliestBirthYear": 1980,
            "mostRecentBirthYear": 2999,  # reported as recorded, and flagged
            "mostCommonBirthYear": [1992],
        },
    },
}


@pytest.mark.parametrize(("filters", "expected"), CASES.items(), ids=" / ".join)
def test_results_match_the_hand_computation(filters, expected):
    df = load_data(*filters)

    assert time_stats(df) == expected["time"]
    assert station_stats(df) == expected["station"]
    assert trip_duration_stats(df) == expected["duration"]
    assert user_stats(df) == expected["user"]


def test_dirty_rows_are_counted(capsys):
    """new_york_city.csv, row by row:

    1  start "23/06/2017 15:09:32", the day-first layout of the statement: read
    2  birth year 2999: kept, and flagged since the rider would not be born yet
    3  start "06/23/2017 15:40:00", month first: not read (never guessed)
    4  duration -60: not used; no gender and no birth year
    5  no duration, no user type, birth year 1985.5: not used
    6  start "not a date", duration "abc", no end station, no birth year
    7  start "2017-13-01 08:00:00" (month 13): not read; duration 0: used
    """
    df = load_data("new york city", "all", "all")
    for stats in (time_stats, station_stats, trip_duration_stats, user_stats):
        stats(df)

    out = capsys.readouterr().out
    assert "Note: 3 trip(s) without a readable start time left out." in out
    assert "Note: 3 trip(s) without a usable duration left out." in out
    assert out.count("(1 trip(s) with no value recorded)") == 2  # user type, then gender
    assert "(1 trip(s) by a rider not yet born or older than 100, kept as recorded)" in out
