# Stage 5 — local portfolio presentation

Implemented October 8, 2026. Presentation only: Stage 1–4 analytical definitions,
source files, database, report tables, and checkpoint reports are unchanged.
No deployment, publication, commit, or push was performed.

## The story shown in the dashboard

**Primary equal-player mean difference: +0.067 PPR.** The 95% player-clustered
bootstrap interval is **−0.443 to +0.604 PPR**; the two-sided player sign-flip
p-value is **0.8124**. **No statistically distinguishable mean revenge effect was
found.** These values are loaded from `stage4_inference.csv`, checked against the
successful Stage 4 snapshot, and formatted for display—not embedded as dashboard
analytical constants.

The cohort contains 359 players, 875 revenge performances, and 23,434 non-revenge
performances. The primary estimate gives each player's mean difference equal weight.
The pooled mean gives games equal weight within each group: −0.021 PPR, 95% CI
−0.406 to +0.381. The secondary mean of within-player median differences is
+0.664 PPR, 95% CI +0.150 to +1.219. It is exploratory, is not the pooled median,
and does not overturn the primary mean result.

Usage and efficiency are descriptive, not a causal decomposition. Saved opportunity
residual contrasts are QB +0.567, RB +0.271, WR −0.199, and TE +0.177 opportunities
per game. QB passing-efficiency contrast is −0.580 yards per attempt; WR receiving
efficiency is +0.410 yards per target. The dashboard shows paired actual/expected
values and valid sample sizes for every metric. TE rushing efficiency has no valid
revenge residuals and remains unavailable, never zero. WR rushing efficiency is
explicitly flagged for its small valid revenge sample.

| Sensitivity analysis | Equal-player mean Δ | Pooled mean Δ | Pooled median Δ |
| --- | ---: | ---: | ---: |
| Raw | +0.067 | −0.021 | +0.188 |
| Trimmed 1st/99th percentiles | −0.020 | +0.035 | +0.213 |
| Winsorized 1st/99th percentiles | +0.049 | −0.011 | +0.188 |

All units above are PPR. Sensitivity values are loaded from the existing table;
no new sensitivity tests or intervals are claimed. The common cutoffs are shown in
the app. Trimming changes the sample and leaves 353 paired players versus 359 in
the raw/winsorized analyses. Source records remain intact.

## Run and inspect

From the project folder, using the existing validated data:

```bash
source .venv/bin/activate
python -m pip install -r requirements-dashboard.txt
python -m streamlit run dashboard/app.py
```

Open <http://127.0.0.1:8501>. The app binds to loopback, not a public network
interface. Stop with Ctrl+C before rebuilding data. Restart after source edits
because file watching is disabled. The [README](../README.md) has fresh-machine
setup and ordered pipeline commands.

The four navigation sections are:

- **Overview:** sample sizes, primary estimate/CI/test, definitions, five distribution
  filters, and the distinction between equal-player, pooled, and median estimands.
- **Patterns:** position, first/later meeting, venue and time-since-former-team
  summaries; five usage and four efficiency metrics; outlier sensitivity and extremes.
- **Player explorer:** all 359 readable player choices, backed by stable IDs;
  revenge-game ledger, game selection, actual/expected PPR, uplift, standardized
  score, former team, first/later status, and exact historical baseline contributors.
- **Methods & limits:** the data-flow diagram, historical rules, inference assumptions,
  limitations, saved validation warnings, source links, and report download.

Bookmarked examples span both directions: Brady's 2021 return to NE (−14.740 PPR
residual), Stafford's 2021 meeting with DET (+7.732), Adams versus GB in 2023
(−9.950), and Jeudy versus DEN in 2024 (+29.125). Only their stable IDs and game IDs
are bookmarks; every displayed statistic comes from the database. These examples
illustrate variation, not a replacement for the aggregate finding.

## Validation results

Commands run against the existing snapshot, without rebuilding it:

```bash
python scripts/validate_stage5.py
python -m unittest discover -s tests -v
python -m pip check
git diff --check
```

| Check | Result |
| --- | --- |
| Stage 1 live SQL error checks | 20/20 passed |
| Stage 2 live SQL error checks | 19/19 passed |
| Stage 3 live SQL error checks | 24/24 passed |
| Stage 4 live SQL error checks | 21/21 passed |
| Stage 5 dashboard contracts | 7/7 passed |
| Existing automated tests | 26/26 passed |
| New dashboard tests | 11/11 passed |
| Total automated tests | 37/37 passed, no skips |
| Dependency compatibility | `pip check`: no broken requirements |
| Whitespace/diff check | Passed |
| Preservation | All 60 protected files match pre-Stage-5 SHA-256 hashes |

The two unchanged Stage 1 warnings are 236 raw rows missing player IDs and two
raw schedule/team mismatch-or-missing rows. They are documented exclusions, not
new Stage 5 failures. Streamlit's test harness emits an expected bare-mode
`ScriptRunContext` warning; the tests report no application exceptions.

