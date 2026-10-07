#!/usr/bin/env python3
"""Moved to citygov/domain/gesetz_stand.py, its command line to citygov/load/gesetz_stand_cli.py —
this wrapper keeps the old name working.

`python3 scripts/gesetz_stand.py …` runs that command line as before (same arguments, same output,
same exit code), and `import gesetz_stand` in a script under scripts/ gets citygov.domain.gesetz_stand.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(1, _ROOT)

if __name__ == "__main__":
    import runpy
    runpy.run_module("citygov.load.gesetz_stand_cli", run_name="__main__")
else:
    import importlib
    sys.modules[__name__] = importlib.import_module("citygov.domain.gesetz_stand")
