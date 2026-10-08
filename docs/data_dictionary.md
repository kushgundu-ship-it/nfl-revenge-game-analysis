# Stages 1 and 2 data dictionary

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

## Stage 2 views

All history uses Stage 1's regular-season QB/RB/WR/TE records for 2015–2025 and
canonical franchise codes. Names are not keys. Dates, not week numbers or text game
IDs, determine which games are earlier.

| View | One row represents | Key |
| --- | --- | --- |
| `player_team_history` | A player's observed relationship with a team over the full dataset. | `player_id, team` |
| `player_team_history_asof` | A team's accumulated history for a player before a particular game. Only positive counts are stored. | `player_id, game_id, history_team` |
| `player_game_revenge_flags` | Every cleaned player-game, including non-revenge records. | `player_id, game_id` |
| `fact_revenge_games` | A qualifying revenge-game performance (a filtered view of the flags). | `player_id, game_id` |
| `stage2_validation_checks` | One check with severity and problem count. | `check_name` |
| `stage2_season_counts` | All player-games, revenge games, and first meetings per season. | `season` |

The full-window summary has `first_observed_game_date`, `last_observed_game_date`,
`observed_games`, `observed_seasons` (a count), and `seasons` (a sorted list).
These fields describe the entire snapshot; they are **not safe historical features**
and are deliberately not used to classify past games.

The as-of view has current `game_date`, `history_team`, `prior_appearances`,
`first_prior_game_date`, and `last_prior_game_date`. Only matching player IDs with
strictly earlier dates contribute. If a team is absent at a given game, its prior
count is zero. This avoids including a team merely because the player joins it later.
The view includes earlier service for the current team as well as other teams;
only the current opponent is consulted for revenge identification.

The all-game flags and revenge view retain every cleaned Stage 1 field and add:

| Field | Meaning |
| --- | --- |
| `prior_opponent_appearances` | Earlier recorded games **for** the current opponent, not earlier games against it. |
| `first_prior_opponent_game_date` | First such earlier appearance in the observed data, or NULL if none. |
| `last_prior_opponent_game_date` | Most recent such earlier appearance, or NULL if none. It is not a transaction/departure date. |
| `is_revenge_game` | True if `prior_opponent_appearances >= 4`. |
| `prior_qualifying_meetings` | Earlier qualifying revenge games **against** this opponent franchise. |
| `is_first_meeting_with_former_team` | True only for a revenge game with zero earlier qualifying meetings. |

The first-meeting flag is per player/former franchise, not per departure or current
team. It does not reset after another stint. A meeting with only three earlier
appearances does not qualify and does not consume the first-qualifying-meeting flag.
No pre-2015 or postseason history is inferred. Counts are recorded appearances,
not roster memberships, calendar weeks, or guaranteed complete career game counts.

`fact_revenge_games` is currently an identification dataset. It does not yet contain
expected points, eight-game averages, standardized scores, or revenge uplift.
