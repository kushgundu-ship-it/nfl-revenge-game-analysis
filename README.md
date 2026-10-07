# NFL revenge-game analysis — Stage 1

This stage prepares a reproducible dataset for the question in [project.md](project.md).
It stops at downloading, importing, cleaning, and checking data. There is no
former-team classification, revenge-game calculation, rolling baseline, or dashboard yet.

## Start here

Open Terminal and run these commands one line at a time:

```bash
cd /Users/kushg/SQL_NFL_Project
source .venv/bin/activate
python scripts/load_data.py --offline
python scripts/load_data.py --offline --verify-rerun
python scripts/query.py
```

The first command selects your folder. Activating `.venv` makes `python` use this
project's installed packages. The first ingestion rebuilds the database from saved
files. The second compares row counts and data checksums with that successful run.
The last command prints counts, checks, and a small sample. `deactivate` leaves the
virtual environment when you finish.

To allow downloading missing source files, run:

```bash
python scripts/load_data.py
```

Existing downloads are reused, not refreshed or overwritten. Normal reruns therefore
need no internet. `--offline` additionally refuses to download if a file is missing.
`--verify-rerun` requires a previous successful run and identical inputs and outputs.

For a fresh setup on a computer with Python 3.9 or newer and internet access:

```bash
cd /Users/kushg/SQL_NFL_Project
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/load_data.py
python scripts/load_data.py --offline --verify-rerun
python scripts/query.py
```

Python 3.9.6 and DuckDB 1.4.4 were used for this checkpoint. DuckDB is pinned to the
tested version in `requirements.txt`. No pandas, database server, API key, or separate
DuckDB command-line installation is needed.

## What is stored where?

The pipeline has three layers:

1. **Raw files:** unchanged downloads in `data/raw/`. Parquet is a compact, typed
   data file format; DuckDB reads it directly. The schedule comes as readable CSV.
2. **Raw tables:** source rows inside `data/processed/nfl.duckdb`. Player statistics
   retain all positions and postseason rows. Schedules retain all game types for
   2015–2025. The original schedule file contains additional seasons and is kept whole.
3. **Clean views:** saved SQL queries on the raw tables. `clean_player_game_stats`
   selects only 2015–2025 regular-season QB, RB, WR, and TE records and adds schedule
   information. A view does not edit the underlying raw data.

Python handles file downloads and runs SQL; SQL handles the data transformations.
Joins use the source `game_id`, and player identity uses `player_id`, never names.
The schedule join is a **left join**, which keeps a player row even if its schedule
is missing, so validation can expose the problem. Missing statistics remain missing;
they are not automatically changed to zero.

The SQL maps OAK to LV, SD to LAC, STL/LAR to LA, and JAC to JAX. These codes represent
franchises across relocation. Original team codes remain in `source_team` and
`source_opponent_team`. Source game IDs remain unchanged. The current player files
already use canonical franchise codes, while historical schedules may not.

Each ingestion rebuilds the two raw tables instead of appending records. This keeps
reruns from adding duplicate copies. The rebuild and checks run in one transaction:
if an error check fails, DuckDB rolls back to the previous database state. Raw files
are never deleted by ingestion. Do not add manual edits to the imported raw tables;
they will be replaced from the snapshot on the next run.

## Sources and reproducibility

