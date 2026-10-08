# Stage 2 checkpoint — former teams and revenge games

## Result

The saved Stage 1 snapshot yields **875 revenge-game performances**, involving
**359 distinct players** and **545 first qualifying meetings**. These are player-game
rows, not 875 distinct NFL matchups. There are 61,977 eligible player-game records,
3,349 observed player/team relationships, and 88,450 history-as-of-game rows.

| Season | Eligible player-games | Revenge games | First qualifying meetings |
| --- | ---: | ---: | ---: |
| 2015 | 5,423 | 2 | 2 |
| 2016 | 5,413 | 22 | 19 |
| 2017 | 5,448 | 40 | 33 |
| 2018 | 5,363 | 63 | 50 |
| 2019 | 5,411 | 78 | 48 |
| 2020 | 5,543 | 88 | 56 |
| 2021 | 5,866 | 114 | 71 |
| 2022 | 5,808 | 101 | 62 |
| 2023 | 5,801 | 119 | 75 |
| 2024 | 5,864 | 127 | 68 |
| 2025 | 6,037 | 121 | 61 |
| **Total** | **61,977** | **875** | **545** |

## How the rule works

For each player-game, find rows with the same stable player ID and a strictly
earlier game date. Group those rows by team and count them. If the current opponent
has at least four such appearances, flag this player-game as revenge. Appearances
across multiple stints with the same franchise accumulate. Current-day and future
appearances are excluded; no name matching is used.

The first-meeting flag is true if this is a qualifying revenge game and the player
has no earlier qualifying revenge game against that franchise. It is independent
for each former team, and does not reset after a later transfer. Facing a future
employer before joining it is not a former-team meeting. A meeting below the
four-appearance threshold is not qualifying and does not consume the flag.

`player_team_history` summarizes the whole observed relationship and therefore can
contain dates after a particular game. It is descriptive only. Classification uses
`player_team_history_asof`, which enforces the strictly-earlier rule, not full-window
totals. Every Stage 2 object is a view, so it follows the current Stage 1 data.

## Manual checks

I inspected each selected current record, independently queried its earlier Stage 1
records by stable ID and opponent, and added the per-season counts shown below.
For the small-count cases I also inspected every supporting game ID/date. These
queries are saved in `sql/06_stage2_inspect.sql`. Linked official team coverage
corroborates the real matchups; exact observed appearance counts come from the local
Stage 1 ledger, not from those articles or a roster/tenure assumption.

| Player (stable ID) | Current game | Team → opponent | Earlier appearances for opponent | Revenge? | First? |
| --- | --- | --- | ---: | --- | --- |
| Shaun Draughn (`00-0028202`) | `2015_14_SF_CLE`, 2015-12-13 | SF → CLE | 5 | Yes | Yes |
| Mark Sanchez (`00-0026898`) | `2016_17_DAL_PHI`, 2017-01-01 | DAL → PHI | 3 | No | No |
| Adrian Peterson (`00-0025394`) | `2018_05_WAS_NO`, 2018-10-08 | WAS → NO | 4 | Yes | Yes |
| Tom Brady (`00-0019596`) | `2021_04_TB_NE`, 2021-10-03 | TB → NE | 76 | Yes | Yes |
| Matthew Stafford (`00-0026498`) | `2021_07_DET_LA`, 2021-10-24 | LA → DET | 88 | Yes | Yes |
| Jared Goff (`00-0033106`) | `2021_07_DET_LA`, 2021-10-24 | DET → LA | 69 | Yes | Yes |
| Baker Mayfield (`00-0034855`) | `2022_01_CLE_CAR`, 2022-09-11 | CAR → CLE | 60 | Yes | Yes |
| Davante Adams (`00-0031381`) | `2023_05_GB_LV`, 2023-10-09 | LV → GB | 100 | Yes | Yes |
| Matthew Stafford (`00-0026498`) | `2024_01_LA_DET`, 2024-09-08 | LA → DET | 88 | Yes | No |
| Amari Cooper (`00-0031544`) | `2024_04_CLE_LV`, 2024-09-29 | CLE → LV | 52 | Yes | Yes |

### Same-season change: Shaun Draughn

