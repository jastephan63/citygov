#!/usr/bin/env python3
"""Moved to citygov/domain/gestaltung_export.py, its command line to citygov/export/gestaltung_export_cli.py —
this wrapper keeps the old name working.

`python3 scripts/gestaltung_export.py …` runs that command line as before (same arguments, same output,
same exit code), and `import gestaltung_export` in a script under scripts/ gets citygov.domain.gestaltung_export.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(1, _ROOT)

if __name__ == "__main__":
    import runpy
    runpy.run_module("citygov.export.gestaltung_export_cli", run_name="__main__")
else:
    import importlib
    sys.modules[__name__] = importlib.import_module("citygov.domain.gestaltung_export")
