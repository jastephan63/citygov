"""The party words of the Lebenslagen key: one definition.

PARTY matches the words of a label or a section that name a party other than the
applicant (Ehegatte, Kind, Arbeitgeber, Vermieter …). export/export_json.py puts the
words it finds into the key of «the same datum» (datum_key) and hands PARTY to
register_map.export_register; domain/rollen.py reads this file's source and checks
every word against LEBENSLAGEN_WOERTER (rollen.lebenslagen_abgleich). Moved unchanged
from export/export_json.py. Standard library only.
"""
import re

PARTY = re.compile(r"ehe(gatt|partner|frau|mann)|partner|kind|tochter|sohn|vater|mutter|eltern|"
                   r"arbeitgeb|vertret|bevollm|verstorb|erblass|eigentüm|vermiet|mieter|pächter|"
                   r"verpächt|käufer|verkäufer|halter|begleit|zeug|gläubig|schuldn|bürge|"
                   r"teilhaber|gesellschafter|geschäftsführ|kontaktperson|ansprechperson", re.I)
