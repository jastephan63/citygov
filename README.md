# citygov — Compliance-Databank Kanton Schaffhausen

A database of the canton's administrative services. For each service it
records: the laws behind it (down to the article), the data its Formulare
collect (down to the single field), the standard each datum maps to (eCH, or
the draft cantonal standard eSH), the rules for handling that data (storage,
retention, disclosure), and how far the service is from being fully digital.

Gaps are shown as gaps. If a legal basis is missing or unverified, the
dashboard says so instead of hiding it.

It is written for two readers: peer administrations building the same kind
of databank, and an LLM agent that has to process cantonal services from it
— which is why every statement has to be precise, sourced and never silently
wrong.

## What is in here

| File | What it is |
|---|---|
| `citygov.db` | The main database (SQLite, about 25 MB). Every generated file (dashboard, flows, exports, dossiers, Datentresor) is built from it. |
| `dashboard.html` | The dashboard, one self-contained file of about 37 MB: per service its Verfahren, Formulare, data fields, legal bases, standards, handling rules and digitalisation status. |
| `flows.html` | Guided questionnaires (2 MB): a step-by-step walkthrough for 57 of the 474 Formulare — the page states this coverage itself. The other Formulare have none yet. |
| `dossiers/` | One printable Datenschutz-Dossier per service (480 HTML pages; typically 1–4 A4 pages, longer where a Formular has many fields or divergences), generated from the same data. Open `dossiers/index.html`, or reach a service's dossier from its page in the dashboard. The page has a print button; `./build.sh --pdf` writes PDFs locally instead. |
| `datentresor.db` | Example storage database with synthetic data (about 49 MB, see below). |
| `data_export.json` | Generated intermediate (about 37 MB): the one export of `citygov.db` that the dashboard, the flows, the dossiers and the machine-readable exports all read. |
| `citygov_llm.json` and the other `citygov_*` files | Machine-readable exports of the databank: `citygov_llm.json` (about 17 MB), `citygov_datafields.jsonl`, `citygov_datarules.jsonl`, `citygov_prefill.json`, `citygov_verzeichnis.json`, `citygov_ech_schemas.json`. |
| `schema.sql` | The database schema — all 43 tables — with the design notes per layer. |
| `build.sh` | The one build command (see «Building»). |
| `requirements.txt` | The three third-party Python packages the loaders and the Datentresor need. |
| `scripts/` | All loaders, harvesters and exporters. `scripts/README.md` says what each script does and in which order the loaders run. Retired tools sit in `scripts/deprecated/`. |
| `formulare/` | The original Formular files (432 PDF/Word/Excel files, about 145 MB), tracked so the «Quelldatei» links work offline. Every `form.source_file` in the database resolves here; the remaining 42 Formulare are eFormulare built from DVSH form definitions and have no file. |
| `forms/` | A local, untracked mirror of the canton's source folder that `scripts/ingest_new.py` fills when new files are ingested. Only its README is in the repository. |
| `ech_xsd/` | The official eCH XML schemas (104 files) the element catalogue and code lists were read from. |
| `quellen/` | Official source PDFs (the eCH-0049 Themenkatalog annexes) and the evidence-backed single corrections that were applied to the database, each with its reason. |
| `inventory/` | The index of the law PDFs the citations were read from (`gesetze_index.json`, written by `scripts/build_gesetze_index.py`) and the Fedlex ELI map. |
| `proposals/` | Input JSON for `scripts/commit_proposal.py` from the retired auto-draft workflow (one file, kept for the record). |

## Opening the dashboard on your computer

The dashboard is a single HTML file with all data built in. Nothing to
install, no server required. It works offline: all data, laws, rules and
standards are inside the file. The only thing the pages fetch from the web is
the typefaces (Google Fonts); without a connection they fall back to system
fonts and nothing else changes. One thing does **not** work: clicking the
file on github.com — GitHub cannot preview a file this large. Get it onto
your computer first, using any of these ways:

**Option 1 — Download just the one file (smallest).**
You don't need the whole repository to view the dashboard. Download the
single file (about 37 MB) from
`https://github.com/jastephan63/citygov/raw/main/dashboard.html`
(the browser will save it rather than show it), then double-click it. It
opens in any modern browser (Chrome, Edge, Firefox, Safari); the first load
takes a few seconds. `flows.html` (2 MB) can be fetched the same way.

**Option 2 — Download the ZIP (everything, no tools needed).**
Click the green **Code** button at the top of this page and choose
**Download ZIP**: about 170 MB to download, about 340 MB unpacked — 145 MB
of that is the original Formular files in `formulare/`. Unzip it and
double-click `dashboard.html`.

**Option 3 — Clone with git (best if you want updates).**
```bash
git clone https://github.com/jastephan63/citygov.git
```
About 200 MB to transfer and roughly 530 MB on disk, because the generated
files are committed together with their history. Then open `dashboard.html`
from the cloned folder. Later, `git pull` brings you the newest version.

