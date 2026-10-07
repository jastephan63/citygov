"""The gates the higher layers hand to the integrity gate (validate_db).

checks sits below domain in the layer order (core <- checks <- domain <- load / export
<- present). Of domain, validate_db imports only the package citygov.domain, once
(`import citygov.domain` inside datenmodell_checks: the registry trigger, the one exception
to the layer order), and no other domain module. citygov/domain/__init__.py imports
citygov.domain.gates, which adds the gates of the data-model layers here.
validate_db.datenmodell_checks() then runs every gate in the order added.

The rule for a new gate: add() is called in citygov/domain/gates.py and nowhere else.
The gate is a function there that imports its module inside its body (or one more line
in gates.datenmodell_gates()), and that function is passed to add() at the end of
gates.py. An add() in the gate's own module is never seen by validate_db: when
validate_db runs as a script or inside a loader, nothing imports that module, so the
gate would not run and bad data would pass as valid. The contract: gate(conn) returns a
list of error strings, [] when the data is valid, and [] while its tables are absent.
tests/test_gates.py checks that every add() call is in gates.py and that a fresh
interpreter finds exactly the gates of its list REGISTERED.

The list lives in this module, never in validate_db: validate_db also runs as a script
(python3 scripts/validate_db.py), and a list kept there would exist twice, once in
__main__ and once in the imported module, so a gate added to the one would be missing
from the other.
"""

_GATES = []


def add(gate):
    """Add gate(conn) -> [error, ...] to the gates validate_db runs (once, in the order added).
    Called only in citygov/domain/gates.py (see the module docstring)."""
    if gate not in _GATES:
        _GATES.append(gate)
    return gate


def gates():
    """The gates added so far, in the order added."""
    return list(_GATES)
