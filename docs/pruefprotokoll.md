# Prüfprotokoll — how each layer of an intake is judged

Every layer an intake adds to `citygov.db` is judged twice: a **first judgement** of each
Formular, then a **sceptical second review** that re-reads the sources and returns the corrected
complete record. Only the second review is loaded. The remedy verdict is reviewed by **three
independent lenses** (norm, entscheid, praxis); it is overturned only when two lenses refute it.
Sibling Formulare judged one by one can diverge, so an intake ends with an **Angleichung** of
same-labelled Angaben across its Formulare (same Angabe in the same procedure → same verdict).

This file keeps the instructions the reviewers followed and the shape of what they return, so a
later intake is judged the same way. The output of each pass is kept as evidence under
`quellen/dokumente/panel_<date>/` and turned into loader input by `scripts/apply_panel.py`
(see its docstring for the order). Placeholders: `<citygov.db>` the database (open it read-only:
`sqlite3 "file:<citygov.db>?mode=ro"`), `<repo>` the repository, `${...}` the values of one
Formular or group. The reviewers never write files or the database.

Order of the layers: **Felder** → **eCH** and **Verfahren** → **Rechtsgrundlage** (then
**Nachtrag** if articles became citable later, and **Angleichung**) → **Subjekt** (only fields
with a register standard, after eCH) → **Rechtsmittel** (only after the legal bases: its
candidates are the cited laws).

## Felder (data dictionary)

One record per new Formular; a newer edition of a held Formular is instead **ported** (every existing field keeps its id; see `scripts/migrate_ausgaben_2026_10_28.py`).

**Ausgabe `FIELDS`**

```json
{
 "type": "object",
 "properties": {
  "form_id": {
   "type": "integer"
  },
  "data_fields": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "name": {
      "type": "string",
      "description": "the label the Formular itself prints (German, verbatim, without colon)"
     },
     "definition": {
      "type": "string",
      "description": "one German sentence: which Angabe this is on THIS Formular"
     },
     "data_type": {
      "type": "string",
      "enum": [
       "text",
       "date",
       "number",
       "money",
       "boolean",
       "enum",
       "multiselect",
       "composite",
       "attachment",
       "signature"
      ]
     },
     "required": {
      "type": "boolean"
     },
     "allowed_values": {
      "type": "array",
      "items": {
       "type": "string"
      },
      "description": "enum/multiselect: the options verbatim from the Formular"
     },
     "subfields": {
      "type": "array",
      "items": {
       "type": "string"
      },
      "description": "composite: the atomic parts, each as printed (Name, Vorname, Geburtsdatum …)"
     },
     "format": {
      "type": "string",
      "description": "printed format hint (TT.MM.JJJJ, CHF, number of rows …) or empty"
     }
    },
    "required": [
     "name",
     "definition",
     "data_type",
     "required",
     "allowed_values",
     "subfields",
     "format"
    ]
   }
  },
  "hinweis": {
   "type": "string"
  }
 },
 "required": [
  "form_id",
  "data_fields",
  "hinweis"
 ]
}
```

**Ausgabe `PORT`**

```json
{
 "type": "object",
 "properties": {
  "form_id": {
   "type": "integer"
  },
  "felder": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "id": {
      "type": [
       "integer",
       "null"
      ],
      "description": "the existing data_field id this Angabe continues, null for a new Angabe"
     },
     "aktion": {
      "type": "string",
      "enum": [
       "unveraendert",
       "geaendert",
       "neu"
      ]
     },
     "name": {
      "type": "string",
      "description": "the label the Formular itself prints (German, verbatim, without colon)"
     },
     "definition": {
      "type": "string",
      "description": "one German sentence: which Angabe this is on THIS Formular"
     },
     "data_type": {
      "type": "string",
      "enum": [
       "text",
       "date",
       "number",
       "money",
       "boolean",
       "enum",
       "multiselect",
       "composite",
       "attachment",
       "signature"
      ]
     },
     "required": {
      "type": "boolean"
     },
     "allowed_values": {
      "type": "array",
      "items": {
       "type": "string"
      },
      "description": "enum/multiselect: the options verbatim from the Formular"
     },
     "subfields": {
      "type": "array",
      "items": {
       "type": "string"
      },
      "description": "composite: the atomic parts, each as printed (Name, Vorname, Geburtsdatum …)"
     },
     "format": {
      "type": "string",
      "description": "printed format hint (TT.MM.JJJJ, CHF, number of rows …) or empty"
     },
     "beleg": {
      "type": "string",
      "description": "for geaendert/neu: what the new edition prints (verbatim)"
     }
    },
    "required": [
     "id",
     "aktion",
     "name",
     "definition",
     "data_type",
     "required",
     "allowed_values",
     "subfields",
     "format",
     "beleg"
    ]
   }
  },
  "entfallen": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "id": {
      "type": "integer"
     },
     "beleg": {
      "type": "string"
     }
    },
    "required": [
     "id",
     "beleg"
    ]
   }
  },
  "hinweis": {
   "type": "string"
  }
 },
 "required": [
  "form_id",
  "felder",
  "entfallen",
  "hinweis"
 ]
}
```

