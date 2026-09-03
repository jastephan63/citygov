-- citygov databank — schema (reference DDL)
-- Source of truth = citygov.db. This file documents its structure.
-- Apply with scripts/init_db.py. Never hand-edit the DB; regenerate (convention 9).
--
-- Design notes (map to the non-negotiable conventions):
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
);

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
);

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
);

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

-- field_mapping — THE reconciliation layer (conv 3,4,5). One row per form_field.
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
    id             INTEGER PRIMARY KEY,
    form_id        INTEGER NOT NULL REFERENCES form(id),
    ord            INTEGER,
    name           TEXT NOT NULL,
    definition     TEXT,
    data_type      TEXT,      -- text|date|number|money|boolean|enum|multiselect|composite|attachment|signature
    required       INTEGER DEFAULT 1,
    allowed_values TEXT,      -- JSON array (enum/multiselect)
    subfields      TEXT,      -- JSON array (composite)
    format         TEXT,
    source_widgets TEXT,      -- JSON array of widget labels (provenance)
    derived_by     TEXT DEFAULT 'agent'
);
CREATE INDEX IF NOT EXISTS idx_data_field_form ON data_field(form_id);

-- besonders schützenswerte Personendaten (DSG Art. 5 lit. c); NULL = nicht besonders schützenswert
-- Werte: gesundheit | religion_weltanschauung | politik | ethnie_herkunft | genetik_biometrie | strafen_verfahren | sozialhilfe
-- ALTER TABLE data_field ADD COLUMN sensitive TEXT;

-- eCH e-government data standards (public, from ech.ch XSDs) and the mapping of
-- each data field to its official standardised element.
CREATE TABLE IF NOT EXISTS ech_standard (
    code TEXT PRIMARY KEY, title TEXT, url TEXT, n_elements INTEGER DEFAULT 0);
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

CREATE TABLE IF NOT EXISTS format_pattern (        -- canonical Swiss input patterns
    code TEXT PRIMARY KEY, regex TEXT NOT NULL, beispiel TEXT NOT NULL, beschreibung TEXT);

CREATE TABLE IF NOT EXISTS canonical_attribute (   -- one row per unique datum (derived)
    id INTEGER PRIMARY KEY,
    ech_element_id INTEGER UNIQUE REFERENCES ech_element(id),
    esh_key TEXT UNIQUE,                           -- 'eSH-xxxx:element' where eCH has none
    label TEXT NOT NULL, datatype TEXT,
    sensitive_categories TEXT,                     -- JSON rollup of observed categories
    register_source TEXT,                          -- 'einwohnerregister' where a register holds it
    n_instances INTEGER NOT NULL, n_forms INTEGER NOT NULL);

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
