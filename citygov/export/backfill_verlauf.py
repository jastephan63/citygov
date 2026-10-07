#!/usr/bin/env python3
"""Reconstruct past snapshots of the key figures from the Git history of citygov.db.

For every day on which citygov.db was committed, the day's last version is read
from Git and measured with kennzahlen.db_kennzahlen — the same definition the
live build uses. Figures a version did not yet carry stay None. Entries are
marked «quelle: git <commit>»; an existing entry of the same day made by a live
build is kept (the live build is the more complete measurement). Idempotent.

    python3 scripts/backfill_verlauf.py
"""
import os, sqlite3, subprocess, tempfile
from citygov.core.common import ROOT
from citygov.core import kennzahlen


def main():
    log = subprocess.run(["git", "-C", ROOT, "log", "--format=%H %cs", "--", "citygov.db"],
                         capture_output=True, text=True, check=True).stdout.split("\n")
    last_of_day = {}
    for line in log:                       # newest first: the first seen per day is its last commit
        if line.strip():
            h, d = line.split()
            last_of_day.setdefault(d, h)
    doc = kennzahlen.load()
    live_days = {e["datum"] for e in doc["eintraege"] if not str(e.get("quelle", "")).startswith("git ")}
    n = 0
    for day, h in sorted(last_of_day.items()):
        if day in live_days:
            continue
        blob = subprocess.run(["git", "-C", ROOT, "cat-file", "-p", f"{h}:citygov.db"], capture_output=True, check=True).stdout
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(blob)
        try:
            k = kennzahlen.db_kennzahlen(sqlite3.connect(tmp.name))
        finally:
            os.unlink(tmp.name)
        if k:
            kennzahlen.upsert(doc, {"datum": day, "quelle": f"git {h[:7]}", **k})
            n += 1
    kennzahlen.save(doc)
    print(f"verlauf.json: {n} Stände aus der Git-Historie rekonstruiert, {len(doc['eintraege'])} Einträge insgesamt")


if __name__ == "__main__":
    main()
