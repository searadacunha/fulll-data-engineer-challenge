# References and technical decisions

What was read to build this solution and what was decided from it. Only documentation,
statements and licence texts were read: no code from another project is used.

## The challenge and its data

- **fulll/hiring**, folder `DataEngineer/Junior` at commit
  [`68d9abfd`](https://github.com/fulll/hiring/tree/68d9abfd8bfc47f8c240bcd9b0bf305886121004/DataEngineer/Junior):
  the statement, the skeleton, the test file, `pyproject.toml` and `Bike_raw_data.zip`. The
  repository has no licence (`license: null` in the GitHub API).
- **Origin of the files.** They have the columns and the period of the data set of Udacity's
  US bikeshare course project. Its statement, read in a public repository
  ([juliaobenauer/us-bikeshare-data-project](https://github.com/juliaobenauer/us-bikeshare-data-project),
  README only), says the data were provided by Motivate, "randomly selected" for the first six
  months of 2017 and condensed to six core columns, plus Gender and Birth Year for Chicago and
  New York City.
- **Licences of the operators**, in their current versions:
  [Capital Bikeshare Data License Agreement](https://capitalbikeshare.com/data-license-agreement)
  (updated 11 January 2022), [Divvy Data License Agreement](https://divvybikes.com/data-license-agreement)
  and [Citi Bike Data Sharing Policy](https://citibikenyc.com/data-sharing-policy). All three
  grant the right to use, copy, analyse and distribute the data "in your product or service",
  and forbid to "Host, stream, publish, distribute, sublicense, or sell the Data as a
  stand-alone dataset", while allowing the data "as source material, as applicable, in
  analyses, reports, or studies published or distributed for non-commercial purposes".
- **GitHub, [Licensing a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)**:
  without a licence, "no one may reproduce, distribute, or create derivative works from your
  work".

**Decision.** The CSV files are not committed. `scripts/fetch_data.py` downloads the archive
from the fulll repository at a pinned commit and checks its SHA-256 and that of each file.
This is a reading of the texts, not legal advice; the terms in force when the 2017 files were
first published were not read.

## pandas 3.1 (BSD-3-Clause)

Read: the reference pages of
[`to_datetime`](https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html),
[`read_csv`](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html),
[`Series.mode`](https://pandas.pydata.org/docs/reference/api/pandas.Series.mode.html),
[`Series.value_counts`](https://pandas.pydata.org/docs/reference/api/pandas.Series.value_counts.html),
[`DataFrame.groupby`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.groupby.html)
and [`Series.dt.day_name`](https://pandas.pydata.org/docs/reference/api/pandas.Series.dt.day_name.html),
and the release notes of [3.0](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html) and
[3.1](https://pandas.pydata.org/docs/whatsnew/v3.1.0.html). Each point below was also run on
pandas 3.1.1.

| Fact | Decision |
|---|---|
| `to_datetime` with an explicit `format` and `errors="coerce"` matches exactly; `format="mixed"` parses each value on its own, and turned `05/06/2017` into 6 May next to `13/06/2017` read as 13 June. The documentation calls it risky. | Two explicit layouts, tried in order, nothing inferred. |
| `value_counts` keeps equal counts in order of appearance (stable since 3.0). | Ties are sorted by the program, so the result does not depend on row order. |
| A filtered categorical column still lists its unused categories, with a count of 0. | Zero counts are dropped before any "most common" or count is reported. |
| The default of `observed` in `groupby` became `True` in 3.0; with `False`, two categorical keys produce every pair of stations. | `observed=True` is passed explicitly. |
| Text columns are `str` in 3.x, backed by Python objects when pyarrow is not installed. | Station names, user types and genders are read as categories (see [performance.md](performance.md)). |
| Copy-on-Write is the default in 3.0. | No defensive `copy()` after filtering. |
| `Series.dt.dayofweek` is deprecated in 3.1 (`Pandas4Warning`). | `day_of_week` is used; the tests turn warnings into errors. |
| pandas 3.1.1 requires Python 3.11 or later ([PyPI metadata](https://pypi.org/pypi/pandas/3.1.1/json)). | `requires-python = ">=3.11"`. |

## pytest 9 (MIT)

- [unittest integration](https://docs.pytest.org/en/stable/how-to/unittest.html): inside a
  `unittest.TestCase`, fixtures (except autouse ones) and parametrization do not work. The
  provided file therefore stays a `TestCase` and uses `subTest`; parametrized tests and
  fixtures live in `tests/`.
- [Capturing output](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html)
  with `capsys.readouterr()`, and `monkeypatch.setattr("builtins.input", ...)` to script the
  terminal.
- [Configuration](https://docs.pytest.org/en/stable/reference/customize.html): the native
  `[tool.pytest]` table and `strict = true` (pytest 9.0), which make unregistered markers,
  unknown options and duplicate parametrize ids errors.

## Hypothesis (MPL-2.0)

- Adopted for two properties: every statistic agrees with a plain Python recomputation on
  random small frames, in any row order; and `get_filters` never fails on arbitrary text.
  `scripts/mutation_check.py` shows what they add: one planted mistake (equal counts listed
  in order of appearance) was caught only by them until an explicit test was added.
- `deadline=None`, since pandas calls vary in duration. On CI Hypothesis loads its `ci`
  profile by itself (derandomized, no example database), as `hypothesis/_settings.py` shows.
- `hypothesis.extra.pandas` is not used: its
  [documentation](https://hypothesis.readthedocs.io/en/latest/reference/strategies.html)
  confirms pandas 1.5 to 2.2 only. Rows are generated as plain dictionaries instead.
- `@given` with function-scoped fixtures triggers a health check: the property tests use no
  fixture and patch `input` inside the test body.
- MPL-2.0 covers Hypothesis's own files; here it is only a test dependency.

## Pandera 0.36 (MIT): not adopted

It validates data frames against declared schemas. For eight columns it would bring
pydantic, typeguard, typing_inspect and typing_extensions
([PyPI metadata](https://pypi.org/pypi/pandera/0.36.0/json)), and its support of pandas 3 is
not stated in what was read. `load_data` checks the required columns and converts every type
explicitly, and the tests cover both.

## Ruff 0.17 (MIT)

[Configuration](https://docs.astral.sh/ruff/configuration/) in `pyproject.toml`, with the
target version inferred from `requires-python`; rule sets E, W, F, I, UP, B, C4, SIM, PT, PD
and RUF; the formatter, whose conflicting lint rules are not selected. CI runs `ruff check`
and `ruff format --check`.

## uv 0.13 (Apache-2.0 or MIT)

[Project workflow](https://docs.astral.sh/uv/concepts/projects/sync/): `uv.lock` is
universal and committed; `uv sync --locked` fails in CI if it is stale; the `dev` dependency
group is installed by default. In CI, uv is pinned to 0.13.0 and `astral-sh/setup-uv` to
v10.3.3, its latest release: the action has no major version tag after v7.

## Python and packaging

- [Python versions](https://devguide.python.org/versions/): 3.10 reached its end of life in
  October 2026. CI runs 3.11, the oldest version pandas 3 supports, and 3.14.
- [PyPI classifiers](https://pypi.org/classifiers/): "To prevent a package from being uploaded
  to PyPI, use the special Private :: Do Not Upload classifier", and "the use of License Trove
  classifiers is deprecated" since PEP 639. The provided `License :: OSI Approved :: Private`
  is not a registered classifier.
