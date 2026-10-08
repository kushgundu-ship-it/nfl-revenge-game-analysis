# Stage 3 checkpoint — October 8, 2026

## Overall comparison

The shared feature view contains all **61,977** cleaned player-games. Of these,
**55,200** have at least four prior appearances and complete PPR values; **6,777**
have insufficient history and receive no residual or standardized score.

The comparison uses **875 revenge games** and **23,434 non-revenge games**, both from
the same **359 players**. Every Stage 2 revenge game has enough rolling history.
Remaining eligible rows from players without an eligible revenge game stay in
`player_game_features` but are not in the comparison cohort.

| Group | Games | Players | Exceeded baseline | Mean actual PPR | Mean expected PPR | Mean residual | Median residual |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Revenge | 875 | 359 | 40.69% | 6.681 | 6.858 | -0.177 | -0.738 |
| Non-revenge, same players | 23,434 | 359 | 40.78% | 8.581 | 8.737 | -0.156 | -0.925 |

The mean residual difference, revenge minus non-revenge, is **-0.021 PPR points**.
The percentage exceeding baseline differs by approximately **-0.09 percentage
points**. Both means are slightly below their rolling baselines. This describes
these games; it does not establish that facing a former team causes performance
to improve or decline. No statistical significance or absence of an effect is claimed.
For the exceeded percentage, residuals within 1e-9 PPR of zero are numerical ties.
Two otherwise tied normal games had positive floating-point roundoff at about 1e-15;
this tolerance keeps them out of the exceeded count without rounding any stored metric.

## Baseline and eligibility rules

SQL partitions by stable player ID, orders games by date, and takes the eight rows
immediately preceding the current appearance. The window is `ROWS BETWEEN 8 PRECEDING
AND 1 PRECEDING`. The current game and later games are excluded. A missing calendar
week adds nothing. Windows continue across seasons, transfers, and position changes
within the eligible data. Stage 2 checks prevent ambiguous multiple games for the
same player/date before Stage 3 is built.

With four to seven prior appearances, use all four to seven; with eight or more, use
the latest eight. `prior_game_count` is the size of this window, capped at eight.
It differs from Stage 2's earlier appearances for the opponent, which is uncapped.

For prior PPR values x and count n:

```text
expected_ppr_points = sum(x) / n
rolling_ppr_stddev = sqrt(sum((x - expected_ppr_points)^2) / (n - 1))
performance_residual = actual_ppr_points - expected_ppr_points
revenge_uplift = performance_residual
revenge_score = performance_residual / rolling_ppr_stddev
```

The standard deviation is the **sample** version (n - 1), not the population version
(n). Residuals and standardized scores are NULL for fewer than four prior appearances.
An early mean can be visible for inspection but does not enter an effect estimate.
Both groups read the same feature view; neither group gets its own baseline calculation.

The cohort contains players with an eligible revenge game anywhere in the observed
snapshot. Their eligible normal games both before and after that reunion are included.
This retrospective membership rule does not enter feature calculations. Removing
future data can change who belongs in the overall cohort, but cannot change the
baseline or label of an earlier player-game.

## Results by current position

| Position | Group | Games | Players | Exceeded | Mean actual | Mean expected | Mean residual | Median residual |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QB | Revenge | 113 | 44 | 41.59% | 10.524 | 11.749 | -1.225 | -1.845 |
| QB | Non-revenge | 2,769 | 44 | 46.91% | 14.406 | 14.656 | -0.250 | -0.485 |
| RB | Revenge | 224 | 91 | 39.29% | 7.264 | 6.767 | 0.497 | -0.725 |
| RB | Non-revenge | 5,541 | 91 | 39.20% | 8.516 | 8.706 | -0.190 | -0.988 |
| WR | Revenge | 366 | 146 | 38.25% | 5.947 | 6.353 | -0.405 | -1.306 |
| WR | Non-revenge | 10,433 | 146 | 40.31% | 8.331 | 8.486 | -0.155 | -1.025 |
| TE | Revenge | 172 | 78 | 47.09% | 4.959 | 4.840 | 0.119 | -0.131 |
| TE | Non-revenge | 4,691 | 78 | 40.06% | 5.772 | 5.835 | -0.063 | -0.788 |

