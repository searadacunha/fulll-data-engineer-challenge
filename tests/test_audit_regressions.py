"""Regressions found by the audit of 2026-11-15: each fails on c945448, passes after the fix."""

import contextlib
import io
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from bike_investigation import load_data, station_stats, time_stats, trip_duration_stats, user_stats

ROOT = Path(__file__).resolve().parents[1]
HEADER = ",Start Time,End Time,Trip Duration,Start Station,End Station,User Type"
ROW = "{i},2017-01-0{d} 08:05:10,2017-01-0{d} 08:15:10,600,{start},Bravo Ave,Subscriber"


def _write(tmp_path, monkeypatch, text):
    (tmp_path / "chicago.csv").write_text(text, encoding="utf-8")
    monkeypatch.setenv("BIKESHARE_DATA_DIR", str(tmp_path))


def _quiet(function, *args):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        result = function(*args)
    return result, out.getvalue()


@pytest.mark.parametrize("with_row_id", [True, False])
def test_a_row_with_an_extra_field_is_refused_not_shifted(monkeypatch, tmp_path, with_row_id):
    rows = [ROW.format(i=0, d=2, start="Alpha St"), ROW.format(i=1, d=3, start="Clark St, North")]
    lines = [HEADER, *rows] if with_row_id else [HEADER[1:], *(r.split(",", 1)[1] for r in rows)]
    _write(tmp_path, monkeypatch, "\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="Expected"):
        load_data("chicago", "all", "all")


@pytest.mark.parametrize("prefix", ["\n", "\r\n"])
def test_duplicate_headers_are_refused_after_a_leading_blank_line(monkeypatch, tmp_path, prefix):
    _write(
        tmp_path,
        monkeypatch,
        prefix + HEADER + ",Start Time\n" + ROW.format(i=0, d=2, start="A") + ",x\n",
    )
    with pytest.raises(ValueError, match="duplicate CSV column names"):
        load_data("chicago", "all", "all")


def test_an_unclosed_quote_in_the_header_is_a_value_error(monkeypatch, tmp_path):
    # Past 131,072 characters the csv module raised _csv.Error, which main() did not catch.
    rows = [ROW.format(i=i, d=2, start="Alpha St") for i in range(3000)]
    _write(tmp_path, monkeypatch, '"' + "\n".join([HEADER, *rows]) + "\n")
    with pytest.raises(ValueError, match="EOF inside string"):
        load_data("chicago", "all", "all")


def test_a_cell_of_spaces_is_a_missing_value(monkeypatch, tmp_path):
    rows = [
        ROW.format(i=0, d=2, start="   "),
        ROW.format(i=1, d=3, start="   "),
        ROW.format(i=2, d=4, start="Alpha"),
    ]
    _write(tmp_path, monkeypatch, "\n".join([HEADER, *rows]) + "\n")
    df = load_data("chicago", "all", "all")
    stats, _ = _quiet(station_stats, df)
    assert stats["mostCommonStartStation"] == ["Alpha"]
    assert int(df["Start Station"].isna().sum()) == 2


def test_a_huge_finite_duration_is_reported_without_crashing():
    df = pd.DataFrame({"Trip Duration": [8.64e13, 600]})
    stats, out = _quiet(trip_duration_stats, df)
    assert stats["totalTravelTime"] == 8.64e13 + 600
    assert "Total travel time: 86,400,000,000,600 seconds" in out


def test_int64_durations_are_summed_without_wrapping():
    df = pd.DataFrame({"Trip Duration": pd.array([2**62, 2**62], dtype="int64")})
    stats, _ = _quiet(trip_duration_stats, df)
    assert stats["totalTravelTime"] == 2.0**63


def test_a_repeated_index_label_does_not_break_the_statistics():
    # The second layout is read only for the values the first one leaves unread: aligned by label.
    parts = [
        pd.DataFrame({"Start Time": [start], "Birth Year": [year]})
        for start, year in [
            ("2017-06-05 08:00:00", 1990),
            ("05/06/2017 09:00:00", 2020),
            ("06/06/2017 10:00:00", 1900),
        ]
    ]
    joined = pd.concat(parts)  # index [0, 0, 0]
    fresh = joined.reset_index(drop=True)
    assert _quiet(time_stats, joined)[0] == _quiet(time_stats, fresh)[0]
    _, out_joined = _quiet(user_stats, joined)
    _, out_fresh = _quiet(user_stats, fresh)
    assert out_joined.split("This took")[0] == out_fresh.split("This took")[0]


@pytest.mark.realdata
@pytest.mark.usefixtures("official_data")
def test_make_docs_reads_the_official_files_even_if_the_data_dir_points_elsewhere():
    env = {**os.environ, "BIKESHARE_DATA_DIR": str(ROOT / "tests" / "data")}
    result = subprocess.run(
        [sys.executable, "scripts/make_docs.py", "--check"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
