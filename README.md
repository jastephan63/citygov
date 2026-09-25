# citygov — Compliance-Databank Kanton Schaffhausen

A database of the canton's administrative services. For each service it
records: the laws behind it (down to the article), the data its Formulare
collect (down to the single field), the standard each datum maps to (eCH, or
the draft cantonal standard eSH), the rules for handling that data (storage,
retention, disclosure), and how far the service is from being fully digital.

Gaps are shown as gaps. If a legal basis is missing or unverified, the
dashboard says so instead of hiding it.

## What is in here

| File | What it is |
|---|---|
| `citygov.db` | The main database (SQLite). Everything else is generated from it. |
| `dashboard.html` | The dashboard: per service its Verfahren, Formulare, data fields, legal bases, standards, handling rules and digitalisation status. |
| `flows.html` | Guided questionnaires: one step-by-step walkthrough per Formular. |
| `datentresor.db` | Example storage database with synthetic data (see below). |
| `dossiers/` | One printable Datenschutz-Dossier per service (480 HTML pages, ~1–2 A4 pages each), generated from the same data. Open `dossiers/index.html`, or reach a service's dossier from its page in the dashboard. The page has a print button; `scripts/export_dossiers.py --pdf` writes PDFs locally instead. |
| `citygov_llm.json` and the other `citygov_*` files | Machine-readable exports of the whole databank. |
| `ech_xsd/` | The official eCH XML schemas the element catalogue and code lists were read from. |
| `formulare/` | The original Formular files, so the «Quelldatei» links work offline. |
| `schema.sql` | The documented database schema. |
| `scripts/` | All loaders, harvesters and exporters. Retired tools sit in `scripts/deprecated/`. |

## Opening the dashboard on your computer

The dashboard is a single HTML file with all data built in. Nothing to
install, no server required, works offline. One thing does **not** work:
clicking the file on github.com — GitHub cannot preview a file this large.
Get it onto your computer first, using any of these ways:

**Option 1 — Download the ZIP (simplest, no tools needed).**
Click the green **Code** button at the top of this page, choose
**Download ZIP**, unzip it, and double-click `dashboard.html`. It opens in
any modern browser (Chrome, Edge, Firefox, Safari). The file is about
32 MB, so the first load takes a few seconds.

**Option 2 — Download just the one file.**
You don't need the whole repository to view the dashboard. Download the
single file from
`https://github.com/jastephan63/citygov/raw/main/dashboard.html`
(the browser will save it rather than show it), then double-click it.

**Option 3 — Clone with git (best if you want updates).**
```bash
git clone https://github.com/jastephan63/citygov.git
```
Then open `dashboard.html` from the cloned folder. Later, `git pull` brings
you the newest version.

**Option 4 — Serve it locally (if your browser is slow with the file).**
Some browsers handle a 32 MB page better over http than from a
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
you have the whole repository (options 1, 3 and 4). Only the single-file
download (option 2) lacks them — everything else in the dashboard works
there too, since all data, laws, rules and standards are inside the HTML
file itself.

## What the data covers

- **Services and Formulare.** The unit is the service as modelled in the
  canton's service model (DVSH). Formulare belong to services; a service can
  have several.
- **Data fields.** Each Formular's fields, broken down to atomic parts
  (Name, Vorname and Geburtsdatum separately, not just "Personalien").
- **Standards.** The full eCH catalogue (290 standards, 9,700 elements)
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
- **Code lists.** The official value lists from the eCH schemas (sex,
  marital status, residence permits, ...) and, per field, whether the form
  uses those codes or its own plain-text values.
- **Life events (Lebenslagen).** Services grouped the way people look for
  them, using the official Swiss topic catalogue eCH-0049 (approved; one
  catalogue for private persons — birth, moving house, a death,
  unemployment, retirement, animals, building … — and one for businesses).
  Every group name is checked word for word against the official PDF, kept
  in `quellen/ech-0049/`. Per life event: which services and offices a
  person meets, how many answers they give, how many of those are the SAME
  datum asked again by another service of the same situation, and how many
  the residents' register already holds. "Same datum" is recognised only via
  the eCH element; answers without a standard are counted separately.
