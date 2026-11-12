"""Unit tests of the four statistics functions, in the unittest style of the provided file.

Every expected value below can be checked by hand from the few rows of its test.
Run with ``python -m unittest -v`` or with pytest (see tests/ for the rest of the suite).
"""

import contextlib
import io
import unittest

import pandas as pd

from bike_investigation import station_stats, time_stats, trip_duration_stats, user_stats

NO_TIME_STATS = {"mostCommonMonth": [], "mostCommonDayOfWeek": [], "mostCommonStartHour": []}
NO_STATION_STATS = {"mostCommonStartStation": [], "mostCommonEndStation": [], "mostCommonTrip": []}
NO_DURATION_STATS = {"totalTravelTime": None, "meanTravelTime": None}


class TestBikeShareData(unittest.TestCase):
    def setUp(self):
        # The functions print their report: capture it to keep the test output readable.
        self.report = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    # ---------------------------------------------------------------- time_stats

    def test_time_stats(self):
        data = {
            "Start Time": ["2017-01-01 09:07:57", "2017-01-02 09:07:57", "2017-01-03 00:07:57"],
            "End Time": ["2017-01-01 09:20:53", "2017-01-02 09:20:53", "2017-01-03 00:20:53"],
        }

        df = pd.DataFrame(data)

        result = time_stats(df)

        self.assertEqual(result["mostCommonMonth"], ["january"])
        # One trip on a Sunday, one on a Monday, one on a Tuesday: the three days tie and
        # come back in week order.
        self.assertEqual(result["mostCommonDayOfWeek"], ["monday", "tuesday", "sunday"])
        self.assertEqual(result["mostCommonStartHour"], [9])
        self.assertEqual(set(result), set(NO_TIME_STATS))

    def test_time_stats_missing_data(self):
        # Two readable Mondays of March at 08:xx; the other four rows cannot be read.
        df = pd.DataFrame(
            {
                "Start Time": [
                    "2017-03-06 08:00:00",
                    None,
                    "2017-03-13 08:30:00",
                    "not a date",
                    float("nan"),
                    "2017-02-30 10:00:00",  # 30 February does not exist
                ]
            }
        )

        result = time_stats(df)

        self.assertEqual(
            result,
            {
                "mostCommonMonth": ["march"],
                "mostCommonDayOfWeek": ["monday"],
                "mostCommonStartHour": [8],
            },
        )
        self.assertIn("4 trip(s) without a readable start time", self.report.getvalue())

    def test_time_stats_without_any_usable_start_time(self):
        frames = {
            "no column at all": pd.DataFrame(),
            "no start time column": pd.DataFrame({"End Time": ["2017-01-01 09:20:53"]}),
            "no row": pd.DataFrame({"Start Time": []}),
            "only missing values": pd.DataFrame({"Start Time": [None, float("nan")]}),
            "only unreadable values": pd.DataFrame({"Start Time": ["?", "2017-06", 20170601]}),
        }
        for label, df in frames.items():
            with self.subTest(label):
                self.assertEqual(time_stats(df), NO_TIME_STATS)

    def test_time_stats_ties_are_all_returned_in_natural_order(self):
        df = pd.DataFrame(
            {
                "Start Time": [
                    "2017-06-30 23:10:00",  # Friday
                    "2017-06-05 00:20:00",  # Monday
                    "2017-01-06 23:30:00",  # Friday
                    "2017-01-02 00:40:00",  # Monday
                ]
            }
        )

        result = time_stats(df)

        self.assertEqual(result["mostCommonMonth"], ["january", "june"])
        self.assertEqual(result["mostCommonDayOfWeek"], ["monday", "friday"])
        self.assertEqual(result["mostCommonStartHour"], [0, 23])

    def test_time_stats_does_not_depend_on_row_order(self):
        rows = ["2017-02-01 10:00:00", "2017-03-01 11:00:00", "2017-03-02 11:30:00"]
        expected = time_stats(pd.DataFrame({"Start Time": rows}))
        self.assertEqual(expected["mostCommonMonth"], ["march"])
        self.assertEqual(time_stats(pd.DataFrame({"Start Time": rows[::-1]})), expected)

    def test_time_stats_reads_the_day_first_layout_of_the_statement(self):
        # "23/06/2017 15:09:32" is the example of data-level-1.md: 23 June 2017, a Friday.
        result = time_stats(pd.DataFrame({"Start Time": ["23/06/2017 15:09:32"]}))
        self.assertEqual(
            result,
            {
                "mostCommonMonth": ["june"],
                "mostCommonDayOfWeek": ["friday"],
                "mostCommonStartHour": [15],
            },
        )

    def test_time_stats_never_swaps_day_and_month(self):
        # With slashes the day always comes first: 3 April 2017 (a Monday), never 4 March.
        result = time_stats(pd.DataFrame({"Start Time": ["03/04/2017 10:00:00"]}))
        self.assertEqual(result["mostCommonMonth"], ["april"])
        self.assertEqual(result["mostCommonDayOfWeek"], ["monday"])

        # A month-first date is refused instead of being guessed.
        self.assertEqual(
            time_stats(pd.DataFrame({"Start Time": ["06/23/2017 15:09:32"]})), NO_TIME_STATS
        )

        # Both accepted layouts can live in the same column.
        mixed = pd.DataFrame({"Start Time": ["2017-06-23 15:09:32", "24/06/2017 15:30:00"]})
        self.assertEqual(time_stats(mixed)["mostCommonDayOfWeek"], ["friday", "saturday"])

    def test_time_stats_accepts_datetime_columns_and_any_month(self):
        df = pd.DataFrame({"Start Time": pd.to_datetime(["2017-12-25 10:00:00"])})
        self.assertEqual(
            time_stats(df),
            {
                "mostCommonMonth": ["december"],
                "mostCommonDayOfWeek": ["monday"],
                "mostCommonStartHour": [10],
            },
        )

    # ------------------------------------------------------------- station_stats

    def test_station_stats(self):
        # Start counts: A 3, C 2, G 1, H 1. End counts: B 3, D 2, E 1, F 1.
        # Trips: C->D twice, every other pair once (A->B included).
        df = pd.DataFrame(
            {
                "Start Station": ["A", "A", "A", "H", "G", "C", "C"],
                "End Station": ["B", "E", "F", "B", "B", "D", "D"],
            }
        )

        result = station_stats(df)

        self.assertEqual(result["mostCommonStartStation"], ["A"])
        self.assertEqual(result["mostCommonEndStation"], ["B"])
        # Not ("A", "B"): the busiest trip is counted on pairs, not on the two columns apart.
        self.assertEqual(result["mostCommonTrip"], [("C", "D")])
        self.assertEqual(set(result), set(NO_STATION_STATS))

    def test_station_stats_keeps_the_direction_of_a_trip(self):
        # A->B twice, B->A twice, C->D three times. Without direction "A/B" would win with 4.
        df = pd.DataFrame(
            {
                "Start Station": ["A", "A", "B", "B", "C", "C", "C"],
                "End Station": ["B", "B", "A", "A", "D", "D", "D"],
            }
        )
        self.assertEqual(station_stats(df)["mostCommonTrip"], [("C", "D")])

        one_way = pd.DataFrame({"Start Station": ["A", "A", "B"], "End Station": ["B", "B", "A"]})
        self.assertEqual(station_stats(one_way)["mostCommonTrip"], [("A", "B")])

    def test_station_stats_ties(self):
        df = pd.DataFrame(
            {
                "Start Station": ["Zed", "Alpha", "Zed", "Alpha"],
                "End Station": ["Alpha", "Zed", "Alpha", "Zed"],
            }
        )
        self.assertEqual(
            station_stats(df),
            {
                "mostCommonStartStation": ["Alpha", "Zed"],
                "mostCommonEndStation": ["Alpha", "Zed"],
                "mostCommonTrip": [("Alpha", "Zed"), ("Zed", "Alpha")],
            },
        )

    def test_station_stats_missing_data(self):
        # A trip needs both ends: rows 3 and 4 count for one station only.
        df = pd.DataFrame(
            {
                "Start Station": ["A", "A", "A", None, "B"],
                "End Station": ["B", "C", None, "C", "C"],
            }
        )

        result = station_stats(df)

        self.assertEqual(result["mostCommonStartStation"], ["A"])
        self.assertEqual(result["mostCommonEndStation"], ["C"])
        self.assertEqual(result["mostCommonTrip"], [("A", "B"), ("A", "C"), ("B", "C")])

    def test_station_stats_missing_columns_and_empty_frames(self):
        for label, df in {
            "no column at all": pd.DataFrame(),
            "no row": pd.DataFrame({"Start Station": [], "End Station": []}),
            "only missing values": pd.DataFrame({"Start Station": [None], "End Station": [None]}),
        }.items():
            with self.subTest(label):
                self.assertEqual(station_stats(df), NO_STATION_STATS)

        only_start = station_stats(pd.DataFrame({"Start Station": ["A", "A", "B"]}))
        self.assertEqual(only_start["mostCommonStartStation"], ["A"])
        self.assertEqual(only_start["mostCommonEndStation"], [])
        self.assertEqual(only_start["mostCommonTrip"], [])

    def test_station_stats_ignores_unused_categories(self):
        # A filtered categorical column still knows the stations that are no longer there.
        df = pd.DataFrame(
            {
                "Start Station": pd.Categorical(["A", "B", "B"]),
                "End Station": pd.Categorical(["C", "A", "A"]),
            }
        )
        kept = df[df["Start Station"] == "A"]
        self.assertEqual(
            station_stats(kept),
            {
                "mostCommonStartStation": ["A"],
                "mostCommonEndStation": ["C"],
                "mostCommonTrip": [("A", "C")],
            },
        )
        self.assertEqual(station_stats(df[df["Start Station"] == "nowhere"]), NO_STATION_STATS)

    # ------------------------------------------------------- trip_duration_stats

    def test_trip_duration_stats(self):
        result = trip_duration_stats(pd.DataFrame({"Trip Duration": [321, 1610, 416, 350, 303]}))
        self.assertEqual(result, {"totalTravelTime": 3000.0, "meanTravelTime": 600.0})
        self.assertIsInstance(result["totalTravelTime"], float)
        self.assertIsInstance(result["meanTravelTime"], float)

    def test_trip_duration_stats_floats_and_numbers_stored_as_text(self):
        floats = trip_duration_stats(pd.DataFrame({"Trip Duration": [489.5, 402.25, 108.25]}))
        self.assertEqual(floats, {"totalTravelTime": 1000.0, "meanTravelTime": 1000 / 3})

        text = trip_duration_stats(pd.DataFrame({"Trip Duration": ["100", "200.5", " 300 "]}))
        self.assertEqual(text, {"totalTravelTime": 600.5, "meanTravelTime": 600.5 / 3})

    def test_trip_duration_stats_missing_and_invalid_data(self):
        # Kept: 100, 0 and 200. Left out: missing, negative, text and infinite values.
        df = pd.DataFrame(
            {"Trip Duration": [100, None, -50, "abc", float("inf"), 0, float("nan"), 200]}
        )

        result = trip_duration_stats(df)

        self.assertEqual(result, {"totalTravelTime": 300.0, "meanTravelTime": 100.0})
        self.assertIn("5 trip(s) without a usable duration", self.report.getvalue())

    def test_trip_duration_stats_zero_is_a_value_and_absence_is_none(self):
        self.assertEqual(
            trip_duration_stats(pd.DataFrame({"Trip Duration": [0, 0]})),
            {"totalTravelTime": 0.0, "meanTravelTime": 0.0},
        )
        for label, df in {
            "no column at all": pd.DataFrame(),
            "no duration column": pd.DataFrame({"Start Time": ["2017-01-01 09:07:57"]}),
            "no row": pd.DataFrame({"Trip Duration": []}),
            "only missing values": pd.DataFrame({"Trip Duration": [None, float("nan")]}),
            "only invalid values": pd.DataFrame({"Trip Duration": [-1, "n/a", float("-inf")]}),
        }.items():
            with self.subTest(label):
                # No division by zero, and no zero standing in for "unknown".
                self.assertEqual(trip_duration_stats(df), NO_DURATION_STATS)

    # ---------------------------------------------------------------- user_stats

    def test_user_stats(self):
        df = pd.DataFrame(
            {
                "User Type": ["Subscriber", "Customer", "Subscriber", "Subscriber", "Dependent"],
                "Gender": ["Male", "Female", "Female", "Male", "Male"],
                "Birth Year": [1992.0, 1981.0, 1992.0, 1986.0, 2004.0],
            }
        )

        result = user_stats(df)

        self.assertEqual(
            result,
            {
                "userTypeCounts": {"Subscriber": 3, "Customer": 1, "Dependent": 1},
                "genderCounts": {"Male": 3, "Female": 2},
                "earliestBirthYear": 1981,
                "mostRecentBirthYear": 2004,
                "mostCommonBirthYear": [1992],
            },
        )
        # Most frequent first, then alphabetical.
        self.assertEqual(list(result["userTypeCounts"]), ["Subscriber", "Customer", "Dependent"])
        self.assertIsInstance(result["earliestBirthYear"], int)

    def test_user_stats_without_gender_and_birth_year_columns(self):
        # The Washington file has no "Gender" and no "Birth Year" column.
        result = user_stats(pd.DataFrame({"User Type": ["Subscriber", "Customer", "Subscriber"]}))

        self.assertEqual(result["userTypeCounts"], {"Subscriber": 2, "Customer": 1})
        self.assertIsNone(result["genderCounts"])
        self.assertIsNone(result["earliestBirthYear"])
        self.assertIsNone(result["mostRecentBirthYear"])
        self.assertEqual(result["mostCommonBirthYear"], [])
        self.assertIn("Gender: not available in this data set", self.report.getvalue())
        self.assertIn("Year of birth: not available in this data set", self.report.getvalue())

    def test_user_stats_missing_data(self):
        df = pd.DataFrame(
            {
                "User Type": ["Subscriber", None, "Customer", "Subscriber"],
                "Gender": [None, "Female", float("nan"), "Female"],
                "Birth Year": [float("nan"), 1990.0, None, 1975.0],
            }
        )

        result = user_stats(df)

        self.assertEqual(result["userTypeCounts"], {"Subscriber": 2, "Customer": 1})
        self.assertEqual(result["genderCounts"], {"Female": 2})
        self.assertEqual(result["earliestBirthYear"], 1975)
        self.assertEqual(result["mostRecentBirthYear"], 1990)
        self.assertEqual(result["mostCommonBirthYear"], [1975, 1990])
        self.assertIn("(1 trip(s) with no value recorded)", self.report.getvalue())
        self.assertIn("(2 trip(s) with no value recorded)", self.report.getvalue())

    def test_user_stats_tells_an_empty_column_from_an_absent_one(self):
        empty = user_stats(
            pd.DataFrame({"User Type": [None], "Gender": [None], "Birth Year": [None]})
        )
        self.assertEqual(
            empty,
            {
                "userTypeCounts": {},
                "genderCounts": {},
                "earliestBirthYear": None,
                "mostRecentBirthYear": None,
                "mostCommonBirthYear": [],
            },
        )

        absent = user_stats(pd.DataFrame())
        self.assertIsNone(absent["userTypeCounts"])
        self.assertIsNone(absent["genderCounts"])
        self.assertIsNone(absent["earliestBirthYear"])
        self.assertEqual(absent["mostCommonBirthYear"], [])

    def test_user_stats_never_reports_a_count_of_zero(self):
        df = pd.DataFrame(
            {
                "User Type": pd.Categorical(["Subscriber", "Customer", "Subscriber"]),
                "Gender": pd.Categorical(["Male", "Female", "Male"]),
            }
        )
        subscribers = df[df["User Type"] == "Subscriber"]

        result = user_stats(subscribers)

        self.assertEqual(result["userTypeCounts"], {"Subscriber": 2})
        self.assertEqual(result["genderCounts"], {"Male": 2})

    def test_user_stats_birth_year_ties_and_invalid_values(self):
        # Whole numbers are kept, as integers or floats or text; the rest is left out.
        df = pd.DataFrame(
            {"Birth Year": [1990, 1985.0, "1985", 1990.0, 1987.5, "unknown", float("inf"), None]}
        )

        result = user_stats(df)

        self.assertEqual(result["earliestBirthYear"], 1985)
        self.assertEqual(result["mostRecentBirthYear"], 1990)
        self.assertEqual(result["mostCommonBirthYear"], [1985, 1990])

    def test_user_stats_reports_implausible_birth_years_without_dropping_them(self):
        # In 2017: born in 1899 means 118 years old, born in 2999 means not born yet.
        df = pd.DataFrame(
            {
                "Start Time": ["2017-06-01 08:00:00"] * 4,
                "Birth Year": [1899.0, 1989.0, 1989.0, 2999.0],
            }
        )

        result = user_stats(df)

        self.assertEqual(result["earliestBirthYear"], 1899)
        self.assertEqual(result["mostRecentBirthYear"], 2999)
        self.assertEqual(result["mostCommonBirthYear"], [1989])
        self.assertIn(
            "(2 trip(s) by a rider not yet born or older than 100", self.report.getvalue()
        )

    # ------------------------------------------------------------------- reports

    def test_reports_are_printed(self):
        df = pd.DataFrame(
            {
                "Start Time": ["2017-06-23 15:09:32", "2017-06-23 18:19:03"],
                "Trip Duration": [321, 1610],
                "Start Station": ["Wood St & Hubbard St", "Theater on the Lake"],
                "End Station": ["Damen Ave & Chicago Ave", "Sheffield Ave & Waveland Ave"],
                "User Type": ["Subscriber", "Subscriber"],
            }
        )
        for stats in (time_stats, station_stats, trip_duration_stats, user_stats):
            stats(df)

        report = self.report.getvalue()
        for line in (
            "Most common month: June",
            "Most common day of week: Friday",
            "Most common start hour: 15:00, 18:00 (tie)",
            "Most common start station: Theater on the Lake, Wood St & Hubbard St (tie)",
            "Most common trip: Theater on the Lake -> Sheffield Ave & Waveland Ave, "
            "Wood St & Hubbard St -> Damen Ave & Chicago Ave (tie)",
            "Total travel time: 1,931 seconds (0:32:11)",
            "Mean travel time: 965.5 seconds (0:16:06)",
            "  Subscriber: 2",
        ):
            with self.subTest(line):
                self.assertIn(line, report)


if __name__ == "__main__":
    unittest.main()
