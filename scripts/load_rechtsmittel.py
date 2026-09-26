#!/usr/bin/env python3
"""Rechtsmittel per Verfahren, proven against the law PDFs.

Two layers, kept apart so the dashboard can say which one it shows:

  allgemein  the general rule of the VRG (SHR 172.200): Anordnungen einer
             unteren Verwaltungsbehörde oder eines Departements -> Rekurs an
             den Regierungsrat (Art. 16 Abs. 1), innert 20 Tagen (Art. 20
             Abs. 1). VRG Art. 1 says it applies "soweit nicht abweichende
             Vorschriften bestehen" - so this is the fallback, never the last
             word, and every surface says so.
  sektoral   what the law a form actually cites says itself (Einsprache an
             die Veranlagungsbehörde, Beschwerde nach ATSG, ...), found by the
             panel in the official PDF.

Gates (nothing enters without them):
  * the quote must be found verbatim in the official PDF text (whitespace
    collapsed, PDF hyphenation removed) - same check as the data rules
  * a Frist in days must appear in the quote as digits or number word — or in
    frist_quote, a second verbatim sentence when the Frist stands in its own Absatz
  * the article row must exist for that law, or is created from the verified
    quote (the PDF is the proof), never from memory
  * vocabulary for rechtsmittel_art

Application to form_outcome: a form gets the sektoral rule of the law its
fields cite most (a 'verweis' to the VRG resolves to the general rule); with
no sektoral rule, decisions of the kinds bewilligung/verfuegung/bestaetigung/
auszahlung get the general VRG rule, marked quelle='allgemein'. A
registereintrag without a sektoral rule stays open (federal register law has
its own remedies; guessing would be wrong), kein_entscheid gets none.

    python3 scripts/load_rechtsmittel.py <dir-with-out_*.json>   (dir optional)
"""
import glob, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DB_PATH, connect
from validate_db import validate
from load_data_rules import law_pdf, pdf_text, normtext

VOCAB = {"einsprache", "rekurs", "beschwerde", "verwaltungsgerichtsbeschwerde", "verweis"}
WORDS = {3: ["drei"], 5: ["fünf", "fuenf"], 10: ["zehn"], 14: ["vierzehn"], 15: ["fünfzehn"],
         20: ["zwanzig"], 30: ["dreissig", "dreißig", "30"], 60: ["sechzig"], 90: ["neunzig"]}
APPLICABLE = ("bewilligung", "verfuegung", "bestaetigung", "auszahlung")

DDL = """
CREATE TABLE IF NOT EXISTS rechtsmittel_regel (
    id               INTEGER PRIMARY KEY,
    law_id           INTEGER NOT NULL REFERENCES law(id),
    article_id       INTEGER NOT NULL REFERENCES article(id),
    scope            TEXT NOT NULL CHECK(scope IN ('allgemein','sektoral')),
    rechtsmittel_art TEXT NOT NULL CHECK(rechtsmittel_art IN
        ('einsprache','rekurs','beschwerde','verwaltungsgerichtsbeschwerde','verweis')),
    frist_tage       INTEGER,
    frist_article_id INTEGER REFERENCES article(id),
    frist_quote      TEXT,
    instanz          TEXT,
    gilt_fuer        TEXT,
    quote            TEXT NOT NULL,
    quote_verified   INTEGER NOT NULL DEFAULT 0,
    hinweis          TEXT,
    last_checked     TEXT,
    UNIQUE(law_id, article_id, rechtsmittel_art)
);
"""

# the general rule, quoted from the VRG PDF; verified like every other quote
VRG_SHR = "172.200"
VRG_REKURS = ("Art. 16", "Anordnungen einer unteren Verwaltungsbehörde oder eines Departements, durch "
              "welche über den Ausstand oder die Zuständigkeit entschieden oder eine Sache erledigt "
              "worden ist, können durch Rekurs an den Regierungsrat weitergezogen werden, sofern die "
              "Weiterzugsmöglichkeit nicht ausdrücklich ausgeschlossen ist.")
VRG_FRIST = ("Art. 20", "Der Rekurs ist innert 20 Tagen nach der Mitteilung oder, mangels einer solchen, "
             "nach der Kenntnisnahme der angefochtenen Anordnung bei der Rekursinstanz schriftlich "
             "einzureichen.")