**Regeln `RULES`**

```text
The citygov databank keeps, per Formular of the Canton of Schaffhausen, its LOGICAL data dictionary: the Angaben a person or business fills in, not the raw widgets. Rules (from real past failures):
- Read the actual Formular (text_file; open the original file when the text is garbled, a scan, or the layout matters — checkbox groups, tables). Content beats title.
- One field per Angabe the Formular asks for, in the order of the Formular. A block of parts that belong together (Personalien, Adresse, Ort und Datum) is ONE composite field whose subfields are the atomic parts exactly as printed — the unit of standards is the atomic part, so never leave «Name, Vorname» as one part if the Formular prints two lines; never invent a part it does not print.
- name = the label the Formular itself prints (verbatim, German, no colon, no numbering); where several blocks share a label, add the block's own heading («Angaben zum Veranstalter»).
- data_type: date for a calendar date, money for amounts in CHF, number for counts/measures, boolean for one checkbox (yes/no), enum for a choice of one among printed options, multiselect for several checkboxes of one question (the Beilagen checklist is a multiselect named as printed, e.g. «Beilagen»), attachment for a document to enclose that is not a checklist, signature for each signature line (one per signatory), composite for blocks, text otherwise.
- required: false only where the Formular marks it optional («freiwillig», «falls vorhanden», «fakultativ», «Bemerkungen»), else true.
- allowed_values verbatim from the Formular (enum/multiselect only). format only when printed.
- Instructions, legal text, office-use-only boxes («Vom Amt auszufüllen», «leer lassen») are NOT fields of the person; note them in hinweis.
- German throughout. Do not use the word «Datum» for anything but a calendar date in definitions (use «Angabe»). Read-only: never write files or the DB.
For comparable held Formulare you may look at their fields read-only: sqlite3 "<citygov.db>" "SELECT name, data_type, subfields FROM data_field WHERE form_id=<id> ORDER BY ord".
```

**Auftrag `fields`**

```text
${RULES}\nFormular ${f.form_id} «${f.title}» (service «${f.service}»). Text: ${f.text_file}. File: ${f.file}.${f.hinweis ? ' ' + f.hinweis : ''} Build its data dictionary.
```

**Auftrag `review`**

```text
${RULES}\nYou are the SCEPTICAL reviewer of the data dictionary of Formular ${f.form_id} «${f.title}» (text ${f.text_file}, file ${f.file}):\n${JSON.stringify(d.data_fields)}\nCheck it against the Formular line by line: every Angabe the person fills in present (missing checkbox groups, table columns, second signatory, Beilagen checklist), nothing invented, composites split into the printed atomic parts, names verbatim as printed, types and required right. Return the CORRECTED complete dictionary (unchanged fields copied) and list your corrections in hinweis («keine» when none).
```

**Auftrag `port`**

```text
${PRULES}\nFormular ${f.form_id} «${f.title}». Existing fields: read them with sqlite3 \"file:<citygov.db>?mode=ro\" \"SELECT id, name, definition, data_type, required, allowed_values, subfields, format FROM data_field WHERE form_id=${f.form_id} ORDER BY ord\" (every id must appear exactly once in felder or entfallen). Old edition text: ${f.alt_text_file}. New edition text: ${f.text_file} (file ${f.file}). Earlier judgement of what changed: ${f.field_change || '—'}.${f.alt_text_file ? '' : ' There is no old edition file: the existing fields were built from the DVSH model (formDefinition) of this very document; port them to the document as printed.'}
```

**Auftrag `portreview`**

```text
${PRULES}\nYou are the SCEPTICAL reviewer of this port of Formular ${f.form_id} «${f.title}» to its new edition (old text ${f.alt_text_file}, new text ${f.text_file}, file ${f.file}; existing fields: sqlite3 \"file:<citygov.db>?mode=ro\" \"SELECT id, name, definition, data_type, required, allowed_values, subfields, format FROM data_field WHERE form_id=${f.form_id} ORDER BY ord\"):\n${JSON.stringify(p)}\nCheck: an existing id dropped although the new edition still asks for it, a renamed label not carried, a new Angabe of the edition missed, an id reused for a different Angabe. Return the CORRECTED complete port and list your corrections in hinweis («keine» when none).
```

## eCH und Verfahren

eCH element per field and per atomic part; the Verfahren record (Beilagen, Entscheid with its DVSH wording, purpose).

**Ausgabe `ECH`**

```json
{
 "type": "object",
 "properties": {
  "urteile": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "art": {
      "type": "string",
      "enum": [
       "feld",
       "teilfeld"
      ]
     },
     "feld": {
      "type": [
       "string",
       "null"
      ],
      "description": "art feld: data_field.name exactly"
     },
     "elternfeld": {
      "type": [
       "string",
       "null"
      ],
      "description": "art teilfeld: the parent data_field.name exactly"
     },
     "teilfeld": {
      "type": [
       "string",
       "null"
      ],
      "description": "art teilfeld: data_subfield.name exactly"
     },
     "urteil": {
      "type": "string",
      "enum": [
       "besser",
       "kein_standard",
       "korrekt"
      ]
     },
     "standard": {
      "type": [
       "string",
       "null"
      ]
     },
     "element": {
      "type": [
       "string",
       "null"
      ]
     },
     "grund": {
      "type": "string"
     }
    },
    "required": [
     "art",
     "feld",
     "elternfeld",
     "teilfeld",
     "urteil",
     "standard",
     "element",
     "grund"
    ]
   }
  }
 },
 "required": [
  "urteile"
 ]
}
```

