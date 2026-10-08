"""Temporal edge cases use clearly synthetic rows in memory, never the real database."""
from pathlib import Path
import unittest

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / 'sql' / '04_team_history.sql').read_text()


class Stage2Tests(unittest.TestCase):
    def setUp(self):
        self.c = duckdb.connect()
        self.c.execute('''CREATE TABLE clean_player_game_stats (
            player_id VARCHAR, player_display_name VARCHAR, game_id VARCHAR,
            game_date DATE, season INTEGER, team VARCHAR, opponent_team VARCHAR)''')

    def tearDown(self):
        self.c.close()

    def add(self, day, team, opponent, player='test-player', name='Test Player', game=None):
        self.c.execute('INSERT INTO clean_player_game_stats VALUES (?, ?, ?, ?, 2020, ?, ?)',
                       [player, name, game or f'test-{player}-{day}', f'2020-01-{day:02d}', team, opponent])

    def flags(self, day):
        return self.c.execute('''SELECT prior_opponent_appearances, is_revenge_game,
            prior_qualifying_meetings, is_first_meeting_with_former_team
            FROM player_game_revenge_flags WHERE game_date=? AND player_id='test-player' ''',
            [f'2020-01-{day:02d}']).fetchone()

    def test_threshold_return_stints_and_future_history(self):
        self.add(1, 'BUF', 'NE')  # Facing NE before any NE tenure is not a reunion.
        for day in (2, 3, 4):
            self.add(day, 'NE', 'NYJ')
        self.add(5, 'BUF', 'NE')  # Only three prior appearances.
        self.add(6, 'NE', 'NYJ')  # Fourth appearance cannot retroactively change day 5.
        self.add(7, 'BUF', 'NE')
        self.add(8, 'BUF', 'NE')
        self.add(9, 'NE', 'NYJ')  # Return to former team does not reset the flag.
        self.add(10, 'MIA', 'NE')
        self.c.execute(SQL)
        self.assertEqual(self.flags(1), (0, False, 0, False))
        self.assertEqual(self.flags(5), (3, False, 0, False))
        self.assertEqual(self.flags(7), (4, True, 0, True))
        self.assertEqual(self.flags(8), (4, True, 1, False))
        self.assertEqual(self.flags(10), (5, True, 2, False))
        self.assertEqual(self.c.sql("SELECT count(*) FROM player_team_history_asof WHERE game_id='test-test-player-1'").fetchone()[0], 0)

    def test_same_day_appearance_does_not_count(self):
        for day in (1, 2, 3):
            self.add(day, 'NE', 'NYJ')
        self.add(4, 'NE', 'NYJ', game='test-same-day-prior')
        self.add(4, 'BUF', 'NE', game='test-same-day-current')
        self.c.execute(SQL)
        self.assertEqual(self.c.sql("SELECT prior_opponent_appearances,is_revenge_game FROM player_game_revenge_flags WHERE game_id='test-same-day-current'").fetchone(), (3, False))

    def test_stable_ids_survive_name_changes_and_name_collisions(self):
        for day in (1, 2, 3, 4):
            self.add(day, 'NE', 'NYJ', name='Shared Name')
        self.add(5, 'BUF', 'NE', name='Changed Name')
        self.add(5, 'MIA', 'NE', player='different-id', name='Shared Name')
        self.c.execute(SQL)
        self.assertEqual(self.flags(5), (4, True, 0, True))
        self.assertEqual(self.c.sql("SELECT prior_opponent_appearances,is_revenge_game FROM player_game_revenge_flags WHERE player_id='different-id'").fetchone(), (0, False))

    def test_real_data_labels_unchanged_when_future_records_removed(self):
        # Read the actual data; all copies/deletions below exist only in memory.
        with duckdb.connect(str(ROOT / 'data/processed/nfl.duckdb'), read_only=True) as source:
            rows = source.execute('''SELECT player_id,player_display_name,game_id,
                game_date,season,team,opponent_team FROM clean_player_game_stats''').fetchall()
        self.c.executemany('INSERT INTO clean_player_game_stats VALUES (?,?,?,?,?,?,?)', rows)
        self.c.execute(SQL)
        self.c.execute('CREATE TABLE full_flags AS SELECT * FROM player_game_revenge_flags')
        self.c.execute('CREATE TABLE full_asof AS SELECT * FROM player_team_history_asof')
        self.c.execute('CREATE TABLE full_source AS SELECT * FROM clean_player_game_stats')
        for cutoff in ('2018-10-31', '2022-11-01'):
            with self.subTest(cutoff=cutoff):
                self.c.execute('DELETE FROM clean_player_game_stats')
                self.c.execute('INSERT INTO clean_player_game_stats SELECT * FROM full_source WHERE game_date < ?', [cutoff])
                for actual, reference in (('player_game_revenge_flags','full_flags'),
                                          ('player_team_history_asof','full_asof')):
                    differences = self.c.execute(f'''
                        SELECT count(*) FROM (
                            (SELECT * FROM {actual} EXCEPT ALL
                             SELECT * FROM {reference} WHERE game_date < ?)
                            UNION ALL
                            (SELECT * FROM {reference} WHERE game_date < ? EXCEPT ALL
                             SELECT * FROM {actual})
                        )
                    ''', [cutoff, cutoff]).fetchone()[0]
                    self.assertEqual(differences, 0, actual)


if __name__ == '__main__':
    unittest.main()
