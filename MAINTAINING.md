# Maintaining citygov — start here

This is the guide for whoever keeps the databank and the dashboard running. `README.md` explains
what the data means and how it is verified; `scripts/README.md` lists every command in its order;
`quellen/README.md` lists every evidence file; `docs/pruefprotokoll.md` keeps the review protocol
of an intake. This file says how the work is actually done, what must never be done, and what is
still open (state of the handover, 2026-11-05).

## 1. The one rule behind everything

The consumer of this data is an administration and a program that will act on it. A wrong
statement is worse than a gap: **a gap stays a gap** («zu ermitteln», «offen», «unbekannt»), every
claim has its evidence, and nothing is typed from memory.

## 2. Setting up

* **Machine.** macOS. The law readers use PDFKit through `osascript` (`scripts/extract_law.py`)
  and Word Formulare are read with `textutil`; on another system `ingest_laws.py`, `ingest_fed.py`
  (from a PDF; from the Fedlex XML it reads anywhere), `gesetz_stand.py`, `load_data_rules.py`,
  `load_rechtsmittel.py`, `load_themenkatalog.py` and the migrations that read law text find no
  text (`extract_quotes.py` reads the PDFs with pypdf). The build itself
  (`./build.sh`) runs anywhere with Python 3.11+.
* **Python.** One virtual environment with the pinned packages:
  ```bash
  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
  ```
  `build.sh` uses `.venv/bin/python3` when it exists; run the loaders with the same interpreter
  (`.venv/bin/python3 scripts/<name>.py …`). The versions in `requirements.txt` are the ones the
  measurement of the Gestaltung was tested with (`scan_gestaltung.py` runs a self-test and stops
  under another pypdf).
* **Page check.** Node 16+ and a local Chrome, Chromium or Edge; without them the last build step
  is skipped and the build still succeeds.
* **Source folders next to the repository** (not in Git; the build needs none of them, the
  loaders need all of them — keep a copy on team storage):

  | Folder | What it holds | Produced by |
  |---|---|---|
  | `../Gesetze/` | cantonal law PDFs (`<SHR>-….pdf`), federal ones in `../Gesetze/Bund/<SR>.pdf` and `<SR>.xml` | `scripts/fetch_rechtsbuch.py <SHR>`; Fedlex filestore (section 5) |
  | `../Verwaltung/` | the Formular files as the offices hold them | the offices; `scripts/ingest_new.py` copies new ones into `formulare/` |
  | `../DVSH/` | `dvsh_harvest_<date>.json`, `assets_<date>/` | the DVSH harvest (section 5) |
  | `../SHEP/` | `<date>/` (SHEP pages), `live-<date>/` (services.sh.ch pages, links, `online/` eForm captures, `steuer/` …) | the portal harvests (section 5) |
  | `../formflows/` | the three hand-built prototypes the guided flows follow | — |

## 3. Daily work

```bash
./build.sh                         # every generated file from citygov.db, then tests and page check
python3 scripts/validate_db.py     # the integrity gate alone
python3 -m citygov list            # every command by layer
```

**Publishing** (the site is this repository on GitHub Pages):
1. Run the loaders, then `./build.sh` until it is green.
2. Every build that moves a count bumps the export contract once. Before committing, restore it
   and build exactly once: `git checkout -- exportvertrag.json schema/ && ./build.sh`.
3. `git status`: stage only what the change produced — never local notes, backups or
   `*.staging` files.
4. Commit (a message that says what changed in the data and why), push `main`. A large push may
   need `git -c http.postBuffer=1048576000 -c http.version=HTTP/1.1 push`.
5. Pages deploys in about a minute (`gh run list` shows «pages build and deployment»); pages may
   be cached for up to ten minutes. Open the live site and check the changed page.

## 4. Rules that are never relaxed