def quote_ok(quote, pdf):
    """Verbatim in the PDF? Compare whitespace-collapsed and dehyphenated."""
    if not pdf:
        return False
    q = normtext(quote)
    t, t2 = pdf_text(pdf)
    return q in t or q.replace("- ", "") in t2 or q in t2


def frist_ok(days, quote):
    if days is None:
        return True
    t = re.sub(r"[^a-zäöüß0-9]+", " ", quote.lower())
    if re.search(rf"\b{int(days)}\b", t):
        return True
    if any(w in t for w in WORDS.get(int(days), [])):
        return True
    # months: "innert 3 Monaten" / "drei Monaten" for 90 days etc.
    if days % 30 == 0 and "monat" in t:
        m = days // 30
        return bool(re.search(rf"\b{m}\b", t)) or any(w in t for w in WORDS.get(m, []))
    return False


def art_key(no):
    return re.sub(r"\s+", "", (no or "").lower().replace("art.", "").replace("§", ""))



def cited_laws(c):
    """form_id -> {law_id: weight}: the laws a form's fields cite (weight = number
    of citing fields) plus the cantonal laws the DVSH model names as the
    service's Rechtsgrundlage (weight 1, only where not already cited). The
    DVSH model is authoritative for legal bases, so a remedy provision of a law
    it names is a candidate even before the field-level legal pass reached the
    form. Federal DVSH references carry Fedlex URLs without SR numbers and are
    not resolved here."""
    cited = {}
    for r in c.execute("SELECT d.form_id, a.law_id, COUNT(*) n FROM data_field_legal_basis lb "
                       "JOIN data_field d ON d.id=lb.data_field_id JOIN article a ON a.id=lb.article_id "
                       "GROUP BY d.form_id, a.law_id"):
        cited.setdefault(r["form_id"], {})[r["law_id"]] = r["n"]
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='dvsh_service'").fetchone():
        return cited
    by_ref = {r["cantonal_ref"]: r["id"] for r in c.execute("SELECT id, cantonal_ref FROM law WHERE cantonal_ref IS NOT NULL")}
    for r in c.execute("SELECT f.id form_id, v.recht_kantonal FROM form f JOIN dvsh_service v ON v.service_id=f.service_id "
                       "WHERE v.recht_kantonal IS NOT NULL"):
        try:
            refs = json.loads(r["recht_kantonal"])
            if isinstance(refs, str):
                refs = json.loads(refs)
        except Exception:
            continue
        for ref in refs if isinstance(refs, list) else []:
            nr = (ref or {}).get("ssr_nummer") if isinstance(ref, dict) else None
            lid = by_ref.get("SHR " + str(nr).strip()) if nr else None
            if lid:
                cited.setdefault(r["form_id"], {}).setdefault(lid, 1)
    return cited


