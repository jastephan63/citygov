#!/usr/bin/env python3
"""For every label classified «prüfen»: which action fixes it.

  aufteilen  the field bundles several data the standard keeps apart
             ("Strasse und Nr", "PLZ und Ort") -> split the FORM field
  zuordnung  the label asks for a different datum than the element
             ("Beschäftigungsgrad" on the type of employment) -> correct the
             DATABANK's eCH assignment

Gate: (element, label) must be a 'pruefen' row of begriff_label; vocabulary;
a reason. Idempotent. Staging -> validate -> swap.

    python3 scripts/load_pruefart.py <dir-with-out_*.json>
"""
import glob, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect, norm_label as norm
from validate_db import validate



def main():
    if os.environ.get("BEGRIFFE_CHAIN") != "1":
        sys.exit("Dieser Schritt baut auf den vorherigen auf und darf nicht allein laufen — "
                 "bitte scripts/run_begriffe.py verwenden.")
    src = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    cols = {r[1] for r in c.execute("PRAGMA table_info(begriff_label)")}
    if "pruefart" not in cols:
        c.execute("ALTER TABLE begriff_label ADD COLUMN pruefart TEXT")
        c.execute("ALTER TABLE begriff_label ADD COLUMN pruefart_grund TEXT")
    c.execute("UPDATE begriff_label SET pruefart=NULL, pruefart_grund=NULL")
    ok = {(r[0], r[1]) for r in c.execute("SELECT ech_element_id, label_norm FROM begriff_label WHERE klasse='pruefen'")}
    n = rej = 0
    counts = {"aufteilen": 0, "zuordnung": 0}
    for jf in sorted(glob.glob(f"{src}/out_*.json")):
        for u in json.load(open(jf, encoding="utf-8")).get("urteile", []):
            key = (u.get("element_id"), norm(u.get("label")))
            pa, gr = u.get("pruefart"), (u.get("grund") or "").strip()
            if key not in ok or pa not in counts or len(gr) < 6:
                rej += 1; continue
            c.execute("UPDATE begriff_label SET pruefart=?, pruefart_grund=? WHERE ech_element_id=? AND label_norm=?",
                      [pa, gr[:240], key[0], key[1]])
            counts[pa] += 1; n += 1
    missing = len(ok) - n
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Prüfart: {n} entschieden {counts}, {missing} ohne Entscheid, {rej} REJECTED")


if __name__ == "__main__":
    main()
