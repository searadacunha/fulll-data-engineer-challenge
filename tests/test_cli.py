"""The interactive part: get_filters() and the main() loop, driven by scripted answers."""

import pytest

from bike_investigation import get_filters, main


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        (["chicago", "all", "all"], ("chicago", "all", "all")),
        (["Chicago", "ALL", "All"], ("chicago", "all", "all")),
        (["  new   YORK city ", " June", "MONDAY\t"], ("new york city", "june", "monday")),
        (["WASHINGTON", "january", "Sunday "], ("washington", "january", "sunday")),
        (["new york city", "february", "saturday"], ("new york city", "february", "saturday")),
    ],
)
def test_get_filters_ignores_case_and_extra_spaces(answers, typed, expected):
    left = answers(*typed)
    assert get_filters() == expected
    assert left == []


def test_get_filters_asks_again_until_the_answer_is_valid(answers, capsys):
    left = answers(
        "paris",  # not a city of the data set
        "",  # empty answer
        "chicago",
        "july",  # the data stop in June
        "13",
        "all",
        "funday",
        "sun",  # no abbreviation
        "sunday",
    )

    assert get_filters() == ("chicago", "all", "sunday")

    assert left == []
    out = capsys.readouterr().out
    assert out.count("is not a valid choice") == 6
    assert "'paris' is not a valid choice. Please type one of: chicago, new york city" in out
    assert "'july' is not a valid choice. Please type one of: all, january" in out
    assert "'funday' is not a valid choice. Please type one of: all, monday" in out


def test_get_filters_lets_a_closed_input_reach_the_caller(answers):
    answers("chicago")  # the input is closed before the month is given
    with pytest.raises(EOFError):
        get_filters()


def test_main_prints_the_four_reports(answers, synthetic_data, capsys):
    answers("chicago", "all", "all", "no")

    assert main() is None

    out = capsys.readouterr().out
    for line in (
        "Most common month: January",
        "Most common day of week: Monday",
        "Most common start hour: 08:00",
        "Most common start station: Alpha St",
        "Most common end station: Bravo Ave",
        "Most common trip: Charlie Sq -> Delta Rd",
        "Total travel time: 11,000 seconds (3:03:20)",
        "Mean travel time: 1,000.0 seconds (0:16:40)",
        "  Subscriber: 7",
        "  Male: 5",
        "  (3 trip(s) with no value recorded)",
        "Year of birth: earliest 1899, most recent 2001, most common 1990",
        "  (1 trip(s) by a rider not yet born or older than 100, kept as recorded)",
    ):
        assert line in out


def test_main_restarts_on_yes_and_asks_again_on_an_unclear_answer(answers, synthetic_data, capsys):
    left = answers("chicago", "january", "all", "maybe", "YES", "washington", "all", "all", " n ")

    main()

    assert left == []
    out = capsys.readouterr().out
    assert out.count("Hello! Let's explore some bikeshare data!") == 2
    assert "'maybe' is not a valid choice. Please type one of: yes, y, no, n." in out
    assert "Total travel time: 2,150 seconds" in out  # Chicago in January
    assert "Total travel time: 500 seconds" in out  # Washington
    assert "Gender: not available in this data set" in out


def test_main_reports_an_empty_selection(answers, synthetic_data, capsys):
    answers("chicago", "april", "all", "no")

    main()

    out = capsys.readouterr().out
    assert "No trip matches these filters." in out
    assert "Calculating" not in out


def test_main_survives_missing_files(answers, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BIKESHARE_DATA_DIR", str(tmp_path))
    answers("chicago", "all", "all", "no")

    main()

    out = capsys.readouterr().out
    assert "Could not load the data: chicago.csv not found" in out
    assert "scripts/fetch_data.py" in out


@pytest.mark.parametrize(
    "script",
    [
        [],  # input closed straight away
        ["chicago", "all"],  # closed in the middle of the questions
        ["chicago", "all", "all"],  # closed at the restart question
        [KeyboardInterrupt()],  # Ctrl-C at the first question
        ["chicago", "all", "all", KeyboardInterrupt()],  # Ctrl-C at the restart question
    ],
)
def test_main_ends_cleanly_when_the_input_is_closed_or_interrupted(
    answers, synthetic_data, capsys, script
):
    answers(*script)

    assert main() is None  # no exception, no SystemExit

    assert capsys.readouterr().out.rstrip().endswith("Input closed, goodbye.")
