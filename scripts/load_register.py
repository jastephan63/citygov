#!/usr/bin/env python3
"""Load the curated Verzeichnis layer — purposes, retention terms, recipients —
from agent output, PROOF-GATED like every other agent-written layer.

Gates:
  * purpose        — form must exist; 30-250 chars; not just the title again
  * retention_term — rule must exist with a retention aspect; a duration is
                     only accepted if its number literally appears in the
                     rule's PDF-verified quote or summary (digits or the
                     German number word), so no invented Frist can enter
  * disclosure     — rule must be a sectoral bekanntgabe rule; recipients are
                     then fanned out to every form whose fields cite that law,
                     carrying the rule's article for traceability

Idempotent (agent-derived rows are replaced wholesale). Staging -> validate -> swap.

    python3 scripts/load_register.py <out-dir>
"""
import glob, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

# German number words that appear in law texts, for the duration gate
WORDS = {1: ["ein", "eine", "einem"], 2: ["zwei"], 3: ["drei"], 4: ["vier"],
         5: ["fünf", "fuenf"], 6: ["sechs"], 7: ["sieben"], 8: ["acht"],
         9: ["neun"], 10: ["zehn"], 12: ["zwölf", "zwoelf"], 14: ["vierzehn"],
         15: ["fünfzehn"], 20: ["zwanzig"], 30: ["dreissig", "dreißig"],
         50: ["fünfzig", "fuenfzig"], 80: ["achtzig"], 100: ["hundert"]}


def norm(s):
    return re.sub(r"[^a-zäöüß0-9]+", " ", (s or "").lower()).strip()


def duration_in_text(value, text):
    t = norm(text)
    if re.search(rf"\b{value}\b", t):
        return True
    return any(w in t for w in WORDS.get(value, []))


def main():
    src = sys.argv[1]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    rejected = []

    # ---- purposes -----------------------------------------------------------
    titles = {r["id"]: r["title"] for r in c.execute("SELECT id, title FROM form")}
    np = 0
    for jf in sorted(glob.glob(os.path.join(src, "purposes_*.json"))):
        try:
            d = json.load(open(jf, encoding="utf-8"))
        except Exception:
            rejected.append(f"{os.path.basename(jf)}: unlesbar"); continue
        for p in d.get("purposes", []):
            fid, zweck = p.get("form_id"), (p.get("zweck") or "").strip()
            if fid not in titles:
                rejected.append(f"Zweck: Formular #{fid} fehlt"); continue
            if not 30 <= len(zweck) <= 250 or norm(zweck) == norm(titles[fid]):
                rejected.append(f"Zweck untauglich: #{fid}"); continue
            c.execute("UPDATE form SET purpose=? WHERE id=?", [zweck, fid])
            np += 1

    # ---- retention terms ----------------------------------------------------
    rules = {r["id"]: r for r in c.execute(
        "SELECT id, aspect, summary, quote FROM data_rule "
        "WHERE aspect IN ('aufbewahrung','loeschung','archivierung')")}
    c.execute("DELETE FROM retention_term")
    nt = 0
    tf = os.path.join(src, "retention_terms.json")
    if os.path.exists(tf):
        for t in json.load(open(tf, encoding="utf-8")).get("terms", []):
            rid = t.get("data_rule_id")
            r = rules.get(rid)
            if not r:
                rejected.append(f"Frist: Regel #{rid} ist keine Retention-Regel"); continue
            dv = t.get("duration_value")
            if dv is not None and not duration_in_text(int(dv), f"{r['quote']} {r['summary']}"):
                rejected.append(f"Frist: {dv} steht nicht im Zitat von Regel #{rid}"); continue
            c.execute("INSERT INTO retention_term(data_rule_id,duration_value,duration_unit,"
                      "min_or_max,trigger_event,disposition,last_checked) VALUES(?,?,?,?,?,?,?)",
                      [rid, dv, t.get("duration_unit"), t.get("min_or_max"),
                       (t.get("trigger_event") or "unbestimmt")[:40], t.get("disposition"),
                       "agent, Frist im Zitat verifiziert" if dv is not None else "agent"])
            nt += 1

    # ---- disclosures: rule recipients fanned out to the citing forms --------
    brules = {r["id"]: r for r in c.execute(
        "SELECT dr.id, dr.article_id, a.law_id FROM data_rule dr "
        "JOIN article a ON a.id=dr.article_id "
        "WHERE dr.aspect='bekanntgabe' AND dr.scope='sektoral'")}
    forms_by_law = {}
    for r in c.execute("SELECT DISTINCT d.form_id, a.law_id FROM data_field_legal_basis lb "
                       "JOIN data_field d ON d.id=lb.data_field_id "
                       "JOIN article a ON a.id=lb.article_id"):
        forms_by_law.setdefault(r["law_id"], set()).add(r["form_id"])
    c.execute("DELETE FROM form_disclosure WHERE last_checked LIKE 'agent%'")
    nd = 0
    df = os.path.join(src, "disclosures.json")
    if os.path.exists(df):
        for e in json.load(open(df, encoding="utf-8")).get("rules", []):
            r = brules.get(e.get("data_rule_id"))
            if not r:
                rejected.append(f"Empfänger: Regel #{e.get('data_rule_id')} ist keine "
                                "sektorale Bekanntgabe-Regel"); continue
            mode = e.get("mode") if e.get("mode") in ("systematisch", "auf_anfrage") else None
            for emp in e.get("empfaenger", []):
                emp = (emp or "").strip()
                if not 3 <= len(emp) <= 120:
                    rejected.append(f"Empfänger untauglich an Regel #{r['id']}"); continue
                for fid in forms_by_law.get(r["law_id"], []):
                    c.execute("INSERT OR IGNORE INTO form_disclosure(form_id,empfaenger,mode,"
                              "article_id,last_checked) VALUES(?,?,?,?,'agent (Regel-Zitat)')",
                              [fid, emp, mode, r["article_id"]])
                    nd += c.execute("SELECT changes() n").fetchone()["n"]

    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"register: {np} Zwecke, {nt} Fristen-Terme, {nd} Empfänger-Einträge, "
          f"{len(rejected)} REJECTED")
    for r in rejected[:10]:
        print("    rejected:", r)


if __name__ == "__main__":
    main()