**Ausgabe `V`**

```json
{
 "type": "object",
 "properties": {
  "zweck": {
   "type": "string",
   "description": "purpose for the Verzeichnis: one German nominal sentence, 30-250 chars"
  },
  "entscheid_art": {
   "type": "string",
   "enum": [
    "bewilligung",
    "verfuegung",
    "bestaetigung",
    "registereintrag",
    "auszahlung",
    "kein_entscheid",
    "unbekannt"
   ]
  },
  "entscheid_beleg": {
   "type": [
    "string",
    "null"
   ],
   "description": "verbatim phrase from the DVSH titel/kurzbeschreibung/ablauf of the service that shows what the Verfahren returns; null with unbekannt"
  },
  "ergebnis_dokument": {
   "type": [
    "string",
    "null"
   ]
  },
  "beilagen": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "bezeichnung": {
      "type": "string"
     },
     "data_field_id": {
      "type": [
       "integer",
       "null"
      ]
     },
     "obligatorium": {
      "type": "string",
      "enum": [
       "zwingend",
       "bedingt",
       "fakultativ",
       "unbekannt"
      ]
     },
     "bedingung": {
      "type": [
       "string",
       "null"
      ]
     },
     "halter": {
      "type": "string",
      "enum": [
       "privat",
       "einwohnerregister",
       "handelsregister",
       "betreibungsregister",
       "strafregister",
       "steuerverwaltung",
       "grundbuch",
       "kanton_andere",
       "bund",
       "unbekannt"
      ]
     },
     "fetchable": {
      "type": "boolean"
     },
     "source": {
      "type": "string",
      "enum": [
       "formular",
       "dvsh",
       "beide"
      ]
     }
    },
    "required": [
     "bezeichnung",
     "data_field_id",
     "obligatorium",
     "bedingung",
     "halter",
     "fetchable",
     "source"
    ]
   }
  },
  "hinweis": {
   "type": "string"
  }
 },
 "required": [
  "zweck",
  "entscheid_art",
  "entscheid_beleg",
  "ergebnis_dokument",
  "beilagen",
  "hinweis"
 ]
}
```

**Regeln `ERULES`**

```text
The citygov databank (SQLite <citygov.db>, READ-ONLY for you) maps every Angabe of a Formular to the eCH standard element that defines it. Catalogue: ech_standard (code, title, status, n_elements) and ech_element (id, standard, name, context, datatype …) — query them, e.g. sqlite3 "<citygov.db>" "SELECT code, title, status, n_elements FROM ech_standard WHERE title LIKE '%…%'" and "SELECT name, context, datatype FROM ech_element WHERE standard='eCH-0044' AND name LIKE '%…%'". See how comparable held fields were mapped: "SELECT d.name, e.standard, e.name FROM data_field d JOIN ech_element e ON e.id=d.ech_element_id WHERE d.name LIKE '%…%' LIMIT 20".
RULES (from real past failures):
- The unit is the ATOMIC part: judge every part (teilfeld) of a composite on its own; the composite field itself gets the container element if one exists, else its standard. Name → officialName, Vorname → firstName, Geburtsdatum → dateOfBirth, AHV-Nummer → vn, Telefon → eCH-0046 phoneNumber, E-Mail → eCH-0046 emailAddress, Strasse/PLZ/Ort → eCH-0010 address parts.
- The meaning comes from the PAIR (parent, part) and from the full label read to the end («… seit» is a date of a period); a yes/no box never takes a value element; a past, changed or period value never takes the current-value element.
- standard = an exact «eCH-NNNN» from ech_standard, never one with status Aufgehoben or Abgelöst; element copied VERBATIM from ech_element of that standard (mandatory when n_elements>0; empty only for a standard without elements).
- kein_standard only after searching the whole catalogue (290 standards) — say what you searched in grund.
- 'korrekt' only to confirm a value the databank already copied onto the row (ech_herkunft 'propagiert'): sqlite3 "<citygov.db>" "SELECT d.name, d.ech_status, d.ech_herkunft, e.standard, e.name FROM data_field d LEFT JOIN ech_element e ON e.id=d.ech_element_id WHERE d.form_id=<id>" and for parts "SELECT d.name, s.name, s.ech_status, e.standard, e.name FROM data_subfield s JOIN data_field d ON d.id=s.data_field_id LEFT JOIN ech_element e ON e.id=s.ech_element_id WHERE d.form_id=<id>".
- Judge EVERY field and EVERY part of the Formular. Read the Formular file for meaning. Never write files or the DB.
```

**Regeln `VRULES`**

