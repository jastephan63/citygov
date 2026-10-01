#!/usr/bin/env python3
"""Ingest only new files into the databank. Existing forms are never touched:
re-running auto_draft on them would clobber curated titles and labels through
its upsert-update.

Input: a JSON list of filenames (plain strings, or pairs whose second element
is the filename, as in the sweep download plan). Each file is located under
../Verwaltung/ (excluding _Neu), tested with the same form test as auto_draft
(name says formular, or at least 3 AcroForm fields), drafted via
auto_draft.draft_form, slug-guarded against collisions with existing rows, and
committed via staging -> validate -> swap.

A file is already known — and skipped — when its sha256 equals a form's
file_hash, or when its file name (composed Unicode, NFC) is already the name
of a Formular in formulare/ or of an ingested source file (document table).
A known name with different bytes is listed as a possible new edition and
left for a decision by hand; nothing is overwritten.

Each new file is copied into formulare/<NFC name> (the tracked folder the
website's «Quelldatei» link points to) and form.source_file points there;
document.source_file keeps the ../Verwaltung/ path it was read from
(provenance). A run that fails removes the copies it made.

    python3 scripts/ingest_new.py <names.json>     # then scan_documents.py
"""
import hashlib, json, os, shutil, sys, unicodedata
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect
from validate_db import validate
import auto_draft as AD
from classify import classify
from commit_proposal import commit

VERW = AD.VERW


def nfc(s):
    return unicodedata.normalize("NFC", s)


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    names = set()
    for it in json.load(open(sys.argv[1], encoding="utf-8")):
        names.add(nfc(it[1] if isinstance(it, (list, tuple)) else it))
    # index current tree by NFC filename (excluding _Neu): the macOS file
    # system may hand back decomposed names
    paths = {}
    for root, _, fs in os.walk(VERW):
        if "_Neu" in root:
            continue
        for f in fs:
            paths.setdefault(nfc(f), os.path.join(root, f))

    staging = DB_PATH + ".staging"
    if os.path.exists(staging):
        os.remove(staging)
    shutil.copy2(DB_PATH, staging)
    conn = connect(staging)
    known_hash = {r[0] for r in conn.execute("SELECT file_hash FROM form WHERE file_hash IS NOT NULL")}
    known_name = {nfc(os.path.basename(r[0])) for r in conn.execute(
        "SELECT source_file FROM form WHERE source_file IS NOT NULL UNION SELECT source_file FROM document")}
    existing_slugs = {r["slug"] for r in conn.execute("SELECT slug FROM form")}
    svc_slugs = {r["slug"] for r in conn.execute("SELECT slug FROM service")}

    copied = []                       # files this run put into formulare/

    def abort(msg):
        conn.close()
        os.remove(staging)
        for f in copied:
            os.remove(f)
        print("ABORT:", msg, sep="\n  ")
        sys.exit(1)

    n_new = n_skip = n_notform = 0
    other_edition = []
    helper_cache = {}
    try:
        for nm in sorted(names):
            full = paths.get(nm)
            if not full:
                continue
            h = sha256(full)
            base = nfc(os.path.basename(full))
            if h in known_hash:
                n_skip += 1
                continue
            if base in known_name:
                other_edition.append(base)
                continue
            ext = os.path.splitext(nm)[1].lower()
            if ext not in (".pdf", ".xlsx", ".xlsm", ".xls", ".doc", ".docx"):
                continue
            if AD.HELPER.search(os.path.splitext(nm)[0]):
                n_notform += 1
                continue
            try:
                if ext in (".xlsx", ".xlsm", ".xls"):
                    fields, ftext, scanned, title, acro = AD.extract_xlsx(full)
                elif ext == ".pdf":
                    fields, ftext, scanned, title, acro = AD.extract_pdf(full)
                else:
                    fields, ftext, scanned, title, acro = AD.extract_doc(full)
            except Exception:
                continue
            if not (classify(nm)[0] == "formular" or acro >= 3):
                n_notform += 1
                continue
            office_dir = os.path.dirname(full)
            rel_office = os.path.relpath(office_dir, VERW)
            dept = rel_office.split("/")[0]
            if dept.startswith("_"):
                continue
            if office_dir not in helper_cache:
                try:
                    helper_cache[office_dir] = AD.office_helper_text(office_dir)
                except Exception:
                    helper_cache[office_dir] = ""
            sr, laws, arts = AD.mine_citations((ftext or "") + "\n" + helper_cache[office_dir][:8000])
            p = AD.draft_form(full, rel_office, dept, fields, scanned, sr, laws, arts, title)
            # slug guard: never collide with an existing form/service (would UPDATE it)
            fs_, ss_ = p["form"]["slug"], p["service"]["slug"]
            if fs_ in existing_slugs or ss_ in svc_slugs:
                suf = 2
                while f"{fs_}-{suf}" in existing_slugs or f"{ss_}-{suf}" in svc_slugs:
                    suf += 1
                p["form"]["slug"] = f"{fs_}-{suf}"
                p["service"]["slug"] = f"{ss_}-{suf}"
            existing_slugs.add(p["form"]["slug"]); svc_slugs.add(p["service"]["slug"])
            # the tracked copy the Quelldatei link points to (draft_form already set
            # form.source_file to formulare/<NFC name>); never overwrite another file
            try:
                if AD.copy_into_formulare(full):
                    copied.append(os.path.join(AD.FORMULARE_DIR, base))
            except FileExistsError as e:
                abort(str(e))
            commit(conn, p)
            conn.execute("UPDATE form SET file_hash=? WHERE slug=?", [h, p["form"]["slug"]])
            # a service without a Themengruppe needs a recorded reason (validate_db);
            # the groups are assigned later by the Begriffe chain (load_themen.py)
            sid = conn.execute("SELECT id FROM service WHERE slug=?", [p["service"]["slug"]]).fetchone()[0]
            if not conn.execute("SELECT 1 FROM service_thema WHERE service_id=?", [sid]).fetchone():
                conn.execute("INSERT OR IGNORE INTO service_thema_grund(service_id, grund, zweitgeprueft) VALUES(?,?,0)",
                             [sid, f"Neu erfasst am {date.today().isoformat()}; die Themengruppen sind noch nicht zugeordnet."])
            known_hash.add(h)
            known_name.add(base)
            n_new += 1
    except Exception as e:          # any failure: no half-done run
        abort(repr(e))
    conn.commit()
    errs = validate(conn)
    if errs:
        abort("\n  ".join(errs[:4]))
    conn.close()
    os.replace(staging, DB_PATH)
    print(f"ingested {n_new} NEW forms (copied into formulare/); {n_skip} already known; {n_notform} not forms")
    for b in other_edition:
        print(f"  same name as a known Formular, other content (new edition? decide by hand): {b}")


if __name__ == "__main__":
    main()