1. **The sites are read-only.** DVSH, SHEP, services.sh.ch, eforms.sh.ch, sh.ch: only the GETs a
   visitor's browser makes (on eforms.sh.ch also the one «Weiter» of a first page that asks for
   nothing). Never a change in the DVSH modeller, never a click in its admin UI,
   **never type into, tick, upload to or submit an online form** (`scripts/capture_eforms.py` is
   built that way). What is wrong on the portal is *recorded* with the right target
   (`quellen/korrekturen/portal_korrekturen_<date>.json`); the office corrects it.
2. **Formulare are read-only.** `formulare/` holds the files exactly as published; the databank
   identifies inconsistent points and never prescribes or edits.
3. **DVSH is authoritative for legal bases and services.** A conflict between a derived citation
   and the DVSH law set resolves towards DVSH.
4. **Never type a citation from memory, never guess an SR/SHR number.** An article is cited only
   when its text was read in the official PDF/XML and it is a row of `article`; the loaders'
   proof gates reject everything else. Verification level in `article.last_checked`.
5. **Content beats title; only the newest edition.** A newer edition is ported field by field
   (`scripts/migrate_ausgaben_2026_10_28.py <ports.json>`: every existing field keeps its id).
6. **The atomic unit is the part** (`data_subfield`): Name, Vorname, Geburtsdatum each carry their
   own eCH element. A printed cell stays one part («Name, Adresse»); never invent a part.
7. **Gaps, not risk.** «no explicit norm» is not over-collection when the task needs the Angabe
   (`basis_typ` aufgabe/ohne/offen); `no_basis=1` only where no ingested law names it; a field whose
   law is not ingested stays «zu ermitteln». Once-only/prefill marks apply only to natural persons
   (`subjekt = 'natuerliche_person'`, a whitelist).
8. **One source of truth.** `citygov.db`; everything else is generated — regenerate, never edit.
   Every write goes staging → validate → swap and is idempotent.
9. **Wording.** «Datum» only for a calendar date (`quellen/wortwahl_datum.json`); quotes verbatim;
   no «Risiko/Verstoss». Colour = who acts next (green geklärt, red Dienststelle, amber Kanton,
   grey Databank); `citygov/core/labels.py` and `theme.py` are the only definitions.
10. **History is the audit trail.** Never amend, rebase or force-push `main`.
11. **One writer of `citygov.db` at a time.** Two people (or two runs) doing staging → swap at the
    same time silently lose one side's writes, and a binary database cannot be merged. Agree who
    loads, pull before loading, push right after.
12. **Evidence first.** A one-off correction is an evidence file under `quellen/korrekturen/` (with
    the reason per row) plus an idempotent, gated migration `citygov/load/migrate_<date>.py` and its
    wrapper in `scripts/`; panel outputs are kept under `quellen/dokumente/panel_<date>/`.

## 5. Harvests (where the data comes from)

* **DVSH modeller** (modeller.dvsh.ch, login with read access needed). In the logged-in browser,
  open the developer console on the services list: find the react-query `QueryClient` and the tRPC
  client by walking the React fiber tree (`queryClient` prop; the provider's sibling prop `client`
  is the proxy — it answers every property with a function, so test with try/catch). Then
  `await client.admin.services.get.query({id})` for every id of the cached `admin.services.list`
  (concurrency 4), add `organisations.list` from the cache, and save one JSON file via a Blob
  download as `../DVSH/dvsh_harvest_<date>.json` (about 5 MB). Assets: the same session's GET
  `/api/service-asset/<id>/<sha256>`. Load with `scripts/load_dvsh_harvest.py <file> [--vorher <date>]`.
  Only GET queries — never a mutation.
* **SHEP** (shep.meetfrida.agency): public pages, plain GETs of `/de/services` and each slug into
  `../SHEP/<date>/`; `scripts/load_shep.py <pages-dir> [--vorher <date>]`.
* **Live portal** (services.sh.ch): one GET per slug of `/de/services` into
  `../SHEP/live-<date>/pages/`, the sh.ch files the pages link fetched once into `links/` with a
  `manifest.json` (url, sha256); `scripts/load_portal.py ../SHEP/live-<date>`.
