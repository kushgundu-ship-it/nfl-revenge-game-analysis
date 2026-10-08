# Stage 4 results — October 8, 2026

**Primary effect: +0.067 PPR points**, revenge minus non-revenge, averaging one
within-player mean difference per player. **95% confidence interval: −0.443 to
+0.604 PPR. Two-sided player sign-flip p-value: 0.8124. Practical effect size:
less than one tenth of a PPR point per game at the point estimate.**

**Conclusion: No statistically distinguishable effect** on mean performance
residuals. These players did not show a reliably higher or lower mean residual
against former teams. The interval permits modest effects in either direction;
failure to reject zero does not prove that the effect is exactly zero. This is
an observational association, not an estimate of revenge causing a change.

Statistical significance concerns compatibility with a specified null model.
Practical importance concerns the size of the football effect. A small p-value
would not make a tiny PPR difference useful. Here the primary estimate is small
and its interval contains zero. For scale only, the entire primary interval is
inside ±1 PPR; that is an illustrative benchmark, not a validated threshold or
a prespecified equivalence test. No formal equivalence claim is made.

## Primary comparison and uncertainty

The unchanged Stage 3 cohort contains **875 revenge games and 23,434 non-revenge
games from 359 players**. Every player has both types of eligible observations;
none was excluded by the Stage 4 paired-player requirement. There are 167 players
with only one revenge game; the median is two, maximum twelve. Player estimates
and both group counts are in [stage4_player_comparisons.csv](../reports/tables/stage4_player_comparisons.csv).

The primary estimand was chosen as the equal-player mean difference before
examining Stage 4 inference results. For each player, SQL computes mean revenge
residual minus mean non-revenge residual, then averages those 359 differences.
The pooled estimand instead weights games equally within each group, so players
receive different weights in the two groups. Those are different questions and
can have different signs without a contradiction.

| Weighting and outcome | Revenge-minus-non-revenge estimate | 95% player-cluster bootstrap CI | Two-sided p-value |
| --- | ---: | ---: | ---: |
| Equal-player mean residual — primary | +0.067 PPR | [−0.443, +0.604] | 0.8124 |
| Game-weighted mean residual | −0.021 PPR | [−0.406, +0.381] | Not tested |
| Game-weighted median residual | +0.188 PPR | [−0.169, +0.475] | Not tested |
| Game-weighted percentage exceeding baseline | −0.093 percentage points | [−3.166, +3.128] | Not tested |
| Mean of within-player median differences — secondary | +0.664 PPR | [+0.150, +1.219] | Not tested |
| Mean of within-player exceeded-percentage differences | +1.566 percentage points | [−2.504, +5.687] | Not tested |

The positive secondary median contrast is visible and must not be confused with
the primary mean result. It averages each player's group medians; it is neither
the pooled median difference nor the median of the player mean differences.
With one revenge game for 167 players, many revenge medians equal a single game,
whereas their non-revenge medians summarize longer, skewed distributions. Unequal
sample sizes can bias these empirical median contrasts. The secondary interval
is pointwise, unadjusted for examining several outcomes, and supports no definitive
subgroup or primary mean discovery.

For reference, the original group mean residuals are −0.177 PPR (revenge) and
−0.156 (non-revenge); medians are −0.738 and −0.925. Exceeded percentages are
40.686% and 40.778%. These reproduce Stage 3. All inference values, counts,
seeds, and units are in [stage4_inference.csv](../reports/tables/stage4_inference.csv).

## Resampling, test assumptions, and reproducibility

