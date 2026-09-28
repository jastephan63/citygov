#!/usr/bin/env python3
"""Apply the reviewed reader wording to the databank's own explanations.

In everyday German «Datum» is a calendar date. The databank's explanations
often used it for «a piece of data» («Gleiches Datum; …»), which readers take
as «same date». quellen/wortwahl_datum.json holds, per text as the website
shows it, the reviewed rewrite («Gleiche Angabe; …») or the verdict that
«Datum» there really is a calendar date (list «behalten»). Every entry was
judged by one reviewer and re-checked by a second.

Scope: the texts the databank writes itself and the website shows —
begriff_label (grund, pruefart_grund, rolle), begriff_vorschlag (begruendung,
pruefung), data_field (definition, basis_begruendung), and exact fragments
of the guided flows (formflow.flow, list «flow_teiltexte»). Quotes from forms,
laws, eCH, DVSH and SHEP are never touched.

Replacement is exact and whole-text: a text changes only when it equals an
«alt» entry (compared after common.klartext, which is how the website shows
the naming texts). Idempotent. Staging -> validate -> swap.

The naming chain (scripts/run_begriffe.py) rebuilds those texts from the
panel outputs and therefore runs this script as its last step. export_json.py
refuses to export a naming or basis text that still says «Datum» without a
verdict here, so a new text cannot slip through unreviewed.

    python3 scripts/apply_wortwahl.py
"""
import json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect, klartext
from validate_db import validate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "quellen", "wortwahl_datum.json")
DATUM = re.compile(r"\bDatums?\b")

# (table, text column, shown through klartext?)
SPALTEN = [
    ("begriff_label", "grund", True),
    ("begriff_label", "pruefart_grund", True),
    ("begriff_label", "rolle", False),
    ("begriff_vorschlag", "begruendung", True),
    ("begriff_vorschlag", "pruefung", True),
    ("data_field", "definition", False),
    ("data_field", "basis_begruendung", False),
]


def lade():
    K = json.load(open(SRC, encoding="utf-8"))
    ersetzen = {e["alt"]: e["neu"] for e in K["ersetzen"]}
    behalten = set(K["behalten"])
    for a, n in ersetzen.items():
        if a == n or not n.strip():
            sys.exit(f"ABBRUCH: leere oder unveränderte Ersetzung: {a[:80]}")
        if "ß" in n:
            sys.exit(f"ABBRUCH: «ß» in der Ersetzung: {n[:80]}")
    doppelt = behalten & set(ersetzen)
    if doppelt:
        sys.exit(f"ABBRUCH: sowohl behalten als auch ersetzt: {sorted(doppelt)[:3]}")
    return ersetzen, behalten


def offen(texte, behalten):
    """Texts that still say «Datum» without a verdict (as the website shows them)."""
    return sorted({t for t in texte if t and DATUM.search(t) and t not in behalten})


def main():
    ersetzen, behalten = lade()
    FLOW = json.load(open(SRC, encoding="utf-8")).get("flow_teiltexte", [])
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    n = {}
    for tab, col, kl in SPALTEN:
        for r in c.execute(f'SELECT rowid AS k, "{col}" AS v FROM {tab} WHERE "{col}" LIKE \'%Datum%\'').fetchall():
            gezeigt = klartext(r["v"]) if kl else r["v"]
            neu = ersetzen.get(gezeigt)
            if neu is not None and neu != r["v"]:
                c.execute(f'UPDATE {tab} SET "{col}"=? WHERE rowid=?', [neu, r["k"]])
                n[f"{tab}.{col}"] = n.get(f"{tab}.{col}", 0) + 1
    # exact fragments inside a guided flow (formflow.flow is JSON; the fragment sits inside one string value)
    for e in FLOW:
        r = c.execute("SELECT rowid AS k, flow FROM formflow WHERE form_id=?", [e["form_id"]]).fetchone()
        alt, neu = json.dumps(e["alt"], ensure_ascii=False)[1:-1], json.dumps(e["neu"], ensure_ascii=False)[1:-1]
        if not r:
            sys.exit(f"ABBRUCH: kein Flow für Formular {e['form_id']}")
        k = r["flow"].count(alt)
        if k == 1:
            c.execute("UPDATE formflow SET flow=? WHERE rowid=?", [r["flow"].replace(alt, neu), r["k"]])
            n["formflow.flow"] = n.get("formflow.flow", 0) + 1
        elif not (k == 0 and neu in r["flow"]):
            sys.exit(f"ABBRUCH: Flow {e['form_id']}: «{e['alt'][:60]}» {k}× gefunden — Flow prüfen")
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st)
        print("ABORT:", *errs[:5], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    for k, v in sorted(n.items()):
        print(f"  {k}: {v} Zeile(n) umformuliert")
    if not n:
        print("  nichts zu ändern (bereits angewandt)")


if __name__ == "__main__":
    main()
