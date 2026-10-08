"""Stage 4 temporal, statistical, and preservation checks; mutations only in memory."""
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tempfile
import unittest

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_stage4 import (EFFECTS, ITERATIONS, SEED, analyze, cluster_bootstrap,
                            percentile, protected_files, sign_flip,
                            upstream_fingerprints, write_csv)


class Stage4FeaturesTests(unittest.TestCase):
    def setUp(self):
        self.c = duckdb.connect()
        self.c.execute('SET threads=1')
        self.c.execute('''CREATE TABLE player_game_revenge_flags (
            player_id VARCHAR,player_display_name VARCHAR,game_id VARCHAR,game_date DATE,
            season INTEGER,week INTEGER,position VARCHAR,team VARCHAR,opponent_team VARCHAR,
            fantasy_points_ppr DOUBLE,is_revenge_game BOOLEAN,
            is_first_meeting_with_former_team BOOLEAN,prior_opponent_appearances BIGINT,
            last_prior_opponent_game_date DATE,home_team VARCHAR,
            attempts DOUBLE,carries DOUBLE,targets DOUBLE,receptions DOUBLE,
            passing_yards DOUBLE,rushing_yards DOUBLE,receiving_yards DOUBLE,
            passing_tds DOUBLE,rushing_tds DOUBLE,receiving_tds DOUBLE)''')
        self.c.execute('CREATE VIEW clean_player_game_stats AS SELECT * FROM player_game_revenge_flags')
        for position in ('QB','RB','WR','TE'):
            for n in range(1,13):
                self.c.execute('INSERT INTO player_game_revenge_flags VALUES ('+','.join(['?']*25)+')',
                    [position,'Synthetic',f'{position}-{n}',date(2020,1,1)+timedelta(days=n*14),
                     2020,n,position,'BUF','NE',n*2,n in (6,10),n==6,4 if n in (6,10) else 0,
                     date(2019,12,1),'BUF',10+n,n,2*n,n,70+10*n,4*n,12*n,2,1,1])
        for filename in ('07_player_game_features.sql','08_stage3_summaries.sql','09_stage3_validation.sql',
                         '11_stage4_features.sql','12_stage4_summaries.sql','13_stage4_validation.sql'):
            self.c.execute((ROOT/'sql'/filename).read_text())

    def tearDown(self):
        self.c.close()

    def metric(self,game,metric):
        r = self.c.execute('SELECT * FROM stage4_metric_features WHERE game_id=? AND metric=?',[game,metric])
        return dict(zip([x[0] for x in r.description],r.fetchone()))

    def test_all_sql_checks_and_shared_group_features(self):
        self.assertEqual(self.c.sql('SELECT check_name,problem_count FROM stage4_validation_checks WHERE problem_count>0').fetchall(),[])
        for group in ('revenge','non_revenge'):
            self.assertGreater(self.c.execute('SELECT count(*) FROM stage4_analysis_metrics WHERE game_group=?',[group]).fetchone()[0],0)
        self.assertEqual(self.c.sql('SELECT count(*) FROM stage4_player_comparisons WHERE revenge_n>0 AND non_revenge_n>0').fetchone()[0],4)

    def test_usage_formula_all_positions_receptions_not_added(self):
        for position in ('QB','RB','WR','TE'):
            r=self.metric(f'{position}-6','opportunities')
            self.assertEqual(r['actual'],22 if position=='QB' else 18)
            self.assertEqual(r['expected'],16 if position=='QB' else 9)
            td=self.metric(f'{position}-6','touchdowns_per_opportunity')
            self.assertAlmostEqual(td['actual'],3/22 if position=='QB' else 2/18)
        self.c.execute('UPDATE player_game_revenge_flags SET receptions=1000')
        self.assertEqual(self.metric('QB-6','opportunities')['actual'],22)
        self.assertEqual(self.metric('RB-6','opportunities')['actual'],18)
        self.assertEqual(self.metric('RB-6','receptions')['actual'],1000)

    def test_window_boundaries_eight_cap_and_ratio_mean(self):
        self.assertIsNone(self.metric('QB-4','pass_attempts')['expected'])
        self.assertEqual(self.metric('QB-5','pass_attempts')['valid_prior_n'],4)
        r=self.metric('QB-12','passing_yards_per_attempt')
        self.assertEqual(r['window_n'],8)
        self.assertAlmostEqual(r['expected'],statistics.mean((70+10*n)/(10+n) for n in range(4,12)))
        self.assertNotAlmostEqual(r['expected'],sum(70+10*n for n in range(4,12))/sum(10+n for n in range(4,12)))

    def test_current_and_future_usage_cannot_leak(self):
        before=self.c.sql("SELECT metric,expected,window_n,valid_prior_n FROM stage4_metric_features WHERE game_id='QB-6' ORDER BY metric").fetchall()
        self.c.execute("""UPDATE player_game_revenge_flags SET attempts=999,carries=999,
            targets=999,receptions=999,passing_yards=999,rushing_yards=999,receiving_yards=999,
            passing_tds=99,rushing_tds=99,receiving_tds=99 WHERE player_id='QB' AND week>=6""")
        after=self.c.sql("SELECT metric,expected,window_n,valid_prior_n FROM stage4_metric_features WHERE game_id='QB-6' ORDER BY metric").fetchall()
        self.assertEqual(before,after)

    def test_zero_negative_and_missing_denominators_are_null(self):
        for value in (0,-1,None):
            self.c.execute("UPDATE player_game_revenge_flags SET attempts=?,carries=?,targets=? WHERE week=6",[value]*3)
            for game,metric in (('QB-6','passing_yards_per_attempt'),('RB-6','rushing_yards_per_carry'),
                                ('WR-6','receiving_yards_per_target'),('TE-6','touchdowns_per_opportunity')):
                self.assertIsNone(self.metric(game,metric)['actual'])
                self.assertIsNone(self.metric(game,metric)['residual'])

    def test_undefined_prior_ratios_no_backfill_and_missing_usage(self):
        self.c.execute("UPDATE player_game_revenge_flags SET carries=0 WHERE week BETWEEN 4 AND 8")
        r=self.metric('RB-12','rushing_yards_per_carry')
        self.assertEqual((r['window_n'],r['valid_prior_n']),(8,3))
        self.assertIsNone(r['expected'])  # valid games 1–3 cannot backfill the eight-appearance window
        self.c.execute("UPDATE player_game_revenge_flags SET carries=2 WHERE week=8")
        self.assertIsNotNone(self.metric('RB-12','rushing_yards_per_carry')['expected'])
        self.c.execute("UPDATE player_game_revenge_flags SET targets=NULL WHERE week=8")
        self.assertIsNone(self.metric('WR-12','targets')['expected'])

    def test_future_removal_all_earlier_metrics_unchanged(self):
        self.c.execute('CREATE TABLE before_metrics AS SELECT * FROM stage4_metric_features')
        self.c.execute('DELETE FROM player_game_revenge_flags WHERE week>=10')
        self.assertEqual(self.c.sql('''SELECT count(*) FROM (
            (SELECT * FROM stage4_metric_features EXCEPT ALL SELECT * FROM before_metrics WHERE game_date<DATE '2020-05-20')
            UNION ALL
            (SELECT * FROM before_metrics WHERE game_date<DATE '2020-05-20' EXCEPT ALL SELECT * FROM stage4_metric_features))''').fetchone()[0],0)

    def test_player_without_comparison_is_excluded(self):
        self.c.execute("UPDATE player_game_revenge_flags SET is_revenge_game=true WHERE player_id='TE'")
        self.assertEqual(self.c.sql("SELECT count(*) FROM stage4_player_comparisons WHERE player_id='TE'").fetchone()[0],0)

    def test_outlier_views_preserve_source_and_apply_common_cutoffs(self):
        self.c.execute("UPDATE player_game_revenge_flags SET fantasy_points_ppr=10000 WHERE game_id='QB-10'")
        before=self.c.sql('SELECT * FROM player_game_revenge_flags ORDER BY player_id,week').fetchall()
        original=self.c.sql('SELECT * FROM player_game_features ORDER BY player_id,game_id').fetchall()
        low,high=self.c.sql('SELECT * FROM stage4_outlier_cutoffs').fetchone()
        values=[r[0] for r in self.c.sql('SELECT performance_residual FROM stage4_analysis_games').fetchall()]
        self.assertAlmostEqual(low,percentile(values,.01))
        self.assertAlmostEqual(high,percentile(values,.99))
        transformed=self.c.sql('SELECT variant,performance_residual,analysis_residual FROM stage4_sensitivity_games').fetchall()
        for variant,value,result in transformed:
            self.assertEqual(result,max(low,min(high,value)) if variant=='winsorized_1_99' else value)
            if variant=='trimmed_1_99':
                self.assertTrue(low<=value<=high)
        self.assertEqual(before,self.c.sql('SELECT * FROM player_game_revenge_flags ORDER BY player_id,week').fetchall())
        self.assertEqual(original,self.c.sql('SELECT * FROM player_game_features ORDER BY player_id,game_id').fetchall())


