"""citygov.checks — the integrity gate every loader runs on its staging copy
(validate_db) and the registry of the gates that live with their layers
(registry). checks imports nothing from load, export or present, and from
domain only the package citygov.domain, once: validate_db.datenmodell_checks()
runs `import citygov.domain` (the registry trigger, the one exception to the
layer order). That package's __init__ loads citygov/domain/gates.py, which adds
the gates of the data-model layers (kennungen, rollen, gesetz_stand,
register_map, konzepte, gesetz_titel) to the registry, and
datenmodell_checks() runs them. checks imports no other domain module. A new
gate is added to the registry in citygov/domain/gates.py and nowhere else
(registry.py says why)."""
