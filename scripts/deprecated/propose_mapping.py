#!/usr/bin/env python3
"""Auto-propose field -> requirement mappings for a modelled proposal (convention 5).

Given a proposal that already has BOTH form_fields and requirements (the law side
modelled by a human), heuristically classify each unmapped field and, where it
plausibly captures a requirement, attach a mapping. EVERY mapping produced here is
match_status='proposed', mapped_by='auto' — proposals, never confirmed facts. A
human reviews, flips the real ones to 'confirmed', fixes the rest, then commits.

Heuristics (deliberately conservative — when unsure, leave for the human):
  * form_mechanic  : signature/date/place/page/stamp plumbing.
  * identity_part  : Name/Vorname/Geburtsdatum/AHV-Nr. when a composite requirement
                     exists -> mapped to that composite requirement.
  * reason_facet   : a checkbox when an enum requirement (Grund/Zweck/...) exists
                     -> mapped to it.
  * mapped         : token-overlap with a requirement's data_point above threshold.
  * overcollection : a real field that matched nothing (a PROPOSED finding to review).

    python3 scripts/propose_mapping.py proposals/<slug>.extracted.json
"""
import argparse
import json
import re
from collections import Counter

MECHANIC = re.compile(r"unterschrift|signature|\bdatum\b|\bort\b|seite|page|stempel|"
                      r"place here|hier unterschreiben", re.I)
IDENTITY = {"name", "vorname", "nachname", "geburtsdatum", "geburtsdat",
            "ahv", "ahv-nr", "ahvnr", "ahv-nummer", "personalien"}
REASON_HINT = re.compile(r"grund|zweck|gesuchsgrund|art des|kategorie", re.I)


def toks(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proposal")
    args = ap.parse_args()
    with open(args.proposal, encoding="utf-8") as fh:
        p = json.load(fh)

    reqs = p.get("requirements", [])
    composite = next((r for r in reqs if r.get("is_composite")), None)
    enum_reqs = [r for r in reqs if (r.get("data_type") == "enum"
                                     or REASON_HINT.search(r.get("data_point", "")))]

    existing = {m["form_field_ref"] for m in p.get("field_mappings", [])}
    proposed = []
    for fld in p.get("form_fields", []):
        if fld["ref"] in existing:
            continue
        label = fld.get("label", "")
        lt = toks(label) | toks(fld.get("field_key", ""))

        # 1. form mechanic
        if MECHANIC.search(label) or fld.get("field_type") == "signature":
            proposed.append(_m(fld, None, "form_mechanic", 0.6, "plumbing")); continue
        # 2. identity part
        if composite and (lt & IDENTITY):
            proposed.append(_m(fld, composite["ref"], "identity_part", 0.8,
                               f"identity sub-field of '{composite['data_point']}'")); continue
        # 3. reason facet (checkbox under an enum requirement)
        if fld.get("field_type") == "checkbox" and enum_reqs:
            proposed.append(_m(fld, enum_reqs[0]["ref"], "reason_facet", 0.55,
                               f"option of '{enum_reqs[0]['data_point']}'")); continue
        # 4a. exact / substring normalized match (handles German compounds)
        nl = norm(label) or norm(fld.get("field_key"))
        exact = next((r for r in reqs
                      if nl and (nl == norm(r.get("data_point"))
                                 or nl == norm(r.get("data_point_key"))
                                 or (len(nl) >= 5 and (nl in norm(r.get("data_point"))
                                                       or norm(r.get("data_point")) in nl)))), None)
        if exact:
            proposed.append(_m(fld, exact["ref"], "mapped", 0.95,
                               f"normalized match with '{exact['data_point']}'")); continue
        # 4b. best token-overlap mapped
        best, score = None, 0.0
        for r in reqs:
            rt = toks(r.get("data_point")) | toks(r.get("data_point_key")) | toks(r.get("label"))
            if not rt:
                continue
            ov = len(lt & rt) / max(1, len(lt | rt))
            if ov > score:
                best, score = r, ov
        if best and score >= 0.34:
            proposed.append(_m(fld, best["ref"], "mapped", round(score, 2),
                               f"token overlap with '{best['data_point']}'"))
        else:
            # 5. nothing matched -> propose over-collection for human review
            proposed.append(_m(fld, None, "overcollection", 0.3,
                               "no requirement matched — review: real over-collection?"))

    p.setdefault("field_mappings", []).extend(proposed)
    out = args.proposal.replace(".extracted.json", "").replace(".json", "") + ".mapped.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(p, fh, ensure_ascii=False, indent=2)

    c = Counter(m["classification"] for m in proposed)
    print(f"wrote {out}")
    print(f"  proposed {len(proposed)} mapping(s): " +
          ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
    print("  ALL are status=proposed/auto — review and confirm before commit (conv 5).")


def _m(fld, req_ref, classification, conf, note):
    return {"form_field_ref": fld["ref"], "requirement_ref": req_ref,
            "classification": classification, "match_status": "proposed",
            "mapped_by": "auto", "confidence": conf, "notes": note}


if __name__ == "__main__":
    main()