The bootstrap samples **359 whole players with replacement, 5,000 times**, using
Python `random.Random(20261008)`. Every selected player's revenge and non-revenge
games travel together; repeated selections retain all games again. Pooled
statistics are recomputed with their resampled group denominators, and medians
are recomputed from all resampled game values. Equal-player statistics average
the sampled player contrasts. The 95% intervals are percentile intervals with
linear interpolation at 0.025 and 0.975. This accounts for repeated games and
overlapping baselines within a player rather than treating games as independent.
Whole-cluster sampling follows the cases-bootstrap construction described by
[Loy and Korobova](https://journal.r-project.org/articles/RJ-2023-015/).

The primary two-sided test independently flips each player's entire mean
difference to its negative or leaves it unchanged. Its statistic is the absolute
mean difference. There are **5,000 sign-flip draws with seed 20261009**;
`p = (1 + draws at least as extreme as observed) / 5001`. This includes the
observed arrangement and prevents reporting a zero Monte Carlo p-value. Its
Monte Carlo standard error near this result is approximately 0.006. The p-value
belongs to the equal-player mean; it is not a test of the pooled mean or medians.

The sign-flip null assumes independent player contrasts whose signs are jointly
invariant to reversal around zero. A zero population mean alone does not ensure
this symmetry. The observed groups were not randomized, so the test is conditional
on a symmetry model, not an exact randomized experiment. Skewed player contrasts,
different roles, or systematic timing may undermine that model. Whole-player
bootstrap intervals provide a complementary assessment without imposing null
sign symmetry; they still assume players are independent and reasonably
representative clusters, with sufficient moments and a useful empirical
approximation to the sampling distribution.

Players can share teams, opponents, and NFL games; clustering only by player does
not model those cross-player dependencies. The analysis conditions on the observed
cohort and past-only residual definitions. It does not simulate new schedules,
reclassify former teams, or refit histories within each resample. The dataset is
not a random sample of all NFL careers. There is no causal identification or
adjustment for injury, age, role, team strength, opponent defense, season, or
transfer selection. Venue and usage summaries below are descriptive, not controls.
These limitations qualify all inference, including intervals that exclude zero.

## Usage and efficiency

All definitions are shared across revenge and non-revenge games. Windows follow
stable player IDs over `ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING`, across seasons,
teams, and missed weeks. SQL calculates features before cohort or group filtering.
At least four prior appearances are required, as in Stage 3.

QB opportunities are pass attempts + carries. RB/WR/TE opportunities are carries
+ targets. Receptions are retained separately and never added to opportunities.
Usage baselines require every count in the window to be known. The current
snapshot has complete usage values in these windows.

The following values are opportunities per game. Actual and expected means use
the same observations, and Δ residual is revenge residual minus normal residual.

| Position | Revenge / normal n | Revenge actual | Revenge expected | Normal actual | Normal expected | Δ usage residual |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QB | 113 / 2,769 | 27.885 | 27.886 | 32.486 | 33.055 | +0.567 |
| RB | 224 / 5,541 | 9.018 | 8.916 | 10.504 | 10.673 | +0.271 |
| WR | 366 / 10,433 | 3.579 | 3.848 | 4.988 | 5.058 | −0.199 |
| TE | 172 / 4,691 | 3.058 | 2.915 | 3.384 | 3.418 | +0.177 |

QB usage differences mostly reflect +0.547 pass attempts and +0.019 carries in
residual terms. RB differences reflect +0.251 carries and +0.019 targets. WR
differences reflect −0.189 targets and −0.010 carries. TE differences reflect
+0.168 targets and +0.009 carries. Reception-residual differences are −0.009 QB,
+0.043 RB, −0.154 WR, and +0.080 TE receptions per game.

Efficiency actuals require positive denominators and known numerators. Their
expected values are the **mean of valid game-level ratios** inside those same
eight appearances, with **at least four valid prior ratios**. Undefined games
consume a window position and are not backfilled with older games. This is not
a ratio of summed yards to summed workload; low-volume and high-volume games
receive equal baseline weight. Undefined actuals/expectations/residuals remain NULL.

| Position / efficiency metric | Valid revenge / normal residual n | Revenge mean residual | Normal mean residual | Δ residual |
| --- | ---: | ---: | ---: | ---: |
| QB passing yards/attempt | 102 / 2,631 | −0.616 | −0.036 | −0.580 |
| QB rushing yards/carry | 92 / 2,332 | +0.085 | −0.032 | +0.117 |
| RB rushing yards/carry | 175 / 4,491 | +0.030 | −0.094 | +0.124 |
| RB receiving yards/target | 132 / 3,787 | +0.173 | −0.153 | +0.326 |
| WR receiving yards/target | 305 / 9,103 | +0.277 | −0.132 | +0.410 |
| TE receiving yards/target | 146 / 4,170 | −0.159 | −0.093 | −0.066 |
| WR rushing yards/carry | 6 / 460 | +1.477 | −0.698 | +2.176 |
| TE rushing yards/carry | 0 / 5 | Undefined | −2.750 | Undefined |
| QB touchdowns/opportunity | 112 / 2,736 | −0.00679 | −0.00071 | −0.00607 |
| RB touchdowns/opportunity | 189 / 4,952 | +0.00555 | −0.00045 | +0.00600 |
| WR touchdowns/opportunity | 309 / 9,239 | −0.00674 | −0.00185 | −0.00489 |
| TE touchdowns/opportunity | 146 / 4,179 | −0.00225 | −0.00008 | −0.00217 |

TD numerators match opportunities: passing + rushing TD for QB; rushing + receiving
TD for other positions. Rare receiving by QBs and passing by non-QBs do not enter
that measure, but remain in source PPR. A −0.00607 TD/opportunity difference is
−0.607 TD per 100 opportunities, not −0.607 TD per game.

These descriptive results show no uniform usage or efficiency pattern: QBs have
slightly higher relative usage but lower passing-efficiency residuals; WRs have
lower relative usage and higher receiving-yard efficiency but lower TD efficiency.
RBs have positive differences on the displayed usage and efficiency measures.
This does not establish mediation, causation, or a reliable position-specific
effect. Metric availability selects different games and sometimes players across
groups; WR rushing has only six revenge observations and TE rushing has none.
There are no hypothesis tests or significance claims for these exploratory tables.

[stage4_usage_efficiency.csv](../reports/tables/stage4_usage_efficiency.csv) includes
all actual/expected/residual means, eligible n, defined-actual n, available-baseline
n, valid-residual n, distinct-player n, and unavailable counts. For example, QB
passing efficiency has 104 defined revenge actuals and 109 available baselines,
but only 102 games with both. Counts of missing actual and missing baseline can
overlap. [stage4_usage_efficiency_differences.csv](../reports/tables/stage4_usage_efficiency_differences.csv)
contains all position/metric differences without rounding.

## Exploratory segments

These are game-weighted descriptions with no subgroup tests or multiplicity-adjusted
intervals. They should not be promoted to discoveries. Current position defines
the position segment. Home/away is schedule designation, including neutral venues.

| Segment | Revenge / normal n | Revenge mean residual | Normal mean residual | Difference |
| --- | ---: | ---: | ---: | ---: |
| QB | 113 / 2,769 | −1.225 | −0.250 | −0.975 |
| RB | 224 / 5,541 | +0.497 | −0.190 | +0.687 |
| WR | 366 / 10,433 | −0.405 | −0.155 | −0.250 |
| TE | 172 / 4,691 | +0.119 | −0.063 | +0.182 |
| Home | 429 / 11,697 | +0.114 | +0.002 | +0.111 |
| Away | 446 / 11,737 | −0.457 | −0.314 | −0.143 |

First/later meetings and departure buckets have no natural non-revenge analogue,
so the following table describes revenge games only. Player composition differs;
these are not paired comparisons with a matched normal-game set.

| Revenge segment | Games | Players | Mean residual | Median residual | Exceeded |
| --- | ---: | ---: | ---: | ---: | ---: |
| First qualifying meeting | 545 | 359 | −0.185 | −0.605 | 41.47% |
| Later qualifying meeting | 330 | 158 | −0.164 | −0.931 | 39.39% |
| 0–365 days since last former-team appearance | 335 | 239 | +0.108 | −0.425 | 43.28% |
| 366–730 days | 217 | 166 | −0.504 | −1.313 | 36.41% |
| 731–1,460 days | 243 | 154 | +0.032 | −0.763 | 42.39% |
| 1,461+ days | 80 | 58 | −1.122 | −1.956 | 36.25% |

The buckets are fixed day ranges approximating up to one year, one–two years,
two–four years, and over four years. They were not selected by searching for a
significant cutoff. Overall elapsed time averages **759.6 days**, median **662**,
range **7–2,905**. It is measured from the most recent earlier recorded appearance
for the former franchise, including a return stint; actual roster departure dates
are unavailable. First means first qualifying meeting in the observed 2015–2025
history and does not reset after a return to that team. Players can appear in
multiple segments. Continuous days and supporting dates for each game are in
[stage4_departure_games.csv](../reports/tables/stage4_departure_games.csv); all
segment statistics are in [stage4_segments.csv](../reports/tables/stage4_segments.csv).

## Outlier sensitivity

SQL computes a single 1st/99th-percentile pair across both groups:
**−14.0332 and +19.6740 PPR residual**. Trimming retains values on the boundaries
and excludes only those below/above them. Winsorization clips to the boundaries.
Neither transformation updates or deletes source data. Both preserve the original
residual in the analysis view. Sensitivity results are descriptive; the primary
confidence intervals above refer to the raw-data estimands.

| Variant | Revenge / normal n | Pooled mean difference | Pooled median difference | Equal-player mean difference | Paired players |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw | 875 / 23,434 | −0.021 | +0.188 | +0.067 | 359 |
| Trimmed at pooled 1st/99th percentiles | 859 / 22,962 | +0.035 | +0.213 | −0.020 | 353 |
| Winsorized at same percentiles | 875 / 23,434 | −0.011 | +0.188 | +0.049 | 359 |

Removing 16 revenge and 472 comparison performances changes the pooled mean's
sign but only by 0.056 PPR. All mean estimates remain close to zero. Thus the
descriptive near-zero mean pattern is not driven by a few extreme games.
Trimming removes all revenge observations for six players; the equal-player
trimmed estimate uses only the 353 players with both surviving groups. The pooled
trimmed estimate includes every surviving game, so it has a slightly different
player population. Outcome-based trimming changes the estimand and is not a
replacement for the primary analysis. Winsorization keeps all 359 players.

Examples for inspection:

| Player | Game | Actual PPR | Expected PPR | Revenge residual |
| --- | --- | ---: | ---: | ---: |
| Jerry Jeudy | 2024_13_CLE_DEN | 40.500 | 11.375 | +29.125 |
| DeSean Jackson | 2019_01_WAS_PHI | 35.400 | 9.238 | +26.162 |
| Rico Dowdle | 2025_06_DAL_CAR | 33.900 | 11.000 | +22.900 |
| Jameis Winston | 2020_09_NO_TB | 0.180 | 20.148 | −19.968 |
| Deshaun Watson | 2022_13_CLE_HOU | 5.340 | 23.822 | −18.482 |
| Jameis Winston | 2023_04_TB_NO | −2.000 | 14.235 | −16.235 |

Large residuals can reflect a changed role or a minimal appearance relative to
past starts, not motivation. The largest ten positive and negative games, with
stable IDs, dates, teams, and ranks, are in
[stage4_extreme_revenge.csv](../reports/tables/stage4_extreme_revenge.csv).
The cutoff, group, and contrast CSVs are `stage4_outlier_cutoffs.csv`,
`stage4_sensitivity_groups.csv`, and `stage4_sensitivity_results.csv`.

## Validation and preserved pipelines

Executed successfully with Python 3.9.6 and pinned DuckDB 1.4.4:

```bash
python scripts/analyze_stage4.py
python -m unittest discover -s tests -v
```

All **84 SQL error checks passed**: 20 Stage 1, 19 Stage 2, 24 Stage 3, and 21
Stage 4. All **26 automated tests passed**, including the original 12 and 14 new
Stage 4 tests. The original warnings persist unchanged: 236 raw `Team` rows lack
player IDs, and two raw rows have missing opponents/team-match warnings. Neither
warning enters the cleaned analysis. No new validation failures remain.

The checks establish:

- Every existing Stage 1–3 table and view has identical before/after row counts,
  hash sums, and XOR fingerprints, including validated summaries. Stage 3's saved
  summary independently agrees to 1e-9. Raw-file SHA-256 hashes, earlier SQL/scripts,
  original tests, requirements, project brief, and all three saved validation
  reports remain unchanged. The full hashes are in the Stage 4 validation JSON.
- Independent strict-date reconstruction agrees with every usage and efficiency
  window, count, and mean. Every window has at most eight earlier appearances.
  Synthetic current/future mutations and future removal leave earlier baselines
  unchanged; zero/three/four-prior boundaries and missing history are tested.
- Both groups use the same features. Opportunity formulas are checked for every
  position, with receptions separate. Ratio tests cover zero, negative, and NULL
  denominators; undefined prior ratios never backfill from an older ninth game.
- Every primary player comparison includes both groups. An explicit fixture
  with no normal observations is excluded. Resampling retains duplicated clusters
  and demonstrates the distinction between game and player weighting.
- A second complete 5,000-draw analysis reproduces **byte-identical inference and
  bootstrap CSV hashes** using the documented seeds. Changing the seed changes
  draws. Symmetric no-mean-effect synthetic data produces intervals centered near
  zero (estimate 0, 95% CI [−0.4, +0.4], sign-flip p=1). Adding a known +3 PPR
  effect shifts both mean estimators' draws by exactly +3: estimate +3, 95% CI
  [+2.6, +3.4], sign-flip p=0.0002. These are synthetic validation results only.
- Trimming and winsorization use the documented common percentiles and leave
  every source and Stage 3 feature row unchanged. Winsorization retains all rows.
  Synthetic mutations occur only in memory; no source records were removed.

All checks are exported in [stage4_validation.csv](../reports/tables/stage4_validation.csv).
The builder uses a transaction and rolls back failed SQL/preservation checks.
No Stage 1–3 pipeline file was edited and no additional Python package was required.

History limitations remain: no pre-2015 careers, postseason, other-position
appearances, or roster-only/snap-only records are inferred. Calendar dates in
January 2026 that belong to the **2025 season** remain eligible; the incomplete
2026 season is excluded. SQL views update if upstream data changes, while CSVs
and this report are snapshot outputs and must be regenerated and reviewed.

Stage 4 is ready for review. No dashboard has been built.
