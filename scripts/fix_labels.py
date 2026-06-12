#!/usr/bin/env python3
"""Apply clean_label() to labels already in citygov.db (no re-extraction needed).

Cleans technical AcroForm names (e.g. 'personalien.versichertennummer1' ->
'Versichertennummer 1') on form_field.label and the matching requirement
data_point/label. Safe to re-run. Operates on a staging copy, validates, swaps.

    python3 scripts/fix_labels.py
"""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from auto_draft import clean_label
from validate_db import validate


def main():
    staging = DB_PATH + ".staging"
    if os.path.exists(staging): os.remove(staging)
    shutil.copy2(DB_PATH, staging)
    conn = connect(staging)
    nf = nr = 0
    for tbl, cols in [("form_field", ["label"]), ("requirement", ["data_point", "label"])]:
        rows = conn.execute(f"SELECT id, {', '.join(cols)} FROM {tbl}").fetchall()
        for r in rows:
            updates = {}
            for col in cols:
                old = r[col]
                new = clean_label(old)
                if new != old:
                    updates[col] = new
            if updates:
                conn.execute(f"UPDATE {tbl} SET {', '.join(c+'=?' for c in updates)} WHERE id=?",
                             list(updates.values()) + [r["id"]])
                if tbl == "form_field": nf += 1
                else: nr += 1
    conn.commit()
    errs = validate(conn); conn.close()
    if errs:
        os.remove(staging); print("ABORT:", *errs[:5], sep="\n  ", file=sys.stderr); sys.exit(1)
    os.replace(staging, DB_PATH)
    print(f"cleaned {nf} field labels, {nr} requirement labels")


if __name__ == "__main__":
    main()
