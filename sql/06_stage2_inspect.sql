-- Run read-only: python scripts/query.py sql/06_stage2_inspect.sql
SELECT * FROM stage2_season_counts ORDER BY season;
SELECT * FROM stage2_validation_checks ORDER BY check_name;
SELECT player_id, player_display_name, game_id, game_date, team, opponent_team,
       prior_opponent_appearances, last_prior_opponent_game_date,
       prior_qualifying_meetings, is_first_meeting_with_former_team
FROM fact_revenge_games ORDER BY game_date, game_id, player_id LIMIT 12;

-- Stable IDs select the examples; names are for display only.
SELECT player_id, player_display_name, game_id, game_date, team, opponent_team,
       prior_opponent_appearances, last_prior_opponent_game_date,
       is_revenge_game, is_first_meeting_with_former_team
FROM player_game_revenge_flags
WHERE (player_id='00-0019596' AND game_id='2021_04_TB_NE')
   OR (player_id IN ('00-0026498','00-0033106') AND game_id='2021_07_DET_LA')
   OR (player_id='00-0034855' AND game_id='2022_01_CLE_CAR')
   OR (player_id='00-0031381' AND game_id='2023_05_GB_LV')
   OR (player_id='00-0026498' AND game_id='2024_01_LA_DET')
   OR (player_id='00-0025394' AND game_id='2018_05_WAS_NO')
   OR (player_id='00-0026898' AND game_id='2016_17_DAL_PHI')
   OR (player_id='00-0028202' AND game_id='2015_14_SF_CLE')
   OR (player_id='00-0031544' AND game_id='2024_04_CLE_LV')
ORDER BY game_date, player_id;

-- Independent manual-audit ledger: count the source appearances by season.
-- This reads Stage 1 directly, not the Stage 2 counts or labels.
WITH examples(player_id, game_id) AS (VALUES
    ('00-0019596','2021_04_TB_NE'), ('00-0026498','2021_07_DET_LA'),
    ('00-0033106','2021_07_DET_LA'), ('00-0034855','2022_01_CLE_CAR'),
    ('00-0031381','2023_05_GB_LV'), ('00-0026498','2024_01_LA_DET'),
    ('00-0025394','2018_05_WAS_NO'), ('00-0026898','2016_17_DAL_PHI'),
    ('00-0028202','2015_14_SF_CLE'), ('00-0031544','2024_04_CLE_LV')
)
SELECT p.player_id, p.player_display_name, p.game_id AS current_game,
       h.team AS earlier_team, h.season AS earlier_season, count(*) AS earlier_games,
       min(h.game_date) AS first_earlier_date, max(h.game_date) AS last_earlier_date
FROM examples e JOIN clean_player_game_stats p USING(player_id,game_id)
JOIN clean_player_game_stats h ON h.player_id=p.player_id
    AND h.team=p.opponent_team AND h.game_date<p.game_date
GROUP BY ALL ORDER BY p.player_id, current_game, earlier_season;

-- Show every supporting game for the small-count boundary and same-season cases.
WITH examples(player_id, game_id) AS (VALUES
    ('00-0025394','2018_05_WAS_NO'), ('00-0026898','2016_17_DAL_PHI'),
    ('00-0028202','2015_14_SF_CLE')
)
SELECT p.player_display_name, p.game_id AS current_game,
       h.game_id AS earlier_game, h.game_date AS earlier_date, h.team AS earlier_team
FROM examples e JOIN clean_player_game_stats p USING(player_id,game_id)
JOIN clean_player_game_stats h ON h.player_id=p.player_id
    AND h.team=p.opponent_team AND h.game_date<p.game_date
ORDER BY p.player_id,h.game_date;
