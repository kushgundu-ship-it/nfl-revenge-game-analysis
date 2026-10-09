#!/usr/bin/env python3
"""Read-only validation of all stages and the dashboard; never rebuilds the DB."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASELINE = ROOT/'data/processed/stage5_preservation_baseline.json'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def snapshot():
    paths = [ROOT/'project.md', ROOT/'requirements.txt', ROOT/'docs/data_dictionary.md']
    paths += list((ROOT/'data/raw').glob('*'))
    paths += [ROOT/'data/processed'/name for name in ('nfl.duckdb', 'validation_report.json',
        'stage2_validation_report.json', 'stage3_validation_report.json', 'stage4_validation_report.json')]
    paths += list((ROOT/'reports/tables').glob('stage4_*.csv'))
    paths += [p for p in (ROOT/'sql').glob('*.sql') if int(p.name[:2]) <= 14]
    paths += [ROOT/'scripts'/name for name in ('load_data.py','query.py','build_stage2.py',
                                               'build_stage3.py','analyze_stage4.py')]
    paths += [ROOT/'tests'/f'test_stage{i}.py' for i in (2,3,4)]
    paths += [ROOT/'docs'/f'stage{i}_results.md' for i in (1,2,3,4)]
    return {str(p.relative_to(ROOT)):digest(p) for p in sorted(paths) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record-baseline', action='store_true',
                        help='Create a preservation record once, before presentation work.')
    args = parser.parse_args()
    if args.record_baseline:
        if BASELINE.exists():
            raise RuntimeError('Preservation baseline already exists; refusing to overwrite it.')
        BASELINE.write_text(json.dumps(snapshot(), indent=2)+'\n')
        print(f'Captured Stage 1–4 preservation hashes: {BASELINE}')
        return
    import duckdb
    from dashboard.data import Repository, load_bundle, validate_bundle
    before = snapshot()
    checks = []
    with duckdb.connect(str(ROOT/'data/processed/nfl.duckdb'), read_only=True) as c:
        c.execute('SET threads=1')
        for stage,view in ((1,'validation_checks'),(2,'stage2_validation_checks'),
                           (3,'stage3_validation_checks'),(4,'stage4_validation_checks')):
            for name,severity,count in c.execute(f'SELECT * FROM {view} ORDER BY check_name').fetchall():
                checks.append(dict(stage=stage,check=name,severity=severity,problems=count))
            print(f'Stage {stage}: SQL checks executed.', flush=True)
    repository = Repository()
    bundle = load_bundle(repository)
    dashboard_checks = validate_bundle(repository, bundle)
    for name in dashboard_checks:
        checks.append(dict(stage=5,check=name,severity='ERROR',problems=0))
    after = snapshot()
    unchanged = before == after
    preserved = after == json.loads(BASELINE.read_text()) if BASELINE.exists() else None
    failed = [x for x in checks if x['severity']=='ERROR' and x['problems']]
    report = dict(passed=not failed and unchanged and preserved is not False,
                  stage1_4_unchanged_during_validation=unchanged,
                  stage1_4_matches_pre_stage5_baseline=preserved,
                  protected_sha256=after,checks=checks)
    destination = ROOT/'reports/stage5_validation.json'
    destination.write_text(json.dumps(report,indent=2)+'\n')
    if not report['passed']:
        raise RuntimeError(f'Validation failed: see {destination}')
    print(f"Passed {sum(x['severity']=='ERROR' for x in checks)} error checks; preservation={preserved}.")
    print(f'Report: {destination}')


if __name__=='__main__':
    main()
