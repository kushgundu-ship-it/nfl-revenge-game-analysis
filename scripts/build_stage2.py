#!/usr/bin/env python3
"""Build Stage 2 SQL views and run both stages' checks without changing Stage 1."""
import sys

import duckdb

from load_data import DATABASE, PROCESSED, ROOT, fingerprints, now, records, write_json


def main():
    if not DATABASE.exists():
        raise RuntimeError('Run scripts/load_data.py first; the Stage 1 database is missing.')
    report = {'started_at_utc': now(), 'passed': False}
    with duckdb.connect(str(DATABASE)) as connection:
        connection.execute('BEGIN TRANSACTION')
        try:
            before = fingerprints(connection)
            report['stage1_checks'] = records(connection, 'SELECT * FROM validation_checks ORDER BY check_name')
            if any(c['severity']=='ERROR' and c['problem_count'] for c in report['stage1_checks']):
                raise RuntimeError('Stage 1 checks failed. Inspect the failed Stage 2 report.')
            for filename in ('04_team_history.sql', '05_stage2_validation.sql'):
                connection.execute((ROOT / 'sql' / filename).read_text())
            report['stage2_checks'] = records(connection, 'SELECT * FROM stage2_validation_checks ORDER BY check_name')
            if any(c['problem_count'] for c in report['stage2_checks']):
                raise RuntimeError('Stage 2 checks failed. Inspect the failed Stage 2 report.')
            report['stage1_unchanged'] = before == fingerprints(connection)
            if not report['stage1_unchanged']:
                raise RuntimeError('Stage 2 unexpectedly changed Stage 1 data.')
            report['counts_by_season'] = records(connection, 'SELECT * FROM stage2_season_counts ORDER BY season')
            report['totals'] = records(connection, '''
                SELECT count(*) AS revenge_games, count(DISTINCT player_id) AS players,
                       count(*) FILTER(WHERE is_first_meeting_with_former_team) AS first_meetings
                FROM fact_revenge_games
            ''')[0]
            report['history_counts'] = records(connection, '''
                SELECT (SELECT count(*) FROM player_team_history) AS player_team_pairs,
                       (SELECT count(*) FROM player_team_history_asof) AS asof_rows
            ''')[0]
            connection.execute('COMMIT')
        except Exception as error:
            connection.execute('ROLLBACK')
            report['error'] = str(error)
            write_json(PROCESSED / 'stage2_failed_run.json', report)
            raise
    report['passed'] = True
    report['finished_at_utc'] = now()
    write_json(PROCESSED / 'stage2_validation_report.json', report)
    print('Stage 1 and Stage 2 checks PASSED; Stage 1 data unchanged.')
    for check in report['stage1_checks']:
        if check['problem_count']:
            print(f"Stage 1 {check['severity']}: {check['check_name']} = {check['problem_count']}")
    print(report['totals'])
    print(f"Report: {PROCESSED / 'stage2_validation_report.json'}")


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
