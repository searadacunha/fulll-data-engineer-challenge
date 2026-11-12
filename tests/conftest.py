"""Shared fixtures: which folder load_data reads, and scripted answers for input()."""

import os
from pathlib import Path

import pytest

from bike_investigation import CITY_DATA

SYNTHETIC_DIR = Path(__file__).parent / "data"
OFFICIAL_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def synthetic_data(monkeypatch):
    """Point load_data at the small hand-checked files of tests/data."""
    monkeypatch.setenv("BIKESHARE_DATA_DIR", str(SYNTHETIC_DIR))
    return SYNTHETIC_DIR


@pytest.fixture
def official_data(monkeypatch):
    """Point load_data at the official files, skipping the test when they are not fetched.

    With BIKESHARE_REQUIRE_DATA=1 (set in CI) a missing file is a failure, so that the
    integration tests can never be skipped silently.
    """
    missing = [name for name in CITY_DATA.values() if not (OFFICIAL_DIR / name).is_file()]
    if missing:
        message = f"official data not found ({', '.join(missing)}): python scripts/fetch_data.py"
        if os.environ.get("BIKESHARE_REQUIRE_DATA") == "1":
            pytest.fail(message)
        pytest.skip(message)
    monkeypatch.setenv("BIKESHARE_DATA_DIR", str(OFFICIAL_DIR))
    return OFFICIAL_DIR


@pytest.fixture
def answers(monkeypatch):
    """Script the terminal: ``answers("chicago", "all", ...)`` feeds input() line by line.

    An exception instance in the script is raised instead of returned, and the input is
    "closed" (EOFError) once the script is exhausted, like a terminal after Ctrl-D.
    """

    def script(*lines):
        queue = list(lines)

        def fake_input(prompt=""):
            print(prompt, end="")
            if not queue:
                raise EOFError
            line = queue.pop(0)
            if isinstance(line, BaseException):
                raise line
            return line

        monkeypatch.setattr("builtins.input", fake_input)
        return queue

    return script
