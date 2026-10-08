-- Independent baseline definition: strict-date self join plus most-recent rank.
-- Unlike production ROWS framing, this does not use appearance_number.
CREATE OR REPLACE VIEW stage3_baseline_audit AS
SELECT p.player_id, p.game_id, h.game_id AS prior_game_id,
       h.game_date AS prior_game_date, h.fantasy_points_ppr AS prior_ppr_points
FROM clean_player_game_stats p
JOIN clean_player_game_stats h ON p.player_id=h.player_id AND h.game_date<p.game_date
QUALIFY row_number() OVER (
    PARTITION BY p.player_id,p.game_id ORDER BY h.game_date DESC,h.game_id DESC
) <= 8;

CREATE OR REPLACE VIEW stage3_validation_checks AS
WITH expected AS MATERIALIZED (
    SELECT p.player_id,p.game_id,
           count(a.prior_game_id) AS n, count(a.prior_ppr_points) AS ppr_n,
           avg(a.prior_ppr_points) AS mean_ppr,
           stddev_samp(a.prior_ppr_points) AS sd_ppr
    FROM clean_player_game_stats p LEFT JOIN stage3_baseline_audit a USING(player_id,game_id)
    GROUP BY p.player_id,p.game_id
), expected_analysis AS MATERIALIZED (
    SELECT f.* FROM player_game_features f
    JOIN expected e USING(player_id,game_id)
    WHERE e.n>=4 AND e.n=e.ppr_n AND f.actual_ppr_points IS NOT NULL
      AND (f.is_revenge_game OR f.player_id IN (
          SELECT r.player_id FROM player_game_features r
          JOIN expected re USING(player_id,game_id)
          WHERE r.is_revenge_game AND re.n>=4 AND re.n=re.ppr_n AND r.actual_ppr_points IS NOT NULL
      ))
)
SELECT 'features_missing_or_extra_keys' AS check_name,'ERROR' AS severity,count(*) AS problem_count
FROM (
    (SELECT player_id,game_id FROM clean_player_game_stats EXCEPT ALL
     SELECT player_id,game_id FROM player_game_features)
    UNION ALL
    (SELECT player_id,game_id FROM player_game_features EXCEPT ALL
     SELECT player_id,game_id FROM clean_player_game_stats)
)
UNION ALL
SELECT 'features_duplicate_keys','ERROR',count(*) FROM (
    SELECT player_id,game_id FROM player_game_features GROUP BY ALL HAVING count(*)>1
)
UNION ALL
SELECT 'current_game_in_baseline','ERROR',count(*) FROM player_game_baseline_support
WHERE game_id=prior_game_id
UNION ALL
SELECT 'same_day_or_future_game_in_baseline','ERROR',count(*) FROM player_game_baseline_support
WHERE prior_game_date>=game_date OR prior_game_date IS NULL
UNION ALL
SELECT 'window_more_than_eight_or_invalid_rank','ERROR',count(*) FROM (
    SELECT player_id,game_id FROM player_game_baseline_support GROUP BY ALL
    HAVING count(*)>8 OR min(appearances_back)<1 OR max(appearances_back)>8
)
UNION ALL
SELECT 'window_not_exact_eight_most_recent','ERROR',count(*) FROM (
    (SELECT player_id,game_id,prior_game_id FROM player_game_baseline_support EXCEPT ALL
     SELECT player_id,game_id,prior_game_id FROM stage3_baseline_audit)
    UNION ALL
    (SELECT player_id,game_id,prior_game_id FROM stage3_baseline_audit EXCEPT ALL
     SELECT player_id,game_id,prior_game_id FROM player_game_baseline_support)
)
UNION ALL
SELECT 'prior_counts_mismatch','ERROR',count(*) FROM player_game_features f JOIN expected e USING(player_id,game_id)
WHERE f.prior_game_count IS DISTINCT FROM e.n OR f.prior_ppr_count IS DISTINCT FROM e.ppr_n
UNION ALL
SELECT 'baseline_average_mismatch','ERROR',count(*) FROM player_game_features f JOIN expected e USING(player_id,game_id)
WHERE (expected_ppr_points IS NULL) != (mean_ppr IS NULL) OR abs(expected_ppr_points-mean_ppr)>1e-9
UNION ALL
SELECT 'sample_stddev_mismatch','ERROR',count(*) FROM player_game_features f JOIN expected e USING(player_id,game_id)
WHERE (rolling_ppr_stddev IS NULL) != (sd_ppr IS NULL) OR abs(rolling_ppr_stddev-sd_ppr)>1e-9
UNION ALL
SELECT 'stage2_fields_or_actual_changed','ERROR',count(*)
FROM player_game_features f JOIN player_game_revenge_flags s USING(player_id,game_id)
WHERE f.is_revenge_game IS DISTINCT FROM s.is_revenge_game
   OR f.is_first_meeting_with_former_team IS DISTINCT FROM s.is_first_meeting_with_former_team
   OR f.prior_opponent_appearances IS DISTINCT FROM s.prior_opponent_appearances
   OR f.actual_ppr_points IS DISTINCT FROM s.fantasy_points_ppr
   OR f.position IS DISTINCT FROM s.position OR f.team IS DISTINCT FROM s.team
   OR f.opponent_team IS DISTINCT FROM s.opponent_team OR f.game_date IS DISTINCT FROM s.game_date
   OR f.season IS DISTINCT FROM s.season OR f.week IS DISTINCT FROM s.week
