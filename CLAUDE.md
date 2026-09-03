# citygov — Kanton Schaffhausen compliance databank

Machine-readable databank that, per **Formular** of the cantonal administration,
captures the **laws** that govern it (down to the article), the **data fields**
it collects, the **standards** (eCH / draft eSH) each datum maps to, and the
**guided flow** that fills it. The consumer is an LLM agent that will administer
services — so the data must be **precise, auditable, and never silently wrong**.
Surfacing gaps and over-collection honestly is the whole point; a fake
"100 % compliant" is a defect.

## The catalogue unit is ONE Formular
One row = one Formular with its own name (never collapsed into DVSH services;
user decision). Current shape: ~400 Formulare + ~129 DVSH eService entries
without a downloadable form. Only the NEWEST edition of a form is kept — dated
older versions get deleted once the current file is in the collection.

## Non-negotiable conventions (from real prior failures — do not relax)
1. **Form content beats form title.** Decide what a form is by reading its
   actual fields, not its title. Record mismatches on `form.title_content_mismatch`.
2. **Only the newest edition.** Same form in two year-stamps → keep the newer
   file; if the older entry was better modelled, migrate its field set first
   (`scripts/recover_fields.py`), then delete.
3. **Never type a citation from memory.** Real Art./§ come from the actual law
   text (cantonal PDFs in `../Gesetze/`, read with `scripts/extract_law.py`;
   `scripts/fetch_rechtsbuch.py <SSR>` fetches any cantonal law). Verification
   levels in `last_checked`: `verified` / `Gesetze-PDF <SHR> (Stand …)` /
   `UNVERIFIED`. Never guess an SR number.
4. **Proof gates on every agent-written layer.** A citation must exist in an
   ingested article; an eCH element must exist in the swept catalogue; a flow
   must cover every data field or excuse it; an eSH code must exist in the
   draft catalogue. Loaders reject everything else — no invented references
   can enter the DB.
5. **DVSH is authoritative for legal bases and READ-ONLY.** Never change
   anything in the modeller. Its asset store and full service JSON are
   reachable via GETs the SPA itself makes (see memory: tRPC
   `admin.services.get`, `/api/service-asset/<id>/<sha256>`).
6. **The atomic unit for standards is the subfield.** "Personalien" is a
   composite; Name/Vorname/Geburtsdatum each carry their OWN eCH element
   (`data_subfield`). Never settle for a container-level badge when parts exist.
7. **eSH never shadows eCH.** The draft cantonal standard (`esh_standard`,
   25 entries) applies only where `ech_status='kein_standard'`, and every
   surface labels it "Entwurf".
8. **`no_basis=1` means "no law demands this"** (over-collection; flows render
   it as a voluntary question). A field whose basis sits in a NOT-yet-ingested
   law is NOT `no_basis` — that would offer legally required data as optional.
9. **One source of truth = `citygov.db`.** `data_export.json`, `dashboard.html`,
   `flows.html`, `citygov_llm.json`, `citygov_fields.jsonl`,
   `citygov_datafields.jsonl` are GENERATED — regenerate, never hand-edit.
10. **Idempotent, validated, copy-then-swap writes.** Every loader works on
   `citygov.db.staging`, validates (`scripts/validate_db.py`), then atomically
   swaps. On failure it aborts and leaves the DB untouched.

