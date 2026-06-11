#!/usr/bin/env python3
"""Create a fresh citygov.db from schema.sql.

Idempotent: schema uses CREATE TABLE IF NOT EXISTS, so re-running never destroys
data. Pass --force to delete and recreate an empty database.

    python3 scripts/init_db.py [--force]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, SCHEMA_PATH, connect


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="delete existing citygov.db and recreate empty")
    args = ap.parse_args()

    if args.force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"removed existing {DB_PATH}")

    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        ddl = fh.read()

    conn = connect(DB_PATH)
    conn.executescript(ddl)
    conn.execute(
        "INSERT INTO meta(key,value) VALUES('schema_version','1') "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
    )
    conn.commit()
    n = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table'"
    ).fetchone()[0]
    conn.close()
    print(f"initialised {DB_PATH}  ({n} tables)")


if __name__ == "__main__":
    main()
