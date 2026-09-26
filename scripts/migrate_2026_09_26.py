#!/usr/bin/env python3
"""One-off data corrections from the quality check of 2026-09-26, each with its
evidence, applied staging -> validate -> swap. Idempotent: a second run changes
nothing and reports 0 everywhere.

  1. Organisation names: the DVSH spelling replaces ASCII-transliterated and
     misspelt values (Veterinaeramt -> Veterinäramt, «Department des Innern» ->
     «Departement des Innern», Sekretariat Finanzdepartment -> …departement) in
     service, dienststelle and form.publisher_dienststelle. Two Dienststelle
     rows that were the same office under two spellings are merged. Source
     file paths are NOT touched (they are paths, not names).
  2. data_field_legal_basis.relation: 'verlangt' (one loader's German) becomes
     'requires' (the documented vocabulary).
  3. law 304: short_title «Pensionskassengesetz Vom 10. Juni 2013 (» -> the
     title without the date suffix; law 252 (SHR 822.101): «Verordnung» -> «V ArG/UVG (SH)».
  4. Waffenverordnung Art. 66: the 30-Jahre term (retention_term 6) hung on a
     quote that says 50 Jahre (Abs. 1). A second rule carries the Abs. 2
     sentence verbatim (checked against Gesetze/Bund/514.541.pdf); term 6 moves
     to it. Abs. 1 (50 Jahre, the federal systems) keeps its rule WITHOUT a
     term — a term there fanned out to every Waffen form as a 50-year retention.
  9. data_field_legal_basis.last_checked equals its article's level (one source
     for the badge; 89 rows said «Gesetze-PDF AVG (ingestiert)» for verified
     federal articles), and «611.100» is named as SHR.
 10. The partial online re-check of 2026-09-26 must not override four curated
     «aktuell» verdicts whose note says the ONLINE copy is the older edition.
 11. Remedy provisions and verdicts added after the second review carry a
     panel_review row 'offen' (review pending) so the gate can see them.
 12. 240 technical snake_case keys that stood as field/part names (132 fields,
     108 parts) are renamed to the form's own labels
     (quellen/korrekturen/feldnamen_2026-09-26.json), plus the lowercase
     single-token keys (feldnamen2_…) and five ASCII umlaut transliterations
     (feldnamen3_…); flow references and the
     naming verdicts keyed by those names move with them.
 13. Seven early article rows (ids 252-258) with a bare number and a status note
     as heading: five duplicates folded into the properly numbered row of the
     same law, two renumbered with the heading the law PDF prints.
 14. Two rule summaries aligned with their law text (MedBG Art. 54 clock
     starts; KDSG Art. 5 Abs. 1 lit. b presumed consent); quotes unchanged.
 15. form.source_file in composed Unicode (NFC), as Git stores the files:
     22 decomposed paths would 404 on a Linux web server (GitHub Pages).
  5. rechtsmittel_verdikt of form 414 named provision 116, which the second
     review struck: the verdict becomes 'offen' with the reason recorded.
  6. data_subfield.esh_code/esh_element restored for 1,221 parts from
     quellen/korrekturen/subfield_esh_2026-09-03.json (wiped by the 2026-09-03
     rebuild of data_subfield), only where no eCH element sits (convention 7).
  7. data_field 2428 (Konfession, Grundstückgewinnsteuer): the reason cited a
     decree that is not among the ingested law texts; the reason now states
     that the norm is still to be sourced instead of citing it from memory.
  8. The 240 placeholder law rows of the 2026-06 auto-draft (last_checked
     'zitiert (unverifiziert)'), their 240 article rows and 7,685
     requirement_legal_basis rows are removed: no curated table references
     them, and they reached the search index and the LLM export as if they
     were laws.

    python3 scripts/migrate_2026_09_26.py
"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DB_PATH, connect
from validate_db import validate
from load_data_rules import law_pdf
from load_rechtsmittel import quote_ok

ORG = {
    "Abteilung Gewaesser und Materialabbau": "Abteilung Gewässer und Materialabbau",
    "Amt fuer Denkmalpflege und Archaeologie": "Amt für Denkmalpflege und Archäologie",
    "Amt fuer Geoinformation": "Amt für Geoinformation",
    "Amt fuer Grundstueckschaetzungen": "Amt für Grundstückschätzungen",
    "Amt fuer Justiz und Gemeinden": "Amt für Justiz und Gemeinden",
    "Bevoelkerungsschutz und Armee": "Bevölkerungsschutz und Armee",
    "Kantonsaerztlicher Dienst": "Kantonsärztlicher Dienst",
    "Kindes- und Erwachsenenschutzbehoerde": "Kindes- und Erwachsenenschutzbehörde",
    "Migrationsamt und Passbuero": "Migrationsamt und Passbüro",
    "Sekretariat Finanzdepartment": "Sekretariat Finanzdepartement",
    "Veterinaeramt": "Veterinäramt",
    "Gebaudeversicherung": "Gebäudeversicherung",
    "Department des Innern": "Departement des Innern",
    "Finanzdepartement ": "Finanzdepartement",
    "Feuerpolizei": "Kantonale Feuerpolizei",
    "Arbeitsmarktliche Massnahmen AMM": "Arbeitsmarktliche Massnahmen",
}
ART66_ABS2 = ("Die Daten der elektronischen Informationssysteme über den Erwerb und den Besitz von "
              "Feuerwaffen und des gemeinsamen harmonisierten Informationssystems über den Erwerb und "
              "den Besitz von Feuerwaffen werden während 30 Jahren nach Vernichtung der Waffe aufbewahrt.")
FIELD_2428_WHY = ("Zweitprüfung: Die Konfession bestimmt, ob und an welche Landeskirche die Kirchensteuer "
                  "auf dem Grundstückgewinn geht — ohne sie kann die Steuerverwaltung die Aufgabe nicht "
                  "erfüllen. Die massgebende Norm (kirchliches Steuerdekret) ist nicht unter den "
                  "eingelesenen Gesetzestexten und daher hier nicht zitiert; als besonders schützenswertes "
                  "Datum braucht es zudem eine Grundlage nach KDSG Art. 5 Abs. 1 — noch zu belegen.")


def main():
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    rep = {}

    # 1. organisation names --------------------------------------------------
    n = 0
    for col, tbl in (("dienststelle", "service"), ("department", "service"), ("department", "dienststelle"),
                     ("publisher_dienststelle", "form"), ("dienststelle", "document")):
        for old, new in ORG.items():
            n += c.execute(f"UPDATE {tbl} SET {col}=? WHERE {col}=?", [new, old]).rowcount
    # dienststelle.name is the primary key: merge into the existing row where the
    # correct spelling already exists, keeping whichever row has contact data
    for old, new in ORG.items():
        o = c.execute("SELECT * FROM dienststelle WHERE name=?", [old]).fetchone()
        if not o:
            continue
        t = c.execute("SELECT * FROM dienststelle WHERE name=?", [new]).fetchone()
        if t:
            for col in ("department", "dateninhaber", "kontakt"):
                if not t[col] and o[col]:
                    c.execute(f"UPDATE dienststelle SET {col}=? WHERE name=?", [o[col], new])
            c.execute("DELETE FROM dienststelle WHERE name=?", [old])
        else:
            c.execute("UPDATE dienststelle SET name=? WHERE name=?", [new, old])
        n += 1
    # a service filed under the placeholder department «Verwaltung» takes the
    # department the DVSH organisation tree gives its Dienststelle
    for r in c.execute("""WITH RECURSIVE up(sid, dst, id, name, kind, parent_id) AS (
                              SELECT s.id, s.dienststelle, o.id, o.name, o.kind, o.parent_id FROM service s
                              JOIN dvsh_organisation o ON o.name=s.dienststelle WHERE s.department='Verwaltung'
                              UNION ALL
                              SELECT up.sid, up.dst, p.id, p.name, p.kind, p.parent_id FROM dvsh_organisation p
                              JOIN up ON p.id=up.parent_id WHERE up.name NOT LIKE '%departement%')
                          SELECT sid AS id, dst AS dienststelle, name AS dep FROM up
                          WHERE name LIKE '%departement%'""").fetchall():
        c.execute("UPDATE service SET department=? WHERE id=?", [r["dep"], r["id"]]); n += 1
        c.execute("UPDATE dienststelle SET department=? WHERE name=? AND department='Verwaltung'",
                  [r["dep"], r["dienststelle"]])
    rep["1 Organisationsnamen"] = n

    # 2. relation vocabulary ---------------------------------------------------
    rep["2 relation verlangt->requires"] = c.execute(
        "UPDATE data_field_legal_basis SET relation='requires' WHERE relation='verlangt'").rowcount

    # 3. law 304 short title ----------------------------------------------------
    rep["3 short_title"] = c.execute(
        "UPDATE law SET short_title='Pensionskassengesetz' WHERE id=304 AND short_title LIKE '%Vom %'").rowcount

    # 4. Waffenverordnung Art. 66 Abs. 2 ----------------------------------------
    r40 = c.execute("SELECT dr.*, a.law_id, l.sr_number, l.jurisdiction_level FROM data_rule dr "
                    "JOIN article a ON a.id=dr.article_id JOIN law l ON l.id=a.law_id WHERE dr.id=40").fetchone()
    done = c.execute("SELECT id FROM data_rule WHERE article_id=? AND quote=?",
                     [r40["article_id"], ART66_ABS2]).fetchone()
    if r40 and not done:
        pdf = law_pdf(r40["sr_number"], r40["jurisdiction_level"])
        if not pdf or not quote_ok(ART66_ABS2, pdf):
            os.remove(st); sys.exit("ABORT: WV Art. 66 Abs. 2 quote not found verbatim in the PDF")
        c.execute("INSERT INTO data_rule(article_id, aspect, scope, sensitive_category, summary, quote, "
                  "quote_verified, last_checked) VALUES(?,?,?,?,?,?,1,?)",
                  [r40["article_id"], "aufbewahrung", "sektoral", None,
                   "Die Daten der Informationssysteme über Erwerb und Besitz von Feuerwaffen werden "
                   "30 Jahre nach Vernichtung der Waffe aufbewahrt.", ART66_ABS2, "Gesetze-PDF 514.541"])
        new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("UPDATE retention_term SET data_rule_id=? WHERE id=6", [new_id])
        rep["4 WV Art. 66 Abs. 2"] = 1
    else:
        rep["4 WV Art. 66 Abs. 2"] = 0
    # Abs. 1 (50 Jahre) governs the FEDERAL systems (fedpol: DEWA, DEWS, …), not what a
    # cantonal Formular feeds; a term on it would fan out to every Waffen form. Rule 40
    # keeps its verified quote as a rule without a term.
    c.execute("UPDATE data_rule SET summary=? WHERE id=40",
              ["Abs. 1: die Informationssysteme des Bundes (DEWA, DEWS, DEBBWA, DAWA, ASWA, DARUE, DANTRAG) "
               "werden während 50 Jahren aufbewahrt — nicht die Frist der kantonalen Systeme; für diese gilt "
               "Abs. 2 (30 Jahre nach Vernichtung der Waffe)."])
    rep["4b Frist auf Abs. 1 entfernt"] = c.execute("DELETE FROM retention_term WHERE data_rule_id=40").rowcount

    # 5. verdict on a struck provision -----------------------------------------
    rep["5 Verdikt auf gestrichener Norm"] = c.execute(
        "UPDATE rechtsmittel_verdikt SET regel_id=NULL, quelle='offen', last_checked='Panel-Zweitprüfung', "
        "begruendung=substr('Zweitprüfung: die zugeordnete Norm wurde in der Zweitprüfung gestrichen — ' "
        "|| begruendung, 1, 400) WHERE regel_id IN (SELECT id FROM rechtsmittel_regel WHERE gestrichen=1)").rowcount

    # 6. subfield eSH restore -----------------------------------------------------
    src = json.load(open(os.path.join(ROOT, "quellen", "korrekturen", "subfield_esh_2026-09-03.json"),
                         encoding="utf-8"))
    known = {r[0] for r in c.execute("SELECT code FROM esh_standard")}
    n = skipped = 0
    for z in src["zuordnungen"]:
        if z["esh_code"] not in known:
            skipped += 1; continue
        n += c.execute("UPDATE data_subfield SET esh_code=?, esh_element=? WHERE data_field_id=? AND name=? "
                       "AND ech_element_id IS NULL AND esh_code IS NULL "
                       "AND (ech_status IS NULL OR ech_status='kein_standard')",
                       [z["esh_code"], z["esh_element"], z["data_field_id"], z["teilfeld"]]).rowcount
    rep["6 Teilfeld-eSH wiederhergestellt"] = n
    rep["6 Teilfeld-eSH übersprungen (Code unbekannt)"] = skipped

    # 7. field 2428 reason ---------------------------------------------------------
    rep["7 Feld 2428 Begründung"] = c.execute(
        "UPDATE data_field SET basis_begruendung=? WHERE id=2428 AND basis_begruendung LIKE '%Kirchensteuerdekret%'",
        [FIELD_2428_WHY]).rowcount

    # 3b. law 252: short_title «Verordnung» says nothing in a citation chip ----------
    rep["3b short_title 822.101"] = c.execute(
        "UPDATE law SET short_title='V ArG/UVG (SH)' WHERE id=252 AND cantonal_ref='SHR 822.101' "
        "AND short_title='Verordnung'").rowcount

    # 9. the verification level of a citation is its ARTICLE's (one source) ---------
    rep["9 dflb.last_checked = article"] = c.execute(
        "UPDATE data_field_legal_basis SET last_checked=(SELECT a.last_checked FROM article a "
        "WHERE a.id=data_field_legal_basis.article_id) WHERE last_checked IS NOT "
        "(SELECT a.last_checked FROM article a WHERE a.id=data_field_legal_basis.article_id)").rowcount
    n = c.execute("UPDATE article SET last_checked='Gesetze-PDF SHR 611.100' WHERE last_checked='Gesetze-PDF 611.100'").rowcount
    n += c.execute("UPDATE data_field_legal_basis SET last_checked='Gesetze-PDF SHR 611.100' "
                   "WHERE last_checked='Gesetze-PDF 611.100'").rowcount
    rep["9b 611.100 als SHR bezeichnet"] = n

    # 10. the partial online re-check never overrides a curated «aktuell» -----------
    # (rows 53, 54, 158, 160: the note says the ONLINE copy is the older edition)
    n = 0
    import sqlite3 as _sq, subprocess, tempfile
    try:
        blob = subprocess.run(["git", "-C", ROOT, "cat-file", "-p", "HEAD:citygov.db"], capture_output=True, check=True).stdout
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); tmp.write(blob); tmp.close()
        head = _sq.connect(tmp.name); head.row_factory = _sq.Row
        rows_ = head.execute("SELECT form_id, status, quelle, online_name, online_url, dvsh_neu, note FROM form_check "
                             "WHERE form_id IN (53,54,158,160) AND status='aktuell'").fetchall()
        head.close(); os.unlink(tmp.name)
        for r in rows_:
            cur = c.execute("SELECT status, note FROM form_check WHERE form_id=?", [r["form_id"]]).fetchone()
            if cur and cur["status"] == "veraltet_verdacht" and "Online-Nachprüfung" in (cur["note"] or ""):
                c.execute("INSERT OR REPLACE INTO form_check(form_id,status,quelle,online_name,online_url,dvsh_neu,note,"
                          "checked_at,next_check_due) VALUES(?,?,?,?,?,?,?,datetime('now'),date('now','+42 days'))",
                          [r["form_id"], "aktuell", r["quelle"], r["online_name"], r["online_url"], r["dvsh_neu"],
                           (r["note"] or "") + "; Online-Nachprüfung 2026-09-26: gleichnamige Datei mit anderem Inhalt "
                                               "(Hash) — frühere Prüfung bestätigt, unsere Fassung ist die neuere"])
                n += 1
    except Exception as ex:
        print("  10: kuratierte form_check-Zeilen nicht wiederhergestellt:", ex)
    rep["10 kuratierte Online-Prüfungen bewahrt"] = n

    # 11. second opinions: items added after the review are marked «offen» ------------
    n = 0
    for rid in [r[0] for r in c.execute("SELECT id FROM rechtsmittel_regel WHERE scope='sektoral' AND COALESCE(gestrichen,0)=0 "
                                        "AND NOT EXISTS (SELECT 1 FROM panel_review p WHERE p.kind='rmrule' AND p.item_id=rechtsmittel_regel.id)")]:
        c.execute("INSERT INTO panel_review(kind,item_id,urteil,grund) VALUES('rmrule',?,'offen',?)",
                  [rid, "Zweitprüfung ausstehend — Norm am 2026-09-26 nachgetragen (Qualitätsprüfung)"]); n += 1
    for fid in [r[0] for r in c.execute("SELECT form_id FROM rechtsmittel_verdikt v WHERE NOT EXISTS "
                                        "(SELECT 1 FROM panel_review p WHERE p.kind='rmverdict' AND p.item_id=v.form_id)")]:
        c.execute("INSERT INTO panel_review(kind,item_id,urteil,grund) VALUES('rmverdict',?,'offen',?)",
                  [fid, "Zweitprüfung ausstehend — Verdikt am 2026-09-26 nachgetragen (Qualitätsprüfung)"]); n += 1
    rep["11 Zweitprüfung ausstehend markiert"] = n

    # 8. placeholder laws of the auto-draft ------------------------------------------
    ph = "SELECT id FROM law WHERE last_checked='zitiert (unverifiziert)'"
    for tbl, col in (("data_field_legal_basis", "article_id"), ("data_rule", "article_id"),
                     ("form_disclosure", "article_id"), ("rechtsmittel_regel", "article_id"),
                     ("form_outcome", "article_id")):
        n = c.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {col} IN (SELECT id FROM article WHERE law_id IN ({ph}))").fetchone()[0]
        if n:
            os.remove(st); sys.exit(f"ABORT: {n} curated rows in {tbl} reference a placeholder law")
    n1 = c.execute(f"DELETE FROM requirement_legal_basis WHERE article_id IN (SELECT id FROM article WHERE law_id IN ({ph}))").rowcount
    n2 = c.execute(f"DELETE FROM article WHERE law_id IN ({ph})").rowcount
    n3 = c.execute(f"DELETE FROM law WHERE last_checked='zitiert (unverifiziert)'").rowcount
    rep["8 Platzhalter-Gesetze entfernt (law/article/requirement_legal_basis)"] = (n3, n2, n1)

    # 13. seven early article rows (ids 252-258) carried a bare number and a status
    # note («im Formular zitiert, in Quelle bestätigt») as heading. Five duplicate a
    # properly numbered row of the same law: their references move to that row and
    # the duplicate goes. Two have no twin: they get the number and the heading the
    # law PDF prints (814.100 Art. 39 / 822.101 § 12 «Inkrafttreten»).
    TWINS = {252: 996, 253: 322, 254: 1037, 256: 2009, 257: 947}
    OWN = {255: ("Art. 39", "Inkrafttreten", "Gesetze-PDF SHR 814.100"),
           258: ("§ 12", "Inkrafttreten", "Gesetze-PDF SHR 822.101")}
    n = 0
    for old_id, new_id in TWINS.items():
        if not c.execute("SELECT 1 FROM article WHERE id=?", [old_id]).fetchone():
            continue
        lc = c.execute("SELECT last_checked FROM article WHERE id=?", [new_id]).fetchone()[0]
        n += c.execute("UPDATE data_field_legal_basis SET article_id=?, last_checked=? WHERE article_id=?",
                       [new_id, lc, old_id]).rowcount
        # a field may now cite the twin twice — keep one row per (field, article)
        c.execute("DELETE FROM data_field_legal_basis WHERE article_id=? AND id NOT IN "
                  "(SELECT MIN(id) FROM data_field_legal_basis WHERE article_id=? GROUP BY data_field_id)",
                  [new_id, new_id])
        c.execute("UPDATE OR IGNORE requirement_legal_basis SET article_id=? WHERE article_id=?", [new_id, old_id])
        c.execute("DELETE FROM requirement_legal_basis WHERE article_id=?", [old_id])
        c.execute("DELETE FROM article WHERE id=?", [old_id])
        n += 1
    for aid, (no, heading, lc) in OWN.items():
        n += c.execute("UPDATE article SET article_no=?, heading=?, last_checked=? WHERE id=? AND article_no NOT LIKE '%.%' "
                       "AND article_no NOT LIKE '§%'", [no, heading, lc, aid]).rowcount
        c.execute("UPDATE data_field_legal_basis SET last_checked=? WHERE article_id=?", [lc, aid])
    rep["13 Artikel mit Status-Notiz bereinigt"] = n

    # 14. two rule summaries paraphrased their law incompletely (the quote, the proof,
    # is unchanged): MedBG Art. 54 names what starts each clock; KDSG Art. 5 Abs. 1
    # lit. b also accepts consent unmistakably presumed from the circumstances.
    n = c.execute("UPDATE data_rule SET summary=? WHERE id=70 AND summary LIKE '%nach zehn Jahren als gelöscht%'",
                  ["Registereinträge werden entfernt: Einschränkungen fünf Jahre nach ihrer Aufhebung, Verwarnungen, "
                   "Verweise und Bussen fünf Jahre nach ihrer Anordnung; bei einem befristeten Berufsausübungsverbot wird "
                   "zehn Jahre nach seiner Aufhebung «gelöscht» vermerkt; meldet eine Behörde das Ableben, werden alle "
                   "Einträge zur Person entfernt (MedBG Art. 54 Abs. 1–3, 5)."]).rowcount
    n += c.execute("UPDATE data_rule SET summary=? WHERE id=86 AND summary LIKE '%ausdrücklich zustimmt.'",
                   ["Besonders schützenswerte Personendaten dürfen nur bearbeitet und ein Profiling darf nur vorgenommen "
                    "werden, wenn ein formelles Gesetz es ausdrücklich vorsieht oder es für eine in einem formellen Gesetz "
                    "klar umschriebene Aufgabe unentbehrlich ist, oder wenn die betroffene Person ausdrücklich zugestimmt "
                    "hat oder ihre Zustimmung nach den Umständen unzweifelhaft vorausgesetzt werden darf."]).rowcount
    rep["14 Regel-Zusammenfassungen am Gesetz ausgerichtet"] = n

    # 15. file paths in composed Unicode (NFC). Git stores the Formular files with
    # composed umlauts; 22 source_file values were decomposed (NFD, as macOS hands
    # them out). The Mac treats both as one file, a Linux web server (GitHub Pages)
    # does not — those «Quelldatei» links would answer 404 online.
    import unicodedata as _ud
    n = 0
    for fid, sf in c.execute("SELECT id, source_file FROM form WHERE source_file IS NOT NULL").fetchall():
        nfc = _ud.normalize("NFC", sf)
        if nfc != sf:
            n += c.execute("UPDATE form SET source_file=? WHERE id=?", [nfc, fid]).rowcount
    rep["15 Dateipfade in NFC"] = n

    # 12. technical snake_case keys shown as field names -> the form's own labels ----
    # (quellen/korrekturen/feldnamen_2026-09-26.json, judged from the form text and
    # second-reviewed). Everything keyed by a field NAME moves with it, in one step:
    #   * data_subfield.name AND the parent's subfields JSON (init_subfields.py
    #     rebuilds data_subfield from that JSON)
    #   * formflow nodes[].field[] (data-field references; the flows' own answer keys
    #     fields[].key / node ids stay — fill_pdf resolves through data_field.name)
    #   * begriff_label rows keyed (element, norm_label(name)): re-keyed to the new
    #     label (a copy per new label when one old label becomes several; an existing
    #     verdict on the new wording wins), and a proposed term that was itself a
    #     snake_case key becomes the new label
    # Runs after step 6 on purpose: the eSH snapshot is keyed by the old part names.
    from common import norm_label
    n = 0
    import glob as _glob
    for fn in sorted(_glob.glob(os.path.join(ROOT, "quellen", "korrekturen", "feldnamen*_2026-09-26.json"))):
        K = json.load(open(fn, encoding="utf-8"))
        form_of = {r[0]: r[1] for r in c.execute("SELECT id, form_id FROM data_field")}
        elem_of_df = {r[0]: r[1] for r in c.execute("SELECT id, ech_element_id FROM data_field")}
        elem_of_sf = {r[0]: r[1] for r in c.execute("SELECT id, ech_element_id FROM data_subfield")}
        sib = {}
        for r in c.execute("SELECT id, standard, name FROM ech_element"):
            sib.setdefault((r[1], r[2]), []).append(r[0])
        sib_of = {eid: ids for ids in sib.values() for eid in ids}
        rekey = {}                      # (element ids tuple, old_norm) -> {new labels}
        flow_map = {}                   # form_id -> {old data_field name -> new}
        for k in K.get("felder", []):
            if k["alt"] == k["neu"]:
                continue
            m = c.execute("UPDATE data_field SET name=? WHERE id=? AND name=?", [k["neu"], k["data_field_id"], k["alt"]]).rowcount
            n += m
            if m:
                flow_map.setdefault(form_of.get(k["data_field_id"]), {})[k["alt"]] = k["neu"]
                e = elem_of_df.get(k["data_field_id"])
                if e:
                    rekey.setdefault((tuple(sib_of.get(e, [e])), norm_label(k["alt"])), set()).add(k["neu"])
        for k in K.get("teilfelder", []):
            if k["alt"] == k["neu"]:
                continue
            m = c.execute("UPDATE data_subfield SET name=? WHERE id=? AND name=?", [k["neu"], k["subfield_id"], k["alt"]]).rowcount
            if not m:
                continue
            n += m
            row = c.execute("SELECT subfields FROM data_field WHERE id=?", [k["data_field_id"]]).fetchone()
            try:
                subs = json.loads(row["subfields"]) if row and row["subfields"] else []
            except Exception:
                subs = []
            changed = False
            for i, x in enumerate(subs):
                if isinstance(x, str) and x.strip() == k["alt"]:
                    subs[i] = k["neu"]; changed = True
                elif isinstance(x, dict) and (x.get("name") or "").strip() == k["alt"]:
                    x["name"] = k["neu"]; changed = True
            if changed:
                c.execute("UPDATE data_field SET subfields=? WHERE id=?", [json.dumps(subs, ensure_ascii=False), k["data_field_id"]])
            e = elem_of_sf.get(k["subfield_id"])
            if e:
                rekey.setdefault((tuple(sib_of.get(e, [e])), norm_label(k["alt"])), set()).add(k["neu"])
        # guided flows: data-field references by name
        nf = 0
        for form_id, mp in flow_map.items():
            r = c.execute("SELECT flow FROM formflow WHERE form_id=?", [form_id]).fetchone()
            if not r:
                continue
            fl = json.loads(r["flow"])
            hit = False
            for node in fl.get("nodes", []):
                if isinstance(node, dict) and isinstance(node.get("field"), list):
                    new_f = [mp.get(x, x) for x in node["field"]]
                    if new_f != node["field"]:
                        node["field"] = new_f; hit = True; nf += 1
            if hit:
                c.execute("UPDATE formflow SET flow=? WHERE form_id=?", [json.dumps(fl, ensure_ascii=False), form_id])
        rep["12b Flow-Verweise umbenannt"] = rep.get("12b Flow-Verweise umbenannt", 0) + nf
        # naming verdicts
        nb = 0
        still = {(r[0], norm_label(r[1])) for r in c.execute(
            "SELECT ech_element_id, name FROM data_field WHERE ech_element_id IS NOT NULL "
            "UNION SELECT ech_element_id, name FROM data_subfield WHERE ech_element_id IS NOT NULL")}
        for (eids, old_norm), news in rekey.items():
            ph = ",".join("?" * len(eids))
            rows_ = c.execute(f"SELECT * FROM begriff_label WHERE label_norm=? AND ech_element_id IN ({ph})",
                              [old_norm, *eids]).fetchall()
            for r in rows_:
                for new_label in sorted(news):
                    if not c.execute("SELECT 1 FROM begriff_label WHERE ech_element_id=? AND label_norm=?",
                                     [r["ech_element_id"], norm_label(new_label)]).fetchone():
                        c.execute("INSERT INTO begriff_label(ech_element_id, label_norm, label, klasse, rolle, grund, "
                                  "zweitgeprueft, pruefart, pruefart_grund) VALUES(?,?,?,?,?,?,?,?,?)",
                                  [r["ech_element_id"], norm_label(new_label), new_label, r["klasse"], r["rolle"],
                                   r["grund"], r["zweitgeprueft"], r["pruefart"], r["pruefart_grund"]])
                        nb += 1
                if not any((e2, old_norm) in still for e2 in eids):
                    c.execute("DELETE FROM begriff_label WHERE ech_element_id=? AND label_norm=?", [r["ech_element_id"], old_norm])
                elif len(news) == 1 and norm_label(next(iter(news))) == old_norm:
                    # same key (only case/umlaut spelling changed): show the form's own spelling
                    c.execute("UPDATE begriff_label SET label=? WHERE ech_element_id=? AND label_norm=?",
                              [next(iter(news)), r["ech_element_id"], old_norm])
            for r in c.execute(f"SELECT ech_element_id, term FROM begriff_vorschlag WHERE ech_element_id IN ({ph})", list(eids)).fetchall():
                if norm_label(r["term"]) == old_norm and len(news) == 1 and r["term"] != next(iter(news)):
                    c.execute("UPDATE begriff_vorschlag SET term=? WHERE ech_element_id=?", [next(iter(news)), r["ech_element_id"]])
                    nb += 1
        rep["12c Begriffs-Urteile neu verschlüsselt"] = rep.get("12c Begriffs-Urteile neu verschlüsselt", 0) + nb
    rep["12 Feldnamen aus dem Formular"] = rep.get("12 Feldnamen aus dem Formular", 0) + n

    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st)
        print("ABORT:", *errs[:5], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    for k, v in rep.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
