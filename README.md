# NFL revenge-game analysis — Stages 1–4

Stage 1 prepares a reproducible dataset for the question in [project.md](project.md).
Stage 2 identifies games against qualifying former teams using only earlier
appearances. Stage 3 adds rolling performance baselines and compares revenge games
with non-revenge games from the same players. There is no dashboard.

## Stage 4: inference, usage, efficiency, and sensitivity

The primary equal-player mean difference is **+0.067 PPR**, with a **95% player-clustered
bootstrap interval of −0.443 to +0.604** and a **two-sided player sign-flip p-value of
0.812**. Conclusion: **No statistically distinguishable effect** on mean residuals.
The point estimate is less than one tenth of a PPR point; statistical significance
and football importance are different questions. This does not prove an exact zero
effect or establish causality.

The pooled game-weighted difference is −0.021 PPR (95% CI −0.406 to +0.381).
Both estimates use the validated 875 revenge games and 23,434 non-revenge games
from 359 players. Trimming and winsorization leave mean differences close to zero.
Usage and efficiency findings vary by position and are descriptive. A positive
secondary average-of-player-medians contrast is discussed explicitly in the report;
it does not change the primary mean conclusion.

Run after the existing Stage 3 build:

```bash
source .venv/bin/activate
python scripts/analyze_stage4.py
python -m unittest discover -s tests -v
python scripts/query.py sql/14_stage4_inspect.sql
```

The script runs all stages' SQL checks, adds only `stage4_` views, and verifies
that every Stage 1–3 table/view, validated summary, raw file, earlier pipeline file,
and saved earlier validation report is unchanged. It uses 5,000 whole-player
bootstrap draws with seed `20261008` and 5,000 sign flips with seed `20261009`.
Python 3.9.6 and the existing pinned DuckDB 1.4.4 were used; **no new dependencies**.
The production CLI rejects fewer than 5,000 iterations. Explicit overrides are
`--iterations 10000 --seed 20261008`; the published report uses the defaults.

Read [docs/stage4_results.md](docs/stage4_results.md) for definitions, all primary
intervals, exploratory segments, usage and valid-ratio sample sizes, sensitivity,
test assumptions, and validation. [reports/tables/](reports/tables/) contains 12
CSV tables, including all bootstrap draws and one comparison per player.
`data/processed/stage4_validation_report.json` records fingerprints, code and CSV
hashes, seeds, versions, and checks; a failed build writes `stage4_failed_run.json`.
CSV blanks mean unavailable/NULL, not zero. Rerun Stage 4 after changing upstream
data; reports are snapshots and do not refresh just because a view changes.

| File | Purpose |
| --- | --- |
| `sql/11_stage4_features.sql` | Shared usage/efficiency windows, cohort, and player contrasts. |
| `sql/12_stage4_summaries.sql` | Descriptive segments, usage/efficiency comparisons, and outlier views. |
| `sql/13_stage4_validation.sql` | Independent historical-window audit and 21 checks. |
| `sql/14_stage4_inspect.sql` | Read-only inspection queries. |
| `scripts/analyze_stage4.py` | Transactional build, inference, CSV export, and preservation checks. |
| `tests/test_stage4.py` | Fourteen new tests, including a full 5,000-draw reproducibility check. |

Stages 1–3 SQL, scripts, tests, source records, and checkpoint reports are preserved.
Stage 4 is complete and stops for review; no dashboard has been built.

## Stage 3: rolling baselines and comparison

```bash
cd /Users/kushg/SQL_NFL_Project
source .venv/bin/activate
python scripts/build_stage3.py
python scripts/query.py sql/10_stage3_inspect.sql
```

`player_game_features` keeps all 61,977 cleaned player-games and all Stage 2 flags.
For each stable player ID, SQL orders appearances by game date and uses
`ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING`: up to eight records before the current
one. Byes and missed games do not add rows. The history continues across seasons,
team changes, and eligible positions; it does not reset at a transfer or January 1.

The expected PPR is the mean of those earlier values. The sample standard deviation
measures their spread using the `n - 1` denominator. With four or more prior records,
the performance residual (also called `revenge_uplift`) is actual minus expected PPR.
The standardized `revenge_score` divides that residual by the sample standard deviation.
No effect is calculated with fewer than four prior appearances. Preliminary means
for one to three prior appearances remain visible only for inspection.

