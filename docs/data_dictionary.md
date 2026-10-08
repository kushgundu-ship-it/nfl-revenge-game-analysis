# Stages 1–4 data dictionary

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

`fact_revenge_games` remains the Stage 2 identification dataset. The Stage 3
`analysis_revenge_games` view adds performance features without changing Stage 2.

## Stage 3 views

| View | Purpose and grain |
| --- | --- |
| `player_game_appearance_order` | Every Stage 2 player-game plus a sequence number per stable player ID. |
| `player_game_features` | Every cleaned player-game with the shared baseline, eligibility, residual, and score. Key: `player_id, game_id`. |
| `player_game_baseline_support` | One row per current game and preceding contributor. Key: `player_id, game_id, prior_game_id`. |
| `analysis_revenge_games` | Eligible revenge-game rows from the common feature view. |
| `stage3_comparison_cohort` | Distinct player IDs with at least one eligible revenge game in the snapshot. |
| `analysis_comparison_games` | Eligible non-revenge rows for players in that cohort. |
| `stage3_analysis_games` | Both groups together, with `game_group` = `revenge` or `non_revenge`. |
| `stage3_summary` | One row per `breakdown, segment, game_group` for overall, position, or first/later meeting. |
| `stage3_baseline_audit` | Independent validation-only reconstruction using strictly earlier dates and most-recent ranks. |
| `stage3_validation_checks` | Twenty-four checks, each with severity and a problem count. |

All Stage 2 columns remain in the feature and analysis views, including names,
positions, teams, opponent/former franchise, dates, IDs, season/week, revenge and
first-meeting flags, and `prior_opponent_appearances`. These are distinct from the
rolling prior-game count: former-team tenure uses all earlier appearances for that
opponent, while performance uses the most recent eight appearances for any team.

| New feature field | Meaning |
| --- | --- |
| `appearance_number` | One-based chronological row number per player, across seasons and teams. |
| `actual_ppr_points` | Unchanged source `fantasy_points_ppr` for the current game. |
| `prior_game_count` | Number of preceding appearances in the rolling window: 0–8, not full-career prior games. |
| `prior_ppr_count` | Number of non-NULL PPR values in those same rows; must equal `prior_game_count` for analysis. |
| `expected_ppr_points` | Mean PPR from those preceding rows. NULL with no prior values; preliminary with fewer than four rows. |
| `rolling_ppr_stddev` | Sample standard deviation over the same preceding window, using denominator `n - 1`. NULL with fewer than two PPR values. |
| `baseline_first_game_date`, `baseline_last_game_date` | Earliest/latest contributor dates, or NULL for an empty window. |
| `is_effect_eligible` | At least four prior appearances, no missing prior PPR in that window, and nonmissing current PPR. Upstream validation additionally requires finite values. |
| `performance_residual` | Actual minus expected PPR if eligible, otherwise NULL. Neutral name used for both groups. |
| `revenge_uplift` | Exact alias of `performance_residual`, including on non-revenge rows for a symmetric comparison. |
| `revenge_score` | Eligible residual divided by a positive sample standard deviation; otherwise NULL. |
| `rolling_stddev_status` | `missing`, `zero`, or `positive`, independently of the minimum-history rule. |
| `revenge_score_unavailable_reason` | NULL for an available score; otherwise the first applicable reason listed below. |

Unavailable-reason priority is `insufficient_prior_appearances`, `missing_prior_ppr`,
`missing_actual_ppr`, `missing_rolling_stddev`, then `zero_rolling_stddev`. For example,
the first appearance has both insufficient history and missing standard deviation;
its reason is insufficient history and its separate standard-deviation status is missing.
An eligible zero-standard-deviation row retains a valid raw residual and stays in
the analysis, but never gets an infinite/NaN standardized score.

Baseline support fields include the current `game_id`/`game_date`, `prior_game_id`,
`prior_game_date`, `prior_season`, `prior_week`, `prior_team`, `prior_opponent_team`,
`prior_ppr_points`, and `appearances_back` (1 is the most recent, 8 the oldest).
The builder checks Stage 2's unique player/date condition before using row ordering.
The audit view checks that all contributors really have earlier dates.

