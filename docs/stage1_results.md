# Stage 1 checkpoint — October 7, 2026

The database is `data/processed/nfl.duckdb`. All 20 error checks passed, with two
raw-data warning categories described below. A second ingestion completed with
`--offline --verify-rerun`: source hashes, row counts, and both data checksums per
table/view were identical. `python -m pip check` also passed.

| Season | Raw player rows | Clean QB/RB/WR/TE rows | All schedule games | Regular games |
| --- | ---: | ---: | ---: | ---: |
| 2015 | 17,613 | 5,423 | 267 | 256 |
| 2016 | 17,552 | 5,413 | 267 | 256 |
| 2017 | 17,477 | 5,448 | 267 | 256 |
| 2018 | 17,414 | 5,363 | 267 | 256 |
| 2019 | 17,362 | 5,411 | 267 | 256 |
| 2020 | 17,602 | 5,543 | 269 | 256 |
| 2021 | 18,969 | 5,866 | 285 | 272 |
| 2022 | 18,831 | 5,808 | 284 | 271 |
| 2023 | 18,643 | 5,801 | 285 | 272 |
| 2024 | 18,983 | 5,864 | 285 | 272 |
| 2025 | 19,422 | 6,037 | 285 | 272 |
| **Total** | **199,868** | **61,977** | **3,028** | **2,895** |

Every raw and cleaned row joins a schedule game by `game_id` (100% coverage).
Every regular-season schedule game has cleaned player rows. No raw or cleaned
player-game duplicate groups were found. Clean IDs, teams, PPR values, and schedule
metadata passed their checks. All expected seasons are present; 2026 is excluded.

## Real data sample

These are the first five alphabetically ordered quarterbacks in 2025 week 1,
not a ranking and not a revenge-game selection. PPR is rounded to two decimals.

| Player ID | Player | Team | Opponent | Game ID | PPR |
| --- | --- | --- | --- | --- | ---: |
| 00-0023459 | Aaron Rodgers | PIT | NYJ | 2025_01_PIT_NYJ | 25.66 |
| 00-0034855 | Baker Mayfield | TB | ATL | 2025_01_TB_ATL | 22.58 |
| 00-0039732 | Bo Nix | DEN | TEN | 2025_01_TEN_DEN | 6.84 |
| 00-0037834 | Brock Purdy | SF | SEA | 2025_01_SF_SEA | 16.78 |
| 00-0039150 | Bryce Young | CAR | JAX | 2025_01_CAR_JAX | 8.16 |

## Warnings and unfinished setup items

- **236 raw missing player IDs:** all source `player_name='Team'`, with no position.
  They remain in raw data and are outside the requested four-position filter.
- **Two raw missing opponents:** Team rows for CLE in `2016_10_CLE_BAL` and ARI in
  `2018_07_DEN_ARI`. They match game IDs but cannot pass a team/opponent comparison.
  These do not enter the cleaned view. Player rows within scope pass that comparison.
- **2022 has 271 regular games:** expected because BUF–CIN was canceled; see the
  [NFL announcement](https://www.buffalobills.com/news/nfl-says-neutral-site-afc-championship-game-is-possible-bills-bengals-week-17-ga).
- **Git initialization remains:** `git init` was attempted and blocked by filesystem
  permissions creating `.git`. Run the README's `git init` command in your Terminal.
  No commits or publishing occurred.
- **Live Python downloading remains unverified:** Python HTTPS and pip network access
  failed with DNS errors in this assistant environment. Real data and the official
  wheel were downloaded via permitted curl commands; DuckDB was installed locally.
  The Python loader's cached-file import and repeated-run paths were executed successfully.

The first strict validation attempt rolled back on the two raw Team records above.
After investigation, raw team comparison became a warning, with a separate blocking
comparison for the cleaned player records. That earlier attempt is preserved in
`data/processed/last_failed_run.json`; the current successful report is
`data/processed/validation_report.json`.

No revenge-game logic, player-team history, baselines, analysis, or dashboard was built.
