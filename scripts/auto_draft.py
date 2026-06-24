#!/usr/bin/env python3
"""Auto-draft modeller: each Formular -> a reviewable DRAFT, ONE requirement PER
FIELD (conv 5/6).

For each Formular it: copies the file into forms/, extracts the REAL fields
(AcroForm fields; if none, parses field labels from the PDF text; flags scanned
PDFs for OCR/manual), breaks every substantive field into its own requirement,
auto-classifies each field, and records the legal references the document + its
Merkblätter actually CITE as research leads in a finding.

Deliberately does NOT assign a legal basis per field: the correct basis depends on
the SERVICE's governing law (a "Name" field on a weapons permit vs a tax return vs
a residence registration have different bases), so guessing one would manufacture
wrong citations — exactly what conv 6 forbids. Each field-requirement is therefore
left legal_basis = [] ("Rechtsgrundlage zu ermitteln"); finding the real Art./§ per
field is the review pass (extract_law.py / Fedlex), driven office-by-office.

Everything here is match_status='proposed'/'auto'. Nothing reads as compliant.

    python3 scripts/auto_draft.py "../Verwaltung/Finanzdepartement /Polizei"
    python3 scripts/auto_draft.py --all
"""
import argparse, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, FORMS_DIR, DB_PATH, connect, log
from classify import classify, HELPER
from commit_proposal import commit
from validate_db import validate

VERW = os.path.normpath(os.path.join(ROOT, "..", "Verwaltung"))

# ---- field extraction --------------------------------------------------------
CHECKGLYPH = re.compile(r"^\s*(?:[☐☑□■○◯❑❏]|\[\s?\]|□|❑|◻|○|o)\s+(.+)$")

def text_fields(text):
    """Heuristic field labels from flat-PDF / Word text (no AcroForm). Noisy -> review.
    Handles: 'Label:' , 'Label _____' , checkbox glyphs, and the common Word
    template style where a label line is followed by a '[placeholder]' line."""
    lines = [l.strip() for l in text.splitlines()]
    out, seen, order = [], set(), 0
    for i, line in enumerate(lines):
        if len(line) < 2:
            continue
        label, ftype = None, "text"
        m = CHECKGLYPH.match(line)
        if m:
            label, ftype = m.group(1).strip(), "checkbox"
        else:
            m = re.match(r"^(.{2,60}?)\s*[:：]\s*[_\.\s]*$", line) or re.match(r"^(.{2,55}?)\s*[_\.]{3,}", line)
            if m:
                label = m.group(1).strip()
            elif (i + 1 < len(lines) and re.match(r"^\[.*\]$", lines[i + 1])
                  and not line.startswith("[") and 2 <= len(line) <= 60):
                label = line          # 'Label' followed by '[placeholder]'
        if not label:
            continue
        label = re.sub(r"\s+", " ", label).strip(" .:_-")
        if not (2 <= len(label) <= 60) or label.lower() in seen:
            continue
        seen.add(label.lower()); order += 1
        out.append({"label": label, "field_type": ftype, "options": None, "order": order, "src": "text"})
        if order >= 120:
            break
    return out

def extract_doc(path):
    """Word .doc/.docx via macOS textutil (built-in), then label heuristics."""
    import subprocess
    base=os.path.splitext(os.path.basename(path))[0]
    try:
        t = subprocess.run(["textutil", "-convert", "txt", "-stdout", path],
                           capture_output=True, text=True, timeout=60).stdout
    except Exception as e:
        log("auto_draft.log", f"doc-extract fail {path}: {e!r}"); t = ""
    return text_fields(t), t, (len(t.strip()) < 50), doc_title("", t, base), 0

def _realwords(t):
    return len(re.findall(r"[A-Za-zÄÖÜäöü]{3,}", t or ""))

# authority/org header lines that are NOT a form title
_AUTH = re.compile(r"eidgen[öo]ssisch|departement\b|bundesamt|staatssekretariat|"
                   r"\bEJPD\b|\bEDA\b|\bWBF\b|\bSEM\b|\bEFD\b|\bUVEK\b|kanton schaffhausen|"
                   r"^amt f[üu]r|^abteilung|^sektion|^dienststelle", re.I)
# words that mark the real form title
_FORMW = re.compile(r"gesuch|antrag|anmeldung|formular|\bmeldung|bewilligung|erkl[äa]rung|"
                    r"bescheinigung|vollmacht|nachweis|deklaration|gesuchsformular", re.I)

