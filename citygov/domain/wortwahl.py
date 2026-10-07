"""Wortwahl «Datum»: the reviewed verdicts of quellen/wortwahl_datum.json.

lade() reads the reviewed rewrites («ersetzen») and the texts in which «Datum» really is
a calendar date («behalten») and stops on an entry that contradicts itself; offen()
lists the texts that still say «Datum» without a verdict. load/apply_wortwahl.py applies
the rewrites; export/export_json.py refuses to export a naming or basis text that
offen() returns. Moved unchanged from load/apply_wortwahl.py (whose docstring describes
the scope). Reads the file only when called; standard library only.
"""
import json, os, re, sys
from citygov.core import common

ROOT = common.ROOT                     # the repository root
SRC = os.path.join(ROOT, "quellen", "wortwahl_datum.json")
DATUM = re.compile(r"\bDatums?\b")


def lade():
    K = json.load(open(SRC, encoding="utf-8"))
    ersetzen = {e["alt"]: e["neu"] for e in K["ersetzen"]}
    behalten = set(K["behalten"])
    for a, n in ersetzen.items():
        if a == n or not n.strip():
            sys.exit(f"ABBRUCH: leere oder unveränderte Ersetzung: {a[:80]}")
        if "ß" in n:
            sys.exit(f"ABBRUCH: «ß» in der Ersetzung: {n[:80]}")
    doppelt = behalten & set(ersetzen)
    if doppelt:
        sys.exit(f"ABBRUCH: sowohl behalten als auch ersetzt: {sorted(doppelt)[:3]}")
    return ersetzen, behalten


def offen(texte, behalten):
    """Texts that still say «Datum» without a verdict (as the website shows them)."""
    return sorted({t for t in texte if t and DATUM.search(t) and t not in behalten})
