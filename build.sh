#!/usr/bin/env bash
# Regenerate EVERY derived artefact from the source of truth (citygov.db):
#
#   init_register.py       rewrites the DERIVED tables inside citygov.db
#                          (canonical_attribute, data_field.format_code) — the
#                          only step that writes to the DB, and only derived data
#   export_json.py         data_export.json  (base data every surface reads)
#   build_dashboard.py     dashboard.html
#   build_flows.py         flows.html
#   export_llm.py          citygov_llm.json, citygov_datafields.jsonl,
#                          citygov_datarules.jsonl, citygov_verzeichnis.json,
#                          citygov_prefill.json
#   export_ech_schema.py   citygov_ech_schemas.json
#   export_dossiers.py     dossiers/*.html + dossiers/index.html
#   validate_db.py         final integrity check of the database
#
#   ./build.sh             everything above
#   ./build.sh --tresor    additionally rebuild datentresor.db (synthetic vault;
#                          needs the venv with `cryptography`, and is not
#                          byte-reproducible because of random AES-GCM nonces)
#   ./build.sh --pdf       additionally write dossiers/*.pdf (needs a local Chrome)
#
# Loading NEW data is a different job: the loaders under scripts/ (load_*.py,
# ingest_*.py, sweep_ech_xsd.py, run_begriffe.py) each write to a staging copy,
# validate and swap — see scripts/README.md for the order.
set -euo pipefail
cd "$(dirname "$0")"
PY=python3
if [[ -x .venv/bin/python3 ]]; then PY=.venv/bin/python3; fi

$PY scripts/init_register.py
$PY scripts/export_json.py
$PY scripts/build_dashboard.py
$PY scripts/build_flows.py
$PY scripts/export_llm.py
$PY scripts/export_ech_schema.py
if [[ " $* " == *" --tresor "* ]]; then $PY scripts/build_datentresor.py; fi
if [[ " $* " == *" --pdf "* ]]; then $PY scripts/export_dossiers.py --pdf; else $PY scripts/export_dossiers.py; fi
$PY scripts/validate_db.py
ls -lh dashboard.html flows.html data_export.json citygov_llm.json | awk '{print "  " $5 "\t" $9}'
echo "done — open dashboard.html in a browser (or: python3 -m http.server 8917)"
