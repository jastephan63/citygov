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

The package __init__ files stay light, and that is a rule, not only a habit:
`python3 -m unittest` (discovery from the repository root) imports this file and
the __init__ of every layer before tests/__init__.py points CITYGOV_DB at a
private copy, and citygov.core.common reads CITYGOV_DB once, when it is first
imported. So no __init__ here, and nothing one of them imports at module level
(today only domain/gates.py and checks/registry.py), may import
citygov.core.common; tests/test_layers.py holds it.

Not every dependency is an import, so the layer test cannot see these:
  - core/theme.py reads the files of present by path (the four page generators
    and assets/) for `theme.py --check`;
  - some loaders start other commands through their wrappers under scripts/, as
    before the move: run_begriffe (its chain of load_* steps and
    apply_wortwahl), ingest_laws, ingest_fed, load_data_rules and
    load_themenkatalog (extract_law.py), scan_gestaltung (the self-tests of
    gestaltung_text, gestaltung_pdf, gestaltung_office) — so those wrappers
    carry load (tests/test_wrappers.py checks that every one they name exists);
  - domain/rollen.py reads the source text of domain/parteiwoerter.py (PARTY)
    by path instead of importing it.

The package root holds the one entry point, `python3 -m citygov <command>`
(__main__.py, cli.py: build, validate, load <name>, list, check-pages, test);
it imports no layer and starts every command through its wrapper under
scripts/. The tests are in tests/ at the repository root (python3 -m unittest);
tests/test_layers.py holds the order above.
"""
__version__ = "0.1.0"
