"""The gates of the data-model layers, added to the integrity gate when the package
citygov.domain is imported (citygov/domain/__init__.py imports this module).

validate_db (checks) sits below domain in the layer order; of domain it imports only the
package citygov.domain, once (the registry trigger, the one exception to the layer order),
never this module or another domain module by name: validate_db.datenmodell_checks() runs
`import citygov.domain`, whose __init__ imports this module, and then runs the gates
citygov.checks.registry holds. The function below is validate_db's former
datenmodell_checks(), moved unchanged except that the law-title gate now comes from
citygov.domain.gesetz_titel (it lived in load/load_gesetz_titel.py); it is called
datenmodell_gates() here, so the two functions do not share a name. It imports the
modules of the gates when it runs, as before, not when this module is imported:
importing citygov.domain stays cheap, and a module that runs as a script
(python3 scripts/rollen.py …) is not imported a second time before it starts.

A NEW GATE is registered here and nowhere else. The rule:
  - its check is a function pruefen(conn) in the domain module of its layer (core for the
    identifiers), never in load/: the loader in load/ imports it from there (as
    load/load_gesetz_titel.py imports domain/gesetz_titel.py);
  - the contract: gate(conn) returns a list of error strings, [] when the data is valid,
    and [] while its tables are absent (a staging copy of an older database);
  - it is called from this file: one more line in datenmodell_gates() below, or a function
    of its own here that imports the gate's module inside its body and is then passed to
    registry.add() at the end of this file;
  - registry.add() anywhere else is never seen by validate_db: when validate_db runs as a
    script or inside a loader, nothing imports that other module, so its gate would not run
    and bad data would pass (tests/test_gates.py: the static check of every registry.add()
    call and the list REGISTERED of the gates a fresh interpreter finds);
  - add its tampered case to tests/test_gates.py and its number to the list of gates in the
    docstring of citygov/checks/validate_db.py.
"""
from citygov.checks import registry


def datenmodell_gates(conn):
    """The gates of the data-model layers (2026-10), each in the domain module of its
    layer (the identifiers in core): permanent identifiers (kennungen.py), parties and
    roles (rollen.py), law editions (gesetz_stand.py) and registers with the prefill rule
    (register_map.py). Each returns [] while its tables are absent. Plus the structure of
    the curated concept file (konzepte.py), which the export reads, and the law titles
    (gesetz_titel.py)."""
    from citygov.core import kennungen
    from citygov.domain import rollen
    from citygov.domain import gesetz_stand
    from citygov.domain import register_map
    from citygov.domain import konzepte
    errors = []
    for gate in (kennungen.pruefen, rollen.pruefen, gesetz_stand.pruefen, register_map.pruefen):
        errors += gate(conn)
    try:
        errors += konzepte.datei_pruefen(konzepte.lade())
    except (OSError, ValueError) as ex:
        errors.append(f"quellen/konzepte.json is not readable: {type(ex).__name__}: {ex}")
    # law titles as the official PDF prints them (gesetz_titel; the loader is load_gesetz_titel.py)
    import re
    from citygov.domain import gesetz_titel
    errors += gesetz_titel.pruefen(conn)
    for lid, t, k in conn.execute("SELECT id, title, short_title FROM law"):
        for x in (t, k):
            if x and (re.search(r"\sVom\s+\d", x) or re.search(r"\s\*\s*$", x)):
                errors.append(f"law {lid}: «{x}» carries the edition line or the footnote marker «*» — "
                              "scripts/load_gesetz_titel.py --lesen, then apply")
    return errors


registry.add(datenmodell_gates)
