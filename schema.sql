-- citygov databank — schema (reference DDL)
-- Source of truth = citygov.db. This file documents its structure.
-- Apply with scripts/init_db.py. Never hand-edit the DB; regenerate. The working rules
-- («conventions») the loaders enforce are listed in scripts/README.md → Conventions.
--
-- Design notes for the legacy 2026-06 auto-draft layer (numbering of that era; the
-- current rules are in scripts/README.md → Conventions):
--  * conv 3: form_field has NO foreign key to requirement. The reconciliation
--    lives only in field_mapping. Over-collection is therefore structurally
--    possible (a form_field with a field_mapping whose requirement_id IS NULL).
--  * conv 4: field_mapping.classification is one of five fixed values.
--  * conv 5: field_mapping.match_status separates proposed from confirmed.
--  * conv 6: law.last_checked / article.last_checked / legal_basis.last_checked
--    default to 'UNVERIFIED'; article.article_no defaults to 'UNKNOWN'.
--  * conv 8: requirement.data_point_key is UNIQUE — requirements are deduped by
--    data point and linked to many articles via requirement_legal_basis (M2M).
--  * conv 10: join tables carry uniqueness constraints so duplicate rows cannot
--    silently inflate compliance scores.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- meta
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ---------------------------------------------------------------------------
-- service — one row per DVSH service (the catalogue unit); same-file bundles stay one
--           row named from DVSH wording; services DVSH has not modelled have in_dvsh=0.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS service (
    id           INTEGER PRIMARY KEY,
    slug         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    dienststelle TEXT,                 -- responsible office
    department   TEXT,
    description  TEXT,
    notes        TEXT
, in_dvsh INTEGER DEFAULT 0, name_alt TEXT);

-- ---------------------------------------------------------------------------
-- law / article — legal acts and their articles.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS law (
    id                 INTEGER PRIMARY KEY,
    slug               TEXT NOT NULL UNIQUE,
    title              TEXT NOT NULL,
    short_title        TEXT,
    jurisdiction_level TEXT NOT NULL
        CHECK (jurisdiction_level IN ('federal','cantonal','communal')),
    sr_number          TEXT,           -- SR number (federal); some cantonal rows also carry their
                                       -- SHR number here — the level is jurisdiction_level
    cantonal_ref       TEXT,           -- cantonal systematic ref; NULL if n/a
    source_note        TEXT,
    last_checked       TEXT NOT NULL DEFAULT 'UNVERIFIED'   -- conv 6
, governance INTEGER DEFAULT 0);

CREATE TABLE IF NOT EXISTS article (
    id           INTEGER PRIMARY KEY,
    law_id       INTEGER NOT NULL REFERENCES law(id),
    article_no   TEXT NOT NULL DEFAULT 'UNKNOWN',           -- conv 6
    heading      TEXT,
    text_excerpt TEXT,
    last_checked TEXT NOT NULL DEFAULT 'UNVERIFIED',         -- conv 6
    UNIQUE (law_id, article_no, heading)
);

