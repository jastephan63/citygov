# scripts/ — how the databank is built and loaded

`citygov.db` is the only data source. `./build.sh` regenerates every file it
lists from it (its first step, `init_register.py`, rewrites only derived data
inside the DB); `verlauf.json` keeps one snapshot per build day. The code, the
schema and `quellen/` are maintained by hand. `formulare/` (`ingest_new.py`),
`ech_xsd/` (`sweep_ech_xsd.py`) and `inventory/` (`build_gesetze_index.py`,
`fetch_rechtsbuch.py`) are inputs written by loaders, never by `./build.sh`.
`citygov.db` is changed only by loaders, and every loader works the same way:
copy the DB to `citygov.db.staging`, write, run `validate_db.validate()`, and
only then swap the staging copy over the real file — a failed loader step
leaves `citygov.db` as it was before that step. `run_begriffe.py` runs several
such steps, each swapped on its own: when a later one fails, the earlier ones
stay applied, so rerun the whole chain. `sweep_ech_xsd.py` keeps the XSD files
it downloaded even when its database write fails. Curated
content (a citation, a standard, a rule quote, a remedy, a topic group, a
term) never enters without its proof gate: the article must exist in the
ingested law text, the eCH element in the swept catalogue, the quote verbatim
in the official PDF.

## Rebuild every generated surface

```bash
./build.sh            # init_register → export_json → theme --check → build_dashboard → build_flows
                      # → export_llm → export_ech_schema → export_dossiers → build_index → validate_db
                      # → check_pages (page check; skipped without Node or Chrome)
./build.sh --tresor   # + build_datentresor right after init_register, before export_json reads the
                      #   vault for the Bürgersicht (needs .venv with cryptography)
./build.sh --pdf      # + dossiers/*.pdf (needs Google Chrome in /Applications; local only, ignored by Git)
```

The build reads nothing outside the repository: `build_flows.py` inlines
`quellen/ch-geo.js` and stops when it is missing, and `export_json.py`,
`export_llm.py`, `export_ech_schema.py` and `build_flows.py` refuse to write
a text that names a local path (`common.assert_no_local_paths`).

`export_json.py` also computes the comparison of the Gestaltung: it imports
`gestaltung_export.py` (standard library only; of the measuring modules it
imports only `gestaltung_text.py`, so the build needs no pypdf), which reads
the stored measurement in `form_gestaltung` and holds every Formular against
the practice of the others. The measurement itself (`scan_gestaltung.py`) is
a loader and never a step of the build: a Formular with a file but without a
row is shown as «noch nicht gemessen», and a row whose profile lacks what
method `gestaltung-2` measures stops the export.

Every step stops the chain rather than write something wrong (`set -e`):
`export_json.py` ends with «ABBRUCH export_json.py — nichts geschrieben» and
leaves `data_export.json` and `verlauf.json` untouched when a layer fails (a
missing column, a failing helper, a wording gate), a sum does not add up, one
of the Gestaltung's own invariants fails (`gestaltung_export.pruefen()`) or
`verlauf.json` is unreadable — only a table that `schema.sql` declares and
that is genuinely missing is skipped, loudly, and listed in
`datenstand.uebersprungen`; `theme.py --check` stops on a colour pair below
4.5:1 or a colour, size or font literal in one of the four page generators;
`build_dashboard.py` stops with «ABORT — data_export.json fehlt, was die Seite
ohne eigene Berechnung liest» on an export that lacks a key the page reads
without computing it (`kopfzahlen.standard_ech.ech_ton`,
`standard_benannt.teile`, `kein_standard`, `kategorien`, `verzeichnis.teile`,
`labels.kontakt`, `forms[].dienststelle`, `forms[].standard` (the data-standard
figures of one Formular on the atomic unit — its header), `data_fields[].ech_state` /
`basis_state`, `services[].dossier_slug`, `gestaltung` with its `bestand` and
`labels`, `forms[].gestaltung`); `export_dossiers.py` and
`export_llm.py` stop the same way on an export without `ech_state` /
`basis_state`; `build_flows.py` stops when `quellen/ch-geo.js` is missing or
holds a «<» (it is inlined as script text and cannot be escaped). The page
check at the end fails the build after every file has been written.

## The automatic page check

