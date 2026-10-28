#!/usr/bin/env python3
"""Load what each file DVSH or SHEP offers is, when no Formular holds its bytes.

DVSH lists per service the files a person submits or reads (documents[],
submissionEndpoint, each with its sha256); SHEP links them from the portal
page (/api/catalog/assets/<sha256>.<ext>). A file whose sha256 equals a
form.file_hash is a Formular of the databank. Every other file was read and
judged from its content by a panel, and a sceptical second review checked each
verdict that would change the databank: a Merkblatt, a newer/older/the same
edition of a held Formular, or a Formular the databank did not hold yet. The
verdicts are kept with their verbatim evidence in quellen/dokumente/urteile_*.json.

Gates: the sha256 must be a file a DVSH or SHEP row of the databank lists;
vocabularies (art, urteil); a form_id must exist; an edition verdict
(neue/gleiche/aeltere Ausgabe, ersetzt_falsch_zugeordnetes) needs a form_id.
The table is rebuilt from all files of quellen/dokumente/ (sorted; a later
file overrides an earlier one), so a run reproduces it. Staging -> validate
-> swap.

    python3 scripts/load_dokument_urteile.py [quellen/dokumente]
"""
import glob, json, os, shutil, sys
from citygov.core.common import ROOT, DB_PATH, connect
from citygov.checks.validate_db import validate

ART = {"formular", "merkblatt", "wegleitung", "liste", "gesetz", "brief", "uebersetzung", "anderes"}
URTEIL = {"neue_ausgabe", "gleiche_ausgabe", "aeltere_ausgabe", "weiteres_formular",
          "ersetzt_falsch_zugeordnetes", "kein_formular", "nicht_lesbar"}
BRAUCHT_FORM = {"neue_ausgabe", "gleiche_ausgabe", "aeltere_ausgabe", "ersetzt_falsch_zugeordnetes"}

DDL = """
CREATE TABLE IF NOT EXISTS dokument_urteil (
    sha256        TEXT PRIMARY KEY,
    art           TEXT NOT NULL CHECK (art IN ('formular','merkblatt','wegleitung','liste','gesetz','brief',
                                               'uebersetzung','anderes')),
    urteil        TEXT NOT NULL CHECK (urteil IN ('neue_ausgabe','gleiche_ausgabe','aeltere_ausgabe',
                                                  'weiteres_formular','ersetzt_falsch_zugeordnetes',
                                                  'kein_formular','nicht_lesbar')),
    form_id       INTEGER REFERENCES form(id),
    titel         TEXT,
    beleg         TEXT,
    zweitgeprueft INTEGER NOT NULL DEFAULT 0,
    abzug         TEXT);
"""


def listed_hashes(c):
    """Every sha256 a DVSH or SHEP row of the databank names."""
    out = set()

    def walk(v):
        for _ in range(3):
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except Exception:
                    return
        if isinstance(v, dict):
            v = [v]
        for x in v or []:
            if isinstance(x, dict) and x.get("sha256"):
                out.add(x["sha256"])

    for r in c.execute("SELECT documents, submission_endpoint FROM dvsh_service"):
        walk(r["documents"]); walk(r["submission_endpoint"])
    for r in c.execute("SELECT dokumente FROM shep_service"):
        walk(r["dokumente"])
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "quellen", "dokumente")
    files = sorted(glob.glob(os.path.join(src, "urteile_*.json")))
    if not files:
        sys.exit(f"ABBRUCH: keine urteile_*.json in {src}")
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    listed = listed_hashes(c)
    forms = {r[0] for r in c.execute("SELECT id FROM form")}
    rows, rej = {}, []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        for u in d.get("urteile", []):
            h, art, urt, fid = u.get("sha256"), u.get("art"), u.get("urteil"), u.get("form_id")
            why = ("sha256 von keiner DVSH-/SHEP-Zeile genannt" if h not in listed else
                   "art" if art not in ART else "urteil" if urt not in URTEIL else
                   "form_id fehlt" if urt in BRAUCHT_FORM and not fid else
                   "form_id unbekannt" if fid and fid not in forms else
                   "Beleg fehlt" if not (u.get("beleg") or "").strip() else None)
            if why:
                rej.append((h, why)); continue
            rows[h] = [h, art, urt, fid, u.get("titel"), u["beleg"], 1 if u.get("zweitgeprueft") else 0,
                       d.get("abzug")]
    c.execute("DELETE FROM dokument_urteil")
    c.executemany("INSERT INTO dokument_urteil VALUES(?,?,?,?,?,?,?,?)", rows.values())
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"dokument_urteil: {len(rows)} Urteile geladen, {len(rej)} abgewiesen")
    for h, why in rej[:20]:
        print(f"  ABGEWIESEN {str(h)[:12]}: {why}")


if __name__ == "__main__":
    main()