* **«Online erledigen»**: the button targets (`online/ziele.json`), the migrationsamt.sh.ch pages and
  the links inside their Hilfsblatt PDFs (link annotations) → `scripts/capture_eforms.py ziele|abrufen`
  → judged in `quellen/dokumente/online_<date>.json` → `scripts/load_online.py … [--shch …]
  [--korrekturen …]`.
* **Laws.** Cantonal: `scripts/fetch_rechtsbuch.py <SHR>` then `scripts/ingest_laws.py <SHR>` (reads
  the full PDF text). Federal: the Fedlex filestore PDF and XML
  (`…/eli/cc/<eli>/<YYYYMMDD>/de/pdf-a/…pdf`, the XML under the same path with `xml`), then
  `scripts/ingest_fed.py <SR>=<file.xml>=<title>=<short>`. Afterwards `extract_quotes.py
  ../Gesetze/Bund`, `gesetz_stand.py`, and for the edition in force `check_gesetz_stand.py`.
* **eCH** catalogue: `scripts/sweep_ech_xsd.py`. **Currency of the Formulare** on sh.ch:
  `scripts/check_online.py` + `scripts/load_currency.py`.

## 6. Taking in new Formulare (an intake)

1. Judge every new file from its content (`quellen/dokumente/urteile_<date>.json` →
   `load_dokument_urteile.py`), plan the intake (`uebernahme_<date>.json` → `load_uebernahme.py`).
2. `scan_documents.py`, then `scan_gestaltung.py` (pypdf interpreter).
3. The layers, each judged and sceptically reviewed (`docs/pruefprotokoll.md`), loaded with
   `scripts/apply_panel.py` in this order: `felder` → `ech` and `verfahren` → `recht` (then
   `ersetzen` for a completion or an Angleichung across sibling Formulare, and `recht` again) →
   `subjekt` → `rechtsmittel`.
4. `extract_quotes.py ../Gesetze/Bund`, `gesetz_stand.py`, `build_similarity.py`, then publish.

Traps that each cost a rerun:
* Never feed a rebuilding loader only the new Formulare: use the scoped modes (`load_verfahren` /
  `load_register --nur <ids>`, `init_subfields --nur-neue`, `load_ech_verdicts_new --nur-offene=<id>`
  or `--nur=<ids>`). `load_esh.py`, `run_begriffe.py` and `load_themen.py` reload whole tables.
* No trial build between loading the fields and the subjekt (it derives party rows early).
* The subjekt layer covers only fields with a register standard (eCH-0044/0010/0011/0007/0008).
* The remedy layer runs after the legal bases (its candidates are the cited laws).
* Sibling Formulare judged one by one diverge: compare same-labelled Angaben across the intake and
  harmonise them (one verdict per Angabe in one procedure, justified differences kept).
* A text layer can hide printed boxes (Formular 7 «PID/UID/FID»): render the page when a sibling
  Formular has them.
* Law readers: the old line-index reader lost articles and took wrapped cross-references
  («Art. 65 sinngemäss.») for articles — check `article` before trusting «kein gültiges Ziel»;
  Fedlex numbers are «<b>Art. 66</b><i>a</i>» (inline tags join without a space).
* Remedy reasons ≤ 400 characters, without «Kandidat», «Zweitprüfung», «im Material», «Regel N».

## 7. Recurring checks

| Check | Command | Last run | Cadence |
|---|---|---|---|
| DVSH harvest | section 5 → `load_dvsh_harvest.py` | 2026-10-28 | monthly |
| SHEP and live portal | `load_shep.py`, `load_portal.py`, `load_online.py` | 2026-10-28 / 2026-11-03 | monthly |
| Currency of the Formulare | `check_online.py` + `load_currency.py` | 2026-09-26 (partial; 301 re-checks overdue) | every 6 weeks |
| Law editions in force | `check_gesetz_stand.py`, then re-read newer editions | 2026-10-04/05 | quarterly, and before 1 January |
| eCH catalogue | `sweep_ech_xsd.py` | 2026-09-26 | quarterly |
| Duplicate radar | `build_similarity.py` | 2026-11-05 | after each intake |

