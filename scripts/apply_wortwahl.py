#!/usr/bin/env python3
"""Runs citygov/load/apply_wortwahl.py under the command name scripts/apply_wortwahl.py.

`python3 scripts/apply_wortwahl.py …` runs that module as __main__ with the arguments untouched
(its output, its exit code), and `import apply_wortwahl` in a script under scripts/ gets that
very module. Every command under scripts/ is this same thin file; the code lives in the package
(scripts/README.md, «Adding a loader, a gate or a command»).
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(1, _ROOT)

if __name__ == "__main__":
    import runpy
    runpy.run_module("citygov.load.apply_wortwahl", run_name="__main__")
else:
    import importlib
    sys.modules[__name__] = importlib.import_module("citygov.load.apply_wortwahl")
