#!/usr/bin/env python3
"""Moved to citygov/domain/konzepte.py, its command line to citygov/export/konzepte_cli.py —
this wrapper keeps the old name working.

`python3 scripts/konzepte.py …` runs that command line as before (same arguments, same output,
same exit code), and `import konzepte` in a script under scripts/ gets citygov.domain.konzepte.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(1, _ROOT)

if __name__ == "__main__":
    import runpy
    runpy.run_module("citygov.export.konzepte_cli", run_name="__main__")
else:
    import importlib
    sys.modules[__name__] = importlib.import_module("citygov.domain.konzepte")
