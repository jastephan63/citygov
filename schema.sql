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
-- service  — the *modelled* unit. A nominal service may be split into several
--            modelled services (convention 2).
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
    sr_number          TEXT,           -- federal SR number; NULL if n/a / unknown
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
--   Deduped by data_point_key (convention 8). Linked to article(s) via the
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
    is_composite   INTEGER NOT NULL DEFAULT 0,  -- 1 = has identity_part sub-fields (conv 4)
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
-- form — a Formular that actually serves a service (decided by CONTENT, conv 1).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS form (
    id                     INTEGER PRIMARY KEY,
    slug                   TEXT NOT NULL UNIQUE,
    service_id             INTEGER NOT NULL REFERENCES service(id),
    title                  TEXT NOT NULL,   -- title as published
    actual_purpose         TEXT,            -- what the content shows it really serves
    title_content_mismatch INTEGER NOT NULL DEFAULT 0,  -- conv 1 finding flag
    mismatch_note          TEXT,
    source_file            TEXT,            -- path under forms/
    file_type              TEXT,            -- pdf|excel|...
    publisher_dienststelle TEXT,
    last_extracted         TEXT
, purpose TEXT, dsfa_status TEXT, dsfa_note TEXT, file_hash TEXT, acroform INTEGER, signature_requirement TEXT, signature_evidence TEXT, parse_error TEXT, submission_channel TEXT, dvsh_match TEXT);

-- LEGACY auto-draft layer (2026-06, retired): requirement / form_field /
--   field_mapping / requirement_legal_basis were written by scripts/auto_draft.py
--   (now scripts/deprecated/). Superseded by data_field + data_field_legal_basis,
--   the proof-gated layer every surface reads. Kept for provenance («aus N
--   Formularfeldern verdichtet»); its 'proposed' mappings are never exported,
--   and the 240 placeholder law rows it created (last_checked 'zitiert
--   (unverifiziert)') were removed by scripts/migrate_2026_09_26.py.
-- form_field — the field as it actually appears on the form. Independent of
--   the law (convention 3): no requirement FK here.
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
-- document — inventory of EVERY source file with its classification (conv 7).
--   Only doc_type='formular' becomes a form (form_id set after extraction).
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
--   citation TODOs, validation issues (conv 1,6,10). Also rendered in dashboard.
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
, no_basis INTEGER DEFAULT 0, sensitive TEXT, ech_element_id INTEGER REFERENCES ech_element(id), ech_status TEXT, ech_standard_code TEXT REFERENCES ech_standard(code), esh_code TEXT REFERENCES esh_standard(code), esh_element TEXT, schutzstufe TEXT, format_code TEXT, basis_typ TEXT, basis_begruendung TEXT, subjekt TEXT);
CREATE INDEX IF NOT EXISTS idx_data_field_form ON data_field(form_id);

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
-- data_field.ech_element_id -> ech_element(id); data_field.ech_status: assigned|kein_standard

-- ---------------------------------------------------------------------------
-- Data-management layer (2026-09): register of processing activities,
-- executable retention, canonical attributes, format patterns, Dienststellen.
-- Created/seeded by scripts/init_register.py; curated content is loaded
-- through the proof gates of scripts/load_register.py.
-- New columns on existing tables:
--   form.purpose        (Zweck der Bearbeitung, agent-curated)
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
--   service.in_dvsh                     1 = the service exists in the DVSH model (load_dvsh_harvest.py)
--   service.name_alt                    alternative name found in DVSH/SHEP (never replaces name)
--   form.dvsh_match                     how the Formular was matched to DVSH: exact|normalized|fuzzy|none
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
    UNIQUE(data_field_id, ord));

CREATE TABLE IF NOT EXISTS data_field_legal_basis ( -- article-level citation per field (gated:
    id              INTEGER PRIMARY KEY,           --  the article must exist in the ingested law)
    data_field_id   INTEGER NOT NULL REFERENCES data_field(id),
    article_id      INTEGER NOT NULL REFERENCES article(id),
    citation_detail TEXT,                          -- Abs./lit. within the article
    last_checked    TEXT,                          -- verification level shown in the dashboard
    relation        TEXT DEFAULT 'requires');      -- requires | permits | informs

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
    form_id     INTEGER PRIMARY KEY REFERENCES form(id) ON DELETE CASCADE,   -- (check_online.py)
    status      TEXT NOT NULL,                     -- aktuell | veraltet_verdacht | nicht_gefunden | nicht_auffindbar
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
-- kind = basis (basis_typ) | subjekt | rmrule | rmverdict. Loader: load_panel_reviews.py.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS panel_review (
    kind     TEXT NOT NULL,
    item_id  INTEGER NOT NULL,                     -- data_field.id / rechtsmittel_regel.id / form.id
    urteil   TEXT NOT NULL,                        -- bestaetigt | geaendert | korrigiert | streichen | offen
    grund    TEXT,
    PRIMARY KEY (kind, item_id));

-- ---------------------------------------------------------------------------
-- «Ein Datum, ein Name» (2026-09): for every eCH element the forms ask for under
-- two or more labels, one proposed term (always an existing form label) and a
-- class per label. Chain: scripts/run_begriffe.py (the single loaders refuse to
-- run alone, BEGRIFFE_CHAIN guard), corrections from quellen/korrekturen/*.json.
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
