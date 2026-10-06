#!/usr/bin/env python3
"""Moved to citygov/present/leitfaden.py — this wrapper keeps the old name working.

`python3 scripts/leitfaden.py …` runs that module as before (same arguments, same output,
same exit code), and `import leitfaden` in a script under scripts/ gets that very module.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(1, _ROOT)

if __name__ == "__main__":
    import runpy
    runpy.run_module("citygov.present.leitfaden", run_name="__main__")
else:
    import importlib
    sys.modules[__name__] = importlib.import_module("citygov.present.leitfaden")
