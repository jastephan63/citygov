# scripts/ — how the databank is built and loaded

Everything in the repository except `citygov.db` is generated. `citygov.db` is
changed only by loaders, and every loader works the same way: copy the DB to
`citygov.db.staging`, write, run `validate_db.validate()`, and only then swap
the staging copy over the real file — a failed load changes nothing. Curated
content (a citation, a standard, a rule quote, a remedy, a topic group, a
term) never enters without its proof gate: the article must exist in the
ingested law text, the eCH element in the swept catalogue, the quote verbatim
in the official PDF.

## Rebuild every generated surface

```bash
./build.sh            # init_register → export_json → build_dashboard → build_flows →
                      # export_llm → export_ech_schema → export_dossiers → validate_db
./build.sh --tresor   # + datentresor.db (needs .venv with cryptography)
./build.sh --pdf      # + dossiers/*.pdf (needs a local Chrome)
```

## Load or refresh data (in this order)

```bash
# 1. laws (official PDFs in ../Gesetze, ../Gesetze/Bund)
python3 scripts/build_gesetze_index.py            # inventory/gesetze_index.json from the PDF folder
python3 scripts/fetch_rechtsbuch.py <SHR> ...     # fetch a cantonal law PDF from rechtsbuch.sh.ch
python3 scripts/ingest_laws.py <SHR> ...          # cantonal law + articles from the PDF index
python3 scripts/ingest_fed.py <SR> ...            # federal laws from Fedlex PDFs
python3 scripts/ingest_bigcode.py <SR> ...        # ZGB/OR/StGB-sized codes (page streaming)
python3 scripts/extract_quotes.py                 # article.text_excerpt copied from the PDFs

# 2. services and Formulare
python3 scripts/load_dvsh_harvest.py <harvest>    # DVSH modeller (read-only source of truth)
python3 scripts/load_shep.py <harvest>            # SHEP portal pages (published citizen view)
python3 scripts/classify.py forms/                # formular vs calculation_tool vs helper
python3 scripts/ingest_new.py <dir>               # new files only; never touches existing forms
python3 scripts/load_data_fields.py <dir>         # logical data dictionary per form (refuses to
                                                  # overwrite curated layers without --force)
python3 scripts/init_subfields.py                 # composite parts -> data_subfield (keeps eCH+eSH)
python3 scripts/scan_documents.py                 # PDF facts: signature, AcroForm, hash
python3 scripts/init_verfahren.py                 # Verfahren layer DDL + channel/contact harvest
python3 scripts/build_similarity.py               # Duplikat-Radar

# 3. standards
python3 scripts/load_ech_map.py <dir>             # eCH standard/element per field, catalogue-gated
python3 scripts/load_subfield_ech.py <dir> --inputs=<dir>   # per (parent, part) pair
python3 scripts/load_ech_verdicts.py <dir>        # sceptical second pass on the assignments
python3 scripts/load_ech_gaps.py <dir>
python3 scripts/propagate_ech_names.py            # consistent name-keyed verdicts -> new forms
python3 scripts/load_ech_verdicts_new.py <dir>    # verification, newest forms only
python3 scripts/load_esh.py <katalog.json> <dir>  # the cantonal DRAFT standard where eCH has nothing
python3 scripts/sweep_ech_xsd.py [--offline]      # XSD versions + code lists (files in ech_xsd/)

# 4. law layer per field, governance rules, register, Verfahren
python3 scripts/load_field_legal.py <dir>         # article citations, gated against the law text
python3 scripts/load_basis_typ.py <dir>           # aufgabe / ohne / offen for fields without an article
python3 scripts/load_subjekt.py <dir>             # whose datum (natural person / organisation / ...)
python3 scripts/load_data_rules.py <dir>          # storage/processing/disclosure rules, quotes PDF-verified
python3 scripts/init_register.py                  # derived: canonical attributes, format codes
python3 scripts/load_register.py <dir>            # purposes, recipients, Fristen (number must be in the quote)
python3 scripts/load_verfahren.py <dir>           # Beilagen + Entscheide
python3 scripts/load_rechtsmittel.py <dir>        # VRG general rule + sektoral provisions, PDF-gated
python3 scripts/load_rechtsmittel_verdicts.py <dir>   # which provision governs a form; then load_rechtsmittel.py again
python3 scripts/load_panel_reviews.py <dir>       # second opinions on basis_typ / subjekt / remedies

# 5. naming and topic groups — ONE chain, in this order only (the steps refuse to run alone)
python3 scripts/load_themenkatalog.py             # eCH-0049 catalogue, verbatim-gated against quellen/ech-0049/*.pdf
python3 scripts/run_begriffe.py <panel-base-dir>  # begriffe -> pruefart -> vorschlag_check -> konsistenz
                                                  # -> rollen -> themen -> quellen/korrekturen/*.json

# 6. currency and flows
python3 scripts/check_online.py <out>             # is our copy still the current edition? (sh.ch)
python3 scripts/load_currency.py <out> <dvsh-out>
python3 scripts/load_flows.py <flow-dir>          # guided flows, coverage-gated
python3 scripts/fill_pdf.py <form_id> <answers.json>   # write flow answers into the official PDF

# one-off, evidence-backed corrections (kept, with their reasons, under quellen/)
python3 scripts/migrate_2026_09_26.py             # idempotent; see its docstring
python3 scripts/load_rechtsmittel.py quellen/rechtsmittel           # SHR 822.101 § 8/§ 9 (Arbeitsinspektorat), quotes PDF-gated
python3 scripts/load_rechtsmittel_verdicts.py quellen/rechtsmittel  # sektoral verdicts for forms 296 and 455
python3 scripts/load_rechtsmittel.py quellen/rechtsmittel           # re-apply so form_outcome reflects the verdicts
python3 scripts/load_subfield_ech.py quellen/korrekturen/subfield_ech_form131_2026-09-26.json   # row-keyed part verdicts
python3 scripts/load_subfield_ech.py quellen/korrekturen/subfield_ech_form122_2026-09-26.json
BEGRIFFE_CHAIN=1 python3 scripts/load_korrekturen.py quellen/korrekturen/begriffe_2026-09-26.json  # last chain step, alone
```