**Option 4 — Serve it locally (if your browser is slow with the file).**
Some browsers handle a 37 MB page better over http than from a
double-clicked file. In the folder, run:
```bash
python3 -m http.server 8917
```
and open `http://localhost:8917/dashboard.html`. Any other static file
server works too.

`flows.html` (the guided questionnaires) opens the same way in every
option. `datentresor.db` opens with any SQLite client, for example
`sqlite3 datentresor.db` or DB Browser for SQLite.

The original Formular files (PDF/Word/Excel) are included in the
`formulare/` folder, so the «Quelldatei» links on Formular pages work when
you have the whole repository (options 2, 3 and 4). Only the single-file
download (option 1) lacks them — everything else in the dashboard works
there too.

## What the data covers

- **Services and Formulare.** The unit is the service as modelled in the
  canton's service model (DVSH). Formulare belong to services; a service can
  have several.
- **Data fields.** Each Formular's fields, broken down to atomic parts
  (Name, Vorname and Geburtsdatum separately, not just "Personalien").
- **Standards.** The eCH catalogue (290 standards, about 9,700 elements)
  plus eSH, a draft cantonal standard for everything eCH does not cover.
  eSH is always marked as a draft.
- **Legal bases.** Article-level citations per field, read from the official
  law texts (Schaffhauser Rechtsbuch, Fedlex), never from memory. A field
  without an explicit article is not automatically over-collection: the
  databank distinguishes "needed for the task" (KDSG Art. 4 Abs. 1 lit. b)
  from "neither a norm nor the task demands it".
- **Whose datum it is.** Each field records whether it describes a natural
  person, an organisation, a thing or an authority. Only a natural person's
  datum can be prefilled from the Einwohnerregister (once-only); a
  company's address cannot, even though it uses the same eCH element.
- **Legal remedies.** Per Verfahren: which Einsprache/Rekurs/Beschwerde a
  person has against the decision, with Frist and Instanz, quoted from the
  law PDF. Sectoral provisions where the cited law has its own; otherwise
  the general rule of the VRG, and the dashboard says which one it shows.
  A VRG default that no Prüfvermerk has yet confirmed is shown as exactly
  that — an unconfirmed default, not a verdict. The laws the DVSH model
  names count as candidates too: decisions of the Arbeitsinspektorat, for
  example, carry a Rekurs to the Regierungsrat within 30 days under the
  cantonal Verordnung zum Arbeitsgesetz (SHR 822.101), not the VRG default.
- **Code lists.** The official value lists from the eCH schemas (sex,
  marital status, residence permits, ...) and, per field, whether the form
  uses those codes or its own plain-text values.
- **Life events (Lebenslagen).** Services grouped the way people look for
  them, using the Themengruppen of the official Swiss topic catalogue
  eCH-0049 (approved; one catalogue for private persons, one for
  businesses). Many groups are life situations — birth, moving house, a
  death, unemployment, retirement, becoming self-employed — others are
  topics such as taxes or energy. Every group is checked in the official PDF
  (kept in `quellen/ech-0049/`) under its own Themenbereich. Per group: which
  services and offices a person meets, how many answers are asked, and where
  the services overlap on the same datum (same eCH element, same party, same
  named role; documents, remarks and mis-mapped fields are never matched).
  The overlap describes the offer, not one person's burden: services can be
  alternatives nobody goes through together.
- **One datum, one name (Begriffe).** For every datum with an eCH element
  that forms ask for under at least two labels: one proposed term (always a
  label that already exists in the forms, never an invented one) and each
  label classified as *angleichen* (same thing, different wording — rename
  in the form), *Rolle* (names whose or which datum, e.g. "Name
  Arbeitnehmer", "Adresse bisher" — fine as it is), *Feld aufteilen* (the
  field bundles data the standard keeps apart, e.g. "Strasse und Nr" — split
  it in the form) or *eCH-Zuordnung korrigieren* (the label means a
  different datum than the element the databank mapped it to — a databank
  fix, not the office's). Where no clean term exists, the proposal is marked
  *unter Vorbehalt* with its reason. Data asked under a single label are not
  checked yet, and the page says how many. Shown per Formular next to each
  field as well.
- **Standard divergences, per Formular.** For every form: which of its data
  are demanded differently than on the other forms — mandatory here but
  optional elsewhere, a different type or format for the same datum, its own
  value list where the standard defines codes — each with what this form
  does, what the rest of the corpus does, the field's legal basis (a
  different basis can justify the difference) and the concrete action. Kept
  apart from data that simply has no citable standard yet, which is a gap,
  not a divergence. Where the corpus itself is split with no clear practice,
  the form is not called the outlier: the entry says a cantonal decision is
  missing.