def doc_title(meta_title, text, fallback):
    """Human-readable title: PDF /Title if it reads like a form name, else the most
    title-like text line. Skips filenames, form-number codes, and authority headers
    (e.g. 'Eidgenössisches Justiz- und Polizeidepartement EJPD')."""
    t = (meta_title or "").strip()
    bad = (not t) or len(t) < 4 or _realwords(t) < 2 or _AUTH.search(t) or re.search(
        r"\.(pdf|docx?|rtf|xls\w*)$|microsoft word|untitled|^form$|^dokument\d*$|^document\d*$", t, re.I)
    if bad:
        lines = [re.sub(r"\s+", " ", l.strip()) for l in (text or "").splitlines()]
        lines = [l for l in lines if 6 <= len(l) <= 100 and _realwords(l) >= 2 and not _AUTH.search(l)]
        t = next((l for l in lines if _FORMW.search(l)), lines[0] if lines else "")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:120] or fallback

def extract_pdf(path):
    """Returns (fields, text, scanned, title, acro_count). Field label prefers the
    /TU tooltip (human label) over the raw field name (e.g. 'toggle_1', '1')."""
    fields, text, title, acro_n = [], "", "", 0
    base = os.path.splitext(os.path.basename(path))[0]
    try:
        from pypdf import PdfReader
        r = PdfReader(path)
        try: text = "\n".join((p.extract_text() or "") for p in r.pages)
        except Exception: text = ""
        acro = r.get_fields() or {}
        TYPE = {"/Tx":"text","/Btn":"checkbox","/Ch":"select","/Sig":"signature"}
        for i,(name,f) in enumerate(acro.items(),1):
            st=f.get("/_States_"); tu=f.get("/TU")
            label=clean_label((str(tu).strip() if tu else "") or str(name))
            fields.append({"label":label,"field_type":TYPE.get(f.get("/FT"),"text"),
                           "options":[s for s in st if s!="/Off"] if st else None,"order":i,"src":"acro"})
        acro_n=len(acro)
        try: title=doc_title((r.metadata or {}).get("/Title"), text, base)
        except Exception: title=base
    except Exception as e:
        log("auto_draft.log", f"pdf-extract fail {path}: {e!r}")
    if not fields:                       # flat PDF -> parse labels from text
        fields = text_fields(text)
    if not title: title = base
    scanned = (not fields) and len(text.strip()) < 200
    return fields, text, scanned, title, acro_n

def extract_xlsx(path):
    fields=[]; text=""; title=""
    base=os.path.splitext(os.path.basename(path))[0]
    try:
        import openpyxl
        wb=openpyxl.load_workbook(path, read_only=True, data_only=True)
        try: title=(wb.properties.title or "").strip()
        except Exception: title=""
        i=0
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for c in row:
                    if isinstance(c,str) and 2<=len(c.strip())<=60:
                        i+=1; fields.append({"label":c.strip(),"field_type":"text","options":None,"order":i,"section":ws.title,"src":"xlsx"})
                        text+=c+"\n"
                    if i>=150: break
    except Exception as e:
        log("auto_draft.log", f"xlsx-extract fail {path}: {e!r}")
    return fields, text, False, doc_title(title, text, base), 0

# ---- legal-citation mining (research leads only; not assigned per field) -----
SR  = re.compile(r"\bSR\s+(\d{3}(?:\.\d+)*)")
ART = re.compile(r"\b(Art\.?|Artikel|§)\s?(\d+[a-z]?)((?:\s?(?:Abs\.?|Bst\.?|lit\.?|Ziff\.?)\s?[\w]+)*)")
LAWNAME = re.compile(r"\b([A-ZÄÖÜ][\wäöü-]*(?:gesetz|verordnung|reglement|ordnung)(?:\s?\([A-ZÄÖÜ]{2,}\))?)\b")

def mine_citations(text):
    sr=sorted(set(SR.findall(text)))[:6]
    laws=sorted(set(LAWNAME.findall(text)))[:8]
    arts=[]; seen=set()
    for kind,no,det in ART.findall(text):
        k=(no,det.strip())
        if k in seen: continue
        seen.add(k); arts.append((("§ " if kind=="§" else "Art. ")+no+(" "+det.strip() if det.strip() else "")))
        if len(arts)>=12: break
    return sr, laws, arts

