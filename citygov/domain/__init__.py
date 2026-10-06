"""citygov.domain — logic shared by the loaders and the exports, without side
effects on import: the parties of every data point (rollen), the register
catalogue and the register map with the prefill rule (register_katalog,
register_map), the change-impact index (wirkung), the concepts (konzepte),
the law editions (gesetz_stand) and the Gestaltung of the Formulare
(gestaltung_export, gestaltung_text, gestaltung_pdf, gestaltung_office).
Moved as whole modules: several still carry their own loader entry point
(main), and konzepte, register_map and gestaltung_export still import
export.export_json inside a function, register_katalog load.init_register and
gesetz_stand load.extract_law, until that logic is split."""
