#!/usr/bin/env python3
"""Build rolling-baseline SQL views and validate all three stages."""
import sys

import duckdb

from load_data import DATABASE, PROCESSED, ROOT, fingerprints, now, records, write_json


def upstream_fingerprints(connection):
    result = fingerprints(connection)
    for name in ('player_team_history', 'player_team_history_asof',
                 'player_game_revenge_flags', 'fact_revenge_games'):
        result[name] = records(connection, f'''
            SELECT count(*) AS row_count,
                   CAST(sum(CAST(hash(t) AS HUGEINT)) AS VARCHAR) AS hash_sum,
                   CAST(bit_xor(hash(t)) AS VARCHAR) AS hash_xor FROM {name} t
        ''')[0]
    return result


def main():
    if not DATABASE.exists():
        raise RuntimeError('Run Stage 1 and Stage 2 before building Stage 3.')
    report = {'started_at_utc': now(), 'passed': False, 'duckdb_version': duckdb.__version__}
    with duckdb.connect(str(DATABASE)) as connection:
        connection.execute('BEGIN TRANSACTION')
        try:
            before = upstream_fingerprints(connection)
            for stage, view in (('stage1', 'validation_checks'), ('stage2', 'stage2_validation_checks')):
                checks = records(connection, f'SELECT * FROM {view} ORDER BY check_name')
                report[f'{stage}_checks'] = checks
                if any(c['severity']=='ERROR' and c['problem_count'] for c in checks):
                    raise RuntimeError(f'{stage} validation failed; see stage3_failed_run.json.')
            for filename in ('07_player_game_features.sql', '08_stage3_summaries.sql',
                             '09_stage3_validation.sql'):
                connection.execute((ROOT / 'sql' / filename).read_text())
            report['stage3_checks'] = records(connection, 'SELECT * FROM stage3_validation_checks ORDER BY check_name')
            if any(c['problem_count'] for c in report['stage3_checks']):
                raise RuntimeError('Stage 3 validation failed; see stage3_failed_run.json.')
            report['upstream_unchanged'] = before == upstream_fingerprints(connection)
            if not report['upstream_unchanged']:
                raise RuntimeError('Stage 3 unexpectedly changed earlier stages.')
            report['upstream_fingerprints'] = before
            report['summary'] = records(connection, 'SELECT * FROM stage3_summary ORDER BY breakdown,segment,game_group')
            report['coverage'] = records(connection, '''
                SELECT count(*) AS feature_rows,
                       count(*) FILTER(WHERE is_effect_eligible) AS eligible_rows_all_players,
                       count(*) FILTER(WHERE prior_game_count<4) AS insufficient_history_rows,
                       (SELECT count(*) FROM stage3_comparison_cohort) AS comparison_players,
                       (SELECT count(*) FROM analysis_revenge_games) AS revenge_rows,
                       (SELECT count(*) FROM analysis_comparison_games) AS comparison_rows
                FROM player_game_features
            ''')[0]
            report['score_availability'] = records(connection, '''
                SELECT game_group,revenge_score_unavailable_reason,count(*) AS rows
                FROM stage3_analysis_games GROUP BY ALL ORDER BY game_group,revenge_score_unavailable_reason
            ''')
            connection.execute('COMMIT')
        except Exception as error:
            connection.execute('ROLLBACK')
            report['error'] = str(error)
            write_json(PROCESSED / 'stage3_failed_run.json', report)
            raise
    report['passed'] = True
    report['finished_at_utc'] = now()
    write_json(PROCESSED / 'stage3_validation_report.json', report)
    print('All three stages passed their error checks; Stage 1/2 fingerprints unchanged.')
    for check in report['stage1_checks']:
        if check['problem_count']:
            print(f"Stage 1 {check['severity']}: {check['check_name']} = {check['problem_count']}")
    print(report['coverage'])
    print('Group | N | % exceeded | Mean actual | Mean expected | Mean residual | Median residual')
    for row in report['summary']:
        if row['breakdown']=='overall':
            print(f"{row['game_group']} | {row['sample_size']} | {row['pct_exceeded_baseline']:.2f} | "
                  f"{row['mean_actual_ppr']:.3f} | {row['mean_expected_ppr']:.3f} | "
                  f"{row['mean_residual']:.3f} | {row['median_residual']:.3f}")
    print(f"Report: {PROCESSED / 'stage3_validation_report.json'}")


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
