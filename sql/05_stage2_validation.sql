-- Independent date-bounded counts check the output, including negative labels.
CREATE OR REPLACE VIEW stage2_validation_checks AS
WITH expected_opponent AS MATERIALIZED (
    SELECT p.player_id, p.game_id,
           (SELECT count(*) FROM clean_player_game_stats h
            WHERE h.player_id=p.player_id AND h.team=p.opponent_team
              AND h.game_date < p.game_date) AS expected_count
    FROM clean_player_game_stats p
), expected_meetings AS MATERIALIZED (
    SELECT p.player_id, p.game_id,
           (SELECT count(*) FROM clean_player_game_stats previous
            JOIN expected_opponent e USING (player_id, game_id)
            WHERE previous.player_id=p.player_id
              AND previous.opponent_team=p.opponent_team
              AND previous.game_date < p.game_date AND e.expected_count >= 4
           ) AS expected_prior_meetings
    FROM clean_player_game_stats p
), expected_history_keys AS (
    SELECT DISTINCT p.player_id, p.game_id, h.team AS history_team
    FROM clean_player_game_stats p JOIN clean_player_game_stats h
      ON p.player_id=h.player_id AND h.game_date<p.game_date
)
SELECT 'source_missing_dates_or_ids' AS check_name, 'ERROR' AS severity, count(*) AS problem_count
FROM clean_player_game_stats
WHERE game_date IS NULL OR player_id IS NULL OR game_id IS NULL
UNION ALL
SELECT 'source_multiple_games_same_player_date', 'ERROR', count(*) FROM (
    SELECT player_id, game_date FROM clean_player_game_stats GROUP BY ALL HAVING count(*)>1
)
UNION ALL
SELECT 'history_duplicate_player_team', 'ERROR', count(*) FROM (
    SELECT player_id, team FROM player_team_history GROUP BY ALL HAVING count(*)>1
)
UNION ALL
SELECT 'history_summary_count_mismatch', 'ERROR', count(*) FROM player_team_history t
WHERE observed_games != (SELECT count(*) FROM clean_player_game_stats p
                         WHERE p.player_id=t.player_id AND p.team=t.team)
UNION ALL
SELECT 'asof_duplicate_keys', 'ERROR', count(*) FROM (
    SELECT player_id, game_id, history_team FROM player_team_history_asof
    GROUP BY ALL HAVING count(*)>1
)
UNION ALL
SELECT 'asof_missing_or_extra_keys', 'ERROR', count(*) FROM (
    (SELECT * FROM expected_history_keys EXCEPT ALL
     SELECT player_id, game_id, history_team FROM player_team_history_asof)
    UNION ALL
    (SELECT player_id, game_id, history_team FROM player_team_history_asof EXCEPT ALL
     SELECT * FROM expected_history_keys)
)
UNION ALL
SELECT 'asof_count_mismatch', 'ERROR', count(*) FROM player_team_history_asof a
WHERE a.prior_appearances != (
    SELECT count(*) FROM clean_player_game_stats h WHERE h.player_id=a.player_id
      AND h.team=a.history_team AND h.game_date<a.game_date
)
UNION ALL
SELECT 'asof_current_or_future_date', 'ERROR', count(*) FROM player_team_history_asof
WHERE prior_appearances < 1 OR first_prior_game_date IS NULL OR last_prior_game_date IS NULL
   OR first_prior_game_date > last_prior_game_date OR last_prior_game_date >= game_date
UNION ALL
SELECT 'flags_missing_or_extra_player_games', 'ERROR', count(*) FROM (
    (SELECT player_id,game_id FROM clean_player_game_stats EXCEPT ALL
     SELECT player_id,game_id FROM player_game_revenge_flags)
    UNION ALL
    (SELECT player_id,game_id FROM player_game_revenge_flags EXCEPT ALL
     SELECT player_id,game_id FROM clean_player_game_stats)
)
UNION ALL
SELECT 'flags_duplicate_player_games', 'ERROR', count(*) FROM (
    SELECT player_id,game_id FROM player_game_revenge_flags GROUP BY ALL HAVING count(*)>1
)
UNION ALL
SELECT 'opponent_prior_count_mismatch', 'ERROR', count(*)
FROM player_game_revenge_flags f JOIN expected_opponent e USING(player_id,game_id)
WHERE prior_opponent_appearances IS DISTINCT FROM expected_count
UNION ALL
SELECT 'revenge_label_mismatch', 'ERROR', count(*)
FROM player_game_revenge_flags f JOIN expected_opponent e USING(player_id,game_id)
WHERE is_revenge_game IS DISTINCT FROM (expected_count >= 4)
UNION ALL
SELECT 'revenge_duplicate_player_games', 'ERROR', count(*) FROM (
    SELECT player_id,game_id FROM fact_revenge_games GROUP BY ALL HAVING count(*)>1
)
UNION ALL
SELECT 'revenge_below_four_earlier_games', 'ERROR', count(*) FROM fact_revenge_games
WHERE prior_opponent_appearances IS NULL OR prior_opponent_appearances < 4
UNION ALL
SELECT 'revenge_current_or_future_date', 'ERROR', count(*) FROM fact_revenge_games
WHERE last_prior_opponent_game_date IS NULL OR last_prior_opponent_game_date >= game_date
UNION ALL
SELECT 'revenge_missing_or_extra_games', 'ERROR', count(*) FROM (
    (SELECT player_id,game_id FROM expected_opponent WHERE expected_count>=4 EXCEPT ALL
     SELECT player_id,game_id FROM fact_revenge_games)
    UNION ALL
    (SELECT player_id,game_id FROM fact_revenge_games EXCEPT ALL
     SELECT player_id,game_id FROM expected_opponent WHERE expected_count>=4)
)
UNION ALL
SELECT 'prior_meeting_count_mismatch', 'ERROR', count(*)
FROM player_game_revenge_flags f JOIN expected_meetings e USING(player_id,game_id)
WHERE prior_qualifying_meetings IS DISTINCT FROM expected_prior_meetings
UNION ALL
SELECT 'first_meeting_flag_mismatch', 'ERROR', count(*)
FROM player_game_revenge_flags f JOIN expected_meetings m USING(player_id,game_id)
JOIN expected_opponent e USING(player_id,game_id)
WHERE is_first_meeting_with_former_team IS DISTINCT FROM
      (e.expected_count>=4 AND m.expected_prior_meetings=0)
UNION ALL
SELECT 'not_exactly_one_first_meeting_per_relationship', 'ERROR', count(*) FROM (
    SELECT player_id,opponent_team FROM fact_revenge_games GROUP BY ALL
    HAVING count(*) FILTER(WHERE is_first_meeting_with_former_team) != 1
);

CREATE OR REPLACE VIEW stage2_season_counts AS
SELECT season, count(*) AS player_games,
       count(*) FILTER(WHERE is_revenge_game) AS revenge_games,
       count(*) FILTER(WHERE is_first_meeting_with_former_team) AS first_meetings
FROM player_game_revenge_flags GROUP BY season;