UNION ALL
SELECT 'eligibility_mismatch','ERROR',count(*) FROM player_game_features f JOIN expected e USING(player_id,game_id)
WHERE is_effect_eligible IS DISTINCT FROM (e.n>=4 AND e.n=e.ppr_n AND actual_ppr_points IS NOT NULL)
UNION ALL
SELECT 'insufficient_history_has_effect','ERROR',count(*) FROM player_game_features
WHERE prior_game_count<4 AND (is_effect_eligible OR performance_residual IS NOT NULL
                             OR revenge_uplift IS NOT NULL OR revenge_score IS NOT NULL)
UNION ALL
SELECT 'residual_formula_mismatch','ERROR',count(*) FROM player_game_features
WHERE revenge_uplift IS DISTINCT FROM performance_residual
   OR (NOT is_effect_eligible AND performance_residual IS NOT NULL)
   OR (is_effect_eligible AND (performance_residual IS NULL
       OR abs(performance_residual-(actual_ppr_points-expected_ppr_points))>1e-9))
UNION ALL
SELECT 'undefined_stddev_has_score','ERROR',count(*) FROM player_game_features
WHERE (rolling_ppr_stddev IS NULL OR rolling_ppr_stddev=0)
  AND (revenge_score IS NOT NULL OR revenge_score_unavailable_reason IS NULL)
UNION ALL
SELECT 'stddev_status_mismatch','ERROR',count(*) FROM player_game_features
WHERE rolling_stddev_status IS DISTINCT FROM (
    CASE WHEN rolling_ppr_stddev IS NULL THEN 'missing'
         WHEN rolling_ppr_stddev=0 THEN 'zero' ELSE 'positive' END)
UNION ALL
SELECT 'score_reason_mismatch','ERROR',count(*) FROM player_game_features
WHERE revenge_score_unavailable_reason IS DISTINCT FROM (
    CASE WHEN prior_game_count<4 THEN 'insufficient_prior_appearances'
         WHEN prior_ppr_count!=prior_game_count THEN 'missing_prior_ppr'
         WHEN actual_ppr_points IS NULL THEN 'missing_actual_ppr'
         WHEN rolling_ppr_stddev IS NULL THEN 'missing_rolling_stddev'
         WHEN rolling_ppr_stddev=0 THEN 'zero_rolling_stddev' ELSE NULL END)
UNION ALL
SELECT 'score_formula_or_availability_mismatch','ERROR',count(*) FROM player_game_features
WHERE (revenge_score IS NULL) != (revenge_score_unavailable_reason IS NOT NULL)
   OR (revenge_score IS NOT NULL AND
       abs(revenge_score-performance_residual/nullif(rolling_ppr_stddev,0))>1e-9)
UNION ALL
SELECT 'nonfinite_metrics','ERROR',count(*) FROM player_game_features
WHERE NOT isfinite(expected_ppr_points) OR NOT isfinite(actual_ppr_points)
   OR NOT isfinite(rolling_ppr_stddev) OR NOT isfinite(performance_residual)
   OR NOT isfinite(revenge_score)
UNION ALL
SELECT 'analysis_duplicate_keys','ERROR',count(*) FROM (
    SELECT player_id,game_id FROM stage3_analysis_games GROUP BY ALL HAVING count(*)>1
)
UNION ALL
SELECT 'analysis_groups_not_shared_feature_rows','ERROR',count(*) FROM (
    (SELECT * EXCLUDE(game_group) FROM stage3_analysis_games EXCEPT ALL SELECT * FROM expected_analysis)
    UNION ALL
    (SELECT * FROM expected_analysis EXCEPT ALL SELECT * EXCLUDE(game_group) FROM stage3_analysis_games)
)
UNION ALL
SELECT 'analysis_group_labels_mismatch','ERROR',count(*) FROM stage3_analysis_games
WHERE game_group IS DISTINCT FROM CASE WHEN is_revenge_game THEN 'revenge' ELSE 'non_revenge' END
UNION ALL
SELECT 'comparison_players_without_eligible_revenge','ERROR',count(*) FROM analysis_comparison_games c
WHERE NOT EXISTS(SELECT 1 FROM analysis_revenge_games r WHERE r.player_id=c.player_id)
UNION ALL
SELECT 'analysis_below_four_prior_games','ERROR',count(*) FROM stage3_analysis_games
WHERE prior_game_count<4 OR NOT is_effect_eligible
UNION ALL
SELECT 'summary_counts_or_exceeded_pct_mismatch','ERROR',count(*) FROM stage3_summary s
WHERE sample_size != (SELECT count(*) FROM stage3_analysis_games a WHERE a.game_group=s.game_group
    AND (s.breakdown='overall' OR (s.breakdown='position' AND a.position=s.segment)
         OR (s.breakdown='meeting' AND a.is_revenge_game AND
             CASE WHEN a.is_first_meeting_with_former_team THEN 'first' ELSE 'later' END=s.segment)))
   OR abs(pct_exceeded_baseline - (
       SELECT 100.0*count(*) FILTER(WHERE performance_residual>1e-9)/count(*)
       FROM stage3_analysis_games a WHERE a.game_group=s.game_group
         AND (s.breakdown='overall' OR (s.breakdown='position' AND a.position=s.segment)
              OR (s.breakdown='meeting' AND a.is_revenge_game AND
                  CASE WHEN a.is_first_meeting_with_former_team THEN 'first' ELSE 'later' END=s.segment))
   ))>1e-9;
