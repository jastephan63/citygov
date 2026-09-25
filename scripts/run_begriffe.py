#!/usr/bin/env python3
"""The Begriffe + Lebenslagen chain, in the only order that is correct.

Each step works on its own staging copy and swaps atomically; later steps
build on earlier ones (load_begriffe rebuilds all label rows, load_pruefart
resets all pruefart values, …), so running one of them alone would silently
undo the others. The later steps therefore refuse to run outside this chain.

    python3 scripts/run_begriffe.py <panel-base-dir>

<panel-base-dir> holds the panel outputs: begriffe/ pruefart/ vorschlag/
konsistenz/ rolle2/ themen/. The verified single corrections come from
quellen/korrekturen/ and are applied last.
"""
import glob, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


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
    for k in sorted(glob.glob(os.path.join(ROOT, "quellen", "korrekturen", "*.json"))):
        r = subprocess.run([sys.executable, os.path.join(HERE, "load_korrekturen.py"), k], env=env)
        if r.returncode:
            sys.exit(f"ABBRUCH in load_korrekturen.py ({k})")
    print("Begriffe-Kette vollständig.")


if __name__ == "__main__":
    main()
