-- Read-only: python scripts/query.py sql/10_stage3_inspect.sql
SELECT breakdown,segment,game_group,sample_size,player_count,
       round(pct_exceeded_baseline,2) AS pct_exceeded,
       round(mean_actual_ppr,3) AS mean_actual,
       round(mean_expected_ppr,3) AS mean_expected,
       round(mean_residual,3) AS mean_residual,
       round(median_residual,3) AS median_residual,standardized_score_count
FROM stage3_summary ORDER BY breakdown,segment,game_group;

SELECT * FROM stage3_validation_checks ORDER BY check_name;

-- Edit these stable IDs/game IDs to inspect other players.
WITH examples(player_id,game_id) AS (VALUES
    ('00-0019596','2021_04_TB_NE'), ('00-0026498','2021_07_DET_LA'),
    ('00-0031381','2023_05_GB_LV'), ('00-0025394','2018_05_WAS_NO')
)
SELECT f.player_display_name,f.game_id,f.prior_game_count,
       round(f.expected_ppr_points,4) AS previous_eight_avg,
       round(f.rolling_ppr_stddev,4) AS sample_stddev,
       f.actual_ppr_points,round(f.revenge_uplift,4) AS uplift,
       round(f.revenge_score,4) AS standardized_score,f.revenge_score_unavailable_reason
FROM player_game_features f JOIN examples e USING(player_id,game_id)
ORDER BY f.player_display_name;

WITH examples(player_id,game_id) AS (VALUES
    ('00-0019596','2021_04_TB_NE'), ('00-0026498','2021_07_DET_LA'),
    ('00-0031381','2023_05_GB_LV'), ('00-0025394','2018_05_WAS_NO')
)
SELECT f.player_display_name,b.game_id AS current_game,b.appearances_back,
       b.prior_game_id,b.prior_game_date,b.prior_team,b.prior_opponent_team,
       round(b.prior_ppr_points,2) AS prior_ppr
FROM examples e JOIN player_game_features f USING(player_id,game_id)
JOIN player_game_baseline_support b USING(player_id,game_id)
ORDER BY f.player_display_name,b.prior_game_date;
