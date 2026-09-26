#!/usr/bin/env python3
"""Export the databank in LLM-ready form (the durable artifact for later use).

citygov.db remains the source of truth. Every DERIVED judgment — Standard-
Divergenzen, rechtsmittel_status, art5_offen, the decoded DVSH block, the
Lebenslagen statistics, the naming catalogue, the German labels — is computed
once in scripts/export_json.py and READ here from data_export.json (one
computation per figure); this script never recomputes one of them differently.
It writes five stable, self-describing files an LLM agent can ingest directly:

  citygov_llm.json         — nested: service -> Formular -> Datenfeld -> legal_basis,
                             plus the Verfahren layer, the DVSH model, Lebenslagen
                             and Begriffe; meta documents every judgment key.
  citygov_datafields.jsonl — one JSON object per logical Datenfeld (flat, RAG-friendly):
                             definition, eCH/eSH mapping, legal basis, sensitivity.
  citygov_datarules.jsonl  — one object per data-governance rule: what the law says
                             about storing, processing and disclosing the data, each
                             with a PDF-verified verbatim quote.
  citygov_verzeichnis.json — the register of processing activities per Formular,
                             structured like KDSG Art. 17b Abs. 2 (the duty itself
                             binds only Polizei/StA/Justizvollzug); open contents say FEHLT.
  citygov_prefill.json     — Datenpunkt -> eCH element per Formular for once-only prefill.

RETIRED: citygov_fields.jsonl and the former «fields» key carried the 2026-06
auto-draft layer (form_field/field_mapping: 'proposed' widget->requirement
links; the placeholder-law citations it lifted from form text were removed by
scripts/migrate_2026_09_26.py). It never passed the proof gate and is superseded
by data_fields, so it is no longer exported (the live counts are written into
META.retired_layer at build time); a stale citygov_fields.jsonl is removed when found.

    python3 scripts/export_llm.py          # after scripts/export_json.py
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, connect, DB_PATH, EXPORT_PATH, _layer_skipped
import labels as L

RETIRED_FILE = "citygov_fields.jsonl"

META = {
    "about": "Kanton Schaffhausen compliance databank of the cantonal administration's "
             "Formulare. Per service: its Formulare, their curated data fields "
             "(data_fields — the proof-gated layer: every article citation exists in an "
             "ingested law text, every eCH element in the swept catalogue, every eSH code "
             "in the draft catalogue) with the legal basis, standard mapping and "
             "sensitivity of each field, the Verfahren (outcome, remedy, enclosures, "
             "channel), the DVSH model of the service, the eCH-0049 Themengruppen and the "
             "naming catalogue. Gaps are exported as gaps (null / 'offen' / FEHLT) and "
             "never filled; 'not researched' is never the same value as 'proven'.",
    "quelle": "generated from citygov.db via data_export.json (scripts/export_json.py, then "
              "scripts/export_llm.py); generated_at is data_export.json's stamp; never hand-edit.",
    "retired_layer": "The 2026-06 auto-draft layer (DB tables form_field/field_mapping/"
                     "requirement_legal_basis: {n_fm:,} 'proposed' widget->requirement links; {n_rlb:,} "
                     "requirement->article links kept for provenance — the placeholder-law citations it "
                     "lifted from form text were removed by scripts/migrate_2026_09_26.py) is NOT "
                     "exported any more — neither as a 'fields' key per Formular nor as "
                     "citygov_fields.jsonl (removed). It never passed the proof gate and is "
                     "superseded by data_fields; the tables remain in the DB for provenance only. "
                     "Never cite from it.",
    "trust_rules": {
        "labels": "Every code in this file (data_type, sensitive_category, entscheid_art, "
                  "rechtsmittel_art, rechtsmittel_status, halter, obligatorium, submission_channel, "
                  "signature_requirement, dvsh status, mode, divergence arts, check status, "
                  "jurisdiction, aspect, scope, trigger_event, disposition, min_or_max, basis_typ, "
                  "subjekt, begriff pruefart (klasse 'pruefen' is decoded through pruefart, see "
                  "trust_rules.begriffe), Handlungsbedarf categories) has its German label in "
                  "meta.labels — the same dicts (scripts/labels.py) the dashboard and the dossiers "
                  "render. A code missing there is a defect, never silently raw.",
        "legal_basis.verification": {
            "verified": "cross-checked live against Fedlex / Rechtsbuch SH — authoritative",
            "sourced_pdf": "read from the official cantonal SHR PDF (Gesetze folder); not yet live-checked",
            "cited_unverified": "a citation lifted from the form/Merkblatt, not yet resolved to a law "
                                "text; the dashboard shows it as «zitiert (unverif.)». In the curated "
                                "data_fields layer this level does not occur today (see meta.zitate).",
            "UNVERIFIED": "no source; do NOT rely on it (does not occur in the curated layer today)",
            "_hinweis": "An empty legal_basis list is not a verification level: read basis_typ.",
        },
        "basis_typ": "artikel=an article names the datum (legal_basis non-empty); aufgabe=no "
                     "explicit article, but the datum is needed to perform the statutory task "
                     "(KDSG Art. 4 Abs. 1 lit. b) — NOT over-collection; ohne=neither a norm nor the "
                     "task requires it = real over-collection ('over_collection' is true only here); "
                     "offen=assessed, undecidable from the form; null=not researched yet "
                     "('zu ermitteln'). Covered = artikel or aufgabe — except where art5_offen is true.",
        "art5_offen": "true when a besonders schützenswertes Datum (sensitive_category set) is "
                      "judged 'aufgabe' without an article. KDSG Art. 4 Abs. 1 lit. b does NOT carry "
                      "such data: Art. 5 Abs. 1 lit. a (a formal law that clearly describes the task, "
                      "«unentbehrlich») or lit. b (consent, express or unmistakably presumed from the circumstances) must be named. Rendered as open "
                      "(«aufgabennotwendig — Grundlage nach KDSG Art. 5 Abs. 1 noch nicht benannt»), "
                      "counted as OPEN in every coverage sum (verzeichnis rechtsgrundlagen.art5_offen), "
                      "never as covered; Handlungsbedarf category sensibel_art5.",
        "basis_begruendung": "the panel's one-sentence reason for basis_typ (aufgabe/ohne/offen); "
                             "null where basis_typ is artikel or not researched.",
        "subjekt": "whose datum the field is: natuerliche_person | organisation | sache | "
                   "behoerde | gemischt | null (not judged). Only natuerliche_person may be "
                   "prefilled from the Einwohnerregister — the same eCH element also carries "
                   "business and object addresses, which the register does not hold.",
        "sensitive_category": "the category of besonders schützenswerte Personendaten after KDSG "
                              "Art. 2 Abs. 1 lit. d (meta.labels.sens: gesundheit, religion_"
                              "weltanschauung, politik, ethnie_herkunft, genetik_biometrie, "
                              "strafen_verfahren, sozialhilfe) or null; 'sensitive' is the boolean "
                              "shorthand of the same fact.",
        "ech": "status: assigned = a citable XML element of the standard is fixed (dashboard "
               "«eCH-XXXX · element»); standard_only = the standard is known but no element — the "
               "dashboard says «Element offen» when the standard has an element catalogue (an "
               "element is still owed) and «nur Standard» when it has none (see standard_divergenzen."
               "fehlend art standard_ohne_elemente: a final answer); kein_standard = no eCH standard "
               "covers the datum (dashboard «kein eCH-Standard»; an eSH draft may apply); null / "
               "'offen' = not yet checked against the catalogue (Handlungsbedarf «eCH-Zuordnung "
               "offen»). standard_status = the approval status eCH publishes for the standard "
               "(Genehmigt | In Arbeit | Sistiert | Aufgehoben | Abgelöst | null = not recorded); "
               "anything but Genehmigt makes the assignment provisional (dashboard ⚠/⛔). "
               "The atomic unit is the subfield (subfields[].ech); a composite's own element never "
               "replaces its parts'.",
        "esh_entwurf": "the cantonal DRAFT standard eSH (25 entries) — applies only where ech.status "
                       "is kein_standard, status is always 'entwurf', and it is never an official "
                       "or approved standard. It shrinks as eCH assignments take fields over.",
        "empfaenger": "documented Bekanntgaben per Formular from form_disclosure: empfaenger, mode "
                      "(systematisch | auf_anfrage; meta.labels.mode), article_no and short_title of "
                      "the article that permits it. An empty list means no documented Bekanntgabe — "
                      "either none exists or it is not yet documented with an article "
                      "(Handlungsbedarf «Empfänger nicht dokumentiert»); it never means «none».",
        "aufbewahrung": "{fristen, standardregime}: fristen = the sektoral retention terms of the "
                        "retention rules in the laws this Formular's fields cite (duration_value/"
                        "unit, min_or_max, trigger_event, disposition are codes -> meta.labels."
                        "minmax/trigger/disposition; the number is gated to appear in the rule's "
                        "quote). When fristen is empty, standardregime carries the ONE default "
                        "sentence every surface uses (data_export.json texte.aufbewahrung_standard: "
                        "KDSG Art. 4, ArchivV § 5/§ 6/§ 7) with its refs [SHR, article, aspect]; "
                        "otherwise standardregime is null. A default is a regime, not a "
                        "Fristentscheid of the canton.",
        "verfahren": "per Formular, from the Verfahren layer: outcome = form_outcome (entscheid_art "
                     "-> meta.labels.outcome; rechtsmittel_art/_frist_tage/_instanz; "
                     "rechtsmittel_quelle allgemein = the VRG general rule, sektoral = a Spezialnorm, "
                     "offen = assessed and undecidable; rechtsmittel = the applied provision with its "
                     "PDF-verified quote; rechtsmittel_kandidaten = every verified remedy provision "
                     "in the laws the form cites, shown so the Spezialnormen are visible — NOT a "
                     "ranking; rechtsmittel_verdikt = the panel's reasoning where a judgment was "
                     "needed). rechtsmittel_status (meta.labels.rm_status): beurteilt_offen = "
                     "assessed and undecidable from the cited law; nicht_beurteilt = not yet looked "
                     "at; default_allgemein = the VRG fallback applied mechanically WITHOUT a "
                     "Prüfvermerk that no Fachgesetz goes first — must never be read as a confirmed "
                     "«allgemein»; entscheidart_offen = entscheid_art 'unbekannt': the outcome itself "
                     "could not be backed from the DVSH text, so the remedy question is not reached; "
                     "absent = decided (rechtsmittel present) or no appealable decision "
                     "(kein_entscheid). outcome null = no Verfahren outcome is modelled for this "
                     "Formular yet (see meta.umfang.formulare_mit_verfahren) — a gap, not «no "
                     "decision». beilagen = the judged enclosures (obligatorium -> meta.labels.oblig, "
                     "halter -> meta.labels.halter = which register already holds the document, "
                     "fetchable = document-level once-only candidate, source = where the demand is "
                     "evidenced), whereas dvsh_verfahren.unterlagen is the modeller's raw list. "
                     "submission_channel / signature_requirement -> meta.labels.chan / sig "
                     "('unbekannt' and null are not «none»). exchange_pct = share of the Formular's "
                     "atomic data points that carry a citable eCH ELEMENT (the one predicate every "
                     "surface uses for «eCH-standardisiert»). blockers = named digitalisation "
                     "blockers (handwritten signature, no online channel, non-fetchable source, eCH "
                     "coverage < 50 %). dsfa_status = the canton's DSFA decision (KDSG Art. 14b); "
                     "null = not decided — the databank never fills it.",
        "dvsh_verfahren": "the service as modelled in DVSH (the modeller is read-only and "
                          "authoritative for legal bases; status -> meta.labels.dvsh_status). "
                          "voraussetzungen / unterlagen / ablauf / recht_kantonal / recht_bund are "
                          "always lists (a double-encoded modeller cell is decoded by export_json; "
                          "what is still not a list is wrapped, so one service's ablauf may hold the "
                          "modeller's malformed text as a single string element — the honest "
                          "result, the modeller cannot be corrected from here). Every recht_bund "
                          "entry carries 'ebene': the law's level read from EVIDENCE only — the URL "
                          "host (rechtsbuch.sh.ch / admin.ch), an SHR or SR marker, a self-naming "
                          "title («Bundesgesetz …», «Kantonale …», «Interkantonale …», «Konkordat»), "
                          "a short title the databank knows, or the titled entry in the same list "
                          "that shares the abbreviation (same rule as the dashboard's jurOfRef): "
                          "cantonal | federal | interkantonal | null = «Ebene offen». The list's "
                          "name recht_bund is NOT evidence: it regularly holds cantonal law, so null "
                          "is never read as federal. Service keys in_dvsh=true with dvsh_verfahren "
                          "null mean the DVSH row is absent from the current harvest. dvsh_n (only "
                          "when present) = several DVSH rows matched this service; the exported one "
                          "is «eine von N DVSH-Modellierungen».",
        "standard_divergenzen": "per Formular (null where no data fields are modelled). angleichen "
                                "= the same eCH element is demanded differently here than on the "
                                "other Formulare; items {art, feld, teilfeld, standard, element, "
                                "hier, andere, basis, aktion}: pflicht (deviates from a clear "
                                "practice elsewhere, >= 2/3 of >= 2 other occurrences), format "
                                "(other data_type/format), codeliste (own value list where "
                                "ech_codelist defines codes), pflicht_uneinheitlich (the corpus "
                                "itself is split < 2/3 — no form is the outlier, a cantonal "
                                "decision is asked for). n_angleichen counts only what THIS form "
                                "should align (pflicht/format/codeliste); n_pflicht_ungeklaert counts "
                                "the pflicht_uneinheitlich items apart. The field's legal basis is "
                                "shown because a different basis legitimately justifies a "
                                "difference. fehlend = aggregated data points with no citable "
                                "standard — a GAP, not a divergence; items {art, sammel: true, n, "
                                "standard, status, felder (up to 14 names), aktion} with art "
                                "element_offen (standard known, element still owed), "
                                "standard_ohne_elemente (the standard has no element catalogue — a "
                                "FINAL answer, no element will ever be named), standard_entwurf "
                                "(standard not in force), kein_standard (no eCH standard; aktion "
                                "names the eSH draft where one exists), ungeprueft (not yet checked); "
                                "n_fehlend sums their n. bezeichnungen = naming items from the "
                                "Begriffe layer {feld, teilfeld, standard, element, klasse, hier, "
                                "vorschlag, pruefart, grund} — NOT counted in n_angleichen so the "
                                "divergence numbers keep their meaning; n_bezeichnungen counts them. "
                                "Arts -> meta.labels.div; thresholds live in export_json.py only.",
        "lebenslagen": "services grouped by the Themengruppen of the official eCH-0049 topic "
                       "catalogues (V4.00, approved; katalog privat = natural persons, unternehmen = "
                       "businesses) — where the person or business who needs a service would look; "
                       "many groups are life situations, some are topics, so the export calls them "
                       "Themengruppen. Assignment: panel with sceptical review, <= 3 groups per "
                       "service. Per group: services (ids), n_services, n_dienststellen, "
                       "services_modelliert (services with at least one Formular whose data fields "
                       "are modelled — every counter below covers ONLY these), services_ohne_daten "
                       "(services of the group without modelled form data — listed, never counted "
                       "as zero burden), n_formulare (modelled Formulare). Counters over the atomic "
                       "data points (subfields where they exist, else the field): n_angaben = all "
                       "points; n_pflicht = required points of fields WITHOUT subfields; "
                       "n_pflicht_teil = points of required composite fields (a part inherits its "
                       "field's Pflicht); n_vorbefuellbar = points the Einwohnerregister already "
                       "holds (person/address standards AND subjekt natuerliche_person); "
                       "n_vorbefuellbar_offen = points of person/address standards whose subjekt is "
                       "not judged or whose mapping is flagged pruefart zuordnung — could be "
                       "prefillable, not claimed; n_kein_standard / n_element_offen / n_ungeprueft "
                       "and their sum n_ohne_standard = points without a citable element, counted "
                       "apart and never matched as «the same datum»; n_zuordnung_offen = points "
                       "whose label means another datum than the mapped element (pruefart "
                       "zuordnung) — excluded from matching; n_container = points on generic "
                       "container elements (document, attachment, comment) — excluded from "
                       "matching; n_partei_offen = person/address points whose party is null or "
                       "gemischt — excluded from matching, never guessed; n_sensibel = fields with a "
                       "sensitive_category; n_beilagen / n_beilagen_beziehbar = demanded enclosures "
                       "and those a register could supply; n_online = Formulare with an online "
                       "channel; n_unterschrift = Formulare demanding a handwritten signature; "
                       "n_daten = distinct matched data (datum keys); wiederholt (top 40) and "
                       "n_wiederholt = data asked by 2+ services of the group, where «the same "
                       "datum» means same eCH element, same judged party for person/address data, "
                       "same named role. n_ueberschneidungen counts overlaps across the OFFER — the "
                       "services can be alternatives nobody uses together, so it is not the burden "
                       "of one person.",
        "begriffe": "one datum, one name: per eCH element (match by element_id — the same element "
                    "name exists in several XML contexts) the proposed term vorschlag (always one of "
                    "the labels the Formulare already use; the loader rejects invented terms), "
                    "begruendung, herkunft (eigen = the term comes from this element's own labels; "
                    "korpus = from another element's labels — never invented), vorbehalt (true = no "
                    "clean term exists anywhere in the corpus; the proposal stands with an explicit "
                    "reservation) and labels[] with klasse -> UI name (meta.labels.begriff_klasse): "
                    "vorschlag = the proposed term itself; variante = same datum, other wording -> UI "
                    "«angleichen»; rolle = the label names whose datum it is (rolle = the role) -> UI "
                    "«Rolle», fine as it is; pruefen = the label promises more/other data than the "
                    "element, split by pruefart: aufteilen = the field bundles data the standard "
                    "separates -> UI «Feld aufteilen» (fix the FORM), zuordnung = the label means "
                    "another datum -> UI «eCH-Zuordnung korrigieren» (fix the DATABANK mapping). "
                    "n / formulare / n_formulare = where the label occurs (Formular ids as in "
                    "services[].forms[].id).",
        "datenhandhabung.scope": "allgemein=applies to every personal-data field; "
                                 "besonders_schuetzenswert=additionally applies to fields with a "
                                 "sensitive category (matching sensitive_category, or all when null); "
                                 "sektoral=applies only to fields whose legal basis cites the same law "
                                 "(match on law). The addressee is part of the claim: rules from "
                                 "DSG/DSV/BGA/EMBAG bind Bundesorgane, not the canton (see each rule's "
                                 "law and quote).",
        "process_steps / findings": "legacy service-level rows of the 2026-06 era (kept as text; "
                                    "process_steps mode is a code); the Verfahren facts a reader "
                                    "should rely on are dvsh_verfahren and forms[].verfahren.",
    },
}

DVSH_KEYS = ("status", "online", "version", "kurzbeschreibung", "voraussetzungen", "unterlagen",
             "ablauf", "gebuehren", "vollzugsbehoerde", "email", "recht_kantonal", "recht_bund")
DVSH_LIST_KEYS = ("voraussetzungen", "unterlagen", "ablauf", "recht_kantonal", "recht_bund")


def verlevel(lc):
    if not lc or lc == "UNVERIFIED":
        return "UNVERIFIED"
    if lc == "verified":
        return "verified"
    if str(lc).startswith("Gesetze"):
        return "sourced_pdf"
    return "cited_unverified"


# ---- the level of a free-text DVSH legal reference (dashboard jurOfRef rule) ----
# evidence only, in order: cantonal source, federal source, a title that names
# its own level, a short title the databank already knows. Never a guess —
# «Verordnung über …» alone stays open, it exists on both levels.
_ABBR = re.compile(r"\(([^)]{2,24})\)")


def _abbrs_of(label):
    """Every candidate short title in a free-text reference: each parenthesised
    abbreviation plus the trailing token («Art. 3 GesG» -> GesG)."""
    out = _ABBR.findall(label or "")
    parts = (label or "").strip().split()
    if parts:
        out.append(parts[-1])
    return out


def _lawjur(laws):
    """short title / parenthesised abbreviation -> jurisdiction_level, from the
    laws data_export.json carries (the placeholder rows are not among them)."""
    m = {}
    for l in laws:
        def add(s):
            s = (s or "").strip()
            if 2 <= len(s) <= 24 and ";" not in s:
                m[s.lower()] = l.get("jurisdiction_level")
        add(l.get("short_title"))
        ab = _ABBR.search(l.get("title") or "")
        if ab:
            add(ab.group(1))
    return m


def _jur_of_ref(x, lawjur):
    url = x.get("url") or ""
    label = x.get("label") or x.get("titel") or ""
    if "rechtsbuch.sh.ch" in url or re.search(r"\bSHR\b", label) or re.match(r"(?i)kantonale?s?\b", label):
        return "cantonal"
    if (re.search(r"(^|\.)admin\.ch", url) or re.search(r"\bSR\s?\d", label)
            or re.match(r"(?i)(bundesgesetz|bundesverfassung|bundesbeschluss|bundesratsbeschluss)\b", label)):
        return "federal"
    if re.match(r"(?i)(interkantonale?s?|konkordat)\b", label):
        return "interkantonal"
    for a in _abbrs_of(label):
        j = lawjur.get(a.lower())
        if j:
            return j
    return None


def _with_ebene(refs, lawjur):
    """recht_bund entries + 'ebene'. A bare article reference («Art. 3 GesG»)
    inherits the level of the titled entry in the SAME list that carries the
    same abbreviation — that entry's URL is the evidence. null = «Ebene offen»."""
    refs = [x if isinstance(x, dict) else {"label": str(x)} for x in refs]
    local = {}
    for x in refs:
        j = _jur_of_ref(x, lawjur)
        if j:
            for a in _abbrs_of(x.get("label") or x.get("titel") or ""):
                local[a.lower()] = j
    out = []
    for x in refs:
        lb = x.get("label") or x.get("titel") or ""
        j = _jur_of_ref(x, lawjur) or next((local[a.lower()] for a in _abbrs_of(lb) if a.lower() in local), None)
        out.append({**x, "ebene": j})
    return out


