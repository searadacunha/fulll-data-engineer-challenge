"""Reject ambiguous source headers before pandas silently mangles duplicates."""

import pytest

from bike_investigation import CORE_COLUMNS, load_data


@pytest.mark.parametrize(
    "columns",
    [
        (*CORE_COLUMNS, "Start Time"),
        (*CORE_COLUMNS, "extra", "extra"),
    ],
)
def test_duplicate_csv_headers_are_rejected(monkeypatch, tmp_path, columns):
    (tmp_path / "chicago.csv").write_text(
        ",".join(columns) + "\n" + ",".join(["value"] * len(columns)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BIKESHARE_DATA_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="duplicate CSV column names"):
        load_data("chicago", "all", "all")


def test_header_reader_accepts_unnamed_index_column_and_bom(monkeypatch, tmp_path):
    columns = ("", *CORE_COLUMNS)
    (tmp_path / "chicago.csv").write_text(
        "\ufeff" + ",".join(columns) + "\n"
        + ",2017-01-02 08:05:10,2017-01-02 08:15:10,600,Alpha St,Bravo Ave,Subscriber\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BIKESHARE_DATA_DIR", str(tmp_path))
    assert len(load_data("chicago", "all", "all")) == 1
