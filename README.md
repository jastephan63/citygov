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
| `citygov_llm.json` and the other `citygov_*` files | Machine-readable exports of the whole databank. |
| `schema.sql` | The documented database schema. |
| `scripts/` | All loaders, harvesters and exporters. Retired tools sit in `scripts/deprecated/`. |

## Opening the dashboard on your computer

The dashboards are single HTML files with all data built in. No server, no
install, no internet needed.

1. Click the green **Code** button above and choose **Download ZIP**, then
   unzip it. (Or `git clone https://github.com/jastephan63/citygov.git`.)
2. Double-click `dashboard.html`. It opens in any modern browser. The file
   is about 32 MB, so the first load takes a few seconds. `flows.html`
   opens the same way.
3. If your browser struggles with the file size, run
   `python3 -m http.server 8917` in the folder and open
   `http://localhost:8917/dashboard.html`.

Note: GitHub cannot preview files this large, so download first. The
«Quelldatei» links on Formular pages point to files on the original working
machine and will not open elsewhere; everything else works offline.
`datentresor.db` opens with any SQLite client.

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
  law texts (Schaffhauser Rechtsbuch, Fedlex), never from memory.
- **Handling rules.** 247 rules on storing, processing and disclosing
  personal data, from 8 data-protection laws and 41 sectoral laws. Every
  rule carries a quote checked word-for-word against the official law PDF.
  Retention periods are machine-readable, so deletion dates can be computed.
- **The register.** Per Formular: purpose, recipients, retention and DSFA
  status — the processing register the KDSG requires.
- **Digitalisation.** Per Formular: submission channel, signature
  requirement, required enclosures, citizen effort, and what blocks a fully
  digital process.

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
1,200 synthetic residents, 10,000 cases, 142,000 stored values. The rules
are enforced by the database itself: a person's datum is stored once and
reused (once-only), sensitive values are AES-256-GCM encrypted with the key
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

All loaders write to a staging copy, validate, and only then replace the
database — a failed load changes nothing.

## Known gaps

Some legal bases are still marked "zu ermitteln". Schutzstufen and DSFA
decisions are the canton's to make and are empty until then. eSH is a
draft. The newest Formulare still lack their standards mapping. The
dashboard shows each gap where it occurs.