```text
The citygov databank (SQLite <citygov.db>, READ-ONLY for you) records per Formular its Verfahren: the documents (Beilagen) the person must enclose, what the procedure returns, and the purpose for the register of processing activities. Sources: the Formular (file and its data fields: sqlite3 "<citygov.db>" "SELECT id, name, data_type, allowed_values FROM data_field WHERE form_id=<id> ORDER BY ord") and the DVSH model of its service (sqlite3 "<citygov.db>" "SELECT d.title, d.kurzbeschreibung, d.ablauf, d.unterlagen FROM dvsh_service d JOIN form f ON f.service_id=d.service_id WHERE f.id=<id>").
RULES:
- zweck: what the authority does with these Angaben and why, from the Formular's CONTENT, one German nominal sentence of 30-250 characters (house style «Prüfung der Voraussetzungen …», «Feststellung …», «Eintragung …»), never a repeat of the title; name a law only if the Formular itself names it. «Datum» only for a calendar date («Angabe(n)»/«Daten» otherwise), Swiss «ss», no risk words.
- entscheid_art from the 7 values with entscheid_beleg = a phrase copied VERBATIM from the DVSH title, kurzbeschreibung or ablauf of the service (the loader checks it and degrades to 'unbekannt' if it is not there). If DVSH does not say what comes back: 'unbekannt'. Never guess 'kein_entscheid' (it means no decision at all, e.g. a pure notification). A Handelsregister filing is 'registereintrag'.
- beilagen: one per document the Formular or the DVSH unterlagen actually demand; bezeichnung VERBATIM from that source (≤120 chars); source = formular / dvsh / beide; data_field_id only when an attachment-type field of THIS Formular names exactly this document; obligatorium 'zwingend' only when the source says it is required, 'bedingt' with the condition in bedingung, 'fakultativ' when optional, else 'unbekannt'; halter = who already holds or issues the document (register holders, kanton_andere, bund, privat, unbekannt); fetchable true only for an authority holder. Not a Beilage: the Formular itself, Merkblätter, the applicant's own signature.
- Never write files or the DB.
```

**Auftrag `ech`**

```text
${ERULES}\nFormular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}). Judge every field and part of it (read them from the DB as above).
```

**Auftrag `echreview`**

```text
${ERULES}\nYou are the SCEPTICAL second reviewer of these eCH verdicts for Formular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}):\n${JSON.stringify(e.urteile)}\nCheck each against the catalogue and the Formular: element really exists in that standard (verbatim), right context for the pair, no value element on a yes/no box, no current-value element on a past/period value, kein_standard only when nothing fits, every field and part covered. Return the CORRECTED complete list.
```

**Auftrag `verf`**

```text
${VRULES}\nFormular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}).
```

**Auftrag `verfreview`**

```text
${VRULES}\nYou are the SCEPTICAL second reviewer of this Verfahren record of Formular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}):\n${JSON.stringify(v)}\nCheck: entscheid_beleg really verbatim in the DVSH text, the kind of decision right, every demanded Beilage present and none invented, bezeichnung verbatim, obligatorium/halter/fetchable honest, the purpose from the content and not the title. Return the CORRECTED complete record and list your corrections in hinweis.
```

## Rechtsgrundlage

Citation per field (only articles whose text was read; the proof gate rejects anything not in the ingested law text), the basis type of an uncited field, the sensitive category.

**Ausgabe `R`**

```json
{
 "type": "object",
 "properties": {
  "felder": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "id": {
      "type": "integer",
      "description": "data_field.id"
     },
     "name": {
      "type": "string"
     },
     "cites": {
      "type": "array",
      "items": {
       "type": "object",
       "properties": {
        "cref": {
         "type": "string",
         "description": "'SHR nnn.nnn' or 'SR <sr_number>' exactly as in the valid-target query"
        },
        "article_no": {
         "type": "string",
         "description": "exactly as stored, e.g. 'Art. 28', '§ 7', 'Art. 12a' — never Abs./lit."
        },
        "beleg": {
         "type": "string",
         "description": "the article words that name or demand this Angabe"
        }
       },
       "required": [
        "cref",
        "article_no",
        "beleg"
       ]
      }
     },
     "over_collection": {
      "type": "boolean",
      "description": "true = no ingested law names this Angabe (NOT a verdict of surplus)"
     },
     "basis_typ": {
      "type": [
       "string",
       "null"
      ],
      "enum": [
       "aufgabe",
       "ohne",
       "offen",
       null
      ],
      "description": "only when cites is empty and over_collection true"
     },
     "basis_begruendung": {
      "type": [
       "string",
       "null"
      ]
     },
     "sensitiv": {
      "type": [
       "string",
       "null"
      ],
      "enum": [
       "gesundheit",
       "religion_weltanschauung",
       "politik",
       "ethnie_herkunft",
       "genetik_biometrie",
       "strafen_verfahren",
       "sozialhilfe",
       null
      ]
     },
     "sensitiv_beleg": {
      "type": [
       "string",
       "null"
      ]
     }
    },
    "required": [
     "id",
     "name",
     "cites",
     "over_collection",
     "basis_typ",
     "basis_begruendung",
     "sensitiv",
     "sensitiv_beleg"
    ]
   }
  },
  "hinweis": {
   "type": "string"
  }
 },
 "required": [
  "felder",
  "hinweis"
 ]
}
```