The player files are the current weekly files documented by
[nflreadr](https://nflreadr.nflverse.com/reference/load_player_stats.html), one per season:

```text
https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.parquet
```

Schedules use the CSV in nflverse's official nfldata repository:

```text
https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv
```

See the [schedule documentation](https://nflreadr.nflverse.com/reference/load_schedules.html)
and [player dictionary](https://nflreadr.nflverse.com/articles/dictionary_player_stats.html).
No incomplete 2026 records enter the database's raw tables or clean view.

`data/raw/manifest.json` records every URL, file size, SHA-256 checksum (a fingerprint
of the file bytes), and the time it was recorded. It distinguishes Python downloads
from files already present. Upstream URLs can change their contents; this saved
snapshot and manifest are the reproducibility record. A changed cached file is an
error, not silently accepted. Archive the full raw directory and manifest together
before intentionally adopting updated upstream data.

## Checkpoint results and things to understand

The ingestion and a second complete ingestion with `--verify-rerun` succeeded.
All 20 error checks passed. All 11 seasons are present. There are no duplicate
player-game groups in either the raw table or the clean view. Every cleaned row has
player and game IDs, valid team codes, PPR points, and a matching schedule. Every
regular-season schedule game is represented. The rerun produced identical counts
and data checksums for both raw tables and the cleaned view.

Two raw-data warnings remain visible:

- 236 rows have a missing player ID. All are named `Team` in the source and have
  no position. They are retained in the raw table and excluded by the four-position
  filter, not assigned made-up IDs.
- Two of those rows also have no opponent: `2016_10_CLE_BAL` for CLE and
  `2018_07_DEN_ARI` for ARI. Neither is in the cleaned view.

2022 has 271 regular-season games rather than 272 because the Bills–Bengals game
was canceled. This is an expected exception, documented in the
[NFL announcement](https://www.buffalobills.com/news/nfl-says-neutral-site-afc-championship-game-is-possible-bills-bengals-week-17-ga).

These checks establish structural consistency, not that every upstream statistic is
correct. Box-score records also do not represent every rostered player or every snap.
That distinction will matter when defining appearances in a later stage.

The authoritative current output is `data/processed/validation_report.json`.
[docs/stage1_results.md](docs/stage1_results.md) provides a readable checkpoint table.

## Environment limitations at setup

The assistant's environment blocked Python/pip internet access. The raw files and
the official DuckDB wheel were downloaded using permitted `curl` commands, and the
wheel was installed into `.venv` without network access. The Python downloader is
implemented, but its live HTTPS download path could not be verified here. The actual
loads and repeated-load verification used those saved, real downloads.

Git is installed (2.50.1), but `git init` failed with `Operation not permitted` when
trying to create `.git`. No repository, commit, or remote was created. To finish that
setup step yourself from your normal Terminal:

```bash
cd /Users/kushg/SQL_NFL_Project
git init
git status --short
```

Do not commit or publish yet. `.gitignore` is already prepared to exclude the virtual
environment, raw downloads, database files, generated reports, and `.env` secrets.

## Files you can inspect

| File or folder | Purpose |
| --- | --- |
| `project.md` | Your original project brief, unchanged. |
| `README.md` | This guide and exact setup/rerun commands. |
| `requirements.txt` | The one third-party Python dependency, with its tested version. |
| `.gitignore` | Keeps local data, packages, and common secrets out of future commits. |
| `.venv/` | Isolated Python environment and installed DuckDB package. |
| `scripts/load_data.py` | Downloads missing files, checks source fingerprints, runs SQL, validates, and saves a report. |
| `scripts/query.py` | Runs a SQL file against the saved database in read-only mode. |
| `sql/01_ingestion.sql` | Main SQL: loads raw tables, standardizes team codes, and creates cleaned views. |
| `sql/02_validation.sql` | Creates the data-quality checks and season count view. |
| `sql/03_inspect.sql` | Example queries to print counts, validation results, and five real rows. |
| `data/raw/stats_player_week_2015.parquet` … `2025.parquet` | The 11 unchanged weekly player-stat files. |
| `data/raw/games.csv` | The unchanged full schedule download. |
| `data/raw/manifest.json` | Source URLs, timestamps, byte sizes, and file checksums. |
| `data/processed/nfl.duckdb` | Persistent database containing the raw tables and SQL views. |
| `data/processed/validation_report.json` | Latest successful run's checks, counts, sample, and rerun result. |
| `data/processed/last_failed_run.json` | If present, diagnostic output from the most recent failed attempt; may predate a successful run. The initial strict check detected the two raw Team rows described above. |
| `data/raw/.gitkeep`, `data/processed/.gitkeep` | Empty placeholders so future Git commits can preserve the folders. |
| `docs/data_dictionary.md` | Explains the main tables and fields. |
| `docs/stage1_results.md` | Human-readable checkpoint results and open setup items. |

To experiment, edit the SELECT queries in `sql/03_inspect.sql`, then run:

```bash
python scripts/query.py sql/03_inspect.sql
```

The query runner opens the database read-only, so exploration cannot alter it.
Read `sql/01_ingestion.sql` next, starting with the final `CREATE OR REPLACE VIEW`.
Pause here to review before beginning former-team or revenge-game logic.
