-- Stage 2 uses only Stage 1's regular-season QB/RB/WR/TE records.
-- This full-window summary is descriptive. NEVER join its total into a past label.
CREATE OR REPLACE VIEW player_team_history AS
SELECT player_id, team,
       min(game_date) AS first_observed_game_date,
       max(game_date) AS last_observed_game_date,
       count(*) AS observed_games,
       count(DISTINCT season) AS observed_seasons,
       list(DISTINCT season ORDER BY season) AS seasons
FROM clean_player_game_stats
GROUP BY player_id, team;

-- One row per current player-game and team with at least one EARLIER appearance.
-- Future-only teams are absent. A missing team row means zero earlier appearances.
-- Date comparison handles season boundaries and excludes the current/same-day game.
CREATE OR REPLACE VIEW player_team_history_asof AS
SELECT current_game.player_id, current_game.game_id, current_game.game_date,
       earlier.team AS history_team,
       count(*) AS prior_appearances,
       min(earlier.game_date) AS first_prior_game_date,
       max(earlier.game_date) AS last_prior_game_date
FROM clean_player_game_stats current_game
JOIN clean_player_game_stats earlier
  ON earlier.player_id = current_game.player_id
 AND earlier.game_date < current_game.game_date
GROUP BY current_game.player_id, current_game.game_id, current_game.game_date, earlier.team;

-- Keep non-revenge games too, so exclusions can be inspected.
CREATE OR REPLACE VIEW player_game_revenge_flags AS
WITH opponent_history AS (
    SELECT p.*,
           coalesce(h.prior_appearances, 0) AS prior_opponent_appearances,
           h.first_prior_game_date AS first_prior_opponent_game_date,
           h.last_prior_game_date AS last_prior_opponent_game_date,
           coalesce(h.prior_appearances, 0) >= 4 AS is_revenge_game
    FROM clean_player_game_stats p
    LEFT JOIN player_team_history_asof h
      ON p.player_id = h.player_id AND p.game_id = h.game_id
     AND p.opponent_team = h.history_team
), meetings AS (
    SELECT *,
           count(*) FILTER (WHERE is_revenge_game) OVER (
               PARTITION BY player_id, opponent_team
               ORDER BY game_date
               RANGE BETWEEN UNBOUNDED PRECEDING AND INTERVAL '1 day' PRECEDING
           ) AS prior_qualifying_meetings
    FROM opponent_history
)
SELECT *, is_revenge_game AND prior_qualifying_meetings = 0
          AS is_first_meeting_with_former_team
FROM meetings;

-- Stage 2 identification only: no expected performance, baseline, or uplift.
CREATE OR REPLACE VIEW fact_revenge_games AS
SELECT * FROM player_game_revenge_flags WHERE is_revenge_game;
