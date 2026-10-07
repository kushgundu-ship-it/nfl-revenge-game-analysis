-- Every check returns a count of problems. ERROR prevents commit; WARN is reported.
CREATE OR REPLACE VIEW validation_checks AS
WITH raw_duplicates AS (
    SELECT player_id, game_id, count(*) AS n
    FROM raw_player_weekly_stats GROUP BY ALL HAVING count(*) > 1
), clean_duplicates AS (
    SELECT player_id, game_id, count(*) AS n
    FROM clean_player_game_stats GROUP BY ALL HAVING count(*) > 1
), schedule_duplicates AS (
    SELECT game_id FROM raw_schedules GROUP BY game_id HAVING count(*) > 1
), expected_seasons AS (
    SELECT range AS season FROM range(2015, 2026)
), valid_teams AS (
    SELECT unnest(['ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE',
        'DAL','DEN','DET','GB','HOU','IND','JAX','KC','LA','LAC',
        'LV','MIA','MIN','NE','NO','NYG','NYJ','PHI','PIT','SEA',
        'SF','TB','TEN','WAS']) AS team
)
SELECT 'raw_missing_player_id' AS check_name, 'WARN' AS severity, count(*) AS problem_count
FROM raw_player_weekly_stats WHERE nullif(trim(player_id), '') IS NULL
UNION ALL
SELECT 'raw_missing_game_id', 'ERROR', count(*) FROM raw_player_weekly_stats
WHERE nullif(trim(game_id), '') IS NULL
UNION ALL
SELECT 'raw_duplicate_player_game_groups', 'ERROR', count(*) FROM raw_duplicates
UNION ALL
SELECT 'clean_missing_player_or_game_id', 'ERROR', count(*) FROM clean_player_game_stats
WHERE nullif(trim(player_id), '') IS NULL OR nullif(trim(game_id), '') IS NULL
UNION ALL
SELECT 'clean_duplicate_player_game_groups', 'ERROR', count(*) FROM clean_duplicates
UNION ALL
SELECT 'schedule_missing_game_id', 'ERROR', count(*) FROM raw_schedules
WHERE nullif(trim(game_id), '') IS NULL
UNION ALL
SELECT 'schedule_duplicate_game_groups', 'ERROR', count(*) FROM schedule_duplicates
UNION ALL
SELECT 'missing_raw_seasons', 'ERROR', count(*) FROM expected_seasons e
WHERE NOT EXISTS (SELECT 1 FROM raw_player_weekly_stats p WHERE p.season=e.season)
UNION ALL
SELECT 'missing_clean_seasons', 'ERROR', count(*) FROM expected_seasons e
WHERE NOT EXISTS (SELECT 1 FROM clean_player_game_stats p WHERE p.season=e.season)
UNION ALL
SELECT 'missing_schedule_seasons', 'ERROR', count(*) FROM expected_seasons e
WHERE NOT EXISTS (SELECT 1 FROM clean_schedules s WHERE s.season=e.season)
UNION ALL
SELECT 'raw_out_of_scope_seasons', 'ERROR', count(*) FROM raw_player_weekly_stats
WHERE season IS NULL OR season NOT BETWEEN 2015 AND 2025
UNION ALL
SELECT 'raw_schedule_unmatched', 'ERROR', count(*) FROM raw_player_weekly_stats p
LEFT JOIN clean_schedules s ON p.game_id=s.game_id WHERE s.game_id IS NULL
UNION ALL
SELECT 'clean_schedule_unmatched', 'ERROR', count(*) FROM clean_player_game_stats
WHERE NOT schedule_matched
UNION ALL
SELECT 'raw_schedule_season_week_type_mismatch', 'ERROR', count(*)
FROM raw_player_weekly_stats p JOIN clean_schedules s ON p.game_id=s.game_id
WHERE p.season IS DISTINCT FROM s.season OR p.week IS DISTINCT FROM s.week
   OR p.season_type IS DISTINCT FROM (CASE WHEN s.game_type='REG' THEN 'REG' ELSE 'POST' END)
UNION ALL
SELECT 'raw_schedule_team_mismatch_or_missing', 'WARN', count(*)
FROM raw_player_weekly_stats p JOIN clean_schedules s ON p.game_id=s.game_id
WHERE NOT coalesce(
       (canonical_team(p.team)=s.home_team AND canonical_team(p.opponent_team)=s.away_team)
       OR (canonical_team(p.team)=s.away_team AND canonical_team(p.opponent_team)=s.home_team), false)
UNION ALL
SELECT 'clean_schedule_team_mismatch_or_missing', 'ERROR', count(*)
FROM clean_player_game_stats
WHERE NOT coalesce((team=home_team AND opponent_team=away_team)
    OR (team=away_team AND opponent_team=home_team), false)
UNION ALL
SELECT 'clean_invalid_team_codes', 'ERROR', count(*) FROM clean_player_game_stats
WHERE team IS NULL OR opponent_team IS NULL
   OR team NOT IN (SELECT team FROM valid_teams)
   OR opponent_team NOT IN (SELECT team FROM valid_teams)
UNION ALL
SELECT 'clean_missing_ppr', 'ERROR', count(*) FROM clean_player_game_stats
WHERE fantasy_points_ppr IS NULL OR NOT isfinite(fantasy_points_ppr)
UNION ALL
SELECT 'clean_out_of_scope_records', 'ERROR', count(*) FROM clean_player_game_stats
WHERE season_type != 'REG' OR position NOT IN ('QB','RB','WR','TE')
   OR season NOT BETWEEN 2015 AND 2025
UNION ALL
SELECT 'regular_schedule_games_without_player_rows', 'ERROR', count(*)
FROM clean_schedules s WHERE s.game_type='REG'
AND NOT EXISTS (SELECT 1 FROM clean_player_game_stats p WHERE p.game_id=s.game_id)
UNION ALL
SELECT 'regular_schedule_unfinished_games', 'ERROR', count(*) FROM clean_schedules
WHERE game_type='REG' AND (home_score IS NULL OR away_score IS NULL)
UNION ALL
-- 2022 had 271 completed games: the BUF-CIN game was canceled.
SELECT 'unexpected_regular_game_count', 'ERROR', count(*) FROM (
    SELECT season, count(*) AS n FROM clean_schedules WHERE game_type='REG' GROUP BY season
) s WHERE n != CASE WHEN season <= 2020 THEN 256 WHEN season=2022 THEN 271 ELSE 272 END;

CREATE OR REPLACE VIEW season_row_counts AS
SELECT e.range AS season,
    (SELECT count(*) FROM raw_player_weekly_stats p WHERE p.season=e.range) AS raw_player_rows,
    (SELECT count(*) FROM clean_player_game_stats p WHERE p.season=e.range) AS clean_player_rows,
    (SELECT count(*) FROM clean_schedules s WHERE s.season=e.range) AS schedule_rows,
    (SELECT count(*) FROM clean_schedules s WHERE s.season=e.range AND game_type='REG') AS regular_games,
    (SELECT count(*) FROM clean_player_game_stats p WHERE p.season=e.range AND schedule_matched) AS matched_clean_rows
FROM range(2015, 2026) e;