Summary fields are `sample_size` (player-game rows), `player_count` (distinct IDs),
`pct_exceeded_baseline` (residuals greater than 1e-9 PPR, divided by all eligible rows,
times 100), `mean_actual_ppr`, `mean_expected_ppr`, `mean_residual`, `median_residual`,
and `standardized_score_count` (non-NULL scores). The 1e-9 tolerance treats numerical
roundoff around zero as ties. Ties are not exceeded performances.
Values remain unrounded in the database; only display queries round them.

`breakdown='overall'` uses segment `ALL`; `position` uses the current record's QB,
RB, WR, or TE; `meeting` uses `first`/`later` for revenge rows only. Players can
appear in both meeting segments, and position can change between records.
Summaries weight games equally rather than weighting each player equally.

Cohort selection is retrospective and may include non-revenge games before a
player's first eligible revenge game. Future cohort membership never enters an
individual baseline. This is a descriptive comparison, not a forecasting cohort
or a causal estimate. The 2015 history boundary and regular-season/position limits
from earlier stages also apply to every rolling window.

## Stage 4 views and exported tables

Every Stage 4 object is a view prefixed `stage4_`. No earlier view/table is replaced.
Data transformations, metric definitions, original estimates, percentiles, and
segments are SQL; Python only orchestrates, resamples, computes inferential
statistics, and serializes outputs.

| View | Grain / meaning |
| --- | --- |
| `stage4_game_context` | Every Stage 3 feature row with usage totals, venue, and elapsed former-team time. |
| `stage4_metric_actuals` | Nine metric rows per player-game, including undefined and position-inapplicable metrics. |
| `stage4_metric_features` | Same grain, with past-only baseline, coverage counts, and residual. |
| `stage4_paired_players` | Player IDs with eligible revenge and non-revenge observations; 359 here. |
| `stage4_analysis_games` | Eligible PPR rows for paired players; same 24,309 rows as Stage 3. |
| `stage4_analysis_metrics` | Applicable metrics for those games, including NULL ratios/baselines. |
| `stage4_player_comparisons` | One row per player, with each group's n, mean, median, exceeded percentage, and differences. |
| `stage4_segments` | One row per breakdown/segment/group, with n, players, PPR summaries, and elapsed-day summaries. |
| `stage4_usage_efficiency` | Current position/metric/group summaries and availability counts. |
| `stage4_usage_efficiency_differences` | Revenge-minus-non-revenge mean residual contrast per position/metric. |
| `stage4_outlier_cutoffs` | One common pooled 1st/99th-percentile pair for the full comparison cohort. |
| `stage4_sensitivity_games` | Player-games per raw/trimmed/winsorized variant; transformed `analysis_residual` is separate from original `performance_residual`. |
| `stage4_sensitivity_groups` | Group n, mean, and median by variant. |
| `stage4_sensitivity_results` | Pooled mean/median differences and equal-player mean differences by variant. |
| `stage4_extreme_revenge` | Largest ten positive and ten negative revenge residuals, with IDs, actual/expected PPR, and ranks. |
| `stage4_baseline_audit` | Independent date-bounded reconstruction for each player-game/metric. |
| `stage4_validation_checks` | Twenty-one Stage 4 checks with severity and problem count. |

### Context and metric definitions

`is_home` means the player's team is the schedule-designated home team. Neutral-site
games retain that designation. `days_since_former_team` is the date difference
from `last_prior_opponent_game_date` to the current game, only for revenge games.
It is **time since the most recent recorded appearance**, not the actual departure
date. It uses the most recent prior stint. `departure_bucket` is `01_0_to_365_days`,
`02_366_to_730_days`, `03_731_to_1460_days`, or `04_1461_plus_days`, with inclusive
integer-day endpoints. Non-revenge rows have NULL elapsed time and bucket.

| Metric | Actual value | Used in summaries for |
| --- | --- | --- |
| `pass_attempts` | Source `attempts` | QB |
| `carries` | Source `carries` | All four positions |
| `targets` | Source `targets` | RB, WR, TE |
| `receptions` | Source `receptions`, separate from opportunities | All four positions |
| `opportunities` | QB: attempts + carries; RB/WR/TE: carries + targets | All four positions |
| `passing_yards_per_attempt` | passing_yards / attempts | QB |
| `rushing_yards_per_carry` | rushing_yards / carries | All four positions |
| `receiving_yards_per_target` | receiving_yards / targets | RB, WR, TE |
| `touchdowns_per_opportunity` | `opportunity_tds` / `opportunities` | All four positions |

