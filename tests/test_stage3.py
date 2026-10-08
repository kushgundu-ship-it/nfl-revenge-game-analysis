"""Synthetic boundaries and independent real-data arithmetic, all read-only/in memory."""
from datetime import date, timedelta
import math
from pathlib import Path
import unittest

import duckdb

ROOT = Path(__file__).resolve().parents[1]
FEATURES_SQL = (ROOT / 'sql/07_player_game_features.sql').read_text()
SUMMARY_SQL = (ROOT / 'sql/08_stage3_summaries.sql').read_text()
CHECKS_SQL = (ROOT / 'sql/09_stage3_validation.sql').read_text()
SOURCE_COLUMNS = '''player_id,player_display_name,game_id,game_date,season,week,
    position,team,opponent_team,fantasy_points_ppr,is_revenge_game,
    is_first_meeting_with_former_team,prior_opponent_appearances'''

# These game IDs and values were inspected directly in the saved Stage 1 snapshot.
# Oldest to newest, not fabricated examples. The synthetic tests below are separate.
REAL_EXAMPLES = [
    ('00-0019596', '2021_04_TB_NE', 11.06,
     ['2020_12_KC_TB','2020_14_MIN_TB','2020_15_TB_ATL','2020_16_TB_DET',
      '2020_17_ATL_TB','2021_01_DAL_TB','2021_02_ATL_TB','2021_03_TB_LA'],
     [21.70,15.64,23.40,29.92,30.26,27.16,29.64,28.68]),
    ('00-0026498', '2021_07_DET_LA', 27.16,
     ['2020_16_TB_DET','2020_17_MIN_DET','2021_01_CHI_LA','2021_02_LA_IND',
      '2021_03_TB_LA','2021_04_ARI_LA','2021_05_LA_SEA','2021_06_LA_NYG'],
     [0.68,22.62,24.34,17.22,29.52,19.30,16.50,25.24]),
    ('00-0031381', '2023_05_GB_LV', 8.50,
     ['2022_15_NE_LV','2022_16_LV_PIT','2022_17_SF_LV','2022_18_KC_LV',
      '2023_01_LV_DEN','2023_02_LV_BUF','2023_03_PIT_LV','2023_04_LV_LAC'],
     [6.80,3.50,34.30,12.30,12.60,20.40,42.20,15.50]),
    ('00-0025394', '2018_05_WAS_NO', 6.20,
     ['2017_07_ARI_LA','2017_09_ARI_SF','2017_10_SEA_ARI','2017_11_ARI_HOU',
      '2017_12_JAX_ARI','2018_01_WAS_ARI','2018_02_IND_WAS','2018_03_GB_WAS'],
     [4.30,16.70,3.20,4.90,13.90,22.60,8.00,24.00]),
]


