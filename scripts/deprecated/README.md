# Deprecated scripts

Retired, not deleted — each of these did its job once and got superseded.
Kept for the record; git history has the full story.

- **parse_dvsh.py / load_dvsh.py** — the first DVSH harvest (text of the
  rendered admin pages, read page by page). Superseded by load_dvsh_harvest.py,
  which reads the modeller's own tRPC JSON in one pass.
- **add_dvsh_services.py** — added the DVSH-only service rows after the first
  harvest. load_dvsh_harvest.py now does this itself.
- **apply_dedup.py** — the one-off Formular dedup (newest-edition rule).
  Ran to completion; the Duplikat-Radar (build_similarity.py) watches now.
- **extract_form.py / propose_mapping.py / resolve_cited.py / verify_cited.py**
  — the auto-draft proposal era: widget extraction, auto mapping, citation
  resolution. Superseded by the curated data_field layer with proof-gated
  loaders. (auto_draft.py and commit_proposal.py stay in scripts/ because
  ingest_new.py still imports them.) Their `proposals/` folder was removed
  on 2026-10-01: its last seed predated the formulare/ paths and would have
  duplicated a Formular if replayed; git history keeps it.
- **fetch_missing_forms.py / search_missing_forms.py** — the sh.ch missing-
  forms hunt (CMS full-text search + web search). Collection is complete;
  the scripted method (sh.ch CMS full-text search via `/CMS/lists/list?filter_text=`
  and `get/file/<uuid>` download) is described in the two scripts' docstrings. The
  `docs.tsv` bulk index they consume was built once by hand and is not reproduced here.
- **recover_fields.py** — copied a backup's field set onto a re-edited Formular
  (2026-08). It predates the eSH, basis_typ, subjekt and Schutzstufe columns
  (it copies 15 of today's data_field columns) and the beilage foreign key
  (its DELETE fails for a form with Beilagen). The «only the newest edition»
  rule therefore has no working tool today: port this one to the current
  data_field and data_subfield columns before a field set is moved again.
- **fix_quality.py** — the 2026-06 quality pass over weak form titles and
  the legacy `form_field` labels, re-derived from the PDFs. The curated
  `data_field` layer has its own names; the pass would also overwrite a
  service name taken from DVSH and stops on an eFormular (no file).
- **annotate_pdf.swift / ocr_pdf.swift** — macOS PDFKit/Vision helpers of the
  2026-06 field-label recovery: render each page with the AcroForm widgets
  outlined and named, and OCR a scanned page. Nothing in the build calls them.

«Convention N» in these scripts refers to the working rules of their time
(2026-06 to 2026-08), not to the current list in scripts/README.md → Conventions.

Note: these still point their sys.path at their own folder; to actually run
one again, move it back to scripts/ first.
