#!/usr/bin/env python3
"""Moved to citygov/core/kennungen.py, its command line to citygov/load/kennungen_cli.py —
this wrapper keeps the old name working.

`python3 scripts/kennungen.py …` runs that command line as before (same arguments, same output,
same exit code), and `import kennungen` in a script under scripts/ gets citygov.core.kennungen.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(1, _ROOT)

if __name__ == "__main__":
    import runpy
    runpy.run_module("citygov.load.kennungen_cli", run_name="__main__")
else:
    import importlib
    sys.modules[__name__] = importlib.import_module("citygov.core.kennungen")