**Regeln `RULES`**

```text
The citygov databank (SQLite <citygov.db>, READ-ONLY for you) records for every data field of a Formular its legal basis, down to the article. Non-negotiable (from real past failures):
1. NEVER cite from memory. Cite only an article whose TEXT you have read and which names or demands this Angabe for this procedure. Read texts with: python3 <repo>/scripts/extract_law.py <pdf> --grep <Wort> (or --index); cantonal PDFs in <repo>/../Gesetze (file per law: python3 -c "import json;print([g for g in json.load(open('<repo>/inventory/gesetze_index.json')) if g['shr']=='<SHR>'])"), federal ones in <repo>/../Gesetze/Bund/<SR>.pdf; or article.text_excerpt where filled.
2. Valid targets only (the loader rejects everything else): sqlite3 "<citygov.db>" "SELECT COALESCE(l.cantonal_ref,'SR '||l.sr_number) cref, a.article_no, a.heading FROM article a JOIN law l ON l.id=a.law_id WHERE (a.last_checked LIKE 'Gesetze-PDF%' OR a.last_checked='verified') AND l.id=<law id>". Cite the bare article number exactly as stored, never Abs./lit./ff.
3. DVSH is authoritative for legal bases: START from the laws DVSH lists for the Formular's service: sqlite3 "<citygov.db>" "SELECT d.recht_kantonal, d.recht_bund FROM dvsh_service d JOIN form f ON f.service_id=d.service_id WHERE f.id=<form id>". Another ingested law may be cited only with article evidence.
4. over_collection=true means «no ingested law names this Angabe» — then judge basis_typ: 'aufgabe' (no norm names it, but the statutory task needs it — KDSG Art. 4 Abs. 1 lit. b), 'ohne' (neither norm nor task needs it — real surplus, shown as voluntary), 'offen' (assessed, not decidable). Optional Bemerkungen boxes are always 'aufgabe'. basis_begruendung: one German sentence (8–240 chars) about THIS procedure. If the basis is in a law that is NOT ingested, do not set over_collection: leave cites empty, over_collection false, basis_typ null, and name the law in hinweis (an honest «zu ermitteln»).
5. sensitiv: the category of besonders schützenswerte Personendaten (KDSG Art. 2 Abs. 1 lit. d) the Angabe IS: gesundheit, religion_weltanschauung, politik, ethnie_herkunft, genetik_biometrie, strafen_verfahren (Verfolgungen und Sanktionen), sozialhilfe (Massnahmen der sozialen Hilfe); null for everything else (most fields). A sensitive Angabe with only 'aufgabe' stays open (KDSG Art. 5 needs a formal basis) — look harder for a citing article there.
6. German texts: «Datum» only for a calendar date («Angabe»/«Daten» otherwise), Swiss «ss», no «Risiko/Verstoss».
7. One entry per field asked, with its id. Read the Formular file for meaning. Never write files or the DB.
```

**Auftrag `recht`**

```text
${RULES}\nFormular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}). Fields to judge: ${f.nur ? 'ONLY these ids (new Angaben of a ported edition): ' + f.nur.join(', ') : 'all of them'} — read them: sqlite3 "<citygov.db>" "SELECT id, name, definition, data_type, required, subfields FROM data_field WHERE form_id=${f.form_id} ORDER BY ord".
```

**Auftrag `rechtreview`**

```text
${RULES}\nYou are the SCEPTICAL second reviewer of this legal-basis record of Formular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}):\n${JSON.stringify(r)}\nRe-read every cited article yourself: does its text really name or demand this Angabe for this procedure, is the number exactly the stored one, is a DVSH-listed law overlooked? For uncited fields: is 'ohne' really surplus, is 'aufgabe' honest, should it rather be 'zu ermitteln' (law not ingested)? Is a sensitive category missed or wrongly set? Return the CORRECTED complete record (unchanged entries copied) and your corrections in hinweis.
```

## Nachtrag (articles that became citable later)

Used on 2026-11-05 after the Steuergesetz was re-read from the full PDF text: the reviewed record is completed with the newly valid articles only, each change reviewed again.

**Regeln `ZIELE`**

```text
These articles were NOT valid targets when the record below was made — missing from the article table (an ingest defect fixed on 05.11.2026: the cantonal Steuergesetz SHR 641.100 and its Verordnung SHR 641.111 are now read from the full PDF text; the lettered articles of DBG SR 642.11 and VStG SR 642.21 were dropped by the XML reader) or stored under a wrong heading («ueberschrift_korrigiert», with the wrong one in «vorher»). They are valid targets NOW. The list (cref, article_no exactly as stored, heading as stored, was = neu / ueberschrift_korrigiert) is the JSON file <neue_ziele.json> — read it first.
```

**Regeln `TASK`**

