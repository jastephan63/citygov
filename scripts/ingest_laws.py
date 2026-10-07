#!/usr/bin/env python3
"""Runs citygov/load/ingest_laws.py under the command name scripts/ingest_laws.py.

`python3 scripts/ingest_laws.py …` runs that module as __main__ with the arguments untouched
(its output, its exit code), and `import ingest_laws` in a script under scripts/ gets that very
module. Every command under scripts/ is this same thin file; the code lives in the package
(scripts/README.md, «Adding a loader, a gate or a command»).
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(1, _ROOT)

if __name__ == "__main__":
    import runpy
    runpy.run_module("citygov.load.ingest_laws", run_name="__main__")
else:
    import importlib
    sys.modules[__name__] = importlib.import_module("citygov.load.ingest_laws")
