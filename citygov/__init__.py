"""citygov — the databank of the Kanton Schaffhausen that links the laws to the
Formulare, as one package.

Layers (an import goes only to the left, with the one exception named below:
core ← checks ← domain ← load / export ← present):

    core     paths (ROOT, DB_PATH with CITYGOV_DB / CITYGOV_SCHEMA), the database
             connection, the text helpers, labels, theme, key figures, identifiers
    checks   the integrity gate (validate_db) and the registry of the gates
             that live with the higher layers (registry)
    domain   logic shared by the loaders and the exports (and the gates the
             integrity gate runs through citygov.checks.registry)
    load     loaders, harvesters, scans, sweeps, migrations
    export   the machine-readable exports
    present  the pages (dashboard, flows, dossiers, start page); their HTML
             templates, stylesheets and scripts are files under present/assets/

The order holds for every import, at module level and inside functions, with
one exception, the registry trigger: the integrity gate runs gates that live in
domain, which domain adds to citygov.checks.registry when the package
citygov.domain is imported, and validate_db.datenmodell_checks() imports that
package once (`import citygov.domain`; its __init__ loads domain/gates.py).
checks imports no other domain module. A command line that needs a higher
layer than its module lives in that layer as <module>_cli (load/kennungen_cli,
load/gesetz_stand_cli, export/konzepte_cli, export/gestaltung_export_cli,
export/register_map_cli).

Every module of scripts/ now lives here (scripts/check_pages.mjs and the
retired scripts/deprecated/ stay where they are). Every command keeps its old
name: scripts/<name>.py is a thin wrapper that runs the module (or its
<module>_cli) with the same arguments, the same output and the same exit code,
and `import <name>` in a script under scripts/ gets the module itself.
Importing the package loads nothing but this file.

The package root holds the one entry point, `python3 -m citygov <command>`
(__main__.py, cli.py: build, validate, load <name>, list, check-pages, test);
it imports no layer and starts every command through its wrapper under
scripts/. The tests are in tests/ at the repository root (python3 -m unittest);
tests/test_layers.py holds the order above.
"""
__version__ = "0.1.0"
