#!/usr/bin/env python3
"""The command line of the Gestaltung comparison (python3 scripts/gestaltung_export.py):
the overview, one Formular (--form), both results as JSON (--json) and the self-test
(--selbsttest).

_eingabe() builds the export in memory with export_json.build (nothing is written), so
the entry point lives in export/; the comparison, the printing helpers and the self-test
stay in citygov/domain/gestaltung_export.py, whose docstring describes them. _eingabe
and main are moved from there unchanged.
"""
import argparse
import json
import sqlite3
import sys

from citygov.core.common import DB_PATH
from citygov.domain.gestaltung_export import _berechnen, _drucke_formular, _drucke_uebersicht, _selbsttest


def _eingabe(db):
    """(conn, forms, services, dienststellen_uebersicht) exactly as export_json.py holds
    them at the hook: the export is built in memory, nothing is written."""
    import contextlib
    import io
    import pathlib
    from citygov.export import export_json as EJ
    conn = sqlite3.connect(pathlib.Path(db).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    with contextlib.redirect_stdout(io.StringIO()):
        data, _todo = EJ.build(conn)
    return conn, data["forms"], data["services"], data["dienststellen_uebersicht"]


def main():
    ap = argparse.ArgumentParser(description="Gestaltung der Formulare: Vergleich je Merkmal (liest citygov.db, "
                                             "schreibt nichts).")
    ap.add_argument("--form", type=int, metavar="FORM_ID", help="ein Formular mit jedem Merkmal")
    ap.add_argument("--json", action="store_true", help="beide Ergebnisse als JSON ausgeben")
    ap.add_argument("--selbsttest", action="store_true", help="jede Prüfung auf veränderten Kopien auslösen")
    ap.add_argument("--db", default=DB_PATH, help="andere Databank-Datei (Vorgabe: citygov.db)")
    args = ap.parse_args()
    try:
        conn, forms, services, dienststellen = _eingabe(args.db)
        if args.selbsttest:
            _selbsttest(conn, forms, services, dienststellen)
            return
        per_form, overview, tab = _berechnen(conn, forms, dienststellen)
    except RuntimeError as e:
        sys.exit(f"ABBRUCH gestaltung_export.py: {e}")
    if args.json:
        json.dump({"forms": {str(fid): g for fid, g in per_form.items()}, "gestaltung": overview}, sys.stdout,
                  ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    elif args.form is not None:
        _drucke_formular(args.form, forms, services, dienststellen, per_form, overview, tab)
    else:
        _drucke_uebersicht(per_form, overview)


if __name__ == "__main__":
    main()
