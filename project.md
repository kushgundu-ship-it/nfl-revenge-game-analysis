# NFL Revenge Game Analysis

## Project overview

Build a SQL-first analytics project that tests whether NFL players perform better than expected when facing a former team.

The project should answer a real analytical question rather than simply rank high-scoring revenge games:

> Do NFL players outperform their own recent baseline when playing against a former team?

The most valuable result may be that no meaningful revenge effect exists. The goal is a defensible analysis, not a predetermined conclusion.

## MVP scope

- Seasons: 2015-2025
- Games: regular season only
- Positions: QB, RB, WR, and TE
- Database: PostgreSQL preferred; DuckDB is acceptable for a lighter local setup
- Primary data source: [nflverse](https://github.com/nflverse/nflverse-data)
- Primary outcome: PPR fantasy points relative to the player's recent baseline
- Supporting outcomes: opportunities, yardage, touchdowns, and efficiency
- Keep data ingestion lightweight; perform cleaning, transformation, and analysis primarily in SQL

Do not include the incomplete 2026 season in the initial analysis.

## Definitions

### Former team

A team qualifies as a player's former team when:

1. The team is the player's opponent in the current game.
2. The player previously recorded game-level statistics for that team.
3. The player appeared in at least four earlier games for that team.

This definition deliberately uses recorded appearances instead of assuming that merely appearing on a roster represents meaningful team history.

### Revenge game

A revenge game is a game against any qualifying former team. Keep a separate flag for the player's first meeting with that former team so the first reunion can be analyzed independently from later meetings.

### Expected performance

Expected performance is the player's average over the eight games immediately preceding the current game. Require at least four prior games before calculating an effect.

Only past games may enter the baseline. Never use full-season averages that include games occurring after the revenge game.

### Revenge uplift

```text
revenge_uplift = actual_ppr_points - expected_ppr_points
```

Also calculate a standardized version so unusually volatile players do not dominate the rankings:

```text
revenge_score =
    (actual_ppr_points - expected_ppr_points)
    / standard_deviation_of_recent_ppr_points
```

Handle a zero or missing standard deviation explicitly.

## Data sources

Start with nflverse weekly player statistics. The dataset provides player IDs, names, positions, seasons, weeks, game IDs, teams, opponents, and passing, rushing, receiving, defensive, and fantasy statistics.

- [Weekly player statistics documentation](https://nflreadr.nflverse.com/reference/load_player_stats.html)
- [Player-stat data dictionary](https://nflreadr.nflverse.com/articles/dictionary_player_stats.html)
- [Schedule documentation](https://nflreadr.nflverse.com/reference/load_schedules.html)
- [Weekly roster loader](https://github.com/nflverse/nflreadr/blob/main/R/load_rosters_weekly.R)

Optional later additions:

- Weekly rosters for players without box-score activity
- Snap counts to control for playing time
- Trades to distinguish trades from free-agent departures
- Next Gen Stats for opportunity and efficiency metrics
- Team defense strength for opponent adjustment

Use stable player IDs for joins. Do not join players by name.

## Suggested data model

### `raw_player_weekly_stats`

One row per player and game, kept close to the source format.

Important fields:

- `player_id`
- `player_display_name`
- `position`
- `season`
- `week`
- `season_type`
- `game_id`
- `team`
- `opponent_team`
- `fantasy_points_ppr`
- Passing, rushing, and receiving statistics

### `dim_players`

One row per player with stable biographical and positional information.

### `dim_games`

One row per game with date, season, week, home team, away team, scores, and location.

### `player_team_history`

One row per player-team relationship, including:

- First appearance
- Last appearance
- Games played
- Seasons represented

### `player_game_features`

One row per player-game containing engineered features:

- Previous eight-game averages
- Previous eight-game standard deviation
- Prior-game count
- Home/away status
- Days since last game
- Whether the opponent is a former team
- Whether this is the first meeting with that former team
- Time since the player left that team

### `fact_revenge_games`

The final analysis-ready revenge-game records, including actual production, expected production, uplift, and standardized revenge score.

## Core analysis

Answer these questions first:

1. What percentage of revenge-game performances exceed the player's rolling baseline?
2. What are the mean and median revenge uplifts?
3. Is the result different for QB, RB, WR, and TE?
4. Is the effect stronger during the first meeting with the former team?
5. Is apparent improvement driven by additional opportunities or greater efficiency?
6. Does the effect change with time since departure?
7. Does home-field status matter?
8. Are the overall results driven by a small number of extreme performances?

Always report sample sizes. Use medians and distributions alongside averages.

## Usage versus efficiency

Separate two possible explanations:

### Usage revenge

- Pass attempts
- Carries
- Targets
- Receptions
- Total opportunities

### Efficiency revenge

- Passing yards per attempt
- Rushing yards per carry
- Receiving yards per target
- Touchdowns per opportunity
- EPA-based measures if play-by-play data is added

A player scoring more because of extra touches is a different finding from a player becoming more efficient with the same workload.

## Comparison group

Do not evaluate revenge games in isolation. Build a comparison group consisting of the same players' non-revenge games and calculate the same rolling-baseline residual:

```text
performance_residual = actual_performance - rolling_expected_performance
```

Compare the distribution of residuals for revenge and non-revenge games. Later versions can match games by position, season, workload, home/away status, and opponent defensive strength.

## Data-quality rules

- Standardize relocated franchise abbreviations, such as OAK/LV and SD/LAC.
- Exclude postseason games from the MVP.
- Verify that each player-game row is unique.
- Exclude games with insufficient prior history from effect estimates.
- Treat byes and missed games carefully: an eight-game baseline means eight appearances, not eight calendar weeks.
- Inspect trades within the same season to ensure that only earlier appearances establish former-team status.
- Preserve raw imported data and perform transformations in separate tables or views.

## Suggested repository structure

```text
NFL_SQL_Project/
├── PROJECT.md
├── README.md
├── data/
│   ├── raw/
│   └── processed/
├── sql/
│   ├── 01_schema.sql
│   ├── 02_data_quality.sql
│   ├── 03_team_history.sql
│   ├── 04_player_game_features.sql
│   ├── 05_revenge_games.sql
│   └── 06_analysis.sql
├── scripts/
│   └── load_data.py
├── dashboard/
└── docs/
    └── data_dictionary.md
```

Do not commit large raw datasets or credentials. Add them to `.gitignore` when the repository is initialized.

## Milestones

### Milestone 1: reproducible dataset

- Download weekly player stats for 2015-2025
- Load them into the database
- Confirm row counts, uniqueness, missing values, and valid team abbreviations

### Milestone 2: revenge-game identification

- Build player-team history
- Identify games against former teams
- Add minimum-tenure and first-meeting flags
- Manually validate a small sample of well-known cases

### Milestone 3: baseline model

- Calculate lagged eight-appearance averages
- Calculate performance residuals
- Prevent future-data leakage
- Compare revenge and non-revenge distributions

### Milestone 4: deeper analysis

- Separate usage from efficiency
- Segment by position and time since departure
- Add home/away and opponent-strength controls
- Test whether outliers drive the result

### Milestone 5: portfolio presentation

- Publish documented SQL queries
- Create an ER diagram
- Build a small dashboard
- Write a clear README covering methods, findings, limitations, and reproducibility

## Completion criteria

The MVP is complete when another person can:

1. Load the source data using the documented process.
2. Run the SQL files in order.
3. Reproduce the revenge-game dataset.
4. See how every metric is defined.
5. Review both aggregate findings and individual examples.
6. Understand the limitations without reading the implementation code.

## Working title

**Is the NFL Revenge Game Real? A SQL Analysis of Player Performance Against Former Teams**

