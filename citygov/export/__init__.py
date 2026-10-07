"""citygov.export — the machine-readable exports (export_json, export_llm,
export_ech_schema, export_vertrag) and the two other files derived from
citygov.db: the synthetic Datentresor (build_datentresor) and the past days of
verlauf.json (backfill_verlauf). Also the command lines that build the export
in memory: konzepte_cli, gestaltung_export_cli and register_map_cli (the
commands of scripts/konzepte.py, gestaltung_export.py and register_map.py).
Imports core, checks, domain and export only — never load."""
