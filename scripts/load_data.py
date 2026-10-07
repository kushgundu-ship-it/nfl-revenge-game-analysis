#!/usr/bin/env python3
"""Download/cache nflverse files, run SQL, and validate a persistent DuckDB file."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from urllib.request import Request, urlopen

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
PROCESSED = ROOT / 'data' / 'processed'
DATABASE = PROCESSED / 'nfl.duckdb'
MANIFEST = RAW / 'manifest.json'
REPORT = PROCESSED / 'validation_report.json'
SEASONS = range(2015, 2026)
PLAYER_URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_player/'
SCHEDULE_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
TABLES = ('raw_player_weekly_stats', 'raw_schedules', 'clean_player_game_stats')


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, payload):
    partial = path.with_suffix(path.suffix + '.partial')
    partial.write_text(json.dumps(payload, indent=2, default=str) + '\n')
    partial.replace(path)


def fetch(url, destination, offline):
    """Never overwrite an existing raw snapshot; rename only completed downloads."""
    if destination.exists():
        if not destination.stat().st_size:
            raise RuntimeError(f'Empty cached file: {destination}')
        print(f'Cached: {destination.name}', flush=True)
        return 'existing_file'
    if offline:
        raise RuntimeError(f'Offline mode: missing {destination}')
    partial = destination.with_suffix(destination.suffix + '.partial')
    for attempt in range(3):
        try:
            request = Request(url, headers={'User-Agent': 'NFL-SQL-Project/Stage1'})
            with urlopen(request, timeout=90) as response, partial.open('wb') as out:
                shutil.copyfileobj(response, out)
            if not partial.stat().st_size:
                raise RuntimeError(f'Empty download: {url}')
            partial.replace(destination)
            print(f'Downloaded: {destination.name}', flush=True)
            return 'python_download'
        except Exception:
            if partial.exists():
                partial.unlink()
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def prepare_files(offline):
    sources = [(f'stats_player_week_{year}.parquet',
                f'{PLAYER_URL}stats_player_week_{year}.parquet') for year in SEASONS]
    sources.append(('games.csv', SCHEDULE_URL))
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {'files': {}}
    for filename, url in sources:
        path = RAW / filename
        mode = fetch(url, path, offline)
        checksum = sha256(path)
        existing = manifest['files'].get(filename)
        if existing and (existing['sha256'] != checksum or existing['url'] != url):
            raise RuntimeError(f'Cached source changed: {filename}. Preserve the old snapshot '
                               'and investigate before intentionally adopting a new one.')
        if not existing:
            manifest['files'][filename] = {
                'url': url, 'sha256': checksum, 'bytes': path.stat().st_size,
                'recorded_at_utc': now(), 'acquisition': mode,
            }
            write_json(MANIFEST, manifest)
    return manifest


def records(connection, query):
    result = connection.execute(query)
    names = [column[0] for column in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def fingerprints(connection):
    # Two order-independent checksums plus counts detect changes without depending
    # on row order. They are a practical rerun check, not a uniqueness constraint.
    return {name: records(connection, f'''
        SELECT count(*) AS row_count,
               CAST(sum(CAST(hash(t) AS HUGEINT)) AS VARCHAR) AS hash_sum,
               CAST(bit_xor(hash(t)) AS VARCHAR) AS hash_xor
        FROM {name} t
    ''')[0] for name in TABLES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Use only saved raw files.')
    parser.add_argument('--verify-rerun', action='store_true',
                        help='Require identical input hashes and table fingerprints to the previous successful run.')
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    previous = json.loads(REPORT.read_text()) if REPORT.exists() else None
    if args.verify_rerun and (not previous or not previous.get('passed')):
        raise RuntimeError('--verify-rerun needs a previous successful ingestion report.')
    manifest = prepare_files(args.offline)
    source_hashes = {name: entry['sha256'] for name, entry in manifest['files'].items()}
    if args.verify_rerun and source_hashes != previous['source_hashes']:
        raise RuntimeError('Rerun verification requires the same source files.')

    connection = duckdb.connect(str(DATABASE))
    report = {'started_at_utc': now(), 'duckdb_version': duckdb.__version__,
              'source_hashes': source_hashes, 'passed': False}
    try:
        connection.execute('BEGIN TRANSACTION')
        connection.execute('SET VARIABLE player_files = ?',
                           [[str(RAW / f'stats_player_week_{year}.parquet') for year in SEASONS]])
        connection.execute('SET VARIABLE schedule_file = ?', [str(RAW / 'games.csv')])
        for filename in ('01_ingestion.sql', '02_validation.sql'):
            connection.execute((ROOT / 'sql' / filename).read_text())
        report['checks'] = records(connection, 'SELECT * FROM validation_checks ORDER BY check_name')
        report['season_counts'] = records(connection, 'SELECT * FROM season_row_counts ORDER BY season')
        report['fingerprints'] = fingerprints(connection)
        report['sample'] = records(connection, '''
            SELECT player_id, player_display_name, position, season, week, game_id,
                   team, opponent_team, game_date, round(fantasy_points_ppr, 2) AS ppr
            FROM clean_player_game_stats WHERE season=2025 AND week=1 AND position='QB'
            ORDER BY player_display_name LIMIT 5
        ''')
        report['raw_missing_id_details'] = records(connection, '''
            SELECT season, player_name, position, count(*) AS rows
            FROM raw_player_weekly_stats WHERE nullif(trim(player_id), '') IS NULL
            GROUP BY ALL ORDER BY season, player_name, position
        ''')
        report['rerun_identical'] = (
            previous['fingerprints'] == report['fingerprints']
            if previous and source_hashes == previous['source_hashes'] else None
        )
        errors = [check for check in report['checks']
                  if check['severity'] == 'ERROR' and check['problem_count']]
        if errors:
            raise RuntimeError(f'Validation failed: {errors}')
        if args.verify_rerun and not report['rerun_identical']:
            raise RuntimeError('Rerun changed row counts or table fingerprints.')
        connection.execute('COMMIT')
        report['passed'] = True
    except Exception as error:
        connection.execute('ROLLBACK')
        report['error'] = str(error)
        write_json(PROCESSED / 'last_failed_run.json', report)
        raise
    finally:
        connection.close()

    report['finished_at_utc'] = now()
    write_json(REPORT, report)
    print('\nSeason | Raw player rows | Clean player rows | REG games | Joined clean rows')
    for row in report['season_counts']:
        print(f"{row['season']} | {row['raw_player_rows']:>15,} | {row['clean_player_rows']:>17,}"
              f" | {row['regular_games']:>9} | {row['matched_clean_rows']:>17,}")
    print('\nValidation: PASSED (see warnings below, if any).')
    for check in report['checks']:
        if check['problem_count']:
            print(f"{check['severity']}: {check['check_name']} = {check['problem_count']}")
    print(f"Rerun identical to previous run: {report['rerun_identical']}")
    print(f'Database: {DATABASE}\nReport: {REPORT}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
