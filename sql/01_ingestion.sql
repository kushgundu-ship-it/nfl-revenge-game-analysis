-- Stage 1 only. Python supplies file paths; all filtering and cleaning is SQL.
-- Rebuilding (rather than INSERT/appending) makes reruns safe.
-- The caller wraps this file and validation in a single transaction.
CREATE OR REPLACE TABLE raw_player_weekly_stats AS
SELECT *, filename AS source_file
FROM read_parquet(getvariable('player_files'), union_by_name = true, filename = true);

-- The complete downloaded CSV is retained on disk. Import only our 11 seasons.
-- all_varchar preserves identifiers (including leading zeroes) in source form.
CREATE OR REPLACE TABLE raw_schedules AS
SELECT *
FROM read_csv(getvariable('schedule_file'), header = true, all_varchar = true)
WHERE CAST(season AS INTEGER) BETWEEN 2015 AND 2025;

-- A SQL macro is a small reusable expression, not a separate Python transform.
-- Use the current nflverse franchise codes; preserve originals in the view.
CREATE OR REPLACE MACRO canonical_team(code) AS
    CASE upper(trim(code))
        WHEN 'OAK' THEN 'LV'
        WHEN 'SD' THEN 'LAC'
        WHEN 'STL' THEN 'LA'
        WHEN 'LAR' THEN 'LA'
        WHEN 'JAC' THEN 'JAX'
        ELSE upper(trim(code))
    END;

CREATE OR REPLACE VIEW clean_schedules AS
SELECT
    game_id,
    CAST(season AS INTEGER) AS season,
    CAST(week AS INTEGER) AS week,
    game_type,
    CAST(gameday AS DATE) AS game_date,
    away_team AS source_away_team,
    home_team AS source_home_team,
    canonical_team(away_team) AS away_team,
    canonical_team(home_team) AS home_team,
    CAST(away_score AS INTEGER) AS away_score,
    CAST(home_score AS INTEGER) AS home_score,
    location
FROM raw_schedules;

-- A view is a saved query: it leaves the raw table untouched.
-- Keep all original statistics. Do not turn unknown values into invented zeros,
-- silently deduplicate, or drop unmatched schedule rows.
CREATE OR REPLACE VIEW clean_player_game_stats AS
SELECT
    p.* EXCLUDE (filename, team, opponent_team),
    p.team AS source_team,
    p.opponent_team AS source_opponent_team,
    canonical_team(p.team) AS team,
    canonical_team(p.opponent_team) AS opponent_team,
    s.game_date,
    s.game_type AS schedule_game_type,
    s.home_team,
    s.away_team,
    s.home_score,
    s.away_score,
    s.game_id IS NOT NULL AS schedule_matched
FROM raw_player_weekly_stats p
LEFT JOIN clean_schedules s ON p.game_id = s.game_id
WHERE p.season BETWEEN 2015 AND 2025
  AND p.season_type = 'REG'
  AND p.position IN ('QB', 'RB', 'WR', 'TE');
