#!/usr/bin/env bash
# Regenerate EVERY derived artefact from the source of truth (citygov.db).
# GitHub Pages publishes the pushed result at https://jastephan63.github.io/citygov/
#
#   init_register.py       rewrites the DERIVED data inside citygov.db: the table
#                          canonical_attribute and data_field.format_code; it
#                          also refreshes format_pattern and adds any new
#                          Dienststelle name to dienststelle (tables it needs are
#                          created if missing) — the only step that writes to the
#                          DB, and only derived or seed data
#   build_datentresor.py   datentresor.db — only with --tresor (synthetic vault;
#                          needs the venv with `cryptography`, and is not
#                          byte-reproducible because of random AES-GCM nonces).
#                          Runs before export_json.py, which reads it for the
#                          Bürgersicht; it reads citygov.db only
#   export_json.py         data_export.json (base data every surface reads, one
#                          generated_at stamp for the whole build) + today's
#                          entry in verlauf.json
#   build_dashboard.py     dashboard.html
#   build_flows.py         flows.html (inlines quellen/ch-geo.js)
#   export_llm.py          citygov_llm.json, citygov_datafields.jsonl,
#                          citygov_datarules.jsonl, citygov_verzeichnis.json,
#                          citygov_prefill.json
#   export_ech_schema.py   citygov_ech_schemas.json
#   export_dossiers.py     dossiers/*.html + dossiers/index.html + dossiers/_repo.js
#                          (marker: the repository is present); with --pdf also
#                          dossiers/*.pdf (local only, needs a local Chrome)
#   build_index.py         index.html — the landing page (GitHub Pages serves it at
#                          https://jastephan63.github.io/citygov/) + 404.html
#   validate_db.py         final integrity check of the database
#
#   ./build.sh             everything above except datentresor.db and the PDFs
#   ./build.sh --tresor    additionally rebuild datentresor.db
#   ./build.sh --pdf       additionally write dossiers/*.pdf; a plain build before
#                          committing drops the PDF column from dossiers/index.html
#
# Loading NEW data is a different job: the loaders under scripts/ (load_*.py,
# ingest_*.py, sweep_ech_xsd.py, run_begriffe.py) each write to a staging copy,
# validate and swap — see scripts/README.md for the order.
set -euo pipefail
cd "$(dirname "$0")"
PY=python3
if [[ -x .venv/bin/python3 ]]; then PY=.venv/bin/python3; fi

$PY scripts/init_register.py
# the vault needs canonical_attribute/format_code (init_register) and must exist
# before export_json.py reads it for the Bürgersicht
if [[ " $* " == *" --tresor "* ]]; then $PY scripts/build_datentresor.py; fi
$PY scripts/export_json.py
$PY scripts/build_dashboard.py
$PY scripts/build_flows.py
$PY scripts/export_llm.py
$PY scripts/export_ech_schema.py
if [[ " $* " == *" --pdf "* ]]; then $PY scripts/export_dossiers.py --pdf; else $PY scripts/export_dossiers.py; fi
$PY scripts/build_index.py
$PY scripts/validate_db.py
ls -lh dashboard.html flows.html data_export.json citygov_llm.json | awk '{print "  " $5 "\t" $9}'
echo "done — open dashboard.html in a browser (or: python3 -m http.server 8917)"