```text
TASK: complete this record with those articles — nothing else.
(a) every field WITHOUT a citation (basis_typ aufgabe/ohne/offen, or «zu ermitteln» = cites empty, over_collection false, basis_typ null): does one of the now-valid articles name or demand this Angabe for this procedure? Read its text first (extract_law.py --grep on the PDF). If yes: add the citation(s) with the article words as beleg, set over_collection false, basis_typ null, basis_begruendung null.
(b) every field whose citations the record's hinweis calls incomplete because a target was missing (e.g. «kein gültiges Ziel», «fehlt als Zeile»): add that article if its text names or demands the Angabe.
(c) every citation of an article whose heading was corrected: re-read the article; keep the citation only if its text names or demands the Angabe.
Everything else stays exactly as it is — copy unchanged entries verbatim (same id, name, cites, flags, texts). In hinweis list each change as «id: what, article, Beleg», or write «keine Änderung».
```

**Auftrag `nachtrag`**

```text
${RULES}
${ZIELE}
Formular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}); its fields: sqlite3 "<citygov.db>" "SELECT id, name, definition, data_type, required, subfields FROM data_field WHERE form_id=${f.form_id} ORDER BY ord".
The reviewed legal-basis record (A) is the JSON file ${f.record_file} — read it in full.
${TASK}
```

**Auftrag `nachtragreview`**

```text
${RULES}
${ZIELE}
You are the SCEPTICAL second reviewer of a completion of the legal-basis record of Formular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}). Record before (A): the JSON file ${f.record_file} (read it in full).
Completed record (B):
${JSON.stringify(b)}
Check EVERY entry where B differs from A: re-read each added article yourself — does its text really name or demand this Angabe for this procedure, is the number exactly the stored one (only the articles listed above are new)? Revert every change that does not hold; restore any entry B changed without cause to A. Also say if a field without citation in A clearly should have got one of the listed articles. Return the CORRECTED complete record and list your corrections in hinweis («keine» when none).
```

## Angleichung (legal basis across sibling Formulare)

One group per same-labelled Angabe; the example text `H` describes the tax Formulare 589–598 and is adapted per intake.

**Regeln `H`**

```text
The ten Formulare 589–598 are the 2026 tax declaration of legal persons of the Canton of Schaffhausen, all in ONE procedure (Veranlagung der Gewinn- und Kapitalsteuer und der direkten Bundessteuer): Formular 5 (589, Kapitalgesellschaften/Genossenschaften), 7 (592, Vereine/Stiftungen/übrige juristische Personen) and their schedules 6 (590), 6a (591), 8c (593), 12a (594), 13 (595), 14a (596), 19 (597), 19.1 (598); files: sqlite3 "<citygov.db>" "SELECT id, source_file FROM form WHERE id BETWEEN 589 AND 598" (under <repo>/). Their legal-basis records were made form by form, so the SAME Angabe got DIFFERENT verdicts (one form cites articles, another says 'aufgabe', a third cites other articles). The groups with their current entries are in the JSON file <gruppen.json> (key «gruppe», entries with form_id and the full record entry).
HARMONISE (rules above still apply in full):
- Same printed label AND same meaning in this one procedure => the same verdict on every form: the same set of citations (only articles whose text you read and that name or demand this Angabe for this procedure; a citation that holds on one form holds on all forms where the Angabe means the same) or, if none holds, the same basis_typ with the same reasoning.
- A form-specific meaning may justify a difference (e.g. «Zweck» on Formular 7 also decides the privileged taxation of ideal purposes; «Firmenname» on a certificate the company must issue under its own article; «Beilagen» as a count of enclosed Lohnausweise) — keep it and say why.
- Return one entry per listed field (same id and name), complete in the record schema, and in hinweis: whether the group is one Angabe, the verdict and why.
```

**Auftrag `recht-harmonie`**

```text
${RULES}
${H}
Your group: «${g}» — read its entries in ${FILE}. Decide and return the corrected entries for exactly the fields of this group.
```

**Auftrag `recht-harmonie-review`**

```text
${RULES}
${H}
You are the SCEPTICAL second reviewer of this harmonisation of the group «${g}» (entries before in ${FILE}):
${JSON.stringify(a)}
Re-read every cited article yourself (does its text name or demand this Angabe for this procedure, exact stored number); check that 'same Angabe' is true and every kept difference is justified, and that every field of the group has exactly one entry. Return the CORRECTED complete entries and your corrections in hinweis («keine» when none).
```

## Angleichung (eCH across sibling Formulare)

Same principle for the eCH element.

**Ausgabe `OUT`**