- **Handling rules.** 248 rules on storing, processing and disclosing
  personal data, from 8 data-protection laws and 36 sectoral laws. Every
  rule carries a quote checked word-for-word against the official law PDF.
  Retention periods are machine-readable, so deletion dates can be computed.
- **The register.** Per Formular: purpose, recipients, retention and DSFA
  status, structured like KDSG Art. 17b Abs. 2. (The duty to keep such a
  register applies under Art. 17b only to Polizei, Staatsanwaltschaft and
  Justizvollzug; for every other office the register here is a management
  tool, and the dashboard says so.)
- **Digitalisation.** Per Formular: submission channel, signature
  requirement, required enclosures, citizen effort, and what blocks a fully
  digital process.

The dashboard also has: a **Handlungsbedarf** board (every open point,
among them missing legal basis, purpose, recipients, DSFA decision, eCH
mapping, over-collection, a sensitive datum without a KDSG Art. 5 basis, a
superseded eCH standard, standard divergence, naming variant, outdated form,
overdue online check, undecided duplicate, unresolved remedy, unconfirmed
remedy default, unbacked Verfahren outcome, missing Schutzstufe — grouped by
the Dienststelle that can close it, with the office's contact and a CSV
export), a **Datenfluss** map (which Dienststelle passes data to which
recipient, from the article-backed disclosures), a **Bürgersicht** (what the
Datentresor holds about three synthetic persons, seen from their side), and a
search box over everything: laws, articles, fields, rules, recipients,
enclosures, standards, offices.

## How the data is verified

Machine-derived entries only enter the database through checks: a citation
must exist in an ingested law article, an eCH element must exist in the
official XSD, a rule quote must appear verbatim in the law PDF. Anything
that fails is rejected. Every citation shows its verification level, and
"not yet researched" is never mixed up with "proven to have no legal basis".
The databank currently holds 6,334 curated citations: 2,900 checked against
the live law text, 3,434 against the Schaffhauser Rechtsbuch PDF (the level is the
cited article's, one column for every surface), none
unverified. The DVSH model and the SHEP portal are the sources of truth for
service facts and were read strictly without changing anything.

The verdict files the loaders read (one JSON per Formular from the review
passes) are transient and are not kept in the repository. What they produced
is inspectable in the database itself: `data_field.derived_by`,
`last_checked` on `article` and `data_field_legal_basis`, the `panel_review`
table (2,168 second opinions, of which the newest are still marked «offen») and `begriff_vorschlag.herkunft`. The single
corrections that were verified by hand are kept under `quellen/korrekturen/`
and `quellen/rechtsmittel/`, with the script that applies them. One check a
peer can run: every article a field citation points to must carry a
`verified` or `Gesetze-PDF` level —

```sql
SELECT count(*) FROM data_field_legal_basis d JOIN article a ON a.id = d.article_id
WHERE a.last_checked NOT LIKE 'Gesetze-PDF%' AND a.last_checked NOT LIKE 'verified%';
-- 0
```

**Datenstand.** The dashboard's home page names the date each layer was
true, not only the build date. Currently: DVSH and SHEP harvest 2026-09-03;
last full online check of the Formulare against sh.ch 2026-07-31, with a
partial re-check on 2026-09-26 (98 Formulare: 91 confirmed current, 7
flagged as probably revised); eCH XSD sweep 2026-09-26 (116 standards looked
up, 82 of them publish their own XSD — the 104 files in `ech_xsd/`). 410 of the 474
Formulare have been checked online at all; for 312 of them the re-check is
overdue and 64 have never been checked — the Handlungsbedarf board lists
these as open points.

## The Datentresor

`datentresor.db` shows how the collected data could actually be stored:
1,200 synthetic residents, 10,000 cases, 184,778 stored values, and 19,142
further uses in later cases that reused an earlier value instead of asking
again (figures from the once-only ledger of the current build; the build
script prints them). The rules are enforced by the database itself: a
person's own datum is stored once and reused (once-only; a company's or an
authority's address is stored per case, not as the person's), sensitive
values (8,548 in this build) are AES-256-GCM encrypted with the key kept
outside the database, and triggers refuse unencrypted sensitive values,
wrong formats, hard deletes, any change to the access log, and any value
that carries neither an article, nor a consent (given only for proven
over-collection), nor an explicit label — «Aufgabenerfüllung» (needed for
the task), «aufgabennotwendig — Grundlage nach KDSG Art. 5 Abs. 1 noch nicht
benannt» (a besonders schützenswertes Datum whose Art.-5 basis is still
open), «Rechtsgrundlage zu ermitteln» or «Aufgabenbedarf noch nicht
beurteilt». An unresearched basis is therefore stored as a labelled gap,
never as consent: 136,479 values cite an article, 492 rest on consent,
47,807 carry one of those labels. Views answer the standard data-protection
questions directly: `v_auskunft`, `v_loeschliste`, `v_verzeichnis`.

