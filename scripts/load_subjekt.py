#!/usr/bin/env python3
"""Load the panel verdicts on WHOSE datum a field is (data_field.subjekt).

The once-only mark ("vorbefüllbar aus dem Einwohnerregister") used to be keyed
on the eCH element alone: eCH-0010 street is register data, so every street
field got the mark - including the address of a Betrieb, the Standort of a
vehicle and the Leitbehörde's Postfach. The Einwohnerregister holds none of
those. So the subject is now recorded per field and the mark (and the
prefillable count, and citygov_prefill.json) apply only where it is a natural
person's datum:

  natuerliche_person  organisation  sache  behoerde  gemischt

Gate: id must be a field that currently carries a register-marked unit (the
input set), verdict must use the vocabulary, reason present. 'gemischt' is the
conservative answer and gets no mark. Idempotent. Staging -> validate -> swap.

    python3 scripts/load_subjekt.py <dir-with-in_*.json-and-out_*.json>
"""
import glob, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

VOCAB = {"natuerliche_person", "organisation", "sache", "behoerde", "gemischt"}


def main():
    src = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    if "subjekt" not in {r[1] for r in c.execute("PRAGMA table_info(data_field)")}:
        c.execute("ALTER TABLE data_field ADD COLUMN subjekt TEXT")
    # the panel only saw the fields we asked about; anything else is rejected
    asked = set()
    for jf in glob.glob(os.path.join(src, "in_*.json")):
        asked |= {r["id"] for r in json.load(open(jf, encoding="utf-8"))}
    n = rejected = 0
    counts = {}
    for jf in sorted(glob.glob(os.path.join(src, "out_*.json"))):
        for v in json.load(open(jf, encoding="utf-8")).get("verdicts", []):
            fid, sj, why = v.get("id"), v.get("subjekt"), (v.get("grund") or "").strip()
            if fid not in asked or sj not in VOCAB or len(why) < 8:
                rejected += 1
                continue
            c.execute("UPDATE data_field SET subjekt=? WHERE id=?", [sj, fid])
            counts[sj] = counts.get(sj, 0) + 1
            n += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"subjekt: {n} Verdikte geladen {counts}, {rejected} REJECTED, "
          f"{len(asked)} Felder angefragt")


if __name__ == "__main__":
    main()
