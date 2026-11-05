"""The full-text reader of ingest_laws.py (articles_text) on line sequences as the official law
PDFs print them (the cases of 2026-11-05: GG Art. 73, PolV § 31a, PolG Art. 24h, KRG Art. 56,
Pflegekinderverordnung Anhang 1a, KV Art. 44, GG Art. 98, SHR 831.301 § 1)."""

from tests import TestCase


def lesen(text):
    from citygov.load.ingest_laws import articles_text
    arts, aufgehoben = articles_text(text.strip("\n").split("\n"))
    return {a["no"]: a["heading"] for a in arts}, aufgehoben


class Volltextleser(TestCase):
    def test_absatzbereich_aufgehoben_artikel_bleibt(self):
        arts, weg = lesen("""
Art. 72 Ausgabenbewilligung
1
Die Gemeindeverfassung bestimmt, welche Ausgaben bewilligt werden.
Art. 73 Rechnungsablage
*
1–2
…
3
Wird die Rechnung nicht genehmigt, so hat sie der Gemeinderat nochmals vorzulegen.
Art. 74
*
…
""")
        self.assertEqual(arts.get("Art. 73"), "Rechnungsablage")
        self.assertEqual(weg, ["Art. 74"])

    def test_absatzbereich_alle_aufgehoben(self):
        arts, weg = lesen("""
Art. 36 Zuständigkeit
1
Zuständig ist das Departement.
Art. 37 Erstattung
1–3
*
…
Art. 38 Berechnung
1
Die Berechnung erfolgt jährlich.
""")
        self.assertNotIn("Art. 37", arts)
        self.assertEqual(weg, ["Art. 37"])

    def test_verweiszeile_mit_gesetzeskuerzel_vor_seitenumbruch(self):
        arts, _ = lesen("""
§ 31a
* Bewilligungsgesuche
1
Gesuche um Erteilung einer Bewilligung im Sinne von Art. 27 Abs. 1 i.V.m.
Art. 27a PolG sind der Schaffhauser Polizei einzureichen.
12
Kanton Schaffhausen 354.111
2
Bewilligungsgesuche haben folgende Unterlagen zu enthalten:
""")
        self.assertEqual(list(arts), ["§ 31a"])
        self.assertEqual(arts["§ 31a"], "Bewilligungsgesuche")

    def test_verweiszeile_mit_absatz_danach(self):
        arts, _ = lesen("""
Art. 24h Wegweisung
1
Der Entscheid wird den Betroffenen vorerst mündlich und unter Hinweis auf
Art. 292 StGB eröffnet.
5
Die schriftliche Wegweisungsverfügung ist summarisch zu begründen.
""")
        self.assertEqual(list(arts), ["Art. 24h"])

    def test_fussnote_nicht_in_der_ueberschrift(self):
        arts, _ = lesen("""
Art. 55a
*
…
Art. 56 Änderung von Gesetzen und Dekreten12)
12)Gegenstandslos.
17
172.200 Kanton Schaffhausen
Art. 57 Übergangsbestimmung
1
Hängige Verfahren werden nach bisherigem Recht erledigt.
""")
        self.assertEqual(arts.get("Art. 56"), "Änderung von Gesetzen und Dekreten")
        self.assertEqual(arts.get("Art. 57"), "Übergangsbestimmung")

    def test_anhang_nummern(self):
        arts, _ = lesen("""
§ A1a-1
*
1
Für Pflegefamilien gemäss § 5 Abs. 2 gelten folgende Bestimmungen:
§ A1a-2
* Zusätzliche Unterlagen zum Bewilligungsgesuch
1
a) b) Mit dem Bewilligungsgesuch sind folgende Unterlagen einzureichen:
""")
        self.assertEqual(arts.get("§ A1a-2"), "Zusätzliche Unterlagen zum Bewilligungsgesuch")

    def test_satzende_auf_der_artikelzeile(self):
        arts, _ = lesen("""
Art. 43 Unvereinbarkeit
1
Dem Regierungsrat dürfen nicht gleichzeitig angehören: Eltern und Kinder, Geschwister.
*
Art. 44 pflichtet.
Verpflichtung auf Verfassung und Gesetz
1
Behördenmitglieder werden vor Amtsantritt auf Verfassung und Gesetz ver-
Art. 45 Ausstand
1
Ein Mitglied tritt in den Ausstand.
""")
        self.assertEqual(arts.get("Art. 44"), "Verpflichtung auf Verfassung und Gesetz")
        self.assertIn("Art. 45", arts)

    def test_verweis_satzende_ohne_folge_ist_kein_artikel(self):
        arts, _ = lesen("""
Art. 64 Verfahren
1
Für das Verfahren gilt
Art. 65 sinngemäss.
2
Das Nähere regelt der Regierungsrat.
""")
        self.assertEqual(list(arts), ["Art. 64"])

    def test_ueberschrift_ueber_zwei_zeilen(self):
        arts, _ = lesen("""
Art. 97 Bürgerrecht
1
Das Bürgerrecht wird verliehen.
Art. 98 Einbürgerungskommission, Bürgerversammlung und Bürger-
kommission
*
1
2
Die Einbürgerungskommission besteht aus Mitgliedern.
""")
        self.assertEqual(arts.get("Art. 98"), "Einbürgerungskommission, Bürgerversammlung und Bürgerkommission")

    def test_zweite_sternzeile_nach_der_ueberschrift(self):
        arts, _ = lesen("""
1 Leistungen
§ 1
* Begrenzung der Heim- und Spitaltaxen
*
1
Für Bewohnerinnen und Bewohner von Heimen gilt eine Begrenzung.
""")
        self.assertEqual(arts.get("§ 1"), "Begrenzung der Heim- und Spitaltaxen")
