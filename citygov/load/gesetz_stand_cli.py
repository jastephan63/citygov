#!/usr/bin/env python3
"""The command line and the write side of the law editions (python3 scripts/gesetz_stand.py).

erheben() reads the PDF of every law (extract_law.extract_text, macOS PDFKit, unless
another reader is passed) and main() derives, compares and writes what differs
(staging -> validate -> swap), or with --trocken, --zeigen and --pruefen only reports.
The read side — the evidence rules, zeile(), the gate pruefen() and what the export
reads — stays in citygov/domain/gesetz_stand.py, whose docstring describes the table
and the commands; erheben() and main() are moved from there unchanged.
"""
import argparse
import datetime
import json
import os
import shutil
import sys

from citygov.core.common import DB_PATH, connect
from citygov.domain.gesetz_stand import (GESETZE_DIR, SPALTEN, TABELLE, _ohne_tag, datei_waehlen, gesetzes_index,
                                         gespeichert, pruefen, tabelle_sql, zeile, zitierte_artikel,
                                         zusammenfassung)


def erheben(conn, index=None, pdf_text=None):
    """{law_id: row} for every law of the databank. pdf_text(path) -> str is the text
    reader (default: extract_law.extract_text, macOS PDFKit)."""
    if pdf_text is None:
        from citygov.load.extract_law import extract_text as pdf_text
    index = gesetzes_index() if index is None else index
    gesetze = conn.execute("SELECT id, jurisdiction_level, sr_number, cantonal_ref, source_note "
                           "FROM law ORDER BY id").fetchall()
    texte = {}
    for law in gesetze:
        rel = datei_waehlen(law, index)[0]
        if rel and rel not in texte:
            texte[rel] = pdf_text(os.path.join(GESETZE_DIR, rel)) or ""
    if texte and not any(texte.values()):
        raise RuntimeError("keine einzige Gesetzesdatei ergab Text (Textauszug braucht macOS PDFKit, "
                           "siehe extract_law.py) — nichts geschrieben")
    zitiert = zitierte_artikel(conn)
    return {law["id"]: zeile(conn, law, index, texte, zitiert) for law in gesetze}


def main():
    ap = argparse.ArgumentParser(description="Gesetzesstand je Gesetz erheben (Tabelle gesetz_stand).")
    ap.add_argument("--trocken", action="store_true", help="erheben und berichten, nichts schreiben")
    ap.add_argument("--zeigen", metavar="GESETZ", help="eine gespeicherte Zeile zeigen (law id, SHR oder SR)")
    ap.add_argument("--pruefen", action="store_true", help="nur die Prüfregeln auf citygov.db anwenden")
    args = ap.parse_args()
    if not os.path.isfile(DB_PATH):
        sys.exit(f"ABBRUCH: keine Databank unter {DB_PATH}")
    conn = connect(DB_PATH)
    if args.pruefen:
        f = pruefen(conn)
        print("\n".join(f) if f else "gesetz_stand / gesetz_stand_pruefung: gültig")
        sys.exit(1 if f else 0)
    if args.zeigen:
        q = args.zeigen.replace("SHR", "").replace("SR", "").strip()
        r = conn.execute(f"SELECT g.* FROM {TABELLE} g JOIN law l ON l.id=g.law_id WHERE CAST(l.id AS TEXT)=? "
                         "OR replace(l.cantonal_ref,'SHR ','')=? OR l.sr_number=?", [q, q, q]).fetchone()
        print(json.dumps(dict(r), ensure_ascii=False, indent=1) if r else "keine Zeile")
        return
    try:
        neu = erheben(conn)
    except RuntimeError as ex:
        sys.exit(f"ABBRUCH gesetz_stand.py: {ex}")
    alt, ddl_alt = gespeichert(conn)
    tabelle_fehlt = alt is None
    alt = alt or {}
    ddl = tabelle_sql()
    ddl_anders = not tabelle_fehlt and ddl_alt != ddl
    dazu = [i for i in neu if i not in alt]
    anders = [i for i in neu if i in alt and _ohne_tag(alt[i]) != _ohne_tag(neu[i])]
    weg = sorted(set(alt) - set(neu))
    heute = datetime.date.today().isoformat()
    for i in neu:
        neu[i]["erhoben_am"] = heute if (i in dazu or i in anders) else alt[i]["erhoben_am"]
    for z in zusammenfassung(neu, conn):
        print(z)
    print(f"Zeilen: {len(dazu)} neu, {len(anders)} geändert, "
          f"{len(neu) - len(dazu) - len(anders)} unverändert, {len(weg)} entfernt")
    for i in sorted(anders)[:10]:
        diff = [k for k in SPALTEN if k != "erhoben_am" and alt[i].get(k) != neu[i].get(k)]
        print(f"  geändert law {i}: {', '.join(diff)}")
    conn.close()
    if args.trocken:
        print("--trocken: nichts geschrieben")
        return
    if not (dazu or anders or weg or ddl_anders):
        print("nichts zu tun — citygov.db bleibt unverändert")
        return
    from citygov.checks.validate_db import validate
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    if tabelle_fehlt:
        c.execute(ddl)
    elif ddl_anders:                                     # same columns, new wording: rebuild with the same rows
        c.execute(f"ALTER TABLE {TABELLE} RENAME TO {TABELLE}_alt")
        c.execute(ddl)
        c.execute(f"INSERT INTO {TABELLE} ({', '.join(SPALTEN)}) SELECT {', '.join(SPALTEN)} FROM {TABELLE}_alt")
        c.execute(f"DROP TABLE {TABELLE}_alt")
        print(f"  Tabellendefinition von {TABELLE} aus schema.sql übernommen (Zeilen unverändert)")
    for i in weg:
        c.execute(f"DELETE FROM {TABELLE} WHERE law_id=?", [i])
    for i in sorted(dazu + anders):
        c.execute(f"INSERT OR REPLACE INTO {TABELLE} ({', '.join(SPALTEN)}) VALUES ({', '.join('?' * len(SPALTEN))})",
                  [neu[i][k] for k in SPALTEN])
    c.commit()
    errs = validate(c) + pruefen(c)
    n = c.execute(f"SELECT COUNT(*) FROM {TABELLE}").fetchone()[0]
    c.close()
    if errs:
        os.remove(st)
        print("ABORT:", *errs[:8], sep="\n  ")
        sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"geschrieben: {TABELLE} hat jetzt {n} Zeilen")


if __name__ == "__main__":
    main()
