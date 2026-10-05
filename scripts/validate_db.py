#!/usr/bin/env python3
"""Integrity validation for a citygov database (staging -> validate -> swap,
convention 9).

Checks, in order:
  1. PRAGMA foreign_key_check       -> no orphan / broken foreign keys
  2. duplicate join-table rows      -> service_requirement, requirement_legal_basis,
                                       field_mapping (the rows that, duplicated,
                                       silently inflate compliance scores)
  3. field_mapping coherence        -> classification vs requirement_id agreement
                                       (enforced by CHECK, re-checked defensively)
  4. dangling references            -> documents marked 'formular' must point at a
                                       form; non-formular docs must not.

  5. convention 7                  -> an eSH draft code never sits on a field or
                                       subfield that eCH covers.
  6. judgment-layer invariants     -> the cross-loader rules every surface relies
                                       on (vocabularies, verdicts never pointing at
                                       struck rules, a Frist number present in the
                                       quote it hangs on, eCH status <-> element,
                                       begriff terms that exist as labels, reviewed
                                       items that exist, schema.sql listing every
                                       table, column and index, formflow node ids
                                       and keys within [A-Za-z0-9_.:-] because
                                       flows.html writes them raw into element ids
                                       and inline handlers). Each is named in the
                                       error text.
  7. source files                  -> every form.source_file is NFC, names a
                                       file directly in formulare/ exactly as
                                       listed there (case, no '..');
                                       form.file_type agrees with the extension.
  8. Gestaltung                    -> every form_gestaltung row belongs to a
                                       Formular with a file and was measured on
                                       the current file (file_hash =
                                       form.file_hash; a stale row is an error,
                                       a missing row is not: «noch nicht
                                       gemessen»); messart agrees with
                                       form.file_type; profil is a JSON object
                                       with exactly the keys GESTALTUNG_KEYS;
                                       the scalar columns repeat the profil
                                       values and nothing else.
  9. Kennungen                     -> kennungen.pruefen(): the triggers of the
                                       identifier table are present; every
                                       identifier has the format of its art and
                                       target table, an existing parent of the
                                       right art, consistent status and successor;
                                       no object and no natural key carries two
                                       active identifiers; every identifier the
                                       published data_export.json carries is
                                       still in the table (a lost or restored
                                       table is reported, also when it is
                                       missing). Safe on a staging copy
                                       where another loader changed data and
                                       kennungen.py has not run yet (the full
                                       check, every object has exactly one, is
                                       «kennungen.py --pruefen» in ./build.sh).
 10. Parteien und Rollen           -> rollen.pruefen(): role list, parties, at
                                       most one row per data point, subjekt
                                       consistency, stage B1/B2, stored verdicts
                                       and their second reviews (a party whose
                                       points another loader removed is stale,
                                       not an error).
 11. Gesetzesstand                 -> gesetz_stand.pruefen(): every row of
                                       gesetz_stand names its Stand only when all
                                       its evidence agrees, the evidence recorded
                                       at reading time equals article/law
                                       last_checked and source_note (unless the
                                       row is stale: basis differs — then the
                                       export says «veraltet»); every row of
                                       gesetz_stand_pruefung asked the right
                                       source for the right number, and its
                                       ergebnis, n_neuere and edition addresses
                                       agree with the edition list it stores; a
                                       later Fedlex edition (kuenftig) carries
                                       its publication date.
 12. Register                      -> register_map.pruefen(): every quote of the
                                       register layer is verbatim in its fetched
                                       source snapshot (quellen/register/, sha256
                                       unchanged), every register has a holder and
                                       a content quote (and a key quote when it
                                       names a key), a holder quote names a
                                       body, one key per Angabe, every context
                                       pattern compiles, access articles quoted
                                       inside their own article, never
                                       «erlaubt»; a register's own sentences
                                       never say who may fetch it and speak of
                                       access only with a quoted article; the
                                       time rule of the prefill (zeit_pruefen:
                                       its patterns against labelled examples,
                                       every exception element named by a quoted
                                       Einwohnerregister rule) and the reviewed
                                       eCH corrections under quellen/korrekturen/
                                       prefill_inhalt_2026-10-05/ (structure, and
                                       each file either pending or applied as a
                                       whole — never half-applied or overwritten).
 13. Konzepte                      -> konzepte.datei_pruefen(): the curated
                                       quellen/konzepte.json is readable and
                                       well-formed (the rule 2/3 with at least
                                       10, one code per concept, every element
                                       listed once, «ausserhalb» with a reason,
                                       no «ß», no risk word). The full check of
                                       the concept layer needs the export's data
                                       points and runs in export_json.py
                                       (konzepte.pruefen).
 14. Gesetzestitel                 -> load_gesetz_titel.pruefen(): the title
                                       corrections of quellen/korrekturen/
                                       gesetz_titel_2026-10-05.json are each
                                       pending or applied (never overwritten),
                                       and no law title carries the edition line
                                       («Vom … (Stand …)») or the footnote marker «*».
Each of the gates 9-12 lives next to its loader and is skipped while its tables
are absent; gate 13 reads only the curated file. Importing them loads only the standard library: no network code
(register_katalog.py imports urllib only inside its fetch function) and no pypdf
(rollen.py imports it only where it reads a Formular text).

Returns a list of error strings. Empty list == valid.
Every loader runs this on its staging copy before swapping; also runnable
standalone:

    python3 scripts/validate_db.py [path-to.db]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, ROOT, connect


def validate(conn):
    errors = []

    # 1. foreign keys
    for row in conn.execute("PRAGMA foreign_key_check").fetchall():
        errors.append(f"orphan FK: table={row[0]} rowid={row[1]} -> {row[2]}({row[3]})")

    # 2. duplicate join rows
    dup_checks = [
        ("service_requirement", "service_id, requirement_id"),
        ("requirement_legal_basis", "requirement_id, article_id"),
        ("field_mapping", "form_field_id"),
    ]
    for table, cols in dup_checks:
        q = (f"SELECT {cols}, count(*) c FROM {table} "
             f"GROUP BY {cols} HAVING c > 1")
        for row in conn.execute(q).fetchall():
            errors.append(f"duplicate rows in {table}: {tuple(row)}")

    # 3. classification / requirement_id coherence
    bad = conn.execute(
        "SELECT id, classification, requirement_id FROM field_mapping WHERE "
        "(requirement_id IS NOT NULL AND classification NOT IN "
        "  ('mapped','identity_part','reason_facet')) "
        "OR (requirement_id IS NULL AND classification NOT IN "
        "  ('form_mechanic','overcollection'))"
    ).fetchall()
    for row in bad:
        errors.append(f"field_mapping {row['id']}: classification "
                      f"'{row['classification']}' inconsistent with requirement_id "
                      f"{row['requirement_id']}")

    # 4. document <-> form linkage
    for row in conn.execute(
        "SELECT id, source_file, doc_type, form_id FROM document"
    ).fetchall():
        if row["doc_type"] == "formular" and row["form_id"] is None:
            errors.append(f"document '{row['source_file']}' is 'formular' but has no form_id")
        if row["doc_type"] != "formular" and row["form_id"] is not None:
            errors.append(f"document '{row['source_file']}' is '{row['doc_type']}' "
                          f"but points at a form")

    # convention 7: the cantonal draft eSH never shadows a real eCH standard —
    # a draft code may only sit on a field that eCH does not cover
    for tbl in ("data_field", "data_subfield"):
        if not _has(conn, tbl):
            continue
        if not {"esh_code", "ech_status"} <= _cols(conn, tbl):
            errors.append(f"convention-7 gate cannot run: {tbl} lacks esh_code/ech_status")
            continue
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl} WHERE esh_code IS NOT NULL "
                         f"AND ech_status IS NOT NULL AND ech_status!='kein_standard'").fetchone()[0]
        if n:
            errors.append(f"{n} rows in {tbl} carry an eSH draft code although eCH covers them "
                          f"(convention 7: eSH never shadows eCH)")

    errors += judgment_layer_checks(conn)
    errors += gestaltung_checks(conn)
    errors += datenmodell_checks(conn)
    return errors


def datenmodell_checks(conn):
    """The gates of the data-model layers (2026-10), each kept with its loader:
    permanent identifiers (kennungen.py), parties and roles (rollen.py), law
    editions (gesetz_stand.py) and registers with the prefill rule (register_map.py).
    Each returns [] while its tables are absent. Plus the structure of the curated
    concept file (konzepte.py), which the export reads."""
    import kennungen
    import rollen
    import gesetz_stand
    import register_map
    import konzepte
    errors = []
    for gate in (kennungen.pruefen, rollen.pruefen, gesetz_stand.pruefen, register_map.pruefen):
        errors += gate(conn)
    try:
        errors += konzepte.datei_pruefen(konzepte.lade())
    except (OSError, ValueError) as ex:
        errors.append(f"quellen/konzepte.json is not readable: {type(ex).__name__}: {ex}")
    # law titles as the official PDF prints them (load_gesetz_titel.py)
    import re
    import load_gesetz_titel
    errors += load_gesetz_titel.pruefen(conn)
    for lid, t, k in conn.execute("SELECT id, title, short_title FROM law"):
        for x in (t, k):
            if x and (re.search(r"\sVom\s+\d", x) or re.search(r"\s\*\s*$", x)):
                errors.append(f"law {lid}: «{x}» carries the edition line or the footnote marker «*» — "
                              "scripts/load_gesetz_titel.py --lesen, then apply")
    return errors


def _has(conn, table):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [table]).fetchone())


def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


# a Frist may be written in digits or as a number word in the quote
_NUMWORDS = {1: ["einem", "ein ", "eines"], 2: ["zwei"], 3: ["drei"], 4: ["vier"], 5: ["fünf", "fuenf"],
             6: ["sechs"], 7: ["sieben"], 8: ["acht"], 9: ["neun"], 10: ["zehn"], 12: ["zwölf", "zwoelf"],
             14: ["vierzehn"], 15: ["fünfzehn", "fuenfzehn"], 20: ["zwanzig"], 30: ["dreissig"],
             50: ["fünfzig", "fuenfzig"], 80: ["achtzig"], 100: ["hundert"]}


def _number_in(n, text):
    t = (text or "").lower()
    return (str(n) in t) or any(w in t for w in _NUMWORDS.get(n, []))


def judgment_layer_checks(conn):
    """Invariants between the judgment layers. Each check is skipped when its
    table does not exist yet (a fresh init_db.py database), never silently
    when it exists."""
    errors = []

    def count(sql, *args):
        return conn.execute(sql, args).fetchone()[0]

    # formflow: a node id, a node key and a form field's key stand raw in id="ac_<key>" and
    # onclick="__ff.select('<id>')" of flows.html — load_flows.py rejects anything outside
    # the character set; this keeps the invariant on the stored flows
    if _has(conn, "formflow"):
        import re
        ident = re.compile(r"^[A-Za-z0-9_.:-]+$")
        bad = []
        for fid, fl in conn.execute("SELECT form_id, flow FROM formflow"):
            try:
                nodes = (json.loads(fl) or {}).get("nodes") or []
            except ValueError:
                bad.append(f"form {fid}: flow is not JSON"); continue
            for n in nodes:
                vals = [("id", n.get("id")), ("key", n.get("key"))]
                vals += [("fields[].key", f.get("key")) for f in (n.get("fields") or []) if isinstance(f, dict)]
                bad += [f"form {fid}: node {what} {v!r}" for what, v in vals if v is not None and not ident.match(str(v))]
        if bad:
            errors.append(f"{len(bad)} formflow node ids/keys outside [A-Za-z0-9_.:-] (flows.html writes them raw into "
                          f"id= and onclick=): " + "; ".join(bad[:3]))

    # vocabularies
    if "basis_typ" in _cols(conn, "data_field"):
        n = count("SELECT COUNT(*) FROM data_field WHERE basis_typ IS NOT NULL "
                  "AND basis_typ NOT IN ('artikel','aufgabe','ohne','offen')")
        if n: errors.append(f"{n} data_field rows with a basis_typ outside artikel|aufgabe|ohne|offen")
        n = count("SELECT COUNT(*) FROM data_field d WHERE basis_typ='artikel' AND NOT EXISTS "
                  "(SELECT 1 FROM data_field_legal_basis b WHERE b.data_field_id=d.id)")
        if n: errors.append(f"{n} data_field rows say basis_typ='artikel' without any citation")
    if "subjekt" in _cols(conn, "data_field"):
        n = count("SELECT COUNT(*) FROM data_field WHERE subjekt IS NOT NULL AND subjekt NOT IN "
                  "('natuerliche_person','organisation','sache','behoerde','gemischt')")
        if n: errors.append(f"{n} data_field rows with a subjekt outside the vocabulary")
    if _has(conn, "data_field_legal_basis") and "relation" in _cols(conn, "data_field_legal_basis"):
        n = count("SELECT COUNT(*) FROM data_field_legal_basis WHERE relation IS NOT NULL "
                  "AND relation NOT IN ('requires','permits','informs')")
        if n: errors.append(f"{n} data_field_legal_basis rows with relation outside requires|permits|informs")

    # eCH: status and element agree, on fields and on subfields
    for tbl in ("data_field", "data_subfield"):
        if not _has(conn, tbl) or "ech_status" not in _cols(conn, tbl):
            continue
        n = count(f"SELECT COUNT(*) FROM {tbl} WHERE (ech_status='assigned') != (ech_element_id IS NOT NULL)")
        if n: errors.append(f"{n} {tbl} rows where ech_status='assigned' and ech_element_id disagree")
        n = count(f"SELECT COUNT(*) FROM {tbl} WHERE ech_status='standard_only' AND ech_standard_code IS NULL")
        if n: errors.append(f"{n} {tbl} rows are standard_only without a standard code")
    if _has(conn, "ech_standard") and _has(conn, "ech_element"):
        n = count("SELECT COUNT(*) FROM ech_standard s WHERE n_elements != "
                  "(SELECT COUNT(*) FROM ech_element e WHERE e.standard=s.code)")
        if n: errors.append(f"{n} ech_standard rows whose n_elements differs from the element count")

    # Rechtsmittel: a verdict or an outcome never rests on a struck provision;
    # quelle and regel_id agree
    if _has(conn, "rechtsmittel_verdikt") and _has(conn, "rechtsmittel_regel"):
        n = count("SELECT COUNT(*) FROM rechtsmittel_verdikt v JOIN rechtsmittel_regel r ON r.id=v.regel_id "
                  "WHERE COALESCE(r.gestrichen,0)=1")
        if n: errors.append(f"{n} rechtsmittel_verdikt rows point at a struck (gestrichen) provision")
        n = count("SELECT COUNT(*) FROM rechtsmittel_verdikt WHERE (quelle='sektoral') != (regel_id IS NOT NULL)")
        if n: errors.append(f"{n} rechtsmittel_verdikt rows where quelle='sektoral' and regel_id disagree")
    if _has(conn, "form_outcome") and "rechtsmittel_quelle" in _cols(conn, "form_outcome"):
        n = count("SELECT COUNT(*) FROM form_outcome WHERE (rechtsmittel_quelle IN ('sektoral','allgemein')) "
                  "!= (rechtsmittel_regel_id IS NOT NULL)")
        if n: errors.append(f"{n} form_outcome rows where rechtsmittel_quelle and rechtsmittel_regel_id disagree")
        if _has(conn, "rechtsmittel_regel"):
            n = count("SELECT COUNT(*) FROM form_outcome o JOIN rechtsmittel_regel r ON r.id=o.rechtsmittel_regel_id "
                      "WHERE COALESCE(r.gestrichen,0)=1")
            if n: errors.append(f"{n} form_outcome rows apply a struck provision")

    # retention: the number a term carries must be in the quote it hangs on
    if _has(conn, "retention_term"):
        bad = [r for r in conn.execute("SELECT rt.id, rt.duration_value, dr.quote FROM retention_term rt "
                                       "JOIN data_rule dr ON dr.id=rt.data_rule_id WHERE rt.duration_value IS NOT NULL")
               if not _number_in(r[1], r[2])]
        if bad: errors.append(f"{len(bad)} retention_term rows whose duration is not in the rule's quote: "
                              f"ids {[r[0] for r in bad][:8]}")
    if _has(conn, "data_rule"):
        n = count("SELECT COUNT(*) FROM data_rule WHERE quote IS NOT NULL AND quote!='' AND quote_verified=0")
        if n: errors.append(f"{n} data_rule rows carry an unverified quote")

    # Begriffe: the key column equals the shared normalisation, a pruefen label
    # says how, and every proposed term is a label that exists in the forms
    if _has(conn, "begriff_label"):
        from common import norm_label
        conn.create_function("norm_label", 1, norm_label)
        n = count("SELECT COUNT(*) FROM begriff_label WHERE label_norm != norm_label(label)")
        if n: errors.append(f"{n} begriff_label rows whose label_norm is not norm_label(label) (common.py)")
        n = count("SELECT COUNT(*) FROM begriff_label WHERE klasse='pruefen' AND pruefart IS NULL")
        if n: errors.append(f"{n} begriff_label rows are 'pruefen' without a pruefart")
        n = count("SELECT COUNT(*) FROM begriff_label WHERE klasse NOT IN ('vorschlag','variante','rolle','pruefen') "
                  "OR (pruefart IS NOT NULL AND pruefart NOT IN ('aufteilen','zuordnung'))")
        if n: errors.append(f"{n} begriff_label rows outside the klasse/pruefart vocabulary")
    if _has(conn, "begriff_vorschlag") and _has(conn, "data_subfield"):
        n = count("SELECT COUNT(*) FROM begriff_vorschlag v WHERE lower(trim(v.term)) NOT IN "
                  "(SELECT lower(trim(name)) FROM data_field UNION SELECT lower(trim(name)) FROM data_subfield)")
        if n: errors.append(f"{n} begriff_vorschlag terms are not a label that exists in any form")

    # Lebenslagen: at most three groups per service; a service without a group has a reason
    if _has(conn, "service_thema"):
        n = count("SELECT COUNT(*) FROM (SELECT service_id, COUNT(*) c FROM service_thema GROUP BY 1 HAVING c>3)")
        if n: errors.append(f"{n} services carry more than three Themengruppen")
        if _has(conn, "service_thema_grund"):
            n = count("SELECT COUNT(*) FROM service s WHERE NOT EXISTS (SELECT 1 FROM service_thema t WHERE t.service_id=s.id) "
                      "AND NOT EXISTS (SELECT 1 FROM service_thema_grund g WHERE g.service_id=s.id)")
            if n: errors.append(f"{n} services have neither a Themengruppe nor a recorded reason")

    # second opinions: every reviewed item exists
    if _has(conn, "panel_review"):
        for kind, tbl, col in (("basis", "data_field", "id"), ("subjekt", "data_field", "id"),
                               ("rmrule", "rechtsmittel_regel", "id"), ("rmverdict", "rechtsmittel_verdikt", "form_id"),
                               ("partei", "form", "id")):
            if _has(conn, tbl):
                n = count(f"SELECT COUNT(*) FROM panel_review p WHERE p.kind=? AND NOT EXISTS "
                          f"(SELECT 1 FROM {tbl} t WHERE t.{col}=p.item_id)", kind)
                if n: errors.append(f"{n} panel_review rows of kind '{kind}' point at a missing {tbl} row")
        n = count("SELECT COUNT(*) FROM panel_review WHERE kind NOT IN ('basis','subjekt','rmrule','rmverdict','partei')")
        if n: errors.append(f"{n} panel_review rows with an unknown kind")

    # undeclared references (columns without a FOREIGN KEY clause)
    for sql, msg in (
        ("SELECT COUNT(*) FROM data_field d WHERE d.esh_code IS NOT NULL AND NOT EXISTS "
         "(SELECT 1 FROM esh_standard e WHERE e.code=d.esh_code)", "data_field.esh_code without an esh_standard row"),
        ("SELECT COUNT(*) FROM data_field d WHERE d.ech_standard_code IS NOT NULL AND NOT EXISTS "
         "(SELECT 1 FROM ech_standard e WHERE e.code=d.ech_standard_code)", "data_field.ech_standard_code unknown"),
        ("SELECT COUNT(*) FROM dvsh_service v WHERE v.service_id IS NOT NULL AND NOT EXISTS "
         "(SELECT 1 FROM service s WHERE s.id=v.service_id)", "dvsh_service.service_id without a service"),
        ("SELECT COUNT(*) FROM shep_service v WHERE v.service_id IS NOT NULL AND NOT EXISTS "
         "(SELECT 1 FROM service s WHERE s.id=v.service_id)", "shep_service.service_id without a service"),
    ):
        try:
            n = count(sql)
        except Exception:
            continue
        if n: errors.append(f"{n} rows: {msg}")

    # the documented schema yields every table AND every column the database has
    try:
        import sqlite3 as _sq
        from common import SCHEMA_PATH
        scratch = _sq.connect(":memory:")
        scratch.executescript(open(SCHEMA_PATH, encoding="utf-8").read())
        doc_cols = {}
        for (t,) in scratch.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            doc_cols[t] = {r[1] for r in scratch.execute(f"PRAGMA table_info({t})")}
        live = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                           "AND name NOT LIKE 'sqlite_%'")}
        missing = sorted(live - set(doc_cols))
        if missing: errors.append(f"{len(missing)} tables are not documented in schema.sql: {missing}")
        for t in sorted(live & set(doc_cols)):
            lc = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
            if lc - doc_cols[t]:
                errors.append(f"schema.sql lacks columns of {t}: {sorted(lc - doc_cols[t])}")
        # explicit indices (sqlite_autoindex_* carry no SQL and are not listed)
        doc_ix = {r[0] for r in scratch.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")}
        live_ix = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")}
        if live_ix - doc_ix:
            errors.append(f"schema.sql lacks indices: {sorted(live_ix - doc_ix)}")
    except OSError:
        pass

    # file paths are composed Unicode (NFC) like the tracked files — a decomposed
    # path works on a Mac and 404s on a Linux web server
    if "source_file" in _cols(conn, "form"):
        import unicodedata as _ud
        n = sum(1 for (sf,) in conn.execute("SELECT source_file FROM form WHERE source_file IS NOT NULL")
                if sf != _ud.normalize("NFC", sf))
        if n: errors.append(f"{n} form.source_file values are not in composed Unicode (NFC)")
        # the Quelldatei link on the website resolves only for a tracked copy in
        # formulare/ (flat), resolved against the repository root, never the cwd.
        # Compared with the exact folder listing (names in NFC, as Git stores
        # them): the default macOS file system also opens a name that differs in
        # case or leaves the folder through '..', and GitHub Pages serves neither.
        fdir = os.path.join(ROOT, "formulare")
        listed = ({_ud.normalize("NFC", f) for f in os.listdir(fdir) if os.path.isfile(os.path.join(fdir, f))}
                  if os.path.isdir(fdir) else set())
        bad = [sf for (sf,) in conn.execute("SELECT source_file FROM form WHERE source_file IS NOT NULL")
               if not sf.startswith("formulare/") or sf[len("formulare/"):] not in listed]
        if bad: errors.append(f"{len(bad)} form.source_file values are not an existing file under formulare/: "
                              f"{bad[:3]}")
        # file_type agrees with the file: pdf <-> .pdf, word <-> .doc/.docx,
        # excel <-> .xls/.xlsx/.xlsm, eformular <-> no file
        if "file_type" in _cols(conn, "form"):
            want = {".pdf": "pdf", ".doc": "word", ".docx": "word",
                    ".xls": "excel", ".xlsx": "excel", ".xlsm": "excel"}
            bad = [(fid, ft, sf) for fid, ft, sf in conn.execute("SELECT id, file_type, source_file FROM form")
                   if ft != (want.get(os.path.splitext(sf)[1].lower(), "?") if sf else "eformular")]
            if bad: errors.append(f"{len(bad)} form rows whose file_type disagrees with the file extension: "
                                  f"ids {[b[0] for b in bad][:8]}")

    # the verification level shown for a citation is the ARTICLE's (one source)
    if _has(conn, "data_field_legal_basis"):
        n = count("SELECT COUNT(*) FROM data_field_legal_basis d JOIN article a ON a.id=d.article_id "
                  "WHERE d.last_checked IS NOT a.last_checked")
        if n: errors.append(f"{n} data_field_legal_basis rows carry a verification level that differs from their article")

    # second opinions: every active sektoral provision and every verdict has a review row
    # (the VRG general rule, id 1, is exempt; items added after the review carry 'offen')
    if _has(conn, "panel_review") and _has(conn, "rechtsmittel_regel"):
        n = count("SELECT COUNT(*) FROM rechtsmittel_regel r WHERE r.scope='sektoral' AND COALESCE(r.gestrichen,0)=0 "
                  "AND NOT EXISTS (SELECT 1 FROM panel_review p WHERE p.kind='rmrule' AND p.item_id=r.id)")
        if n: errors.append(f"{n} active sektoral remedy provisions have no second-opinion row (panel_review rmrule)")
        if _has(conn, "rechtsmittel_verdikt"):
            n = count("SELECT COUNT(*) FROM rechtsmittel_verdikt v WHERE NOT EXISTS "
                      "(SELECT 1 FROM panel_review p WHERE p.kind='rmverdict' AND p.item_id=v.form_id)")
            if n: errors.append(f"{n} remedy verdicts have no second-opinion row (panel_review rmverdict)")

    return errors


# ---- Gestaltung: how a Formular looks (scan_gestaltung.py) ---------------------
# The top-level keys of form_gestaltung.profil, identical for every messart (a
# value that could not be measured is null, the key stays). scan_gestaltung.py
# checks each measured profile against this tuple before it writes the row.
GESTALTUNG_KEYS = ("messart", "seiten", "seitenformat", "schriften", "hauptschrift", "n_schriftfamilien",
                   "groessen", "grundgroesse", "kleinste", "anteil_unter_8", "farben", "akzent",
                   "n_farbfamilien", "anteil_text_farbig", "barrierefrei", "telefon", "email", "elemente",
                   "ausfuellbar", "hinweise")
# form.file_type -> the messart values a measurement of such a file can have
GESTALTUNG_MESSART = {"pdf": ("pdf", "pdf_bild"), "word": ("word", "nicht_messbar"),
                      "excel": ("excel", "nicht_messbar")}


def gestaltung_spalten(profil):
    """The scalar columns of form_gestaltung as they follow from a profil: the
    ONE mapping, used by scan_gestaltung.py to write a row and by the gate
    below to check it. hinweise is NULL when the measurement names none."""
    akzent, tags, pt = profil["akzent"], profil["barrierefrei"]["tags"], profil["grundgroesse"]
    return {"messart": profil["messart"], "seiten": profil["seiten"],
            "hauptschrift": profil["hauptschrift"], "grundgroesse": None if pt is None else float(pt),
            "akzentfarbe": akzent["hex"] if akzent else None,
            "pdf_tags": None if tags is None else int(bool(tags)),
            "hinweise": json.dumps(profil["hinweise"], ensure_ascii=False) if profil["hinweise"] else None}


def gestaltung_checks(conn):
    """form_gestaltung is a set of measured facts about the file a Formular
    points at. Skipped when the table does not exist yet."""
    if not _has(conn, "form_gestaltung"):
        return []
    need = {"form_id", "file_hash", "messart", "methode", "seiten", "hauptschrift", "grundgroesse",
            "akzentfarbe", "pdf_tags", "profil", "hinweise"}
    if not need <= _cols(conn, "form_gestaltung"):
        return [f"Gestaltung gate cannot run: form_gestaltung lacks {sorted(need - _cols(conn, 'form_gestaltung'))}"]
    form_cols = _cols(conn, "form")
    if not {"source_file", "file_type", "file_hash"} <= form_cols:
        return ["Gestaltung gate cannot run: form lacks source_file/file_type/file_hash"]
    errors = []
    bad = {k: [] for k in ("form", "stale", "messart", "methode", "profil", "keys", "columns", "tags")}
    for r in conn.execute(
            "SELECT g.*, f.id AS f_id, f.source_file AS f_source, f.file_type AS f_type, f.file_hash AS f_hash "
            "FROM form_gestaltung g LEFT JOIN form f ON f.id = g.form_id ORDER BY g.form_id"):
        fid = r["form_id"]
        if r["f_id"] is None or not r["f_source"]:
            bad["form"].append(fid)             # no Formular, or one without a file (eFormular)
            continue
        if r["file_hash"] != r["f_hash"]:
            bad["stale"].append(fid)
        if r["messart"] not in GESTALTUNG_MESSART.get(r["f_type"], ()):
            bad["messart"].append(fid)
        if not (r["methode"] or "").strip():
            bad["methode"].append(fid)
        if r["messart"] not in ("pdf", "pdf_bild") and r["pdf_tags"] is not None:
            bad["tags"].append(fid)
        try:
            profil = json.loads(r["profil"])
            if not isinstance(profil, dict):
                raise ValueError("not an object")
        except (TypeError, ValueError):
            bad["profil"].append(fid)
            continue
        if set(profil) != set(GESTALTUNG_KEYS):
            bad["keys"].append(fid)
            continue
        try:
            want = gestaltung_spalten(profil)
            if not isinstance(profil["hinweise"], list):
                raise TypeError("hinweise is not a list")
        except (TypeError, ValueError, KeyError, AttributeError):
            bad["profil"].append(fid)           # a nested part has the wrong shape
            continue
        if any(type(r[k]) is not type(v) or r[k] != v for k, v in want.items()):
            bad["columns"].append(fid)
    for key, text in (
            ("form", "point at no Formular with a source_file"),
            ("stale", "are stale: file_hash differs from form.file_hash (whoever changes form.file_hash "
                      "removes the row, as scan_documents.py does; scan_gestaltung.py measures the new file)"),
            ("messart", "carry a messart that disagrees with form.file_type"),
            ("methode", "have an empty methode"),
            ("tags", "carry pdf_tags although the file is not a PDF"),
            ("profil", "hold a profil that is not a JSON object of the expected shape"),
            ("keys", "hold a profil whose top-level keys differ from GESTALTUNG_KEYS"),
            ("columns", "have scalar columns that differ from their profil")):
        if bad[key]:
            errors.append(f"{len(bad[key])} form_gestaltung rows {text}: form ids {bad[key][:8]}")
    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    if not os.path.exists(path):
        print(f"no database at {path}", file=sys.stderr)
        sys.exit(2)
    conn = connect(path)
    errors = validate(conn)
    conn.close()
    if errors:
        print(f"INVALID ({len(errors)} problem(s)):")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print(f"valid: {path}")


if __name__ == "__main__":
    main()