Rows are equally weighted player-games. They are not equally weighted players.
Players with longer histories contribute more normal games. The current record's
position determines the segment; the baseline itself follows the player across teams.
These are descriptive segments, not separate causal tests.

## First versus later qualifying meetings

The Stage 2 flag is retained unchanged. "First" means first qualifying regular-season
meeting against that former franchise within the observed history, not necessarily
the first reunion in the player's career.

| Meeting | Games | Players | Exceeded | Mean actual | Mean expected | Mean residual | Median residual |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| First | 545 | 359 | 41.47% | 6.535 | 6.720 | -0.185 | -0.605 |
| Later | 330 | 158 | 39.39% | 6.923 | 7.087 | -0.164 | -0.931 |

The player sets overlap: players can have both first and later meetings.

## Four manually calculated real examples

I read each current record and retrieved its most recent eight earlier Stage 1 rows
by player ID and strictly earlier date, independently of the production rolling view.
I inspected their game IDs and PPR values, then computed the sum, mean, squared
deviations, sample standard deviation, residual, and score separately with decimal
arithmetic. An automated regression check also reproduces the arithmetic from these
explicit game IDs and value lists and compares it with the SQL to nine decimal places.
These are real records from the saved snapshot, not the synthetic boundary fixtures.

| Player | Revenge game | Prior n | Previous-eight mean | Actual PPR | Uplift | Sample SD | Standardized score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Tom Brady | TB at NE, 2021-10-03 | 8 | 25.8000 | 11.06 | -14.7400 | 5.1762 | -2.8476 |
| Matthew Stafford | LA vs DET, 2021-10-24 | 8 | 19.4275 | 27.16 | 7.7325 | 8.7415 | 0.8846 |
| Davante Adams | LV vs GB, 2023-10-09 | 8 | 18.4500 | 8.50 | -9.9500 | 13.4114 | -0.7419 |
| Adrian Peterson | WAS at NO, 2018-10-08 | 8 | 12.2000 | 6.20 | -6.0000 | 8.3228 | -0.7209 |

### Tom Brady — `00-0019596`, `2021_04_TB_NE`

Prior PPR, oldest to newest: **21.70, 15.64, 23.40, 29.92, 30.26, 27.16, 29.64, 28.68**.
These run from `2020_12_KC_TB` on 2020-11-29 through `2021_03_TB_LA` on 2021-09-26.
The sum is 206.40, so the mean is 206.40 / 8 = **25.80**. Squared deviations sum to
187.5512; sample SD is sqrt(187.5512 / 7) = **5.176198274**. Actual 11.06 minus 25.80
gives **-14.74**; divide by SD for **-2.847649804**. This window crosses an offseason
and excludes postseason games, consistent with the cleaned input.

### Matthew Stafford — `00-0026498`, `2021_07_DET_LA`

Prior PPR: **0.68, 22.62, 24.34, 17.22, 29.52, 19.30, 16.50, 25.24**.
The first two are DET appearances (`2020_16_TB_DET`, `2020_17_MIN_DET`); the next six
are LA appearances in 2021 weeks 1–6. Their sum is **155.42**, mean **19.4275**,
and squared deviations total **534.89675**. Sample SD is sqrt(534.89675 / 7) =
**8.741499953**. Uplift is 27.16 - 19.4275 = **7.7325**, and score **0.884573591**.
This verifies the baseline does not reset at a team change or discard a low-scoring
record merely because it would change the baseline.

### Davante Adams — `00-0031381`, `2023_05_GB_LV`

Prior PPR: **6.80, 3.50, 34.30, 12.30, 12.60, 20.40, 42.20, 15.50**.
The window contains the last four 2022 LV appearances and the first four 2023 LV
appearances (`2022_15_NE_LV` through `2023_04_LV_LAC`). Sum **147.60** / 8 gives
**18.45**. Squared deviations total **1259.06**; sqrt(1259.06 / 7) = **13.411402398**.
Uplift is 8.50 - 18.45 = **-9.95** and score **-0.741906007**.

