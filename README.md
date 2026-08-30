# citygov — Kanton Schaffhausen Compliance-Databank

A machine-readable databank of the cantonal administration's **Formulare**: which
laws govern each form (down to the article), which data fields it collects, how
each datum maps to the official **eCH** e-government standards (and to the draft
cantonal **eSH** standard where eCH has no coverage), whether our copy is the
current edition, and a guided, TurboTax-style flow for filling each form out.

## Start here

| File | What it is |
|---|---|
| `dashboard.html` | Compliance view — all Formulare with data fields, legal bases (with quotes), eCH/eSH badges, currency checks, DVSH panels. Opens directly in a browser. |
| `flows.html` | Guided-flow view — per Formular the field→question mapping and a clickable "Ausprobieren" walkthrough with help sidebar. |
| `citygov.db` | The single source of truth (SQLite). Everything else is generated. |
| `citygov_llm.json` / `citygov_datafields.jsonl` | LLM-ready exports with trust rules and provenance. |
| `CLAUDE.md` | Working conventions and the operating loop (for the AI agent maintaining this repo). |

Both dashboards are self-contained (no server needed). If a preview tool balks at
the file size, serve the folder: `python3 -m http.server 8917`.

## Numbers (as of the last build)
~400 Formulare · ~10,400 atomic data points · 74 % mapped to eCH elements ·
25 draft eSH standards covering the rest · 381 forms verified current online.

## Regenerating
```
./build.sh                      # data_export.json + dashboard.html
python3 scripts/build_flows.py  # flows.html
python3 scripts/export_llm.py   # LLM exports
```
Source PDFs live outside the repo (../Verwaltung) by design; the DB records their
paths and hashes.
