"""Dashboard contracts and real Streamlit interactions, with read-only source access."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
AVAILABLE = importlib.util.find_spec('streamlit') is not None
if AVAILABLE:
    import pandas as pd
    from streamlit.testing.v1 import AppTest
    from dashboard.data import (DataIssue,POSITIONS,Repository,TABLE_NAMES,available_efficiency,
                                headline,load_bundle,require_finite,validate_bundle)
    from dashboard import charts


@unittest.skipUnless(AVAILABLE,'Install requirements-dashboard.txt to run Stage 5 tests.')
class DashboardDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = Repository()
        cls.bundle = load_bundle(cls.repository)

    def test_required_outputs_queries_and_snapshot_contracts(self):
        for name in TABLE_NAMES:
            self.assertFalse(self.repository.report(name).empty,name)
        self.assertEqual(len(validate_bundle(self.repository,self.bundle)),7)

    def test_primary_display_matches_saved_json_and_changes_with_input(self):
        saved = pd.DataFrame(self.bundle['report']['inference'])
        self.assertEqual(headline(saved),headline(self.bundle['tables']['inference']))
        changed = saved.copy()
        changed.loc[changed.effect=='equal_player_mean','estimate']=.12345
        self.assertEqual(headline(changed)['estimate'],'+0.123 PPR')
        self.assertNotEqual(headline(changed),headline(saved))

    def test_missing_outputs_and_corruption_fail_clearly(self):
        repository=Repository()
        with tempfile.TemporaryDirectory() as directory:
            repository.tables=Path(directory)
            with self.assertRaisesRegex(DataIssue,'Missing stage4_inference.csv'):
                repository.report('inference')
        with patch('dashboard.data.hashlib.sha256') as mocked:
            mocked.return_value.hexdigest.return_value='wrong'
            with self.assertRaisesRegex(DataIssue,'does not match'):
                load_bundle(self.repository)

    def test_ids_are_unique_parameterized_and_isolate_players(self):
        players=self.bundle['players']
        self.assertEqual(players.player_id.nunique(),len(players))
        for pid in self.bundle['examples'].player_id:
            self.assertEqual(set(self.repository.query('player_games',[pid]).player_id),{pid})
        self.assertTrue(self.repository.query('player_games',["' OR 1=1 --"]).empty)
        with self.assertRaises(ValueError):
            self.repository.query('DELETE FROM raw_schedules')

    def test_expected_nulls_are_distinguished_from_bad_plot_data(self):
        differences=self.bundle['tables']['usage_efficiency_differences']
        valid,missing=available_efficiency(differences)
        self.assertEqual(set(missing.position),{'TE'})
        self.assertEqual(set(missing.metric),{'rushing_yards_per_carry'})
        self.assertTrue((missing.revenge_n==0).all())
        broken=differences.copy()
        broken.loc[broken.index[0],'mean_residual_difference']=float('nan')
        with self.assertRaises(DataIssue):
            available_efficiency(broken)
        for value in (float('inf'),float('-inf'),float('nan'),None):
            with self.assertRaises(DataIssue):
                require_finite(pd.DataFrame({'metric':[value]}),['metric'])

    def test_all_chart_specs_serialize_without_nonfinite_plot_values(self):
        tables=self.bundle['tables']
        plots=[charts.interval(tables['inference']),charts.sensitivity(tables['sensitivity_results'])]
        for position in ('All positions',)+POSITIONS:
            distribution=charts.distribution(self.repository.query('histogram',[position,position]))
            self.assertEqual(distribution.to_dict()['layer'][0]['mark']['orient'],'vertical')
            plots.append(distribution)
        for breakdown in ('position','meeting','venue','departure'):
            frame=tables['segments'].loc[tables['segments'].breakdown==breakdown]
            plots.append(charts.group_bars(frame,'segment'))
        differences=tables['usage_efficiency_differences']
        for metric in differences.metric.unique():
            plots.append(charts.metric_difference(differences.loc[differences.metric==metric],'Metric residual')[0])
        for example in self.bundle['examples'].itertuples():
            support=self.repository.query('baseline',[example.player_id,example.game_id])
            game=self.repository.query('player_games',[example.player_id]).set_index('game_id').loc[example.game_id]
            self.assertEqual(len(support),game.prior_game_count)
            self.assertTrue((support.prior_game_date<game.game_date).all())
            plots.append(charts.baseline(support,game))
        for plot in plots:
            json.dumps(plot.to_dict(),allow_nan=False)
            spec=charts.inline_spec(plot)
            serialized=json.dumps(spec,allow_nan=False)
            self.assertNotIn('datasets',spec)
            self.assertIn('"values":',serialized)
            self.assertNotIn('"data": {"name":',serialized)


@unittest.skipUnless(AVAILABLE,'Install requirements-dashboard.txt to run Stage 5 tests.')
class DashboardAppTests(unittest.TestCase):
    def app(self):
        app=AppTest.from_file(str(ROOT/'dashboard/app.py'),default_timeout=30).run()
        self.assert_clean(app)
        return app

    def assert_clean(self,app):
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.error),0,str(app.error))

    def test_headline_and_all_distribution_filters(self):
        app=self.app()
        expected=headline(Repository().report('inference'))
        self.assertEqual([m.value for m in app.metric],
                         [expected['estimate'],expected['interval'],expected['p_value']])
        for position in ('All positions',)+POSITIONS:
            app.selectbox(key='distribution_position').set_value(position).run()
            self.assert_clean(app)
            self.assertEqual(app.metric[0].value,expected['estimate'])
            self.assertEqual(len(app.get('arrow_vega_lite_chart')),2)

    def test_every_breakdown_usage_efficiency_and_sensitivity_view(self):
        app=self.app()
        app.radio(key='page').set_value('Patterns').run()
        for breakdown in ('Position','First vs later meeting','Home vs away','Time since former team'):
            app.selectbox(key='breakdown').set_value(breakdown).run()
            self.assert_clean(app)
            self.assertGreater(len(app.dataframe[0].value),0)
        app.radio(key='pattern_view').set_value('Usage & efficiency').run()
        table=Repository().report('usage_efficiency_differences')
        for family in ('Usage','Efficiency'):
            app.selectbox(key='metric_family').set_value(family).run()
            for metric in table.loc[table.metric_family==family.lower(),'metric'].unique():
                app.selectbox(key='usage_metric').set_value(metric).run()
                self.assert_clean(app)
                self.assertEqual(len(app.get('arrow_vega_lite_chart')),1)
                self.assertGreater(len(app.dataframe[0].value),0)
        app.radio(key='pattern_view').set_value('Outlier sensitivity').run()
        self.assert_clean(app)
        self.assertEqual(len(app.dataframe[0].value),3)

    def test_each_example_and_every_game_for_example_players(self):
        app=self.app()
        app.radio(key='page').set_value('Player explorer').run()
        examples=Repository().query('examples')
        for example in examples.itertuples():
            app.button(key=f'example_{example.player_id}').click().run()
            self.assert_clean(app)
            self.assertEqual(app.selectbox(key='player_id').value,example.player_id)
            self.assertEqual(app.selectbox(key=f'game_{example.player_id}').value,example.game_id)
            games=Repository().query('player_games',[example.player_id])
            for game_id in games.game_id:
                app.selectbox(key=f'game_{example.player_id}').set_value(game_id).run()
                self.assert_clean(app)
                support=Repository().query('baseline',[example.player_id,game_id])
                self.assertEqual(len(app.dataframe[-1].value),len(support))

    def test_player_search_and_unavailable_score(self):
        app=self.app()
        app.radio(key='page').set_value('Player explorer').run()
        # Find a real, eligible zero-variance case; do not invent a score of zero.
        import duckdb
        with duckdb.connect(str(ROOT/'data/processed/nfl.duckdb'),read_only=True) as c:
            pid,gid=c.sql('''SELECT player_id,game_id FROM stage4_analysis_games
                WHERE is_revenge_game AND revenge_score IS NULL ORDER BY player_id,game_id LIMIT 1''').fetchone()
        app.selectbox(key='player_id').set_value(pid).run()
        app.selectbox(key=f'game_{pid}').set_value(gid).run()
        self.assert_clean(app)
        self.assertTrue(any('Standardized score unavailable' in x.value for x in app.info))

    def test_methods_and_missing_input_empty_state(self):
        app=self.app()
        app.radio(key='page').set_value('Methods & limits').run()
        self.assert_clean(app)
        self.assertEqual(len(app.dataframe[0].value),2)
        with patch('dashboard.data.Repository.signature',return_value=(('missing',None,None),)), \
             patch('dashboard.data.load_bundle',side_effect=DataIssue('Missing Stage 4 inputs')):
            broken=AppTest.from_file(str(ROOT/'dashboard/app.py'),default_timeout=30).run()
            self.assertEqual(len(broken.exception),0)
            self.assertIn('Missing Stage 4 inputs',broken.error[0].value)


if __name__=='__main__':
    unittest.main()
