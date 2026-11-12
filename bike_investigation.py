"""Explore bike share trips in Chicago, New York City and Washington from the terminal.

Each ``*_stats`` function prints a short report and returns the same figures as a
dictionary, so that they can be tested and reused. They share three conventions:

* a "most common" value is a list holding every tied value, in its natural order
  (calendar order, Monday to Sunday, ascending hours and years, alphabetical stations);
* a row whose value is missing or unusable is left out of the statistic and counted in a note;
* a statistic that cannot be computed is ``None`` or an empty list, never zero.
"""

import os
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd

CITY_DATA = {
    "chicago": "chicago.csv",
    "new york city": "new_york_city.csv",
    "washington": "washington.csv",
}

ALL = "all"
MONTH_NAMES = (
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
)
MONTHS = MONTH_NAMES[:6]  # the data set covers January to June 2017
DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# The only two timestamp layouts accepted, in this order: the one used by the CSV files and
# by the official test, then the day-first one printed in the statement. Nothing is inferred,
# and the two cannot be mistaken for each other, so a day and a month are never swapped.
TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S")

CORE_COLUMNS = (
    "Start Time",
    "End Time",
    "Trip Duration",
    "Start Station",
    "End Station",
    "User Type",
)
OPTIONAL_COLUMNS = ("Gender", "Birth Year")  # not in the Washington file
TEXT_COLUMNS = ("Start Station", "End Station", "User Type", "Gender")


def _clean(text):
    """Lower-case an answer and drop its stray spaces ("  New   York city " -> "new york city")."""
    return " ".join(str(text).split()).casefold()


def _ask(prompt, choices):
    """Ask until the answer is one of ``choices``.

    A closed or interrupted input (EOFError, KeyboardInterrupt) is left to the caller.
    """
    while True:
        answer = _clean(input(prompt))
        if answer in choices:
            return answer
        print(f"{answer!r} is not a valid choice. Please type one of: {', '.join(choices)}.")


def get_filters():
    """
    Asks user to specify a city, month, and day to analyze.

    Answers are matched without regard to case or extra spaces, and the question is asked
    again until the answer is valid.

    Returns:
        (str) city - name of the city to analyze
        (str) month - name of the month to filter by, or "all" to apply no month filter
        (str) day - name of the day of week to filter by, or "all" to apply no day filter
    Raises:
        EOFError, KeyboardInterrupt - when the input is closed or interrupted (handled by main)
    """
    print("Hello! Let's explore some bikeshare data!")
    city = _ask(f"Which city? ({', '.join(CITY_DATA)})\n> ", tuple(CITY_DATA))
    month = _ask(f"Which month? ({ALL}, {', '.join(MONTHS)})\n> ", (ALL, *MONTHS))
    day = _ask(f"Which day of week? ({ALL}, {', '.join(DAYS)})\n> ", (ALL, *DAYS))

    print("-" * 40)
    return city, month, day


def _data_path(city):
    """Find the CSV file of a city.

    The folder is $BIKESHARE_DATA_DIR when set. Otherwise it is ``data/`` next to this file
    (where scripts/fetch_data.py puts the files), then the folder of this file itself (the
    layout of the original skeleton).
    """
    here = Path(__file__).resolve().parent
    override = os.environ.get("BIKESHARE_DATA_DIR")
    folders = [Path(override)] if override else [here / "data", here]
    for folder in folders:
        if (folder / CITY_DATA[city]).is_file():
            return folder / CITY_DATA[city]
    searched = ", ".join(str(folder) for folder in folders)
    raise FileNotFoundError(
        f"{CITY_DATA[city]} not found in {searched}. "
        "Run `python scripts/fetch_data.py` or set BIKESHARE_DATA_DIR."
    )


