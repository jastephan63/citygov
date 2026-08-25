#!/usr/bin/env python3
"""Ingest only new files into the databank. Existing forms are never touched:
re-running auto_draft on them would clobber curated titles and labels through
its upsert-update.

Input: a JSON list of filenames (plain strings, or pairs whose second element
is the filename, as in the sweep download plan). Each file is located under
Verwaltung/ (excluding _Neu), tested with the same form test as auto_draft
(name says formular, or at least 3 AcroForm fields), drafted via
auto_draft.draft_form, slug-guarded against collisions with existing rows, and
committed via staging -> validate -> swap.

    python3 scripts/ingest_new.py <names.json>
"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect
from validate_db import validate
import auto_draft as AD
from classify import classify
from commit_proposal import commit

VERW = AD.VERW


def main():
    names = set()
    for it in json.load(open(sys.argv[1], encoding="utf-8")):
        names.add(it[1] if isinstance(it, (list, tuple)) else it)
    # index current tree by filename (excluding _Neu)
    paths = {}
    for root, _, fs in os.walk(VERW):
        if "_Neu" in root:
            continue
        for f in fs:
            paths.setdefault(f, os.path.join(root, f))

    staging = DB_PATH + ".staging"
    if os.path.exists(staging):
        os.remove(staging)
    shutil.copy2(DB_PATH, staging)
    conn = connect(staging)
    existing_src = {r["source_file"] for r in conn.execute("SELECT source_file FROM form")}
    existing_slugs = {r["slug"] for r in conn.execute("SELECT slug FROM form")}
    svc_slugs = {r["slug"] for r in conn.execute("SELECT slug FROM service")}

    n_new = n_skip = n_notform = 0
    helper_cache = {}
    for nm in sorted(names):
        full = paths.get(nm)
        if not full:
            continue
        rel = os.path.relpath(full, ROOT)
        if rel in existing_src:
            n_skip += 1
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
        # copy into forms/ mirror like auto_draft does
        dest = os.path.join(AD.FORMS_DIR, os.path.relpath(full, VERW))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if not os.path.exists(dest):
            try:
                shutil.copy2(full, dest)
            except Exception:
                pass
        commit(conn, p)
        n_new += 1
    conn.commit()
    errs = validate(conn)
    conn.close()
    if errs:
        os.remove(staging); print("ABORT:", *errs[:4], sep="\n  "); sys.exit(1)
    os.replace(staging, DB_PATH)
    print(f"ingested {n_new} NEW forms; {n_skip} already known; {n_notform} not forms")


if __name__ == "__main__":
    main()
