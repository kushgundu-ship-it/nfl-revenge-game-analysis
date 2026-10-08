-- Read-only SQL outputs; inference CSVs are produced by scripts/analyze_stage4.py.
SELECT * FROM stage4_segments ORDER BY breakdown,segment,game_group;
SELECT * FROM stage4_usage_efficiency_differences ORDER BY position,metric_family,metric;
SELECT * FROM stage4_outlier_cutoffs;
SELECT * FROM stage4_sensitivity_results ORDER BY variant;
SELECT * FROM stage4_extreme_revenge ORDER BY performance_residual DESC;
SELECT * FROM stage4_validation_checks ORDER BY check_name;