def _load_export():
    """data_export.json is a hard dependency: every derived judgment comes from
    it. A missing or stale export must stop the run, not silently thin the files."""
    try:
        with open(EXPORT_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception as ex:
        sys.exit(f"data_export.json fehlt oder ist nicht lesbar ({ex}) — zuerst scripts/export_json.py ausführen")
    if not d.get("generated_at"):
        sys.exit("data_export.json trägt kein generated_at — zuerst scripts/export_json.py ausführen")
    return d


def main():
    X = _load_export()
    generated_at = X["generated_at"]
    x_forms = {f["id"]: f for f in X.get("forms", [])}
    x_svcs = {s["id"]: s for s in X.get("services", [])}
    # art5_offen is judged once (export_json); read it per data_field id
    art5 = {}
    for f in x_forms.values():
        for d in f.get("data_fields") or []:
            art5[d["id"]] = bool(d.get("art5_offen"))
    lawjur = _lawjur(X.get("laws", []))
    standard_ret = (X.get("texte") or {}).get("aufbewahrung_standard")
    if not standard_ret:
        sys.exit("data_export.json trägt keinen texte.aufbewahrung_standard — Export veraltet; zuerst scripts/export_json.py ausführen")

    def aufbewahrung(fristen):
        # the ONE default sentence, rendered where the surfaces used to phrase it themselves
        return {"fristen": fristen, "standardregime": None if fristen else standard_ret}

    c = connect(DB_PATH)
    # the retired layer's size is read, never typed (and the placeholder laws must be gone)
    n_fm = c.execute("SELECT count(*) FROM field_mapping WHERE match_status='proposed'").fetchone()[0]
    n_rlb = c.execute("SELECT count(*) FROM requirement_legal_basis").fetchone()[0]
    assert c.execute("SELECT count(*) FROM law WHERE last_checked LIKE 'zitiert%'").fetchone()[0] == 0, \
        "placeholder laws present — run scripts/migrate_2026_09_26.py"
    META["retired_layer"] = META["retired_layer"].format(n_fm=n_fm, n_rlb=n_rlb)
    rows = lambda q: [dict(r) for r in c.execute(q).fetchall()]
    services = rows("SELECT * FROM service")
    svc_dst = {s["id"]: s["dienststelle"] for s in services}
    forms = rows("SELECT * FROM form")
    # DB and export must describe the same Formulare, else the Verfahren layer
    # would be attached to the wrong state
    drift = {fm["id"] for fm in forms} ^ set(x_forms)
    if drift:
        sys.exit(f"{len(drift)} Formulare unterscheiden sich zwischen citygov.db und data_export.json — "
                 "Export veraltet; zuerst scripts/export_json.py ausführen")
    steps = {}
    for st in rows("SELECT * FROM process_step ORDER BY service_id, step_no"):
        steps.setdefault(st["service_id"], []).append({"step": st["step_no"], "description": st["description"], "mode": st["mode"]})
    findings = {}
    for f in rows("SELECT * FROM finding"):
        findings.setdefault(f["service_id"], []).append({"type": f["type"], "severity": f["severity"], "description": f["description"]})

    # logical Datenfeld catalogue: legal basis + eCH standard + KDSG sensitivity
    dflb = {}
    for lb in rows("SELECT dflb.data_field_id did, a.article_no, dflb.citation_detail, dflb.last_checked, "
                   "l.title, l.short_title, l.jurisdiction_level, l.sr_number, l.cantonal_ref "
                   "FROM data_field_legal_basis dflb JOIN article a ON a.id=dflb.article_id "
                   "JOIN law l ON l.id=a.law_id"):
        dflb.setdefault(lb["did"], []).append({
            "jurisdiction": lb["jurisdiction_level"], "law_title": lb["title"],
            "law_short": lb["short_title"], "sr_number": lb["sr_number"],
            "cantonal_ref": lb["cantonal_ref"], "article_no": lb["article_no"],
            "citation_detail": lb["citation_detail"], "verification": verlevel(lb["last_checked"])})
    eshk = {}
    try:
        for r in rows("SELECT code, titel FROM esh_standard"):
            eshk[r["code"]] = r["titel"]
    except Exception as _ex:
        _layer_skipped('eSH-Titel (esh_standard)', _ex)
    subs = {}
    for r in rows("SELECT sf.data_field_id d, sf.name, sf.ech_status, sf.esh_code, sf.esh_element, "
                  "e.standard estd, e.name ename, st.status sstat, "
                  "COALESCE(s1.code, s2.code) scode "
                  "FROM data_subfield sf "
                  "LEFT JOIN ech_element e ON e.id=sf.ech_element_id "
                  "LEFT JOIN ech_standard s1 ON s1.code=e.standard "
                  "LEFT JOIN ech_standard s2 ON s2.code=sf.ech_standard_code "
                  "LEFT JOIN ech_standard st ON st.code=COALESCE(e.standard, sf.ech_standard_code) "
                  "ORDER BY sf.data_field_id, sf.ord"):
        sub = {"name": r["name"],
               "ech": ({"standard": r["scode"], "element": r["ename"],
                        "standard_status": r["sstat"], "status": r["ech_status"]}
                       if r["scode"] else {"status": r["ech_status"] or "offen"})}
        if r["esh_code"]:
            sub["esh_entwurf"] = {"code": r["esh_code"], "element": r["esh_element"],
                                  "titel": eshk.get(r["esh_code"]), "status": "entwurf"}
        subs.setdefault(r["d"], []).append(sub)

    dfs_by_form = {}
    missing_a5 = 0
    for d in rows("SELECT d.*, e.standard estd, e.name ename, e.datatype edt, "
                  "COALESCE(s1.title, s2.title) etitle, COALESCE(s1.url, s2.url) eurl, "
                  "COALESCE(s1.status, s2.status) estatus "
                  "FROM data_field d "
                  "LEFT JOIN ech_element e ON e.id=d.ech_element_id "
                  "LEFT JOIN ech_standard s1 ON s1.code=e.standard "
                  "LEFT JOIN ech_standard s2 ON s2.code=d.ech_standard_code "
                  "ORDER BY d.form_id, d.ord"):
        std = d["estd"] or d["ech_standard_code"]
        if d["id"] not in art5:
            missing_a5 += 1
        dfs_by_form.setdefault(d["form_id"], []).append({
            "id": d["id"],
            "name": d["name"], "definition": d["definition"], "data_type": d["data_type"],
            "required": bool(d["required"]),
            "allowed_values": json.loads(d["allowed_values"]) if d["allowed_values"] else [],
            "sensitive": bool(d["sensitive"]), "sensitive_category": d["sensitive"],
            "ech": ({"status": d["ech_status"], "standard": std, "element": d["ename"],
                     "datatype": d["edt"], "standard_titel": d["etitle"], "url": d["eurl"],
                     "standard_status": d["estatus"]}
                    if std else {"status": d["ech_status"] or "offen"}),
            "legal_basis": dflb.get(d["id"], []),
            "over_collection": d["basis_typ"] == "ohne",
            "basis_typ": d["basis_typ"], "basis_begruendung": d["basis_begruendung"],
            "art5_offen": art5.get(d["id"], False),
            "subjekt": d["subjekt"],
            "esh_entwurf": ({"code": d["esh_code"], "element": d["esh_element"],
                             "titel": eshk.get(d["esh_code"]), "status": "entwurf"}
                            if d["esh_code"] else None),
            "subfields": subs.get(d["id"], [])})
    if missing_a5:
        sys.exit(f"{missing_a5} Datenfelder fehlen in data_export.json — Export veraltet; "
                 "zuerst scripts/export_json.py ausführen")

    # Verzeichnis layer: purpose/recipients/retention per form
    disc_by_form, ret_by_form = {}, {}
    try:
        for r in rows("SELECT fd.form_id, fd.empfaenger, fd.mode, a.article_no, l.short_title "
                      "FROM form_disclosure fd LEFT JOIN article a ON a.id=fd.article_id "
                      "LEFT JOIN law l ON l.id=a.law_id"):
            disc_by_form.setdefault(r.pop("form_id"), []).append(r)
        lt = {}
        for r in rows("SELECT a.law_id, rt.duration_value, rt.duration_unit, rt.min_or_max, "
                      "rt.trigger_event, rt.disposition, a.article_no, l.short_title, l.sr_number "
                      "FROM retention_term rt JOIN data_rule dr ON dr.id=rt.data_rule_id "
                      "JOIN article a ON a.id=dr.article_id JOIN law l ON l.id=a.law_id "
                      "WHERE dr.scope='sektoral'"):
            lt.setdefault(r.pop("law_id"), []).append(r)
        for r in rows("SELECT DISTINCT d.form_id, a.law_id FROM data_field_legal_basis lb "
                      "JOIN data_field d ON d.id=lb.data_field_id "
                      "JOIN article a ON a.id=lb.article_id"):
            for t in lt.get(r["law_id"], []):
                ret_by_form.setdefault(r["form_id"], []).append(t)
    except Exception as _ex:
        _layer_skipped('Bekanntgabe/Fristen je Formular (form_disclosure, retention_term)', _ex)

    # prefill map: every eCH-keyed ATOMIC point of every form, for once-only
    # autofill — read from the export so 'einwohnerregister' is the SAME mark the
    # dashboard shows (register standards eCH-0044/0010/0011/0007/0008 AND subjekt
    # natuerliche_person; a Betrieb's street is eCH-0010 too, but not in the
    # residents register). A composite whose parts carry their own elements is
    # not counted next to its own parts.
    prefill = {}
    n_mehrdeutig = 0
    for fid, xf in x_forms.items():
        pts = []
        # a composite parent whose Teilfelder carry their own elements gets no
        # point of its own — but build_flows.py puts the parent's OWN element into
        # the collision set next to its Teilfelder, so a leaf that shares it (the
        # applicant's «Personalien» eCH-0044·personIdentification vs. «Name /
        # Vorname der MitbewohnerInnen») is flagged. Register it as a virtual
        # partner (None marker) so the rule here is the same rule.
        virt = []
        for d in xf.get("data_fields") or []:
            sf = [s for s in (d.get("subfields") or []) if isinstance(s, dict)]
            pe = d.get("ech") or {}
            if sf and d.get("subjekt") == "natuerliche_person" and pe.get("element"):
                virt.append((pe["standard"], pe["element"]))
            for s in (sf or [None]):
                u = s if s is not None else d
                e = u.get("ech") or {}
                if not e.get("element"):
                    continue
                pts.append({"feld": d["name"] + ("›" + s["name"] if s is not None else ""),
                            "feld_parent": d["name"] if s is not None else None,
                            "standard": e["standard"], "element": e["element"],
                            "pflicht": bool(d.get("required")),
                            "subjekt": d.get("subjekt"),
                            "einwohnerregister": u.get("register") == "einwohnerregister",
                            "mehrdeutig": False})
        # same rule as build_flows.py: among a natural person's points, an element
        # that identifies MORE than one point cannot prefill any of them — the
        # profile holds one value, and writing it into both would fill a wrong
        # answer (e.g. the applicant's and a family member's Name)
        seen = {}
        for p in pts:
            if p["subjekt"] == "natuerliche_person":
                seen.setdefault((p["standard"], p["element"]), []).append(p)
        for key in virt:
            seen.setdefault(key, []).append(None)   # virtual partner, never exported
        for ps in seen.values():
            if len(ps) > 1:
                for p in ps:
                    if p is None:
                        continue
                    p["mehrdeutig"] = True
                    n_mehrdeutig += 1
        if pts:
            prefill[fid] = pts

    # data-governance rules: how the data may be stored, treated, communicated
    datarules = []
    try:
        for r in rows("SELECT dr.aspect, dr.scope, dr.sensitive_category, dr.summary, "
                      "dr.quote, dr.quote_verified, a.article_no, a.heading, "
                      "l.title law_title, l.short_title law_short, l.sr_number, "
                      "l.jurisdiction_level jurisdiction "
                      "FROM data_rule dr JOIN article a ON a.id=dr.article_id "
                      "JOIN law l ON l.id=a.law_id ORDER BY dr.scope, a.law_id, a.id"):
            r["quote_verified"] = bool(r["quote_verified"])
            datarules.append(r)
    except Exception as _ex:
        _layer_skipped('Datenhandhabung (data_rule)', _ex)

    # the Verfahren layer per form, as judged once in export_json
    def verfahren_of(fid):
        xf = x_forms[fid]
        return {"outcome": xf.get("outcome"),
                "beilagen": xf.get("beilagen") or [],
                "submission_channel": xf.get("submission_channel"),
                "signature_requirement": xf.get("signature_requirement"),
                "exchange_pct": xf.get("exchange_pct"),
                "blockers": xf.get("blockers") or [],
                "dsfa_status": xf.get("dsfa_status")}

    forms_by_service = {}
    verzeichnis = []
    n_outcomes = 0
    for fm in forms:
        dfs = dfs_by_form.get(fm["id"], [])
        xf = x_forms[fm["id"]]
        verf = verfahren_of(fm["id"])
        n_outcomes += bool(verf["outcome"])
        forms_by_service.setdefault(fm["service_id"], []).append({
            "id": fm["id"],
            "title": fm["title"], "source_file": fm["source_file"], "file_type": fm["file_type"],
            "title_content_mismatch": bool(fm["title_content_mismatch"]),
            "zweck": fm.get("purpose"),
            "empfaenger": disc_by_form.get(fm["id"], []),
            "aufbewahrung": aufbewahrung(ret_by_form.get(fm["id"], [])),
            "verfahren": verf,
            "standard_divergenzen": xf.get("standard_divergenzen"),
            "data_fields": dfs})
        # one register-extract row per form (KDSG Art. 17b structure, gaps explicit)
        if dfs:
            # coverage by basis_typ, the dashboard's rule: artikel and aufgabe cover;
            # art5_offen is OPEN although basis_typ says aufgabe; null = zu ermitteln
            tally = {"artikel": 0, "aufgabe": 0, "art5_offen": 0, "ohne": 0, "offen": 0, "zu_ermitteln": 0}
            for d in dfs:
                if d["art5_offen"]:
                    tally["art5_offen"] += 1
                elif d["legal_basis"] or d["basis_typ"] == "artikel":
                    tally["artikel"] += 1
                elif d["basis_typ"] in ("aufgabe", "ohne", "offen"):
                    tally[d["basis_typ"]] += 1
                else:
                    tally["zu_ermitteln"] += 1
            tally["n_gedeckt"] = tally["artikel"] + tally["aufgabe"]
            tally["n_offen"] = tally["art5_offen"] + tally["offen"] + tally["zu_ermitteln"]
            sens = sorted({d["sensitive_category"] for d in dfs if d.get("sensitive_category")})
            verzeichnis.append({
                "form_id": fm["id"], "formular": fm["title"],
                "verantwortliche_stelle": svc_dst.get(fm["service_id"]) or fm["publisher_dienststelle"] or "FEHLT",
                "zweck": fm.get("purpose") or "FEHLT",
                "datenkategorien": {"felder": len(dfs),
                                    "besonders_schuetzenswert": sens,
                                    "n_besonders_schuetzenswert": sum(1 for d in dfs if d.get("sensitive_category"))},
                "rechtsgrundlagen": tally,
                "empfaenger": [e["empfaenger"] for e in disc_by_form.get(fm["id"], [])] or "FEHLT",
                "aufbewahrung": aufbewahrung(ret_by_form.get(fm["id"], [])),
                "dsfa_status": fm.get("dsfa_status") or "FEHLT"})

    # service-level Verfahren facts: the DVSH block as export_json decoded it
    # (no second read of the modeller table — one decode, one truth) + SHEP state
    dvsh_svc = {}
    for sid, xs in x_svcs.items():
        dv = xs.get("dvsh")
        if not dv:
            continue
        r = {k: dv.get(k) for k in DVSH_KEYS}
        for k in DVSH_LIST_KEYS:
            if r[k] is None:
                r[k] = []
            assert isinstance(r[k], list), \
                f"service {sid}: dvsh.{k} ist {type(r[k]).__name__}, nicht list — export_json dekodiert nicht mehr?"
        r["recht_bund"] = _with_ebene(r["recht_bund"], lawjur)
        dvsh_svc[sid] = r
    shep_svc = {}
    try:
        for r in rows("SELECT service_id, slug, updated FROM shep_service WHERE service_id IS NOT NULL"):
            shep_svc[r["service_id"]] = {"portal_url": "https://shep.meetfrida.agency/de/services/" + r["slug"],
                                         "stand": r["updated"]}
    except Exception as _ex:
        _layer_skipped('sh.ch-Portal (shep_service)', _ex)
    c.close()

    out_services = []
    dfl = []
    for s in services:
        xs = x_svcs.get(s["id"]) or {}
        svc = {"id": s["id"], "slug": s["slug"], "name": s["name"],
               "department": s["department"], "dienststelle": s["dienststelle"],
               "description": s["description"],
               "in_dvsh": bool(s.get("in_dvsh")),
               "lebenslagen_ech0049": [{"id": t.get("id"), "katalog": t["katalog"], "bereich": t["bereich"], "gruppe": t["gruppe"]}
                                       for t in (xs.get("themen") or [])],
               "dvsh_verfahren": dvsh_svc.get(s["id"]),
               "shep_publikation": shep_svc.get(s["id"]),
               "forms": forms_by_service.get(s["id"], []),
               "process_steps": steps.get(s["id"], []), "findings": findings.get(s["id"], [])}
        if xs.get("dvsh_n"):
            svc["dvsh_n"] = xs["dvsh_n"]
            svc["dvsh_hinweis"] = f"eine von {xs['dvsh_n']} DVSH-Modellierungen dieses Services"
        out_services.append(svc)
        for fm in svc["forms"]:
            for d in fm["data_fields"]:
                dfl.append({"service": s["name"], "department": s["department"],
                            "dienststelle": s["dienststelle"], "form": fm["title"],
                            "form_id": fm["id"], "source_file": fm["source_file"], **d})

    n_a5 = sum(1 for r in dfl if r["art5_offen"])
    umfang = {"services": len(out_services), "formulare": len(forms),
              "formulare_mit_datenfeldern": len(verzeichnis),
              "formulare_mit_verfahren": n_outcomes,
              "datenfelder": len(dfl), "datenfelder_art5_offen": n_a5,
              "services_mit_dvsh": len(dvsh_svc)}
    LEBENSLAGEN_KEYS = ("id", "katalog", "bereich", "gruppe", "n_services", "n_dienststellen", "n_formulare",
                        "services", "services_modelliert", "services_ohne_daten",
                        "n_angaben", "n_pflicht", "n_pflicht_teil", "n_vorbefuellbar", "n_vorbefuellbar_offen",
                        "n_kein_standard", "n_element_offen", "n_ungeprueft", "n_ohne_standard",
                        "n_zuordnung_offen", "n_container", "n_partei_offen", "n_sensibel",
                        "n_beilagen", "n_beilagen_beziehbar", "n_online", "n_unterschrift",
                        "n_daten", "wiederholt", "n_wiederholt", "n_ueberschneidungen")
    doc = {"meta": {**META, "generated_at": generated_at,
                    "datenstand": X.get("datenstand"), "zitate": X.get("zitate"),
                    "umfang": umfang, "labels": L.as_export()},
           "datenhandhabung": datarules,
           "lebenslagen": [{k: t.get(k) for k in LEBENSLAGEN_KEYS}
                           for t in (X.get("themenkatalog") or []) if t.get("n_services")],
           "begriffe": X.get("begriffe") or [],
           "services": out_services}
    json.dump(doc, open(os.path.join(ROOT, "citygov_llm.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "citygov_datafields.jsonl"), "w", encoding="utf-8") as fh:
        for r in dfl:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(ROOT, "citygov_datarules.jsonl"), "w", encoding="utf-8") as fh:
        for r in datarules:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    BT = L.BASIS_TYP
    json.dump({"meta": {"generated_at": generated_at,
                        "hinweis": "Verzeichnis der Bearbeitungstätigkeiten je Formular, Struktur "
                        "nach KDSG Art. 17b Abs. 2 (die Führungspflicht nach Art. 17b trifft nur "
                        "Polizei, Staatsanwaltschaft und Justizvollzug; für alle anderen Stellen "
                        "ist dies ein Steuerungsinstrument); «FEHLT» markiert offene Inhalte ehrlich. "
                        f"Erfasst sind die {len(verzeichnis)} von {len(forms)} Formularen mit "
                        "modellierter Datenfeld-Schicht.",
                        "felder": {
                            "verantwortliche_stelle": "Dienststelle des Services; sonst die publizierende "
                                                      "Dienststelle des Formulars; sonst FEHLT.",
                            "datenkategorien.besonders_schuetzenswert":
                                "Kategorien besonders schützenswerter Personendaten nach KDSG Art. 2 Abs. 1 lit. d, "
                                "die das Formular erhebt (Codes: " + ", ".join(f"{k} = {v}" for k, v in L.SENS.items()) + ").",
                            "rechtsgrundlagen":
                                "Zählung der Datenfelder nach Grundlage: "
                                f"artikel = {BT['artikel']} (Artikel zitiert und gegen den Gesetzestext geprüft) · "
                                f"aufgabe = {BT['aufgabe']} (keine Norm nennt das Feld, die gesetzliche Aufgabe "
                                "braucht es — KDSG Art. 4 Abs. 1 lit. b; keine Over-collection) · "
                                "art5_offen = besonders schützenswertes Datum, nur als aufgabennotwendig beurteilt — "
                                "Grundlage nach KDSG Art. 5 Abs. 1 lit. a oder b noch nicht benannt; OFFEN, nie gedeckt · "
                                f"ohne = {BT['ohne']} (weder Norm noch Aufgabe verlangen das Feld) · "
                                f"offen = {BT['offen']} (beurteilt, aus dem Formular nicht entscheidbar) · "
                                "zu_ermitteln = noch nicht recherchiert (Wissenslücke der Databank, kein Befund). "
                                "n_gedeckt = artikel + aufgabe; n_offen = art5_offen + offen + zu_ermitteln.",
                            "aufbewahrung": "fristen = sektorale Fristen aus den Aufbewahrungsregeln der zitierten "
                                            "Gesetze (Codes trigger_event/disposition/min_or_max wie in citygov_llm.json "
                                            "meta.labels); ohne Frist gilt standardregime — der eine Standardsatz "
                                            "(KDSG Art. 4, ArchivV § 5/§ 6/§ 7) mit refs [SHR, Artikel, Aspekt]. "
                                            "Ein Standardregime ist kein Fristentscheid des Kantons.",
                            "dsfa_status": "Entscheid des Kantons zur Datenschutz-Folgenabschätzung (KDSG Art. 14b); "
                                           "FEHLT = noch nicht entschieden, die Databank setzt keinen.",
                        }},
               "verzeichnis": verzeichnis},
              open(os.path.join(ROOT, "citygov_verzeichnis.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    n_pts = sum(len(v) for v in prefill.values())
    n_reg = sum(1 for v in prefill.values() for p in v if p["einwohnerregister"])
    json.dump({"meta": {"generated_at": generated_at,
                        "hinweis": "Datenpunkt→eCH-Element-Map je Formular (Schlüssel = Formular-id) für "
                                   "Once-Only-Prefill: ein nach eCH-Element gekeytes Profil einer natürlichen "
                                   "Person füllt damit die Punkte vor, die einwohnerregister = true und "
                                   "mehrdeutig = false tragen — nur diese, nie alle Punkte.",
                        "felder": {
                            "feld": "Pfad «Feld›Teilfeld» (ein Teilfeld ist die atomare Einheit; feld_parent = das "
                                    "Feld, sonst null). Ein zusammengesetztes Feld, dessen Teile eigene Elemente "
                                    "tragen, erscheint nicht neben seinen Teilen.",
                            "pflicht": "Pflichtangabe des Felds (ein Teilfeld erbt die Pflicht seines Felds).",
                            "subjekt": "wessen Datum: " + ", ".join(f"{k} = {v}" for k, v in L.SUBJEKT.items())
                                       + "; null = noch nicht beurteilt (dann nie vorbefüllen).",
                            "einwohnerregister": "true nur, wenn das Einwohnerregister das Datum tatsächlich führt: "
                                                 "Personen-/Adressstandard (eCH-0044, eCH-0010, eCH-0011, eCH-0007, "
                                                 "eCH-0008) UND subjekt natürliche Person — dieselbe Marke ↺ wie im "
                                                 "Dashboard. Eine Betriebs- oder Behördenadresse ist eCH-0010, aber "
                                                 "nicht im Register.",
                            "mehrdeutig": "true, wenn dasselbe eCH-Element auf diesem Formular mehr als einen Punkt "
                                          "einer natürlichen Person bezeichnet (z. B. Name der gesuchstellenden Person "
                                          "und Name eines Familienmitglieds): das Profil hält einen Wert, keiner "
                                          "dieser Punkte darf damit befüllt werden. Zählt mit: das eigene Element eines "
                                          "zusammengesetzten Felds derselben Person, dessen Teilfelder hier als Punkte "
                                          "erscheinen (das Feld selbst ist kein Punkt) — ein so markierter Punkt kann "
                                          "darum ohne sichtbaren Zwilling stehen. Dieselbe Regel wie in flows.html.",
                        },
                        "zaehlung": {
                            "n_formulare": len(prefill), "n_formulare_gesamt": len(x_forms),
                            "formulare_ohne_ech_punkt": sorted(int(fid) for fid in x_forms if fid not in prefill),
                            "n_punkte": n_pts, "n_einwohnerregister": n_reg,
                            "n_mehrdeutig": n_mehrdeutig,
                            "hinweis": "n_punkte zählt alle eCH-Punkte (Pflicht und optional, alle Subjekte); die "
                                       "Kennzahl «vorbefüllbar» des Dashboards (burden.prefillable) zählt nur "
                                       "PFLICHT-Punkte mit einwohnerregister = true — beide Zahlen sind aus pflicht "
                                       "und einwohnerregister ableitbar.",
                        }},
               "formulare": prefill},
              open(os.path.join(ROOT, "citygov_prefill.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # the retired auto-draft export must not linger next to the curated files
    retired = os.path.join(ROOT, RETIRED_FILE)
    removed = False
    if os.path.exists(retired):
        os.remove(retired)
        removed = True
    nech = sum(1 for r in dfl if r["ech"].get("standard"))
    print(f"wrote citygov_llm.json ({len(out_services)} services, {n_outcomes}/{len(forms)} Formulare mit Verfahren, "
          f"{len(dvsh_svc)} mit DVSH-Block, generated_at {generated_at}) + "
          f"citygov_datafields.jsonl ({len(dfl)} Datenfelder, {nech} mit eCH-Standard, {n_a5} art5_offen) + "
          f"citygov_datarules.jsonl ({len(datarules)} Regeln) + "
          f"citygov_verzeichnis.json ({len(verzeichnis)} Formulare) + "
          f"citygov_prefill.json ({n_pts} Prefill-Punkte, {n_reg} Einwohnerregister, {n_mehrdeutig} mehrdeutig)")
    print(f"{RETIRED_FILE}: " + ("entfernt — " if removed else "wird nicht mehr geschrieben — ")
          + "die Auto-Entwurf-Schicht (form_field/field_mapping) wird nicht mehr exportiert; massgeblich ist data_fields")


if __name__ == "__main__":
    main()
