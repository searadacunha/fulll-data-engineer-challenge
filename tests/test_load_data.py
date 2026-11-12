"""load_data(): reading, typing, cleaning and filtering, on the synthetic files of tests/data.

tests/data/chicago.csv has 11 trips. Start dates, with their weekday in 2017:

    January   2 (Mon) x2, 8 (Sun), 9 (Mon)       4 trips
    February  7 (Tue) x2                         2 trips
    March     1 (Wed), 8 (Wed)                   2 trips
    May       1 (Mon)                            1 trip
    June      5 (Mon), 30 (Fri)                  2 trips
"""

import pandas as pd
import pytest

import bike_investigation
from bike_investigation import (
    DAYS,
    MONTHS,
    load_data,
    station_stats,
    time_stats,
    trip_duration_stats,
    user_stats,
)

TRIPS_PER_MONTH = {"january": 4, "february": 2, "march": 2, "april": 0, "may": 1, "june": 2}
TRIPS_PER_DAY = {
    "monday": 5,
    "tuesday": 2,
    "wednesday": 2,
    "thursday": 0,
    "friday": 1,
    "saturday": 0,
    "sunday": 1,
}
TRIPS_PER_MONTH_AND_DAY = {
    ("january", "monday"): 3,
    ("january", "sunday"): 1,
    ("february", "tuesday"): 2,
    ("march", "wednesday"): 2,
    ("may", "monday"): 1,
    ("june", "monday"): 1,
    ("june", "friday"): 1,
}

pytestmark = pytest.mark.usefixtures("synthetic_data")


def test_loads_every_row_with_typed_columns():
    df = load_data("chicago", "all", "all")

    assert len(df) == 11
    assert list(df.columns) == [
        "Start Time",
        "End Time",
        "Trip Duration",
        "Start Station",
        "End Station",
        "User Type",
        "Gender",
        "Birth Year",
    ]  # the unnamed row id of the file is not loaded
    assert pd.api.types.is_datetime64_any_dtype(df["Start Time"])
    assert pd.api.types.is_datetime64_any_dtype(df["End Time"])
    assert pd.api.types.is_numeric_dtype(df["Trip Duration"])
    assert pd.api.types.is_numeric_dtype(df["Birth Year"])
    for column in ("Start Station", "End Station", "User Type", "Gender"):
        assert isinstance(df[column].dtype, pd.CategoricalDtype)
    assert df["Start Time"].iloc[0] == pd.Timestamp(2017, 1, 2, 8, 5, 10)
    assert df["End Time"].iloc[8] == pd.Timestamp(2017, 7, 1, 0, 29, 59)
    assert df["Trip Duration"].tolist() == [
        600,
        900,
        300,
        450,
        1200,
        1500,
        60,
        3600,
        1800,
        240,
        350,
    ]


def test_station_names_lose_their_stray_spaces():
    # Row 107 of the file reads "Charlie Sq " with a trailing space.
    df = load_data("chicago", "all", "all")
    assert sorted(df["Start Station"].unique()) == [
        "Alpha St",
        "Bravo Ave",
        "Charlie Sq",
        "Delta Rd",
    ]
    assert (df["Start Station"] == "Charlie Sq").sum() == 3


def test_a_file_without_row_id_gender_and_birth_year_loads_too():
    df = load_data("washington", "all", "all")

    assert list(df.columns) == [
        "Start Time",
        "End Time",
        "Trip Duration",
        "Start Station",
        "End Station",
        "User Type",
    ]
    assert df["Trip Duration"].tolist() == [60.5, 120.25, 300.0, 19.25]


@pytest.mark.parametrize(("month", "expected"), TRIPS_PER_MONTH.items())
def test_month_filter(month, expected):
    df = load_data("chicago", month, "all")
    assert len(df) == expected
    assert set(df["Start Time"].dt.month) <= {MONTHS.index(month) + 1}


@pytest.mark.parametrize(("day", "expected"), TRIPS_PER_DAY.items())
def test_day_filter(day, expected):
    df = load_data("chicago", "all", day)
    assert len(df) == expected
    assert set(df["Start Time"].dt.day_name().str.lower()) <= {day}


@pytest.mark.parametrize("month", MONTHS)
@pytest.mark.parametrize("day", DAYS)
def test_month_and_day_filters_combine(month, day):
    df = load_data("chicago", month, day)
    assert len(df) == TRIPS_PER_MONTH_AND_DAY.get((month, day), 0)
    assert set(df["Start Time"].dt.month) <= {MONTHS.index(month) + 1}
    assert set(df["Start Time"].dt.day_name().str.lower()) <= {day}


def test_the_filters_partition_the_file():
    everything = load_data("chicago", "all", "all")
    assert sum(len(load_data("chicago", month, "all")) for month in MONTHS) == len(everything)
    assert sum(len(load_data("chicago", "all", day)) for day in DAYS) == len(everything)
    assert sum(TRIPS_PER_MONTH_AND_DAY.values()) == len(everything)


