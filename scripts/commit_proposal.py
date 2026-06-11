#!/usr/bin/env python3
"""Idempotently commit a service-model proposal into citygov.db (conventions 8,10).

A proposal JSON fully describes one modelled service: the service, the laws and
articles that govern it, the requirements (deduped by data_point_key), the
service<->requirement links, the form that serves it, the form's actual fields
(law-blind), the field<->requirement mappings with their classification, process
steps, inventory documents, and any human-declared findings.

Safety wrapper:
  1. work on a *copy* of the DB (citygov.db.staging)
  2. upsert everything inside one transaction (every write checks-before-insert,
     so re-running the same proposal is a no-op)
  3. validate the staging copy (validate_db.validate)
  4. only if valid: atomically swap staging in. Otherwise abort, keep the source
     of truth untouched, and log the failure.

Usage:
    python3 scripts/commit_proposal.py proposals/anmeldung-wohnsitz.json
"""
import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, SCHEMA_PATH, connect, log
from validate_db import validate


# --- generic check-before-insert upsert ------------------------------------
def upsert(conn, table, key_cols, row):
    """Insert row (dict) if no row matches key_cols, else update non-key cols.
    Returns the row's rowid (== id for tables whose PK is `id`). Idempotent.
    Uses rowid so it also works on join tables that have no `id` column."""
    where = " AND ".join(f"{c} IS ?" for c in key_cols)
    keyvals = [row.get(c) for c in key_cols]
    existing = conn.execute(
        f"SELECT rowid FROM {table} WHERE {where}", keyvals
    ).fetchone()
    cols = list(row.keys())
    if existing:
        rid = existing[0]
        upd = [c for c in cols if c not in key_cols]
        if upd:
            conn.execute(
                f"UPDATE {table} SET {', '.join(c+'=?' for c in upd)} WHERE rowid=?",
                [row[c] for c in upd] + [rid],
            )
        return rid
    placeholders = ", ".join("?" for _ in cols)
    cur = conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
        [row[c] for c in cols],
    )
    return cur.lastrowid


def jdump(v):
    return json.dumps(v, ensure_ascii=False) if v is not None else None


