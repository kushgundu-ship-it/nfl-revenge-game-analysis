-- Stage 5 is a READ-ONLY presentation layer. Named queries are selected by data.py.
-- No labels, eligibility, baselines, residuals, or inferential statistics are rebuilt.

-- name: scope
SELECT min(season) AS first_season,max(season) AS last_season,count(*) AS cleaned_games
FROM clean_player_game_stats;

-- name: counts
SELECT game_group,count(*) AS games,count(DISTINCT player_id) AS players
FROM stage4_analysis_games GROUP BY game_group ORDER BY game_group;

-- name: histogram
-- Binning/normalization is display-only: every residual enters a 2-PPR-wide bin.
SELECT game_group,floor(performance_residual/2)*2 AS bin_start,
       floor(performance_residual/2)*2+2 AS bin_end,count(*) AS games,
       100.0*count(*)/sum(count(*)) OVER(PARTITION BY game_group) AS percentage
FROM stage4_analysis_games WHERE (?='All positions' OR position=?)
GROUP BY game_group,bin_start,bin_end ORDER BY game_group,bin_start;

-- name: players
SELECT p.player_id,p.player_display_name,p.revenge_n,p.non_revenge_n,
       string_agg(DISTINCT a.position,', ' ORDER BY a.position) AS positions
FROM stage4_player_comparisons p JOIN stage4_analysis_games a USING(player_id)
GROUP BY p.player_id,p.player_display_name,p.revenge_n,p.non_revenge_n
ORDER BY p.player_display_name,p.player_id;

-- name: player_games
SELECT player_id,player_display_name,game_id,game_date,position,season,team,
       opponent_team AS former_team,is_first_meeting_with_former_team AS first_meeting,
       actual_ppr_points,expected_ppr_points,performance_residual,revenge_score,
       revenge_score_unavailable_reason,prior_game_count
FROM stage4_analysis_games WHERE player_id=? AND is_revenge_game
ORDER BY game_date,game_id;

-- name: baseline
SELECT player_id,game_id,prior_game_id,prior_game_date,prior_team,prior_opponent_team,
       prior_ppr_points,appearances_back
FROM player_game_baseline_support WHERE player_id=? AND game_id=?
ORDER BY prior_game_date,prior_game_id;

-- name: examples
-- These are bookmarks to inspected games, not embedded analytical values.
WITH selected(player_id,game_id) AS (VALUES
    ('00-0019596','2021_04_TB_NE'),('00-0026498','2021_07_DET_LA'),
    ('00-0031381','2023_05_GB_LV'),('00-0036407','2024_13_CLE_DEN'))
SELECT a.player_id,a.player_display_name,a.game_id,a.game_date,a.team,
       a.opponent_team AS former_team,a.actual_ppr_points,a.expected_ppr_points,
       a.performance_residual
FROM stage4_analysis_games a JOIN selected s USING(player_id,game_id)
ORDER BY a.game_date,a.player_id;