class Stage4InferenceTests(unittest.TestCase):
    def test_no_effect_interval_centered_near_zero_and_known_shift_recovered(self):
        clusters=[([offset-1,offset+1],[0,0,0]) for offset in [-1,1]*10]
        no_effect=cluster_bootstrap(clusters)
        shifted=cluster_bootstrap([([x+3 for x in r],n) for r,n in clusters])
        for column in (0,3):
            null_values=[d[column] for d in no_effect]
            lo,hi=percentile(null_values,.025),percentile(null_values,.975)
            self.assertLess(lo,0)
            self.assertGreater(hi,0)
            self.assertLess(abs((lo+hi)/2),.1)
            effect_values=[d[column] for d in shifted]
            self.assertLess(percentile(effect_values,.025),3)
            self.assertGreater(percentile(effect_values,.975),3)
            for null,effect in zip(null_values,effect_values):
                self.assertAlmostEqual(effect-null,3)
        self.assertEqual(sign_flip([-1,1]*10),1)
        self.assertLess(sign_flip([2,4]*10),.01)

    def test_repeated_clusters_are_not_deduplicated_and_weights_differ(self):
        clusters=[([10],[0]*9),([0]*9,[10])]
        draws=cluster_bootstrap(clusters,iterations=100,seed=SEED)
        self.assertEqual(draws,cluster_bootstrap(clusters,iterations=100,seed=SEED))
        self.assertNotEqual(draws,cluster_bootstrap(clusters,iterations=100,seed=SEED+1))
        self.assertIn((10,10,100,10,10,100),draws)
        self.assertIn((-10,-10,-100,-10,-10,-100),draws)
        # Mixed draw pooled mean=0 here; asymmetric within-player sample counts
        # can yield different estimands even when all observations are retained.
        unequal=cluster_bootstrap([([10],[0]*9),([0]*9,[0])],iterations=100)
        self.assertTrue(any(abs(d[0]-d[3])>1 for d in unequal))

    def test_invalid_clusters_rejected(self):
        with self.assertRaises(ValueError):
            cluster_bootstrap([([1],[]),([2],[0])])

    def test_real_5000_draws_and_csv_reproducibility(self):
        report=json.loads((ROOT/'data/processed/stage4_validation_report.json').read_text())
        with duckdb.connect(str(ROOT/'data/processed/nfl.duckdb'),read_only=True) as c:
            c.execute('SET threads=1')
            inference,draws=analyze(c)
        self.assertEqual(len(draws),5000)
        with tempfile.TemporaryDirectory() as folder:
            for name,rows in (('inference',inference),('bootstrap_draws',draws)):
                path=Path(folder)/f'{name}.csv'
                write_csv(path,rows)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),report['csv_sha256'][name])

    def test_real_preservation_all_stages_and_all_checks(self):
        report=json.loads((ROOT/'data/processed/stage4_validation_report.json').read_text())
        self.assertTrue(report['upstream_unchanged'])
        self.assertTrue(report['stage3_saved_summary_unchanged'])
        self.assertEqual(protected_files(),report['protected_file_sha256'])
        with duckdb.connect(str(ROOT/'data/processed/nfl.duckdb'),read_only=True) as c:
            c.execute('SET threads=1')
            self.assertEqual(upstream_fingerprints(c),report['upstream_fingerprints'])
        self.assertFalse([r for r in report['checks'] if r['severity']=='ERROR' and r['problem_count']])


if __name__=='__main__':
    unittest.main()