A zero or missing standard deviation produces a NULL score, with an explicit reason.
An otherwise eligible zero-variance game still contributes to raw residual summaries.
Missing PPR is never filled with zero or silently replaced by an older ninth game;
incomplete windows are ineligible. Stage 1 checks enforce complete, finite source PPR.

Both analysis views read the same features and apply the same eligibility rule:

- `analysis_revenge_games`: 875 revenge performances by 359 players.
- `analysis_comparison_games`: 23,434 non-revenge performances from those same players.

This is a retrospective cohort: qualifying players' normal games before and after
their first revenge game are included. Knowing who belongs to this cohort does not
enter an earlier game's baseline or label. The comparison is weighted by player-game,
so players with more appearances contribute more rows; it is not a matched causal
estimate or an equal-weight average of player effects.

| Group | Games | Exceeded baseline | Mean actual | Mean expected | Mean residual | Median residual |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Revenge | 875 | 40.69% | 6.681 | 6.858 | -0.177 | -0.738 |
| Non-revenge, same players | 23,434 | 40.78% | 8.581 | 8.737 | -0.156 | -0.925 |

Both groups average slightly below their rolling baselines. The mean residual
difference (revenge minus non-revenge) is approximately -0.021 PPR. This describes
the snapshot and does not establish that facing a former team causes any change.
No significance test, opponent/usage adjustment, or uncertainty interval is claimed.
For the exceeded percentage, residuals within 1e-9 PPR of zero are numerical ties,
not wins; this avoids binary floating-point roundoff misclassifying tied games.

[docs/stage3_results.md](docs/stage3_results.md) contains the position and first/later
meeting summaries, four independently calculated real examples, and validation
details. `sql/10_stage3_inspect.sql` shows each example's eight supporting game IDs,
dates, teams, and PPR values so you can trace every calculation.

| New file | Purpose |
| --- | --- |
| `sql/07_player_game_features.sql` | Shared rolling features, baseline contributors, and analysis group views. |
| `sql/08_stage3_summaries.sql` | Overall, position, and first/later-meeting summaries. |
| `sql/09_stage3_validation.sql` | Independent strict-date baseline reconstruction and 24 data checks. |
| `sql/10_stage3_inspect.sql` | Read-only summaries, checks, and supporting histories for real examples. |
| `scripts/build_stage3.py` | Builds Stage 3, checks all stages, and verifies Stage 1/2 are unchanged. |
| `tests/test_stage3.py` | Eight tests covering boundaries, independent real arithmetic, and future-data removal. |
| `docs/stage3_results.md` | Human-readable comparison and worked calculations. |
| `data/processed/stage3_validation_report.json` | Current checks, summaries, coverage, and score availability. |

Stage 1/2 SQL and scripts are unchanged, including the Stage 2 `fact_revenge_games`
identification view. Stage 3 uses additional views rather than replacing it. Rerunning
earlier stages updates those views automatically; rerun Stage 3 afterward to refresh
its validation report. Failures roll back the build and write `stage3_failed_run.json`.

To rebuild and check all implemented stages (Stage 4 added after Stage 3):

```bash
cd /Users/kushg/SQL_NFL_Project
source .venv/bin/activate
python scripts/load_data.py --offline --verify-rerun
python scripts/build_stage2.py
python scripts/build_stage3.py
python scripts/analyze_stage4.py
python -m unittest discover -s tests -v
python scripts/query.py sql/10_stage3_inspect.sql
```

The first ingestion on a fresh machine should omit `--offline --verify-rerun` so it
can download data and establish a reference report. Tests use memory-only copies;
synthetic rows never enter the project database. The original Stage 3 review
checkpoint is preserved; the current stopping point is Stage 4 review above.

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

To rerun and verify Stages 1 and 2:

```bash
python scripts/load_data.py --offline --verify-rerun
python scripts/build_stage2.py
python scripts/query.py sql/06_stage2_inspect.sql
python -m unittest discover -s tests -v
```

`--verify-rerun` compares Stage 1 against its saved successful report; omit that flag
for the very first ingestion on a new machine. Stage 3 commands are above.

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
For former-team logic, continue to `sql/04_team_history.sql`, then read
`sql/07_player_game_features.sql` for rolling baselines.