`scripts/check_pages.mjs` is the last step of `./build.sh`. It opens the built
pages of the repository root in a local headless Chrome (Node, no npm package;
the browser is driven through a pipe and cannot reach the network) and fails
the build with one plain message per finding. Without Node or Chrome it prints
«Seitenprüfung übersprungen: Node oder Chrome nicht gefunden» and the build
goes on; a Chrome that is found but does not start (a crash, a sandbox refusal
in a container) is a finding — «Seitenprüfung fehlgeschlagen: …» names the
cause and the build stops, because no page was checked. `CHROME_FLAGS=--no-sandbox`
is the usual cure in a container; `CHECK_PAGES=skip` builds without the check
on purpose and says so. It takes three to ten seconds.

```bash
node scripts/check_pages.mjs                   # every check
node scripts/check_pages.mjs --only kontrast   # one check (several: --only summen,links)
node scripts/check_pages.mjs --verbose         # every measured value and every finding
node scripts/check_pages.mjs --root <dir>      # the pages of another directory (a copy, an older build)
node scripts/check_pages.mjs --breite 1024     # a window of 1024 px instead of 1280 (the dashboard
                                               # changes its table layout at 1340 and 700 px)
```

| Check | Fails when |
|---|---|
| `syntax` | an inline script of `dashboard.html` or `flows.html` does not parse, the inlined data is not valid JSON, or a `</script>` is missing (file cut off) |
| `seiten` | a page of the dashboard or another document (`index.html`, `flows.html`, `404.html`, `dossiers/index.html`, the largest and the smallest dossier) does not start, shows too little text, «Unbekannte Seite» or an error message, writes an error to the console, asks another host for anything, shows a program word («undefined», «NaN», «[object Object]») in its text — not counted inside a verbatim quote marked `data-wortlaut` (the remarks of the measurement of a Formular, which may quote a placeholder found in the file) — or the navigation offers a page that is not in the list |
| `summen` | the segments of a bar, the numbers of its legend and the total its card states do not agree; or the numbers (`.sumn`) of a list that states its total (`.sumbox`) do not add up to its one total (`.sumtot`), column by column where a table pairs them by `data-s` — the value lists, finding counts and the Dienststellen table of the Gestaltung (Abweichungen and Lücken apart) |
| `kontrast` | a text colour has less than 4.5:1 against its background (3:1 for large text, WCAG 2.1 AA); measured on the pages marked `contrast: true`, in `flows.html` and in the largest dossier |
| `links` | a link has no colour rule and is drawn in the browser's default blue |
| `schrift` | visible text is smaller than 12 px (`sup`/`sub` excepted; text in an SVG counts at its drawn size) |
| `groesse` | `dashboard.html` reaches 95 MiB — GitHub refuses files over 100 MB, so the push would fail; from 50 MiB GitHub only warns, which the check reports as information |
| `tastatur` | something reacts to a click but is neither a native control nor has a `tabindex`, and holds no such element |

**A new page of the dashboard must be added to the constant `PAGES` at the
top of the file** — the check fails when the navigation offers a page that is
not listed there; `contrast: true` also measures its colours, and `open: true`
opens every folded part of the page and presses every «weitere …» / «alle …
zeigen» button first, so that text a reader can unfold is measured too. A
list that states its total belongs in a `.sumbox` so that the check adds it
up (several columns of one table: each `.sumn` and its `.sumtot` carry the
same `data-s`). For the Gestaltung the list holds `gestaltung` (colours
measured, everything unfolded), the section address `gestaltung/all/grenzen`
(the limits of the measurement, unfolded; colours measured) and the Formular
view `fields/116/form-116~gest` with its panel «Gestaltung» open (colours
measured, everything unfolded). The limits
(`MIN_TEXT`, `TEXT_FLOOR_PX`, `MAX_DASHBOARD_MIB`, the 1280 × 900 window) are
constants beside it. Chrome is looked up in the usual places;
`CHROME=/path/to/chrome` overrides. Not seen by the check: text drawn by CSS
(`::before`), text on a picture or gradient and the colours of text inside an
SVG (both counted, see `--verbose`), and whatever appears only after a click
(an opened explanation, the steps of a guided form).

## Load or refresh data (in this order)

The loaders read the canton's source folders next to the repository
(`../Gesetze`, `../Verwaltung`, `../DVSH`), which are not part of it. Text
extraction from law PDFs (`extract_law.py`) and from Word files needs macOS.
`scan_gestaltung.py` reads the Formular files from `formulare/` only and needs no macOS.

