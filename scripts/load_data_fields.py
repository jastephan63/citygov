#!/usr/bin/env python3
"""Load agent-derived data dictionaries into the data_field table.

Each JSON (scratchpad/df/<form_id>.json) is the logical data dictionary of one
form: consolidated data fields (enum with allowed_values, composite with
subfields, boolean, etc.), NOT raw widgets. Replaces the BASE field list of a form;
curated eCH/eSH/basis_typ/subjekt/citations/subfields/reviews are NOT preserved, so a
form that already carries them is refused unless --force is given. All rows of
a form being loaded are replaced. Staging -> validate -> swap.

    python3 scripts/load_data_fields.py <dir-of-json>
"""
import glob, json, os, shutil, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

TYPES = {"text", "date", "number", "money", "boolean", "enum", "multiselect",
         "composite", "attachment", "signature"}



def curated_layers(conn, fid):
    """Names of the curated layers that exist on a form's fields (empty = none)."""
    out = []
    cols = {r[1] for r in conn.execute("PRAGMA table_info(data_field)")}
    for col, label in (("ech_element_id", "eCH"), ("esh_code", "eSH"), ("basis_typ", "basis_typ"), ("subjekt", "subjekt")):
        if col in cols and conn.execute(f"SELECT 1 FROM data_field WHERE form_id=? AND {col} IS NOT NULL LIMIT 1", [fid]).fetchone():
            out.append(label)
    for tbl, sql in (("data_subfield", "SELECT 1 FROM data_subfield s JOIN data_field d ON d.id=s.data_field_id WHERE d.form_id=? LIMIT 1"),
                     ("data_field_legal_basis", "SELECT 1 FROM data_field_legal_basis b JOIN data_field d ON d.id=b.data_field_id WHERE d.form_id=? LIMIT 1"),
                     ("beilage", "SELECT 1 FROM beilage b JOIN data_field d ON d.id=b.data_field_id WHERE d.form_id=? LIMIT 1"),
                     ("panel_review", "SELECT 1 FROM panel_review p JOIN data_field d ON d.id=p.item_id AND p.kind IN ('basis','subjekt') WHERE d.form_id=? LIMIT 1")):
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", [tbl]).fetchone() and conn.execute(sql, [fid]).fetchone():
            out.append(tbl)
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "."
    staging = DB_PATH + ".staging"
    if os.path.exists(staging):
        os.remove(staging)
    shutil.copy2(DB_PATH, staging)
    conn = connect(staging)
    conn.execute("CREATE TABLE IF NOT EXISTS data_field (id INTEGER PRIMARY KEY, "
                 "form_id INTEGER NOT NULL REFERENCES form(id), ord INTEGER, name TEXT NOT NULL, "
                 "definition TEXT, data_type TEXT, required INTEGER DEFAULT 1, allowed_values TEXT, "
                 "subfields TEXT, format TEXT, source_widgets TEXT, derived_by TEXT DEFAULT 'agent')")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_data_field_form ON data_field(form_id)")
    nforms = nfields = 0
    for jf in sorted(glob.glob(os.path.join(src, "*.json"))):
        try:
            fid = int(os.path.splitext(os.path.basename(jf))[0])
            data = json.load(open(jf, encoding="utf-8"))
        except Exception:
            continue
        dfs = data.get("data_fields") if isinstance(data, dict) else None
        if not isinstance(dfs, list):
            continue
        if not conn.execute("SELECT 1 FROM form WHERE id=?", [fid]).fetchone():
            continue
        # replacing the field list drops everything curated on top of it (eCH,
        # eSH, basis_typ, subjekt, citations, subfields, reviews). Refuse unless
        # the caller says --force, so a re-run can never silently wipe a layer.
        curated = curated_layers(conn, fid)
        if curated and "--force" not in sys.argv:
            print(f"ABORT: form {fid} already carries curated layers ({', '.join(curated)}); "
                  f"re-run with --force to replace them", file=sys.stderr)
            conn.close(); os.remove(staging); sys.exit(1)
        conn.execute("DELETE FROM data_field_legal_basis WHERE data_field_id IN "
                     "(SELECT id FROM data_field WHERE form_id=?)", [fid])
        try:
            conn.execute("DELETE FROM data_field WHERE form_id=?", [fid])   # replace
        except sqlite3.IntegrityError as e:
            print(f"ABORT: form {fid}: rows still reference its fields ({e})", file=sys.stderr)
            conn.close(); os.remove(staging); sys.exit(1)
        for i, d in enumerate(dfs):
            if not isinstance(d, dict) or not (d.get("name") or "").strip():
                continue
            dt = (d.get("data_type") or "text").strip().lower()
            if dt not in TYPES:
                dt = "text"
            conn.execute(
                "INSERT INTO data_field(form_id,ord,name,definition,data_type,required,"
                "allowed_values,subfields,format,source_widgets,derived_by) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                [fid, i, str(d["name"]).strip()[:160], (d.get("definition") or "").strip()[:400],
                 dt, 0 if d.get("required") is False else 1,
                 json.dumps(d.get("allowed_values") or [], ensure_ascii=False),
                 json.dumps(d.get("subfields") or [], ensure_ascii=False),
                 (d.get("format") or "").strip()[:80],
                 json.dumps(d.get("source_widgets") or [], ensure_ascii=False), "agent"])
            nfields += 1
        nforms += 1
    conn.commit()
    errs = validate(conn)
    conn.close()
    if errs:
        os.remove(staging); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(staging, DB_PATH)
    print(f"loaded data dictionaries for {nforms} form(s), {nfields} data fields")


if __name__ == "__main__":
    main()