`datentresor.key` is deliberately not in the repository. In the committed
`datentresor.db` the encrypted values therefore appear as `[verschlüsselt]`
in `v_auskunft` and cannot be decrypted. Rebuilding (`./build.sh --tresor`)
creates a fresh key locally and re-encrypts; it needs a Python with the
`cryptography` package (the project uses `.venv/bin/python3`, which
`build.sh` picks up automatically). Without it the build falls back to a
labelled demo cipher and records that in the `meta` table. The file is not
byte-reproducible because the AES-GCM nonces are random.

All data in it is synthetic. There is no real personal data anywhere in
this repository.

## Building

```bash
./build.sh            # every generated surface from citygov.db
./build.sh --tresor   # additionally rebuild datentresor.db
./build.sh --pdf      # additionally write dossiers/*.pdf
```

One command rebuilds everything in dependency order: `init_register.py`
(rewrites the derived table `canonical_attribute` and the derived column
`data_field.format_code` inside `citygov.db` — the only step that writes to
the database) → `export_json.py` (`data_export.json`) → `build_dashboard.py`
(`dashboard.html`) → `build_flows.py` (`flows.html`) → `export_llm.py` (the
`citygov_*` exports) → `export_ech_schema.py` (`citygov_ech_schemas.json`) →
`export_dossiers.py` (`dossiers/`) → `validate_db.py`. It prints the sizes
of `dashboard.html`, `flows.html`, `data_export.json` and `citygov_llm.json`
at the end, and writes `logs/citation_todo.txt` (every ingested law article
not yet at level `verified`) locally; `logs/` is not tracked.

Loading new data is a different job. The loaders under `scripts/`
(`load_*.py`, `ingest_*.py`, `sweep_ech_xsd.py`, `run_begriffe.py`) each
write to a staging copy, validate, and only then replace the database — a
failed load changes nothing. `scripts/README.md` gives their order, from the
law chain to the flows, and a one-line purpose for every Python script.

**Requirements.** Python 3. `./build.sh` itself needs only the standard
library, except `--tresor`, which needs the `cryptography` package, and
`--pdf`, which needs a local Chrome. The loaders and harvesters need `pypdf`
and `openpyxl`; the Datentresor build needs `cryptography` — all three are
in `requirements.txt`:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

`build.sh` uses `.venv/bin/python3` when it exists; run the loaders with it
too.

## Known gaps

- **Legal bases.** The 74 Formulare taken from the DVSH model have their
  standards mapping but not yet their article-level legal bases: 1,110
  fields on 75 Formulare are marked "zu ermitteln" — the 74 DVSH-sourced
  ones entirely (1,100 fields) plus 10 fields of one older form.
- **Cantonal decisions.** Schutzstufen and DSFA decisions are the canton's
  to make and stay empty until then.
- **Legal remedies.** A Verfahren outcome is modelled for 172 of the 474
  Formulare; the other 302 have none yet. Of the 172, 104 carry a quoted
  remedy — 20 from a sectoral provision, 84 the general VRG rule, and 31 of
  those 84 are still the default without a Prüfvermerk confirming that no
  sectoral provision applies. 28 end without an appealable decision, 16 have
  an outcome the DVSH text does not back (so the remedy question is not
  reached), and 24 have none: 18 were assessed and could not be decided from
  the cited law (mostly commercial-register and notarial acts under federal
  law), 6 have not been looked at yet. The dashboard says which is which.
- **Standards.** eSH is a draft and shrinks as eCH assignments take fields
  over. Where the corpus is split on how a datum is demanded, the entry asks
  for a cantonal decision instead of naming an outlier.
- **Naming.** Data asked under a single label are not checked for a common
  term yet; the Begriffe page says how many.
- **Currency.** 312 Formulare are overdue for their online re-check and 64
  have never been checked against sh.ch (see Datenstand above).
- **Guided flows** exist for 57 of the 474 Formulare.
- **Retired layer.** The auto-draft field layer of 2026-06 (tables
  `form_field`, `field_mapping`) is retired: it is no longer exported and the
  curated `data_field` layer replaced it. The tables stay in the database for
  the record.

The Handlungsbedarf board lists every open point by Dienststelle; the
dashboard shows each one where it occurs.

## Licence

Not decided yet. Until the rights holder chooses a licence, all rights to the
scripts, the schema, the database and the generated files are reserved — ask
before republishing. Independently of that choice: `formulare/` reproduces the
canton's official Formulare from sh.ch, and `ech_xsd/` and `quellen/ech-0049/`
reproduce eCH's schemas and catalogues from ech.ch (with their copyright
headers intact); those files stay under their publishers' own terms.
