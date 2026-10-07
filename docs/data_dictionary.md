# Stage 1 data dictionary

`raw_player_weekly_stats` retains all source columns and rows from the 11 Parquet
files. `filename` and `source_file` add the local file path for traceability.
`raw_schedules` retains source columns for 2015–2025, as text, to avoid accidentally
changing identifier formatting. The original CSV on disk retains all seasons.

`clean_schedules` casts dates and numbers and normalizes franchise codes. It includes
postseason schedules so raw postseason statistics can also be validated.
`clean_player_game_stats` retains the player-stat columns and limits records to
regular-season QB/RB/WR/TE appearances. Its intended key is `(player_id, game_id)`;
validation checks uniqueness rather than silently removing duplicates.

| Main cleaned field | Meaning |
| --- | --- |
| `player_id` | Stable nflverse/GSIS player identifier, stored as text. |
| `player_display_name` | Human-readable name; never used as a join key. |
| `position` | Source position for this record; QB, RB, WR, or TE in the clean view. |
| `season`, `week` | NFL season and week, not calendar year. January games may belong to the prior season. |
| `season_type` | `REG` in the clean view; raw data also includes `POST`. |
| `game_id` | Source game identifier; join key to schedules, not rewritten after team normalization. |
| `team`, `opponent_team` | Canonical franchise abbreviations. |
| `source_team`, `source_opponent_team` | Original player-file team abbreviations. |
| `game_date` | Date obtained from the schedule's `gameday` field. |
| `schedule_game_type` | Schedule game type; expected to be `REG` for cleaned player rows. |
| `home_team`, `away_team` | Canonical schedule teams. |
| `home_score`, `away_score` | Final schedule scores. |
| `schedule_matched` | Whether the game ID was found in the schedule. |
| `fantasy_points_ppr` | Source PPR fantasy points (point per reception); not recomputed in this stage. |
| `attempts`, `completions`, `passing_yards`, `passing_tds` | Source passing statistics. |
| `carries`, `rushing_yards`, `rushing_tds` | Source rushing statistics. |
| `targets`, `receptions`, `receiving_yards`, `receiving_tds` | Source receiving statistics. |
| `source_file` | Local Parquet file from which the row came. |

Other source statistics remain accessible in the view. Consult the
[nflverse player dictionary](https://nflreadr.nflverse.com/articles/dictionary_player_stats.html)
for their definitions. Missing values are retained; zero and unknown mean different things.

`validation_checks` has one row per check (`check_name`, `severity`, `problem_count`).
Any nonzero `ERROR` count fails ingestion. Nonzero `WARN` counts are reported and
retained for review. `season_row_counts` summarizes raw and clean counts, schedule
counts, regular-season games, and the count of clean rows with matching schedules.