def _parse_times(values):
    """Turn a column of timestamps into datetimes, using TIME_FORMATS only.

    A value written in any other layout becomes NaT: it is better to lose a row, and say so,
    than to guess a date.
    """
    if pd.api.types.is_datetime64_any_dtype(values):
        return values
    text = values.astype("string")
    parsed = pd.to_datetime(text, format=TIME_FORMATS[0], errors="coerce")
    for layout in TIME_FORMATS[1:]:
        unread = parsed.isna() & text.notna()
        if not unread.any():
            break
        parsed = parsed.fillna(pd.to_datetime(text[unread], format=layout, errors="coerce"))
    return parsed


def _squeeze(text):
    """Collapse runs of spaces and trim the ends ("23rd & E St NW " -> "23rd & E St NW")."""
    return " ".join(text.split())


def _read_city(path):
    """Read one city file into a typed frame: datetimes, numbers and compact text columns."""
    known = (*CORE_COLUMNS, *OPTIONAL_COLUMNS)
    df = pd.read_csv(
        path,
        usecols=lambda name: name in known,  # skips the unnamed row id of the raw export
        dtype={
            "Start Time": "string",
            "End Time": "string",
            **dict.fromkeys(TEXT_COLUMNS, "category"),
        },
    )
    missing = [name for name in CORE_COLUMNS if name not in df.columns]
    if missing:
        raise ValueError(f"{path.name} lacks the column(s): {', '.join(missing)}")

    for name in ("Start Time", "End Time"):
        df[name] = _parse_times(df[name])
    for name in ("Trip Duration", "Birth Year"):
        if name in df.columns:
            df[name] = pd.to_numeric(df[name], errors="coerce")
    for name in TEXT_COLUMNS:
        if name in df.columns:
            # Mapping a categorical only touches its few hundred categories, not every row.
            df[name] = df[name].map(_squeeze, na_action="ignore").astype("category")
    return df


def load_data(city, month, day):
    """
    Loads data for the specified city and filters by month and day if applicable.

    Filters apply to the start time of a trip. A row whose start time could not be read is
    kept when no filter is set and dropped by any filter.

    Args:
        (str) city - name of the city to analyze
        (str) month - name of the month to filter by, or "all" to apply no month filter
        (str) day - name of the day of week to filter by, or "all" to apply no day filter
    Returns:
        df - Pandas DataFrame containing city data filtered by month and day
    Raises:
        ValueError - unknown city, month or day, or a file without the expected columns
        FileNotFoundError - the CSV file of the city is not available
    """
    city, month, day = _clean(city), _clean(month), _clean(day)
    for label, value, choices in (
        ("city", city, tuple(CITY_DATA)),
        ("month", month, (ALL, *MONTHS)),
        ("day", day, (ALL, *DAYS)),
    ):
        if value not in choices:
            raise ValueError(f"Unknown {label} {value!r}. Expected one of: {', '.join(choices)}.")

    df = _read_city(_data_path(city))
    if month != ALL:
        df = df[df["Start Time"].dt.month == MONTHS.index(month) + 1]
    if day != ALL:
        df = df[df["Start Time"].dt.day_of_week == DAYS.index(day)]
    return df.reset_index(drop=True)


def _modes(values, key=None):
    """Every most frequent value of a column, all of them on a tie, sorted.

    Missing values are ignored.
    """
    counts = values.value_counts()
    # A filtered categorical column still lists its unused categories, with a count of 0.
    if counts.empty or counts.iloc[0] == 0:
        return []
    return sorted(counts.index[counts == counts.iloc[0]].tolist(), key=key)


def _counts(df, column):
    """Number of rows per value, most frequent first, or None when the column does not exist."""
    if column not in df.columns:
        return None
    counts = ((str(value), int(count)) for value, count in df[column].value_counts().items())
    return dict(sorted((item for item in counts if item[1]), key=lambda item: (-item[1], item[0])))


def _start_times(df):
    """Parsed start times of a frame, empty when the column does not exist."""
    if "Start Time" not in df.columns:
        return pd.Series([], dtype="datetime64[ns]")
    return _parse_times(df["Start Time"])


