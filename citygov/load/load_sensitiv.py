#!/usr/bin/env python3
"""Load which data fields are besonders schützenswerte Personendaten (KDSG Art. 2
Abs. 1 lit. d) — data_field.sensitive, one category key of labels.SENS.

The mark drives the ⛨ badge, the DSFA indication, the «Art. 5 offen» rule for
fields whose basis is only «aufgabennotwendig», the stricter rules in the
Datenhandhabung profile and encryption in the Datentresor. It was set once for
the Formulare before 2026-09 and had no loader since; this one adds it for the
fields a panel judged (with a sceptical second review), from <dir>/out_*.json:

    {"felder": [{"id": <data_field id>, "kategorie": "<SENS key>" | null, "beleg": "…"}]}

A null kategorie records «not sensitive» and changes nothing. Gates: the field
exists; the category is a key of labels.SENS; the evidence is not empty; a field
that already carries a category is left as it is (a curated mark is never
overwritten here). Staging -> validate -> swap.

    python3 scripts/load_sensitiv.py <dir>
"""
import glob, json, os, shutil, sys
from citygov.core.common import DB_PATH, connect
from citygov.core.labels import SENS
from citygov.checks.validate_db import validate


def main():
    src = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    n = keep = 0
    rej = []
    for jf in sorted(glob.glob(os.path.join(src, "out_*.json"))):
        for f in json.load(open(jf, encoding="utf-8")).get("felder", []):
            fid, kat = f.get("id"), f.get("kategorie")
            if kat is None:
                continue
            r = c.execute("SELECT sensitive FROM data_field WHERE id=?", [fid]).fetchone()
            if not r:
                rej.append(f"Feld {fid} fehlt"); continue
            if kat not in SENS:
                rej.append(f"Feld {fid}: Kategorie {kat!r}"); continue
            if not (f.get("beleg") or "").strip():
                rej.append(f"Feld {fid}: ohne Beleg"); continue
            if r[0] not in (None, ""):
                keep += 1; continue
            c.execute("UPDATE data_field SET sensitive=? WHERE id=?", [kat, fid])
            n += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"sensitive: {n} Felder markiert, {keep} schon markiert (unverändert), {len(rej)} abgewiesen")
    for r in rej[:10]:
        print("   ", r)


if __name__ == "__main__":
    main()
