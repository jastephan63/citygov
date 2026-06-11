#!/usr/bin/env python3
"""Auto-draft modeller: turn Formulare into reviewable DRAFT services (conv 5/6).

For each Formular it: copies the file into forms/, extracts the REAL fields, mines
the legal references the document (and its same-office Merkblätter) actually CITE,
auto-classifies each field, derives requirement candidates, and writes a proposal.
Everything it produces is match_status='proposed'/'auto' and last_checked carries
the honest provenance ('zitiert in <doc>' = a citation lifted from an official
document but NOT yet verified against Fedlex/register). NOTHING is invented and
NOTHING is marked confirmed/compliant — this is a first draft for human review.

Known draft limitation (by design, surfaced not hidden): requirements here are
derived from the form's own fields, so genuine LEGAL GAPS (law demands X, form
omits X) are NOT detected — that needs law-first modelling in review (Stage 2).

    python3 scripts/auto_draft.py "../Verwaltung/Finanzdepartement /Polizei"
    python3 scripts/auto_draft.py --all
"""
import argparse, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, FORMS_DIR, DB_PATH, connect, log
from classify import classify
from commit_proposal import commit
from validate_db import validate

VERW = os.path.normpath(os.path.join(ROOT, "..", "Verwaltung"))

# ---- field extraction (pypdf / openpyxl), text for citation mining -----------
def extract_pdf(path):
    fields, text = [], ""
    try:
        from pypdf import PdfReader
        r = PdfReader(path)
        try: text = "\n".join((p.extract_text() or "") for p in r.pages)
        except Exception: text = ""
        acro = r.get_fields() or {}
        TYPE = {"/Tx":"text","/Btn":"checkbox","/Ch":"select","/Sig":"signature"}
        for i,(name,f) in enumerate(acro.items(),1):
            st=f.get("/_States_")
            fields.append({"label":str(name),"field_type":TYPE.get(f.get("/FT"),"text"),
                           "options":[s for s in st if s!="/Off"] if st else None,"order":i})
    except Exception as e:
        log("auto_draft.log", f"pdf-extract fail {path}: {e!r}")
    return fields, text

def extract_xlsx(path):
    fields=[]; text=""
    try:
        import openpyxl
        wb=openpyxl.load_workbook(path, read_only=True, data_only=True)
        i=0
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for c in row:
                    if isinstance(c,str) and 2<=len(c.strip())<=60:
                        i+=1; fields.append({"label":c.strip(),"field_type":"text","options":None,"order":i,"section":ws.title})
                        text+=c+"\n"
                    if i>=150: break
    except Exception as e:
        log("auto_draft.log", f"xlsx-extract fail {path}: {e!r}")
    return fields, text

# ---- legal-citation mining ---------------------------------------------------
SR  = re.compile(r"\bSR\s+(\d{3}(?:\.\d+)*)")
ART = re.compile(r"\b(Art\.?|Artikel|§)\s?(\d+[a-z]?)((?:\s?(?:Abs\.?|Bst\.?|lit\.?|Ziff\.?)\s?[\w]+)*)")
LAWNAME = re.compile(r"\b([A-ZÄÖÜ][\wäöü-]*(?:gesetz|verordnung|reglement|ordnung)(?:\s?\([A-ZÄÖÜ]{2,}\))?)\b")

def mine_citations(text):
    cites={"sr":sorted(set(SR.findall(text)))[:6],
           "articles":[],"laws":sorted(set(LAWNAME.findall(text)))[:8]}
    seen=set()
    for kind,no,det in ART.findall(text):
        key=(no, det.strip())
        if key in seen: continue
        seen.add(key)
        mark = "§" if kind=="§" else "Art."
        cites["articles"].append({"no":no,"detail":det.strip(),"mark":mark})
        if len(cites["articles"])>=12: break
    return cites

# ---- field classification (draft heuristics) ---------------------------------
MECH = re.compile(r"unterschrift|signature|\bdatum\b|\bort\b|seite|page|stempel|"
                  r"ort, datum|ort/datum|hier unterschreiben|place here", re.I)
IDENT = re.compile(r"\bname\b|vorname|nachname|geburtsname|ledigname|geburtsdatum|"
                   r"\bahv|geschlecht|zivilstand|heimatort|heimatgemeinde|nationalit|"
                   r"staatsangeh|b[üu]rgerort|personalien|geburtsort", re.I)
OVER = re.compile(r"e-?mail|telefon|natel|handy|mobil|newsletter|website|fax", re.I)
ADDR = re.compile(r"adresse|strasse|wohnort|plz\b|postleitzahl|domizil", re.I)
norm = lambda s: re.sub(r"[^a-z0-9]+","",(s or "").lower())

