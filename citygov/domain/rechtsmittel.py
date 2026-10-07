"""Rechtsmittel: what the loader and the export share.

cited_laws(c) — per Formular the laws its fields cite (weight = number of citing fields)
plus the cantonal laws the DVSH model names as the service's Rechtsgrundlage — is the
one definition load/load_rechtsmittel.py applies the sektoral rule with,
load/load_rechtsmittel_verdicts.py prepares the panel input with and
export/export_json.py lists the candidate remedy provisions of a Formular with. Moved
unchanged from load/load_rechtsmittel.py (whose docstring describes the two layers of
Rechtsmittel). Standard library only, nothing written.
"""
import json


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
