-- Read-only queries to explore the finished ingestion stage.
SELECT * FROM season_row_counts ORDER BY season;
SELECT * FROM validation_checks ORDER BY severity, check_name;
SELECT player_id, player_display_name, position, season, week, game_id,
       team, opponent_team, game_date, round(fantasy_points_ppr, 2) AS ppr
FROM clean_player_game_stats
WHERE season=2025 AND week=1 AND position='QB'
ORDER BY player_display_name LIMIT 5;