# ---- field classification (draft) --------------------------------------------
MECH = re.compile(r"unterschrift|signature|\bdatum\b|\bort\b|ort, datum|ort/datum|"
                  r"seite|page|stempel|hier unterschreiben|place here|"
                  r"n[äa]chste seite|vorherige seite|zur[üu]cksetzen|formulareingaben|"
                  r"\bnav\b|ausdrucken|drucken|\bsenden\b|speichern|\bweiter\b|\breset\b|\bprint\b|"
                  r"absenderzeile", re.I)
def slug(s):
    s=re.sub(r"[^a-z0-9]+","-",(s or "").lower()).strip("-"); return s[:48] or "x"

def clean_label(label):
    """Make a technical AcroForm field name readable.
    'personalien.versichertennummer1' -> 'Versichertennummer 1';
    'adresse_neu' -> 'Adresse neu'. Leaves already-readable labels untouched."""
    l = (label or "").strip()
    if " " in l or len(l) < 2:
        return l
    if "." in l:                       # dotted hierarchy -> last segment
        l = l.split(".")[-1]
    l = l.replace("_", " ")
    l = re.sub(r"(?<=[a-zäöü])(?=[A-ZÄÖÜ])", " ", l)   # camelCase boundary
    l = re.sub(r"(?<=[A-Za-zäöüÄÖÜ])(?=\d)", " ", l)    # trailing number
    l = re.sub(r"\s+", " ", l).strip()
    return (l[:1].upper() + l[1:]) if l else label

def draft_form(path, office, dept, fields, scanned, sr, laws, arts, title=None):
    base=os.path.splitext(os.path.basename(path))[0]
    name=title or base                    # human-readable display title (PDF /Title)
    ext=os.path.splitext(path)[1].lower()
    sslug=slug(office.split("/")[-1]+"-"+base)   # slug stays filename-based (stable id)
    rel=os.path.relpath(path, ROOT)

    form_fields=[]; reqs={}; mappings=[]; svc_reqs=set()
    def ensure_req(key,dp,dtype,composite=False):
        if key not in reqs:
            reqs[key]={"ref":key,"data_point_key":f"{sslug}::{key}","data_point":dp,
                       "label":dp,"data_type":dtype,"is_composite":composite,"legal_basis":[]}
            svc_reqs.add(key)
        return key
    for i,fl in enumerate(fields,1):
        fref=f"f{i}"; lab=fl["label"]; ft=fl.get("field_type","text"); sec=fl.get("section")
        form_fields.append({"ref":fref,"field_key":f"{slug(lab)}-{i}","label":lab,"section":sec,
                            "field_type":ft,"options":fl.get("options"),"raw_order":fl.get("order",i),
                            "notes":("aus PDF-Text geparst (zu prüfen)" if fl.get("src")=="text" else None)})
        if MECH.search(lab) or ft=="signature":
            mappings.append(_m(fref,None,"form_mechanic")); continue
        if ft=="checkbox":
            grp="opt-"+slug(sec or lab)           # checkbox group -> one enum requirement
            ensure_req(grp,(sec or lab),"enum")
            mappings.append(_m(fref,grp,"reason_facet")); continue
        # every other field -> its OWN requirement (the data point), basis TBD
        k=slug(lab)
        ensure_req(k, lab, "string")
        mappings.append(_m(fref,k,"mapped"))

    leads = (("zitierte Gesetze: "+", ".join(laws)+". ") if laws else "") + \
            (("SR: "+", ".join(sr)+". ") if sr else "") + \
            (("zitierte Artikel: "+"; ".join(arts)+"." ) if arts else "")
    note = (f"Auto-Entwurf: {len(form_fields)} Feld(er); je Feld eine Anforderung, "
            f"Rechtsgrundlage je Feld ZU ERMITTELN. " + (("Recherche-Leads — "+leads) if leads else
            "Keine Zitate im Dokument gefunden.")) if not scanned else \
           ("Gescanntes/Bild-PDF: keine Felder extrahierbar — OCR oder manuelle Erfassung nötig.")

    return {
      "service":{"slug":sslug,"name":name,"dienststelle":office.split("/")[-1],
                 "department":dept,"description":f"AUTO-ENTWURF aus {rel}. Felder einzeln; Rechtsgrundlagen zu ermitteln.",
                 "notes":"auto_draft; Datei: "+os.path.basename(path)},
      "laws":[], "requirements":list(reqs.values()),
      "service_requirements":[{"requirement_ref":r} for r in svc_reqs],
      "form":{"slug":sslug+"-form","title":name,"actual_purpose":None,
              "title_content_mismatch":False,"source_file":rel,
              "file_type":"excel" if ext.startswith(".xls") else "pdf",
              "publisher_dienststelle":office.split("/")[-1],"last_extracted":"auto"},
      "form_fields":form_fields,"field_mappings":mappings,
      "documents":[{"source_file":rel,"file_name":os.path.basename(path),
                    "department":dept,"dienststelle":office.split("/")[-1],
                    "doc_type":"formular","is_this_form":True,
                    "classification_note":"auto-klassifiziert (conv 7)."}],
      "findings":[{"type":("validation" if scanned else "note"),
                   "severity":("warning" if scanned else "info"),"fingerprint":"autodraft-"+sslug,
                   "description":note,"status":"open","created_at":"AUTODRAFT"}],
    }

