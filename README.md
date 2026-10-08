# NFL revenge-game analysis — Stages 1 and 2

Stage 1 prepares a reproducible dataset for the question in [project.md](project.md).
Stage 2 identifies games against qualifying former teams using only earlier
appearances. There are no rolling baselines, revenge uplift calculations, or dashboards yet.

## Stage 2: former teams and revenge games

From the project folder, run:

```bash
cd /Users/kushg/SQL_NFL_Project
source .venv/bin/activate
python scripts/build_stage2.py
python scripts/query.py sql/06_stage2_inspect.sql
python -m unittest discover -s tests -v
```

The builder runs both Stage 1 and Stage 2 database checks and confirms Stage 1 data
was not changed. The sample query is read-only. The tests use isolated in-memory
databases; their small synthetic examples never enter the real project database.

The current snapshot has **875 revenge-game performances by 359 players**, including
**545 first qualifying meetings** across 61,977 player-games. A performance is one
player in one game; several players can qualify in the same NFL game.

The rule is: find the same stable `player_id` in earlier records, count appearances
for the current opponent, and require at least four. Only records with
`earlier.game_date < current.game_date` count. Current-day and future records cannot
contribute. Team codes already represent franchises, so Oakland and Las Vegas count
as the same team. Names are used only for display.

`is_first_meeting_with_former_team` means the first **qualifying** revenge game for a
player/opponent franchise in this dataset. Facing a team before playing for it does
not count as a former-team meeting. Meetings before the four-appearance threshold
do not consume the flag. The flag does not reset after another transfer or a return
to the same team. Different former teams have separate first-meeting flags.

History begins in 2015 and uses only the cleaned regular-season QB/RB/WR/TE records.
It is not complete career history: pre-2015 service, postseason games, other positions,
and unrecorded appearances are not counted. Early seasons therefore have less observable
history, and "first" means first observed qualifying meeting, not necessarily first
career reunion. No new historical data was downloaded in Stage 2.

Read [docs/stage2_results.md](docs/stage2_results.md) for ten manually checked examples,
boundary cases, counts by season, and validation evidence. The machine-readable report
is `data/processed/stage2_validation_report.json`.

| New file | Purpose |
| --- | --- |
| `sql/04_team_history.sql` | History summary, history as of each game, all-game flags, and revenge-game view. |
| `sql/05_stage2_validation.sql` | Nineteen checks and season counts for Stage 2. |
| `sql/06_stage2_inspect.sql` | Read-only samples and independent appearance ledgers for the manual examples. |
| `scripts/build_stage2.py` | Runs Stage 2 SQL in a transaction, checks both stages, and writes a report. |
| `tests/test_stage2.py` | Threshold, same-day exclusion, identity, return-stint, and future-removal tests. |
| `docs/stage2_results.md` | Reviewed examples, scope limits, and checkpoint results. |
| `data/processed/stage2_validation_report.json` | Latest successful Stage 2 checks and counts. |

Stage 2 uses views (saved queries), so a Stage 1 reload automatically flows through
them. Run the Stage 2 builder afterward to refresh its validation report. The existing
Stage 1 scripts, SQL, and dependency requirements are unchanged.

To rerun and verify the entire implemented project:

```bash
python scripts/load_data.py --offline --verify-rerun
python scripts/build_stage2.py
python scripts/query.py sql/06_stage2_inspect.sql
python -m unittest discover -s tests -v
```

`--verify-rerun` compares Stage 1 against its saved successful report; omit that flag
for the very first ingestion on a new machine. Stop here for review before Stage 3.

## Stage 1: setup and ingestion

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

During Stage 1, `git init` was blocked while trying to create `.git`. You subsequently
initialized Git and saved Stage 1 in commit `b6a1f4a` (`Complete stage 1 data ingestion`).
Stage 2 makes no commits or publishing changes. `.gitignore` excludes the virtual
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
For former-team logic, continue to `sql/04_team_history.sql`; pause before Stage 3.