```json
{
 "type": "object",
 "properties": {
  "gruppen": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "gruppe": {
      "type": "string"
     },
     "gleiche_angabe": {
      "type": "boolean",
      "description": "true = all rows of the group are the same Angabe (then one element for all); false = they differ in meaning"
     },
     "begruendung": {
      "type": "string"
     },
     "urteile": {
      "type": "array",
      "items": {
       "type": "object",
       "properties": {
        "form_id": {
         "type": "integer"
        },
        "art": {
         "type": "string",
         "enum": [
          "feld",
          "teilfeld"
         ]
        },
        "feld": {
         "type": [
          "string",
          "null"
         ],
         "description": "art feld: data_field.name exactly"
        },
        "elternfeld": {
         "type": [
          "string",
          "null"
         ],
         "description": "art teilfeld: the parent data_field.name exactly"
        },
        "teilfeld": {
         "type": [
          "string",
          "null"
         ],
         "description": "art teilfeld: data_subfield.name exactly"
        },
        "urteil": {
         "type": "string",
         "enum": [
          "besser",
          "kein_standard",
          "korrekt"
         ]
        },
        "standard": {
         "type": [
          "string",
          "null"
         ]
        },
        "element": {
         "type": [
          "string",
          "null"
         ]
        },
        "grund": {
         "type": "string"
        }
       },
       "required": [
        "form_id",
        "art",
        "feld",
        "elternfeld",
        "teilfeld",
        "urteil",
        "standard",
        "element",
        "grund"
       ]
      }
     }
    },
    "required": [
     "gruppe",
     "gleiche_angabe",
     "begruendung",
     "urteile"
    ]
   }
  },
  "hinweis": {
   "type": "string"
  }
 },
 "required": [
  "gruppen",
  "hinweis"
 ]
}
```

**Regeln `RULES`**

```text
The citygov databank (SQLite <citygov.db>, READ-ONLY for you) maps every Angabe of a Formular (and every part of a composite) to the eCH element that defines it. Catalogue: ech_standard (code, title, status, n_elements) and ech_element (id, standard, name, context, datatype, …): sqlite3 "<citygov.db>" "SELECT name, context, datatype FROM ech_element WHERE standard='eCH-0229' AND name LIKE '%…%'". The ten Formulare 589–598 are the 2026 tax declaration of legal persons of the Canton of Schaffhausen (Formular 5 for companies, 7 for associations/foundations, and their schedules 6, 6a, 8c, 12a, 13, 14a, 19, 19.1); files: sqlite3 "<citygov.db>" "SELECT id, source_file FROM form WHERE id BETWEEN 589 AND 598" (under <repo>/). Their eCH layer was judged form by form, so the SAME Angabe got DIFFERENT elements on different forms (below). Rules:
- The same Angabe (same printed label AND same meaning in the same procedure) gets ONE element on all forms — choose the most exact one from the catalogue; a different meaning (e.g. «Beilagen» as a checklist vs. as a count of enclosed Lohnausweise) may keep a different element — say why.
- standard = exact «eCH-NNNN» from ech_standard, never status Aufgehoben/Abgelöst; element copied VERBATIM from ech_element of that standard; check its context/documentation (the element's context path) really fits a legal person's tax declaration.
- A part is judged as the pair (parent, part): «Name, Adresse» of «Organe – Präsident/-in» on Formular 7 (Vereine/Stiftungen) is the same printed cell as «Name, Adresse» of «Organe – Verwaltungsratspräsident/-in» on Formular 5 — but say whether the element of the VR-Präsident fits the president of an association/foundation.
- urteil 'besser' = set this element; 'korrekt' = the row already has exactly the chosen element; 'kein_standard' only after searching the whole catalogue.
- One verdict per row listed (form_id + feld, or form_id + elternfeld + teilfeld, names exactly as listed). German texts, Swiss «ss».
```

**Auftrag `harmonie`**

```text
${RULES}\nThe groups (current assignment per row):\n${data}\nDecide each group and return the verdicts for every row.
```

**Auftrag `harmonie-review`**

```text
${RULES}\nYou are the SCEPTICAL second reviewer of these harmonisation verdicts:\n${JSON.stringify(a)}\nfor these groups:\n${data}\nRe-check each chosen element in the catalogue (exists verbatim, status, context fits), whether «same Angabe» is really true, whether an exception is justified, and that every listed row has exactly one verdict. Return the CORRECTED complete verdicts and your corrections in hinweis («keine» when none).
```

## Subjekt und Rechtsmittel

Subjekt: whose Angabe a register-standard field is (natural person, organisation, …). Rechtsmittel: which provision governs the Formular's decision — a verdict, then three lenses.

**Ausgabe `SJ`**

```json
{
 "type": "object",
 "properties": {
  "verdicts": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "id": {
      "type": "integer"
     },
     "subjekt": {
      "type": "string",
      "enum": [
       "natuerliche_person",
       "organisation",
       "sache",
       "behoerde",
       "gemischt"
      ]
     },
     "grund": {
      "type": "string"
     }
    },
    "required": [
     "id",
     "subjekt",
     "grund"
    ]
   }
  }
 },
 "required": [
  "verdicts"
 ]
}
```

**Ausgabe `RV`**

```json
{
 "type": "object",
 "properties": {
  "quelle": {
   "type": "string",
   "enum": [
    "sektoral",
    "allgemein",
    "offen"
   ]
  },
  "regel_id": {
   "type": [
    "integer",
    "null"
   ]
  },
  "begruendung": {
   "type": "string"
  }
 },
 "required": [
  "quelle",
  "regel_id",
  "begruendung"
 ]
}
```

**Ausgabe `LV`**