def slug(s):
    s=re.sub(r"[^a-z0-9]+","-",(s or "").lower()).strip("-"); return s[:60] or "x"

def draft_form(path, office, dept, cites):
    base=os.path.splitext(os.path.basename(path))[0]
    ext=os.path.splitext(path)[1].lower()
    fields,_ = (extract_xlsx(path) if ext.startswith(".xls") else extract_pdf(path))
    sslug=slug(office+"-"+base)
    rel=os.path.relpath(path, ROOT)

    # law records from mined citations (UNVERIFIED — extracted from the document)
    laws=[]; article_refs={}
    # group articles under a generic "cited law" per jurisdiction guess
    fed = bool(cites["sr"])
    if cites["articles"] or cites["sr"]:
        jur = "federal" if fed else "cantonal"
        lslug=f"{sslug}-zit"
        arts=[]
        for i,a in enumerate(cites["articles"][:12]):
            ar=f"a{i}"
            arts.append({"ref":ar,"article_no":(a["mark"]+" "+a["no"]) if a["mark"]=="§" else a["no"],
                         "heading":(a["detail"] or "zitiert"),"last_checked":"UNVERIFIED"})
            article_refs[ar]=a
        laws.append({"slug":lslug,
                     "title":(", ".join(cites["laws"][:3]) or "Im Dokument zitierte Rechtsgrundlagen"),
                     "short_title":"zitiert","jurisdiction_level":jur,
                     "sr_number":(cites["sr"][0] if cites["sr"] else None),
                     "source_note":f"Zitate maschinell aus {rel} (und Merkbl./Office) extrahiert; NICHT verifiziert.",
                     "last_checked":"UNVERIFIED","articles":arts})
    basis = [{"article_ref":r,"citation_detail":article_refs[r]["detail"] or None,"last_checked":"UNVERIFIED"}
             for r in article_refs]  # generic: attach all cited articles to each requirement

    # fields + requirements + mappings.
    # Draft modelling keeps requirement count small (no per-field explosion):
    #   * personalien / adresse  -> SHARED global requirements (deduped by key,
    #     conv 8). No legal basis attached in the draft (varies per service;
    #     filled during law-first review) so shared reqs stay clean.
    #   * reason-group(s)        -> one per form-section of checkboxes.
    #   * "uebrige-<svc>"        -> ONE catch-all per form for the remaining data
    #     fields. The mined citations attach HERE only.
    form_fields=[]; reqs={}; mappings=[]; svc_reqs=set()
    def ensure_req(key,dp,label,dtype,composite=False,with_basis=False):
        if key not in reqs:
            reqs[key]={"ref":key,"data_point_key":key,"data_point":dp,"label":label,
                       "data_type":dtype,"is_composite":composite,
                       "legal_basis":(list(basis) if with_basis else [])}
            svc_reqs.add(key)
        return key
    uebrige_key=f"uebrige-{sslug}"
    has_generic=False
    for i,fl in enumerate(fields,1):
        fref=f"f{i}"; lab=fl["label"]; ft=fl.get("field_type","text"); sec=fl.get("section")
        form_fields.append({"ref":fref,"field_key":f"{slug(lab)}-{i}","label":lab,"section":sec,
                            "field_type":ft,"options":fl.get("options"),"raw_order":fl.get("order",i)})
        if MECH.search(lab) or ft=="signature":
            mappings.append(_m(fref,None,"form_mechanic")); continue
        if OVER.search(lab):
            mappings.append(_m(fref,None,"overcollection")); continue
        if IDENT.search(lab):
            ensure_req("personalien","Personalien","Amtliche Identität / Registermerkmale","composite",True)
            mappings.append(_m(fref,"personalien","identity_part")); continue
        if ft=="checkbox":
            grp=f"grund-{sslug}-{slug(sec or 'auswahl')}"
            ensure_req(grp, ("Auswahl: "+(sec or "")).strip(), "Mehrfachauswahl", "enum", with_basis=True)
            mappings.append(_m(fref,grp,"reason_facet")); continue
        if ADDR.search(lab):
            ensure_req("adresse","Adresse","Adressangaben","string")
            mappings.append(_m(fref,"adresse","mapped")); continue
        # generic data field -> ONE shared-per-form catch-all requirement
        ensure_req(uebrige_key, "Übrige Sachangaben", "Weitere im Formular erhobene Sachangaben (Sammelposten, zu verfeinern)", "composite", with_basis=True)
        has_generic=True
        mappings.append(_m(fref, uebrige_key, "mapped"))

    proposal={
      "service":{"slug":sslug,"name":base,"dienststelle":office.split("/")[-1],
                 "department":dept,"description":f"AUTO-ENTWURF aus {rel}. Juristisch zu prüfen.",
                 "notes":"auto_draft"},
      "laws":laws,"requirements":list(reqs.values()),
      "service_requirements":[{"requirement_ref":r} for r in svc_reqs],
      "form":{"slug":sslug+"-form","title":base,"actual_purpose":None,
              "title_content_mismatch":False,"source_file":rel,
              "file_type":"excel" if ext.startswith(".xls") else "pdf",
              "publisher_dienststelle":office.split("/")[-1],"last_extracted":"auto"},
      "form_fields":form_fields,"field_mappings":mappings,
      "documents":[{"source_file":rel,"file_name":os.path.basename(path),
                    "department":dept,"dienststelle":office.split("/")[-1],
                    "doc_type":"formular","is_this_form":True,
                    "classification_note":"auto-klassifiziert; zu bestätigen (conv 7)."}],
      "findings":[{"type":"note","severity":"info","fingerprint":"autodraft-"+sslug,
                   "description":f"Auto-Entwurf: {len(form_fields)} Felder extrahiert, "
                   f"{len(cites['articles'])} Zitat(e) gefunden. Rechtsgrundlagen UNVERIFIED, "
                   f"Mappings proposed — juristische Prüfung nötig.","status":"open","created_at":"AUTODRAFT"}],
    }
    return proposal

