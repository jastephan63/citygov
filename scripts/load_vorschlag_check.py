#!/usr/bin/env python3
"""Quality pass on the proposed terms (one datum, one name).

The first naming panel could only choose among an element's OWN labels, so a
proposal sometimes bundled data itself («Postleitzahl, Ort» for a postcode).
This pass decides per element:

  sauber     keep the proposal
  ersetzen   use a cleaner term — it must occur somewhere in the canton's
             forms (never invented); the old proposal label is reclassified
             (variante / pruefen+aufteilen / pruefen+zuordnung)
  vorbehalt  no clean term exists anywhere: keep it, flagged as provisional

Gates: element must have a proposal; a replacement must match (normalised) a
label that occurs in data_field or data_subfield; vocabulary; a reason.
Run AFTER load_begriffe.py and load_pruefart.py (both rebuild their rows).
Staging -> validate -> swap.

    python3 scripts/load_vorschlag_check.py <dir-with-out_*.json>
"""
import glob, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect, norm_label as norm
from validate_db import validate

ALT = {"variante": ("variante", None), "rolle": ("rolle", None),
       "pruefen_aufteilen": ("pruefen", "aufteilen"), "pruefen_zuordnung": ("pruefen", "zuordnung")}



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
    cols = {r[1] for r in c.execute("PRAGMA table_info(begriff_vorschlag)")}
    for col, typ in (("vorbehalt", "INTEGER NOT NULL DEFAULT 0"), ("herkunft", "TEXT"), ("pruefung", "TEXT")):
        if col not in cols:
            c.execute(f"ALTER TABLE begriff_vorschlag ADD COLUMN {col} {typ}")
    c.execute("UPDATE begriff_vorschlag SET vorbehalt=0, herkunft='eigen', pruefung=NULL")
    corpus = {}
    for r in c.execute("SELECT name FROM data_field UNION SELECT name FROM data_subfield"):
        if r[0] and r[0].strip():
            corpus.setdefault(norm(r[0]), r[0].strip())
    have = {r[0]: r[1] for r in c.execute("SELECT ech_element_id, term FROM begriff_vorschlag")}
    n = rej = 0
    counts = {"sauber": 0, "ersetzen": 0, "vorbehalt": 0}
    for jf in sorted(glob.glob(f"{src}/out_*.json")):
        for u in json.load(open(jf, encoding="utf-8")).get("urteile", []):
            eid, ur, gr = u.get("element_id"), u.get("urteil"), (u.get("grund") or "").strip()
            if eid not in have or ur not in counts or len(gr) < 6:
                rej += 1; continue
            if ur == "sauber":
                c.execute("UPDATE begriff_vorschlag SET pruefung=? WHERE ech_element_id=?", [gr[:240], eid])
            elif ur == "vorbehalt":
                c.execute("UPDATE begriff_vorschlag SET vorbehalt=1, pruefung=? WHERE ech_element_id=?", [gr[:240], eid])
            else:
                new = norm(u.get("vorschlag"))
                alt = ALT.get(u.get("alt_klasse") or "")
                if new not in corpus or not alt or new == norm(have[eid]):
                    rej += 1; continue
                own = {r[0] for r in c.execute("SELECT label_norm FROM begriff_label WHERE ech_element_id=?", [eid])}
                old = norm(have[eid])
                # the old proposal label becomes what the check says it is
                c.execute("UPDATE begriff_label SET klasse=?, pruefart=?, pruefart_grund=CASE WHEN ? IS NULL THEN pruefart_grund ELSE ? END, "
                          "grund=? WHERE ech_element_id=? AND label_norm=?",
                          [alt[0], alt[1], alt[1], gr[:240], gr[:240], eid, old])
                if new in own:
                    c.execute("UPDATE begriff_label SET klasse='vorschlag', pruefart=NULL, grund=NULL "
                              "WHERE ech_element_id=? AND label_norm=?", [eid, new])
                c.execute("UPDATE begriff_vorschlag SET term=?, herkunft=?, pruefung=? WHERE ech_element_id=?",
                          [corpus[new], "eigen" if new in own else "korpus", "Zweitprüfung: " + gr[:220], eid])
            counts[ur] += 1; n += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Vorschlag-Prüfung: {n} Urteile {counts}, {len(have) - n} ohne Urteil, {rej} REJECTED")


if __name__ == "__main__":
    main()