def test_a_filtered_frame_is_renumbered_from_zero():
    assert load_data("chicago", "june", "all").index.tolist() == [0, 1]


def test_arguments_are_cleaned_like_typed_answers():
    df = load_data(" CHICAGO ", "January", "  monday")
    assert len(df) == 3
    assert len(load_data("New  York City", "ALL", "all")) == 7


@pytest.mark.parametrize(
    ("city", "month", "day", "message"),
    [
        ("paris", "all", "all", "Unknown city 'paris'"),
        ("", "all", "all", "Unknown city ''"),
        ("chicago", "july", "all", "Unknown month 'july'"),
        ("chicago", "1", "all", "Unknown month '1'"),
        ("chicago", "all", "funday", "Unknown day 'funday'"),
        ("chicago", "monday", "june", "Unknown month 'monday'"),  # arguments swapped
    ],
)
def test_unknown_arguments_are_refused(city, month, day, message):
    with pytest.raises(ValueError, match=message):
        load_data(city, month, day)


@pytest.mark.parametrize(
    ("month", "day"), [("april", "all"), ("all", "thursday"), ("march", "monday")]
)
def test_an_empty_selection_gives_an_empty_frame_and_no_invented_figure(month, day, capsys):
    df = load_data("chicago", month, day)

    assert df.empty
    assert "Trip Duration" in df.columns
    assert time_stats(df) == {
        "mostCommonMonth": [],
        "mostCommonDayOfWeek": [],
        "mostCommonStartHour": [],
    }
    assert station_stats(df) == {
        "mostCommonStartStation": [],
        "mostCommonEndStation": [],
        "mostCommonTrip": [],
    }
    assert trip_duration_stats(df) == {"totalTravelTime": None, "meanTravelTime": None}
    assert user_stats(df) == {
        "userTypeCounts": {},  # the column exists, it is only empty: not None, and no zero
        "genderCounts": {},
        "earliestBirthYear": None,
        "mostRecentBirthYear": None,
        "mostCommonBirthYear": [],
    }
    assert ": 0" not in capsys.readouterr().out


def test_unreadable_start_times_are_kept_without_filter_and_dropped_by_any_filter():
    # tests/data/new_york_city.csv: rows 3 (month first), 6 (text) and 7 (month 13) cannot
    # be read; row 1 uses the day-first layout of the statement and can.
    everything = load_data("new york city", "all", "all")

    assert len(everything) == 7
    assert everything["Start Time"].isna().tolist() == [
        False,
        False,
        True,
        False,
        False,
        True,
        True,
    ]
    assert everything["Start Time"].iloc[0] == pd.Timestamp(2017, 6, 23, 15, 9, 32)
    assert everything["End Time"].iloc[0] == pd.Timestamp(2017, 6, 23, 15, 14, 53)
    assert len(load_data("new york city", "june", "all")) == 2
    assert len(load_data("new york city", "june", "friday")) == 2
    assert len(load_data("new york city", "may", "thursday")) == 2
    assert sum(len(load_data("new york city", month, "all")) for month in MONTHS) == 4


def test_durations_and_birth_years_that_are_not_numbers_become_missing():
    df = load_data("new york city", "all", "all")

    assert pd.api.types.is_numeric_dtype(df["Trip Duration"])
    assert df["Trip Duration"].isna().tolist() == [False, False, False, False, True, True, False]
    assert df["Trip Duration"].iloc[3] == -60  # kept as read: the statistics decide what to use
    assert df["Birth Year"].iloc[4] == 1985.5


def test_a_missing_file_is_reported_with_the_way_to_get_it(monkeypatch, tmp_path):
    monkeypatch.setenv("BIKESHARE_DATA_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError, match=r"chicago\.csv not found .*fetch_data\.py"):
        load_data("chicago", "all", "all")


def test_a_file_without_the_expected_columns_is_refused(monkeypatch, tmp_path):
    (tmp_path / "chicago.csv").write_text("Start Time,User Type\n2017-01-02 08:05:10,Subscriber\n")
    monkeypatch.setenv("BIKESHARE_DATA_DIR", str(tmp_path))
    with pytest.raises(
        ValueError, match=r"chicago\.csv lacks the column\(s\): End Time, Trip Duration"
    ):
        load_data("chicago", "all", "all")


def test_default_folders_are_data_then_the_folder_of_the_program(monkeypatch, tmp_path):
    monkeypatch.delenv("BIKESHARE_DATA_DIR")
    monkeypatch.setattr(bike_investigation, "__file__", str(tmp_path / "bike_investigation.py"))
    line = "2017-01-02 08:05:10,2017-01-02 08:15:10,600,Alpha St,Bravo Ave,Subscriber\n"
    header = "Start Time,End Time,Trip Duration,Start Station,End Station,User Type\n"

    (tmp_path / "chicago.csv").write_text(header + line)
    assert len(load_data("chicago", "all", "all")) == 1  # next to the program, as in the skeleton

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "chicago.csv").write_text(header + line * 2)
    assert len(load_data("chicago", "all", "all")) == 2  # data/ comes first
