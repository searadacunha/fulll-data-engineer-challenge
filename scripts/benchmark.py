"""Measure time and memory on the official files and write docs/performance.md.

The program was written with a few performance choices from the start. This script
measures each of them against the plain alternative it replaces, on the same machine and
the same data, so that docs/performance.md states measurements rather than claims. Times
change from one machine and one run to the next: they are medians of several runs, and the
file says where and when they were taken. It is not checked in CI for that reason.

Usage: python scripts/benchmark.py [--runs N]
"""

import argparse
import contextlib
import datetime
import io
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

import pandas as pd

import bike_investigation as bi

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TITLES = {"chicago": "Chicago", "new york city": "New York City", "washington": "Washington"}


def median_time(function, runs):
    """Median wall-clock time of ``function()`` over ``runs`` calls, in seconds."""
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        function()
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def megabytes(df):
    return df.memory_usage(deep=True).sum() / 1e6


def n(value):
    return f"{value:,}"


def quiet(function, *args):
    with contextlib.redirect_stdout(io.StringIO()):
        return function(*args)


def all_stats(df):
    for stats in (bi.time_stats, bi.station_stats, bi.trip_duration_stats, bi.user_stats):
        quiet(stats, df)


# The plain alternatives, written the way the statement's skeleton suggests at first sight.


def plain_read(path):
    df = pd.read_csv(path)
    df["Start Time"] = pd.to_datetime(df["Start Time"])
    df["End Time"] = pd.to_datetime(df["End Time"])
    return df


def plain_trip(df):
    return (df["Start Station"] + " -> " + df["End Station"]).mode()


def plain_strip(df):
    return df["Start Station"].str.split().str.join(" ")


PEAK_PROBE = """
import resource, sys
import pandas as pd
import bike_investigation as bi
sys.path.insert(0, {scripts!r})
from benchmark import plain_read
path = {path!r}
df = plain_read(path) if {plain!r} else bi.load_data({city!r}, "all", "all")
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(peak * (1 if sys.platform == "darwin" else 1024))
"""


