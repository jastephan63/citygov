# scripts/ — how the databank is built and loaded

`citygov.db` is the only data source. `./build.sh` regenerates every file it
lists from it (its first three steps, `init_register.py`, `kennungen.py` and
`rollen.py ableiten`, rewrite only derived data inside the DB, each through
staging → validate → swap); `verlauf.json` keeps one snapshot per build day. The code, the
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
./build.sh            # init_register → kennungen → rollen ableiten → export_json → theme --check
                      # → build_dashboard → build_flows → export_llm → export_ech_schema
                      # → export_vertrag (contract check) → kennungen --pruefen → export_dossiers
                      # → build_index → validate_db → check_pages (page check; skipped without Node or Chrome)
./build.sh --tresor   # + build_datentresor right after rollen ableiten, before export_json reads the
                      #   vault for the Bürgersicht (needs .venv with cryptography; the vault names every
                      #   Angabe by its permanent identifier, so it needs kennungen.py first)
./build.sh --pdf      # + dossiers/*.pdf (needs Google Chrome in /Applications; local only, ignored by Git)
```

The build reads nothing outside the repository: `build_flows.py` inlines
`quellen/ch-geo.js` and stops when it is missing, and `export_json.py`,
`export_llm.py`, `export_ech_schema.py` and `build_flows.py` refuse to write
a text that names a local path (`common.assert_no_local_paths`).

`export_json.py` also computes the data-model layers once, each from a module
of its own (standard library only): the party of every data point
(`rollen.parteien_anhaengen`, from the tables `rollen.py ableiten` wrote), the
change-impact index per law and article with the edition read and its latest
check (`wirkung.py`), and the register map with the corrected
«vorbefüllbar» count (`register_map.prefill_korrigieren`, `export_register`);
a missing table is skipped loudly like any layer. Then every exporter puts the
permanent identifiers on its objects (`kennungen.anreichern`: `kennung` next
to every id, `formular_kennung`, `artikel_kennung`, `angabe_kennung` next to
every reference; an identifier that does not resolve stops the export) and
stamps its version (`export_vertrag.fertigstellen`); after its files are
written, `Vertrag.festschreiben()` writes the JSON Schema under `schema/` and
`exportvertrag.json` — only when the structure or a count changed. The rules:
a removed required key path, a changed type or an object that became a map
raises the major version, an added key path, a removed optional one or a
changed nullability or presence the minor version, a moved count (not the
trend history `verlauf`, which grows by one entry per build day) or a changed
schema wording the patch; objects keyed by states or codes are maps (a state
reaching zero is a moved count), every identifier key carries the pattern of
its scheme, and a reviewed note in
`quellen/exportvertrag_hinweise.json` (absent today) can raise it where a key
kept its name but changed its meaning. `export_vertrag.py` checks all seven
exports read-only at the end of the build.

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
`export_json.py` also stops when a figure of the data-model layers does not
add up (the corrected «vorbefüllbar» against its parts, the parties counted
again on the data points, the register figures against the Formulare) or
`wirkung.pruefen()` finds a count of the change-impact index that the
citations do not back; `export_llm.py` stops when its prefill map and the
dashboard's «vorbefüllbar» disagree on a Formular or when a prefilled point
belongs, by `citygov.db`, to anyone but the applicant; `export_vertrag.py` stops
on an export whose version, schema file or counts differ from
`exportvertrag.json` (a hand-edited schema file stops the next export, too);
`kennungen.py --pruefen` stops when an object has no active identifier or an
identifier no longer names its object; `build_dashboard.py` stops with «ABORT — data_export.json fehlt, was die Seite
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
python3 scripts/rollen.py ableiten                  # Parteien und Rollen, stage B1 (deterministic; also a step of ./build.sh)
python3 scripts/rollen.py bericht [--json F]        # coverage: per rule, per Formular, the ambiguous register points
python3 scripts/rollen.py stichprobe [N] [SEED]     # random settled assignments to check against the Formular text
python3 scripts/rollen.py vorbereiten DIR [ID …|--pilot N]   # stage B2 input, one in_<id>.json per Formular
python3 scripts/rollen.py laden DIR                 # stage B2 verdicts out_<id>.json through the gates, then B1 again;
                                                  # a second review loads the same way (panel_review 'partei').
                                                  # Needs pypdf (the quotes are checked in the Formular text):
                                                  # run it with a Python that has it
python3 scripts/rollen.py pruefen                   # the gate plus completeness, standalone
python3 scripts/load_data_rules.py <dir> ...      # storage/processing/disclosure rules, quotes PDF-verified
python3 scripts/init_register.py                  # derived: canonical attributes, format codes
python3 scripts/kennungen.py                      # permanent identifiers (also a step of ./build.sh, right after
                                                  # init_register.py): new objects get one, gone ones become
                                                  # «entfallen», none is reused; writes nothing when nothing changed.
                                                  # A rename keeps its identifier only on evidence a re-inserted row
                                                  # cannot fake (same element, or same definition); refuses to mint
                                                  # into a missing or empty table (first issue only with
                                                  # --erstausgabe, never once data_export.json carries identifiers).
                                                  # --abloesungen <json> applies reviewed «abgelöst durch» decisions
                                                  # (default quellen/kennung_abloesungen.json, absent today);
                                                  # --aufloesen <kennung> resolves one (read-only)
python3 scripts/load_register.py <dir>            # purposes, recipients, Fristen (number must be in the quote)
python3 scripts/load_verfahren.py <dir>           # Beilagen + Entscheide
python3 scripts/register_katalog.py --abrufen     # network, read-only GETs: refresh quellen/register/ (unchanged texts keep their file)
python3 scripts/register_katalog.py               # register catalogue: holder, level, content, key, eCH links — every claim quoted from a fetched source
python3 scripts/register_map.py                   # Angabe × entity -> register, Beilage terms, access articles (after load_verfahren.py)
python3 scripts/register_map.py --bericht         # the register figures on today's data (builds the export in memory, writes nothing)
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

# 7. law editions (Gesetzesstand) — loaders, not build steps; after the law chain of step 1 and
# after load_field_legal.py / extract_quotes.py, whose article.last_checked and text_excerpt they read
python3 scripts/gesetz_stand.py                   # per law the edition (Stand) the articles were read from:
                                                  # article/law last_checked, law.source_note, the head of the
                                                  # PDF the loaders read (../Gesetze, ../Gesetze/Bund), the cited
                                                  # texts found again in that file -> gesetz_stand; needs macOS
                                                  # PDFKit (extract_law.py); idempotent («nichts zu tun»); again
                                                  # after every ingest_laws.py / ingest_fed.py / extract_quotes.py
python3 scripts/check_gesetz_stand.py [--roh <dir>]   # read-only GETs: rechtsbuch.sh.ch (cantonal) and the Fedlex
                                                  # SPARQL endpoint (federal), one per law, 1.5 s apart -> one
                                                  # dated row per law in gesetz_stand_pruefung; lists laws whose
                                                  # current edition is newer; a later Fedlex edition counts only
                                                  # when it is published (an announced one without publication
                                                  # date and text stays in details); re-reads nothing; stops when
                                                  # gesetz_stand is incomplete or stale; --aus <dir> re-runs from
                                                  # kept answers (rows dated as the answers, the address they
                                                  # asked), --trocken writes nothing, --liste shows the latest
                                                  # result per law
# then ./build.sh (export_json.py computes the change-impact index, scripts/wirkung.py)

# evidence-backed corrections (evidence under quellen/ or in the script's docstring)
python3 scripts/migrate_2026_09_26.py             # idempotent; see its docstring
python3 scripts/migrate_2026_09_27.py             # services that bundled several DVSH services, split or renamed
                                                  # (quellen/korrekturen/dvsh_aufteilung_2026-09-27.json); again after run_begriffe.py
python3 scripts/migrate_2026_10_01.py             # idempotent clean-up of 2026-10-01; see its docstring
python3 scripts/migrate_2026_10_05.py             # two article rows that are ingest artefacts (SR 831.20 «Art. 27»,
                                                  # SR 510.10 «Art. 48»), quellen/korrekturen/artikel_artefakte_2026-10-05.json;
                                                  # then gesetz_stand.py (their laws' evidence changed) and
                                                  # kennungen.py (their identifiers become «entfallen»)
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
10. **One computation per figure**: labels, Handlungsbedarf, the «same datum» key, the eCH and legal-basis state of every data point, texts, the Datenstand, the verdicts of the Gestaltung, the party of every data point, the change-impact index, the register map and the «vorbefüllbar» rule are computed once (`labels.py`, `export_json.py`, `gestaltung_export.py`, `rollen.py`, `wirkung.py`, `register_map.py` — `citygov_prefill.json` and burden.prefillable share `register_map.prefill_punkte`) and read by every surface; the look of every page (fonts, colours, tones, symbols, text sizes) is defined once in `theme.py`.

## What each script does

| Script | Purpose |
|---|---|
| `common.py` | Paths (the environment variables `CITYGOV_DB` and `CITYGOV_SCHEMA` point every script at a private copy of the database and its schema — to develop or test a layer without touching the shared files; a private database without the identifier table, or with an older one, fails the identifier gate against the published `data_export.json` unless `CITYGOV_EXPORTE` names a folder of other published files, e.g. an empty one), `connect()`, the shared normalisations (`norm_ascii`, `norm_label`, and `klartext()`, the display form `apply_wortwahl.py` compares against), `pl()`, the local-path guard `assert_no_local_paths()` the exporters run on their output, and `size_txt()` / `net_size_txt()` (the page sizes the dashboard and the start page state) |
| `labels.py` | German labels for every enumerated value, the four status tones (who acts next), the priority tiers and the words of the contact line (`KONTAKT`: «Kontakt (laut DVSH)», «Tel.», «E-Mail», «nicht hinterlegt») — the single source for dashboard, guided forms, dossiers and exports |
| `theme.py` | The shared look: fonts (system fonts only), colours, the four tones with their tints and symbols, the eSH violet, the six text sizes (12–28 px on screen, 9–20 pt on paper). The four page generators write their `:root` block from it (`css_root()`) and use only `var(--…)`; `python3 scripts/theme.py` prints tokens, contrast table and findings, `--check` (a step of `./build.sh`) exits 1 on a text colour below 4.5:1 on one of its backgrounds, on a colour, size or font literal left in a generator — a hex, `rgb()`/`hsl()` or named colour (also `%23…` in a data URI and `el.style.color=`), a font size in px/pt/em/rem/% (also `el.style.fontSize=`), a font family — (a literal kept on purpose carries `theme:keep` and its reason in the same line) or on tone names that differ from `labels.TON` |
| `validate_db.py` | Integrity gate every loader runs on its staging copy (FKs, vocabularies, cross-layer invariants, schema.sql coverage of tables, columns and indices, every `form.source_file` an existing file under `formulare/` with a matching `file_type`, every `form_gestaltung` row measured on the current file and equal to its own profile) and the gates of the data-model layers, each kept next to its loader: `kennungen.pruefen`, `rollen.pruefen`, `gesetz_stand.pruefen`, `register_map.pruefen` (each skipped while its tables are absent; importing them loads no network code and no pypdf) |
| `kennungen.py` | Permanent identifiers («Kennungen») for every service, Formular, Datenfeld, Teilfeld, canonical Angabe, law, article and handling rule, in a neutral scheme (`sh:formular:<slug>:feld:<n>:teil:<m>`, `sh:angabe:<eCH-code>:<element>[:<context>]`, `sh:gesetz:sr-<SR>:art-<no>` …; the base address for resolvable URIs is the one constant `BASIS_URI`, an owner decision). Minted once from the natural key, never changed, reused or re-pointed; a renamed field or part keeps its identifier only on evidence a deleted and re-inserted row cannot fake (the same eCH element or eSH key at the same place, or for a field without one the same definition; never the row id), a gone object becomes «entfallen», «abgelöst durch» only from the reviewed `quellen/kennung_abloesungen.json`. The table `kennung` guards itself with triggers, and the registry itself is guarded: no minting into a missing or empty table without `--erstausgabe`, and `pruefen()` reports every identifier the published `data_export.json` carries that the table lacks. Every identifier that is no longer active is published with status, date, reason and successor (`kennungen` in `data_export.json`, `meta.kennungen` in `citygov_llm.json`). A step of `./build.sh` right after `init_register.py` (which renumbers `canonical_attribute`), `--pruefen` again at its end; `pruefen()` for `validate_db.py`, `anreichern()` for the exporters, `aufloesen()` the resolver |
| `export_vertrag.py` | The contract of the seven published exports: the hook `fertigstellen()` (identifiers via `kennungen.anreichern`, then the version stamp) that `export_json.py`, `export_llm.py` and `export_ech_schema.py` call per file, `Vertrag.festschreiben()` (writes `schema/<export>.schema.json` and `exportvertrag.json` only when the structure or a count changed; deterministic), and the read-only check `python3 scripts/export_vertrag.py` at the end of `./build.sh` (version, schema checksum, the file against its schema, the recorded counts) |
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
| `rollen.py` | Parteien und Rollen — whose Angabe each data point is. The controlled role list (26 roles, «Vorschlag», each grounded in the free-text role strings of the naming layer, the Lebenslagen party words and the labels), the parties of every Formular and the assignment of every data point (Teilfeld, or Datenfeld without parts) to exactly one party or to «unklar» with a reason. Stage B1 (`ableiten`, standard library, a step of `./build.sh` after `kennungen.py`) settles what the begriff role, party words in labels and sections and the subjekt settle; stage B2 (`vorbereiten`, `laden`) loads judged verdicts per Formular through proof gates (role from the list, every point exactly once, every quote found in the Formular text, entity type equal to the field's subjekt) and second reviews (`panel_review` kind `partei`). `pruefen()` is the gate validate_db calls; `parteien_anhaengen()` the hook export_json calls |
| `wirkung.py` | The change-impact index, computed once inside `export_json.py` (standard library only): per law and per article the citations, Datenfelder, data points (atomic units), Formulare, services and Dienststellen that cite it, other places that rest on the article (data rules, remedies, disclosures, outcomes), the edition read (`gesetz_stand`) and the latest currency check (`gesetz_stand_pruefung`), and the union of everything that cites a law with a newer edition. `pruefen()` checks every count against the databank and the export's Dienststellen and units and stops the export when one fails; `python3 scripts/wirkung.py` prints the overview, `--gesetz`, `--artikel`, `--json`, `--selbsttest` makes every invariant fire on tampered copies |
| `register_katalog.py` / `register_map.py` | Once-only through registers («Was der Kanton schon weiss»). `register_katalog.py` holds the catalogue of 18 Swiss registers and official information systems; every holder, content, key and eCH link is a verbatim quote from a source it fetched read-only (Fedlex filestore, the Rechtsbuch interface, agency pages, ech.ch) and stored as a text snapshot under `quellen/register/`; the gate refuses a claim whose quote is not in its snapshot. `register_map.py` maps canonical Angaben (eCH element by id, or eSH key) × entity type to registers, quoted from the register's content source (an element that identifies its party — UID, EGID, E-GRID, Stammnummer, chip number — confirms by itself; a name, an address or a legal form only with a judged subjekt; a rule may demand or exclude a context: the dog database only for a dog, the GWR not for the heating or the areas a permit applies for, the IVZ no ships), names the documents a register issues (term in the quote), records ingested access articles as «kandidat» or «schranke» (never «erlaubt»; an article not yet ingested waits and is reported), and holds `pruefen()` (called by `validate_db.py`), `prefill_punkte()` (the one «vorbefüllbar» rule `export_llm.py` writes `citygov_prefill.json` with and `build_flows.py` fills the guided Formulare by: the Einwohnerregister mark — a quoted rule names the element of a natural person's field — AND the applicant's own Angabe by the party layer AND not mehrdeutig within that party), `prefill_korrigieren()` (sets the mark and burden.prefillable) and `export_register()` (levels standard / element / bestaetigt per data point, Beilagen by halter or document term, model estimate per Formular and Themengruppe; run inside `export_json.py`). Standard library only (the fetch imports urllib only when it runs); the snapshots are the evidence and belong in the repository |
| `export_dossiers.py` | `dossiers/<slug>.html` per service + `dossiers/index.html` + `dossiers/_repo.js` (the marker a local dashboard probes); `--pdf` for local PDFs. Reads `ech_state` / `basis_state` and `services[].dossier_slug` from the export and stops, writing nothing, on an older one; the contact line reads as in the dashboard; the look comes from `theme.py`; every value written into a page passes `esc()` |
| `build_index.py` | `index.html` — the start page of the website served by GitHub Pages (<https://jastephan63.github.io/citygov/>) — and `404.html` |
| `build_datentresor.py` | `datentresor.db` — the synthetic storage example (`./build.sh --tresor`, before `export_json.py`); every stored Angabe is named by its permanent identifier (vault table `angabe`), never by `canonical_attribute.id`, and the build stops, writing nothing, when an Angabe has no identifier |
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
| `gesetz_stand.py` | Loader: per law the edition («Stand») the databank read its articles from, from evidence only — the Stand recorded when the articles were read (`article.last_checked`, `law.last_checked`, `law.source_note`), the Stand printed in the head of the PDF the loaders read (cantonal: the file of `inventory/gesetze_index.json`, as `ingest_laws.py` and `extract_quotes.py` pick it; federal: `../Gesetze/Bund/<SR>.pdf`), and how many cited article texts occur in that file. All sources agree → `belegt`; they disagree → `widerspruch`, none → `unbekannt` (Stand NULL, reason in `grund`). Writes `gesetz_stand` (idempotent; «nichts zu tun» leaves `citygov.db` untouched). Its `pruefen(conn)` is the gate `validate_db.py` runs on `gesetz_stand` and `gesetz_stand_pruefung`; a row whose `basis` no longer matches the databank is stale (shown «veraltet», renewed by the next run), never an error. Needs macOS PDFKit; `--trocken`, `--zeigen <law>`, `--pruefen` |
| `check_gesetz_stand.py` | Loader (network, read-only GETs): asks the Schaffhauser Rechtsbuch (`rechtsbuch.sh.ch/api/de/texts_of_law/<SHR>`, the interface of `fetch_rechtsbuch.py`) and the Fedlex SPARQL endpoint (consolidations of the act under the SR number) for the edition in force, one request per law, 1.5 s apart, and writes one dated row per law into `gesetz_stand_pruefung`: aktuell, neuer_stand (with the number of newer editions), aufgehoben, stand_unbekannt, nicht_gefunden, nicht_pruefbar, fehler or unklar, plus editions already published for later. Lists the laws with a newer edition by number of citations; re-reads no article and changes no citation. `--roh <dir>` keeps every answer, `--aus <dir>` re-runs from kept answers, `--nur`, `--trocken`, `--liste` |
| `load_flows.py` / `fill_pdf.py` | Guided flows and writing answers back into the official PDF |
| `commit_proposal.py` / `auto_draft.py` | The retired 2026-06 auto-draft layer, kept because `ingest_new.py` imports it (it drafts the rows of a new file and copies the file into `formulare/`); `auto_draft.py` itself no longer runs as a command (a re-run would overwrite curated rows). Its field drafts are not exported, and its per-service notes reach `citygov_llm.json` only as legacy `findings` |
| `migrate_2026_09_26.py` | One-off, idempotent corrections from the 2026-09-26 quality check |
| `migrate_2026_09_27.py` | One-off, idempotent: one service row per DVSH service with its own file; same-file bundles named from DVSH wording; duplicate form 475 removed |
| `migrate_2026_10_05.py` | One-off, idempotent correction of 2026-10-05: removes the two article rows that are ingest artefacts (a footnote or Amtliche-Sammlung list as «heading», no text, nothing cites them, the real article with the same number is its own row), gated on law, number, heading, the real row and every foreign key; evidence in `quellen/korrekturen/artikel_artefakte_2026-10-05.json` |
| `migrate_2026_10_01.py` | One-off, idempotent corrections from the clean-up of 2026-10-01: `file_type` of the Word Formulare, the `ech_herkunft` column, the eCH-0147 XSD pin, the auto-draft placeholder descriptions cleared, names stored in composed Unicode (NFC), the file compacted so the cleared texts are gone from it; checks that no exported column holds a local path |
| `apply_wortwahl.py` | Reader wording: in everyday German «Datum» is a calendar date, so the databank's own naming and basis texts say «Angabe» where they mean a piece of data. Applies the reviewed whole-text rewrites of `quellen/wortwahl_datum.json`; runs last in `run_begriffe.py`; `export_json.py` stops on a naming or basis text that says «Datum» without a verdict there |
| `deprecated/` | Retired tools, kept for the record (see its README for what replaced each) |
