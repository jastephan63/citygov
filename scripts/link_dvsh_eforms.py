#!/usr/bin/env python3
"""Give every DVSH service its appropriate Formular, without inventing files.

Two mechanical passes over the form-less DVSH services:
  1. eFormulare — where the modeller carries formDefinitions with fields, the
     online form is registered as a file-less form row (file_type 'eformular')
     and its data_field rows come 1:1 from the DVSH field definitions
     (derived_by 'dvsh-formdefinition'; DVSH is the source of truth).
  2. Tentative matches — where OUR catalogue already holds a form whose title
     strongly resembles the DVSH service title (token-Jaccard >= 0.6) and that
     form's current service row has no DVSH link, the form is re-parented to
     the DVSH-matched service and marked 'tentativ (Titel-Aehnlichkeit)' —
     visible, revocable, never silent.
Services whose channel is email/telefon/vor_ort/externer_link keep no form at
all — that is their honest shape (user decision 2026-09-03).

Idempotent. Staging -> validate -> swap.

    python3 scripts/link_dvsh_eforms.py
"""
import json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

# DVSH widget type -> our logical data_type (+ optional format hint)
TYPEMAP = {"text": ("text", None), "textarea": ("text", None), "checkbox": ("boolean", None),
           "number": ("number", None), "select": ("enum", None), "date": ("date", "TT.MM.JJJJ"),
           "tel": ("text", "Telefon"), "email": ("text", "E-Mail"), "year": ("number", "JJJJ"),
           "time": ("text", "HH:MM"), "month": ("text", None)}


def norm_tokens(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return {t for t in re.split(r"[^a-z0-9]+", s) if len(t) > 3}


def slugify(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80]


def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    try:
        c.execute("ALTER TABLE form ADD COLUMN dvsh_match TEXT")
    except Exception:
        pass

    have = {r[0] for r in c.execute("SELECT DISTINCT service_id FROM form")}
    slugs = {r[0] for r in c.execute("SELECT slug FROM form")}
    linked_svc = {r[0] for r in c.execute("SELECT DISTINCT service_id FROM dvsh_service")}

    # pass 1: eFormulare from the modeller's own field definitions
    ne = nef = 0
    for r in c.execute("SELECT dvsh_id, service_id, title, form_definitions FROM dvsh_service "
                       "WHERE form_definitions IS NOT NULL").fetchall():
        if r["service_id"] in have:
            continue
        try:
            fds = json.loads(r["form_definitions"])
        except Exception:
            continue
        for fd in fds:
            felder = fd.get("felder") or []
            if not felder:
                continue
            title = fd.get("titel") or r["title"]
            slug = slugify(title) or f"dvsh-eform-{r['dvsh_id']}"
            while slug in slugs:
                slug += "-e"
            slugs.add(slug)
            c.execute("INSERT INTO form(service_id,slug,title,file_type,submission_channel,"
                      "dvsh_match) VALUES(?,?,?,?,?,?)",
                      [r["service_id"], slug, title[:160], "eformular", "online_formular",
                       "dvsh-formdefinition"])
            fid = c.execute("SELECT last_insert_rowid() i").fetchone()["i"]
            for i, f in enumerate(felder):
                dt, fmt = TYPEMAP.get(f.get("type"), ("text", None))
                opts = f.get("options") or f.get("werte") or []
                c.execute("INSERT INTO data_field(form_id,ord,name,definition,data_type,required,"
                          "allowed_values,subfields,format,source_widgets,derived_by) "
                          "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                          [fid, i, (f.get("label") or f.get("name") or "?")[:160],
                           (f.get("hint") or "")[:400], dt,
                           1 if f.get("required") else 0,
                           json.dumps(opts, ensure_ascii=False), "[]", fmt or "",
                           json.dumps([f.get("name")], ensure_ascii=False),
                           "dvsh-formdefinition"])
                nef += 1
            have.add(r["service_id"])
            ne += 1

    # pass 2: tentative title matches against forms we already hold
    #         (only forms whose current service row has no DVSH identity)
    cand_forms = [dict(x) for x in c.execute(
        "SELECT f.id, f.title, f.service_id FROM form f WHERE f.service_id NOT IN "
        f"({','.join(str(s) for s in linked_svc) or '0'})")]
    for f in cand_forms:
        f["tok"] = norm_tokens(f["title"])
    nt = 0
    for r in c.execute("SELECT dvsh_id, service_id, title FROM dvsh_service").fetchall():
        if r["service_id"] in have:
            continue
        dt = norm_tokens(r["title"])
        best, bj = None, 0.0
        for f in cand_forms:
            u = dt | f["tok"]
            j = len(dt & f["tok"]) / len(u) if u else 0
            if j > bj:
                best, bj = f, j
        if best and bj >= 0.6:
            c.execute("UPDATE form SET service_id=?, dvsh_match=? WHERE id=?",
                      [r["service_id"], f"tentativ (Titel-Ähnlichkeit {bj:.2f})", best["id"]])
            have.add(r["service_id"])
            cand_forms.remove(best)
            nt += 1

    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    total = "?"
    import sqlite3
    c2 = sqlite3.connect(DB_PATH)
    n_dv = c2.execute("SELECT COUNT(*) FROM dvsh_service").fetchone()[0]
    n_with = c2.execute("SELECT COUNT(*) FROM dvsh_service dv WHERE EXISTS "
                        "(SELECT 1 FROM form f WHERE f.service_id=dv.service_id)").fetchone()[0]
    print(f"eFormulare: +{ne} Formulare mit {nef} Feldern aus DVSH-formDefinitions; "
          f"tentative Matches: {nt}; DVSH-Services mit Formular: {n_with}/{n_dv}")


if __name__ == "__main__":
    main()