### Adrian Peterson — `00-0025394`, `2018_05_WAS_NO`

Prior PPR: **4.30, 16.70, 3.20, 4.90, 13.90, 22.60, 8.00, 24.00**.
The first five rows are ARI games in 2017 weeks 7, 9, 10, 11, and 12. The next three
are WAS games in 2018 weeks 1, 2, and 3. The sum is **97.60**, mean **12.20**, and
squared deviations total **484.88**. Sample SD is sqrt(484.88 / 7) = **8.322774263**.
Actual 6.20 produces uplift **-6.00** and score **-0.720913461**. The elapsed calendar
time does not change the eight-appearance rule.

All 32 supporting game IDs, dates, teams, and PPR values are printed by
`sql/10_stage3_inspect.sql`; the explicit regression records are in
`tests/test_stage3.py`. PPR display values have two decimals; SQL calculations retain
source precision and do not round intermediate averages or scores.

## Undefined standardized scores

| Group | Eligible rows | Scores available | Zero-SD scores unavailable |
| --- | ---: | ---: | ---: |
| Revenge | 875 | 861 | 14 |
| Non-revenge | 23,434 | 23,227 | 207 |

These 221 zero-variance rows remain in raw-residual summaries, including the percent
exceeded denominator. Their standardized score is NULL with reason
`zero_rolling_stddev`. None of the eligible analysis rows has missing SD. Earlier
features with zero/one prior value can have missing sample SD and are ineligible.
`rolling_stddev_status` separately records missing/zero/positive; the reason field
prioritizes insufficient history when multiple conditions apply. Synthetic tests
also check an all-missing prior window, without modifying real data.

## Validation and preservation

Executed successfully:

```bash
python scripts/load_data.py --offline --verify-rerun
python scripts/build_stage2.py
python scripts/build_stage3.py
python -m unittest discover -s tests -v
python scripts/query.py sql/10_stage3_inspect.sql
```

- All **20 Stage 1**, **19 Stage 2**, and **24 Stage 3** error checks passed.
- All **12 automated tests** passed: four existing Stage 2 tests and eight new
  Stage 3 tests. The new tests include synthetic 0/3/4-prior-game boundaries,
  sample-versus-population SD, the eight-row cap, gaps, season/team changes, same-name
  different-ID isolation, missing/zero SD, identical cohort rules, and ties.
- Mutating a synthetic current game's PPR and every future PPR left that game's
  expected value, prior count, and sample SD unchanged.
- Independent SQL reconstructs each baseline by joining strictly earlier dates and
  selecting the eight most recent appearances. Contributor sets, counts, means,
  and sample SDs match production. Numeric comparisons use a 1e-9 tolerance.
- A deliberate corrupted-contributor test confirms the checks detect current and
  future dates in a baseline, rather than only checking successful data.
- In memory-only real-data copies, deleting records on/after **2018-10-31** and
  **2022-11-01** left every earlier feature row unchanged. No database source records
  were deleted or modified.
- The Stage 1 rerun retained identical row counts and fingerprints. Stage 3 confirmed
  unchanged fingerprints for Stage 1's raw/clean data and all four Stage 2 history
  and identification views. Both earlier pipelines and their SQL remain unchanged.

The original two raw-data warning categories persist: 236 `Team` rows lack player
IDs and two lack opponents. They do not enter the cleaned data. No new data-quality
warning was found in Stage 3. The current machine-readable report is
`data/processed/stage3_validation_report.json`.

## Interpretation limits and stopping point

History begins in 2015 and includes only recorded regular-season QB/RB/WR/TE
appearances, not every rostered player, snap, or postseason game. An appearance with
little or no offensive production still counts. Changes in role, injury, age, team,
opponent strength, and opportunity are not controlled here. The same players appear
repeatedly, groups differ in size and timing, and the cohort is selected retrospectively.
Do not read the pooled difference as a causal estimate or independent observations
for a simple significance test.

Stage 3 preserves the Stage 2 `fact_revenge_games` view and creates separate
`analysis_revenge_games` and `analysis_comparison_games` views. No dashboard or
Stage 4 opportunity/efficiency analysis was built. Stop here for review.
