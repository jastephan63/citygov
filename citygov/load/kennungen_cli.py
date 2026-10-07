#!/usr/bin/env python3
"""The command line of the permanent identifiers (python3 scripts/kennungen.py).

    python3 scripts/kennungen.py                       mint and update the table kennung
                                                       (staging -> validate -> swap)
    python3 scripts/kennungen.py --pruefen             the end-of-build check, read-only
    python3 scripts/kennungen.py --aufloesen <kennung> what an identifier names, read-only
    (--datum JJJJ-MM-TT, --abloesungen PATH, --erstausgabe: see main)

The identifiers themselves are core (citygov/core/kennungen.py, whose docstring
describes the scheme and the rules). This entry point runs the integrity gate
(checks.validate_db) on its staging copy, so it lives in load/; main() is moved
unchanged from core/kennungen.py.
"""
import json, os, re, shutil, sqlite3, sys
from datetime import date
from citygov.core.common import DB_PATH, connect
from citygov.core.kennungen import (ABLOESUNGEN, REIHENFOLGE, _has, abgleich, aufloesen, pruefen_aktuell,
                                    veroeffentlichte)


# ---- entry point ----------------------------------------------------------------------
def main(argv):
    from citygov.checks.validate_db import validate
    datum, abl = date.today().isoformat(), ABLOESUNGEN
    if "--aufloesen" in argv:
        k = argv[argv.index("--aufloesen") + 1]
        c = connect(DB_PATH)
        r = aufloesen(c, k)
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str) if r else f"{k}: nie vergeben")
        return 0 if r else 1
    if "--pruefen" in argv:                   # read-only: the end-of-build check
        c = connect(DB_PATH)
        errs = pruefen_aktuell(c)
        n = c.execute("SELECT COUNT(*) FROM kennung WHERE status='aktiv'").fetchone()[0] if not errs else 0
        c.close()
        if errs:
            print("ABBRUCH Kennungen:", *errs[:8], sep="\n  ")
            return 1
        print(f"Kennungen geprüft: {n} aktiv, jedes Objekt hat genau eine, jede nennt ihr Objekt")
        return 0
    if "--datum" in argv:
        datum = argv[argv.index("--datum") + 1]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", datum):
            sys.exit("ABBRUCH: --datum JJJJ-MM-TT")
    if "--abloesungen" in argv:
        abl = argv[argv.index("--abloesungen") + 1]
    # never mint into a lost registry: a missing or empty table is a first issue only on
    # purpose, and never once identifiers are published
    c0 = connect(DB_PATH)
    leer = not _has(c0, "kennung") or not c0.execute("SELECT COUNT(*) FROM kennung").fetchone()[0]
    c0.close()
    if leer:
        veroeff = veroeffentlichte()
        if veroeff:
            sys.exit(f"ABBRUCH kennungen.py — nichts geschrieben: die Tabelle kennung fehlt oder ist leer, das "
                     f"veröffentlichte data_export.json trägt aber {len(veroeff)} Kennungen. Neu vergeben hiesse, "
                     "dieselben Zeichenketten anderen Objekten zu geben — citygov.db mit der Tabelle wiederherstellen.")
        if "--erstausgabe" not in argv:
            sys.exit("ABBRUCH kennungen.py — nichts geschrieben: die Tabelle kennung fehlt oder ist leer. Die erste "
                     "Vergabe geschieht nur ausdrücklich: python3 scripts/kennungen.py --erstausgabe")
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    try:
        stat, karten = abgleich(c, datum, abl)
        c.commit()
        errs = list(dict.fromkeys(validate(c) + pruefen_aktuell(c)))
    except (RuntimeError, sqlite3.DatabaseError) as ex:
        c.close(); os.remove(st)
        sys.exit(f"ABBRUCH kennungen.py — nichts geschrieben: {ex}")
    n_akt = {art: len(karten[art]) for art in REIHENFOLGE}
    n_alle = dict(c.execute("SELECT status, COUNT(*) FROM kennung GROUP BY 1").fetchall())
    c.close()
    if errs:
        os.remove(st)
        print("ABBRUCH kennungen.py — nichts geschrieben:", *errs[:8], sep="\n  ")
        return 1
    geaendert = any(stat.values())
    if not geaendert:
        os.remove(st)
    else:
        os.replace(st, DB_PATH)
    print(f"Kennungen: {sum(n_akt.values())} aktiv (" + ", ".join(f"{a} {n_akt[a]}" for a in REIHENFOLGE) + ")"
          + f"; entfallen {n_alle.get('entfallen', 0)}, abgelöst {n_alle.get('abgeloest', 0)}")
    if geaendert:
        print("  geändert: " + ", ".join(f"{k} {v}" for k, v in stat.items() if v)
              + " — geschrieben" + (f" (Vergabedatum {datum})" if stat["neu"] else ""))
    else:
        print("  keine Änderung — nichts geschrieben")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
