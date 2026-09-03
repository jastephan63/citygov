#!/usr/bin/env python3
"""The plain-language guide (Leitfaden) shown on the dashboard's Leitfaden tab.

The Datenhandhabung tab lists all 247 verified rules — complete but dense.
This module answers the practical questions in plain German: how may data be
collected, what and where may it be stored, may we check a document without
keeping a copy, how may data be used and passed on, how long is it kept.

Every bullet carries refs into the verified rule corpus: (SR/SHR, article,
aspect[, scope]). build_dashboard.py refuses to build if a ref does not
resolve to a loaded data_rule row, so the guide can never cite law that is
not in the databank. Interpretive advice (not a rule paraphrase) goes into
a 'praxis' box that is visibly labelled as Einordnung, not Gesetzeszitat.

Every section was adversarially reviewed against the rule quotes in the DB
(workflow verify-leitfaden); the wording below carries those corrections —
be precise about actors (Kanton vs. Bundesorgane), qualifiers ("in der
Regel", "mindestens") and alternative conditions before editing.
"""

# ref = (sr_number, article_no, aspect) or (sr_number, article_no, aspect, scope)
LEITFADEN = [
 {
  "id": "erheben",
  "frage": "Erheben — wie dürfen wir Daten überhaupt sammeln?",
  "kurz": "Nur was für die gesetzliche Aufgabe wirklich nötig ist, nur zu einem für "
          "die Person erkennbaren Zweck, und im Grundsatz direkt bei der Person "
          "selbst — nicht hinter ihrem Rücken bei Dritten.",
  "punkte": [
   {"text": "Daten sind grundsätzlich direkt bei der betroffenen Person zu erheben. "
            "Wer systematisch Daten beschafft (z.B. mit einem Formular), muss zudem "
            "darauf hinweisen, wenn die Person zur Auskunft nicht verpflichtet ist — "
            "freiwillige Angaben müssen als freiwillig erkennbar sein.",
    "refs": [("174.100", "Art. 7", "erhebung"), ("235.11", "Art. 30", "erhebung")]},
   {"text": "Der Zweck muss bei der Beschaffung feststehen und für die Person erkennbar "
            "sein — ein Formularfeld «auf Vorrat» ist unzulässig.",
    "refs": [("235.1", "Art. 6", "erhebung")]},
   {"text": "Die Person muss wissen: wer bearbeitet die Daten, wozu, und an wen gehen "
            "sie? Diese Information ist auch geschuldet, wenn die Daten ausnahmsweise "
            "bei Dritten (etwa einer anderen Behörde) beschafft werden.",
    "refs": [("174.100", "Art. 5a", "betroffenenrechte"), ("235.1", "Art. 19", "betroffenenrechte")]},
   {"text": "Es gilt Datenminimierung: Systeme und Voreinstellungen müssen die "
            "Bearbeitung auf das Nötige beschränken — jedes Feld braucht einen Grund.",
    "refs": [("235.1", "Art. 7", "bearbeitung"), ("235.1", "Art. 6", "bearbeitung", "allgemein")]},
  ],
  "praxis": "Genau dafür markiert diese Databank Felder ohne gesetzliche Grundlage als "
            "Over-collection: ein Formularfeld, das keine Rechtsgrundlage hat, dürfte "
            "so nicht erhoben werden.",
 },
 {
  "id": "speichern",
  "frage": "Speichern — was darf wohin?",
  "kurz": "Gespeichert wird nur, was die eigene Aufgabe erfordert; Register enthalten "
          "nur die gesetzlich oder per Reglement abschliessend festgelegten Daten "
          "(abschliessend heisst: nur diese, keine weiteren). Alles wird nach "
          "Schutzbedarf klassifiziert und gegen unbefugten Zugriff gesichert; die "
          "elektronische Langzeitablage muss in der Schweiz liegen.",
  "punkte": [
   {"text": "Register führen heisst: nur die abschliessend festgelegten Daten. Das "
            "Einwohnerregister etwa führt die Merkmale nach "
            "Registerharmonisierungsrecht, die in Art. 88 Gemeindegesetz zusätzlich "
            "aufgezählten Daten sowie allfällige vom Gemeinderat in einem allgemein "
            "verbindlichen Reglement bezeichnete Personendaten — mehr nicht. Für "
            "Adressbücher und Verzeichnisse gilt dieselbe Logik.",
    "refs": [("120.100", "88", "speicherung"), ("431.101", "§ 1", "speicherung"),
             ("174.101", "§ 1", "bekanntgabe")]},
   {"text": "In die Registratur (Aktenablage) gehören nur Akten, die aus der eigenen "
            "Tätigkeit anfallen oder für die Erfüllung der eigenen Aufgaben "
            "erforderlich sind; elektronische Datensammlungen müssen im "
            "Registraturplan erfasst sein.",
    "refs": [("172.301", "§ 3", "speicherung"), ("172.301", "§ 5", "speicherung")]},
   {"text": "Vor dem Speichern wird der Schutzbedarf bestimmt und klassifiziert — "
            "nach Verfügbarkeit, Vertraulichkeit, Integrität und Nachvollziehbarkeit; "
            "besonders schützenswerte Daten bis zur höchsten Vertraulichkeitsstufe.",
    "refs": [("174.102", "Art. 5", "sicherheit"), ("174.102", "Art. 6", "sicherheit")]},
   {"text": "Gespeicherte Daten sind durch Speicher- und Zugriffskontrollen zu schützen; "
            "Zugriff erhält nur, wer ihn für seine Tätigkeit braucht (Rollenprinzip). "
            "Backups werden gesondert und gesichert aufbewahrt.",
    "refs": [("235.11", "Art. 3", "speicherung"), ("174.102", "Art. 10", "sicherheit"),
             ("174.102", "Art. 12", "speicherung")]},
   {"text": "Die elektronische Langzeitarchivierung darf innerhalb oder ausserhalb des "
            "Kantons liegen — aber nur in der Schweiz.",
    "refs": [("172.301", "§ 15", "speicherung")]},
  ],
  "praxis": "Zur Cloud-Frage: Einen Schweizer Serverstandort schreibt von den erfassten "
            "Regeln nur die Langzeitarchivierung ausdrücklich vor. Für die laufende "
            "Bearbeitung greifen stattdessen die Auslagerungs-Regeln (der Dritte darf "
            "nur bearbeiten, was das Amt selbst dürfte; keine Geheimhaltungspflicht "
            "darf entgegenstehen) und die ISV-Sicherheitsanforderungen — ein "
            "Cloud-Einsatz ist also kein Standort-, sondern ein Vertrags- und "
            "Sicherheitsthema.",
 },
 {
  "id": "pruefvermerk",
  "frage": "«Gesehen und geprüft» — müssen wir eine Kopie behalten?",
  "kurz": "Nicht immer. Das Recht verlangt sogar, nicht mehr und nicht länger "
          "aufzubewahren als nötig. Ist ein Dokument nur einmalig zu kontrollieren, "
          "genügt der dokumentierte Prüfvermerk. Ist es aber Grundlage eines "
          "Entscheids oder gilt eine Aufbewahrungspflicht, gehört es in die Akte.",
  "punkte": [
   {"text": "Daten dürfen nicht länger aufbewahrt und bearbeitet werden, als der Zweck "
            "es erfordert; nicht mehr Erforderliches ist zu vernichten oder zu "
            "anonymisieren. Eine unnötige Kopie ist also nicht «sicherheitshalber gut», "
            "sondern ein Rechtsrisiko.",
    "refs": [("174.100", "Art. 4", "aufbewahrung"), ("235.1", "Art. 6", "loeschung")]},
   {"text": "Umgekehrt gilt die Registraturpflicht: Akten, die aus der eigenen Tätigkeit "
            "anfallen oder für die Aufgabenerfüllung erforderlich sind, werden "
            "aufbewahrt, solange die Verwaltung sie braucht — in der Regel mindestens "
            "zehn Jahre; die Registraturperioden selbst betragen in der Regel zehn "
            "bis zwanzig Jahre.",
    "refs": [("172.301", "§ 3", "speicherung"), ("172.301", "§ 6", "aufbewahrung"),
             ("172.301", "§ 5", "aufbewahrung")]},
   {"text": "Fachrecht kann die Aufbewahrung des Belegs selbst verlangen — etwa "
            "Krankengeschichten (mindestens zehn Jahre nach der letzten Behandlung) "
            "oder Waffenerwerbs-Unterlagen (zwanzig Jahre). Solche Spezialfristen "
            "gehen vor.",
    "refs": [("810.102", "§ 36", "aufbewahrung"), ("514.54", "Art. 21", "aufbewahrung")]},
  ],
  "praxis": "Faustregel: Stützt sich ein Entscheid auf das Dokument, gehört es "
            "(oder eine Kopie) in die Akte — es muss nachvollziehbar bleiben, worauf "
            "entschieden wurde. Dient das Dokument nur der einmaligen Kontrolle "
            "(z.B. einen Ausweis vorzeigen), genügt der Vermerk: wer hat wann was "
            "geprüft, mit welchem Ergebnis — ohne Kopie. Das ist die datensparsamste "
            "Umsetzung der Verhältnismässigkeit.",
 },
 {
  "id": "verwenden",
  "frage": "Verwenden — wofür dürfen wir die Daten nutzen?",
  "kurz": "Nur für den Zweck, der bei der Erhebung genannt wurde, sich klar aus den "
          "Umständen ergibt oder im Gesetz steht. Ein neuer Zweck braucht eine neue "
          "Grundlage. Wer Dritte bearbeiten lässt oder riskante Bearbeitungen plant, "
          "hat zusätzliche Pflichten.",
  "punkte": [
   {"text": "Zweckbindung: Daten dürfen nur für den bei der Beschaffung angegebenen, "
            "ersichtlichen oder gesetzlich vorgesehenen Zweck verwendet werden. "
            "Zulässig ist die Bearbeitung gestützt auf eine gesetzliche Grundlage, "
            "zur Erfüllung der gesetzlich umschriebenen Aufgaben oder mit Zustimmung "
            "der betroffenen Person; Bundesorgane brauchen stets eine gesetzliche "
            "Grundlage.",
    "refs": [("174.100", "Art. 4", "bearbeitung"), ("235.1", "Art. 34", "bearbeitung", "allgemein")]},
   {"text": "Für Statistik, Planung und Forschung dürfen Daten nur verwendet werden, "
            "wenn sie so früh wie möglich anonymisiert werden, keine Rückschlüsse auf "
            "Personen möglich sind und die oder der Datenschutzbeauftragte zustimmt.",
    "refs": [("174.100", "Art. 12", "bearbeitung"), ("235.1", "Art. 39", "bearbeitung")]},
   {"text": "Auslagerung (Auftragsbearbeitung) ist nur zulässig, wenn keine "
            "Rechtsvorschrift oder Geheimhaltungspflicht entgegensteht und der Dritte "
            "die Daten nur so bearbeitet, wie es das Amt selbst dürfte. Der Auftrag "
            "ist grundsätzlich schriftlich zu erteilen und muss Rückgabe oder "
            "Vernichtung der Daten nach Vertragsende regeln.",
    "refs": [("174.100", "Art. 13", "bearbeitung"), ("174.101", "§ 3", "bearbeitung"),
             ("235.1", "Art. 9", "bearbeitung")]},
   {"text": "Vor Bearbeitungen mit erhöhtem Risiko für die Grundrechte braucht es eine "
            "Datenschutz-Folgenabschätzung; bleibt ein hohes Risiko, muss vorab die "
            "Aufsichtsstelle (kantonal: die oder der Datenschutzbeauftragte) Stellung "
            "nehmen. Alle Bearbeitungstätigkeiten stehen in einem Verzeichnis.",
    "refs": [("174.100", "Art. 14b", "bearbeitung"), ("174.100", "Art. 14c", "bearbeitung"),
             ("235.1", "Art. 22", "bearbeitung"), ("235.1", "Art. 12", "bearbeitung")]},
  ],
 },
 {
  "id": "weitergeben",
  "frage": "Weitergeben — an wen dürfen die Daten?",
  "kurz": "Nur bei gesetzlicher Grundlage, wenn der Empfänger die Daten für seine "
          "gesetzlichen Aufgaben benötigt, mit Zustimmung der Person — oder wenn sie "
          "ihre Daten selbst allgemein zugänglich gemacht hat. Schweigepflichten "
          "gehen vor, soweit kein Gesetz die Auskunft verlangt; die Bekanntgabe an "
          "Private lässt sich sperren, und ins Ausland geht nur, was dort angemessen "
          "geschützt ist.",
  "punkte": [
   {"text": "Grundregel: Bekanntgabe braucht eine gesetzliche Grundlage, einen "
            "Empfänger, der die Daten für seine gesetzlichen Aufgaben benötigt, die "
            "Zustimmung der betroffenen Person — oder Daten, die die Person selbst "
            "allgemein zugänglich gemacht hat. Stehen wesentliche öffentliche "
            "Interessen oder offensichtlich schutzwürdige Interessen einer betroffenen "
            "Person entgegen, muss die Stelle die Bekanntgabe ablehnen, einschränken "
            "oder an Auflagen knüpfen.",
    "refs": [("174.100", "Art. 8", "bekanntgabe"), ("174.100", "Art. 10", "bekanntgabe")]},
   {"text": "An Private gibt die Einwohnerregisterstelle ohne besonderes Interesse nur "
            "Name, Vorname, Adresse, Zu-/Wegzugsdatum und Beruf heraus — und jede "
            "Person kann die Bekanntgabe an Private sperren lassen (Meldung an das "
            "verantwortliche Organ; Behörden-Amtshilfe lässt sich nicht sperren).",
    "refs": [("174.100", "Art. 9", "bekanntgabe"), ("174.100", "Art. 11", "betroffenenrechte"),
             ("174.101", "§ 2", "betroffenenrechte")]},
   {"text": "Unter Behörden gilt Amtshilfe nach Fachrecht: die Gesetze sagen genau, "
            "welche Stelle welcher anderen Stelle was liefern muss — etwa unter "
            "Steuerbehörden oder an die Migrationsbehörden.",
    "refs": [("641.100", "Art. 128", "bekanntgabe"), ("641.100", "Art. 129", "bekanntgabe"),
             ("142.20", "Art. 97", "bekanntgabe")]},
   {"text": "Schweigepflichten sind die Gegenkraft: Berufsgeheimnis, Sozialhilfe-, "
            "Steuer-, Personal- und Amtsgeheimnis verbieten die Weitergabe ausserhalb "
            "der gesetzlichen Kanäle — auch nach Ende des Arbeitsverhältnisses.",
    "refs": [("235.1", "Art. 62", "bekanntgabe"), ("810.100", "Art. 15", "bekanntgabe"),
             ("850.100", "Art. 6", "bekanntgabe"), ("641.100", "Art. 127", "bekanntgabe"),
             ("180.100", "Art. 34", "bekanntgabe"), ("120.100", "Art. 14", "bekanntgabe")]},
   {"text": "Ins Ausland nur, wenn dort ein angemessenes Datenschutzniveau besteht "
            "(massgeblich ist die vom Bundesrat festgestellte Staatenliste — das muss "
            "niemand selbst beurteilen), wenn besondere Garantien vorliegen oder wenn "
            "im Einzelfall eine gesetzliche Ausnahme greift — namentlich Einwilligung "
            "der Person, Schutz von Leib und Leben oder überwiegende öffentliche "
            "Interessen. Für EU/EWR-Stellen gelten erleichterte Regeln.",
    "refs": [("174.100", "Art. 11a", "bekanntgabe"), ("174.100", "Art. 11b", "bekanntgabe"),
             ("235.1", "Art. 16", "bekanntgabe"), ("235.1", "Art. 17", "bekanntgabe")]},
   {"text": "Personendaten sind nie Open Government Data; elektronischer Datenaustausch "
            "zwischen Behörden läuft über geregelte Schnittstellen.",
    "refs": [("172.019", "Art. 10", "bekanntgabe"), ("172.019", "Art. 13", "bekanntgabe")]},
  ],
  "praxis": "Zum Übermittlungsweg sagen die Bekanntgabe-Regeln nichts Ausdrückliches — "
            "aber die Sicherheitsregeln (Zugriffs-, Transport- und "
            "Empfängerkontrollen nach KDSV und ISV) gelten auch beim Versand. "
            "Besonders schützenswerte Daten gehören darum nicht in unverschlüsselte "
            "E-Mails; zwischen Behörden sind die geregelten Kanäle zu nutzen.",
 },
 {
  "id": "fristen",
  "frage": "Wie lange aufbewahren?",
  "kurz": "So lange, wie die Aufgabe es erfordert und die Registraturperiode läuft "
          "(in der Regel 10–20 Jahre) — nicht länger, aber auch nicht kürzer, wenn "
          "Fachrecht eigene Fristen setzt. Welche Frist für die konkrete Akte gilt, "
          "steht im Registraturplan der eigenen Dienststelle.",
  "punkte": [
   {"text": "Obergrenze: nicht länger aufbewahren, als der Bearbeitungszweck es "
            "erfordert. Untergrenze: Akten bleiben in der Registratur, solange die "
            "laufende Verwaltungstätigkeit sie braucht, in der Regel mindestens zehn "
            "Jahre; die Registraturperioden betragen in der Regel zehn bis zwanzig "
            "Jahre und sind im Registraturplan festgelegt — dort schlägt man die "
            "eigene Frist nach.",
    "refs": [("174.100", "Art. 4", "aufbewahrung"), ("172.301", "§ 6", "aufbewahrung"),
             ("172.301", "§ 5", "aufbewahrung")]},
   {"text": "Fachrecht setzt eigene Fristen — Beispiele aus dieser Databank: "
            "Krankengeschichten mindestens 10 Jahre nach Abschluss der letzten "
            "Behandlung; Waffenhandelsunterlagen 20 Jahre; Waffeninformationssysteme "
            "bis zu 50 Jahre (Systeme über Erwerb und Besitz: 30 Jahre nach "
            "Vernichtung der Waffe); Arbeitslosenversicherung: Geschäftsbücher und "
            "Belege 10 Jahre, Versicherungsfall-Daten 5 Jahre nach der letzten "
            "Bearbeitung; Disziplinareinträge im Medizinalberuferegister 5 Jahre nach "
            "Aufhebung bzw. Anordnung (befristete Berufsausübungsverbote werden nach "
            "10 Jahren als gelöscht vermerkt).",
    "refs": [("810.102", "§ 36", "aufbewahrung"), ("514.54", "Art. 21", "aufbewahrung"),
             ("514.541", "Art. 66", "aufbewahrung"), ("837.02", "Art. 125", "aufbewahrung"),
             ("811.11", "Art. 54", "loeschung")]},
   {"text": "Auch Neben-Daten haben Fristen: Bearbeitungsprotokolle mindestens ein "
            "Jahr, Datenschutz-Folgenabschätzungen mindestens zwei Jahre nach Ende "
            "der Bearbeitung.",
    "refs": [("235.11", "Art. 4", "aufbewahrung"), ("235.11", "Art. 14", "aufbewahrung")]},
  ],
 },
 {
  "id": "archivieren",
  "frage": "Archivieren und Vernichten — was passiert am Ende?",
  "kurz": "Nicht mehr Benötigtes wird zuerst dem Staatsarchiv angeboten — einfach "
          "löschen ist verboten. Erst was das Archiv nicht übernimmt, wird "
          "datenschutzgerecht vernichtet. Im Archiv schützen Sperrfristen die "
          "Personendaten weiter.",
  "punkte": [
   {"text": "Anbietepflicht: Nicht mehr benötigte Akten einer Registraturperiode "
            "werden dem Staatsarchiv gesamthaft zur Übernahme angeboten; für "
            "Bundesunterlagen gilt eine entsprechende Anbietepflicht gegenüber dem "
            "Bundesarchiv.",
    "refs": [("172.301", "§ 7", "archivierung"), ("172.301", "§ 14", "archivierung"),
             ("174.100", "Art. 17", "archivierung"), ("152.1", "Art. 6", "archivierung")]},
   {"text": "Vernichten ohne das Archiv geht nicht: anbietepflichtige Unterlagen dürfen "
            "nur mit Zustimmung des Archivs vernichtet werden; was es nicht übernimmt, "
            "ist unter Wahrung des Datenschutzes zu vernichten. Widerrechtlich "
            "bearbeitete Daten sind auf Verlangen der betroffenen Person zu "
            "vernichten.",
    "refs": [("152.1", "Art. 8", "loeschung"), ("172.301", "§ 7", "loeschung"),
             ("174.100", "Art. 17", "loeschung"), ("174.100", "Art. 21", "loeschung")]},
   {"text": "Im Archiv gelten Sperrfristen: Verwaltungsakten unter Ausschluss der "
            "Öffentlichkeit 50 Jahre, Bundesarchivgut 30 Jahre — und abgeliefertes "
            "Archivgut darf nicht mehr verändert werden.",
    "refs": [("172.301", "§ 17", "bekanntgabe", "allgemein"), ("152.1", "Art. 9", "bekanntgabe"),
             ("152.1", "Art. 14", "bearbeitung")]},
  ],
 },
 {
  "id": "rechte",
  "frage": "Rechte der Betroffenen — was können die Personen verlangen?",
  "kurz": "Auskunft (beim Bund innert 30 Tagen; kantonal ohne feste Frist, aber "
          "grundsätzlich kostenlos), Berichtigung, Sperrung der Bekanntgabe an "
          "Private und Vernichtung widerrechtlich bearbeiteter Daten. Ablehnungen "
          "müssen begründet und anfechtbar sein.",
  "punkte": [
   {"text": "Jede Person erhält auf Verlangen in verständlicher Form Auskunft, ob und "
            "welche Daten über sie bearbeitet werden — grundsätzlich kostenlos und "
            "schriftlich verlangt, gerichtet an die Stelle, die die Daten bearbeitet. "
            "Beim Bund gilt eine Frist von 30 Tagen; das kantonale Recht setzt keine "
            "feste Frist. Einschränkungen sind nur in engen gesetzlichen Grenzen "
            "zulässig und müssen begründet werden.",
    "refs": [("174.100", "Art. 18", "betroffenenrechte"), ("235.11", "Art. 18", "betroffenenrechte"),
             ("235.11", "Art. 16", "betroffenenrechte"), ("174.101", "§ 9", "betroffenenrechte"),
             ("174.100", "Art. 19", "betroffenenrechte")]},
   {"text": "Unrichtige Daten sind kostenlos zu berichtigen; lässt sich weder "
            "Richtigkeit noch Unrichtigkeit feststellen, wird ein Bestreitungsvermerk "
            "angebracht. Frühere Empfänger sind zu informieren, sofern sie die Daten "
            "voraussichtlich noch bearbeiten; bei unverhältnismässigem Aufwand kann "
            "darauf verzichtet werden.",
    "refs": [("174.100", "Art. 20", "betroffenenrechte"), ("174.100", "Art. 17a", "betroffenenrechte")]},
   {"text": "Sperren und wehren: Die Bekanntgabe der eigenen Daten an Private kann "
            "gesperrt werden (Meldung an das verantwortliche Organ). Wer ein "
            "schutzwürdiges Interesse dartut, kann zudem die Unterlassung "
            "widerrechtlicher Bearbeitung und die Vernichtung widerrechtlich "
            "bearbeiteter Daten verlangen.",
    "refs": [("174.100", "Art. 11", "betroffenenrechte"), ("174.101", "§ 2", "betroffenenrechte"),
             ("174.100", "Art. 21", "betroffenenrechte")]},
   {"text": "Daten, die die Person selbst bekanntgegeben hat und die automatisiert "
            "bearbeitet werden, kann sie in einem gängigen elektronischen Format "
            "herausverlangen oder übertragen lassen (Bundesrecht).",
    "refs": [("235.1", "Art. 28", "betroffenenrechte"), ("235.11", "Art. 21", "betroffenenrechte")]},
   {"text": "Wird ein Begehren abgelehnt, braucht es einen begründeten, anfechtbaren "
            "Entscheid. Bei einer Datenschutzverletzung ist die betroffene Person zu "
            "informieren, wenn es zu ihrem Schutz erforderlich ist oder die "
            "Aufsichtsstelle (Bund: der EDÖB) es verlangt.",
    "refs": [("174.100", "Art. 22", "betroffenenrechte"), ("174.100", "Art. 14a", "betroffenenrechte"),
             ("235.1", "Art. 24", "betroffenenrechte")]},
  ],
 },
 {
  "id": "sensibel",
  "frage": "Besonders schützenswerte Daten (⛨) — was gilt zusätzlich?",
  "kurz": "Gesundheit, Religion, politische Ansichten, Sozialhilfe, Straf- und "
          "Disziplinardaten: hier braucht die Bearbeitung ein formelles Gesetz "
          "(vom Parlament beschlossen, nicht bloss eine Verordnung) oder eine enge "
          "Ausnahme, Einwilligungen müssen ausdrücklich sein, und im kantonalen "
          "Archiv gilt eine Sperrfrist von 100 Jahren.",
  "punkte": [
   {"text": "Bearbeitung und Profiling nur, wenn ein formelles Gesetz es ausdrücklich "
            "vorsieht, die Aufgabe es zwingend erfordert (unentbehrlich) oder die "
            "Person ausdrücklich einwilligt — das gilt im Kanton wie beim Bund.",
    "refs": [("174.100", "Art. 5", "bearbeitung", "besonders_schuetzenswert"),
             ("235.1", "Art. 34", "bearbeitung", "besonders_schuetzenswert")]},
   {"text": "Wo eine Einwilligung nötig ist, muss sie für besonders schützenswerte "
            "Daten ausdrücklich erfolgen — Stillschweigen genügt nicht.",
    "refs": [("235.1", "Art. 6", "bearbeitung", "besonders_schuetzenswert")]},
   {"text": "Bundesorgane dürfen solche Daten Privaten für nicht personenbezogene "
            "Zwecke nur so bekanntgeben, dass die Personen nicht bestimmbar sind. "
            "Im kantonalen Archiv gilt für besonders schützenswerte Personendaten "
            "eine Sperrfrist von 100 Jahren; beim Bund unterliegt nach Personennamen "
            "erschlossenes Archivgut mit solchen Daten einer verlängerten Schutzfrist "
            "von 50 Jahren (Ende drei Jahre nach dem Tod).",
    "refs": [("235.1", "Art. 39", "bekanntgabe", "besonders_schuetzenswert"),
             ("152.1", "Art. 11", "bekanntgabe", "besonders_schuetzenswert"),
             ("172.301", "§ 17", "bekanntgabe", "besonders_schuetzenswert")]},
   {"text": "Die Fachgesetze verschärfen zusätzlich: Schweigepflicht der "
            "Gesundheitsberufe (inkl. Hilfspersonen), gesicherte Aufbewahrung von "
            "Gesundheitsbefunden, Sozialhilfe-Geheimnis, eingeschränkte Kreise für "
            "Disziplinardaten.",
    "refs": [("810.100", "Art. 15", "bekanntgabe"), ("741.51", "Art. 11c", "sicherheit"),
             ("850.100", "Art. 6", "bekanntgabe"), ("811.11", "Art. 53", "bekanntgabe")]},
  ],
  "praxis": "In dieser Databank tragen betroffene Felder das ⛨-Zeichen mit ihrer "
            "Kategorie. Wo ein ⛨-Feld auftaucht, gelten die Regeln dieses Abschnitts "
            "zusätzlich zum normalen Programm — Regeln, die nur Bundesorgane binden, "
            "sind oben als solche gekennzeichnet.",
 },
]
