# Performance

Measured by `scripts/benchmark.py` on 12 November 2026, on arm64, Darwin 23.6.0, Python 3.14.7, pandas 3.1.1. Each time is the median of 5 runs; memory is measured with `DataFrame.memory_usage(deep=True)` and, for the peak, `getrusage` in a fresh process (one that only imports pandas and the program peaks at 77 MB). Expect other figures on another machine.

## Each choice against the plain alternative

The program was written with these choices from the start: there is no slower earlier version. Each row compares a choice with the plain way of doing the same step, which reads the file with the defaults of `pd.read_csv`, lets pandas guess the date layout and keeps text columns as text. The program reads only the known columns, gives the date layout, and stores station names, user types and genders as categories (one small integer per row, each distinct text once).

Each cell reads *plain alternative / this program*.

| Step | Chicago | New York City | Washington |
|---|---|---|---|
| Read the file | 183 ms / 203 ms | 183 ms / 201 ms | 181 ms / 222 ms |
| Parse the start times | 26 ms / 32 ms | 26 ms / 30 ms | 27 ms / 30 ms |
| Most common trip | 67 ms / 9.0 ms | 72 ms / 9.6 ms | 68 ms / 8.9 ms |
| Clean the spaces of one station column | 122 ms / 0.3 ms | 119 ms / 0.4 ms | 135 ms / 0.3 ms |
| Loaded frame in memory | 87.8 MB / 11.5 MB | 86.0 MB / 11.5 MB | 70.7 MB / 8.8 MB |
| Peak memory of the process | 219 MB / 174 MB | 212 MB / 168 MB | 204 MB / 175 MB |

- Reading a city with categories is 10% to 23% slower than the plain read, and the loaded frame takes 7 to 8 times less memory.
- The most common trip is computed 7 to 8 times faster by grouping the two category columns than by joining the two names of every row into a text (and the program's time covers the three station statistics, not the trip alone).
- Cleaning the station names is 325 to 445 times faster once per distinct name than once per row.
- Giving the date layout is not faster than letting pandas guess it (13% to 22% slower): it is there so that no date is ever read with the day and the month swapped, not for speed.

## Whole run per city

| City | load_data (all) | Filters (june, friday) on a loaded frame | Four statistics | Load and statistics |
|---|---|---|---|---|
| Chicago | 203 ms | 3.6 ms | 43 ms | 246 ms |
| New York City | 201 ms | 2.9 ms | 48 ms | 250 ms |
| Washington | 222 ms | 4.1 ms | 19 ms | 241 ms |

## Scaling

The Chicago frame repeated in memory, to see how the four statistics grow with the number of rows.

| Rows | Frame in memory | Four statistics | Per million rows |
|---|---|---|---|
| 300,000 | 12 MB | 45 ms | 149 ms |
| 1,200,000 | 46 MB | 173 ms | 145 ms |
| 3,000,000 | 114 MB | 442 ms | 147 ms |

From 300,000 to 3,000,000 rows the time per million rows stays between 145 ms and 149 ms: it grows linearly, as expected from statistics that each make one pass over the rows (value counts, one group-by on the two station columns, sums). A loaded Chicago trip takes 38 bytes, so a file too large for memory would be far beyond this data set; it would need reading in chunks.
