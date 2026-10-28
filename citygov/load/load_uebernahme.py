#!/usr/bin/env python3
"""Take over the Formulare that DVSH or SHEP offer and the databank did not hold:
new Formulare and newer editions of held ones. From the reviewed plan
quellen/dokumente/uebernahme_<date>.json, built on the content verdicts of
quellen/dokumente/urteile_<date>.json (load_dokument_urteile.py).

The files come from the read-only harvests: ../DVSH/assets_<date>/<sha256> (the
DVSH asset store and sh.ch sources) and ../SHEP/<date>/assets/<sha256>.<ext>.
Each one is checked against its sha256 before it is copied into formulare/
(NFC name; an existing file of that name is never overwritten).

  neue_formulare  a new form row under the service DVSH/SHEP lists it for (dvsh_id, or
                  service_id for a file only SHEP links): title as
                  printed on the document, file, file_type, file_hash, the channel the
                  parent's DVSH model records (formular_pdf -> pdf, eformular ->
                  online_formular, else unbekannt), and in
                  form.dvsh_match the DVSH/SHEP entry that names the file. No data
                  field yet — load_data_fields.py adds them.
  neue_ausgaben   a held Formular whose newer edition arrived: the form row keeps its
                  id, fields and every curated layer on them; source_file, file_type
                  and file_hash point at the new file, the title follows the new
                  edition where the plan gives one, and the old file leaves
                  formulare/ (only the newest edition is kept). What the edition
                  changed in the fields is ported afterwards (migrate_ausgaben_*.py).
                  The Gestaltung row and the currency verdict of the old file go
                  (scan_gestaltung.py measures the new file).

Idempotent: a file already held (form.file_hash) is skipped. Staging -> validate ->
swap; on failure the copies this run made are removed.

    python3 scripts/load_uebernahme.py quellen/dokumente/uebernahme_2026-10-28.json
"""
import glob, hashlib, json, os, re, shutil, sys, unicodedata
from citygov.core.common import ROOT, DB_PATH, connect
from citygov.checks.validate_db import validate

FORMULARE = os.path.join(ROOT, "formulare")
QUELLEN = os.path.normpath(os.path.join(ROOT, ".."))
FILE_TYPE = {".pdf": "pdf", ".doc": "word", ".docx": "word", ".xls": "excel", ".xlsx": "excel", ".xlsm": "excel"}


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def locate(sha, abzug):
    for p in [os.path.join(QUELLEN, "DVSH", f"assets_{abzug}", sha)] + \
             glob.glob(os.path.join(QUELLEN, "SHEP", abzug, "assets", sha + ".*")):
        if os.path.isfile(p) and sha256(p) == sha:
            return p
    return None


