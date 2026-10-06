"""citygov — the databank of the Kanton Schaffhausen that links the laws to the
Formulare, as one package.

Layers (an import goes only to the left: core ← checks ← domain ← load / export ← present):

    core     paths (ROOT, DB_PATH with CITYGOV_DB / CITYGOV_SCHEMA), the database
             connection, the text helpers, labels, theme, key figures, identifiers
    checks   the integrity gate (validate_db)
    domain   logic shared by the loaders and the exports
    load     loaders, harvesters, scans, sweeps, migrations
    export   the machine-readable exports
    present  the pages (dashboard, flows, dossiers, start page)

Every module of scripts/ now lives here (scripts/check_pages.mjs and the
retired scripts/deprecated/ stay where they are). Every command keeps its old
name: scripts/<name>.py is a thin wrapper that runs the module with the same
arguments, the same output and the same exit code, and `import <name>` in a
script under scripts/ gets the module itself. Importing the package loads
nothing but this file.
"""
__version__ = "0.1.0"
