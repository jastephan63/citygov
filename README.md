# citygov — Compliance-Databank Kanton Schaffhausen

A machine-readable databank of the canton's administrative services: which
**laws** govern each service (down to the article), which **data** its
Formulare collect (down to the atomic subfield), which **standard** every
datum maps to (eCH, or the cantonal draft standard eSH where eCH has none),
how that data **must be handled** — storage, retention, disclosure, the
person's rights — and how far each service is from being **fully digital**.

The consumer is both people and software: everything is exported in
LLM-ready form so an automated caseworker could one day administer these
services against verifiable rules. That sets the bar for the data: precise,
auditable, and never silently wrong. Gaps are shown as gaps — a fake
"100 % compliant" would be a defect, not a success.

## What is in here

| Artifact | What it is |
|---|---|
| `citygov.db` | The single source of truth (SQLite). Everything else is generated from it. |
| `dashboard.html` | The compliance dashboard: per service — Verfahren, Formulare, data fields with legal basis and standard, handling profile, digitalisation blockers; plus corpus tabs (rule corpus, plain-language Leitfaden, processing register per KDSG Art. 17b, data catalogue, eSH draft catalogue). Self-contained, opens from file. |
| `flows.html` | The guided-flow dashboard: per Formular a conversational, TurboTax-style walkthrough with help texts, once-only prefill and eCH-JSON export. |
| `datentresor.db` | An applied example of how the collected data would actually be **stored**: 1,200 synthetic residents, 10,000 Fälle, 142k datapoints — with the compliance rules enforced by the database itself (see below). All data synthetic. |
| `citygov_llm.json`, `citygov_*.jsonl`, `citygov_verzeichnis.json`, `citygov_prefill.json`, `citygov_ech_schemas.json` | The LLM/exchange exports: nested service model, flat field records, the verified rule corpus, the processing register, the once-only prefill map, and per-Formular eCH exchange schemas. |
| `schema.sql` | The documented database schema, layer by layer. |
| `scripts/` | Every loader, harvester, generator and exporter. `scripts/deprecated/` holds retired tooling with a README saying what replaced each piece. |

## The data model, layer by layer

- **Services and Formulare.** The unit is the *service* as modelled in the
  canton's own service model (DVSH); Formulare are its children, several per
  service where reality demands it. Services the model has not covered yet
  are kept and marked as such — never force-fitted.
- **Data fields and subfields.** Each Formular's logical data dictionary,
  down to atomic parts: "Personalien" is a composite; Name, Vorname and
  Geburtsdatum each carry their own standard element.
- **Standards.** The full eCH catalogue (290 standards, 9.7k XSD elements,
  including approval status — some standards are drafts or repealed), plus
  **eSH**, our draft cantonal standard covering every datum eCH misses.
  eSH never shadows eCH and is labelled *Entwurf* everywhere.
- **Legal bases.** Article-level citations per data field, read from the
  official law texts (Schaffhauser Rechtsbuch, Fedlex) — never typed from
  memory, and carrying their verification level openly.
- **Data handling rules.** 247 rules on storing, processing and disclosing
  personal data, extracted from 8 governance laws (KDSG, KDSV, ISV, ArchivV,
  DSG, DSV, BGA, EMBAG) and 41 sectoral laws — every rule with a verbatim
  quote mechanically verified against the official law PDF. Retention rules
  are additionally machine-readable (duration, trigger, disposition), so a
  deletion date can be computed, not just cited.
- **The register layer.** Per Formular: purpose, recipients (article-backed),
  retention, DSFA triage — the contents of the processing register the KDSG
  demands, with missing pieces marked *fehlt* instead of papered over.
- **The Verfahren layer.** Submission channel, signature requirement (with
  evidence from the PDF itself), demanded enclosures with their holder
  (documents the state already holds are once-only candidates), the
  procedure's outcome, citizen burden, and named digitalisation blockers.
- **The data catalogue.** The ~3,000 unique data points behind 140k+ field
  instances — the master-data view that makes once-only measurable.

## How the data earns trust

Three rules run through everything:

1. **Proof gates.** Machine-assisted mappings are only accepted by loaders
   that verify them against reality: a citation must exist in an ingested
   article, an eCH element must exist in the official XSD, a rule quote must
   appear verbatim in the law PDF, a retention duration must appear in its
   quote, an enclosure must be traceable to its source. Everything else is
   rejected — invented references cannot enter the databank.
2. **Verification levels are visible.** Every citation shows whether it was
   verified live against Fedlex/Rechtsbuch, read from the official PDF, or
   is still unverified. "Not yet researched" and "proven baseless"
   (over-collection) are strictly different states and never conflated.
3. **Sources of truth stay untouched.** The DVSH service model and the SHEP
   portal are harvested strictly read-only and treated as the correct
   version of service-level facts. The two dated harvest snapshots live in
   `../DVSH/` outside this repo.

## The Datentresor (applied storage example)

`datentresor.db` demonstrates the rules as running constraints instead of
documentation. All data is synthetic (generated residents; says so in its
`meta` table). The storage unit is the canonical attribute — once-only, so a
later Fall references an existing datum instead of re-collecting it (67,927
reuses in the shipped build). Sensitive values are AES-256-GCM-encrypted at
rest, with the key kept outside the database (and outside git). Seven
database triggers refuse: unencrypted sensitive values, datapoints without a
legal basis or consent, values violating their standard's format, hard
deletes, and any edit of the access log — provable from any SQLite client.
Views answer the DSG questions directly from the data: `v_auskunft` (a
person's full dossier with citations and deletion dates), `v_loeschliste`,
`v_verzeichnis`.

Rebuild it with `scripts/build_datentresor.py` (a local Python venv with the
`cryptography` package gives real AES; without it the build falls back to a
clearly labelled demo cipher).

## Building

```bash
./build.sh          # regenerates data_export.json + dashboard.html from citygov.db
```

`scripts/` contains the full pipeline: ingesting Formulare and laws,
deriving data dictionaries, assigning standards, loading the rule and
register layers, harvesting DVSH/SHEP, and the exporters. Every loader is
idempotent and writes copy-then-swap: it works on a staging copy, validates,
and only then replaces `citygov.db` — a failed load leaves the databank
untouched.

## Honest limitations

Documented rather than hidden: some legal bases are still *zu ermitteln*;
Schutzstufen and DSFA decisions are the canton's to make and stay empty until
then; the eSH standard is a draft, not an official one; Rechtsmittel data
waits for a dedicated pass over the VRG; and the newest Formulare still lack
their standards mapping. The dashboard shows each of these gaps where it
occurs.

No real personal data exists anywhere in this repository.
