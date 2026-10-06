#!/usr/bin/env python3
"""The Begriffe + Lebenslagen chain, in the only order that is correct.

Each step works on its own staging copy and swaps atomically; later steps
build on earlier ones (load_begriffe rebuilds all label rows, load_pruefart
resets all pruefart values, …), so running one of them alone would silently
undo the others. The later steps therefore refuse to run outside this chain.

    python3 scripts/run_begriffe.py <panel-base-dir>

<panel-base-dir> holds the panel outputs: begriffe/ pruefart/ vorschlag/
konsistenz/ rolle2/ themen/. The verified naming corrections come from the
quellen/korrekturen/ files that carry begriff_label, begriff_vorschlag or
service_thema (the only keys load_korrekturen.py reads; today
begriffe*.json — the other files there feed other loaders) and are applied
last, followed by the reviewed reader wording (scripts/apply_wortwahl.py).
"""
import glob, json, os, subprocess, sys

from citygov.core import common

HERE = os.path.join(common.ROOT, "scripts")   # runs the chain as scripts/<step>.py, as before the move
ROOT = os.path.dirname(HERE)
# the top-level keys load_korrekturen.py applies
KORREKTUR_KEYS = {"begriff_label", "begriff_vorschlag", "service_thema"}


def korrektur_files():
    """quellen/korrekturen/*.json that load_korrekturen.py understands, sorted."""
    out = []
    for k in sorted(glob.glob(os.path.join(ROOT, "quellen", "korrekturen", "*.json"))):
        d = json.load(open(k, encoding="utf-8"))
        if isinstance(d, dict) and KORREKTUR_KEYS & set(d):
            out.append(k)
    return out


def main():
    base = sys.argv[1]
    steps = [("load_begriffe.py", "begriffe"), ("load_pruefart.py", "pruefart"),
             ("load_vorschlag_check.py", "vorschlag"), ("load_begriff_konsistenz.py", "konsistenz"),
             ("load_begriff_rollen.py", "rolle2"), ("load_themen.py", "themen")]
    env = dict(os.environ, BEGRIFFE_CHAIN="1")
    for script, sub in steps:
        src = os.path.join(base, sub)
        if not os.path.isdir(src):
            sys.exit(f"ABBRUCH: {src} fehlt")
        r = subprocess.run([sys.executable, os.path.join(HERE, script), src], env=env)
        if r.returncode:
            sys.exit(f"ABBRUCH in {script} — die vorherigen Schritte sind gespeichert, die folgenden nicht gelaufen")
    for k in korrektur_files():
        r = subprocess.run([sys.executable, os.path.join(HERE, "load_korrekturen.py"), k], env=env)
        if r.returncode:
            sys.exit(f"ABBRUCH in load_korrekturen.py ({k})")
    # the reviewed reader wording («Angabe», not «Datum» for a piece of data) —
    # the steps above rebuild those texts from the panel outputs
    r = subprocess.run([sys.executable, os.path.join(HERE, "apply_wortwahl.py")], env=env)
    if r.returncode:
        sys.exit("ABBRUCH in apply_wortwahl.py")
    print("Begriffe-Kette vollständig.")


if __name__ == "__main__":
    main()