## Schema (see `schema.sql`)
Core: `service` · `form` · `data_field` (logical fields incl. `ech_*`, `esh_*`,
`no_basis`, `sensitive`) · `data_subfield` (atomic parts with their own eCH/eSH)
· `data_field_legal_basis` · `law` · `article`.
Standards: `ech_standard` (290 real standards incl. approval `status` — some are
drafts/repealed!) · `ech_element` (9.7k elements from the official XSDs) ·
`esh_standard` (25 draft cantonal standards).
Governance: `data_rule` — how data may be stored, treated and communicated, one
rule per (article, aspect); every quote is mechanically verified against the
official law PDF by `scripts/load_data_rules.py`. `law.governance=1` marks the
8 core laws (KDSG/KDSV/ISV/ArchivV + DSG/DSV/BGA/EMBAG). Scope semantics:
`allgemein` = every personal-data field, `besonders_schuetzenswert` = fields
with a `sensitive` category, `sektoral` = fields of forms citing the same law.
Data management (see schema.sql tail): `retention_term` (machine-readable Frist
per retention rule — duration gate: the number must appear in the rule's quote)
· `retention_decision` (cantonal Fristentscheid, never mixed with law) ·
`form_disclosure` (recipients per form, article-backed) · `form.purpose` /
`dsfa_status` · `canonical_attribute` (one row per unique datum, derived;
`register_source` marks Einwohnerregister data) · `format_pattern` +
`data_field.format_code` · `dienststelle` (ISV data-owner entity) ·
`data_field.schutzstufe` (empty until the canton decides — no fake defaults).
Integrations: `dvsh_service` (READ-ONLY harvest of the modeller) · `form_check`
(online currency verdict per form) · `formflow` (guided TurboTax-style flow per
form, with `form_hash` staleness tracking) · `document` (file inventory).
Legacy (auto-draft era, still present): `requirement`, `requirement_legal_basis`,
`service_requirement`, `form_field`, `field_mapping`.

## Operating loop
```
# add or refresh a Formular
python3 scripts/classify.py forms/           # formular vs calculation_tool vs helper
python3 scripts/ingest_new.py <dir>          # new files only (auto_draft would clobber curated titles)
python3 scripts/load_data_fields.py <dir>    # agent-derived logical data dictionary
python3 scripts/init_subfields.py            # promote composite parts to data_subfield
# standards + law layers (agent output -> proof-gated loaders)
python3 scripts/load_ech_map.py / load_subfield_ech.py / load_ech_verdicts.py / load_ech_gaps.py
python3 scripts/load_esh.py <katalog.json> <assign-dir>
python3 scripts/load_field_legal.py <dir>    # article citations, gate-checked against law text
python3 scripts/load_data_rules.py <dir>     # governance rules, quotes PDF-verified
python3 scripts/init_register.py             # register layer schema + derived seeds
python3 scripts/load_register.py <dir>       # purposes/recipients/Fristen, gated
python3 scripts/export_ech_schema.py         # eCH exchange schema per Formular
# currency sweep (is our copy still the current edition?)
python3 scripts/check_online.py <out>        # sh.ch CMS search + byte-compare
python3 scripts/load_currency.py <out> <dvsh-out>
# guided flows (second dashboard)
python3 scripts/load_flows.py <flow-dir>     # coverage-gated
python3 scripts/build_flows.py               # -> flows.html
# rebuild everything
./build.sh                                   # export_json.py + build_dashboard.py
python3 scripts/export_llm.py                # LLM-ready exports
# fill the official PDF from answers
python3 scripts/fill_pdf.py <form_id> <answers.json>
```

## The two dashboards (both self-contained, open via file://)
* **dashboard.html** — compliance view. Sidebar of all Formulare (full titles),
  six tabs: Felder & Rechtsgrundlagen (data fields with eCH/eSH badges, DSG
  flags, law quotes, currency badge, DVSH panel, per-Formular Datenhandhabung
  panel) · Gesetzes-Baum · Geforderte Informationen · Datenhandhabung (the full
  rule corpus by scope and law) · Leitfaden (plain-language guide; content in
  `scripts/leitfaden.py`, every claim ref-gated against data_rule at build time
  and adversarially reviewed against the rule quotes) · Verzeichnis (register
  of processing activities per KDSG Art. 17b: completeness counters, DSFA
  triage, Dienststellen risk heatmap, one register row per Formular) ·
  Datenkatalog (canonical attributes, Once-Only potential, requiredness/format
  divergences, exchange pilot list) · eSH-Katalog (Entwurf).
  Note: ~29 MB — serve via `.claude/launch.json` (`citygov-static`) if a
  preview pane balks.
* **flows.html** — guided-flow view (paper/gold design from ../formflows
  prototypes). Per Formular: data field ↔ derived question mapping and an
  «Ausprobieren» player with help drawer, once-only profile prefill keyed by
  eCH element, and eCH-JSON export.

## Git
Every meaningful change is a commit. Never amend or rebase — history is the
audit trail. Generated artifacts are committed so examples open from the repo.