def commit(conn, p):
    """Apply one proposal dict to an open connection. Returns a summary dict."""
    counts = {}
    def bump(k): counts[k] = counts.get(k, 0) + 1

    # 1. service
    s = p["service"]
    service_id = upsert(conn, "service", ["slug"], {
        "slug": s["slug"], "name": s["name"],
        "dienststelle": s.get("dienststelle"), "department": s.get("department"),
        "description": s.get("description"), "notes": s.get("notes"),
    }); bump("service")

    # 2. laws + articles  (article_ref -> article_id)
    article_ids = {}
    for law in p.get("laws", []):
        law_id = upsert(conn, "law", ["slug"], {
            "slug": law["slug"], "title": law["title"],
            "short_title": law.get("short_title"),
            "jurisdiction_level": law["jurisdiction_level"],
            "sr_number": law.get("sr_number"),
            "cantonal_ref": law.get("cantonal_ref"),
            "source_note": law.get("source_note"),
            "last_checked": law.get("last_checked", "UNVERIFIED"),
        }); bump("law")
        for art in law.get("articles", []):
            aid = upsert(conn, "article", ["law_id", "article_no", "heading"], {
                "law_id": law_id,
                "article_no": art.get("article_no", "UNKNOWN"),
                "heading": art.get("heading"),
                "text_excerpt": art.get("text_excerpt"),
                "last_checked": art.get("last_checked", "UNVERIFIED"),
            }); bump("article")
            article_ids[art["ref"]] = aid

    # 3. requirements (dedupe by data_point_key, conv 8) + legal basis
    requirement_ids = {}
    for req in p.get("requirements", []):
        existing = conn.execute(
            "SELECT id FROM requirement WHERE data_point_key=?",
            [req["data_point_key"]],
        ).fetchone()
        rid = upsert(conn, "requirement", ["data_point_key"], {
            "data_point_key": req["data_point_key"],
            "data_point": req["data_point"], "label": req.get("label"),
            "data_type": req.get("data_type"), "condition": req.get("condition"),
            "is_composite": 1 if req.get("is_composite") else 0,
            "notes": req.get("notes"),
        }); bump("requirement")
        if existing:
            log("commit.log", f"  reused existing requirement '{req['data_point_key']}' (conv 8)")
        requirement_ids[req["ref"]] = rid
        for lb in req.get("legal_basis", []):
            upsert(conn, "requirement_legal_basis", ["requirement_id", "article_id"], {
                "requirement_id": rid,
                "article_id": article_ids[lb["article_ref"]],
                "citation_detail": lb.get("citation_detail"),
                "last_checked": lb.get("last_checked", "UNVERIFIED"),
            }); bump("legal_basis")

    # 4. service <-> requirement
    for sr in p.get("service_requirements", []):
        upsert(conn, "service_requirement", ["service_id", "requirement_id"], {
            "service_id": service_id,
            "requirement_id": requirement_ids[sr["requirement_ref"]],
            "applicability_condition": sr.get("applicability_condition"),
        }); bump("service_requirement")

    # 5. form
    form_id = None
    if "form" in p:
        f = p["form"]
        form_id = upsert(conn, "form", ["slug"], {
            "slug": f["slug"], "service_id": service_id, "title": f["title"],
            "actual_purpose": f.get("actual_purpose"),
            "title_content_mismatch": 1 if f.get("title_content_mismatch") else 0,
            "mismatch_note": f.get("mismatch_note"),
            "source_file": f.get("source_file"), "file_type": f.get("file_type"),
            "publisher_dienststelle": f.get("publisher_dienststelle"),
            "last_extracted": f.get("last_extracted"),
        }); bump("form")

    # 6. form fields (field_ref -> form_field_id)
    field_ids = {}
    for fld in p.get("form_fields", []):
        fid = upsert(conn, "form_field", ["form_id", "field_key"], {
            "form_id": form_id, "field_key": fld["field_key"],
            "label": fld["label"], "section": fld.get("section"),
            "field_type": fld.get("field_type"),
            "options": jdump(fld.get("options")),
            "required": 1 if fld.get("required") else 0,
            "raw_order": fld.get("raw_order"), "notes": fld.get("notes"),
        }); bump("form_field")
        field_ids[fld["ref"]] = fid

    # 7. field mappings (the reconciliation layer)
    for m in p.get("field_mappings", []):
        req_ref = m.get("requirement_ref")
        upsert(conn, "field_mapping", ["form_field_id"], {
            "form_field_id": field_ids[m["form_field_ref"]],
            "requirement_id": requirement_ids[req_ref] if req_ref else None,
            "classification": m["classification"],
            "match_status": m.get("match_status", "proposed"),
            "mapped_by": m.get("mapped_by", "auto"),
            "confidence": m.get("confidence"),
            "notes": m.get("notes"),
        }); bump("field_mapping")

    # 8. process steps
    for st in p.get("process_steps", []):
        upsert(conn, "process_step", ["service_id", "step_no"], {
            "service_id": service_id, "step_no": st["step_no"],
            "description": st["description"], "mode": st.get("mode", "manual"),
            "notes": st.get("notes"),
        }); bump("process_step")

    # 9. inventory documents
    for d in p.get("documents", []):
        upsert(conn, "document", ["source_file"], {
            "source_file": d["source_file"], "file_name": d.get("file_name"),
            "department": d.get("department"), "dienststelle": d.get("dienststelle"),
            "doc_type": d["doc_type"], "formula_note": d.get("formula_note"),
            "classification_note": d.get("classification_note"),
            "form_id": form_id if (d.get("is_this_form") and d["doc_type"] == "formular") else None,
        }); bump("document")

    # 10. human-declared findings (idempotent by fingerprint)
    for fnd in p.get("findings", []):
        fp = fnd.get("fingerprint") or f"{fnd['type']}::{s['slug']}::{fnd['description'][:80]}"
        upsert(conn, "finding", ["fingerprint"], {
            "fingerprint": fp, "type": fnd["type"],
            "severity": fnd.get("severity", "info"),
            "service_id": service_id,
            "form_id": form_id if fnd.get("attach_form") else None,
            "law_id": None,
            "description": fnd["description"],
            "status": fnd.get("status", "open"),
            "created_at": fnd.get("created_at"),
        }); bump("finding")

    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proposal")
    args = ap.parse_args()

    with open(args.proposal, encoding="utf-8") as fh:
        proposal = json.load(fh)

    if not os.path.exists(DB_PATH):
        print("citygov.db missing — run scripts/init_db.py first", file=sys.stderr)
        sys.exit(2)

    staging = DB_PATH + ".staging"
    if os.path.exists(staging):
        os.remove(staging)
    shutil.copy2(DB_PATH, staging)

    conn = connect(staging)
    try:
        counts = commit(conn, proposal)
        conn.commit()
    except Exception as e:        # noqa: BLE001 — abort on any error
        conn.close()
        os.remove(staging)
        log("commit_errors.log", f"ABORT committing {args.proposal}: {e!r}")
        print(f"ABORT: {e!r}  (source of truth untouched)", file=sys.stderr)
        sys.exit(1)

    errors = validate(conn)
    conn.close()
    if errors:
        os.remove(staging)
        log("commit_errors.log",
            f"ABORT committing {args.proposal}: validation failed:\n  " +
            "\n  ".join(errors))
        print("ABORT: staging failed validation (source of truth untouched):",
              file=sys.stderr)
        for e in errors:
            print("  -", e, file=sys.stderr)
        sys.exit(1)

    os.replace(staging, DB_PATH)          # atomic swap
    print(f"committed {args.proposal}")
    print("  " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
