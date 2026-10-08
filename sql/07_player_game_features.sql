-- Stage 3: all eligible player-games, BEFORE any revenge/cohort filtering.
-- Stage 2 validation rejects duplicate player dates; game_id is a stable tie-breaker.
-- Do not partition by season or team: appearances carry across gaps and transfers.
CREATE OR REPLACE VIEW player_game_appearance_order AS
SELECT *, row_number() OVER (
    PARTITION BY player_id ORDER BY game_date, game_id
) AS appearance_number
FROM player_game_revenge_flags;

CREATE OR REPLACE VIEW player_game_features AS
WITH rolling AS (
    SELECT *,
           fantasy_points_ppr AS actual_ppr_points,
           count(*) OVER previous_eight AS prior_game_count,
           count(fantasy_points_ppr) OVER previous_eight AS prior_ppr_count,
           avg(fantasy_points_ppr) OVER previous_eight AS expected_ppr_points,
           stddev_samp(fantasy_points_ppr) OVER previous_eight AS rolling_ppr_stddev,
           min(game_date) OVER previous_eight AS baseline_first_game_date,
           max(game_date) OVER previous_eight AS baseline_last_game_date
    FROM player_game_appearance_order
    WINDOW previous_eight AS (
        PARTITION BY player_id ORDER BY game_date, game_id
        ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    )
), eligibility AS (
    SELECT *,
           prior_game_count >= 4 AND prior_ppr_count = prior_game_count
               AND actual_ppr_points IS NOT NULL AS is_effect_eligible,
           CASE WHEN rolling_ppr_stddev IS NULL THEN 'missing'
                WHEN rolling_ppr_stddev = 0 THEN 'zero'
                ELSE 'positive' END AS rolling_stddev_status
    FROM rolling
), residuals AS (
    SELECT *,
           CASE WHEN is_effect_eligible THEN actual_ppr_points - expected_ppr_points
                END AS performance_residual,
           CASE WHEN prior_game_count < 4 THEN 'insufficient_prior_appearances'
                WHEN prior_ppr_count != prior_game_count THEN 'missing_prior_ppr'
                WHEN actual_ppr_points IS NULL THEN 'missing_actual_ppr'
                WHEN rolling_ppr_stddev IS NULL THEN 'missing_rolling_stddev'
                WHEN rolling_ppr_stddev = 0 THEN 'zero_rolling_stddev'
                ELSE NULL END AS revenge_score_unavailable_reason
    FROM eligibility
)
SELECT *,
       -- Same residual formula for both groups; the neutral alias is used in summaries.
       performance_residual AS revenge_uplift,
       CASE WHEN revenge_score_unavailable_reason IS NULL
            THEN performance_residual / nullif(rolling_ppr_stddev, 0)
            END AS revenge_score
FROM residuals;

-- Auditable membership of the actual row-based rolling window; one row per contributor.
CREATE OR REPLACE VIEW player_game_baseline_support AS
SELECT p.player_id, p.game_id, p.game_date,
       h.game_id AS prior_game_id, h.game_date AS prior_game_date,
       h.season AS prior_season, h.week AS prior_week,
       h.team AS prior_team, h.opponent_team AS prior_opponent_team,
       h.fantasy_points_ppr AS prior_ppr_points,
       p.appearance_number - h.appearance_number AS appearances_back
FROM player_game_appearance_order p
JOIN player_game_appearance_order h
  ON p.player_id=h.player_id
 AND h.appearance_number BETWEEN p.appearance_number-8 AND p.appearance_number-1;

-- Preserve Stage 2 fact_revenge_games. These are new analysis-ready views.
CREATE OR REPLACE VIEW analysis_revenge_games AS
SELECT * FROM player_game_features WHERE is_effect_eligible AND is_revenge_game;

-- Retrospective cohort: players with at least one eligible revenge game anywhere
-- in this snapshot. Cohort membership NEVER enters the rolling feature calculation.
CREATE OR REPLACE VIEW stage3_comparison_cohort AS
SELECT DISTINCT player_id FROM analysis_revenge_games;

CREATE OR REPLACE VIEW analysis_comparison_games AS
SELECT f.* FROM player_game_features f
WHERE f.is_effect_eligible AND NOT f.is_revenge_game
  AND EXISTS (SELECT 1 FROM stage3_comparison_cohort c WHERE c.player_id=f.player_id);

CREATE OR REPLACE VIEW stage3_analysis_games AS
SELECT *, 'revenge' AS game_group FROM analysis_revenge_games
UNION ALL
SELECT *, 'non_revenge' AS game_group FROM analysis_comparison_games;