def find_or_add_article(c, law_id, article_no, heading, quote, nr):
    rows = c.execute("SELECT id, article_no, heading FROM article WHERE law_id=?", [law_id]).fetchall()
    for r in rows:
        if art_key(r["article_no"]) == art_key(article_no):
            return r["id"], False
    c.execute("INSERT INTO article(law_id, article_no, heading, text_excerpt, last_checked) "
              "VALUES(?,?,?,?,?)", [law_id, article_no, heading or None, quote[:600], f"Gesetze-PDF {nr}"])
    return c.execute("SELECT last_insert_rowid()").fetchone()[0], True


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    st = DB_PATH + ".staging"
    if os.path.exists(st):
        os.remove(st)
    shutil.copy2(DB_PATH, st)
    c = connect(st)
    c.executescript(DDL)
    cols = {r[1] for r in c.execute("PRAGMA table_info(form_outcome)")}
    if "rechtsmittel_regel_id" not in cols:
        c.execute("ALTER TABLE form_outcome ADD COLUMN rechtsmittel_regel_id INTEGER REFERENCES rechtsmittel_regel(id)")
        c.execute("ALTER TABLE form_outcome ADD COLUMN rechtsmittel_quelle TEXT")
    # rule ids are STABLE across runs (the verdict table points at them):
    # rules are upserted on (law, article, art), never deleted and re-created
    c.execute("UPDATE form_outcome SET rechtsmittel_regel_id=NULL, rechtsmittel_quelle=NULL")
    laws = {r["id"]: dict(r) for r in c.execute(
        "SELECT id, jurisdiction_level, sr_number, cantonal_ref, short_title FROM law")}

    def pdf_of(l):
        nr = l["sr_number"] or (l["cantonal_ref"] or "").replace("SHR ", "").strip()
        return law_pdf(nr, l["jurisdiction_level"]), nr

    # --- 1. the general VRG rule ---------------------------------------------
    vrg = next(l for l in laws.values() if (l["cantonal_ref"] or "").endswith(VRG_SHR))
    vpdf, _ = pdf_of(vrg)
    if not (quote_ok(VRG_REKURS[1], vpdf) and quote_ok(VRG_FRIST[1], vpdf)
            and frist_ok(20, VRG_FRIST[1])):
        os.remove(st); print("ABORT: VRG-Zitate nicht im PDF verifizierbar"); sys.exit(1)
    a16, _ = find_or_add_article(c, vrg["id"], VRG_REKURS[0], "Weiterziehbare Anordnung", VRG_REKURS[1], "SHR " + VRG_SHR)
    a20, _ = find_or_add_article(c, vrg["id"], VRG_FRIST[0], "Rekursfrist", VRG_FRIST[1], "SHR " + VRG_SHR)
    c.execute("INSERT INTO rechtsmittel_regel(law_id, article_id, scope, rechtsmittel_art, "
              "frist_tage, frist_article_id, frist_quote, instanz, gilt_fuer, quote, quote_verified, hinweis, last_checked) "
              "VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?) ON CONFLICT(law_id, article_id, rechtsmittel_art) DO UPDATE SET "
              "frist_tage=excluded.frist_tage, frist_article_id=excluded.frist_article_id, frist_quote=excluded.frist_quote, "
              "instanz=excluded.instanz, gilt_fuer=excluded.gilt_fuer, quote=excluded.quote, hinweis=excluded.hinweis, "
              "last_checked=excluded.last_checked",
              [vrg["id"], a16, "allgemein", "rekurs", 20, a20, VRG_FRIST[1], "Regierungsrat",
               "Anordnungen einer unteren Verwaltungsbehörde oder eines Departements",
               VRG_REKURS[1],
               "Allgemeine Regel des VRG; gilt nach Art. 1 nur, soweit nicht abweichende Vorschriften in andern Gesetzen, Dekreten oder Verordnungen bestehen",
               f"Gesetze-PDF SHR {VRG_SHR}"])
    general_id = c.execute("SELECT id FROM rechtsmittel_regel WHERE scope='allgemein'").fetchone()[0]

    # --- 2. the sektoral rules from the panel, gated --------------------------
    n = rejected = added_arts = 0
    why = {}
    for jf in sorted(glob.glob(os.path.join(src, "out_*.json"))) if src else []:
        for r in json.load(open(jf, encoding="utf-8")).get("rules", []):
            l = laws.get(r.get("law_id"))
            art = (r.get("rechtsmittel_art") or "").strip().lower()
            q = (r.get("quote") or "").strip()
            fq = (r.get("frist_quote") or "").strip() or None   # the Frist sentence, when it is a
            days = r.get("frist_tage")                            # separate Absatz (like VRG Art. 16 + 20)
            reason = None
            if not l: reason = "law"
            elif art not in VOCAB: reason = "vocab"
            elif len(q) < 40: reason = "quote-short"
            else:
                pdf, nr = pdf_of(l)
                if not quote_ok(q, pdf): reason = "quote-not-in-pdf"
                elif fq and not quote_ok(fq, pdf): reason = "frist-quote-not-in-pdf"
                elif days is not None and not frist_ok(days, fq or q): reason = "frist-not-in-quote"
            if reason:
                rejected += 1; why[reason] = why.get(reason, 0) + 1
                continue
            pdf, nr = pdf_of(l)
            aid, new = find_or_add_article(c, l["id"], r.get("article_no") or "UNKNOWN",
                                           r.get("heading"), q, nr)
            added_arts += new
            # the second review may have CORRECTED this provision's art (e.g.
            # rekurs -> beschwerde). Re-inserting the panel's original art would
            # add a second row for the same article and resurrect the mistake,
            # so a reviewed provision keeps the reviewed art.
            rev = c.execute(
                "SELECT rr.rechtsmittel_art FROM rechtsmittel_regel rr "
                "JOIN panel_review p ON p.kind='rmrule' AND p.item_id=rr.id "
                "WHERE rr.law_id=? AND rr.article_id=? AND p.urteil IN ('korrigiert','streichen')",
                [l["id"], aid]).fetchone() if c.execute(
                "SELECT 1 FROM sqlite_master WHERE name='panel_review'").fetchone() else None
            if rev:
                art = rev["rechtsmittel_art"]
            c.execute("INSERT INTO rechtsmittel_regel(law_id, article_id, scope, rechtsmittel_art, "
                      "frist_tage, frist_article_id, frist_quote, instanz, gilt_fuer, quote, quote_verified, hinweis, last_checked) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?) ON CONFLICT(law_id, article_id, rechtsmittel_art) DO UPDATE SET "
                      "frist_tage=excluded.frist_tage, frist_article_id=excluded.frist_article_id, frist_quote=excluded.frist_quote, "
                      "instanz=excluded.instanz, gilt_fuer=excluded.gilt_fuer, "
                      "quote=excluded.quote, hinweis=excluded.hinweis, last_checked=excluded.last_checked",
                      [l["id"], aid, "sektoral", art, int(days) if days is not None else None,
                       aid if fq else None, fq,
                       (r.get("instanz") or None), (r.get("gilt_fuer") or None), q,
                       (r.get("hinweis") or None), f"Gesetze-PDF {nr}"])
            n += 1

    # --- 3. apply to every form's outcome ------------------------------------
    # provisions that only regulate suspensive effect or filing formalities are
    # kept (they are real, verified law) but never chosen as THE remedy
    if "gestrichen" not in {r[1] for r in c.execute("PRAGMA table_info(rechtsmittel_regel)")}:
        c.execute("ALTER TABLE rechtsmittel_regel ADD COLUMN gestrichen INTEGER NOT NULL DEFAULT 0")
    # a provision the second review struck (not a person's remedy) stays as
    # evidence but is never applied
    rules = [dict(r) for r in c.execute("SELECT * FROM rechtsmittel_regel WHERE scope='sektoral' AND gestrichen=0")]
    def usable(r):
        h = (r["hinweis"] or "").lower() + " " + (r["gilt_fuer"] or "").lower()
        return not any(w in h for w in ("aufschiebende wirkung", "suspensiv", "nur die aufschiebende",
                                          "einreichungsort", "filing place", "nicht benannt"))
    RANK = {"einsprache": 0, "rekurs": 1, "beschwerde": 2, "verwaltungsgerichtsbeschwerde": 3, "verweis": 9}
    by_law = {}
    for r in rules:
        if usable(r):
            by_law.setdefault(r["law_id"], []).append(r)
    cited = cited_laws(c)   # form_id -> {law_id: weight}
    # Which of a law's provisions governs THIS form's decision is a judgment
    # (GesG Art. 49 Abs. 2 covers Proben, not every Verfügung); it is made by a
    # verdict pass (load_rechtsmittel_verdicts.py), never by ranking. Here the
    # mechanical part only: a law with exactly ONE usable remedy of its own is
    # unambiguous; a verweis to the VRG resolves to the general rule; anything
    # else falls back to the general rule and keeps its candidates visible.
    # a verdict that names a provision the review STRUCK is void — the struck
    # provision is not a person's remedy, so the form falls back to 'offen'
    verdicts = {r["form_id"]: r for r in c.execute(
        "SELECT v.form_id, v.regel_id, CASE WHEN v.quelle='sektoral' AND "
        "COALESCE((SELECT rr.gestrichen FROM rechtsmittel_regel rr WHERE rr.id=v.regel_id),0)=1 "
        "THEN 'offen' ELSE v.quelle END quelle FROM rechtsmittel_verdikt v")} if c.execute(
        "SELECT 1 FROM sqlite_master WHERE name='rechtsmittel_verdikt'").fetchone() else {}
    rule_by_id = {r["id"]: r for r in rules}
    applied = {"sektoral": 0, "allgemein": 0, "offen": 0, "keins": 0, "verdikt": 0}
    for o in c.execute("SELECT form_id, entscheid_art FROM form_outcome").fetchall():
        fid, kind = o["form_id"], o["entscheid_art"]
        pick, quelle = None, None
        v = verdicts.get(fid)
        if v and v["quelle"] == "sektoral" and v["regel_id"] in rule_by_id:
            pick, quelle = rule_by_id[v["regel_id"]], "sektoral"; applied["verdikt"] += 1
        elif v and v["quelle"] == "allgemein" and kind in APPLICABLE:
            quelle = "allgemein"; applied["verdikt"] += 1
        elif v and v["quelle"] == "offen":
            quelle = "offen"            # assessed and undecidable — not the same as unassessed
            applied["verdikt"] += 1
        elif kind in APPLICABLE or kind == "registereintrag":
            for law_id, _ in sorted(cited.get(fid, {}).items(), key=lambda x: -x[1]):
                cand = by_law.get(law_id)
                if not cand:
                    continue
                real = [r for r in cand if r["rechtsmittel_art"] != "verweis"]
                vrg = [r for r in cand if r["rechtsmittel_art"] == "verweis"
                       and "172.200" in (r["instanz"] or "") + (r["quote"] or "") + (r["hinweis"] or "")]
                if len(real) == 1:
                    pick, quelle = real[0], "sektoral"
                elif not real and vrg:
                    quelle = "allgemein"
                elif not real and cand:
                    pick, quelle = cand[0], "sektoral"     # a single verweis elsewhere (ATSG, VwVG)
                else:
                    quelle = "allgemein"                    # ambiguous: verdict pass decides
                break
            if pick is None and quelle is None and kind in APPLICABLE:
                quelle = "allgemein"
        if quelle == "allgemein":
            g = c.execute("SELECT * FROM rechtsmittel_regel WHERE id=?", [general_id]).fetchone()
            c.execute("UPDATE form_outcome SET rechtsmittel_art=?, rechtsmittel_frist_tage=?, rechtsmittel_instanz=?, "
                      "article_id=?, rechtsmittel_regel_id=?, rechtsmittel_quelle='allgemein' WHERE form_id=?",
                      [g["rechtsmittel_art"], g["frist_tage"], g["instanz"], g["article_id"], g["id"], fid])
            applied["allgemein"] += 1
        elif pick:
            c.execute("UPDATE form_outcome SET rechtsmittel_art=?, rechtsmittel_frist_tage=?, rechtsmittel_instanz=?, "
                      "article_id=?, rechtsmittel_regel_id=?, rechtsmittel_quelle='sektoral' WHERE form_id=?",
                      [pick["rechtsmittel_art"], pick["frist_tage"], pick["instanz"], pick["article_id"], pick["id"], fid])
            applied["sektoral"] += 1
        else:
            # 'offen' = the panel looked and could not decide; NULL = never looked
            c.execute("UPDATE form_outcome SET rechtsmittel_art=NULL, rechtsmittel_frist_tage=NULL, rechtsmittel_instanz=NULL, "
                      "article_id=NULL, rechtsmittel_regel_id=NULL, rechtsmittel_quelle=? WHERE form_id=?",
                      ["offen" if quelle == "offen" else None, fid])
            applied["offen" if quelle == "offen" or kind == "registereintrag" else "keins"] += 1
    c.commit()
    errs = validate(c)
    c.close()
    if errs:
        os.remove(st); print("ABORT:", *errs[:3], sep="\n  "); sys.exit(1)
    os.replace(st, DB_PATH)
    print(f"rechtsmittel: allgemeine VRG-Regel verifiziert; {n} sektorale Regeln geladen "
          f"({added_arts} Artikel neu aus PDF-Zitat), {rejected} REJECTED {why}; "
          f"form_outcome: {applied}")


if __name__ == "__main__":
    main()
