#!/usr/bin/env python3
"""Run a SQL file against the saved database in read-only mode."""
import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sql_file', nargs='?', default=str(ROOT / 'sql' / '03_inspect.sql'))
    args = parser.parse_args()
    with duckdb.connect(str(ROOT / 'data' / 'processed' / 'nfl.duckdb'), read_only=True) as connection:
        # DuckDB parses the statements, so semicolons inside SQL strings are safe.
        for statement in connection.extract_statements(Path(args.sql_file).read_text()):
            connection.sql(statement.query).show(max_rows=50, max_width=180)


if __name__ == '__main__':
    main()
