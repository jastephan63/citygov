# forms/ — local mirror of the source folder (not tracked)

`forms/` is a gitignored working copy. When new files are ingested,
`scripts/ingest_new.py` (and the retired `scripts/auto_draft.py` it still
imports) copy each ingested file from the canton's source folder
`../Verwaltung/<Department>/<Office>/` into the same sub-path here, so a
modelled Formular has a local twin of the file it was read from. Nothing in
this directory is in the repository except this README, and no build or
export step reads it; of the loaders, only `scripts/classify.py` and the
ingest step look at it.

The source files the databank actually points to are in `formulare/`: every
`form.source_file` (432 files) resolves there, and that folder is tracked so
the «Quelldatei» links in the dashboard work offline. The remaining 42
Formulare are eFormulare built from DVSH form definitions and have no file.

The widget extraction that once produced field proposals from a PDF in this
folder is retired to `scripts/deprecated/extract_form.py`; the curated
`data_field` layer replaced it (see `scripts/deprecated/README.md`).