-- ---------------------------------------------------------------------------
-- requirement — a discrete legal demand tied to a concrete data point.
--   Deduped by data_point_key (conv 8 of the 2026-06 layer). Linked to article(s) via the
--   requirement_legal_basis M2M, so a shared requirement (e.g. Personalien)
--   can carry several legal bases without being duplicated.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS requirement (
    id             INTEGER PRIMARY KEY,
    data_point_key TEXT NOT NULL UNIQUE,   -- canonical key for dedupe (conv 8)
    data_point     TEXT NOT NULL,          -- human label of the datum demanded
    label          TEXT,                   -- description of the demand
    data_type      TEXT,                   -- string|date|number|boolean|enum|document|composite
    condition      TEXT,                   -- constraint that must hold (NULL = mere presence)
    is_composite   INTEGER NOT NULL DEFAULT 0,  -- 1 = has identity_part sub-fields
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS requirement_legal_basis (
    id              INTEGER PRIMARY KEY,
    requirement_id  INTEGER NOT NULL REFERENCES requirement(id),
    article_id      INTEGER NOT NULL REFERENCES article(id),
    citation_detail TEXT,                  -- e.g. 'Abs. 2 lit. a Ziff. 1'
    last_checked    TEXT NOT NULL DEFAULT 'UNVERIFIED',     -- conv 6
    UNIQUE (requirement_id, article_id)    -- conv 10: no duplicate join rows
);

-- service ↔ requirement (M2M). Which services a requirement applies to.
CREATE TABLE IF NOT EXISTS service_requirement (
    service_id             INTEGER NOT NULL REFERENCES service(id),
    requirement_id         INTEGER NOT NULL REFERENCES requirement(id),
    applicability_condition TEXT,          -- requirement may apply only conditionally
    PRIMARY KEY (service_id, requirement_id)   -- conv 10: no duplicate join rows
);

-- ---------------------------------------------------------------------------
-- form — a Formular that actually serves a service (decided by CONTENT, not title).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS form (
    id                     INTEGER PRIMARY KEY,
    slug                   TEXT NOT NULL UNIQUE,
    service_id             INTEGER NOT NULL REFERENCES service(id),
    title                  TEXT NOT NULL,   -- title as published
    actual_purpose         TEXT,            -- what the content shows it really serves
    title_content_mismatch INTEGER NOT NULL DEFAULT 0,  -- 1 = the content serves something else than the title says
    mismatch_note          TEXT,
    source_file            TEXT,            -- path under formulare/ (NFC; NULL for eFormulare)
    file_type              TEXT,            -- pdf|word|excel|eformular (agrees with the extension; gated)
    publisher_dienststelle TEXT,
    last_extracted         TEXT
, purpose TEXT, dsfa_status TEXT, dsfa_note TEXT, file_hash TEXT, acroform INTEGER, signature_requirement TEXT, signature_evidence TEXT, parse_error TEXT, submission_channel TEXT, dvsh_match TEXT);

-- LEGACY auto-draft layer (2026-06, retired): requirement / form_field /
--   field_mapping / requirement_legal_basis were written by scripts/auto_draft.py
--   (retired; kept in scripts/ because ingest_new.py imports it). Superseded by
--   data_field + data_field_legal_basis, the proof-gated layer every surface
--   reads. Kept in the DB for the record only (no surface reads it;
--   citygov_llm.json keeps the 388 per-service notes as legacy findings); its
--   'proposed' mappings are never exported,
--   and the 240 placeholder law rows it created (last_checked 'zitiert
--   (unverifiziert)') were removed by scripts/migrate_2026_09_26.py.
-- form_field — the field as it actually appears on the form. Independent of
--   the law (conv 3 of the 2026-06 layer): no requirement FK here.
CREATE TABLE IF NOT EXISTS form_field (
    id         INTEGER PRIMARY KEY,
    form_id    INTEGER NOT NULL REFERENCES form(id),
    field_key  TEXT NOT NULL,               -- stable key within the form
    label      TEXT NOT NULL,               -- label as printed on the form
    section    TEXT,                        -- section/group on the form
    field_type TEXT,                        -- text|date|number|checkbox|select|attachment|signature
    options    TEXT,                        -- JSON array for checkbox/select
    required   INTEGER NOT NULL DEFAULT 0,
    raw_order  INTEGER,
    notes      TEXT,
    UNIQUE (form_id, field_key)
);

-- field_mapping — the legacy reconciliation layer (conv 3,4,5). One row per form_field.
--   classification ∈ the five fixed buckets (conv 4).
--   requirement_id NULL is valid and meaningful (form_mechanic / overcollection).
CREATE TABLE IF NOT EXISTS field_mapping (
    id             INTEGER PRIMARY KEY,
    form_field_id  INTEGER NOT NULL UNIQUE REFERENCES form_field(id),  -- conv 10
    requirement_id INTEGER REFERENCES requirement(id),                 -- NULL allowed
    classification TEXT NOT NULL
        CHECK (classification IN
            ('mapped','identity_part','reason_facet','form_mechanic','overcollection')),
    match_status   TEXT NOT NULL DEFAULT 'proposed'
        CHECK (match_status IN ('proposed','confirmed','rejected')),   -- conv 5
    mapped_by      TEXT NOT NULL DEFAULT 'auto'
        CHECK (mapped_by IN ('auto','human')),
    confidence     REAL,
    notes          TEXT,
    -- a mapping that points at a requirement must be one of the three positive
    -- classes; form_mechanic / overcollection must NOT point at a requirement.
    CHECK (
        (requirement_id IS NOT NULL AND classification IN ('mapped','identity_part','reason_facet'))
        OR
        (requirement_id IS NULL AND classification IN ('form_mechanic','overcollection'))
    )
);

-- ---------------------------------------------------------------------------
-- process_step — ordered steps of delivering the service, tagged automatable.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS process_step (
    id          INTEGER PRIMARY KEY,
    service_id  INTEGER NOT NULL REFERENCES service(id),
    step_no     INTEGER NOT NULL,
    description TEXT NOT NULL,
    mode        TEXT NOT NULL DEFAULT 'manual'
        CHECK (mode IN ('automatable','manual')),
    notes       TEXT,
    UNIQUE (service_id, step_no)
);

-- ---------------------------------------------------------------------------
-- document — ingest-time inventory of the canton's source files with their
--   classification (decided before modelling). Only doc_type='formular' becomes
--   a form (form_id set after extraction). source_file is the path relative to
--   the repository root AT INGEST TIME (../Verwaltung/…, or the untracked forms/
--   mirror for the two oldest rows): provenance, NOT the tracked copy in
--   formulare/ (that is form.source_file). Not exported.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document (
    id                  INTEGER PRIMARY KEY,
    source_file         TEXT NOT NULL UNIQUE,
    file_name           TEXT,
    department          TEXT,
    dienststelle        TEXT,
    doc_type            TEXT NOT NULL
        CHECK (doc_type IN ('formular','calculation_tool','helper')),
    formula_note        TEXT,            -- for calculation_tool: which formula it implements
    classification_note TEXT,
    form_id             INTEGER REFERENCES form(id)   -- set only when doc_type='formular'
);

-- ---------------------------------------------------------------------------
-- finding — recorded flags: title/content mismatch, legal gaps, over-collection,
--   citation TODOs, validation issues (title vs content, never a citation from
--   memory, no duplicate rows). Legacy: today only the 2026-06 auto-draft notes.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finding (
    id          INTEGER PRIMARY KEY,
    type        TEXT NOT NULL
        CHECK (type IN ('title_mismatch','legal_gap','overcollection','citation_todo','validation','note')),
    severity    TEXT NOT NULL DEFAULT 'info'
        CHECK (severity IN ('info','warning','critical')),
    service_id  INTEGER REFERENCES service(id),
    form_id     INTEGER REFERENCES form(id),
    law_id      INTEGER REFERENCES law(id),
    fingerprint TEXT NOT NULL UNIQUE,      -- idempotency: dedupe identical findings
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','ack','resolved')),
    created_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_article_law            ON article(law_id);
CREATE INDEX IF NOT EXISTS idx_rlb_requirement        ON requirement_legal_basis(requirement_id);
CREATE INDEX IF NOT EXISTS idx_rlb_article            ON requirement_legal_basis(article_id);
CREATE INDEX IF NOT EXISTS idx_sr_requirement         ON service_requirement(requirement_id);
CREATE INDEX IF NOT EXISTS idx_form_service           ON form(service_id);
CREATE INDEX IF NOT EXISTS idx_field_form             ON form_field(form_id);
CREATE INDEX IF NOT EXISTS idx_mapping_requirement    ON field_mapping(requirement_id);

CREATE TABLE IF NOT EXISTS data_field (
  id INTEGER PRIMARY KEY,
  form_id INTEGER NOT NULL REFERENCES form(id),
  ord INTEGER,
  name TEXT NOT NULL,
  definition TEXT,
  data_type TEXT,          -- text|date|number|money|boolean|enum|multiselect|composite|attachment|signature
  required INTEGER DEFAULT 1,
  allowed_values TEXT,     -- JSON array (enum/multiselect)
  subfields TEXT,          -- JSON array (composite)
  format TEXT,             -- unit/format hint
  source_widgets TEXT,     -- JSON array of widget labels (provenance)
  derived_by TEXT DEFAULT 'agent'
, no_basis INTEGER DEFAULT 0, sensitive TEXT, ech_element_id INTEGER REFERENCES ech_element(id), ech_status TEXT, ech_standard_code TEXT REFERENCES ech_standard(code), esh_code TEXT REFERENCES esh_standard(code), esh_element TEXT, schutzstufe TEXT, format_code TEXT, basis_typ TEXT, basis_begruendung TEXT, subjekt TEXT, ech_herkunft TEXT);
CREATE INDEX IF NOT EXISTS ix_data_field_form ON data_field(form_id);

-- besonders schützenswerte Personendaten: für die kantonalen Organe gilt KDSG
-- Art. 2 Abs. 1 lit. d (Religion/Weltanschauung/Politik/Gewerkschaft, Gesundheit/
-- Intimsphäre/ethnische Herkunft, soziale Hilfe, Verfolgungen und Sanktionen,
-- genetische und biometrische Daten); DSG Art. 5 lit. c gilt für Bundesorgane.
-- NULL = nicht besonders schützenswert
-- Werte: gesundheit | religion_weltanschauung | politik | ethnie_herkunft | genetik_biometrie | strafen_verfahren | sozialhilfe
-- ALTER TABLE data_field ADD COLUMN sensitive TEXT;

-- eCH e-government data standards (public, from ech.ch XSDs) and the mapping of
-- each data field to its official standardised element.
CREATE TABLE IF NOT EXISTS ech_standard (
  code    TEXT PRIMARY KEY,     -- 'eCH-0044'
  title   TEXT,
  url     TEXT,
  n_elements INTEGER DEFAULT 0
, status TEXT, reifegrad TEXT, fachgruppe TEXT, xsd_version TEXT, xsd_file TEXT, xsd_swept_at TEXT);
CREATE TABLE IF NOT EXISTS ech_element (
    id INTEGER PRIMARY KEY, standard TEXT NOT NULL REFERENCES ech_standard(code),
    name TEXT NOT NULL, datatype TEXT, context TEXT, UNIQUE(standard, name, context));
CREATE INDEX IF NOT EXISTS ix_ech_el_std ON ech_element(standard);
CREATE INDEX IF NOT EXISTS ix_ech_el_name ON ech_element(name);
-- data_field.ech_element_id -> ech_element(id); data_field.ech_status: assigned | standard_only |
--   kein_standard (see the data_field column notes below)

-- ---------------------------------------------------------------------------
-- Data-management layer (2026-09): register of processing activities,
-- executable retention, canonical attributes, format patterns, Dienststellen.
-- Created/seeded by scripts/init_register.py; curated content is loaded
-- through the proof gates of scripts/load_register.py.
-- New columns on existing tables:
--   form.purpose        (Zweck der Bearbeitung, curated, proof-gated)
--   form.dsfa_status / form.dsfa_note   (DSFA decision, human-set)
--   data_field.schutzstufe              (ISV classification, human-set; empty = gap)
--   data_field.format_code -> format_pattern(code)
--   data_field.basis_typ                (artikel | aufgabe | ohne | offen | NULL: what the
--                                        "no explicit norm" case really is - 'aufgabe' =
--                                        needed for the task, KDSG Art. 4 Abs. 1 lit. b;
--                                        'ohne' = true over-collection; panel verdict, gated
--                                        by scripts/load_basis_typ.py) + basis_begruendung
--   data_field.subjekt                  (natuerliche_person | organisation | sache |
--                                        behoerde | gemischt | NULL: whose datum the field
--                                        is; the once-only mark, the prefill map and the
--                                        Datentresor ledger apply only to natural persons;
--                                        scripts/load_subjekt.py)

CREATE TABLE IF NOT EXISTS format_pattern (        -- canonical Swiss input patterns
    code TEXT PRIMARY KEY, regex TEXT NOT NULL, beispiel TEXT NOT NULL, beschreibung TEXT);

CREATE TABLE IF NOT EXISTS canonical_attribute (
    id             INTEGER PRIMARY KEY,
    ech_element_id INTEGER UNIQUE REFERENCES ech_element(id),
    esh_key        TEXT UNIQUE,
    label          TEXT NOT NULL,
    datatype       TEXT,
    sensitive_categories TEXT,
    register_source TEXT,
    n_instances    INTEGER NOT NULL,
    n_forms        INTEGER NOT NULL
, n_register INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS dienststelle (          -- the ISV 'Inhaber der Datensammlung' entity
    name TEXT PRIMARY KEY, department TEXT, dateninhaber TEXT, kontakt TEXT);

CREATE TABLE IF NOT EXISTS form_disclosure (       -- who receives this form's data, article-backed
    id INTEGER PRIMARY KEY,
    form_id INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    empfaenger TEXT NOT NULL,
    mode TEXT CHECK(mode IN ('systematisch','auf_anfrage')),
    article_id INTEGER REFERENCES article(id),
    last_checked TEXT,
    UNIQUE(form_id, empfaenger));

CREATE TABLE IF NOT EXISTS retention_term (        -- machine-readable Frist per retention rule
    id INTEGER PRIMARY KEY,
    data_rule_id INTEGER NOT NULL UNIQUE REFERENCES data_rule(id) ON DELETE CASCADE,
    duration_value INTEGER,                        -- NULL = the rule states no number
    duration_unit TEXT CHECK(duration_unit IN ('jahre','monate')),
    min_or_max TEXT CHECK(min_or_max IN ('min','max','exakt')),
    trigger_event TEXT,                            -- what starts the clock (snake_case)
    disposition TEXT CHECK(disposition IN ('vernichten','anonymisieren',
        'anbieten_staatsarchiv','loeschen_vermerken')),
    last_checked TEXT);

CREATE TABLE IF NOT EXISTS retention_decision (    -- cantonal Fristentscheid, never a law
    id INTEGER PRIMARY KEY,
    form_id INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    duration_value INTEGER, duration_unit TEXT, trigger_event TEXT, disposition TEXT,
    decided_by TEXT, decided_at TEXT, basis TEXT, note TEXT);

-- ---------------------------------------------------------------------------
-- Verfahren & lifecycle layer (2026-09): what surrounds a Formular.
-- Mechanical seeds: scripts/scan_documents.py (PDF facts), init_verfahren.py
-- (DDL, channel harvest, review dates, contacts), build_similarity.py.
-- Curated content through the gates of scripts/load_verfahren.py.
-- New columns on form: submission_channel, signature_requirement/evidence,
-- acroform, parse_error, file_hash; on form_check: next_check_due.

CREATE TABLE IF NOT EXISTS beilage (               -- one demanded document per row
    id INTEGER PRIMARY KEY,
    form_id INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    data_field_id INTEGER REFERENCES data_field(id),
    bezeichnung TEXT NOT NULL,
    obligatorium TEXT CHECK(obligatorium IN ('zwingend','bedingt','fakultativ','unbekannt')),
    bedingung TEXT,
    halter TEXT CHECK(halter IN ('privat','einwohnerregister','handelsregister',
        'betreibungsregister','strafregister','steuerverwaltung','grundbuch',
        'kanton_andere','bund','unbekannt')),
    fetchable INTEGER NOT NULL DEFAULT 0,          -- canton could fetch it itself (Once-Only)
    source TEXT NOT NULL CHECK(source IN ('formular','dvsh','beide')),
    last_checked TEXT,
    UNIQUE(form_id, bezeichnung));

CREATE TABLE IF NOT EXISTS form_outcome (
    form_id            INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,
    entscheid_art      TEXT CHECK(entscheid_art IN ('bewilligung','verfuegung','bestaetigung',
                          'registereintrag','auszahlung','kein_entscheid','unbekannt')),
    ergebnis_dokument  TEXT,
    rechtsmittel_art   TEXT,
    rechtsmittel_frist_tage INTEGER,
    rechtsmittel_instanz TEXT,
    article_id         INTEGER REFERENCES article(id),
    last_checked       TEXT
, rechtsmittel_regel_id INTEGER REFERENCES rechtsmittel_regel(id), rechtsmittel_quelle TEXT);

CREATE TABLE IF NOT EXISTS form_similarity (       -- Duplikat-Radar, verdict curated
    form_a INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    form_b INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    jaccard_names REAL NOT NULL, jaccard_ech REAL,
    verdict TEXT CHECK(verdict IN ('duplicate_ingest','merge_candidate','template_family','ok')),
    note TEXT,
    PRIMARY KEY(form_a, form_b));

-- ---------------------------------------------------------------------------
-- Columns added to existing tables since a layer's first DDL are part of the
-- CREATE TABLE bodies above (taken from the live database, so init_db.py yields
-- a database every loader can fill); this list says which loader fills them
-- and what the values mean. validate_db.py fails when the live columns and
-- this file disagree.
-- ---------------------------------------------------------------------------
--   law.governance                      1 = one of the 8 data-governance laws (KDSG, KDSV, ISV,
--                                        ArchivV, DSG, DSV, BGA, EMBAG) whose rules the Leitfaden
--                                        and the Datenhandhabung tab group as «allgemein»
--   service.in_dvsh                     1 = the service is modelled in DVSH (load_dvsh_harvest.py); 7 such
--                                        rows have no dvsh_service row in the current harvest and are
--                                        shown as «DVSH-Modellierung nicht in der Databank»
--   service.name_alt                    alternative name found in DVSH/SHEP (never replaces name)
--   form.dvsh_match                     why the Formular sits under its DVSH service: NULL (filename link
--                                        of 2026-07, or a service DVSH has not modelled) |
--                                        dvsh-formdefinition (eFormular built from DVSH) |
--                                        konsolidiert (Dateiname im DVSH-Modell) |
--                                        zuordnung (sicher|wahrscheinlich): <Beleg> |
--                                        zuordnung (DVSH-Aufteilung 2026-09-27): <Beleg> |
--                                        tentativ (Titel-Ähnlichkeit <score>) (link_dvsh_eforms.py)
--   form.signature_requirement/evidence which signature the form demands, and the quote proving it
--   form.file_hash                      SHA-256 of the source file (change detection, formflow.form_hash)
--   data_field.no_basis                 1 = the legal pass found no article (superseded by basis_typ;
--                                        kept for the export's verification level)
--   data_field.ech_status               assigned | standard_only | kein_standard
--                                        (standard_only = the standard is known but has no element
--                                        for this datum — a final answer, not a gap in the sweep)
--   data_field.ech_standard_code        the standard when ech_status = standard_only
--   data_field.esh_code / esh_element   the draft cantonal standard where eCH has nothing;
--                                        NULL whenever ech_element_id is set (convention 7, gated)
--   data_field.ech_herkunft / data_subfield.ech_herkunft   provenance of the eCH verdict:
--                                        NULL = no copy recorded (judged directly, or copied before
--                                        2026-09-16 when no marker was written) | 'propagiert (Name Nx
--                                        geprüft)' / 'propagiert' = copied from a same-named field by
--                                        propagate_ech_names.py | 'zweitgeprüft' = later covered by a
--                                        verdict (load_ech_verdicts_new.py)
--   form_outcome.rechtsmittel_regel_id -> rechtsmittel_regel(id); form_outcome.rechtsmittel_quelle
--                                        allgemein | sektoral | offen | NULL (see the Rechtsmittel layer)
--   canonical_attribute.n_register      how many of the datum's fields describe a natural person
--                                        (only those can be prefilled from the Einwohnerregister)
--   ech_standard.status / reifegrad / fachgruppe   from the ech.ch catalogue sweep
--   ech_standard.xsd_version / xsd_file / xsd_swept_at   the schema file the elements and
--                                        code lists were read from (sweep_ech_xsd.py); foreign
--                                        schemas imported by a standard are never pinned as its own

-- ---------------------------------------------------------------------------
-- Field layer (2026-08): the Formular's data, atomised, with article-level bases
-- and the eCH/eSH mapping. Loaders: load_data_fields.py, init_subfields.py,
-- load_field_legal.py, load_ech_map.py, load_subfield_ech.py, load_esh.py.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS data_subfield (         -- atomic parts of a composite data_field
    id                INTEGER PRIMARY KEY,
    data_field_id     INTEGER NOT NULL REFERENCES data_field(id) ON DELETE CASCADE,
    ord               INTEGER NOT NULL,
    name              TEXT NOT NULL,
    ech_element_id    INTEGER REFERENCES ech_element(id),
    ech_standard_code TEXT REFERENCES ech_standard(code),
    ech_status        TEXT,                        -- assigned | standard_only | kein_standard
    esh_code          TEXT REFERENCES esh_standard(code),
    esh_element       TEXT,
    ech_herkunft      TEXT,                        -- provenance of the eCH verdict (column notes above)
    UNIQUE(data_field_id, ord));
CREATE INDEX IF NOT EXISTS ix_subfield_field ON data_subfield(data_field_id);

CREATE TABLE IF NOT EXISTS data_field_legal_basis ( -- article-level citation per field (gated:
    id              INTEGER PRIMARY KEY,           --  the article must exist in the ingested law)
    data_field_id   INTEGER NOT NULL REFERENCES data_field(id),
    article_id      INTEGER NOT NULL REFERENCES article(id),
    citation_detail TEXT,                          -- Abs./lit. within the article
    last_checked    TEXT,                          -- verification level shown in the dashboard
    relation        TEXT DEFAULT 'requires');      -- requires | permits | informs
CREATE INDEX IF NOT EXISTS ix_dflb_df ON data_field_legal_basis(data_field_id);

CREATE TABLE IF NOT EXISTS esh_standard (          -- the DRAFT cantonal standard (eSH): one row per
    code TEXT PRIMARY KEY,                         --  standard, covering what eCH does not; never
    titel TEXT NOT NULL, beschreibung TEXT, themen TEXT,   --  confusable with eCH (status stays 'entwurf')
    status TEXT DEFAULT 'entwurf',
    n_felder INTEGER DEFAULT 0);                   -- live count is recomputed in export_json.py

CREATE TABLE IF NOT EXISTS ech_codelist (          -- enumerations read from the eCH XSD files
    id        INTEGER PRIMARY KEY,                 --  (sweep_ech_xsd.py); a field's own value list
    standard  TEXT NOT NULL REFERENCES ech_standard(code),   -- is compared against these
    type_name TEXT NOT NULL,                       -- the simpleType that carries the enumeration
    value     TEXT NOT NULL,
    doc       TEXT,                                -- xs:documentation of the value, if any
    UNIQUE(standard, type_name, value));
CREATE INDEX IF NOT EXISTS ix_codelist_std ON ech_codelist(standard);

-- ---------------------------------------------------------------------------
-- Data-handling rules (2026-08): what the law says about storing, processing,
-- disclosing personal data. Loader: load_data_rules.py — every quote is gated
-- verbatim against the official law PDF (quote_verified = 1 or the row is rejected).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS data_rule (
    id                 INTEGER PRIMARY KEY,
    article_id         INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,
    aspect             TEXT NOT NULL,              -- erhebung | bearbeitung | speicherung | aufbewahrung |
                                                   --  loeschung | archivierung | bekanntgabe | sicherheit |
                                                   --  betroffenenrechte
    scope              TEXT NOT NULL,              -- allgemein | besonders_schuetzenswert | sektoral
    sensitive_category TEXT,                       -- when scope = besonders_schuetzenswert
    summary            TEXT NOT NULL,              -- one plain-German sentence
    quote              TEXT,                       -- verbatim from the law PDF
    quote_verified     INTEGER NOT NULL DEFAULT 0,
    last_checked       TEXT);
CREATE INDEX IF NOT EXISTS ix_data_rule_article ON data_rule(article_id);

-- ---------------------------------------------------------------------------
-- Source-of-truth mirrors (read-only harvests; never written back):
-- the DVSH service model (load_dvsh_harvest.py) and the SHEP portal (load_shep.py).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dvsh_service (          -- one row per DVSH service, fields as modelled
    dvsh_id      INTEGER PRIMARY KEY,
    slug TEXT, title TEXT, version TEXT, department TEXT, dienststelle TEXT,
    kurzbeschreibung TEXT, beschreibung TEXT,
    voraussetzungen TEXT, unterlagen TEXT, ablauf TEXT,            -- JSON arrays
    bearbeitungsdauer TEXT, fristen TEXT, gebuehren TEXT,
    recht_kantonal TEXT, recht_bund TEXT,          -- JSON arrays [{titel, ssr}] / [{titel, sr}]
    externe_links TEXT, abgabe TEXT, kontakt TEXT, -- JSON arrays
    service_id   INTEGER REFERENCES service(id),   -- our matched service (nullable)
    match_kind   TEXT,                             -- exact | normalized | fuzzy | none | kept | harvest-<date>
    status TEXT, online INTEGER, online_version INTEGER, published_at TEXT, dvsh_updated_at TEXT,
    endpoint_typ TEXT, vollzugsbehoerde TEXT, submission_endpoint TEXT,
    documents TEXT, sources TEXT, form_definitions TEXT, completeness TEXT,   -- JSON
    email TEXT, phone TEXT, address TEXT, org_id INTEGER, opening_hours TEXT);
CREATE INDEX IF NOT EXISTS idx_dvsh_service ON dvsh_service(service_id);

CREATE TABLE IF NOT EXISTS dvsh_organisation (     -- the DVSH organisation tree with contacts
    id INTEGER PRIMARY KEY, parent_id INTEGER,
    slug TEXT, name TEXT, kind TEXT,
    contact_name TEXT, contact_email TEXT, contact_phone TEXT,
    contact_address TEXT, contact_url TEXT, opening_hours TEXT,
    updated_at TEXT);

CREATE TABLE IF NOT EXISTS shep_service (          -- one row per SHEP portal page
    slug TEXT PRIMARY KEY,
    service_id INTEGER REFERENCES service(id),
    dvsh_id INTEGER,
    title TEXT, teaser TEXT, updated TEXT, kurzbeschreibung TEXT,
    voraussetzungen TEXT, unterlagen TEXT, ablauf TEXT,            -- JSON arrays
    formular_url TEXT, dokumente TEXT, links TEXT,                 -- JSON arrays
    kontakt_einheit TEXT, kontakt_adresse TEXT, kontakt_email TEXT,
    harvested_at TEXT);

CREATE TABLE IF NOT EXISTS form_check (            -- is the Formular still the current one online?
    form_id     INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,   -- (load_currency.py, from
                                                   -- check_online.py output; Formulare with a file only)
    status      TEXT NOT NULL,                     -- aktuell | veraltet_verdacht | nicht_gefunden | nicht_auffindbar
                                                   -- | lokal_fehlt
    quelle TEXT, online_name TEXT, online_url TEXT, dvsh_neu TEXT, note TEXT,
    checked_at  TEXT DEFAULT (datetime('now')),
    next_check_due TEXT);

CREATE TABLE IF NOT EXISTS formflow (              -- guided questionnaire per Formular (flows.html)
    form_id      INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,
    flow         TEXT NOT NULL,                    -- the QuestionFlow JSON (load_flows.py)
    n_nodes      INTEGER NOT NULL,
    n_ausgelassen INTEGER NOT NULL DEFAULT 0,
    generated_at TEXT DEFAULT (datetime('now')),
    form_hash    TEXT);                            -- form.file_hash the flow was built from

-- ---------------------------------------------------------------------------
-- Rechtsmittel layer (2026-09): which remedy a person has against a Verfahren's
-- decision. Rules are quoted verbatim from the law PDF (gated); the general rule
-- is VRG Art. 16 Abs. 1 / Art. 20 Abs. 1; sectoral provisions where the cited
-- law has its own. Loaders: load_rechtsmittel.py, load_rechtsmittel_verdicts.py.
-- form_outcome.rechtsmittel_quelle (allgemein | sektoral | offen | NULL) and
-- form_outcome.rechtsmittel_regel_id say which rule a form shows, or that the
-- panel could not decide it (offen); NULL = not assessed yet.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rechtsmittel_regel (
    id               INTEGER PRIMARY KEY,
    law_id           INTEGER NOT NULL REFERENCES law(id),
    article_id       INTEGER NOT NULL REFERENCES article(id),
    scope            TEXT NOT NULL CHECK(scope IN ('allgemein','sektoral')),
    rechtsmittel_art TEXT NOT NULL CHECK(rechtsmittel_art IN
        ('einsprache','rekurs','beschwerde','verwaltungsgerichtsbeschwerde','verweis')),
    frist_tage       INTEGER,                      -- the number must appear in frist_quote
    frist_article_id INTEGER REFERENCES article(id),
    frist_quote      TEXT,
    instanz          TEXT,
    gilt_fuer        TEXT,                         -- which decisions the provision covers
    quote            TEXT NOT NULL,
    quote_verified   INTEGER NOT NULL DEFAULT 0,
    hinweis          TEXT,
    last_checked     TEXT,
    gestrichen       INTEGER NOT NULL DEFAULT 0,   -- struck by the second review; kept for the FK,
    UNIQUE(law_id, article_id, rechtsmittel_art)); --  never shown, never a candidate

CREATE TABLE IF NOT EXISTS rechtsmittel_verdikt (  -- the panel's per-form reasoning
    form_id      INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,
    regel_id     INTEGER REFERENCES rechtsmittel_regel(id),
    quelle       TEXT NOT NULL CHECK(quelle IN ('sektoral','allgemein','offen')),
    begruendung  TEXT NOT NULL,
    last_checked TEXT);

-- ---------------------------------------------------------------------------
-- Second opinions: every single-pass judgment layer got an adversarial review;
-- this table records which items were reviewed and the reviewer's verdict.
-- kind = basis (basis_typ) | subjekt | rmrule | rmverdict | partei (item_id = form.id: the second
-- review of a Formular's judged parties, loaded by scripts/rollen.py laden). Loader: load_panel_reviews.py.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS panel_review (
    kind     TEXT NOT NULL,
    item_id  INTEGER NOT NULL,                     -- data_field.id / rechtsmittel_regel.id / form.id
    urteil   TEXT NOT NULL,                        -- bestaetigt | geaendert | korrigiert | streichen | offen
    grund    TEXT,
    PRIMARY KEY (kind, item_id));

-- ---------------------------------------------------------------------------
-- «Eine Angabe, ein Name» (2026-09): for every eCH element the forms ask for under
-- two or more labels, one proposed term (always an existing form label) and a
-- class per label. Chain: scripts/run_begriffe.py (the single loaders refuse to
-- run alone, BEGRIFFE_CHAIN guard), corrections from the quellen/korrekturen/ files
-- that carry begriff_label / begriff_vorschlag / service_thema.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS begriff_vorschlag (
    ech_element_id INTEGER PRIMARY KEY REFERENCES ech_element(id),
    term           TEXT NOT NULL,                  -- must be a label that exists in the forms
    begruendung    TEXT,
    zweitgeprueft  INTEGER NOT NULL DEFAULT 0,
    vorbehalt      INTEGER NOT NULL DEFAULT 0,     -- 1 = no clean term exists; pruefung says why
    herkunft       TEXT,                           -- eigen (panel) | korpus (most frequent label)
    pruefung       TEXT);

CREATE TABLE IF NOT EXISTS begriff_label (         -- one row per (element, normalised label)
    ech_element_id INTEGER NOT NULL REFERENCES ech_element(id),
    label_norm     TEXT NOT NULL,
    label          TEXT NOT NULL,
    klasse         TEXT NOT NULL CHECK(klasse IN ('vorschlag','variante','rolle','pruefen')),
                                                   -- variante = same datum, other wording (angleichen)
                                                   -- rolle    = names whose/which datum; fine as is
                                                   -- pruefen  = see pruefart
    rolle          TEXT,                           -- the role a 'rolle' label names
    grund          TEXT,
    zweitgeprueft  INTEGER NOT NULL DEFAULT 0,
    pruefart       TEXT,                           -- aufteilen (field bundles several data) |
                                                   --  zuordnung (eCH mapping is wrong — a databank fix)
    pruefart_grund TEXT,
    PRIMARY KEY (ech_element_id, label_norm));

-- ---------------------------------------------------------------------------
-- Lebenslagen (2026-09): the Themengruppen of eCH-0049 V4.00 (approved), one
-- catalogue for private persons and one for businesses, each group gated as a
-- verbatim block against quellen/ech-0049/*.pdf (load_themenkatalog.py).
-- Services get up to three groups, ranked (load_themen.py); the reasoning per
-- service is kept for the second review.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS themenkatalog (
    id        INTEGER PRIMARY KEY,
    katalog   TEXT NOT NULL CHECK(katalog IN ('privat','unternehmen')),
    bereich   TEXT NOT NULL,                       -- Themenbereich (the parent heading)
    gruppe    TEXT NOT NULL,                       -- Themengruppe, verbatim from the PDF
    ord       INTEGER NOT NULL,
    quelle    TEXT NOT NULL,                       -- PDF file + Darstellung the group was read from
    UNIQUE(katalog, bereich, gruppe));

CREATE TABLE IF NOT EXISTS service_thema (
    service_id    INTEGER NOT NULL REFERENCES service(id),
    thema_id      INTEGER NOT NULL REFERENCES themenkatalog(id),
    rang          INTEGER NOT NULL,                -- 1 = primary group
    PRIMARY KEY (service_id, thema_id));

CREATE TABLE IF NOT EXISTS service_thema_grund (
    service_id    INTEGER PRIMARY KEY REFERENCES service(id),
    grund         TEXT,
    zweitgeprueft INTEGER NOT NULL DEFAULT 0);

-- ---------------------------------------------------------------------------
-- Gestaltung (2026-10): how each Formular looks and is presented — fonts,
-- sizes, colours, the accessibility facts the file carries, the phone numbers
-- and e-mail types it prints, edition mark, page numbers, sender. Measured
-- facts only: a value that cannot be measured is NULL with the reason in
-- hinweise, never a guess; no verdict and no comparison across Formulare is
-- stored here. Loader: scan_gestaltung.py (needs pypdf; the measuring code is
-- gestaltung_pdf.py, gestaltung_office.py, gestaltung_text.py — their
-- docstrings define every value). One row per Formular with a file; the
-- eFormulare have none (their look is the platform's). A missing row means
-- «noch nicht gemessen»; a row whose file_hash differs from form.file_hash is
-- stale and fails validate_db.py, which also checks messart against
-- form.file_type and the scalar columns against profil.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS form_gestaltung (       -- how a Formular looks: measured facts, no verdicts
    form_id      INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,
    file_hash    TEXT NOT NULL,             -- sha256 of the measured file (= form.file_hash when current)
    messart      TEXT NOT NULL CHECK (messart IN ('pdf','pdf_bild','word','excel','nicht_messbar')),
    methode      TEXT NOT NULL,             -- version of the measuring code, e.g. 'gestaltung-1'
    seiten       INTEGER,
    hauptschrift TEXT,                      -- normalised family of most characters
    grundgroesse REAL,                      -- pt, size of most characters
    akzentfarbe  TEXT,                      -- '#rrggbb' of the accent colour (profil.akzent); NULL = none above the threshold (link colours, field colours, a logo drawn in the head of page 1 and everything inside images do not count) or not measurable — profil.farben and hinweise tell which
    pdf_tags     INTEGER,                   -- 1/0 = marked as tagged with a structure tree that is not empty (says nothing about the quality of the tags); NULL when not a PDF
    profil       TEXT NOT NULL,             -- JSON, the full measured profile (keys: validate_db.py GESTALTUNG_KEYS)
    hinweise     TEXT                       -- JSON array of limitations of this measurement
);

-- ---------------------------------------------------------------------------
-- Permanent identifiers (2026-10): one identifier per service, Formular,
-- Datenfeld, Teilfeld, canonical Angabe, law, article and data-handling rule
-- that never changes meaning, so that other systems (the Datentresor, the LLM
-- agent, a peer canton) can store it. Neutral scheme without a web address
-- (the base address for resolvable URIs is an owner decision, the constant
-- BASIS_URI in scripts/kennungen.py):
--   sh:service:<slug> · sh:formular:<slug> · sh:formular:<slug>:feld:<n>
--   · sh:formular:<slug>:feld:<n>:teil:<m> · sh:angabe:<eCH-code>:<element>[:<context>]
--   · sh:angabe:<eSH-code>:<element> · sh:gesetz:sr-<SR> | shr-<SHR> | <slug>
--   · sh:gesetz:<…>:art-<no> | par-<no> | nr-<no> · <article>:regel:<aspect>-<scope>[-<category>]
-- Minted once from the natural key the object has at that moment (Datenfeld and
-- Teilfeld: a serial number per parent, in field order — a label is no stable
-- key), never changed, reused or reassigned; a clash gets «~2». Loader:
-- scripts/kennungen.py (runs in ./build.sh right after init_register.py, which
-- renumbers canonical_attribute on every build); the resolver is
-- kennungen.aufloesen(). The parent of a Datenfeld, Teilfeld, article or rule is
-- the identifier it was minted under (its prefix; kennungen.eltern_von()). The
-- gates live in the schema: the triggers below refuse a DELETE, any change of
-- kennung/art/ziel_tabelle/seit, a new element for an Angabe identifier and any
-- change to a superseded identifier; validate_db.py runs kennungen.pruefen() on
-- every staging copy.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kennung (
    kennung         TEXT PRIMARY KEY,              -- the permanent identifier, e.g. sh:formular:<slug>:feld:3
    art             TEXT NOT NULL CHECK (art IN ('service','formular','feld','teilfeld',
                                                 'angabe','gesetz','artikel','regel')),
    ziel_tabelle    TEXT NOT NULL CHECK (ziel_tabelle IN ('service','form','data_field','data_subfield',
                                                 'canonical_attribute','law','article','data_rule')),
    ziel_id         INTEGER,                       -- the row the identifier names today (NULL unless aktiv);
                                                   --  canonical_attribute ids are renumbered on every build,
                                                   --  so this is re-resolved by the natural key each run
    schluessel      TEXT NOT NULL,                 -- natural key it stands for: slug (service, Formular) |
                                                   --  norm_label(name) within the parent (Datenfeld, Teilfeld) |
                                                   --  ech|standard|element|context or esh|<eSH key> (Angabe,
                                                   --  never changes) | sr:<SR> / shr:<SHR> / slug:<slug> (law) |
                                                   --  article_no (article) | aspect|scope|category (rule)
    merkmal         TEXT,                          -- checksum (12 hex of sha256) of the evidence that lets a
                                                   --  renamed object keep its identifier: name (service) |
                                                   --  title (Formular) | ord|data_type (Datenfeld) |
                                                   --  ord|element (Teilfeld) | slug (law) | heading (article) |
                                                   --  quote (rule); NULL (Angabe: a new element is a new Angabe)
    status          TEXT NOT NULL DEFAULT 'aktiv' CHECK (status IN ('aktiv','abgeloest','entfallen')),
                                                   -- entfallen = the object is no longer in the databank (the
                                                   --  identifier stays; it lives again only for the identical
                                                   --  schluessel) | abgeloest = superseded, successor named
    abgeloest_durch TEXT REFERENCES kennung(kennung),   -- only from the reviewed decision file
                                                   --  quellen/kennung_abloesungen.json, never guessed
    seit            TEXT NOT NULL,                 -- date the identifier was issued (JJJJ-MM-TT)
    bis             TEXT,                          -- date it stopped naming a current object
    grund           TEXT,                          -- why it is no longer active
    CHECK ((status = 'aktiv') = (ziel_id IS NOT NULL)),
    CHECK ((status = 'aktiv') = (bis IS NULL)),
    CHECK ((status = 'abgeloest') = (abgeloest_durch IS NOT NULL))
) WITHOUT ROWID;                                   -- clustered on the identifier, no further index: one
                                                   --  active identifier per (ziel_tabelle, ziel_id) and per
                                                   --  natural key is checked by kennungen.pruefen()

CREATE TABLE IF NOT EXISTS kennung_verlauf (       -- what happened to an identifier after it was issued
    id       INTEGER PRIMARY KEY,                  --  (append-only; issuance itself is kennung.seit)
    kennung  TEXT NOT NULL REFERENCES kennung(kennung),
    datum    TEXT NOT NULL,
    ereignis TEXT NOT NULL CHECK (ereignis IN ('umbenannt','entfallen','reaktiviert','abgeloest')),
    vorher   TEXT,                                 -- schluessel before (umbenannt, entfallen)
    nachher  TEXT                                  -- schluessel after (umbenannt, reaktiviert) or the successor
);
CREATE INDEX IF NOT EXISTS ix_kennung_verlauf ON kennung_verlauf(kennung);

CREATE TRIGGER IF NOT EXISTS tg_kennung_nie_loeschen BEFORE DELETE ON kennung
BEGIN SELECT RAISE(ABORT, 'GATE: eine Kennung wird nie gelöscht — sie bleibt als entfallen oder abgelöst stehen'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_unveraenderlich BEFORE UPDATE ON kennung
WHEN NEW.kennung IS NOT OLD.kennung OR NEW.art IS NOT OLD.art OR NEW.ziel_tabelle IS NOT OLD.ziel_tabelle
     OR NEW.seit IS NOT OLD.seit
BEGIN SELECT RAISE(ABORT, 'GATE: Kennung, Art, Zieltabelle und Vergabedatum ändern sich nie'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_angabe_fest BEFORE UPDATE ON kennung
WHEN OLD.art = 'angabe' AND NEW.schluessel IS NOT OLD.schluessel
BEGIN SELECT RAISE(ABORT, 'GATE: eine Angabe-Kennung steht für genau ein eCH-Element oder einen eSH-Schlüssel'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_schluessel_nur_aktiv BEFORE UPDATE ON kennung
WHEN NEW.schluessel IS NOT OLD.schluessel AND NOT (OLD.status = 'aktiv' AND NEW.status = 'aktiv')
BEGIN SELECT RAISE(ABORT, 'GATE: nur eine aktive Kennung folgt einer Umbenennung; eine entfallene lebt nur für denselben Schlüssel wieder auf'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_abgeloest_endgueltig BEFORE UPDATE ON kennung
WHEN OLD.status = 'abgeloest' AND (NEW.status IS NOT OLD.status OR NEW.abgeloest_durch IS NOT OLD.abgeloest_durch)
BEGIN SELECT RAISE(ABORT, 'GATE: eine abgelöste Kennung bleibt abgelöst, ihr Nachfolger ändert sich nie'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_verlauf_u BEFORE UPDATE ON kennung_verlauf
BEGIN SELECT RAISE(ABORT, 'GATE: der Verlauf der Kennungen ist unveränderlich'); END;
CREATE TRIGGER IF NOT EXISTS tg_kennung_verlauf_d BEFORE DELETE ON kennung_verlauf
BEGIN SELECT RAISE(ABORT, 'GATE: der Verlauf der Kennungen ist unveränderlich'); END;

-- ---------------------------------------------------------------------------
-- Parteien und Rollen (2026-10): whose Angabe each data point is. The finer layer
-- above data_field.subjekt: a controlled role list, the parties of every Formular
-- and the assignment of every data point (Teilfeld, or Datenfeld without parts) to
-- exactly one party of its Formular, or «unklar» with a reason — never a guess.
-- Stage B1 is derived deterministically from the databank's own words (begriff
-- role, party words in labels and sections, subjekt) by scripts/rollen.py ableiten
-- (standard library; the build runs it right after init_register.py); stage B2 is
-- a judged verdict per Formular, loaded by scripts/rollen.py laden through proof
-- gates (role from the list, every point exactly once, every evidence quote found
-- in the Formular text) and second-reviewed (panel_review kind 'partei'). Subjekt
-- stays consistent: an assigned point's field subjekt equals the party's entity
-- type, or the party is 'gemischt' and the subjekt natuerliche_person,
-- organisation or gemischt (gate: scripts/rollen.py pruefen, called by validate_db).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS partei_rolle (          -- the controlled role list («Vorschlag» until the canton confirms it)
    code       TEXT PRIMARY KEY,                   -- stable key, e.g. 'gesuchsteller'
    label      TEXT NOT NULL UNIQUE,               -- German label shown to readers
    entitaet   TEXT NOT NULL CHECK (entitaet IN ('natuerliche_person','organisation','sache','behoerde','offen')),
                                                   -- offen = person or organisation, the Formular decides
    erklaerung TEXT NOT NULL,
    grundlage  TEXT NOT NULL,                      -- JSON: role strings, party words and labels that ground it
    ord        INTEGER NOT NULL,
    status     TEXT NOT NULL DEFAULT 'vorschlag' CHECK (status IN ('vorschlag','bestaetigt')));

CREATE TABLE IF NOT EXISTS formular_partei (       -- the parties a Formular asks about
    form_id     INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    partei_nr   INTEGER NOT NULL,                  -- 1..n in the order the Formular first asks about them
    rolle       TEXT NOT NULL REFERENCES partei_rolle(code),
    entitaet    TEXT NOT NULL CHECK (entitaet IN ('natuerliche_person','organisation','sache','behoerde','gemischt','offen')),
    bezeichnung TEXT NOT NULL,                     -- how the Formular names it («Kind 2», «anderer Elternteil»)
    mehrere     INTEGER NOT NULL DEFAULT 0,        -- 1 = a list of several (Kinder, Gesellschafter/innen)
    beleg       TEXT NOT NULL,                     -- evidence: label/section text (B1) or Formular quote (B2)
    herkunft    TEXT NOT NULL CHECK (herkunft IN ('regel','urteil')),
    PRIMARY KEY (form_id, partei_nr));

CREATE TABLE IF NOT EXISTS datenpunkt_partei (     -- every data point -> exactly one party, or «unklar»
    data_field_id INTEGER NOT NULL REFERENCES data_field(id) ON DELETE CASCADE,
    teil          TEXT NOT NULL DEFAULT '',        -- norm_ascii(Teilfeld name); '' = Datenfeld without parts
    form_id       INTEGER NOT NULL REFERENCES form(id) ON DELETE CASCADE,
    teil_name     TEXT NOT NULL,                   -- the label when assigned (a changed label = stale row)
    status        TEXT NOT NULL CHECK (status IN ('zugeordnet','unklar')),
    partei_nr     INTEGER,                         -- NULL exactly when status = 'unklar'
    regel         TEXT,                            -- B1 rule (rolle_begriff | wort_bezeichnung | wort_abschnitt | subjekt | definition)
    grund_code    TEXT,                            -- why unklar (UNKLAR_GRUENDE)
    grund         TEXT NOT NULL,                   -- the evidence (zugeordnet) or the reason (unklar), German
    herkunft      TEXT NOT NULL CHECK (herkunft IN ('regel','urteil')),
    regel_rolle   TEXT,                            -- what stage B1 derived, kept when B2 decides (calibration)
    PRIMARY KEY (data_field_id, teil),
    FOREIGN KEY (form_id, partei_nr) REFERENCES formular_partei(form_id, partei_nr));
CREATE INDEX IF NOT EXISTS ix_datenpunkt_partei_form ON datenpunkt_partei(form_id);

CREATE TABLE IF NOT EXISTS partei_urteil (         -- stage B2: the judged parties of one Formular (proof-gated)
    form_id     INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,
    file_hash   TEXT,                              -- form.file_hash the verdict was made on (NULL for eFormulare)
    parteien    TEXT NOT NULL,                     -- JSON array: nr, rolle, entitaet, bezeichnung, mehrere, beleg
    punkte      TEXT NOT NULL,                     -- JSON array: key, partei | unklar, beleg
    quelle      TEXT NOT NULL,                     -- file the verdict was loaded from
    geladen     TEXT NOT NULL);                    -- load date (YYYY-MM-DD)

-- ---------------------------------------------------------------------------
-- Gesetzesstand (2026-10): which edition («Stand») of each law the databank read
-- its articles from, and dated checks of that edition against the official
-- sources. Evidence only: a value that is not evidenced is NULL with the reason
-- in grund, never a guess. Loaders: scripts/gesetz_stand.py (gesetz_stand; reads
-- the databank and the law PDFs next to the repository, needs macOS PDFKit like
-- extract_law.py) and scripts/check_gesetz_stand.py (gesetz_stand_pruefung;
-- read-only GETs to rechtsbuch.sh.ch for cantonal law and to the Fedlex SPARQL
-- endpoint for federal law). Neither re-reads an article or changes a citation:
-- a newer edition is listed for review. The change-impact index over both
-- tables and the citations is computed once in scripts/wirkung.py (export). The
-- gate is gesetz_stand.pruefen(), run by validate_db.py: vocabularies, the Stand
-- among its own evidence, the evidence recorded at reading time against the
-- databank (unless the row is stale: basis differs), and every check row
-- consistent with the edition list it stores.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gesetz_stand (          -- one row per law: the edition its articles were read from
    law_id             INTEGER PRIMARY KEY REFERENCES law(id) ON DELETE CASCADE,
    stand              TEXT,                -- ISO date of the edition read («Stand» / «Fassung»); NULL = not evidenced
    status             TEXT NOT NULL CHECK (status IN ('belegt','widerspruch','unbekannt')),
                                            -- belegt = every source that names a Stand names this one;
                                            -- widerspruch = the sources disagree (stand NULL, grund names them);
                                            -- unbekannt = no source names one (stand NULL, grund says why)
    stand_quelle       TEXT CHECK (stand_quelle IN ('einlesen','pdf_datei')),
                                            -- einlesen = recorded when the articles were read (article or law
                                            -- last_checked, law.source_note); pdf_datei = printed in the head of the
                                            -- PDF the loaders read, not recorded at reading time; NULL with stand NULL
    datei              TEXT,                -- that PDF relative to the law folder beside the repository:
                                            -- '<SHR>-….de.pdf' (cantonal) or 'Bund/<SR>.pdf' (federal); NULL = none
    datei_herkunft     TEXT CHECK (datei_herkunft IN ('gesetzessammlung','rechtsbuch_api','fedlex')),
                                            -- the canton's PDF collection | fetched by fetch_rechtsbuch.py
                                            -- ('-rechtsbuch.de.pdf') | a Fedlex PDF (ingest_fed.py, extract_quotes.py)
    datei_sha256       TEXT,                -- SHA-256 of the file when the row was written
    texte_zitiert      INTEGER,             -- cited articles (data_field_legal_basis) with a stored text_excerpt
    texte_gefunden     INTEGER,             -- … whose text occurs in the file (at least one 40-letter window)
    texte_vollstaendig INTEGER,             -- … whose text occurs in the file in every window
    belege             TEXT NOT NULL,       -- JSON list, one entry per source and value: {quelle, stand, roh, …};
                                            -- quelle artikel_vermerk | gesetz_vermerk | pdf_kopf | index_titel
    grund              TEXT,                -- why stand is NULL; NULL when status = 'belegt'
    basis              TEXT NOT NULL,       -- fingerprint of the databank rows the row was derived from
                                            -- (gesetz_stand.fingerabdruck); a different value = stale row
    erhoben_am         TEXT NOT NULL        -- ISO day the row's content last changed
);

CREATE TABLE IF NOT EXISTS gesetz_stand_pruefung ( -- one row per law and day: is the edition read still current?
    law_id          INTEGER NOT NULL REFERENCES law(id) ON DELETE CASCADE,
    geprueft_am     TEXT NOT NULL,              -- ISO day the official source answered
    quelle          TEXT NOT NULL CHECK (quelle IN ('rechtsbuch','fedlex','keine')),
                                                -- keine = the law has no official number to ask for
    abfrage         TEXT,                       -- the GET that was sent; NULL for quelle 'keine'
    ergebnis        TEXT NOT NULL CHECK (ergebnis IN ('aktuell','neuer_stand','aufgehoben','stand_unbekannt',
                        'nicht_gefunden','nicht_pruefbar','fehler','unklar')),
                                                -- aktuell = stand_gelesen is the edition in force; neuer_stand =
                                                -- a later edition is in force; stand_unbekannt = the edition read is
                                                -- not evidenced, so there is nothing to compare
    stand_gelesen   TEXT,                       -- gesetz_stand.stand when the check ran
    fassung_gelesen TEXT,                       -- the source's address of that edition; NULL = not identifiable
                                                -- (details says why)
    stand_aktuell   TEXT,                       -- in-force date of the current edition at the source
    fassung_aktuell TEXT,                       -- the source's address of the current edition
    n_neuere        INTEGER,                    -- editions in force after stand_gelesen up to geprueft_am
    kuenftig        TEXT NOT NULL DEFAULT '[]', -- JSON list {art: fassung|aufhebung, stand, fassung}: already
                                                -- published, in force after geprueft_am
    details         TEXT NOT NULL DEFAULT '{}', -- JSON object: the edition list as the source gave it
    grund           TEXT,                       -- required unless ergebnis is aktuell or neuer_stand
    PRIMARY KEY (law_id, geprueft_am));

-- ---------------------------------------------------------------------------
-- Register (2026-10, «Was der Kanton schon weiss»): which Swiss registers already
-- hold the data and the Beilagen the Formulare ask for. Facts only: every register,
-- its holder, content, key, standard links, the Angaben it holds and the documents
-- it issues carry a verbatim quote from an official source fetched with a read-only
-- GET (Fedlex filestore, Schaffhauser Rechtsbuch interface, agency pages, ech.ch) or
-- from an official schema file of the repository; the text snapshot lies under
-- quellen/register/<id>.txt and the gate finds the quote in it.
-- Loaders, in this order: scripts/register_katalog.py (--abrufen fetches the sources,
-- without it the catalogue is loaded) and scripts/register_map.py (Angaben,
-- documents, access articles). Gate: register_map.pruefen(), called by validate_db.py.
-- «Ein Register hält es» never means «die Stelle darf es beziehen»: access is a
-- second step, recorded only as an ingested and quoted article (kandidat or
-- schranke), otherwise «Zugriff offen — rechtlich zu klären». What a Formular would
-- save is computed once in export_json.py (register_map.export_register) and is a
-- model estimate, never a measurement.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS register_quelle (        -- one fetched source (official page, law text or repository schema)
    id        TEXT PRIMARY KEY,                     -- e.g. 'fedlex_rhg', 'sh_gg', 'ech_0108'
    url       TEXT NOT NULL UNIQUE,                 -- what was fetched (art 'repo': path inside the repository)
    art       TEXT NOT NULL CHECK(art IN ('html','rechtsbuch','repo')),
    titel     TEXT NOT NULL,
    datei     TEXT NOT NULL,                        -- the text snapshot under quellen/register/
    sha256    TEXT NOT NULL,                        -- of the snapshot text, a changed file fails the gate
    abgerufen TEXT NOT NULL);                       -- fetch time (ISO), kept while the fetched text stays the same

CREATE TABLE IF NOT EXISTS register (               -- one Swiss register or official information system
    code       TEXT PRIMARY KEY,                    -- stable key: einwohnerregister, uid_register, gwr …
    name       TEXT NOT NULL,
    inhaber    TEXT NOT NULL,                       -- who keeps it, as the quoted sources say
    ebene      TEXT NOT NULL CHECK(ebene IN ('bund','kanton','gemeinde')),
    entitaet   TEXT NOT NULL CHECK(entitaet IN ('natuerliche_person','organisation','sache','gemischt')),
    inhalt     TEXT NOT NULL,                       -- what it holds, one German sentence
    schluessel TEXT,                                -- identifying key(s), NULL = no quoted source names one
    stelle_sh  TEXT REFERENCES dienststelle(name),  -- the Schaffhausen office that keeps or feeds it, where a source says so
    bemerkung  TEXT);                               -- a limit the reader must know (statistical register, only Swiss documents …)

CREATE TABLE IF NOT EXISTS register_beleg (         -- the quote behind each claim about a register
    register TEXT NOT NULL REFERENCES register(code) ON DELETE CASCADE,
    aspekt   TEXT NOT NULL CHECK(aspekt IN ('inhaber','inhalt','schluessel','dokument')),
    quelle   TEXT NOT NULL REFERENCES register_quelle(id),
    zitat    TEXT NOT NULL,                         -- verbatim in the snapshot (whitespace collapsed)
    PRIMARY KEY (register, aspekt, quelle, zitat));

CREATE TABLE IF NOT EXISTS register_standard (      -- the eCH standards (present in ech_standard) a register exchanges with
    register TEXT NOT NULL REFERENCES register(code) ON DELETE CASCADE,
    standard TEXT NOT NULL REFERENCES ech_standard(code),
    art      TEXT NOT NULL CHECK(art IN ('quelle','projektregel')),
                                                    -- quelle = the standard's own ech.ch page names the register
                                                    -- projektregel = init_register.REGISTER_STDS (Einwohnerregister only)
    quelle   TEXT REFERENCES register_quelle(id),
    zitat    TEXT,                                  -- NULL only for 'projektregel'
    PRIMARY KEY (register, standard));

CREATE TABLE IF NOT EXISTS register_angabe (        -- canonical Angabe × entity type -> register that holds it
    register    TEXT NOT NULL REFERENCES register(code) ON DELETE CASCADE,
    angabe      TEXT NOT NULL,                      -- 'ech:<ech_element.id>' or 'esh:<code>:<element>' (the canonical Angabe)
    ech_element_id INTEGER REFERENCES ech_element(id),
    esh_code    TEXT REFERENCES esh_standard(code),
    esh_element TEXT,                               -- exactly one of ech_element_id / (esh_code, esh_element) is set
    entitaet    TEXT NOT NULL CHECK(entitaet IN ('natuerliche_person','organisation','sache','jede')),
    entitaet_aus_element INTEGER NOT NULL DEFAULT 0 CHECK(entitaet_aus_element IN (0,1)),
                                                    -- 1 = the element IDENTIFIES its party (UID, EGID, E-GRID,
                                                    -- Stammnummer, chip number); 0 = the field's judged subjekt must
                                                    -- say whose Angabe it is (a name, an address, a legal form)
    quelle      TEXT NOT NULL REFERENCES register_quelle(id),
    zitat       TEXT NOT NULL,                      -- the source naming this Angabe as content of the register
    kontext     TEXT,                               -- pattern the unit's context (Formular title, field and part label,
                                                    -- folded) must contain: the dog database only for a dog
    ohne        TEXT,                               -- pattern it must not contain: the GWR's Bauprojekt, ships in the IVZ
    PRIMARY KEY (register, angabe, entitaet));
CREATE INDEX IF NOT EXISTS ix_register_angabe_el ON register_angabe(ech_element_id);

CREATE TABLE IF NOT EXISTS register_dokument (      -- documents a register or its office issues: the term found in a Beilage name
    register TEXT NOT NULL REFERENCES register(code) ON DELETE CASCADE,
    begriff  TEXT NOT NULL,                         -- e.g. 'Familienausweis', 'Fahrzeugausweis' (it occurs in the quote)
    quelle   TEXT NOT NULL REFERENCES register_quelle(id),
    zitat    TEXT NOT NULL,
    PRIMARY KEY (register, begriff));

CREATE TABLE IF NOT EXISTS register_zugriff (       -- ingested articles on access to a register, quoted: a candidate or a limit
    register   TEXT NOT NULL REFERENCES register(code) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES article(id),
    art        TEXT NOT NULL CHECK(art IN ('kandidat','schranke')),
                                                    -- never «erlaubt»: whether an office may fetch is for the canton's lawyers
    adressat   TEXT NOT NULL,                       -- whom the article addresses, in its own words
    quelle     TEXT NOT NULL REFERENCES register_quelle(id),
    zitat      TEXT NOT NULL,                       -- verbatim in the official text of that law
    PRIMARY KEY (register, article_id, art));