```bash
# 1. laws (official PDFs in ../Gesetze, ../Gesetze/Bund; text extraction needs macOS)
python3 scripts/build_gesetze_index.py            # inventory/gesetze_index.json from the PDF folder
python3 scripts/fetch_rechtsbuch.py <SHR> ...     # fetch a cantonal law PDF from rechtsbuch.sh.ch
python3 scripts/ingest_laws.py <SHR> ... [--out <dir>]                       # cantonal law + articles from the PDF index
python3 scripts/ingest_fed.py <SR>=<pdf>=<title>=<short> ... [--out <dir>]   # federal laws from Fedlex PDFs
python3 scripts/ingest_bigcode.py <SR>=<pdf>=<title>=<short> ... [--out <dir>]   # ZGB/OR/StGB-sized codes (page streaming)
python3 scripts/extract_quotes.py ../Gesetze/Bund # article.text_excerpt for every cited article (federal PDFs in
                                                  # <dir>, cantonal via inventory/gesetze_index.json from ../Gesetze)

# 2. services and Formulare
python3 scripts/load_dvsh_harvest.py ../DVSH/dvsh_harvest_<date>.json   # DVSH modeller (read-only source of truth)
python3 scripts/load_shep.py <pages-dir>          # SHEP portal pages (published citizen view)
python3 scripts/classify.py "../Verwaltung/<Departement>/<Amt>"   # formular vs calculation_tool vs helper
python3 scripts/ingest_new.py <names.json>        # new files only (JSON list of names under ../Verwaltung);
                                                  # copies each into formulare/, never touches existing forms
python3 scripts/consolidate_services.py           # stage 1: fold Formular-era service rows into their DVSH service
                                                  # (filename gate)
python3 scripts/apply_consolidation.py <dir-with-cons_out_*.json>   # stage 2: gated verdicts for the ambiguous rest
python3 scripts/link_dvsh_eforms.py               # eFormulare from DVSH form definitions; tentative title matches marked
python3 scripts/load_data_fields.py <dir>         # logical data dictionary per form (refuses to
                                                  # overwrite curated layers without --force)
python3 scripts/init_subfields.py                 # composite parts -> data_subfield (keeps eCH+eSH)
python3 scripts/scan_documents.py                 # PDF facts: signature, AcroForm, hash; needs pypdf
python3 scripts/scan_gestaltung.py [--only <form_id> ...] [--dry]   # how each Formular looks: fonts, sizes, colours,
                                                  # accessibility facts of the file, printed phone numbers, edition mark
                                                  # -> form_gestaltung, method gestaltung-2. After scan_documents.py (a
                                                  # row is tied to form.file_hash; scan_documents.py removes the row of
                                                  # a file that changed). Needs pypdf: run it with a Python that has
                                                  # it; without one the script refuses to start, and the self-tests of
                                                  # the measuring modules, run first, stop the scan when a pypdf other
                                                  # than 6.13 reads a PDF differently. Idempotent: writes only rows
                                                  # that differ, and «nichts zu tun» leaves citygov.db untouched;
                                                  # --dry prints the rows as JSON and writes nothing. Not part of
                                                  # ./build.sh
python3 scripts/init_verfahren.py                 # Verfahren layer DDL + channel/contact harvest
python3 scripts/build_similarity.py               # Duplikat-Radar

# 3. standards
python3 scripts/load_ech_map.py <dir> ...         # eCH standard/element per field, catalogue-gated
python3 scripts/load_subfield_ech.py <dir|file.json> [--inputs=<dir>]   # per (parent, part) pair
python3 scripts/load_ech_verdicts.py <dir>        # sceptical second pass on the assignments
python3 scripts/load_ech_gaps.py <dir>
python3 scripts/propagate_ech_names.py            # consistent name-keyed verdicts -> new forms (ech_herkunft 'propagiert')
python3 scripts/load_ech_verdicts_new.py <dir> [--from=<form_id>]   # verification, newest forms only
python3 scripts/load_esh.py <katalog.json> <dir>  # the cantonal DRAFT standard where eCH has nothing
python3 scripts/sweep_ech_xsd.py [--offline]      # XSD versions + code lists (files in ech_xsd/)

# 4. law layer per field, governance rules, register, Verfahren
python3 scripts/load_field_legal.py <dir>         # article citations, gated against the law text
python3 scripts/load_basis_typ.py <dir>           # aufgabe / ohne / offen for fields without an article
python3 scripts/load_subjekt.py <dir>             # whose datum (natural person / organisation / ...)
python3 scripts/load_data_rules.py <dir> ...      # storage/processing/disclosure rules, quotes PDF-verified
python3 scripts/init_register.py                  # derived: canonical attributes, format codes
python3 scripts/load_register.py <dir>            # purposes, recipients, Fristen (number must be in the quote)
python3 scripts/load_verfahren.py <dir>           # Beilagen + Entscheide
python3 scripts/load_rechtsmittel.py [<dir>]      # VRG general rule + sektoral provisions, PDF-gated
python3 scripts/load_rechtsmittel_verdicts.py <dir>   # which provision governs a form; then load_rechtsmittel.py again
python3 scripts/load_panel_reviews.py <dir>       # second opinions on basis_typ / subjekt / remedies
                                                  # (<dir> holds basis/ subjekt/ rmrules/ rmverdicts/)

# 5. naming and topic groups — ONE chain, in this order only (the steps refuse to run alone)
python3 scripts/load_themenkatalog.py             # eCH-0049 catalogue, verbatim-gated against quellen/ech-0049/*.pdf
python3 scripts/run_begriffe.py <panel-base-dir>  # begriffe -> pruefart -> vorschlag_check -> konsistenz
                                                  # -> rollen -> themen -> the quellen/korrekturen/ files that
                                                  # carry naming keys (today begriffe*.json)
                                                  # -> apply_wortwahl.py (reader wording, see below)

# 6. currency and flows
python3 scripts/check_online.py <out> [--limit N] # is our copy still the current edition? (sh.ch)
python3 scripts/load_currency.py <out> <dvsh-out> [--only-found]   # --only-found: CMS-only re-check, writes only
                                                  # «aktuell»/«aktualisiert», never downgrades a row
python3 scripts/load_flows.py <flow-dir> ...      # guided flows, coverage-gated
python3 scripts/fill_pdf.py <form_id> <answers.json>   # write flow answers into the official PDF

# evidence-backed corrections (evidence under quellen/ or in the script's docstring)
python3 scripts/migrate_2026_09_26.py             # idempotent; see its docstring
python3 scripts/migrate_2026_09_27.py             # services that bundled several DVSH services, split or renamed
                                                  # (quellen/korrekturen/dvsh_aufteilung_2026-09-27.json); again after run_begriffe.py
python3 scripts/migrate_2026_10_01.py             # idempotent clean-up of 2026-10-01; see its docstring
python3 scripts/apply_wortwahl.py                 # «Angabe», not «Datum», where the databank means a piece of data
                                                  # (quellen/wortwahl_datum.json, reviewed per text); idempotent
python3 scripts/load_rechtsmittel.py quellen/rechtsmittel           # SHR 822.101 § 8/§ 9 (Arbeitsinspektorat), quotes PDF-gated
python3 scripts/load_rechtsmittel_verdicts.py quellen/rechtsmittel  # sektoral verdicts for forms 296 and 455
python3 scripts/load_rechtsmittel.py quellen/rechtsmittel           # re-apply so form_outcome reflects the verdicts
python3 scripts/load_subfield_ech.py quellen/korrekturen/subfield_ech_form131_2026-09-26.json   # row-keyed part verdicts
python3 scripts/load_subfield_ech.py quellen/korrekturen/subfield_ech_form122_2026-09-26.json
BEGRIFFE_CHAIN=1 python3 scripts/load_korrekturen.py quellen/korrekturen/begriffe_2026-09-26.json  # the korrektur step alone
                                                  # (run apply_wortwahl.py after it)
```