def slug(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "formular"


def main():
    plan = json.load(open(sys.argv[1], encoding="utf-8"))
    abzug = plan["abzug"]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    held = {r[0] for r in c.execute("SELECT file_hash FROM form WHERE file_hash IS NOT NULL")}
    slugs = {r[0] for r in c.execute("SELECT slug FROM form")}
    copied, removed, n_neu, n_ausg = [], [], 0, 0

    def abort(msg):
        c.close(); os.remove(st)
        for f in copied:
            os.remove(f)
        sys.exit("ABBRUCH: " + msg)

    def bring(e):
        """Copy the verified file into formulare/; returns the repository path."""
        src = locate(e["sha256"], abzug)
        if not src:
            abort(f"{e['sha256'][:12]}: Datei nicht gefunden oder Prüfsumme falsch")
        name = unicodedata.normalize("NFC", e["datei"])
        if "/" in name or not os.path.splitext(name)[1].lower() in FILE_TYPE:
            abort(f"{name}: kein flacher Name mit bekannter Endung")
        dest = os.path.join(FORMULARE, name)
        if os.path.exists(dest):
            if sha256(dest) != e["sha256"]:
                abort(f"formulare/{name} gibt es schon mit anderem Inhalt")
        else:
            shutil.copy2(src, dest); copied.append(dest)
        return "formulare/" + name, FILE_TYPE[os.path.splitext(name)[1].lower()]

    for e in plan.get("neue_formulare", []):
        if e["sha256"] in held:
            continue
        if e.get("dvsh_id") is not None:      # the parent named by its DVSH service
            r = c.execute("SELECT service_id FROM dvsh_service WHERE dvsh_id=?", [e["dvsh_id"]]).fetchone()
            if not r or r[0] is None:
                abort(f"DVSH {e['dvsh_id']} hat keinen Service")
            e["service_id"] = r[0]
        if not c.execute("SELECT 1 FROM service WHERE id=?", [e["service_id"]]).fetchone():
            abort(f"Service {e['service_id']} fehlt")
        sf, ft = bring(e)
        s = slug(e["titel"]); k = 2
        while s in slugs:
            s = f"{slug(e['titel'])[:56]}-{k}"; k += 1
        slugs.add(s)
        # the channel as the parent's DVSH model records it (eFormular / PDF-Formular), else unknown
        ep = c.execute("SELECT endpoint_typ FROM dvsh_service WHERE service_id=? ORDER BY dvsh_id LIMIT 1",
                       [e["service_id"]]).fetchone()
        kanal = {"formular_pdf": "pdf", "eformular": "online_formular"}.get(ep[0] if ep else None, "unbekannt")
        c.execute("INSERT INTO form(slug, service_id, title, source_file, file_type, file_hash, dvsh_match, "
                  "submission_channel) VALUES(?,?,?,?,?,?,?,?)",
                  [s, e["service_id"], e["titel"], sf, ft, e["sha256"], e["beleg"], kanal])
        held.add(e["sha256"]); n_neu += 1

    for e in plan.get("neue_ausgaben", []):
        if e["sha256"] in held:
            continue
        r = c.execute("SELECT source_file, title FROM form WHERE id=?", [e["form_id"]]).fetchone()
        if not r:
            abort(f"Formular {e['form_id']} fehlt")
        sf, ft = bring(e)
        c.execute("UPDATE form SET source_file=?, file_type=?, file_hash=?, title=?, parse_error=NULL, "
                  "acroform=NULL, signature_requirement=NULL, signature_evidence=NULL WHERE id=?",
                  [sf, ft, e["sha256"], e.get("titel") or r["title"], e["form_id"]])
        # what was measured or checked on the old file does not hold for the new one:
        # the Gestaltung row (scan_gestaltung.py measures the new file) and the currency
        # verdict about the old edition (the next check judges the new one)
        c.execute("DELETE FROM form_gestaltung WHERE form_id=?", [e["form_id"]])
        c.execute("DELETE FROM form_check WHERE form_id=?", [e["form_id"]])
        old = r["source_file"]
        if old and old != sf and not c.execute("SELECT 1 FROM form WHERE source_file=? AND id<>?",
                                               [old, e["form_id"]]).fetchone():
            removed.append(os.path.join(ROOT, old))
        held.add(e["sha256"]); n_ausg += 1

    c.commit()
    # the replaced files leave formulare/ before the gate runs (it compares the folder);
    # kept aside so a failed gate can put them back
    aside = []
    for p in removed:
        if os.path.exists(p):
            tmp = p + ".ersetzt"
            os.replace(p, tmp); aside.append((tmp, p))
    errs = validate(c)
    c.close()
    if errs:
        for tmp, p in aside:
            os.replace(tmp, p)
        os.remove(st)
        for f in copied:
            os.remove(f)
        print("ABORT:", *errs[:5], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    for tmp, _ in aside:
        os.remove(tmp)
    print(f"Übernahme {abzug}: {n_neu} neue Formulare, {n_ausg} neue Ausgaben "
          f"({len(copied)} Dateien nach formulare/, {len(aside)} ersetzte Dateien entfernt)")


if __name__ == "__main__":
    main()
