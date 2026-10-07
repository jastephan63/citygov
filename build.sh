#!/usr/bin/env bash
# Regenerate EVERY derived artefact from the source of truth (citygov.db).
# GitHub Pages publishes the pushed result at https://jastephan63.github.io/citygov/
#
#   ./build.sh             everything except datentresor.db and the PDFs
#   ./build.sh --tresor    additionally rebuild datentresor.db
#   ./build.sh --pdf       additionally write dossiers/*.pdf; a plain build before
#                          committing drops the PDF column from dossiers/index.html
#
# This file runs `python3 -m citygov build` (the same build, the same output). The
# steps, in their order, and what each one does are listed in citygov/cli.py
# (BUILD); `python3 -m citygov list` prints them: init_register.py, kennungen.py
# and rollen.py ableiten rewrite the derived data inside citygov.db (the only steps
# that write to it), then the exports and the pages with the theme, contract and
# identifier checks between them (the exact order is BUILD), validate_db.py, the
# sizes of the largest files, the tests (python3 -m unittest, tests/) and last the
# page check (node scripts/check_pages.mjs). The first step that fails stops the build with its exit
# code. The steps run with .venv/bin/python3 when it exists.
#
# Loading NEW data is a different job: the loaders under scripts/ (load_*.py,
# ingest_*.py, sweep_ech_xsd.py, run_begriffe.py, gesetz_stand.py,
# check_gesetz_stand.py, register_katalog.py, register_map.py) each write to a
# staging copy, validate and swap — see scripts/README.md for the order.
# gesetz_stand.py needs macOS PDFKit, check_gesetz_stand.py and
# register_katalog.py --abrufen the network (read-only GETs); none of the four
# is a build step.
set -euo pipefail
cd "$(dirname "$0")"
PY=python3
if [[ -x .venv/bin/python3 ]]; then PY=.venv/bin/python3; fi
# the words after «--» are read as this file always read them: only --tresor and
# --pdf count, wherever they stand, and any other word is ignored
exec "$PY" -m citygov build -- "$@"
