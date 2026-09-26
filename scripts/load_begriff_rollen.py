#!/usr/bin/env python3
"""Re-judge the labels that were demoted when a proposed term changed.

The term check replaced proposals and pushed the old proposal label to
«variante» without asking whether it names a role («TeilhaberIn 2»,
«Adresse bisher»). A panel with a sceptical review re-judged each of them:
variante | rolle (with the role) | pruefen with pruefart aufteilen|zuordnung.
Gates: the (element, label) row must exist; vocabulary; a role text for
rolle and a pruefart for pruefen. Part of scripts/run_begriffe.py.

    python3 scripts/load_begriff_rollen.py <dir-with-out_0.json/verify_0.json>
"""
import json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect, norm_label as norm
from validate_db import validate



def main():
    if os.environ.get("BEGRIFFE_CHAIN") != "1":
        sys.exit("Dieser Schritt baut auf den vorherigen auf und darf nicht allein laufen — "
                 "bitte scripts/run_begriffe.py verwenden.")
    src = sys.argv[1]
    verdicts = {}
    for name in ("out_0.json", "verify_0.json"):
        path = os.path.join(src, name)
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding="utf-8"))
        for u in d.get("urteile") or d.get("korrekturen") or []:
            verdicts[(u.get("element_id"), norm(u.get("label")))] = (u, name.startswith("verify"))
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    n = rej = 0
    counts = {}
    for (eid, ln), (u, rev) in verdicts.items():
        kl, rolle, pa, gr = u.get("klasse"), u.get("rolle"), u.get("pruefart"), (u.get("grund") or "").strip()
        ok = c.execute("SELECT klasse FROM begriff_label WHERE ech_element_id=? AND label_norm=?", [eid, ln]).fetchone()
        if (not ok or ok[0] == "vorschlag" or kl not in ("variante", "rolle", "pruefen") or len(gr) < 6
                or (kl == "rolle" and not rolle) or (kl == "pruefen" and pa not in ("aufteilen", "zuordnung"))):
            rej += 1; continue
        c.execute("UPDATE begriff_label SET klasse=?, rolle=?, pruefart=?, pruefart_grund=?, grund=? "
                  "WHERE ech_element_id=? AND label_norm=?",
                  [kl, rolle if kl == "rolle" else None, pa if kl == "pruefen" else None,
                   gr[:240] if kl == "pruefen" else None, ("Zweitprüfung: " if rev else "") + gr[:230], eid, ln])
        counts[kl] = counts.get(kl, 0) + 1; n += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"Rollen-Nachprüfung: {n} Bezeichnungen neu eingeordnet {counts}, {rej} REJECTED")


if __name__ == "__main__":
    main()
