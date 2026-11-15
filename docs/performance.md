# Performance

Measured by `scripts/benchmark.py` on 15 November 2026, on arm64, Darwin 23.6.0, Python 3.14.7, pandas 3.1.1. Each time is the median of 5 runs; memory is measured with `DataFrame.memory_usage(deep=True)` and, for the peak, `getrusage` in a fresh process (one that only imports pandas and the program peaks at 77 MB). Expect other figures on another machine.

## Each choice against the plain alternative

The program was written with these choices from the start: there is no slower earlier version. Each row compares a choice with the plain way of doing the same step, which reads the file with the defaults of `pd.read_csv`, lets pandas guess the date layout and keeps text columns as text. The program keeps only the known columns, gives the date layout, and stores station names, user types and genders as categories (one small integer per row, each distinct text once).

Each cell reads *plain alternative / this program*.

| Step | Chicago | New York City | Washington |
|---|---|---|---|
| Read the file | 256 ms / 288 ms | 228 ms / 264 ms | 319 ms / 435 ms |
| Parse the start times | 31 ms / 35 ms | 32 ms / 38 ms | 43 ms / 52 ms |
| Most common trip | 86 ms / 11 ms | 112 ms / 16 ms | 124 ms / 17 ms |
| Clean the spaces of one station column | 156 ms / 0.3 ms | 196 ms / 0.5 ms | 233 ms / 0.6 ms |
| Loaded frame in memory | 87.8 MB / 11.5 MB | 86.0 MB / 11.5 MB | 70.7 MB / 8.8 MB |
| Peak memory of the process | 221 MB / 189 MB | 214 MB / 169 MB | 207 MB / 189 MB |

- Reading a city with categories is 12% to 36% slower than the plain read, and the loaded frame takes 7 to 8 times less memory.
- The most common trip is computed 7 to 8 times faster by grouping the two category columns than by joining the two names of every row into a text (and the program's time covers the three station statistics, not the trip alone).
- Cleaning the station names is 360 to 469 times faster once per distinct name than once per row.
- Giving the date layout is not faster than letting pandas guess it (14% to 21% slower): it is there so that no date is ever read with the day and the month swapped, not for speed.

## Whole run per city

| City | load_data (all) | Filters (june, friday) on a loaded frame | Four statistics | Load and statistics |
|---|---|---|---|---|
| Chicago | 288 ms | 4.5 ms | 55 ms | 342 ms |
| New York City | 264 ms | 4.8 ms | 82 ms | 346 ms |
| Washington | 435 ms | 6.8 ms | 32 ms | 466 ms |

## Scaling

The Chicago frame repeated in memory, to see how the four statistics grow with the number of rows.

| Rows | Frame in memory | Four statistics | Per million rows |
|---|---|---|---|
| 300,000 | 12 MB | 70 ms | 234 ms |
| 1,200,000 | 46 MB | 252 ms | 210 ms |
| 3,000,000 | 114 MB | 557 ms | 186 ms |

From 300,000 to 3,000,000 rows the time per million rows stays between 186 ms and 234 ms: it grows linearly, as expected from statistics that each make one pass over the rows (value counts, one group-by on the two station columns, sums). A loaded Chicago trip takes 38 bytes, so a file too large for memory would be far beyond this data set; it would need reading in chunks.