class Stage3Tests(unittest.TestCase):
    def setUp(self):
        self.c = duckdb.connect()
        self.c.execute('''CREATE TABLE player_game_revenge_flags (
            player_id VARCHAR,player_display_name VARCHAR,game_id VARCHAR,game_date DATE,
            season INTEGER,week INTEGER,position VARCHAR,team VARCHAR,opponent_team VARCHAR,
            fantasy_points_ppr DOUBLE,is_revenge_game BOOLEAN,
            is_first_meeting_with_former_team BOOLEAN,prior_opponent_appearances BIGINT)''')
        self.c.execute('CREATE VIEW clean_player_game_stats AS SELECT * FROM player_game_revenge_flags')

    def tearDown(self):
        self.c.close()

    def add(self, number, ppr, player='synthetic-a', revenge=False, day=None, team='BUF'):
        game_day = day or date(2020, 1, 1) + timedelta(days=number*7)
        self.c.execute('INSERT INTO player_game_revenge_flags VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       [player,'Shared Test Name',f'{player}-{number}',game_day,game_day.year,
                        number,'QB',team,'NE',ppr,revenge,revenge,4 if revenge else 0])

    def build(self):
        self.c.execute(FEATURES_SQL)
        self.c.execute(SUMMARY_SQL)
        self.c.execute(CHECKS_SQL)

    def row(self, number, player='synthetic-a'):
        result = self.c.execute('SELECT * FROM player_game_features WHERE player_id=? AND game_id=?',
                                [player,f'{player}-{number}'])
        return dict(zip([x[0] for x in result.description],result.fetchone()))

    def assert_checks_pass(self):
        self.assertEqual(self.c.sql('SELECT check_name,problem_count FROM stage3_validation_checks WHERE problem_count>0').fetchall(), [])

    def test_zero_three_four_prior_and_sample_not_population_sd(self):
        for n,value in enumerate([1,2,3,4,10],1):
            self.add(n,value,revenge=(n==5))
        self.build()
        first = self.row(1)
        self.assertEqual(first['prior_game_count'],0)
        self.assertIsNone(first['expected_ppr_points'])
        self.assertIsNone(first['rolling_ppr_stddev'])
        for n in range(1,5):
            r=self.row(n)
            self.assertFalse(r['is_effect_eligible'])
            self.assertIsNone(r['revenge_uplift'])
            self.assertIsNone(r['revenge_score'])
            self.assertEqual(r['revenge_score_unavailable_reason'],'insufficient_prior_appearances')
        r=self.row(5)
        self.assertEqual(r['prior_game_count'],4)
        self.assertEqual(r['expected_ppr_points'],2.5)
        self.assertAlmostEqual(r['rolling_ppr_stddev'],math.sqrt(5/3))
        self.assertEqual(r['revenge_uplift'],7.5)
        self.assertAlmostEqual(r['revenge_score'],7.5/math.sqrt(5/3))
        self.assert_checks_pass()

    def test_eight_appearance_cap_gaps_seasons_and_team_changes(self):
        dates=[date(2019,10,1)+timedelta(days=i*14) for i in range(5)]
        dates += [date(2020,9,1)+timedelta(days=i*21) for i in range(5)]
        for n,(value,day) in enumerate(zip([1000,1,2,3,4,5,6,7,8,10000],dates),1):
            self.add(n,value,day=day,team='NE' if n<=5 else 'BUF',revenge=n==10)
        self.build()
        r=self.row(10)
        self.assertEqual(r['prior_game_count'],8)
        self.assertEqual(r['expected_ppr_points'],4.5)
        self.assertAlmostEqual(r['rolling_ppr_stddev'],math.sqrt(6))
        support=self.c.sql("SELECT prior_game_id FROM player_game_baseline_support WHERE game_id='synthetic-a-10' ORDER BY appearances_back DESC").fetchall()
        self.assertEqual(support,[(f'synthetic-a-{n}',) for n in range(2,10)])
        self.assert_checks_pass()

    def test_zero_and_missing_stddev_are_explicit(self):
        for n in range(1,7):
            self.add(n,5,revenge=n==6)
            self.add(n,None,player='missing-history',revenge=n==6)
        self.build()
        r=self.row(6)
        self.assertTrue(r['is_effect_eligible'])
        self.assertEqual(r['performance_residual'],0)
        self.assertEqual(r['rolling_ppr_stddev'],0)
        self.assertIsNone(r['revenge_score'])
        self.assertEqual(r['revenge_score_unavailable_reason'],'zero_rolling_stddev')
        missing=self.row(6,'missing-history')
        self.assertEqual(missing['prior_game_count'],5)
        self.assertFalse(missing['is_effect_eligible'])
        self.assertIsNone(missing['revenge_score'])
        self.assertEqual(missing['rolling_stddev_status'],'missing')
        self.assertEqual(missing['revenge_score_unavailable_reason'],'missing_prior_ppr')
        self.assertIsNone(self.row(2)['rolling_ppr_stddev'])
        self.assert_checks_pass()

    def test_current_future_and_other_players_cannot_change_baseline(self):
        for n in range(1,12):
            self.add(n,n,revenge=n==6)
            self.add(n,999,player='different-id',revenge=n==6)
        self.build()
        before=self.row(6)
        self.c.execute("UPDATE player_game_revenge_flags SET fantasy_points_ppr=1000000 WHERE player_id='synthetic-a' AND game_date >= ?",[before['game_date']])
        after=self.row(6)
        for key in ('prior_game_count','expected_ppr_points','rolling_ppr_stddev'):
            self.assertEqual(before[key],after[key],key)
        self.assertEqual(after['expected_ppr_points'],3)
        self.assertEqual(after['actual_ppr_points'],1000000)
        self.assert_checks_pass()

    def test_same_player_cohort_shared_rules_and_ties(self):
        for n in range(1,8):
            self.add(n,10,revenge=n==6)
            self.add(n,20,player='never-revenge')
        self.build()
        self.assertEqual(self.c.sql('SELECT game_id FROM analysis_comparison_games ORDER BY game_id').fetchall(),
                         [('synthetic-a-5',),('synthetic-a-7',)])
        self.assertEqual(self.c.sql('SELECT sample_size,pct_exceeded_baseline,mean_residual,median_residual FROM stage3_summary WHERE breakdown=\'overall\' ORDER BY game_group').fetchall(),
                         [(2,0,0,0),(1,0,0,0)])
        self.assert_checks_pass()
        # Decimal PPR values may produce microscopic roundoff around an exact tie.
        self.c.execute("UPDATE player_game_revenge_flags SET fantasy_points_ppr=0.1")
        self.assertEqual(self.c.sql("SELECT pct_exceeded_baseline FROM stage3_summary WHERE breakdown='overall'").fetchall(),[(0.0,),(0.0,)])
        self.assert_checks_pass()

    def test_validation_detects_current_and_future_contributors(self):
        for n in range(1,7):
            self.add(n,n,revenge=n==6)
        self.build()
        self.c.execute('CREATE TABLE saved_support AS SELECT * FROM player_game_baseline_support')
        self.c.execute('''CREATE OR REPLACE VIEW player_game_baseline_support AS
            SELECT * REPLACE(game_id AS prior_game_id, game_date + INTERVAL '1 day' AS prior_game_date)
            FROM saved_support''')
        failures=dict(self.c.sql('SELECT check_name,problem_count FROM stage3_validation_checks').fetchall())
        self.assertGreater(failures['current_game_in_baseline'],0)
        self.assertGreater(failures['same_day_or_future_game_in_baseline'],0)
        self.assertGreater(failures['window_not_exact_eight_most_recent'],0)

    def test_four_real_examples_independent_arithmetic(self):
        with duckdb.connect(str(ROOT / 'data/processed/nfl.duckdb'),read_only=True) as source:
            for pid,gid,actual,game_ids,values in REAL_EXAMPLES:
                with self.subTest(game=gid,player=pid):
                    day=source.execute('SELECT game_date FROM clean_player_game_stats WHERE player_id=? AND game_id=?',[pid,gid]).fetchone()[0]
                    prior=source.execute('''SELECT game_id,fantasy_points_ppr FROM clean_player_game_stats
                        WHERE player_id=? AND game_date<? ORDER BY game_date DESC,game_id DESC LIMIT 8''',[pid,day]).fetchall()[::-1]
                    self.assertEqual([x[0] for x in prior],game_ids)
                    for row,value in zip(prior,values):
                        self.assertAlmostEqual(row[1],value,places=9)
                    mean=sum(values)/8
                    sd=math.sqrt(sum((value-mean)**2 for value in values)/7)
                    expected=(8,actual,mean,sd,actual-mean,(actual-mean)/sd)
                    observed=source.execute('''SELECT prior_game_count,actual_ppr_points,expected_ppr_points,
                        rolling_ppr_stddev,revenge_uplift,revenge_score FROM analysis_revenge_games
                        WHERE player_id=? AND game_id=?''',[pid,gid]).fetchone()
                    self.assertIsNotNone(observed)
                    for value,target in zip(observed,expected):
                        self.assertAlmostEqual(value,target,places=9)

    def test_real_features_unchanged_when_future_records_removed(self):
        # Copy directly in SQL, avoiding a slow row-by-row Python import.
        db_path=str(ROOT / 'data/processed/nfl.duckdb').replace("'","''")
        self.c.execute(f"ATTACH '{db_path}' AS snapshot (READ_ONLY)")
        self.c.execute(f'INSERT INTO player_game_revenge_flags SELECT {SOURCE_COLUMNS} FROM snapshot.player_game_revenge_flags')
        self.c.execute('DETACH snapshot')
        self.build()
        self.c.execute('CREATE TABLE full_features AS SELECT * FROM player_game_features')
        self.c.execute('CREATE TABLE full_source AS SELECT * FROM player_game_revenge_flags')
        for cutoff in ('2018-10-31','2022-11-01'):
            with self.subTest(cutoff=cutoff):
                self.c.execute('DELETE FROM player_game_revenge_flags')
                self.c.execute('INSERT INTO player_game_revenge_flags SELECT * FROM full_source WHERE game_date<?',[cutoff])
                # Floating arithmetic is identical here because feature windows use
                # the same row ordering. Compare the whole feature row in both directions.
                changes=self.c.execute('''SELECT count(*) FROM (
                    (SELECT * FROM player_game_features EXCEPT ALL
                     SELECT * FROM full_features WHERE game_date<?)
                    UNION ALL
                    (SELECT * FROM full_features WHERE game_date<? EXCEPT ALL
                     SELECT * FROM player_game_features)
                )''',[cutoff,cutoff]).fetchone()[0]
                self.assertEqual(changes,0)
                self.assert_checks_pass()


if __name__ == '__main__':
    unittest.main()