def _listed(values):
    """Text of a "most common" result: one value, several on a tie, or a placeholder."""
    if not values:
        return "no data"
    return ", ".join(str(value) for value in values) + (" (tie)" if len(values) > 1 else "")


def time_stats(df):
    """Displays statistics on the most frequent times of travel.

    Returns:
        dict - "mostCommonMonth" and "mostCommonDayOfWeek" (lists of lower-case names) and
        "mostCommonStartHour" (list of hours, 0 to 23), computed on the start times
    """

    print("\nCalculating The Most Frequent Times of Travel...\n")
    start_time = time.perf_counter()

    start = _start_times(df).dropna()
    stats = {
        "mostCommonMonth": [MONTH_NAMES[month - 1] for month in _modes(start.dt.month)],
        "mostCommonDayOfWeek": [DAYS[day] for day in _modes(start.dt.day_of_week)],
        "mostCommonStartHour": _modes(start.dt.hour),
    }

    print("Most common month:", _listed([name.title() for name in stats["mostCommonMonth"]]))
    print(
        "Most common day of week:",
        _listed([name.title() for name in stats["mostCommonDayOfWeek"]]),
    )
    print(
        "Most common start hour:",
        _listed([f"{hour:02d}:00" for hour in stats["mostCommonStartHour"]]),
    )
    if len(start) < len(df):
        print(f"Note: {len(df) - len(start):,} trip(s) without a readable start time left out.")

    print(f"\nThis took {time.perf_counter() - start_time:.3f} seconds.")
    print("-" * 40)
    return stats


def station_stats(df):
    """Displays statistics on the most popular stations and trip.

    Returns:
        dict - "mostCommonStartStation" and "mostCommonEndStation" (lists of names) and
        "mostCommonTrip" (list of (start station, end station) tuples)
    """

    print("\nCalculating The Most Popular Stations and Trip...\n")
    start_time = time.perf_counter()

    stats = {"mostCommonStartStation": [], "mostCommonEndStation": [], "mostCommonTrip": []}
    for key, column in (
        ("mostCommonStartStation", "Start Station"),
        ("mostCommonEndStation", "End Station"),
    ):
        if column in df.columns:
            stats[key] = [str(name) for name in _modes(df[column], key=str)]
    if {"Start Station", "End Station"} <= set(df.columns):
        # Count ordered pairs: A to B and B to A are two different trips, and the busiest
        # trip is not the busiest start station paired with the busiest end station.
        trips = df.groupby(["Start Station", "End Station"], observed=True, sort=False).size()
        if len(trips):
            busiest = trips.index[trips == trips.max()]
            stats["mostCommonTrip"] = sorted((str(start), str(end)) for start, end in busiest)

    print("Most common start station:", _listed(stats["mostCommonStartStation"]))
    print("Most common end station:", _listed(stats["mostCommonEndStation"]))
    print(
        "Most common trip:",
        _listed([f"{start} -> {end}" for start, end in stats["mostCommonTrip"]]),
    )

    print(f"\nThis took {time.perf_counter() - start_time:.3f} seconds.")
    print("-" * 40)
    return stats


def trip_duration_stats(df):
    """Displays statistics on the total and average trip duration.

    Durations are in seconds. A duration that is missing, not a number, infinite or negative
    is left out; zero is kept.

    Returns:
        dict - "totalTravelTime" and "meanTravelTime" in seconds (floats), or None for both
        when no row has a usable duration
    """

    print("\nCalculating Trip Duration...\n")
    start_time = time.perf_counter()

    stats = {"totalTravelTime": None, "meanTravelTime": None}
    if "Trip Duration" in df.columns:
        durations = pd.to_numeric(df["Trip Duration"], errors="coerce")
        usable = durations[durations.between(0, float("inf"), inclusive="left")]
        if len(usable):
            stats = {
                "totalTravelTime": float(usable.sum()),
                "meanTravelTime": float(usable.mean()),
            }

    if stats["totalTravelTime"] is None:
        print("No usable trip duration.")
    else:
        total, mean = stats["totalTravelTime"], stats["meanTravelTime"]
        print(f"Total travel time: {total:,.0f} seconds ({timedelta(seconds=round(total))})")
        print(f"Mean travel time: {mean:,.1f} seconds ({timedelta(seconds=round(mean))})")
        if len(usable) < len(df):
            print(f"Note: {len(df) - len(usable):,} trip(s) without a usable duration left out.")

    print(f"\nThis took {time.perf_counter() - start_time:.3f} seconds.")
    print("-" * 40)
    return stats