The panel output directories these loaders read are transient and are not
kept in the repository — except `quellen/rechtsmittel/`, the one kept `out_*.json`
directory, applied with the three commands above. What the panels produced is
inspectable in the DB (`data_field.derived_by`, `*.last_checked`, `panel_review`,
`begriff_vorschlag.herkunft`); the verified single corrections are in
`quellen/korrekturen/` (applied by the loaders named beside them;
`quellen/README.md` lists which script reads which file).

## Conventions

The ten working rules every loader enforces (the DB is the only place they can
be broken, so the gate `validate_db.py` checks what it can):

1. The catalogue unit is the **service** as modelled in DVSH — one row per DVSH service with its own file or procedure (same-file bundles stay one row, named from DVSH wording); services DVSH has not modelled keep their own row (`in_dvsh=0`); Formulare are its children.
2. **The DVSH modeller and the SHEP portal are read-only sources of truth** — harvested, never written.
3. The unit of a datum is the **atomic part** (Teilfeld), never the composite field.
4. **Proof gates on every machine-written layer**: a citation must exist in an ingested article, an eCH element in the swept catalogue, an eSH code in the draft catalogue, a rule or remedy quote verbatim in the official PDF, a Frist number in that quote; loaders reject the rest.
5. **Never a citation from memory**: what is not in the ingested texts is not cited — it is marked «zu ermitteln».
6. Every citation carries its **verification level**, taken from the article row: «verified» (a federal article read from the official Fedlex text when the law was ingested), «Gesetze-PDF» (read from the official law PDF; for cantonal law the Schaffhauser Rechtsbuch) or unverified.
7. **eSH never shadows eCH**: a draft code sits only on a unit eCH does not cover.
8. **Gaps are gaps**: «not researched» never reads as «proven»; «assessed and open» is a different state from «never assessed» (basis_typ, rechtsmittel_status).
9. **Generated files are never edited**; `citygov.db` changes only through loaders (staging → validate → swap) and `./build.sh` rebuilds everything from it.
10. **One computation per figure**: labels, Handlungsbedarf, the «same datum» key, the eCH and legal-basis state of every data point, texts, the Datenstand and the verdicts of the Gestaltung are computed once (`labels.py`, `export_json.py`, `gestaltung_export.py`) and read by every surface; the look of every page (fonts, colours, tones, symbols, text sizes) is defined once in `theme.py`.

