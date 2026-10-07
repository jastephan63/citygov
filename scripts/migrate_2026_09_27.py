#!/usr/bin/env python3
"""Runs citygov/load/migrate_2026_09_27.py under the command name scripts/migrate_2026_09_27.py.

`python3 scripts/migrate_2026_09_27.py …` runs that module as __main__ with the arguments
untouched (its output, its exit code), and `import migrate_2026_09_27` in a script under
scripts/ gets that very module. Every command under scripts/ is this same thin file; the code
lives in the package (scripts/README.md, «Adding a loader, a gate or a command»).
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(1, _ROOT)

if __name__ == "__main__":
    import runpy
    runpy.run_module("citygov.load.migrate_2026_09_27", run_name="__main__")
else:
    import importlib
    sys.modules[__name__] = importlib.import_module("citygov.load.migrate_2026_09_27")