def _print_counts(title, df, column, counts):
    """Print one block of counts, telling an absent column from an empty one."""
    if counts is None:
        print(f"{title}: not available in this data set")
        return
    print(f"{title}:" if counts else f"{title}: no value recorded")
    for value, count in counts.items():
        print(f"  {value}: {count:,}")
    unknown = int(df[column].isna().sum())
    if unknown:
        print(f"  ({unknown:,} trip(s) with no value recorded)")


def user_stats(df):
    """Displays statistics on bikeshare users.

    Birth years are reported as recorded, even when they are implausible: a whole number is
    never discarded, the report only counts those that do not fit the date of the trip.

    Returns:
        dict - "userTypeCounts" and "genderCounts" ({value: number of trips}, or None when
        the column does not exist, as for Washington), "earliestBirthYear" and
        "mostRecentBirthYear" (int or None) and "mostCommonBirthYear" (list of years)
    """

    print("\nCalculating User Stats...\n")
    start_time = time.perf_counter()

    stats = {
        "userTypeCounts": _counts(df, "User Type"),
        "genderCounts": _counts(df, "Gender"),
        "earliestBirthYear": None,
        "mostRecentBirthYear": None,
        "mostCommonBirthYear": [],
    }
    odd_ages = 0
    if "Birth Year" in df.columns:
        years = pd.to_numeric(df["Birth Year"], errors="coerce")
        years = years[years % 1 == 0]  # whole numbers only: NaN, infinities and 1990.5 drop out
        if len(years):
            stats["earliestBirthYear"] = int(years.min())
            stats["mostRecentBirthYear"] = int(years.max())
            stats["mostCommonBirthYear"] = [int(year) for year in _modes(years)]
            ages = _start_times(df).dt.year - years
            odd_ages = int(((ages < 0) | (ages > 100)).sum())

    _print_counts("User types", df, "User Type", stats["userTypeCounts"])
    _print_counts("Gender", df, "Gender", stats["genderCounts"])
    if "Birth Year" not in df.columns:
        print("Year of birth: not available in this data set")
    elif stats["earliestBirthYear"] is None:
        print("Year of birth: no value recorded")
    else:
        print(
            f"Year of birth: earliest {stats['earliestBirthYear']}, "
            f"most recent {stats['mostRecentBirthYear']}, "
            f"most common {_listed(stats['mostCommonBirthYear'])}"
        )
        if odd_ages:
            print(
                f"  ({odd_ages:,} trip(s) by a rider not yet born or older than 100, "
                "kept as recorded)"
            )

    print(f"\nThis took {time.perf_counter() - start_time:.3f} seconds.")
    print("-" * 40)
    return stats


def main():
    try:
        while True:
            city, month, day = get_filters()
            try:
                df = load_data(city, month, day)
            except (OSError, ValueError) as error:
                print(f"\nCould not load the data: {error}")
            else:
                if df.empty:
                    print("\nNo trip matches these filters.")
                else:
                    time_stats(df)
                    station_stats(df)
                    trip_duration_stats(df)
                    user_stats(df)

            restart = _ask(
                "\nWould you like to restart? Enter yes or no.\n", ("yes", "y", "no", "n")
            )
            if restart in ("no", "n"):
                break
    except (EOFError, KeyboardInterrupt):
        print("\nInput closed, goodbye.")


if __name__ == "__main__":
    main()
