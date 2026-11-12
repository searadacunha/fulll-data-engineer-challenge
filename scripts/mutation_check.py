"""Check that the tests notice calculation errors, by planting some on purpose.

Each fault below is a small, plausible mistake (an off-by-one in a filter, a tie dropped,
an invalid value kept, ...). It is applied to a temporary copy of the program, and the fast
test suite must then fail. A fault that leaves the suite green is a gap in the tests.

Usage: python scripts/mutation_check.py [pytest arguments]   (exit status 1 if a fault survives)

Extra arguments go to pytest, to see what a part of the suite catches on its own, e.g.
``python scripts/mutation_check.py tests/test_properties.py``.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRAM = "bike_investigation.py"

# (what the fault does, text of the program, text that replaces it)
FAULTS = [
    (
        "month filter shifted by one month",
        ".dt.month == MONTHS.index(month) + 1]",
        ".dt.month == MONTHS.index(month)]",
    ),
    (
        "day filter numbered from Sunday instead of Monday",
        ".dt.day_of_week == DAYS.index(day)]",
        ".dt.day_of_week == (DAYS.index(day) + 6) % 7]",
    ),
    (
        "filters applied to the end time of the trip",
        'df = df[df["Start Time"].dt.month',
        'df = df[df["End Time"].dt.month',
    ),
    (
        "rows with an unreadable start time dropped without notice",
        "return df.reset_index(drop=True)",
        'return df.dropna(subset=["Start Time"]).reset_index(drop=True)',
    ),
    (
        "filtered frame keeps the row numbers of the file",
        "return df.reset_index(drop=True)",
        "return df",
    ),
    (
        "station names keep their stray spaces",
        'df[name] = df[name].map(_squeeze, na_action="ignore").astype("category")',
        "pass",
    ),
    (
        "slash dates read month first",
        '"%d/%m/%Y %H:%M:%S"',
        '"%m/%d/%Y %H:%M:%S"',
    ),
    (
        "only one value returned on a tie",
        "return sorted(counts.index[counts == counts.iloc[0]].tolist(), key=key)",
        "return [counts.index[0]]",
    ),
    (
        "least frequent value returned instead of the most frequent",
        "counts.index[counts == counts.iloc[0]]",
        "counts.index[counts == counts.iloc[-1]]",
    ),
    (
        "month name shifted by one",
        "MONTH_NAMES[month - 1]",
        "MONTH_NAMES[month % 12]",
    ),
    (
        "most common hour computed on the minutes",
        "_modes(start.dt.hour)",
        "_modes(start.dt.minute)",
    ),
    (
        "busiest trip built from the busiest start and end stations",
        'stats["mostCommonTrip"] = sorted((str(start), str(end)) for start, end in busiest)',
        'stats["mostCommonTrip"] = [(stats["mostCommonStartStation"][0], '
        'stats["mostCommonEndStation"][0])]',
    ),
    (
        "the two stations of a trip swapped",
        "sorted((str(start), str(end)) for start, end in busiest)",
        "sorted((str(end), str(start)) for start, end in busiest)",
    ),
    (
        "unused categories counted as trips",
        'df.groupby(["Start Station", "End Station"], observed=True, sort=False)',
        'df.groupby(["Start Station", "End Station"], observed=False, sort=False)',
    ),
    (
        "negative and infinite durations kept",
        'durations.between(0, float("inf"), inclusive="left")',
        "durations.notna()",
    ),
    (
        "durations of zero dropped",
        'inclusive="left"',
        'inclusive="neither"',
    ),
    (
        "mean divided by all rows, usable or not",
        '"meanTravelTime": float(usable.mean()),',
        '"meanTravelTime": float(usable.sum() / len(df)),',
    ),
    (
        "zero reported when there is no duration",
        'stats = {"totalTravelTime": None, "meanTravelTime": None}',
        'stats = {"totalTravelTime": 0.0, "meanTravelTime": 0.0}',
    ),
    (
        "values with a count of zero reported",
        "(item for item in counts if item[1])",
        "(item for item in counts)",
    ),
    (
        "counts sorted by name only",
        "key=lambda item: (-item[1], item[0])",
        "key=lambda item: item[0]",
    ),
    (
        "equal counts left in their order of appearance",
        "key=lambda item: (-item[1], item[0])",
        "key=lambda item: -item[1]",
    ),
    (
        "birth years that are not whole numbers kept",
        "years = years[years % 1 == 0]",
        "years = years.dropna()",
    ),
    (
        "earliest birth year takes the latest",
        'stats["earliestBirthYear"] = int(years.min())',
        'stats["earliestBirthYear"] = int(years.max())',
    ),
    (
        "implausible ages flagged above 120 instead of 100",
        "(ages > 100)",
        "(ages > 120)",
    ),
    (
        "answers compared without cleaning case and spaces",
        "answer = _clean(input(prompt))",
        "answer = input(prompt)",
    ),
    (
        "restart question inverted",
        'if restart in ("no", "n"):',
        'if restart in ("yes", "y"):',
    ),
]


def run_tests(folder):
    """Run the fast suite in ``folder``; return True when it passes."""
    environment = {k: v for k, v in os.environ.items() if k != "BIKESHARE_DATA_DIR"}
    command = [sys.executable, "-m", "pytest", "-q", "-x", "-m", "not realdata"]
    command += ["-p", "no:cacheprovider", *sys.argv[1:]]
    result = subprocess.run(command, cwd=folder, env=environment, capture_output=True, text=True)
    return result.returncode == 0


def main():
    source = (ROOT / PROGRAM).read_text()
    survivors = []
    with tempfile.TemporaryDirectory() as scratch:
        copy = Path(scratch) / "project"
        copy.mkdir()
        for name in (PROGRAM, "test_bike_investigation.py", "pyproject.toml"):
            shutil.copy(ROOT / name, copy / name)
        skip = shutil.ignore_patterns("__pycache__")
        shutil.copytree(ROOT / "tests", copy / "tests", ignore=skip)

        # The copy must be the module under test, and it must pass before any fault.
        probe = subprocess.run(
            [sys.executable, "-c", "import bike_investigation; print(bike_investigation.__file__)"],
            cwd=copy,
            capture_output=True,
            text=True,
            check=True,
        )
        if Path(probe.stdout.strip()).resolve() != (copy / PROGRAM).resolve():
            sys.exit(f"The tests would not import the copy but {probe.stdout.strip()}")
        if not run_tests(copy):
            sys.exit("The suite fails on the unmodified program: nothing can be concluded.")

        for label, before, after in FAULTS:
            if source.count(before) != 1:
                sys.exit(f"Fault '{label}': its text is found {source.count(before)} times.")
            (copy / PROGRAM).write_text(source.replace(before, after))
            caught = not run_tests(copy)
            print(f"{'caught  ' if caught else 'SURVIVED'}  {label}")
            if not caught:
                survivors.append(label)

    print(f"\n{len(FAULTS) - len(survivors)} of {len(FAULTS)} planted faults caught by the tests.")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
