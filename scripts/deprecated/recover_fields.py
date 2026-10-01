#!/usr/bin/env python3
"""Recover a well-modelled data-field set from a backup onto a form whose own
extraction is deficient.

Needed when dedup keeps the CURRENT edition of a Formular (the right catalogue
entry) but that edition's file extracted poorly, while the superseded edition we
dropped had a full, legally grounded field set for the same document. Copying is
only honest when both editions really are the same form — verify the sections
first, and pass --skip for fields the newer edition no longer has.

    python3 scripts/recover_fields.py <backup.db> <src-form-id> <dst-service-id> \
        [--skip=Fax,Telefax] [--apply]
"""
import os, shutil, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

COLS = ("ord", "name", "definition", "data_type", "required", "allowed_values",
        "subfields", "format", "source_widgets", "derived_by", "no_basis", "sensitive",
        "ech_element_id", "ech_status", "ech_standard_code")


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    bpath, sfid, dsid = pos[0], int(pos[1]), int(pos[2])
    apply = "--apply" in sys.argv
    skip = []
    for a in sys.argv:
        if a.startswith("--skip"):
            skip = [x.strip().lower() for x in a.split("=", 1)[-1].split(",") if x.strip()]

    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    b = sqlite3.connect(bpath); b.row_factory = sqlite3.Row

    dst = c.execute("SELECT id FROM form WHERE service_id=? ORDER BY id LIMIT 1", [dsid]).fetchone()
    if not dst:
        print(f"ABORT: Service #{dsid} hat kein Formular"); sys.exit(1)
    dfid = dst["id"]

    src = [dict(r) for r in b.execute("SELECT * FROM data_field WHERE form_id=? ORDER BY ord", [sfid])]
    src = [r for r in src if not any(s in (r["name"] or "").lower() for s in skip)]
    if not src:
        print("ABORT: keine Quellfelder"); sys.exit(1)

    old = [r["id"] for r in c.execute("SELECT id FROM data_field WHERE form_id=?", [dfid])]
    print(f"Ziel: Formular #{dfid} (Service #{dsid}) — {len(old)} bisherige Felder werden "
          f"durch {len(src)} aus dem Backup ersetzt")
    if skip:
        print(f"  übersprungen (nicht mehr in der neuen Fassung): {', '.join(skip)}")
    for r in src[:6]:
        print(f"    + {r['name'][:58]} [{r['data_type']}]")
    if not apply:
        c.close(); os.remove(st); print("(dry-run — pass --apply)"); return

    for did in old:
        c.execute("DELETE FROM data_subfield WHERE data_field_id=?", [did])
        c.execute("DELETE FROM data_field_legal_basis WHERE data_field_id=?", [did])
    c.execute("DELETE FROM data_field WHERE form_id=?", [dfid])

    nlb = 0
    for r in src:
        vals = [r[k] for k in COLS]
        c.execute(f"INSERT INTO data_field(form_id,{','.join(COLS)}) "
                  f"VALUES(?,{','.join('?' * len(COLS))})", [dfid] + vals)
        new = c.execute("SELECT last_insert_rowid() i").fetchone()["i"]
        for lb in b.execute("SELECT * FROM data_field_legal_basis WHERE data_field_id=?", [r["id"]]):
            # only carry a citation whose article still exists here
            if not c.execute("SELECT 1 FROM article WHERE id=?", [lb["article_id"]]).fetchone():
                continue
            c.execute("INSERT INTO data_field_legal_basis(data_field_id,article_id,relation,"
                      "citation_detail,last_checked) VALUES(?,?,?,?,?)",
                      [new, lb["article_id"], lb["relation"], lb["citation_detail"], lb["last_checked"]])
            nlb += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"übernommen: {len(src)} Datenfelder, {nlb} Rechtsgrundlagen-Zitate")


if __name__ == "__main__":
    main()
