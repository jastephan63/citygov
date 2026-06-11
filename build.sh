#!/usr/bin/env bash
# Regenerate the derived artifacts (data_export.json + dashboard.html) from the
# source of truth (citygov.db). Safe to run any time; never edits the DB.
#
#   ./build.sh
#
# To (re)load data, run the ingestion steps first — see CLAUDE.md:
#   python3 scripts/init_db.py            # once (or --force to reset)
#   python3 scripts/commit_proposal.py proposals/<service>.json
#   ./build.sh
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/export_json.py
python3 scripts/build_dashboard.py
echo "done — open dashboard.html in a browser"