def _m(fref,req,cls):
    return {"form_field_ref":fref,"requirement_ref":req,"classification":cls,
            "match_status":"proposed","mapped_by":"auto","confidence":0.4,
            "notes":"Auto-Entwurf (conv 5) — Rechtsgrundlage zu prüfen."}

# ---- office processing -------------------------------------------------------
def office_helper_text(office_dir):
    txt=""
    for root,_,files in os.walk(office_dir):
        if "_files" in root: continue
        for f in files:
            full=os.path.join(root,f)
            if os.path.isfile(full) and classify(f)[0]=="helper" and f.lower().endswith(".pdf"):
                txt+=extract_pdf(full)[1]+"\n"
                if len(txt)>40000: return txt
    return txt

def process_office(conn, office_dir):
    rel_office=os.path.relpath(office_dir, VERW); dept=rel_office.split("/")[0]
    helper_txt=office_helper_text(office_dir)
    n=0
    seen=set()
    for root,_,files in os.walk(office_dir):     # recurse into office subfolders
        if "_files" in root: continue
        for f in sorted(files):
            full=os.path.join(root,f)
            if not os.path.isfile(full): continue
            ext=os.path.splitext(f)[1].lower()
            if ext not in (".pdf",".xlsx",".xlsm",".xls",".doc",".docx"): continue
            if HELPER.search(os.path.splitext(f)[0]): continue   # strong guidance -> never a form
            if ext in (".xlsx",".xlsm",".xls"): fields,ftext,scanned,title,acro=extract_xlsx(full)
            elif ext==".pdf":                   fields,ftext,scanned,title,acro=extract_pdf(full)
            else:                               fields,ftext,scanned,title,acro=extract_doc(full)
            # a file is a FORM if its name says so OR it is a fillable PDF (>=3 AcroForm
            # fields) — recovers coded/hash-named sheets (e.g. SVA's bei02, allg01).
            if not (classify(f)[0]=="formular" or acro>=3):
                continue
            dest=os.path.join(FORMS_DIR, os.path.relpath(full, VERW))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if not os.path.exists(dest):
                try: shutil.copy2(full,dest)
                except Exception: pass
            sr,laws,arts=mine_citations((ftext or "")+"\n"+helper_txt[:8000])
            commit(conn, draft_form(full, rel_office, dept, fields, scanned, sr, laws, arts, title)); n+=1
    return n

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("office", nargs="?"); ap.add_argument("--all", action="store_true")
    args=ap.parse_args()
    staging=DB_PATH+".staging"
    if os.path.exists(staging): os.remove(staging)
    shutil.copy2(DB_PATH, staging)
    conn=connect(staging); total=0
    try:
        if args.all:
            for dep in sorted(os.listdir(VERW)):
                dpath=os.path.join(VERW,dep)
                if not os.path.isdir(dpath): continue
                for off in sorted(os.listdir(dpath)):
                    op=os.path.join(dpath,off)
                    if os.path.isdir(op) and "_files" not in off:
                        k=process_office(conn,op)
                        if k: print(f"  {k:3} forms <- {os.path.relpath(op,VERW)}")
                        total+=k
        else:
            total=process_office(conn,args.office); print(f"  {total} forms from {args.office}")
        conn.commit()
    except Exception as e:
        conn.close(); os.remove(staging); log("auto_draft.log",f"ABORT: {e!r}")
        print(f"ABORT: {e!r}",file=sys.stderr); sys.exit(1)
    errs=validate(conn); conn.close()
    if errs:
        os.remove(staging); print("ABORT validation:",*errs[:5],sep="\n  ",file=sys.stderr); sys.exit(1)
    os.replace(staging,DB_PATH); print(f"committed {total} draft form(s)")

if __name__=="__main__":
    main()