## What each script does

| Script | Purpose |
|---|---|
| `common.py` | Paths, `connect()`, the shared normalisations (`norm_ascii`, `norm_label`, and `klartext()`, the display form `apply_wortwahl.py` compares against), `pl()`, the local-path guard `assert_no_local_paths()` the exporters run on their output, and `size_txt()` / `net_size_txt()` (the page sizes the dashboard and the start page state) |
| `labels.py` | German labels for every enumerated value, the four status tones (who acts next), the priority tiers and the words of the contact line (`KONTAKT`: «Kontakt (laut DVSH)», «Tel.», «E-Mail», «nicht hinterlegt») — the single source for dashboard, guided forms, dossiers and exports |
| `theme.py` | The shared look: fonts (system fonts only), colours, the four tones with their tints and symbols, the eSH violet, the six text sizes (12–28 px on screen, 9–20 pt on paper). The four page generators write their `:root` block from it (`css_root()`) and use only `var(--…)`; `python3 scripts/theme.py` prints tokens, contrast table and findings, `--check` (a step of `./build.sh`) exits 1 on a text colour below 4.5:1 on one of its backgrounds, on a colour, size or font literal left in a generator — a hex, `rgb()`/`hsl()` or named colour (also `%23…` in a data URI and `el.style.color=`), a font size in px/pt/em/rem/% (also `el.style.fontSize=`), a font family — (a literal kept on purpose carries `theme:keep` and its reason in the same line) or on tone names that differ from `labels.TON` |
| `validate_db.py` | Integrity gate every loader runs on its staging copy (FKs, vocabularies, cross-layer invariants, schema.sql coverage of tables, columns and indices, every `form.source_file` an existing file under `formulare/` with a matching `file_type`, every `form_gestaltung` row measured on the current file and equal to its own profile) |
| `check_pages.mjs` | The automatic page check at the end of `./build.sh`: opens the built pages in a headless Chrome and fails with one message per finding (see «The automatic page check») |
| `init_db.py` | Create an empty database from `schema.sql` |
| `export_json.py` | `data_export.json` — one computation of every derived figure (divergences, Handlungsbedarf with tier and tone, the `ech_state` and `basis_state` of every data point, Dienststellen summaries, headline figures, Lebenslagen, labels, Datenstand); also writes today's snapshot to `verlauf.json`. Both files are written only after every gate passed: it stops with «ABBRUCH … nichts geschrieben» when a layer fails, a sum does not add up (`_summen_pruefen`: every figure with parts sums to its total, each Dienststelle adds up and all together equal the canton), `verlauf.json` is unreadable or a naming or basis text says «Datum» without a verdict (see `apply_wortwahl.py`). It also runs the comparison of the Gestaltung (`gestaltung_export.py`: `forms[].gestaltung` and the overview `gestaltung`), whose figures stay out of the headline figures, the open points and the Handlungsbedarf; `_summen_pruefen` checks that its Formulare per Dienststelle and its number of Formulare are those of `dienststellen_uebersicht` and `forms` |
| `kennzahlen.py` | The one definition of the key figures over time (works on a `citygov.db` of any vintage) and the `verlauf.json` reader/writer |
| `backfill_verlauf.py` | One-off: reconstructs past snapshots from the Git history of `citygov.db` (idempotent; a live build's entry of the same day wins) |
| `build_dashboard.py` | `dashboard.html` from `data_export.json` (+ `leitfaden.py`): the page reads every figure and state from the export and computes none itself; it stops on an older export (see «Rebuild every generated surface»). One contact form on every page (`kontaktHtml`), a glossary on «Methode & Quellen» whose terms are explained on the headline cards, shares with one decimal everywhere, Back/Forward return to the remembered place; the checklist above `drawView()` names the seven places a new page must be registered. The page «Gestaltung der Formulare» (`#gestaltung`, with shareable section addresses `#gestaltung/all/<gruppe>`, `m-<merkmal>`, `e-<merkmal>`, `kanton`, `dienststellen`, `grenzen`), the panel «Gestaltung» of each Formular and the section in the Dienststelle brief draw only what `gestaltung_export.py` computed, with the layer's own tone texts |
| `leitfaden.py` | The plain-German guide; the build refuses if a bullet cites a rule not in the databank |
| `build_flows.py` | `flows.html`, the guided questionnaires; inlines `quellen/ch-geo.js` for the place, postcode and country autocomplete and stops when it is missing or holds a «<». Keyboard-operable throughout (form picker, answer cards, suggestion lists, help drawer); answers stay in the reader's browser (localStorage keys `ff_profil` and `ff_draft_<form id>`), the page says so and offers «Profil und Entwürfe löschen» — a new storage key must be added to `storeKeys()` in the template; a step that throws shows a message instead of a blank screen |
| `export_llm.py` | `citygov_llm.json` and the `citygov_*.jsonl/json` exports |
| `export_ech_schema.py` | `citygov_ech_schemas.json` — one eCH-shaped exchange schema per Formular |
| `export_dossiers.py` | `dossiers/<slug>.html` per service + `dossiers/index.html` + `dossiers/_repo.js` (the marker a local dashboard probes); `--pdf` for local PDFs. Reads `ech_state` / `basis_state` and `services[].dossier_slug` from the export and stops, writing nothing, on an older one; the contact line reads as in the dashboard; the look comes from `theme.py`; every value written into a page passes `esc()` |
| `build_index.py` | `index.html` — the start page of the website served by GitHub Pages (<https://jastephan63.github.io/citygov/>) — and `404.html` |
| `build_datentresor.py` | `datentresor.db` — the synthetic storage example (`./build.sh --tresor`, before `export_json.py`) |
| `extract_law.py` | Text of a law PDF (offline; macOS PDFKit via osascript), the ground truth every citation gate maps against |
| `ingest_laws.py` / `ingest_fed.py` / `ingest_bigcode.py` / `fetch_rechtsbuch.py` / `build_gesetze_index.py` / `extract_quotes.py` | The law chain (step 1 above) |
| `load_dvsh_harvest.py` / `load_shep.py` / `consolidate_services.py` / `apply_consolidation.py` / `link_dvsh_eforms.py` | Service universe from DVSH and SHEP (read-only harvests) |
| `classify.py` / `ingest_new.py` / `load_data_fields.py` / `init_subfields.py` | Formulare and their fields |
| `scan_documents.py` / `init_verfahren.py` / `load_verfahren.py` / `build_similarity.py` | Verfahren layer and Duplikat-Radar |
| `scan_gestaltung.py` (+ `gestaltung_pdf.py`, `gestaltung_office.py`, `gestaltung_text.py`) | Gestaltung: how each Formular with a file looks and is presented, as measured facts in `form_gestaltung` — fonts, sizes, colours, the accessibility facts the file carries, printed phone numbers and e-mail types, edition mark, page numbers, sender; what cannot be measured is NULL with the reason, no verdict is stored. The three modules measure a PDF, a Word/Excel file and the text lines (each runs its self-test when started without arguments); `scan_gestaltung.py` runs those self-tests, measures every file and writes only rows that changed (idempotent; method `gestaltung-2`, raised whenever a measuring module returns something else for an unchanged file). Needs pypdf — run it with a Python that has it — and is not part of `./build.sh`: the build imports only `gestaltung_text.py` (standard library only, through `gestaltung_export.py`), never `gestaltung_pdf.py`, `gestaltung_office.py` or `scan_gestaltung.py` |
| `gestaltung_export.py` | The comparison of the Gestaltung, run inside `export_json.py` (standard library only): reads `form_gestaltung` and judges every Formular in 21 Merkmale against the practice of the measured Formulare — a value shared by at least two thirds of them, with at least 30 measured; without one no Formular is the outlier, and the Merkmal carries one open decision of the canton. Accessibility counts as machine-checkable Mindestmerkmale only. Returns `forms[].gestaltung` (per Formular: verdict, value, practice and detail sentences per Merkmal; for an eFormular only the mark that it has no look of its own) and the overview `gestaltung` (groups, Merkmale with their distribution and verdict counts, open decisions, Dienststellen, limits of the measurement, the layer's own labels and tone texts). `pruefen()` holds its invariants (verdict counts add up to the Formulare, every list equals its count, the open decisions a Formular counts are those whose lists name it, the Dienststellen add up to the canton — Abweichungen and Lücken apart —, each door figure of the page equals its source, no «@», no local path, no document title that looks like a person's name) and stops the export when one fails. Numbers are written with a decimal point, as everywhere on the dashboard; a decimal comma that an older run of the measurement stored is read the same way. `python3 scripts/gestaltung_export.py` prints the overview, `--form <id>` one Formular, `--json` both results, `--selbsttest` makes every invariant fire on tampered copies |
| `load_ech_map.py` / `load_subfield_ech.py` / `load_ech_verdicts*.py` / `load_ech_gaps.py` / `propagate_ech_names.py` / `load_esh.py` / `sweep_ech_xsd.py` | Standards |
| `load_field_legal.py` / `load_basis_typ.py` / `load_subjekt.py` / `load_data_rules.py` / `init_register.py` / `load_register.py` | Law layer per field, rules, register |
| `load_rechtsmittel.py` / `load_rechtsmittel_verdicts.py` / `load_panel_reviews.py` | Remedies and second opinions |
| `load_themenkatalog.py` / `run_begriffe.py` (+ `load_begriffe.py`, `load_pruefart.py`, `load_vorschlag_check.py`, `load_begriff_konsistenz.py`, `load_begriff_rollen.py`, `load_themen.py`, `load_korrekturen.py`) | Naming («Eine Angabe, ein Name») and Themengruppen |
| `check_online.py` / `load_currency.py` | Is our copy still the current edition? |
| `load_flows.py` / `fill_pdf.py` | Guided flows and writing answers back into the official PDF |
| `commit_proposal.py` / `auto_draft.py` | The retired 2026-06 auto-draft layer, kept because `ingest_new.py` imports it (it drafts the rows of a new file and copies the file into `formulare/`); `auto_draft.py` itself no longer runs as a command (a re-run would overwrite curated rows). Its field drafts are not exported, and its per-service notes reach `citygov_llm.json` only as legacy `findings` |
| `migrate_2026_09_26.py` | One-off, idempotent corrections from the 2026-09-26 quality check |
| `migrate_2026_09_27.py` | One-off, idempotent: one service row per DVSH service with its own file; same-file bundles named from DVSH wording; duplicate form 475 removed |
| `migrate_2026_10_01.py` | One-off, idempotent corrections from the clean-up of 2026-10-01: `file_type` of the Word Formulare, the `ech_herkunft` column, the eCH-0147 XSD pin, the auto-draft placeholder descriptions cleared, names stored in composed Unicode (NFC), the file compacted so the cleared texts are gone from it; checks that no exported column holds a local path |
| `apply_wortwahl.py` | Reader wording: in everyday German «Datum» is a calendar date, so the databank's own naming and basis texts say «Angabe» where they mean a piece of data. Applies the reviewed whole-text rewrites of `quellen/wortwahl_datum.json`; runs last in `run_begriffe.py`; `export_json.py` stops on a naming or basis text that says «Datum» without a verdict there |
| `deprecated/` | Retired tools, kept for the record (see its README for what replaced each) |
