#!/usr/bin/env python3
"""Load data-governance rules (how personal data may be stored, treated and
communicated) from agent output into the data_rule table, PROOF-GATED.

A rule is one article's statement about the handling of personal data —
retention, processing limits, who it may be disclosed to, security duties,
the rights of the person concerned. Two gates keep invented law out:
  * the cited article must already exist in the article table (whose rows
    were themselves read from the official PDFs), otherwise REJECTED;
  * the verbatim quote must literally appear in the law's local PDF text,
    otherwise REJECTED. Only when no local PDF exists at all is a rule
    accepted without a quote, marked quote_verified=0.

Scopes decide which data fields a rule reaches at export time:
  allgemein                - every personal-data field (general DSG/KDSG law)
  besonders_schuetzenswert - fields flagged sensitive (optionally one category)
  sektoral                 - fields of forms grounded in the same law

Idempotent per law: all previous rules of a law being loaded are replaced.
Staging -> validate -> swap.

    python3 scripts/load_data_rules.py <out-dir> [<out-dir> ...]
"""
import glob, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate

HERE = os.path.dirname(os.path.abspath(__file__))
# the law PDFs live in the Gesetze folder NEXT TO the repo, not inside it
GESETZE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "Gesetze")

ASPECTS = {"erhebung", "bearbeitung", "speicherung", "aufbewahrung", "bekanntgabe",
           "sicherheit", "betroffenenrechte", "archivierung", "loeschung"}
SCOPES = {"allgemein", "besonders_schuetzenswert", "sektoral"}
CATEGORIES = {"gesundheit", "politik", "religion_weltanschauung", "sozialhilfe",
              "strafen_verfahren"}

DDL = """
CREATE TABLE IF NOT EXISTS data_rule (
    id                 INTEGER PRIMARY KEY,
    article_id         INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,
    aspect             TEXT NOT NULL,
    scope              TEXT NOT NULL,
    sensitive_category TEXT,
    summary            TEXT NOT NULL,
    quote              TEXT,
    quote_verified     INTEGER NOT NULL DEFAULT 0,
    last_checked       TEXT
);
CREATE INDEX IF NOT EXISTS ix_data_rule_article ON data_rule(article_id);
"""


def normtext(s):
    """Collapse whitespace so a quote can be matched against PDF line breaks."""
    return re.sub(r"\s+", " ", (s or "")).strip()


def law_pdf(sr, level):
    """Locate the local PDF for a law: Bund/<SR>.pdf or <SHR>-*.pdf."""
    if not sr:
        return None
    if level == "federal":
        p = os.path.join(GESETZE, "Bund", sr + ".pdf")
        return p if os.path.exists(p) else None
    hits = sorted(glob.glob(os.path.join(GESETZE, sr + "-*.pdf")))
    return hits[0] if hits else None


_text_cache = {}

def pdf_text(path):
    if path not in _text_cache:
        try:
            out = subprocess.run(["python3", os.path.join(HERE, "extract_law.py"), path],
                                 capture_output=True, text=True, timeout=120).stdout
        except Exception:
            out = ""
        t = normtext(out)
        # also keep a dehyphenated variant: PDFs break words as "Daten- bearbeitung"
        _text_cache[path] = (t, t.replace("- ", ""))
    return _text_cache[path]


def main():
    srcs = [a for a in sys.argv[1:] if not a.startswith("-")]
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)

    by_sr = {r["sr_number"]: r for r in c.execute(
        "SELECT id, sr_number, jurisdiction_level FROM law WHERE sr_number IS NOT NULL")}
    by_id = {r["id"]: r for r in c.execute("SELECT id, sr_number, jurisdiction_level FROM law")}

    rules, involved, rejected = [], set(), []
    for src in srcs:
        for jf in sorted(glob.glob(os.path.join(src, "*.json"))):
            try:
                d = json.load(open(jf, encoding="utf-8"))
            except Exception:
                rejected.append(f"{os.path.basename(jf)}: unlesbar")
                continue
            for z in d.get("regeln", []):
                law = by_id.get(z.get("law_id")) or by_sr.get(str(z.get("law") or "").strip())
                if not law:
                    rejected.append(f"Gesetz unbekannt: {z.get('law') or z.get('law_id')}")
                    continue
                art_no = normtext(z.get("artikel"))
                a = c.execute("SELECT id FROM article WHERE law_id=? AND article_no=?",
                              [law["id"], art_no]).fetchone()
                if not a:
                    rejected.append(f"Artikel fehlt: {law['sr_number'] or law['id']} {art_no}")
                    continue
                aspect, scope = z.get("aspect"), z.get("scope")
                cat = z.get("sensitive_category") or None
                if aspect not in ASPECTS or scope not in SCOPES or (cat and cat not in CATEGORIES):
                    rejected.append(f"Vokabular: {art_no} {aspect}/{scope}/{cat}")
                    continue
                summary = normtext(z.get("summary"))
                if len(summary) < 15:
                    rejected.append(f"Summary fehlt: {art_no}")
                    continue
                quote, verified = normtext(z.get("quote")), 0
                pdf = law_pdf(law["sr_number"], law["jurisdiction_level"])
                if pdf:
                    # with a local PDF the quote MUST be found in it, or the rule dies
                    if not quote:
                        rejected.append(f"Zitat fehlt (PDF vorhanden): {law['sr_number']} {art_no}")
                        continue
                    full, dehyph = pdf_text(pdf)
                    if quote not in full and quote.replace("- ", "") not in dehyph:
                        rejected.append(f"Zitat nicht im PDF: {law['sr_number']} {art_no}")
                        continue
                    verified = 1
                else:
                    quote = quote or None
                rules.append((a["id"], law["id"], aspect, scope, cat, summary[:400], quote, verified))
                involved.add(law["id"])

    # replace all rules of every law we have fresh output for (idempotent re-run)
    for lid in involved:
        c.execute("DELETE FROM data_rule WHERE article_id IN "
                  "(SELECT id FROM article WHERE law_id=?)", [lid])
    seen = set()
    n = 0
    for aid, lid, aspect, scope, cat, summary, quote, verified in rules:
        k = (aid, aspect, scope, cat)
        if k in seen:
            continue
        seen.add(k)
        c.execute("INSERT INTO data_rule(article_id, aspect, scope, sensitive_category,"
                  " summary, quote, quote_verified, last_checked)"
                  " VALUES(?,?,?,?,?,?,?, 'agent+PDF-Zitat')",
                  [aid, aspect, scope, cat, summary, quote, verified])
        n += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    nv = sum(1 for r in rules if r[7])
    print(f"data_rule: {n} Regeln aus {len(involved)} Gesetzen "
          f"({nv} mit PDF-verifiziertem Zitat), {len(rejected)} REJECTED")
    if rejected:
        from collections import Counter
        for k, v in Counter(rejected).most_common(10):
            print(f"    rejected: {k}" + (f" ({v}x)" if v > 1 else ""))


if __name__ == "__main__":
    main()
