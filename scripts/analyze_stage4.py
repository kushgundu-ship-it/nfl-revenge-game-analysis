#!/usr/bin/env python3
"""Add Stage 4 SQL views, cluster inference, and deterministic CSV exports.

Only resampling/inference is done in Python; SQL defines datasets and estimates.
No additional dependency: DuckDB + Python standard library.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys

import duckdb

from load_data import DATABASE, PROCESSED, ROOT, now, records, sha256, write_json

SEED = 20261008
ITERATIONS = 5000
SQL_FILES = ('11_stage4_features.sql', '12_stage4_summaries.sql', '13_stage4_validation.sql')
EFFECTS = ('pooled_mean', 'pooled_median', 'pooled_pct',
           'equal_player_mean', 'equal_player_median', 'equal_player_pct')
EXPORTS = {
    'player_comparisons': 'SELECT * FROM stage4_player_comparisons ORDER BY player_id',
    'segments': 'SELECT * FROM stage4_segments ORDER BY breakdown,segment,game_group',
    'usage_efficiency': 'SELECT * FROM stage4_usage_efficiency ORDER BY position,metric,game_group',
    'usage_efficiency_differences': 'SELECT * FROM stage4_usage_efficiency_differences ORDER BY position,metric',
    'sensitivity_groups': 'SELECT * FROM stage4_sensitivity_groups ORDER BY variant,game_group',
    'sensitivity_results': 'SELECT * FROM stage4_sensitivity_results ORDER BY variant',
    'outlier_cutoffs': 'SELECT * FROM stage4_outlier_cutoffs',
    'extreme_revenge': 'SELECT * FROM stage4_extreme_revenge ORDER BY performance_residual DESC,player_id,game_id',
    'departure_games': '''SELECT player_id,game_id,game_date,last_prior_opponent_game_date,
        days_since_former_team,departure_bucket,performance_residual FROM stage4_analysis_games
        WHERE is_revenge_game ORDER BY player_id,game_date,game_id''',
}


def percentile(values, fraction):
    """Linear interpolation (same convention as SQL quantile_cont)."""
    ordered = sorted(values)
    index = (len(ordered)-1)*fraction
    lower = int(index)
    upper = min(lower+1, len(ordered)-1)
    return ordered[lower]+(index-lower)*(ordered[upper]-ordered[lower])


def cluster_bootstrap(clusters, iterations=ITERATIONS, seed=SEED):
    """Each (revenge values, non-revenge values) pair is one entire player.

    Uniformly draw N players with replacement. A repeated player contributes all
    its games again, including to pooled medians; never deduplicate sampled IDs.
    Equal-player median is the MEAN of within-player median differences.
    """
    if len(clusters)<2 or any(not r or not n for r,n in clusters):
        raise ValueError('Need at least two players with both groups.')
    if iterations<1:
        raise ValueError('iterations must be positive')
    rng = random.Random(seed)
    prepared = []
    for r,n in clusters:
        prepared.append((sum(r),sum(n),len(r),len(n),sum(x>1e-9 for x in r),
                         sum(x>1e-9 for x in n),statistics.mean(r)-statistics.mean(n),
                         statistics.median(r)-statistics.median(n),
                         100*(sum(x>1e-9 for x in r)/len(r)-sum(x>1e-9 for x in n)/len(n))))
    draws = []
    size = len(clusters)
    for _ in range(iterations):
        indices = [rng.randrange(size) for _ in range(size)]
        totals = [sum(prepared[i][j] for i in indices) for j in range(9)]
        revenge = [x for i in indices for x in clusters[i][0]]
        normal = [x for i in indices for x in clusters[i][1]]
        draws.append((totals[0]/totals[2]-totals[1]/totals[3],
                      statistics.median(revenge)-statistics.median(normal),
                      100*(totals[4]/totals[2]-totals[5]/totals[3]),
                      totals[6]/size,totals[7]/size,totals[8]/size))
    return draws


def sign_flip(differences, iterations=ITERATIONS, seed=SEED+1):
    """Two-sided Monte Carlo test of independent, sign-symmetric player contrasts.

    Raw mean statistic; no game-label shuffling/exchangeability claim. Plus-one
    correction includes the observed arrangement and prevents a zero p-value.
    """
    rng = random.Random(seed)
    observed = abs(math.fsum(differences))
    extreme = sum(abs(math.fsum(d if rng.getrandbits(1) else -d for d in differences))
                  >= observed-1e-12 for _ in range(iterations))
    return (extreme+1)/(iterations+1)


def upstream_fingerprints(connection):
    """Every existing Stage 1–3 table/view, including validated summaries."""
    names = [r[0] for r in connection.execute('''SELECT table_name FROM information_schema.tables
        WHERE table_schema='main' AND NOT starts_with(table_name,'stage4_')
        ORDER BY table_name''').fetchall()]
    return {name: records(connection, f'''SELECT count(*) AS row_count,
        CAST(sum(CAST(hash(t) AS HUGEINT)) AS VARCHAR) AS hash_sum,
        CAST(bit_xor(hash(t)) AS VARCHAR) AS hash_xor FROM "{name}" t''')[0] for name in names}


def protected_files():
    paths = [ROOT/'project.md',ROOT/'requirements.txt']
    paths += [p for p in (ROOT/'sql').glob('*.sql') if int(p.name[:2])<=10]
    paths += [ROOT/'scripts'/n for n in ('load_data.py','build_stage2.py','build_stage3.py','query.py')]
    paths += [ROOT/'tests'/n for n in ('test_stage2.py','test_stage3.py')]
    paths += list((ROOT/'data/raw').glob('*'))
    paths += [PROCESSED/n for n in ('validation_report.json','stage2_validation_report.json','stage3_validation_report.json')]
    return {str(p.relative_to(ROOT)):sha256(p) for p in sorted(paths) if p.is_file()}


def write_csv(path, rows):
    if not rows:
        raise ValueError(f'Unexpected empty export: {path}')
    partial = path.with_suffix('.csv.partial')
    with partial.open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    partial.replace(path)


def analyze(connection, iterations=ITERATIONS, seed=SEED):
    rows = records(connection, '''SELECT player_id,
        list(performance_residual ORDER BY game_date,game_id) FILTER(WHERE is_revenge_game) AS revenge,
        list(performance_residual ORDER BY game_date,game_id) FILTER(WHERE NOT is_revenge_game) AS normal
        FROM stage4_analysis_games GROUP BY player_id ORDER BY player_id''')
    draws = cluster_bootstrap([(r['revenge'],r['normal']) for r in rows],iterations,seed)
    pooled = records(connection, '''SELECT
        avg(performance_residual) FILTER(WHERE is_revenge_game)-avg(performance_residual) FILTER(WHERE NOT is_revenge_game) AS pooled_mean,
        median(performance_residual) FILTER(WHERE is_revenge_game)-median(performance_residual) FILTER(WHERE NOT is_revenge_game) AS pooled_median,
        100*(avg(CAST(performance_residual>1e-9 AS INTEGER)) FILTER(WHERE is_revenge_game)
            -avg(CAST(performance_residual>1e-9 AS INTEGER)) FILTER(WHERE NOT is_revenge_game)) AS pooled_pct,
        count(*) FILTER(WHERE is_revenge_game) AS revenge_n,
        count(*) FILTER(WHERE NOT is_revenge_game) AS non_revenge_n
        FROM stage4_analysis_games''')[0]
    estimates = dict(pooled)
    estimates.update(records(connection, '''SELECT avg(mean_difference) AS equal_player_mean,
        avg(median_difference) AS equal_player_median,avg(pct_difference) AS equal_player_pct
        FROM stage4_player_comparisons''')[0])
    differences = [r[0] for r in connection.sql('SELECT mean_difference FROM stage4_player_comparisons ORDER BY player_id').fetchall()]
    p_value = sign_flip(differences,iterations,seed+1)
    inference = []
    for column,effect in enumerate(EFFECTS):
        values = [d[column] for d in draws]
        inference.append(dict(effect=effect,estimate=estimates[effect],
            ci_low=percentile(values,.025),ci_high=percentile(values,.975),
            p_value=p_value if effect=='equal_player_mean' else None,
            test='two_sided_player_sign_flip' if effect=='equal_player_mean' else 'not_tested',
            units='percentage_points' if effect.endswith('pct') else 'PPR_points',
            players=len(rows),revenge_n=pooled['revenge_n'],non_revenge_n=pooled['non_revenge_n'],
            bootstrap_iterations=iterations,bootstrap_seed=seed,sign_flip_seed=seed+1))
    return inference,[dict(iteration=i+1,**dict(zip(EFFECTS,d))) for i,d in enumerate(draws)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations',type=int,default=ITERATIONS)
    parser.add_argument('--seed',type=int,default=SEED)
    args = parser.parse_args()
    if args.iterations<5000:
        parser.error('Production inference requires at least 5,000 iterations.')
    report = dict(started_at_utc=now(),passed=False,python_version=platform.python_version(),
                  duckdb_version=duckdb.__version__,iterations=args.iterations,seed=args.seed)
    files_before = protected_files()
    tables = ROOT/'reports/tables'
    tables.mkdir(parents=True,exist_ok=True)
    with duckdb.connect(str(DATABASE)) as c:
        # Stable aggregate order for reproducibility and numeric fingerprints.
        c.execute('SET threads=1')
        c.execute('BEGIN TRANSACTION')
        try:
            before = upstream_fingerprints(c)
            checks = []
            for stage,view in ((1,'validation_checks'),(2,'stage2_validation_checks'),(3,'stage3_validation_checks')):
                checks += [dict(stage=stage,**r) for r in records(c,f'SELECT * FROM {view} ORDER BY check_name')]
            if any(r['severity']=='ERROR' and r['problem_count'] for r in checks):
                raise RuntimeError('Upstream validation failed.')
            saved = json.loads((PROCESSED/'stage3_validation_report.json').read_text())
            current = records(c,'SELECT * FROM stage3_summary ORDER BY breakdown,segment,game_group')
            report['stage3_saved_summary_unchanged'] = all(
                a.keys()==b.keys() and all(math.isclose(a[k],b[k],rel_tol=0,abs_tol=1e-9)
                    if isinstance(a[k],(int,float)) else a[k]==b[k] for k in a)
                for a,b in zip(current,saved['summary'])) and len(current)==len(saved['summary'])
            if not report['stage3_saved_summary_unchanged']:
                raise RuntimeError('Snapshot differs from validated Stage 3 summary.')
            for filename in SQL_FILES:
                c.execute((ROOT/'sql'/filename).read_text())
            checks += [dict(stage=4,**r) for r in records(c,'SELECT * FROM stage4_validation_checks ORDER BY check_name')]
            report['checks'] = checks
            if any(r['severity']=='ERROR' and r['problem_count'] for r in checks):
                raise RuntimeError('Stage 4 validation failed.')
            print('SQL checks passed; running player bootstrap and sign-flip test.',flush=True)
            inference,draws = analyze(c,args.iterations,args.seed)
            exports = {name:records(c,query) for name,query in EXPORTS.items()}
            exports.update(inference=inference,bootstrap_draws=draws,validation=checks)
            report['upstream_unchanged'] = before==upstream_fingerprints(c)
            report['protected_files_unchanged'] = files_before==protected_files()
            report['upstream_fingerprints'] = before
            report['protected_file_sha256'] = files_before
            if not report['upstream_unchanged'] or not report['protected_files_unchanged']:
                raise RuntimeError('Stage 1–3 preservation failure.')
            c.execute('COMMIT')
        except Exception as error:
            c.execute('ROLLBACK')
            report['error'] = str(error)
            write_json(PROCESSED/'stage4_failed_run.json',report)
            raise
    for name,rows in exports.items():
        write_csv(tables/f'stage4_{name}.csv',rows)
    report['csv_sha256'] = {name:sha256(tables/f'stage4_{name}.csv') for name in exports}
    report['analysis_code_sha256'] = {str(p.relative_to(ROOT)):sha256(p)
        for p in [Path(__file__)]+[ROOT/'sql'/n for n in SQL_FILES]}
    report.update(passed=True,finished_at_utc=now(),inference=inference)
    write_json(PROCESSED/'stage4_validation_report.json',report)
    for row in inference:
        print(f"{row['effect']}: {row['estimate']:.6f} [{row['ci_low']:.6f}, {row['ci_high']:.6f}], p={row['p_value']}")
    print('All four stages validated; earlier objects, source files, and reports unchanged.')


if __name__=='__main__':
    main()