```json
{
 "type": "object",
 "properties": {
  "refuted": {
   "type": "boolean"
  },
  "besser": {
   "type": [
    "object",
    "null"
   ],
   "properties": {
    "quelle": {
     "type": "string",
     "enum": [
      "sektoral",
      "allgemein",
      "offen"
     ]
    },
    "regel_id": {
     "type": [
      "integer",
      "null"
     ]
    }
   }
  },
  "grund": {
   "type": "string"
  }
 },
 "required": [
  "refuted",
  "besser",
  "grund"
 ]
}
```

**Regeln `SRULES`**

```text
The citygov databank records WHOSE Angabe a data field is (data_field.subjekt) — judged from the Formular's actual content, not from the eCH element. natuerliche_person = a private individual's own Angabe: the ONLY value that unlocks the once-only/Einwohnerregister mark, prefill and the Datentresor ledger, so use it only when the field is certainly about one natural person. organisation = a firm, association, foundation, cooperative. sache = an object, place, vehicle, parcel or event. behoerde = the authority's own data. gemischt = person or organisation both possible (conservative; gets no mark). grund: a short German reason (≥ 8 chars). Fields: sqlite3 "<citygov.db>" "SELECT d.id, d.name, d.definition, d.subfields FROM data_field d WHERE d.id IN (<ids>)". Read the Formular file for meaning. READ-ONLY.
```

**Regeln `RRULES`**

```text
The citygov databank records per Formular WHICH remedy provision governs the applicant's remedy against the decision of its Verfahren — a legal JUDGMENT, never a ranking. Material (READ-ONLY): the Formular (file), its decision: sqlite3 "<citygov.db>" "SELECT entscheid_art, ergebnis_dokument FROM form_outcome WHERE form_id=<id>"; the laws it cites: "SELECT DISTINCT l.id, COALESCE(l.cantonal_ref,'SR '||l.sr_number), l.title FROM data_field_legal_basis lb JOIN data_field d ON d.id=lb.data_field_id JOIN article a ON a.id=lb.article_id JOIN law l ON l.id=a.law_id WHERE d.form_id=<id>"; the CANDIDATES = the active sektoral rules of those laws: "SELECT rr.id, rr.law_id, a.article_no, rr.rechtsmittel_art, rr.frist_tage, rr.instanz, rr.gilt_fuer, rr.quote FROM rechtsmittel_regel rr JOIN article a ON a.id=rr.article_id WHERE rr.scope='sektoral' AND COALESCE(rr.gestrichen,0)=0 AND rr.law_id IN (<cited law ids>)"; how comparable held Formulare were judged: "SELECT v.form_id, f.title, v.quelle, v.regel_id, v.begruendung FROM rechtsmittel_verdikt v JOIN form f ON f.id=v.form_id WHERE f.title LIKE '%…%'".
Answers: 'sektoral' + regel_id (one of the candidates) when that provision covers the remedy against THIS decision — name the article and why; 'allgemein' when none of the candidates covers it, so the VRG general rule applies (Rekurs an den Regierungsrat, 20 Tage) — say why each candidate does not fit; 'offen' when it cannot be decided from the material (e.g. the governing law, often federal, is not among the candidates) — name what is missing. Known: every Handelsregister Formular so far got 'offen' or OR Art. 942 (rule 125), because HRegV Art. 33 Abs. 4 (rule 14) covers only the EHRA's refusal. Never a remedy outside the candidates. German, ≤ 400 chars.
```

**Auftrag `subjekt`**

```text
${SRULES}\nFormular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}). Judge exactly these field ids: ${f.ids.join(', ')}.
```

**Auftrag `subjektreview`**

```text
${SRULES}\nYou are the SCEPTICAL second reviewer of these subjekt verdicts for Formular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}): ${JSON.stringify(v.verdicts)}. Re-read the fields and the Formular. Typical errors: a firm's address judged natuerliche_person; a contact person of a firm judged organisation; «gemischt» where the Formular clearly names a private person (or the reverse). Return the verdict you hold correct for EVERY id (same as the first if you agree) with your reason.
```

**Auftrag `rm`**

```text
${RRULES}\nFormular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}). Give the verdict.
```

**Auftrag `linse`**

```text
${RRULES}\nYou are one of three INDEPENDENT reviewers (lens «${l}»: ${what[l]}) of this remedy verdict for Formular ${f.form_id} «${f.title}» (file <repo>/formulare/${f.f}): ${JSON.stringify(v)}. Try to refute it through your lens. refuted=true only with a concrete reason; then name the verdict you hold right in besser (regel_id only among the candidates). Otherwise refuted=false, besser null.
```

## After loading

* Remedy reasons are shown to readers: at most 400 characters and none of the review's internal
  words («Kandidat», «Zweitprüfung», «im Material», «Regel N») — `apply_panel.py rechtsmittel`
  stops on them; reword and keep the panel's text as `begruendung_panel`.
* A basis reason that says «Datum» must mean a calendar date and be listed as «behalten» in
  `quellen/wortwahl_datum.json`, else reworded («Angabe»).
* Then `scripts/extract_quotes.py`, `scripts/gesetz_stand.py`, `scripts/build_similarity.py`
  and the build (MAINTAINING.md, «Publishing»).