`opportunity_tds` is passing_tds + rushing_tds for QB and rushing_tds + receiving_tds
for RB/WR/TE. Rare QB receiving and non-QB passing plays are excluded from this
position-specific opportunity/TD measure; source PPR still contains its original
full scoring. Receptions are already a subset of targets and are never added again.
Null inputs propagate rather than becoming zero. Ratios are defined only for
strictly positive denominators and known numerators; NULL, zero, and negative
denominators produce NULL. Negative usage also fails validation.

`metric_family` is `usage` or `efficiency`; `denominator` is populated only for ratios.
`position_applicable` controls summaries, after calculating the windows over all
appearances. Historical opportunities use each historical row's own position;
windows follow stable IDs across position changes, teams, seasons, and gaps.

| Metric feature | Meaning |
| --- | --- |
| `actual` | Current count or ratio, or NULL when unknown/undefined. |
| `window_n` | Number of the previous eight appearances actually available, 0–8. |
| `valid_prior_n` | Non-NULL metric values among those appearances. |
| `window_first_date`, `window_last_date` | Earliest/latest appearance in that window, including undefined ratios. |
| `prior_mean` | Mean of valid historical values for inspection, including short windows. |
| `baseline_available` | At least four prior appearances and four valid values; usage additionally requires no missing historical value in the window. |
| `expected` | `prior_mean` only when baseline_available; otherwise NULL. |
| `residual` | actual − expected when both exist; otherwise NULL. |

Efficiency expected values are **means of valid game-level ratios**, not ratios of
summed yardage to summed attempts. Zero-denominator games still consume a place in
the previous-eight-appearance window; an older ninth game can never backfill them.
No residual enters analysis unless the game's Stage 3 PPR eligibility also holds.

### Summary fields and inference CSV

Usage/efficiency summaries retain `eligible_games`, `actual_n`, `expected_n`,
`residual_n`, and `residual_players`; undefined current values and unavailable
baselines have separate counts and can overlap. `mean_actual_all_valid` uses all
defined actual values. `mean_actual_paired` and `mean_expected_paired` use the same
rows as `mean_residual`, so their difference agrees with that mean residual.
Efficiency metrics can have different player/game subsets in the two groups.
These descriptive contrasts are not an adjusted causal decomposition of PPR.

Player comparison fields `revenge_n`, `non_revenge_n`, `revenge_mean`,
`non_revenge_mean`, and `mean_difference` define the primary within-player effect.
The equivalent median and percentage fields use each player's own group summaries.
Exceeded retains Stage 3's >1e-9 PPR tolerance, with ties in the denominator.

`reports/tables/stage4_inference.csv` contains six effects. `pooled_mean`,
`pooled_median`, and `pooled_pct` compare equally weighted games in each group.
`equal_player_mean`, `equal_player_median`, and `equal_player_pct` average the
corresponding **within-player differences**, weighting players equally. In
particular, `equal_player_median` is the mean of player median differences, not a
weighted pooled median and not the median of player effects.

`estimate`, `ci_low`, `ci_high` use PPR points except percentage effects, which use
percentage points. Bounds are linearly interpolated 2.5th/97.5th percentiles of
5,000 whole-player bootstrap estimates. Every draw samples 359 players with
replacement and retains every selected player's games with full multiplicity.
The bootstrap seed is 20261008. Only the primary `equal_player_mean` has a p-value:
a two-sided player sign-flip test with 5,000 draws, seed 20261009, and plus-one
Monte Carlo correction. Other p-value cells are empty and `test=not_tested`.
Player independence and null sign symmetry are assumptions, not established facts.

`stage4_bootstrap_draws.csv` has one row per iteration and six effect columns.
`stage4_validation.csv` has stage, check_name, severity, and problem_count.
Other CSVs mirror their named SQL views; `stage4_departure_games.csv` exports
individual revenge-game dates and elapsed time for auditing. All CSVs have headers,
stable row order, unrounded numeric results, and empty fields for NULL.