- **One datum, one name (Begriffe).** For every datum with an eCH element:
  the labels under which the forms ask for it, one proposed term (always a
  label that already exists in the forms, never an invented one), and each
  label classified as *angleichen* (same thing, different wording — rename),
  *Rolle* (names whose datum, e.g. "Name Arbeitnehmer" — fine as it is) or
  one of two checks: *Feld aufteilen* (the field bundles data the standard
  keeps apart, e.g. "Strasse und Nr") or *eCH-Zuordnung prüfen* (the label
  means a different datum than the element it is mapped to). Where no clean
  term exists in any form, the proposal is marked *unter Vorbehalt* instead
  of inventing one. Shown per Formular next to each field as well.
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
- **Handling rules.** 247 rules on storing, processing and disclosing
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

The dashboard also has: a **Handlungsbedarf** board (every open point —
missing legal basis, purpose, recipients, DSFA decision, eCH mapping,
outdated form, undecided duplicate, unresolved remedy — grouped by the
Dienststelle that can close it, with the office's contact and a CSV
export), a **Datenfluss** map (which Dienststelle passes data to which
recipient, from the article-backed disclosures), a **Bürgersicht** (what the
Datentresor holds about one synthetic person, seen from their side), and a
search box over everything: laws, articles, fields, rules, recipients,
enclosures, standards, offices.

## How the data is verified

Machine-derived entries only enter the database through checks: a citation
must exist in an ingested law article, an eCH element must exist in the
official XSD, a rule quote must appear verbatim in the law PDF. Anything
that fails is rejected. Every citation shows its verification level, and
"not yet researched" is never mixed up with "proven to have no legal basis".
The DVSH model and the SHEP portal are the sources of truth for service
facts and were read strictly without changing anything.

## The Datentresor

`datentresor.db` shows how the collected data could actually be stored:
1,200 synthetic residents, 10,000 cases, about 186,000 stored values, with
15,000 more reused from an earlier case instead of asked again. The rules are enforced by
the database itself: a person's own datum is stored once and reused
(once-only; a company's or an authority's address is stored per case, not
as the person's), sensitive values are AES-256-GCM encrypted with the key
kept outside the database, and triggers block unencrypted sensitive values,
entries without a legal basis or consent, wrong formats, hard deletes and
any change to the access log. Views answer the standard data-protection
questions directly: `v_auskunft`, `v_loeschliste`, `v_verzeichnis`.

All data in it is synthetic. There is no real personal data anywhere in
this repository. Rebuild with `scripts/build_datentresor.py`.

## Building

```bash
./build.sh    # regenerates data_export.json and dashboard.html from citygov.db
```

Other generated outputs: `scripts/build_flows.py` (flows.html),
`scripts/export_llm.py` (the `citygov_*` exports),
`scripts/export_dossiers.py` (the dossiers; add `--pdf` for PDFs, which
needs a local Chrome), `scripts/build_datentresor.py` (datentresor.db),
`scripts/sweep_ech_xsd.py` (re-reads the eCH schemas from ech.ch).

All loaders write to a staging copy, validate, and only then replace the
database — a failed load changes nothing.

## Known gaps

The 74 newest Formulare (taken from the DVSH model) have their standards
mapping but not yet their article-level legal bases — 1,110 fields are
marked "zu ermitteln". Schutzstufen and DSFA decisions are the canton's to
make and are empty until then. Legal remedies are stated per Verfahren, but
24 procedures have none: 18 were assessed and could not be decided from the
cited law (mostly commercial-register and notarial acts under federal law),
6 have not been looked at yet — the dashboard says which is which. eSH is a
draft, and it shrinks as eCH assignments take fields over. The
Handlungsbedarf board lists every gap by Dienststelle; the dashboard shows
each one where it occurs.