def peak_memory(city, plain):
    """Peak resident memory of a fresh process that loads one city, in megabytes."""
    code = PEAK_PROBE.format(
        scripts=str(ROOT / "scripts"),
        path=str(DATA / bi.CITY_DATA[city]),
        plain=plain,
        city=city,
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return int(out.stdout.strip()) / 1e6


IMPORT_PROBE = """
import resource, sys
import pandas, bike_investigation
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(peak * (1 if sys.platform == "darwin" else 1024))
"""


def baseline_peak():
    """Peak memory of a fresh process that only imports pandas and the program."""
    code = IMPORT_PROBE
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return int(out.stdout.strip()) / 1e6


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def ms(value):
    return f"{value * 1000:,.1f} ms" if value < 0.01 else f"{value * 1000:,.0f} ms"


def change(ratios):
    """Describe time ratios (ours / plain) as '5% to 9% slower', '3% to 6% faster' or a mix."""
    low, high = min(ratios) - 1, max(ratios) - 1
    if low >= 0:
        return f"{low:.0%} to {high:.0%} slower"
    if high <= 0:
        return f"{-high:.0%} to {-low:.0%} faster"
    return f"between {-low:.0%} faster and {high:.0%} slower"


def factor(ratios):
    low, high = f"{min(ratios):,.0f}", f"{max(ratios):,.0f}"
    return f"about {low}" if low == high else f"{low} to {high}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5, help="runs per measurement (default 5)")
    runs = parser.parse_args().runs
    if not all((DATA / name).is_file() for name in bi.CITY_DATA.values()):
        sys.exit("The official files are missing: run scripts/fetch_data.py")

    steps = {}  # step -> city -> (plain, ours)
    whole, ratios = [], {key: [] for key in ("read", "memory", "parse", "trip", "clean")}
    for city in bi.CITY_DATA:
        path = DATA / bi.CITY_DATA[city]
        plain = plain_read(path)
        df = bi.load_data(city, "all", "all")
        text = pd.read_csv(path, usecols=["Start Time"], dtype=str)["Start Time"]
        stations = plain["Start Station"].astype("category")

        measured = {
            "Read the file": (
                median_time(lambda path=path: plain_read(path), runs),
                median_time(lambda city=city: bi.load_data(city, "all", "all"), runs),
            ),
            "Parse the start times": (
                median_time(lambda text=text: pd.to_datetime(text), runs),
                median_time(lambda text=text: bi._parse_times(text), runs),
            ),
            "Most common trip": (
                median_time(lambda plain=plain: plain_trip(plain), runs),
                median_time(lambda df=df: quiet(bi.station_stats, df), runs),
            ),
            "Clean the spaces of one station column": (
                median_time(lambda plain=plain: plain_strip(plain), runs),
                median_time(lambda s=stations: s.map(bi._squeeze, na_action="ignore"), runs),
            ),
        }
        memory = (megabytes(plain), megabytes(df))
        peaks = (peak_memory(city, True), peak_memory(city, False))
        for step, (a, b) in measured.items():
            steps.setdefault(step, {})[city] = f"{ms(a)} / {ms(b)}"
        steps.setdefault("Loaded frame in memory", {})[city] = (
            f"{memory[0]:,.1f} MB / {memory[1]:,.1f} MB"
        )
        steps.setdefault("Peak memory of the process", {})[city] = (
            f"{peaks[0]:,.0f} MB / {peaks[1]:,.0f} MB"
        )
        for key, step in (
            ("read", "Read the file"),
            ("parse", "Parse the start times"),
            ("trip", "Most common trip"),
            ("clean", "Clean the spaces of one station column"),
        ):
            a, b = measured[step]
            ratios[key].append(b / a if key in ("read", "parse") else a / b)
        ratios["memory"].append(memory[0] / memory[1])

        # The filter path of load_data on a frame already read: only the file read is skipped.
        with mock.patch.object(bi, "_read_city", return_value=df):
            filtering = median_time(lambda city=city: bi.load_data(city, "june", "friday"), runs)
        load = measured["Read the file"][1]
        stats = median_time(lambda df=df: all_stats(df), runs)
        whole.append([TITLES[city], ms(load), ms(filtering), ms(stats), ms(load + stats)])

    df = bi.load_data("chicago", "all", "all")
    bytes_per_trip = megabytes(df) * 1e6 / len(df)
    scale, per_million = [], []
    for repeat in (1, 4, 10):
        big = pd.concat([df] * repeat, ignore_index=True)
        elapsed = median_time(lambda big=big: all_stats(big), runs)
        per_million.append(elapsed / len(big) * 1e6)
        scale.append(
            [
                n(len(big)),
                f"{megabytes(big):,.0f} MB",
                ms(elapsed),
                ms(per_million[-1]),
            ]
        )
        del big

    explicit = (
        "faster"
        if max(ratios["parse"]) < 1
        else "not faster in every file"
        if min(ratios["parse"]) < 1
        else "not faster"
    )
    machine = f"{platform.machine()}, {platform.system()} {platform.release()}"
    cities = list(bi.CITY_DATA)
    lines = [
        "# Performance",
        "",
        f"Measured by `scripts/benchmark.py` on {datetime.date.today():%d %B %Y}, on "
        f"{machine}, Python {platform.python_version()}, pandas {pd.__version__}. "
        f"Each time is the median of {runs} runs; memory is measured with "
        "`DataFrame.memory_usage(deep=True)` and, for the peak, `getrusage` in a fresh process "
        f"(one that only imports pandas and the program peaks at {baseline_peak():,.0f} MB). "
        "Expect other figures on another machine.",
        "",
        "## Each choice against the plain alternative",
        "",
        "The program was written with these choices from the start: there is no slower "
        "earlier version. Each row compares a choice with the plain way of doing the same "
        "step, which reads the file with the defaults of `pd.read_csv`, lets pandas guess the "
        "date layout and keeps text columns as text. The program reads only the known columns, "
        "gives the date layout, and stores station names, user types and genders as categories "
        "(one small integer per row, each distinct text once).",
        "",
        "Each cell reads *plain alternative / this program*.",
        "",
        table(
            ["Step", *(TITLES[c] for c in cities)],
            [[step, *(values[c] for c in cities)] for step, values in steps.items()],
        ),
        "",
        f"- Reading a city with categories is {change(ratios['read'])} than the plain read, "
        f"and the loaded frame takes {factor(ratios['memory'])} times less memory.",
        "- The most common trip is computed "
        f"{factor(ratios['trip'])} times faster by grouping the two category columns than by "
        "joining the two names of every row into a text (and the program's time covers the "
        "three station statistics, not the trip alone).",
        "- Cleaning the station names is "
        f"{factor(ratios['clean'])} times faster once per distinct name than once per row.",
        f"- Giving the date layout is {explicit} than letting pandas guess it "
        f"({change(ratios['parse'])}): it is there so that no date is ever read with the day "
        "and the month swapped, not for speed.",
        "",
        "## Whole run per city",
        "",
        table(
            [
                "City",
                "load_data (all)",
                "Filters (june, friday) on a loaded frame",
                "Four statistics",
                "Load and statistics",
            ],
            whole,
        ),
        "",
        "## Scaling",
        "",
        "The Chicago frame repeated in memory, to see how the four statistics grow with the "
        "number of rows.",
        "",
        table(["Rows", "Frame in memory", "Four statistics", "Per million rows"], scale),
        "",
        f"From {scale[0][0]} to {scale[-1][0]} rows the time per million rows stays between "
        f"{ms(min(per_million))} and {ms(max(per_million))}: it grows linearly, as expected "
        "from statistics that each make one pass over the rows (value counts, one group-by on "
        f"the two station columns, sums). A loaded Chicago trip takes {bytes_per_trip:,.0f} "
        "bytes, so a file too large for memory would be far beyond this data set; it would "
        "need reading in chunks.",
        "",
    ]
    (ROOT / "docs" / "performance.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