The panel/agent output directories these loaders read are transient and are not
kept in the repository — except `quellen/rechtsmittel/`, the one kept `out_*.json`
directory, applied with the three commands above. What the panels produced is
inspectable in the DB (`data_field.derived_by`, `*.last_checked`, `panel_review`,
`begriff_vorschlag.herkunft`); the verified single corrections are in
`quellen/korrekturen/` (applied by the loaders named beside them).

## Conventions

The ten working rules every loader enforces (the DB is the only place they can
be broken, so the gate `validate_db.py` checks what it can):

1. The catalogue unit is the **service** as modelled in DVSH; Formulare are its children.
2. **The DVSH modeller and the SHEP portal are read-only sources of truth** — harvested, never written.
3. The unit of a datum is the **atomic part** (Teilfeld), never the composite field.
4. **Proof gates on every machine-written layer**: a citation must exist in an ingested article, an eCH element in the swept catalogue, an eSH code in the draft catalogue, a rule or remedy quote verbatim in the official PDF, a Frist number in that quote; loaders reject the rest.
5. **Never a citation from memory**: what is not in the ingested texts is not cited — it is marked «zu ermitteln».
6. Every citation carries its **verification level** («verified» live, «Gesetze-PDF», or unverified), taken from the article row.
7. **eSH never shadows eCH**: a draft code sits only on a unit eCH does not cover.
8. **Gaps are gaps**: «not researched» never reads as «proven»; «assessed and open» is a different state from «never assessed» (basis_typ, rechtsmittel_status).
9. **Generated files are never edited**; `citygov.db` changes only through loaders (staging → validate → swap) and `./build.sh` rebuilds everything from it.
10. **One computation per figure**: labels, Handlungsbedarf, the «same datum» key, texts and the Datenstand are computed once (`labels.py`, `export_json.py`) and read by every surface.