def _m(fref,req,cls):
    return {"form_field_ref":fref,"requirement_ref":req,"classification":cls,
            "match_status":"proposed","mapped_by":"auto","confidence":0.4,
            "notes":"Auto-Entwurf (conv 5) — zu prüfen."}

# ---- office helpers: gather Merkblatt text for citation context --------------
def office_helper_text(office_dir):
    txt=""
    for f in os.listdir(office_dir):
        full=os.path.join(office_dir,f)
        if not os.path.isfile(full): continue
        dt,_=classify(f)
        if dt=="helper" and f.lower().endswith(".pdf"):
            _,t=extract_pdf(full); txt+=t+"\n"
            if len(txt)>40000: break
    return txt

def process_office(conn, office_dir):
    rel_office=os.path.relpath(office_dir, VERW)
    dept=rel_office.split("/")[0]
    helper_txt=office_helper_text(office_dir)
    n=0
    for f in sorted(os.listdir(office_dir)):
        full=os.path.join(office_dir,f)
        if not os.path.isfile(full): continue
        if os.path.splitext(f)[1].lower() not in (".pdf",".xlsx",".xlsm",".xls",".doc",".docx"): continue
        dt,_=classify(f)
        if dt!="formular": continue
        # copy into forms/ for provenance
        dest_dir=os.path.join(FORMS_DIR, rel_office); os.makedirs(dest_dir,exist_ok=True)
        dest=os.path.join(dest_dir,f)
        if not os.path.exists(dest):
            try: shutil.copy2(full,dest)
            except Exception: pass
        _,ftext=extract_pdf(full) if f.lower().endswith(".pdf") else (None, "")
        cites=mine_citations((ftext or "")+"\n"+helper_txt[:8000])
        prop=draft_form(full, rel_office, dept, cites)
        commit(conn, prop); n+=1
    return n

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("office", nargs="?")
    ap.add_argument("--all", action="store_true")
    args=ap.parse_args()

    staging=DB_PATH+".staging"
    if os.path.exists(staging): os.remove(staging)
    shutil.copy2(DB_PATH, staging)
    conn=connect(staging)
    total=0
    try:
        if args.all:
            offices=[]
            for dep in sorted(os.listdir(VERW)):
                dpath=os.path.join(VERW,dep)
                if not os.path.isdir(dpath): continue
                for off in sorted(os.listdir(dpath)):
                    op=os.path.join(dpath,off)
                    if os.path.isdir(op) and "_files" not in off: offices.append(op)
            for op in offices:
                k=process_office(conn,op)
                if k: print(f"  {k:3} forms <- {os.path.relpath(op,VERW)}")
                total+=k
        else:
            total=process_office(conn, args.office)
            print(f"  {total} forms from {args.office}")
        conn.commit()
    except Exception as e:
        conn.close(); os.remove(staging)
        log("auto_draft.log", f"ABORT: {e!r}")
        print(f"ABORT: {e!r} (source untouched)", file=sys.stderr); sys.exit(1)
    errs=validate(conn); conn.close()
    if errs:
        os.remove(staging)
        print("ABORT validation:", *errs[:5], sep="\n  ", file=sys.stderr); sys.exit(1)
    os.replace(staging, DB_PATH)
    print(f"committed {total} draft form(s)")

if __name__=="__main__":
    main()