The five earlier CLE records are `2015_01_CLE_NYJ` (September 13),
`2015_02_TEN_CLE` (September 20), `2015_03_OAK_CLE` (September 27),
`2015_04_CLE_SD` (October 4), and `2015_06_DEN_CLE` (October 18).
All precede his December 13 SF appearance against CLE. The 49ers documented his
[signing](https://www.49ers.com/news/49ers-sign-rb-shaun-draughn-16210362) and
[Cleveland matchup](https://www.49ers.com/news/live-updates-san-francisco-49ers-vs-cleveland-browns-16488329).
This verifies history from earlier in the same season counts without using a later roster.

### Below threshold: Mark Sanchez

The only PHI records in this dataset are `2015_10_MIA_PHI` (November 15),
`2015_11_TB_PHI` (November 22), and `2015_12_PHI_DET` (November 26).
Three is below four, so his [2016 season finale appearance for Dallas against
Philadelphia](https://www.dallascowboys.com/news/game-recap-cowboys-fall-to-eagles-27-13-in-season-finale-424836)
is excluded. This is a dataset-scoped decision, not a claim that he had only three
career Eagles appearances. Pre-2015 games are outside our history window.

### Exactly four: Adrian Peterson

His Saints records are `2017_01_NO_MIN` (September 11), `2017_02_NE_NO`
(September 17), `2017_03_NO_CAR` (September 24), and `2017_04_NO_MIA`
(October 1). All four precede the 2018 Washington–New Orleans game.
The [official Washington signing article](https://www.commanders.com/news/redskins-sign-running-back-adrian-peterson)
also explicitly records his four-game Saints stint. The threshold is inclusive:
four qualifies; three does not.

### Established former teams and a repeated meeting

- **Brady:** NE counts for 2015–2019 are 16 + 12 + 16 + 16 + 16 = **76**.
  The latest is 2019-12-29, before his [2021 return](https://www.buccaneers.com/news/bucs-patriots-week-four-game-recap-bucs-win-19-17).
- **Stafford:** DET counts for 2015–2020 are 16 + 16 + 16 + 16 + 8 + 16 = **88**.
  The latest is 2021-01-03. His [2021 Lions game](https://www.therams.com/news/game-recap-rams-lions-week-7-2021)
  is first; his [2024 Lions game](https://www.therams.com/news/game-recap-rams-fall-to-lions-26-20-in-overtime-on-sunday-night-football)
  remains revenge with the same 88 earlier DET appearances but is not first.
- **Goff:** LA counts for 2016–2020 are 7 + 15 + 16 + 16 + 15 = **69**.
  The latest is 2020-12-27. He qualifies on the other side of the same 2021 game.
  Two players in one NFL game have separate player-game records.
- **Mayfield:** CLE counts for 2018–2021 are 14 + 16 + 16 + 14 = **60**.
  The latest is 2022-01-03, before his [Carolina opener against Cleveland](https://www.panthers.com/news/slow-start-fast-finish-for-baker-mayfield).
- **Adams:** GB counts for 2015–2021 are 13 + 16 + 14 + 15 + 12 + 14 + 16 = **100**.
  The latest is 2022-01-09, before the [2023 Packers–Raiders game](https://www.raiders.com/game-day/2023/reg-week5/packers-at-raiders/box-score).

### Franchise relocation: Amari Cooper

The historical Raiders counts are 16 + 16 + 14 + 6 = **52** for 2015–2018, all
before [Cleveland's September 2024 game at Las Vegas](https://www.clevelandbrowns.com/news/raiders-20-browns-16-final-score-stats-game-recap).
The latest is 2018-10-14. Stage 1 canonical codes let the historical Oakland
appearances count toward the same Raiders franchise, represented as `LV`.

## Validation performed

- Reran the unchanged Stage 1 ingestion with `--offline --verify-rerun` after adding
  Stage 2. It passed all 20 error checks and retained identical Stage 1 fingerprints.
- Ran Stage 2's builder and all 19 Stage 2 checks. All returned zero problems.
  These cover history/as-of key uniqueness and completeness, exact prior counts,
  revenge dataset uniqueness/completeness, the four-game minimum, strictly earlier
  dates, independent opponent counts, and first-meeting correctness.
- Confirmed Stage 2 did not change fingerprints for Stage 1's two raw tables and
  cleaned view. Reran the builder successfully; views are replaced, not appended.
- Ran four automated test cases successfully. They check three versus four prior
  games, future appearances not changing an earlier decision, first versus repeated
  meetings, return stints, name changes/name collisions, and same-day exclusion.
- The real-data test removes all records on/after **2018-10-31**, then separately
  **2022-11-01**, in memory. Every remaining all-game flag and history-as-of row is
  identical to its full-data counterpart. This checks that later data cannot affect
  earlier counts or labels. Descriptive full-window history is intentionally excluded
  from this test because its purpose is to summarize the whole available window.
- Executed both read-only inspection SQL files successfully.

The two existing Stage 1 warnings remain: 236 raw `Team` rows lack player IDs, and
two of those lack opponents. These records do not enter the cleaned data or Stage 2.
Current machine-readable results are in `data/processed/stage2_validation_report.json`.

## Limits and checkpoint

History starts in 2015; no prior career appearances are inferred. This especially
reduces detected revenge games in early seasons, so the increasing counts by year
must not be interpreted as a trend in player motivation. First means first qualifying
meeting in the observed regular-season window; postseason reunions are excluded.
Only recorded appearances at the four eligible positions count, including records
that may have zero offensive production. Neither roster membership nor transaction
dates establish former-team status.

The word "revenge" is a rule-based label, not evidence of intent or better performance.
No previous-eight-game averages, expected points, revenge uplift, or dashboard was
created. Stage 2 stops here for review.

```bash
cd /Users/kushg/SQL_NFL_Project
source .venv/bin/activate
python scripts/build_stage2.py
python scripts/query.py sql/06_stage2_inspect.sql
python -m unittest discover -s tests -v
```
