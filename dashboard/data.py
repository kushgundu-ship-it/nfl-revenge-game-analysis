"""Read existing views and saved reports. No statistical model lives here."""
import hashlib
import json
import math
from pathlib import Path
import re

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLE_NAMES = ('inference','segments','usage_efficiency','usage_efficiency_differences',
               'sensitivity_results','sensitivity_groups','outlier_cutoffs',
               'player_comparisons','extreme_revenge','departure_games','validation','bootstrap_draws')
POSITIONS = ('QB','RB','WR','TE')


class DataIssue(RuntimeError):
    """A missing, stale, or invalid analytical input that the UI should explain."""


def require_finite(frame, columns):
    for column in columns:
        if column not in frame or any(pd.isna(x) or not math.isfinite(float(x)) for x in frame[column]):
            raise DataIssue(f'Unexpected missing or nonfinite plot metric: {column}.')


def available_efficiency(frame):
    """Only documented zero-sample contrasts may be omitted, never fabricated as zero."""
    missing = frame['mean_residual_difference'].isna()
    if (missing & (frame['revenge_n']>0) & (frame['non_revenge_n']>0)).any():
        raise DataIssue('An efficiency contrast is missing despite nonzero sample sizes.')
    valid = frame.loc[~missing].copy()
    require_finite(valid,['mean_residual_difference','revenge_n','non_revenge_n'])
    return valid,frame.loc[missing].copy()


def signed(value, places=3):
    return f'{float(value):+.{places}f}'.replace('-', '−')


def headline(inference):
    selected = inference.loc[inference['effect']=='equal_player_mean']
    if len(selected)!=1:
        raise DataIssue('Saved primary inference must have exactly one row.')
    require_finite(selected,['estimate','ci_low','ci_high','p_value','players','revenge_n','non_revenge_n'])
    row = selected.iloc[0]
    if row['ci_low']>row['ci_high'] or not 0<=row['p_value']<=1:
        raise DataIssue('Saved confidence interval or p-value is invalid.')
    # This interpretation is conditional on the saved test and interval, not a fixed number.
    if row['ci_low']<=0<=row['ci_high'] and row['p_value']>=.05:
        conclusion = 'No statistically distinguishable mean revenge effect was found.'
    else:
        conclusion = 'The saved inference differs from the reviewed conclusion; review Stage 4 before interpreting it.'
    return dict(estimate=f"{signed(row['estimate'])} PPR",
                interval=f"{signed(row['ci_low'])} to {signed(row['ci_high'])}",
                p_value=f"{row['p_value']:.4f}",conclusion=conclusion)


class Repository:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.database = self.root/'data/processed/nfl.duckdb'
        self.tables = self.root/'reports/tables'
        text = (self.root/'sql/15_dashboard_queries.sql').read_text()
        parts = re.split(r'^-- name: (\w+)\s*$',text,flags=re.MULTILINE)
        self.queries = {parts[i]:parts[i+1].strip() for i in range(1,len(parts),2)}

    def query(self,name,parameters=None):
        if name not in self.queries:
            raise ValueError(f'Unknown dashboard query: {name}')
        if not self.database.exists():
            raise DataIssue('The local DuckDB database is missing. Complete Stages 1–4 first.')
        try:
            with duckdb.connect(str(self.database),read_only=True) as connection:
                connection.execute('SET threads=1')
                return connection.execute(self.queries[name],parameters or []).fetchdf()
        except duckdb.Error as error:
            raise DataIssue('Could not read the validated database. Stop any pipeline rebuild, '
                            'then confirm Stages 1–4 completed successfully.') from error

    def report(self,name):
        if name not in TABLE_NAMES:
            raise ValueError(f'Unknown Stage 4 table: {name}')
        path = self.tables/f'stage4_{name}.csv'
        if not path.exists():
            raise DataIssue(f'Missing {path.name}. Run scripts/analyze_stage4.py before opening the dashboard.')
        return pd.read_csv(path,float_precision='round_trip',dtype={'player_id':str,'game_id':str})

    def signature(self):
        paths = [self.database,self.root/'data/processed/stage4_validation_report.json',
                 self.root/'sql/15_dashboard_queries.sql']
        paths += [self.tables/f'stage4_{name}.csv' for name in TABLE_NAMES]
        return tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) if p.exists()
                     else (str(p),None,None) for p in paths)


