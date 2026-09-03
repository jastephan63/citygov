# citygov — Kanton Schaffhausen compliance databank

Machine-readable databank that, per **Formular** of the cantonal administration,
captures the **laws** that govern it (down to the article), the **data fields**
it collects, the **standards** (eCH / draft eSH) each datum maps to, and the
**guided flow** that fills it. The consumer is an LLM agent that will administer
services — so the data must be **precise, auditable, and never silently wrong**.
Surfacing gaps and over-collection honestly is the whole point; a fake
"100 % compliant" is a defect.

## The catalogue unit is the SERVICE (user decision 2026-09-03)
The primary unit is one SERVICE as modelled in DVSH; Formulare are its
children — several per service is the normal shape (34 services carry >1).
480 service rows = 313 DVSH-linked + 167 honest ours-only (domains DVSH has
not modelled: the whole SVA office, Polizei, KESB, Schulzahnklinik, much of
the Landwirtschaftsamt — never force-fitted). Formular-era rows were folded
into their DVSH service by scripts/consolidate_services.py (filename gate) +
apply_consolidation.py (agent verdicts, gated); form.dvsh_match records
every move's evidence.
`dvsh_service` holds the full modeller harvest (330 services, source of
truth), `shep_service` the published citizen view (196). A Formular keeps its
own row under its service; only the NEWEST edition of a form is kept.
474 Formulare total: file-backed ones, 32 from the DVSH asset store
(sha256-verified), and 42 file-less eFormulare built 1:1 from DVSH
formDefinitions (derived_by 'dvsh-formdefinition'); 259/330 DVSH services
carry a Formular, the other 71 are honestly channel-only (email/Telefon/
externer Link, or no file exists upstream). form.dvsh_match marks tentative
links. The dashboard's formSection has an Einzelansicht (state.sub='form-<id>')
restoring the old per-Formular page.

## The DVSH/SHEP harvest (both sites STRICTLY read-only)
* DVSH: `../DVSH/dvsh_harvest_<date>.json` — exported in the browser from the
  modeller's own tRPC GET queries (react-query client via fiber; never any
  mutation, never a click in the admin UI). Re-ingest with
  `scripts/load_dvsh_harvest.py <file>`; it refreshes dvsh_service +
  dvsh_organisation and creates service rows for new DVSH services.
* SHEP (shep.meetfrida.agency): public server-rendered pages, plain GETs.
  `scripts/load_shep.py <pages-dir>` parses the template's h2 sections into
  shep_service, matched to services via the shared DVSH slug.

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
`data_field.format_code` · `dienststelle` (ISV data-owner entity, kontakt
backfilled from DVSH) · `data_field.schutzstufe` (empty until the canton
decides — no fake defaults).
Verfahren & lifecycle (schema.sql tail): `beilage` (every demanded document,
source-traceable gate; `halter`+`fetchable` = document-level Once-Only) ·
`form_outcome` (what the Verfahren returns; Rechtsmittel columns wait for a
VRG-gated pass — VRG = law #328, SHR 172.200, fully ingested) ·
`form_similarity` (Duplikat-Radar, verdict curated by humans) · on `form`:
submission_channel, signature_requirement (+evidence from the PDF scan),
acroform, parse_error, file_hash, and computed-at-export burden/blockers.
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
python3 scripts/scan_documents.py            # PDF facts: signature, AcroForm, hash
python3 scripts/init_verfahren.py            # Verfahren DDL + channel/contact harvest
python3 scripts/build_similarity.py          # Duplikat-Radar (verdicts curated)
python3 scripts/load_verfahren.py <dir>      # Beilagen + Entscheide, gated
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
* **dashboard.html** — compliance view, redesigned 2026-09 for peer readers:
  grouped navigation (Einstieg / Nachschlagewerke / Steuerung) with question
  subtitles, hash-router (#tab/service/sub — links are shareable), contextual
  legend, and a `pageHead()` on every corpus page stating what the page shows,
  where the data comes from, and what is verified vs curated vs derived.
  Tabs: **Überblick & Methode** (landing: methodology box — proof gates,
  verification levels, Lücke=Lücke — plus KPI tiles and the per-department
  documentation state, computed on the curated layer) · **Formular-Seite**
  (the hub: hub head with Ampel/blockers, channel, signature fact, Bürgerlast
  incl. prefillable count, Verfahrens-Ergebnis, contact; segments «Datenfelder
  & Handhabung» and «Gesetze» — the former Gesetzes-Baum/Geforderte
  Informationen tabs live here now; panels for Beilagen (halter + Once-Only),
  Digitalisierungs-Blocker, Datenhandhabung-Profil, Duplikat-Radar) ·
  **Datenhandhabung** (rule corpus, sektoral cards carry «gilt für N
  Formulare» back-links) · **Leitfaden** (chips jump to the concrete rule
  card) · **Verzeichnis** · **Datenkatalog** (rows expand to the collecting
  forms) · **eSH-Katalog**. Legacy viewRecon code was removed; the overview
  bars run on the curated data_field layer and are labelled as documentation
  state, never as legality. Sidebar search also matches data-field names.
  Note: ~29 MB — serve via `.claude/launch.json` (`citygov-static`) if a
  preview pane balks.
* **flows.html** — guided-flow view (paper/gold design from ../formflows
  prototypes). Per Formular: data field ↔ derived question mapping and an
  «Ausprobieren» player with help drawer, once-only profile prefill keyed by
  eCH element, and eCH-JSON export.

## Git
Every meaningful change is a commit. Never amend or rebase — history is the
audit trail. Generated artifacts are committed so examples open from the repo.
