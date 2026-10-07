#!/usr/bin/env python3
"""Runs citygov/load/kennungen_cli.py, the command line of citygov/core/kennungen.py, under the
command name scripts/kennungen.py.

`python3 scripts/kennungen.py …` runs that command line as __main__ with the arguments
untouched (its output, its exit code), and `import kennungen` in a script under scripts/ gets
citygov.core.kennungen. Every command under scripts/ is this same thin file; the code lives in
the package (scripts/README.md, «Adding a loader, a gate or a command»).
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
