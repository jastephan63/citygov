"""The gates the higher layers hand to the integrity gate (validate_db).

checks sits below domain in the layer order (core <- checks <- domain <- load / export
<- present). Of domain, validate_db imports only the package citygov.domain, once
(`import citygov.domain` inside datenmodell_checks: the registry trigger, the one exception
to the layer order), and no other domain module. A layer that holds gates adds them here
when it is imported: citygov/domain/__init__.py imports citygov.domain.gates, which adds
the gates of the data-model layers. validate_db.datenmodell_checks() then runs every gate
in the order added.

The list lives in this module, never in validate_db: validate_db also runs as a script
(python3 scripts/validate_db.py), and a list kept there would exist twice, once in
__main__ and once in the imported module, so a gate added to the one would be missing
from the other.
"""

_GATES = []


def add(gate):
    """Add gate(conn) -> [error, ...] to the gates validate_db runs (once, in the order added)."""
    if gate not in _GATES:
        _GATES.append(gate)
    return gate


def gates():
    """The gates added so far, in the order added."""
    return list(_GATES)
