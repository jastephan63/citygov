"""citygov.checks — the integrity gate every loader runs on its staging copy
(validate_db). When it runs, validate() also calls the gates that still live
with their layers: rollen, gesetz_stand, register_map and konzepte (domain/)
and load_gesetz_titel (load/). These imports go against the layer order; they
sit inside datenmodell_checks() and stay until each gate is separated from its
module."""
