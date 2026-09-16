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
- **Handling rules.** 247 rules on storing, processing and disclosing
  personal data, from 8 data-protection laws and 41 sectoral laws. Every
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
1,200 synthetic residents, 10,000 cases, about 167,000 stored values of
which 20,000 were reused instead of asked again. The rules are enforced by
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
mapping but not yet their article-level legal bases — about 1,100 fields
are marked "zu ermitteln". Schutzstufen and DSFA decisions are the
canton's to make and are empty until then. Legal remedies are stated per
Verfahren, but for 19 register-type procedures under federal law none
could be assigned with proof. eSH is a draft. The Handlungsbedarf board
lists every gap by Dienststelle; the dashboard shows each one where it
occurs.