New tests cover all required Stage 4 files and CSV hashes; live query counts;
headline agreement with the saved JSON report; a changed-input check proving the
headline is not hardcoded; unique stable IDs and parameterized player queries;
all chart specifications; expected NULL versus invalid nonfinite data; every
filter; every bookmarked player and each of their revenge-game baselines; a real
unavailable-score case; and the missing-input recovery message.

`reports/stage5_validation.json` contains machine-readable checks and hashes.
The local, Git-ignored `data/processed/stage5_preservation_baseline.json` was recorded
before presentation edits. The validator also hashes before and after its read-only
run. It never rewrites upstream data to make a check pass. On another machine,
record a baseline once after Stage 4; a check with no baseline cannot prove
preservation from before the presentation work.

## Browser and visual verification

Chrome was used at **1366 × 900** and **1280 × 800** laptop viewports. All four
sections, four subgroup choices, five distribution choices, nine usage/efficiency
metrics, sensitivity and extreme-game tables, definition expanders, player-name
search, four example buttons, and a later Stafford baseline were exercised.
The Stage 4 report download was verified. Automated interaction tests additionally
exercise every revenge-game baseline for the four example players and missing-input
and unavailable-score states.

Visual review corrected the histogram's inferred bar orientation, removed an unused
non-revenge legend in revenge-only segments, shortened a diagram label, removed a
duplicate sensitivity legend, and narrowed the sensitivity table to avoid clipped
columns. A browser-only Streamlit named-dataset update error was fixed by sending
small chart datasets inline in self-contained Vega-Lite specifications. Automated
tests now check this serialization and the explicit histogram orientation. Final
navigation/filter checks showed no new browser errors; no document-level horizontal
overflow was present at 1280 pixels. The pinned frontend can log a Vega-Lite schema
version warning, but all chart types render correctly in the verified browser.

Screenshots document the actual local build:

- [Headline at 1280 × 800](screenshots/stage5_overview.jpg)
- [Residual distributions](screenshots/stage5_distribution.jpg)
- [Usage comparison](screenshots/stage5_usage.jpg)
- [Sensitivity comparison](screenshots/stage5_sensitivity.jpg)
- [Eight-appearance player baseline](screenshots/stage5_player_baseline.jpg)
- [Methods and data flow](screenshots/stage5_methods.jpg)

## New files, in plain English

| File | Purpose |
| --- | --- |
| `dashboard/__init__.py` | Makes the dashboard helpers importable as a Python package. |
| `dashboard/app.py` | The four Streamlit sections, controls, explanatory text, and drill-downs. |
| `dashboard/data.py` | Opens DuckDB read-only, loads saved tables, checks inputs, and formats the primary result. |
| `dashboard/charts.py` | Reusable chart encodings and self-contained chart serialization; no statistical estimation. |
| `dashboard/style.css` | Typography, colors, spacing, and responsive metric-card styling. |
| `sql/15_dashboard_queries.sql` | Named read-only queries; presentation-only histogram bins and parameterized player/baseline lookups. |
| `.streamlit/config.toml` | Localhost-only server defaults, quiet telemetry setting, and matching theme. |
| `requirements-dashboard.txt` | Pinned optional presentation dependencies; retains the original DuckDB requirement. |
| `scripts/validate_stage5.py` | Reruns SQL and dashboard checks without mutation and verifies preservation. |
| `tests/test_stage5.py` | Data contracts, chart checks, and Streamlit interaction regression tests. |
| `docs/data_flow.svg` | The raw-data-to-dashboard diagram used in both the app and README. |
| `docs/stage5_results.md` | This implementation, validation, and handoff record. |
| `docs/screenshots/stage5_*.jpg` | Six browser captures showing the verified presentation. |
| `reports/stage5_validation.json` | Generated validation results and protected-file hashes. |
| `data/processed/stage5_preservation_baseline.json` | Local, Git-ignored pre-edit preservation checkpoint. |

The top-level README was rewritten as a concise portfolio entry point. Earlier
stage reports and the data dictionary remain unchanged and linked. Streamlit,
Altair, and pandas are the only newly declared direct dependencies; pinned versions
were selected for the existing Python 3.9.6 environment. No additional statistical
dependencies were introduced.

## Limitations and remaining work

This is observational data without causal identification. History begins in 2015
and covers only regular-season QB/RB/WR/TE statistical appearances. Player clustering
does not eliminate dependence across players sharing games, opponents, or teams.
Role, injury, opponent strength, age, and selection remain possible explanations.
Failing to reject zero is not an equivalence test or proof of no effect. Exploratory
subgroups and secondary medians must not be promoted to definitive discoveries.

No required local presentation work remains. Optional future work includes a formal
mobile/accessibility audit and, only if requested, selecting a hosting approach,
updating the runtime for public operation, and defining a data refresh/review process.
There is no hosted URL or production deployment. Stop here for user review.
