#!/usr/bin/env python3
"""One-off data corrections from the repository clean-up of 2026-10-01, each
with its evidence, applied staging -> validate -> swap. Idempotent: a second
run changes nothing, reports 0 everywhere and leaves citygov.db untouched.

  1. form.file_type of the Word Formulare: 55 .doc/.docx files (53 .docx,
     2 .doc) were stored as 'pdf'. Cause: auto_draft.py mapped every non-Excel
     extension to 'pdf' (fixed there). The databank itself already said
     otherwise: all 55 carry parse_error 'kein_pdf' (scan_documents.py), and
     7 other .docx rows already had 'word'. The value follows the extension;
     validate_db.py now refuses a file_type that disagrees with it.
  2. data_field.ech_herkunft and data_subfield.ech_herkunft: the provenance of
     an eCH verdict that propagate_ech_names.py writes ('propagiert …') and
     load_ech_verdicts_new.py upgrades ('zweitgeprüft'). The column was added
     by the first loader at run time and was missing from schema.sql, so the
     schema gate aborted that loader and the second one failed with «no such
     column». The column is now part of schema.sql and is added here; existing
     rows stay NULL (no copy recorded).
  3. eCH-0147: ech_standard.xsd_file named the illustrative supplement
     «eCH-0147_V1.2_Zusatzbestimmungen%20%C3%9CDP%20illustrativ.xsd» (saved
     under its URL-encoded name), because sweep_ech_xsd.py ranked files by
     every digit in the name and its percent escapes outranked T0, T1 and T2.
     The pin moves to the file sweep_ech_xsd.main_xsd() now selects (T0: the
     type definitions T1 and T2 import; xsd_version stays «1.2 (aus
     Dateiname)»). ech_codelist rows of eCH-0147 that occur in the supplement
     and in none of the standard's own files (exRecipientsEnumType, 2 values)
     are removed; errorKindType (T0) stays. No field or part is mapped to
     eCH-0147.
  4. service.description: 336 rows held the 2026-06 auto-draft placeholder
     «AUTO-ENTWURF aus ../Verwaltung/<Departement>/<Amt>/<Datei>. Felder
     einzeln; Rechtsgrundlagen zu ermitteln.» — a local path outside the
     repository and no description at all; it reached citygov_llm.json. Only
     values that match this template exactly are cleared (NULL); the 136 real
     descriptions are untouched. auto_draft.py no longer writes it.
  5. Check, nothing written: no other column holds a local path
     ('../Verwaltung', '../Gesetze', '../DVSH', '../formflows', '/Users/',
     '/private/') that reaches an export. Known and kept:
     document.source_file (ingest-time provenance, not exported) and the
     meta.quelldatei inside formflow.flow (build_flows.py replaces it with
     form.source_file). A hit anywhere else aborts the migration.
  6. Names in decomposed Unicode (NFD): 4 form titles (156, 238, 249, 282),
     2 service names (238, 249) and 2 service.name_alt values (156, 282) were
     taken from macOS file names, which come back decomposed. They look the
     same but differ byte for byte from the same text typed elsewhere, so the
     dashboard search did not find them. They are rewritten in composed form
     (NFC), the text itself unchanged; slugs stay as they are (stable ids).
     auto_draft.draft_form now stores every name in NFC. Source texts kept
     verbatim (dvsh_service, ech_standard, form_check.online_name) and the
     provenance columns (document, service.notes) are not touched.
  7. Compaction: the placeholders cleared in step 4 stayed readable as free
     space inside the database file (`strings citygov.db`). When such bytes
     are left and no row holds the placeholder any more, the staging copy is
     rebuilt with VACUUM before it is validated and swapped in.

    python3 scripts/migrate_2026_10_01.py
"""
import glob, json, os, re, shutil, sys, unicodedata
from citygov.core.common import ROOT, DB_PATH, connect
from citygov.checks.validate_db import validate
from citygov.load import sweep_ech_xsd as SW

PLACEHOLDER = re.compile(r"AUTO-ENTWURF aus .+\. Felder einzeln; Rechtsgrundlagen zu ermitteln\.", re.S)
LOCAL = ("../Verwaltung", "../Gesetze", "../DVSH", "../formflows", "/Users/", "/private/")
# (table, column) where a local path is known, documented and never exported
KNOWN_LOCAL = {("document", "source_file"), ("formflow", "flow")}
# names shown and searched on the surfaces; written in NFC (step 6)
NFC_COLUMNS = (("form", "title"), ("service", "name"), ("service", "name_alt"))
STALE = b"AUTO-ENTWURF aus "          # the step-4 placeholder (step 7)


