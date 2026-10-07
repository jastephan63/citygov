"""citygov.domain — logic shared by the loaders and the exports, without side
effects on import: the parties of every data point (rollen) and the party
words of the Lebenslagen key (parteiwoerter), the register catalogue and the
register map with the prefill rule (register_katalog, register_map), the
change-impact index (wirkung), the concepts (konzepte), the law editions
(gesetz_stand, read side) and the law titles (gesetz_titel), the remedies
(rechtsmittel), the «Datum» verdicts (wortwahl) and the Gestaltung of the
Formulare (gestaltung_export, gestaltung_text, gestaltung_pdf,
gestaltung_office). Imports only core, checks and domain.

Importing the package imports gates, which adds the gates of the data-model
layers to citygov.checks.registry (validate_db runs them; the modules of the
gates are imported only when they run). A command line that needs the export
or the loaders lives there: load/gesetz_stand_cli, export/konzepte_cli,
export/gestaltung_export_cli, export/register_map_cli. Some modules here still
carry a command line of their own — rollen, register_katalog and
register_map.main_laden load their own tables, wirkung prints its index — and
it imports only core, checks and domain."""
from citygov.domain import gates      # noqa: F401  adds the data-model gates to citygov.checks.registry
