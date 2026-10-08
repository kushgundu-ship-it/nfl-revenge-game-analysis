CREATE OR REPLACE VIEW stage4_segments AS
WITH segmented AS (
    SELECT 'overall' AS breakdown,'ALL' AS segment,* FROM stage4_analysis_games
    UNION ALL SELECT 'position',position,* FROM stage4_analysis_games
    UNION ALL SELECT 'venue',CASE WHEN is_home THEN 'home' ELSE 'away' END,* FROM stage4_analysis_games
    UNION ALL SELECT 'meeting',CASE WHEN is_first_meeting_with_former_team THEN 'first' ELSE 'later' END,*
        FROM stage4_analysis_games WHERE is_revenge_game
    UNION ALL SELECT 'departure',departure_bucket,* FROM stage4_analysis_games WHERE is_revenge_game
)
SELECT breakdown,segment,game_group,count(*) AS games,count(DISTINCT player_id) AS players,
       avg(performance_residual) AS mean_residual,median(performance_residual) AS median_residual,
       100.0*avg(CAST(performance_residual>1e-9 AS INTEGER)) AS pct_exceeded,
       avg(days_since_former_team) AS mean_days_since_former_team,
       median(days_since_former_team) AS median_days_since_former_team,
       min(days_since_former_team) AS min_days_since_former_team,
       max(days_since_former_team) AS max_days_since_former_team
FROM segmented GROUP BY ALL;

CREATE OR REPLACE VIEW stage4_usage_efficiency AS
SELECT position,metric,metric_family,game_group,count(*) AS eligible_games,
       count(actual) AS actual_n,count(expected) AS expected_n,count(residual) AS residual_n,
       count(DISTINCT player_id) FILTER(WHERE residual IS NOT NULL) AS residual_players,
       count(*) FILTER(WHERE actual IS NULL) AS undefined_actual_n,
       count(*) FILTER(WHERE expected IS NULL) AS unavailable_baseline_n,
       avg(actual) AS mean_actual_all_valid,
       avg(actual) FILTER(WHERE residual IS NOT NULL) AS mean_actual_paired,
       avg(expected) FILTER(WHERE residual IS NOT NULL) AS mean_expected_paired,
       avg(residual) AS mean_residual,median(residual) AS median_residual
FROM stage4_analysis_metrics GROUP BY ALL;

CREATE OR REPLACE VIEW stage4_usage_efficiency_differences AS
SELECT r.position,r.metric,r.metric_family,r.residual_n AS revenge_n,n.residual_n AS non_revenge_n,
       r.mean_residual AS revenge_mean_residual,n.mean_residual AS non_revenge_mean_residual,
       r.mean_residual-n.mean_residual AS mean_residual_difference
FROM stage4_usage_efficiency r JOIN stage4_usage_efficiency n USING(position,metric,metric_family)
WHERE r.game_group='revenge' AND n.game_group='non_revenge';

-- One common, outcome-defined cutoff pair over BOTH groups; ties are retained.
-- These analysis views never update/delete any source or Stage 3 record.
CREATE OR REPLACE VIEW stage4_outlier_cutoffs AS
SELECT quantile_cont(performance_residual,0.01) AS p01,
       quantile_cont(performance_residual,0.99) AS p99 FROM stage4_analysis_games;

CREATE OR REPLACE VIEW stage4_sensitivity_games AS
SELECT 'raw' AS variant,a.*,performance_residual AS analysis_residual
FROM stage4_analysis_games a
UNION ALL
SELECT 'trimmed_1_99',a.*,performance_residual FROM stage4_analysis_games a,stage4_outlier_cutoffs c
WHERE performance_residual BETWEEN c.p01 AND c.p99
UNION ALL
SELECT 'winsorized_1_99',a.*,greatest(c.p01,least(c.p99,performance_residual))
FROM stage4_analysis_games a,stage4_outlier_cutoffs c;

CREATE OR REPLACE VIEW stage4_sensitivity_groups AS
SELECT variant,game_group,count(*) AS games,count(DISTINCT player_id) AS players,
       avg(analysis_residual) AS mean_residual,median(analysis_residual) AS median_residual
FROM stage4_sensitivity_games GROUP BY ALL;

CREATE OR REPLACE VIEW stage4_sensitivity_results AS
WITH paired AS (
    SELECT variant,player_id,
        avg(analysis_residual) FILTER(WHERE is_revenge_game)
          -avg(analysis_residual) FILTER(WHERE NOT is_revenge_game) AS difference
    FROM stage4_sensitivity_games GROUP BY ALL
    HAVING count(*) FILTER(WHERE is_revenge_game)>0 AND count(*) FILTER(WHERE NOT is_revenge_game)>0
), equal_players AS (
    SELECT variant,count(*) AS paired_players,avg(difference) AS equal_player_mean_difference
    FROM paired GROUP BY variant
)
SELECT r.variant,r.games AS revenge_n,n.games AS non_revenge_n,
       r.mean_residual-n.mean_residual AS pooled_mean_difference,
       r.median_residual-n.median_residual AS pooled_median_difference,
       e.paired_players,e.equal_player_mean_difference
FROM stage4_sensitivity_groups r JOIN stage4_sensitivity_groups n USING(variant)
JOIN equal_players e USING(variant)
WHERE r.game_group='revenge' AND n.game_group='non_revenge';

CREATE OR REPLACE VIEW stage4_extreme_revenge AS
WITH ranked AS (
    SELECT player_id,player_display_name,game_id,game_date,position,team,opponent_team,
           actual_ppr_points,expected_ppr_points,performance_residual,
           row_number() OVER(ORDER BY performance_residual DESC,player_id,game_id) AS positive_rank,
           row_number() OVER(ORDER BY performance_residual,player_id,game_id) AS negative_rank
    FROM stage4_analysis_games WHERE is_revenge_game
)
SELECT * FROM ranked WHERE positive_rank<=10 OR negative_rank<=10;
