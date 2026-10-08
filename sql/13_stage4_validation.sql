-- Independent strict-date contributor set from Stage 3's validated audit.
CREATE OR REPLACE VIEW stage4_baseline_audit AS
SELECT m.player_id,m.game_id,m.metric,count(h.game_id) AS window_n,
       count(h.actual) AS valid_prior_n,avg(h.actual) AS prior_mean,
       min(h.game_date) AS first_date,max(h.game_date) AS last_date
FROM stage4_metric_actuals m
LEFT JOIN stage3_baseline_audit b USING(player_id,game_id)
LEFT JOIN stage4_metric_actuals h
  ON h.player_id=m.player_id AND h.game_id=b.prior_game_id AND h.metric=m.metric
GROUP BY m.player_id,m.game_id,m.metric;

CREATE OR REPLACE VIEW stage4_validation_checks AS
WITH audited AS MATERIALIZED (
    SELECT f.*,a.window_n AS audit_n,a.valid_prior_n AS audit_valid_n,a.prior_mean AS audit_mean,
           a.first_date,a.last_date
    FROM stage4_metric_features f JOIN stage4_baseline_audit a USING(player_id,game_id,metric)
)
SELECT 'metric_key_coverage' AS check_name,'ERROR' AS severity,count(*) AS problem_count FROM (
    SELECT player_id,game_id FROM stage4_metric_features GROUP BY ALL
    HAVING count(*)!=9 OR count(DISTINCT metric)!=9
)
UNION ALL SELECT 'game_key_coverage','ERROR',count(*) FROM (
    (SELECT player_id,game_id FROM stage4_game_context EXCEPT ALL SELECT player_id,game_id FROM player_game_features)
    UNION ALL
    (SELECT player_id,game_id FROM player_game_features EXCEPT ALL SELECT player_id,game_id FROM stage4_game_context)
)
UNION ALL SELECT 'window_exceeds_eight','ERROR',count(*) FROM audited WHERE window_n>8 OR window_n<0
UNION ALL SELECT 'current_future_in_window','ERROR',count(*) FROM audited
WHERE window_last_date>=game_date OR window_first_date>=game_date
UNION ALL SELECT 'window_counts_mismatch','ERROR',count(*) FROM audited
WHERE window_n!=audit_n OR valid_prior_n!=audit_valid_n
UNION ALL SELECT 'window_dates_mismatch','ERROR',count(*) FROM audited
WHERE window_first_date IS DISTINCT FROM first_date OR window_last_date IS DISTINCT FROM last_date
UNION ALL SELECT 'baseline_mean_mismatch','ERROR',count(*) FROM audited
WHERE (prior_mean IS NULL)!=(audit_mean IS NULL) OR abs(prior_mean-audit_mean)>1e-9
UNION ALL SELECT 'metric_eligibility_mismatch','ERROR',count(*) FROM audited
WHERE baseline_available IS DISTINCT FROM
    (audit_n>=4 AND audit_valid_n>=4 AND (metric_family='efficiency' OR audit_n=audit_valid_n))
UNION ALL SELECT 'expected_or_residual_mismatch','ERROR',count(*) FROM audited
WHERE (expected IS NULL)!=NOT baseline_available
   OR abs(expected-prior_mean)>1e-9
   OR (residual IS NULL)!=(actual IS NULL OR expected IS NULL)
   OR abs(residual-(actual-expected))>1e-9
UNION ALL SELECT 'nonfinite_metrics','ERROR',count(*) FROM stage4_metric_features
WHERE NOT isfinite(actual) OR NOT isfinite(expected) OR NOT isfinite(residual)
UNION ALL SELECT 'invalid_denominator_has_ratio','ERROR',count(*) FROM stage4_metric_features
WHERE metric_family='efficiency' AND (denominator IS NULL OR denominator<=0) AND actual IS NOT NULL
UNION ALL SELECT 'position_opportunity_formula','ERROR',count(*) FROM stage4_game_context
WHERE opportunities IS DISTINCT FROM CASE WHEN position='QB' THEN attempts+carries ELSE carries+targets END
   OR opportunity_tds IS DISTINCT FROM CASE WHEN position='QB' THEN passing_tds+rushing_tds ELSE rushing_tds+receiving_tds END
UNION ALL SELECT 'negative_usage_denominators','ERROR',count(*) FROM stage4_game_context
WHERE attempts<0 OR carries<0 OR targets<0 OR receptions<0
UNION ALL SELECT 'paired_players_missing_group','ERROR',count(*) FROM stage4_player_comparisons
WHERE revenge_n<1 OR non_revenge_n<1 OR mean_difference IS NULL
UNION ALL SELECT 'cohort_differs_from_validated_snapshot','ERROR',count(*) FROM (
    (SELECT player_id,game_id FROM stage3_analysis_games EXCEPT ALL SELECT player_id,game_id FROM stage4_analysis_games)
    UNION ALL
    (SELECT player_id,game_id FROM stage4_analysis_games EXCEPT ALL SELECT player_id,game_id FROM stage3_analysis_games)
)
UNION ALL SELECT 'analysis_not_shared_features','ERROR',count(*) FROM stage4_analysis_metrics a
JOIN stage4_metric_features f USING(player_id,game_id,metric)
WHERE a.actual IS DISTINCT FROM f.actual OR a.expected IS DISTINCT FROM f.expected
   OR a.residual IS DISTINCT FROM f.residual OR NOT f.position_applicable
UNION ALL SELECT 'group_label_mismatch','ERROR',count(*) FROM stage4_analysis_metrics
WHERE game_group IS DISTINCT FROM CASE WHEN is_revenge_game THEN 'revenge' ELSE 'non_revenge' END
UNION ALL SELECT 'departure_not_strictly_positive','ERROR',count(*) FROM stage4_analysis_games
WHERE is_revenge_game AND (days_since_former_team IS NULL OR days_since_former_team<=0)
UNION ALL SELECT 'winsorized_changed_row_count','ERROR',abs(
    (SELECT count(*) FROM stage4_sensitivity_games WHERE variant='winsorized_1_99')
    -(SELECT count(*) FROM stage4_analysis_games))
UNION ALL SELECT 'raw_sensitivity_changed_values','ERROR',count(*) FROM stage4_sensitivity_games
WHERE variant='raw' AND analysis_residual IS DISTINCT FROM performance_residual
UNION ALL SELECT 'outlier_transform_invalid','ERROR',count(*) FROM stage4_sensitivity_games,stage4_outlier_cutoffs
WHERE (variant='trimmed_1_99' AND (analysis_residual<p01 OR analysis_residual>p99
       OR analysis_residual IS DISTINCT FROM performance_residual))
   OR (variant='winsorized_1_99' AND analysis_residual IS DISTINCT FROM greatest(p01,least(p99,performance_residual)));