def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    rep = {k: 0 for k in ("1 file_type pdf -> word", "2 Spalte ech_herkunft ergänzt",
                          "3 eCH-0147 xsd_file", "3 eCH-0147 Codelisten-Werte entfernt",
                          "4 Platzhalter-Beschreibungen geleert", "6 Namen in NFC",
                          "7 Datei verdichtet (VACUUM)")}

    # 1. file_type of the Word Formulare ----------------------------------------
    rep["1 file_type pdf -> word"] = c.execute(
        "UPDATE form SET file_type='word' WHERE file_type='pdf' AND "
        "(lower(source_file) LIKE '%.docx' OR lower(source_file) LIKE '%.doc')").rowcount

    # 2. ech_herkunft ---------------------------------------------------------------
    for tbl in ("data_field", "data_subfield"):
        if "ech_herkunft" not in {r[1] for r in c.execute(f"PRAGMA table_info({tbl})")}:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN ech_herkunft TEXT")
            rep["2 Spalte ech_herkunft ergänzt"] += 1

    # 3. eCH-0147: the standard's own schema, not the illustrative supplement ---------
    code = "eCH-0147"
    files = sorted(glob.glob(os.path.join(SW.XSD_DIR, code, "*.xsd")))
    mx = SW.main_xsd(code, files)
    if not mx or SW.SUPPLEMENT.search(os.path.basename(mx)):
        sys.exit(f"ABBRUCH: keine eigene Schemadatei für {code} in ech_xsd/{code}/")
    target = os.path.relpath(mx, ROOT)
    rep["3 eCH-0147 xsd_file"] = c.execute(
        "UPDATE ech_standard SET xsd_file=? WHERE code=? AND xsd_file IS NOT ?", [target, code, target]).rowcount
    own = set()
    for f in SW.own_files(code, files):
        own |= {(t, v) for t, v, _ in SW.parse_xsd(f)[2]}
    supplement = set()
    for f in files:
        if SW.SUPPLEMENT.search(os.path.basename(f)):
            supplement |= {(t, v) for t, v, _ in SW.parse_xsd(f)[2]}
    for r in c.execute("SELECT id, type_name, value FROM ech_codelist WHERE standard=?", [code]).fetchall():
        k = (r["type_name"], r["value"])
        if k in own:
            continue
        if k not in supplement:
            print(f"   {code}: Codelisten-Wert {k} in keiner Datei gefunden — belassen")
            continue
        c.execute("DELETE FROM ech_codelist WHERE id=?", [r["id"]])
        rep["3 eCH-0147 Codelisten-Werte entfernt"] += 1
        print(f"   {code}: entfernt {k[0]} = {k[1]} (nur in der illustrativen Zusatzdatei)")

    # 4. the auto-draft placeholder description -------------------------------------
    odd = 0
    for r in c.execute("SELECT id, description FROM service WHERE description LIKE 'AUTO-ENTWURF%'").fetchall():
        if PLACEHOLDER.fullmatch(r["description"]):
            c.execute("UPDATE service SET description=NULL WHERE id=?", [r["id"]])
            rep["4 Platzhalter-Beschreibungen geleert"] += 1
        else:
            odd += 1
    if odd:
        print(f"   {odd} Beschreibungen beginnen mit AUTO-ENTWURF, folgen aber nicht der Vorlage — belassen")

    # 5. no local path left where an export can read it --------------------------------
    hits = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        for col in [r[1] for r in c.execute(f"PRAGMA table_info({t})")]:
            n = c.execute(f"SELECT COUNT(*) FROM \"{t}\" WHERE " + " OR ".join(
                f"instr(CAST(\"{col}\" AS TEXT), ?)" for _ in LOCAL), LOCAL).fetchone()[0]
            if n:
                hits[(t, col)] = n
    unknown = {k: v for k, v in hits.items() if k not in KNOWN_LOCAL}
    for (t, col), n in sorted(hits.items()):
        print(f"   5 lokaler Pfad in {t}.{col}: {n} Zeilen"
              + ("" if (t, col) in KNOWN_LOCAL else "  <- UNERWARTET"))
    if unknown:
        c.close(); os.remove(st)
        sys.exit("ABBRUCH: lokale Pfade in Spalten, die ein Export lesen kann: "
                 + ", ".join(f"{t}.{col}" for t, col in unknown))

    # 6. names in composed Unicode (NFC) ------------------------------------------------
    for t, col in NFC_COLUMNS:
        for r in c.execute(f"SELECT id, {col} v FROM {t} WHERE {col} IS NOT NULL").fetchall():
            v = unicodedata.normalize("NFC", r["v"])
            if v != r["v"]:
                c.execute(f"UPDATE {t} SET {col}=? WHERE id=?", [v, r["id"]])
                rep["6 Namen in NFC"] += 1
                print(f"   6 {t}.{col} #{r['id']}: {v}")

    c.commit()

    # 7. no cleared placeholder left as free space in the file ---------------------------
    live = c.execute("SELECT COUNT(*) FROM service WHERE description LIKE 'AUTO-ENTWURF aus %'").fetchone()[0]
    with open(st, "rb") as fh:
        stale = fh.read().count(STALE)
    if stale and not live:
        c.execute("VACUUM")
        with open(st, "rb") as fh:
            left = fh.read().count(STALE)
        if left:
            c.close(); os.remove(st)
            sys.exit(f"ABBRUCH: nach VACUUM noch {left} Platzhalter-Bytes in der Datei")
        rep["7 Datei verdichtet (VACUUM)"] = 1
        print(f"   7 {stale} Platzhalter-Reste entfernt")

    errs = validate(c)
    c.close()
    if errs:
        os.remove(st)
        print("ABORT:", *errs[:5], sep="\n  "); sys.exit(1)
    for k, v in rep.items():
        print(f"  {k}: {v}")
    if not any(rep.values()):
        os.remove(st)
        print("nichts zu tun — citygov.db unverändert (gültig)")
        return
    os.replace(st, DB_PATH)
    print("citygov.db aktualisiert (gültig)")


if __name__ == "__main__":
    main()
