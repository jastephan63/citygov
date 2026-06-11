#!/usr/bin/env python3
"""Integrity validation for a citygov database (convention 10).

Checks, in order:
  1. PRAGMA foreign_key_check       -> no orphan / broken foreign keys
  2. duplicate join-table rows      -> service_requirement, requirement_legal_basis,
                                       field_mapping (the rows that, duplicated,
                                       silently inflate compliance scores)
  3. field_mapping coherence        -> classification vs requirement_id agreement
                                       (enforced by CHECK, re-checked defensively)
  4. dangling references            -> documents marked 'formular' must point at a
                                       form; non-formular docs must not.

Returns a list of error strings. Empty list == valid.
Used by commit_proposal.py before swapping, and runnable standalone:

    python3 scripts/validate_db.py [path-to.db]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect


def validate(conn):
    errors = []

    # 1. foreign keys
    for row in conn.execute("PRAGMA foreign_key_check").fetchall():
        errors.append(f"orphan FK: table={row[0]} rowid={row[1]} -> {row[2]}({row[3]})")

    # 2. duplicate join rows
    dup_checks = [
        ("service_requirement", "service_id, requirement_id"),
        ("requirement_legal_basis", "requirement_id, article_id"),
        ("field_mapping", "form_field_id"),
    ]
    for table, cols in dup_checks:
        q = (f"SELECT {cols}, count(*) c FROM {table} "
             f"GROUP BY {cols} HAVING c > 1")
        for row in conn.execute(q).fetchall():
            errors.append(f"duplicate rows in {table}: {tuple(row)}")

    # 3. classification / requirement_id coherence
    bad = conn.execute(
        "SELECT id, classification, requirement_id FROM field_mapping WHERE "
        "(requirement_id IS NOT NULL AND classification NOT IN "
        "  ('mapped','identity_part','reason_facet')) "
        "OR (requirement_id IS NULL AND classification NOT IN "
        "  ('form_mechanic','overcollection'))"
    ).fetchall()
    for row in bad:
        errors.append(f"field_mapping {row['id']}: classification "
                      f"'{row['classification']}' inconsistent with requirement_id "
                      f"{row['requirement_id']}")

    # 4. document <-> form linkage
    for row in conn.execute(
        "SELECT id, source_file, doc_type, form_id FROM document"
    ).fetchall():
        if row["doc_type"] == "formular" and row["form_id"] is None:
            errors.append(f"document '{row['source_file']}' is 'formular' but has no form_id")
        if row["doc_type"] != "formular" and row["form_id"] is not None:
            errors.append(f"document '{row['source_file']}' is '{row['doc_type']}' "
                          f"but points at a form")

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    if not os.path.exists(path):
        print(f"no database at {path}", file=sys.stderr)
        sys.exit(2)
    conn = connect(path)
    errors = validate(conn)
    conn.close()
    if errors:
        print(f"INVALID ({len(errors)} problem(s)):")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print(f"valid: {path}")


if __name__ == "__main__":
    main()