The dashboard's «Datenstand» names the date of each source; when one ages, it says so.

## 8. Open work at the handover (2026-11-05)

**Data work (the databank's own homework, «Recherche» in the dashboard):**
* Formulare 468–541 (73, from the DVSH model): legal bases, purpose, Beilagen, outcome and remedy
  are missing for 66 of them — the largest open block (about 960 fields «zu ermitteln»).
* Laws not ingested yet: ZPO, SchKG, SVAG, UIDG, BSV/BSO, KLV, KVG Art. 25a (fields of 542+ wait
  for them); a remedy rule for DBG Art. 132 (Einsprache, direkte Bundessteuer) for the tax
  Formulare 589–598; their Entscheid stays «unbekannt» until DVSH describes it.
* 35 cited laws have a newer edition in force than the one read (about half of all citations):
  re-read them and check each citation against the new text.
* eCH: 548 data points whose label means another Angabe than the assigned element; 94 on
  superseded standards. eSH codes are missing on most new «kein Standard» fields (`load_esh.py`
  reloads the whole table — its inputs must be rebuilt first).
* Naming (Begriffe) stopped at the 2026-10-28 intake: `run_begriffe.py` needs its review folder,
  which is no longer available — rebuild it before naming the new Formulare.
* Party (B2) verdicts for Formulare 542–598; 7 remedy items await a second review.
* 13 online-only eForms without a paper version; 4 guided flows are stale (186, 190, 405, 452).
* Article rows `§ A…`/`Art. T…` (annexes, transitional provisions) have no quote text yet.
* The register remark of the Einwohnerregister still says that § 6 of SHR 431.101 is not in the
  databank; it is ingested since 2026-11-05 (headings only, no text yet) — update the remark when
  the article text is read.
* Field 2617 (Formular 280): its definition says «Rechnungsprüfungsorgan», but the cover sheet asks
  for the Zweckverband's president. Left unchanged on 2026-11-05 because a changed definition can
  move a field's identifier — correct it through a reviewed port.

**Decisions for the canton (#kanton in the dashboard):** data points without a standard in force,
fields demanded differently across Formulare, Schutzstufe and DSFA, retention decisions, register
access, the 26 proposed roles and the concepts, the Gestaltung decisions (font sizes, telephone
format, Stand, Absender), the 90 pairs of the duplicate radar.

**Decisions for the team (were the former owner's):**
* the duplicate Formular pairs 154/498 and 410/499 (same file twice under one service);
* the provenance value `derived_by = 'agent'` (6,325 fields) — keep or rename;
* the synthetic AHV and telephone numbers of the Datentresor fall in real number ranges;
* the base address of the permanent identifiers (`citygov/core/kennungen.py`, `BASIS_URI`);
* the prefill points «until the owner decides» and the moved headline figures of 2026-10-05
  (README, «Known gaps»).

**Passed on to the offices:** the six corrections for services.sh.ch (dashboard, Abgleich, «Was
auf services.sh.ch zu korrigieren ist») — record in the evidence file when an office has fixed one.

## 9. Moving the repository

The site address is written in several places; after a transfer to another account
(`<owner>.github.io/citygov` — GitHub does not redirect Pages addresses) change all of them and
rebuild: `citygov/present/build_index.py` (`SITE`, `REPO`, docstring), `citygov/present/assets/dashboard/boot.js`
(three places), `citygov/present/assets/dashboard/dashboard.js` (one fallback), `build.sh` (comment),
`citygov/cli.py` (comment), `README.md` and `scripts/README.md`. Then `git remote set-url origin …`,
enable Pages for `main` on the new repository, and check the live site.
