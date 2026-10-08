-- Additive Stage 4 views. No Stage 1–3 object is replaced.
-- Keep all appearances until AFTER the rolling windows are calculated.
CREATE OR REPLACE VIEW stage4_game_context AS
SELECT f.*, team=home_team AS is_home,
       CASE WHEN is_revenge_game THEN date_diff('day',last_prior_opponent_game_date,game_date)
            END AS days_since_former_team,
       CASE WHEN NOT is_revenge_game THEN NULL
            WHEN days_since_former_team<=365 THEN '01_0_to_365_days'
            WHEN days_since_former_team<=730 THEN '02_366_to_730_days'
            WHEN days_since_former_team<=1460 THEN '03_731_to_1460_days'
            ELSE '04_1461_plus_days' END AS departure_bucket,
       CASE WHEN position='QB' THEN attempts+carries ELSE carries+targets END AS opportunities,
       CASE WHEN position='QB' THEN passing_tds+rushing_tds
            ELSE rushing_tds+receiving_tds END AS opportunity_tds
FROM player_game_features f;

-- Long format keeps exactly the same metric definitions for both game groups.
-- Receptions are a separate metric, never added to opportunities.
CREATE OR REPLACE VIEW stage4_metric_actuals AS
SELECT g.player_id,g.game_id,g.game_date,g.position,m.*
FROM stage4_game_context g,
LATERAL (VALUES
    ('pass_attempts','usage',CAST(attempts AS DOUBLE),NULL::DOUBLE,position='QB'),
    ('carries','usage',CAST(carries AS DOUBLE),NULL::DOUBLE,true),
    ('targets','usage',CAST(targets AS DOUBLE),NULL::DOUBLE,position!='QB'),
    ('receptions','usage',CAST(receptions AS DOUBLE),NULL::DOUBLE,true),
    ('opportunities','usage',CAST(opportunities AS DOUBLE),NULL::DOUBLE,true),
    ('passing_yards_per_attempt','efficiency',
        CASE WHEN attempts>0 THEN passing_yards*1.0/nullif(attempts,0) END,attempts,position='QB'),
    ('rushing_yards_per_carry','efficiency',
        CASE WHEN carries>0 THEN rushing_yards*1.0/nullif(carries,0) END,carries,true),
    ('receiving_yards_per_target','efficiency',
        CASE WHEN targets>0 THEN receiving_yards*1.0/nullif(targets,0) END,targets,position!='QB'),
    ('touchdowns_per_opportunity','efficiency',
        CASE WHEN opportunities>0 THEN opportunity_tds*1.0/nullif(opportunities,0) END,opportunities,true)
) m(metric,metric_family,actual,denominator,position_applicable);

CREATE OR REPLACE VIEW stage4_metric_features AS
WITH rolling AS (
    SELECT *,count(*) OVER w AS window_n,count(actual) OVER w AS valid_prior_n,
           avg(actual) OVER w AS prior_mean,
           min(game_date) OVER w AS window_first_date,max(game_date) OVER w AS window_last_date
    FROM stage4_metric_actuals
    WINDOW w AS (PARTITION BY player_id,metric ORDER BY game_date,game_id
                 ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING)
), eligible AS (
    SELECT *,window_n>=4 AND valid_prior_n>=4
        AND (metric_family='efficiency' OR valid_prior_n=window_n) AS baseline_available
    FROM rolling
)
SELECT *,CASE WHEN baseline_available THEN prior_mean END AS expected,
       CASE WHEN baseline_available THEN actual-prior_mean END AS residual
FROM eligible;

-- Explicitly require both groups per player; report any exclusions in validation.
CREATE OR REPLACE VIEW stage4_paired_players AS
SELECT player_id FROM stage3_analysis_games GROUP BY player_id
HAVING count(*) FILTER(WHERE is_revenge_game)>0
   AND count(*) FILTER(WHERE NOT is_revenge_game)>0;

CREATE OR REPLACE VIEW stage4_analysis_games AS
SELECT g.*,CASE WHEN is_revenge_game THEN 'revenge' ELSE 'non_revenge' END AS game_group
FROM stage4_game_context g JOIN stage4_paired_players p USING(player_id)
WHERE is_effect_eligible;

CREATE OR REPLACE VIEW stage4_analysis_metrics AS
SELECT a.game_group,a.is_revenge_game,m.*
FROM stage4_analysis_games a JOIN stage4_metric_features m USING(player_id,game_id)
WHERE m.position_applicable;

CREATE OR REPLACE VIEW stage4_player_comparisons AS
SELECT player_id,max(player_display_name) AS player_display_name,
       count(*) FILTER(WHERE is_revenge_game) AS revenge_n,
       count(*) FILTER(WHERE NOT is_revenge_game) AS non_revenge_n,
       avg(performance_residual) FILTER(WHERE is_revenge_game) AS revenge_mean,
       avg(performance_residual) FILTER(WHERE NOT is_revenge_game) AS non_revenge_mean,
       revenge_mean-non_revenge_mean AS mean_difference,
       median(performance_residual) FILTER(WHERE is_revenge_game) AS revenge_median,
       median(performance_residual) FILTER(WHERE NOT is_revenge_game) AS non_revenge_median,
       revenge_median-non_revenge_median AS median_difference,
       100.0*avg(CAST(performance_residual>1e-9 AS INTEGER)) FILTER(WHERE is_revenge_game) AS revenge_pct,
       100.0*avg(CAST(performance_residual>1e-9 AS INTEGER)) FILTER(WHERE NOT is_revenge_game) AS non_revenge_pct,
       revenge_pct-non_revenge_pct AS pct_difference
FROM stage4_analysis_games GROUP BY player_id;