def load_bundle(repository):
    validation = repository.root/'data/processed/stage4_validation_report.json'
    if not validation.exists():
        raise DataIssue('The successful Stage 4 validation report is missing. Complete Stage 4 first.')
    report = json.loads(validation.read_text())
    if not report.get('passed'):
        raise DataIssue('Stage 4 is not marked as passed.')
    tables = {}
    for name in TABLE_NAMES:
        tables[name] = repository.report(name)
        path = repository.tables/f'stage4_{name}.csv'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=report['csv_sha256'].get(name):
            raise DataIssue(f'{path.name} does not match the saved Stage 4 validation report. Rebuild and review Stage 4.')
    counts = repository.query('counts').set_index('game_group')
    primary = tables['inference'].set_index('effect').loc['equal_player_mean']
    if (counts.loc['revenge','games']!=primary['revenge_n'] or
            counts.loc['non_revenge','games']!=primary['non_revenge_n'] or
            any(counts['players']!=primary['players'])):
        raise DataIssue('Live database counts differ from the saved inference. Rebuild and review Stage 4.')
    headline(tables['inference'])
    return dict(tables=tables,scope=repository.query('scope').iloc[0].to_dict(),
                players=repository.query('players'),examples=repository.query('examples'),
                report=report)


def validate_bundle(repository,bundle):
    tables = bundle['tables']
    primary = headline(tables['inference'])
    saved = pd.DataFrame(bundle['report']['inference'])
    if primary!=headline(saved):
        raise DataIssue('Displayed primary values differ from the Stage 4 JSON report.')
    require_finite(tables['inference'],['estimate','ci_low','ci_high'])
    require_finite(tables['segments'],['games','players','mean_residual','median_residual','pct_exceeded'])
    require_finite(tables['sensitivity_results'],['pooled_mean_difference','equal_player_mean_difference',
                                                 'pooled_median_difference','revenge_n','non_revenge_n'])
    available_efficiency(tables['usage_efficiency_differences'])
    for row in tables['usage_efficiency'].to_dict('records'):
        if row['residual_n']>0:
            require_finite(pd.DataFrame([row]),['mean_actual_paired','mean_expected_paired','mean_residual'])
    players = bundle['players']
    if players.empty or players['player_id'].duplicated().any() or players['player_id'].isna().any():
        raise DataIssue('Player choices must have unique stable IDs.')
    if set(players['player_id'])!=set(tables['player_comparisons']['player_id']):
        raise DataIssue('Live player choices differ from the saved Stage 4 cohort.')
    for position in ('All positions',)+POSITIONS:
        frame = repository.query('histogram',[position,position])
        if frame.empty:
            raise DataIssue(f'Empty distribution for {position}')
        require_finite(frame,['bin_start','bin_end','games','percentage'])
        if any(abs(x-100)>1e-8 for x in frame.groupby('game_group')['percentage'].sum()):
            raise DataIssue('Distribution percentages do not sum to 100 within each group.')
    if len(bundle['examples'])!=4:
        raise DataIssue('One of the four inspected player examples is missing.')
    for row in bundle['examples'].to_dict('records'):
        games = repository.query('player_games',[row['player_id']])
        support = repository.query('baseline',[row['player_id'],row['game_id']])
        require_finite(games,['actual_ppr_points','expected_ppr_points','performance_residual'])
        require_finite(support,['prior_ppr_points'])
        if games.empty or not 4<=len(support)<=8 or set(games['player_id'])!={row['player_id']}:
            raise DataIssue('Player example or baseline query failed.')
    return ['required_stage4_files_and_hashes','live_counts_match_saved_inference',
            'displayed_primary_matches_stage4_report','plot_metrics_finite_or_documented_null',
            'stable_unique_player_ids','all_position_distribution_queries',
            'all_example_and_baseline_queries']