## What each script does

| Script | Purpose |
|---|---|
| `common.py` | Paths, `connect()`, the two shared normalisations (`norm_ascii`, `norm_label`), `pl()` |
| `labels.py` | German labels for every enumerated value — the single source for dashboard, dossiers and exports |
| `validate_db.py` | Integrity gate every loader runs on its staging copy (FKs, vocabularies, cross-layer invariants, schema.sql coverage) |
| `init_db.py` | Create an empty database from `schema.sql` |
| `export_json.py` | `data_export.json` — one computation of every derived figure (divergences, Handlungsbedarf, Lebenslagen, labels, Datenstand) |
| `build_dashboard.py` | `dashboard.html` from `data_export.json` (+ `leitfaden.py`) |
| `leitfaden.py` | The plain-German guide; the build refuses if a bullet cites a rule not in the databank |
| `build_flows.py` | `flows.html`, the guided questionnaires |
| `export_llm.py` | `citygov_llm.json` and the `citygov_*.jsonl/json` exports |
| `export_ech_schema.py` | `citygov_ech_schemas.json` — one eCH-shaped exchange schema per Formular |
| `export_dossiers.py` | `dossiers/<slug>.html` per service + index (`--pdf` for PDFs) |
| `build_datentresor.py` | `datentresor.db` — the synthetic storage example |
| `extract_law.py` | Text of a law PDF (offline), the ground truth every citation gate maps against |
| `ingest_laws.py` / `ingest_fed.py` / `ingest_bigcode.py` / `fetch_rechtsbuch.py` / `build_gesetze_index.py` / `extract_quotes.py` | The law chain (step 1 above) |
| `load_dvsh_harvest.py` / `load_shep.py` / `consolidate_services.py` / `apply_consolidation.py` / `link_dvsh_eforms.py` | Service universe from DVSH and SHEP (read-only harvests) |
| `classify.py` / `ingest_new.py` / `load_data_fields.py` / `init_subfields.py` / `recover_fields.py` / `fix_quality.py` | Formulare and their fields |
| `scan_documents.py` / `init_verfahren.py` / `load_verfahren.py` / `build_similarity.py` | Verfahren layer and Duplikat-Radar |
| `load_ech_map.py` / `load_subfield_ech.py` / `load_ech_verdicts*.py` / `load_ech_gaps.py` / `propagate_ech_names.py` / `load_esh.py` / `sweep_ech_xsd.py` | Standards |
| `load_field_legal.py` / `load_basis_typ.py` / `load_subjekt.py` / `load_data_rules.py` / `init_register.py` / `load_register.py` | Law layer per field, rules, register |
| `load_rechtsmittel.py` / `load_rechtsmittel_verdicts.py` / `load_panel_reviews.py` | Remedies and second opinions |
| `load_themenkatalog.py` / `run_begriffe.py` (+ `load_begriffe.py`, `load_pruefart.py`, `load_vorschlag_check.py`, `load_begriff_konsistenz.py`, `load_begriff_rollen.py`, `load_themen.py`, `load_korrekturen.py`) | Naming («Ein Datum, ein Name») and Themengruppen |
| `check_online.py` / `load_currency.py` | Is our copy still the current edition? |
| `load_flows.py` / `fill_pdf.py` | Guided flows and writing answers back into the official PDF |
| `commit_proposal.py` / `auto_draft.py` | The retired 2026-06 auto-draft layer (kept because `ingest_new.py` imports it; never exported) |
| `migrate_2026_09_26.py` | One-off, idempotent corrections from the 2026-09-26 quality check |
| `annotate_pdf.swift` / `ocr_pdf.swift` | macOS helpers (PDFKit / Vision OCR) used by the field-label recovery of 2026-06; not part of the build |
| `deprecated/` | Tools that did their job once and were superseded (see its README) |
