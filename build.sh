#!/usr/bin/env bash
# Regenerate EVERY derived artefact from the source of truth (citygov.db).
# GitHub Pages publishes the pushed result at https://jastephan63.github.io/citygov/
#
#   init_register.py       rewrites the DERIVED data inside citygov.db: the table
#                          canonical_attribute and data_field.format_code; it
#                          also refreshes format_pattern and adds any new
#                          Dienststelle name to dienststelle (tables it needs are
#                          created if missing). It and the next two steps are the
#                          only ones that write to the DB, and only derived data
#   kennungen.py           permanent identifiers (table kennung): new objects get
#                          one, gone ones are marked «entfallen», none is ever
#                          reused or re-pointed (a rename only on evidence a
#                          re-inserted row cannot fake); refuses to mint into a
#                          missing or empty table; right after init_register.py,
#                          which renumbers canonical_attribute; staging -> validate
#                          -> swap, writes nothing when nothing changed
#   rollen.py ableiten     Parteien und Rollen (stage B1, deterministic): rewrites
#                          partei_rolle, formular_partei and datenpunkt_partei from
#                          the field layer and applies the loaded stage-B2
#                          verdicts (partei_urteil) that still fit; staging ->
#                          validate -> swap, says «unverändert» when nothing changed
#   build_datentresor.py   datentresor.db — only with --tresor (synthetic vault;
#                          needs the venv with `cryptography`, and is not
#                          byte-reproducible because of random AES-GCM nonces).
#                          Runs before export_json.py, which reads it for the
#                          Bürgersicht; it reads citygov.db only
#   export_json.py         data_export.json (base data every surface reads, one
#                          generated_at stamp for the whole build) + today's
#                          entry in verlauf.json; stops with «ABBRUCH …» and
#                          writes nothing when a layer fails, a sum does not
#                          add up or verlauf.json is unreadable. It computes the
#                          parties per data point (rollen.py), the change-impact
#                          index (wirkung.py), the concepts (konzepte.py: one
#                          preferred element per Angabe and role) and the register
#                          map with the corrected prefill count and the time rule
#                          (register_map.py) once, puts
#                          the permanent identifiers on every object and stamps
#                          the export contract (export_vertrag.py: version,
#                          schema/*.schema.json, exportvertrag.json — rewritten
#                          only when the structure or a count changed)
#   theme.py --check       the shared look (fonts, colours, tones, symbols, text
#                          sizes): every text colour reaches 4.5:1 on its
#                          backgrounds and no colour, size or font literal is
#                          left in the four page generators; reads only
#   build_flows.py         flows.html (inlines quellen/ch-geo.js; the profile prefill
#                          map is the vorbefuellbar rule of data_export.json)
#   export_llm.py          citygov_llm.json, citygov_datafields.jsonl,
#                          citygov_datarules.jsonl, citygov_verzeichnis.json,
#                          citygov_prefill.json (identifiers and contract stamp
#                          as export_json.py)
#   export_ech_schema.py   citygov_ech_schemas.json (identifiers, contract stamp)
#   build_dashboard.py     dashboard.html — after the exports above, because its page
#                          «Datenmodell» shows the version of every export as
#                          exportvertrag.json holds it once all of them are stamped
#   export_vertrag.py      checks the export contract (read-only): every published
#                          export carries the version exportvertrag.json records,
#                          matches its JSON Schema under schema/ and its counts
#   kennungen.py --pruefen every object has exactly one active identifier and every
#                          active identifier names its object (read-only)
#   export_dossiers.py     dossiers/*.html + dossiers/index.html + dossiers/_repo.js
#                          (marker: the repository is present); with --pdf also
#                          dossiers/*.pdf (local only, needs a local Chrome)
#   build_index.py         index.html — the landing page (GitHub Pages serves it at
#                          https://jastephan63.github.io/citygov/) + 404.html
#   validate_db.py         final integrity check of the database (with the gates of
#                          the identifiers, parties, law editions and registers;
#                          the register gate reads quellen/register/)
#   check_pages.mjs        opens the built pages in a headless Chrome: scripts parse,
#                          every page starts without an error, bars add up, contrast,
#                          link colour, text size, file size, keyboard; needs Node and
#                          a local Chrome and is skipped without them; a Chrome that is
#                          found but does not start fails the build (CHROME_FLAGS=
#                          --no-sandbox in a container, CHECK_PAGES=skip to build
#                          without the check on purpose) — scripts/README.md
#
#   ./build.sh             everything above except datentresor.db and the PDFs
#   ./build.sh --tresor    additionally rebuild datentresor.db
#   ./build.sh --pdf       additionally write dossiers/*.pdf; a plain build before
#                          committing drops the PDF column from dossiers/index.html
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

$PY scripts/init_register.py
# identifiers right after the canonical Angaben were rebuilt (the vault and every
# export carry them), then the parties of every data point
$PY scripts/kennungen.py
$PY scripts/rollen.py ableiten
# the vault needs canonical_attribute/format_code (init_register) and the
# identifiers of the Angaben (kennungen.py), and must exist
# before export_json.py reads it for the Bürgersicht
if [[ " $* " == *" --tresor "* ]]; then $PY scripts/build_datentresor.py; fi
$PY scripts/export_json.py
$PY scripts/theme.py --check
$PY scripts/build_flows.py
$PY scripts/export_llm.py
$PY scripts/export_ech_schema.py
# after every export has stamped its version: the page «Datenmodell» shows the export contract
$PY scripts/build_dashboard.py
$PY scripts/export_vertrag.py
$PY scripts/kennungen.py --pruefen
if [[ " $* " == *" --pdf "* ]]; then $PY scripts/export_dossiers.py --pdf; else $PY scripts/export_dossiers.py; fi
$PY scripts/build_index.py
$PY scripts/validate_db.py
ls -lh dashboard.html flows.html data_export.json citygov_llm.json | awk '{print "  " $5 "\t" $9}'
# the built pages, opened in a headless Chrome: a finding fails the build here,
# after every file has been written
if command -v node >/dev/null 2>&1; then node scripts/check_pages.mjs
else echo "Seitenprüfung übersprungen: Node oder Chrome nicht gefunden"; fi
echo "done — open dashboard.html in a browser (or: python3 -m http.server 8917)"
