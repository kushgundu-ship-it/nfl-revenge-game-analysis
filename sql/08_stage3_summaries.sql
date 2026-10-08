-- Every summary weights player-game rows equally, NOT each player equally.
-- Exceeded means positive residual beyond 1e-9 PPR numerical tolerance.
-- This prevents floating-point roundoff from counting mathematical ties as wins.
-- Ties count in N but not as exceeded; the underlying residual stays unrounded.
-- Undefined standardized scores do not remove otherwise valid residuals.
CREATE OR REPLACE VIEW stage3_summary AS
WITH segments AS (
    SELECT 'overall' AS breakdown, 'ALL' AS segment, * FROM stage3_analysis_games
    UNION ALL
    SELECT 'position', position, * FROM stage3_analysis_games
    UNION ALL
    SELECT 'meeting', CASE WHEN is_first_meeting_with_former_team THEN 'first' ELSE 'later' END,
           * FROM stage3_analysis_games WHERE is_revenge_game
)
SELECT breakdown, segment, game_group,
       count(*) AS sample_size,
       count(DISTINCT player_id) AS player_count,
       100.0 * count(*) FILTER(WHERE performance_residual > 1e-9) / count(*) AS pct_exceeded_baseline,
       avg(actual_ppr_points) AS mean_actual_ppr,
       avg(expected_ppr_points) AS mean_expected_ppr,
       avg(performance_residual) AS mean_residual,
       median(performance_residual) AS median_residual,
       count(revenge_score) AS standardized_score_count
FROM segments GROUP BY breakdown, segment, game_group;
