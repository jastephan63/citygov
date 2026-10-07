"""Every gate passes on the real data and fires on a tampered copy.

The gates: validate_db (each of its families, on an in-memory copy of the database), the sum
gate of export_json (_summen_pruefen, on the export built in memory), and the gates of the
data-model layers (rollen, register_map, kennungen, gesetz_stand, gesetz_titel, konzepte,
wirkung). Where a module has a self-test that tampers with copies itself (konzepte, wirkung,
gestaltung_export), the test calls it, as `--selbsttest` does.
"""
import copy
import unittest
from unittest import mock

from tests import TestCase, export_daten, kopie, lesen, still

from citygov.checks.validate_db import validate

# (gate, SQL that breaks it on an in-memory copy, a text its error carries)
VALIDATE_DB = (
    ("1 foreign keys",
     "UPDATE document SET form_id = 999999999 WHERE id = (SELECT min(id) FROM document WHERE form_id IS NOT NULL)",
     "orphan FK: table=document"),
    ("2 duplicate join rows (the primary key that prevents them is removed first)",
     "ALTER TABLE service_requirement RENAME TO sr_alt;"
     "CREATE TABLE service_requirement (service_id INTEGER, requirement_id INTEGER, applicability_condition TEXT);"
     "INSERT INTO service_requirement SELECT * FROM sr_alt;"
     "INSERT INTO service_requirement SELECT * FROM sr_alt LIMIT 1;"
     "DROP TABLE sr_alt",
     "duplicate rows in service_requirement"),
    ("3 field_mapping coherence (past its CHECK constraint)",
     "PRAGMA ignore_check_constraints = ON;"
     "UPDATE field_mapping SET classification = 'form_mechanic' "
     "WHERE id = (SELECT min(id) FROM field_mapping WHERE requirement_id IS NOT NULL)",
     "inconsistent with requirement_id"),
    ("4 document <-> form",
     "UPDATE document SET form_id = NULL WHERE id = (SELECT min(id) FROM document WHERE doc_type = 'formular')",
     "is 'formular' but has no form_id"),
    ("5 convention 7 (eSH never shadows eCH)",
     "UPDATE data_field SET esh_code = 'X' WHERE id = (SELECT min(id) FROM data_field WHERE ech_status = 'assigned')",
     "convention 7"),
    ("6 judgment layers (a vocabulary)",
     "UPDATE data_field SET basis_typ = 'erfunden' WHERE id = (SELECT min(id) FROM data_field)",
     "basis_typ outside"),
    ("7 source files",
     "UPDATE form SET source_file = 'formulare/gibt-es-nicht.pdf' "
     "WHERE id = (SELECT min(id) FROM form WHERE source_file LIKE '%.pdf')",
     "not an existing file under formulare/"),
    ("8 Gestaltung",
     "UPDATE form_gestaltung SET file_hash = 'veraltet' WHERE form_id = (SELECT min(form_id) FROM form_gestaltung)",
     "are stale"),
    ("9 Kennungen",
     "DROP TRIGGER tg_kennung_nie_loeschen",
     "Trigger fehlen"),
    ("10 Parteien und Rollen",
     "UPDATE partei_rolle SET label = label || ' (verändert)' WHERE code = (SELECT min(code) FROM partei_rolle)",
     "partei_rolle weicht"),
    ("11 Gesetzesstand",
     "UPDATE gesetz_stand SET erhoben_am = 'gestern' WHERE law_id = (SELECT min(law_id) FROM gesetz_stand)",
     "is no ISO day"),
    ("12 Register",
     "UPDATE register_beleg SET zitat = zitat || ' erfunden' WHERE rowid = (SELECT min(rowid) FROM register_beleg)",
     "Zitat steht nicht in der Quelle"),
    ("14 Gesetzestitel (the edition line)",
     "UPDATE law SET title = title || ' Vom 1. Januar 2000' WHERE id = (SELECT min(id) FROM law)",
     "carries the edition line"),
)


def _fehler(gate, sql=None):
    """The errors gate(conn) returns on an in-memory copy changed by sql."""
    mem = kopie()
    try:
        if sql:
            mem.executescript(sql)
        with still():
            return gate(mem)
    finally:
        mem.close()


class ValidateDb(TestCase):
    def test_real_data_passes(self):
        conn = lesen()
        try:
            with still():
                self.assertEqual(validate(conn), [])
        finally:
            conn.close()

    def test_every_gate_fires_on_a_tampered_copy(self):
        for name, sql, text in VALIDATE_DB:
            with self.subTest(gate=name):
                fehler = _fehler(validate, sql)
                self.assertTrue(any(text in f for f in fehler), f"«{text}» not among {fehler[:5]}")

    def test_concept_file_gate_fires(self):
        """13 Konzepte: validate runs konzepte.datei_pruefen on the curated file."""
        from citygov.domain import konzepte
        k = konzepte.lade()
        k["konzepte"][0]["grund"] = ""
        with mock.patch.object(konzepte, "lade", return_value=k):
            fehler = _fehler(validate)
        self.assertTrue(any("grund missing" in f for f in fehler), fehler[:5])


class ExportSums(TestCase):
    """export_json._summen_pruefen: every published total is the sum of its parts."""

    def test_real_export_adds_up(self):
        from citygov.export import export_json
        _conn, data = export_daten()
        export_json._summen_pruefen(data)

    def test_fires_on_a_tampered_export(self):
        from citygov.export import export_json
        _conn, data = export_daten()
        k = data["kopfzahlen"]
        name = next(n for n, v in k.items() if isinstance(v, dict) and "teile" in v)
        faelle = (("a part of a headline figure", k[name]["teile"], next(iter(k[name]["teile"])), f"kopfzahlen.{name}"),
                  ("the open points of the canton", k["offene_punkte"], "act", "kopfzahlen.offene_punkte"),
                  ("one Dienststelle", data["dienststellen_uebersicht"][0]["offen"], "act", "dienststellen_uebersicht"))
        for was, teil, key, text in faelle:
            with self.subTest(tampered=was):
                teil[key] += 1          # the export is shared by the tests of this run: put back below
                try:
                    with self.assertRaises(RuntimeError) as fall:
                        export_json._summen_pruefen(data)
                    self.assertIn(text, str(fall.exception))
                finally:
                    teil[key] -= 1


class Rollen(TestCase):
    def test_real_data_passes(self):
        from citygov.domain import rollen
        self.assertEqual(_fehler(rollen.pruefen), [])

    def test_fires_on_a_tampered_copy(self):
        from citygov.domain import rollen
        for sql, text in (
                ("UPDATE partei_rolle SET entitaet = 'sache' WHERE code = (SELECT min(code) FROM partei_rolle)",
                 "partei_rolle weicht"),
                ("UPDATE datenpunkt_partei SET grund = ' ' WHERE rowid = (SELECT min(rowid) FROM datenpunkt_partei)",
                 "ohne Beleg oder Grund")):
            with self.subTest(sql=sql):
                fehler = _fehler(rollen.pruefen, sql)
                self.assertTrue(any(text in f for f in fehler), fehler[:5])


class Register(TestCase):
    def test_real_data_passes(self):
        from citygov.domain import register_map
        self.assertEqual(_fehler(register_map.pruefen), [])
        self.assertEqual(_fehler(register_map.zeit_pruefen), [])

    def test_fires_on_a_tampered_copy(self):
        from citygov.domain import register_map
        for sql, text in (
                ("UPDATE register_beleg SET zitat = zitat || ' erfunden' "
                 "WHERE rowid = (SELECT min(rowid) FROM register_beleg)", "Zitat steht nicht in der Quelle"),
                ("DELETE FROM register_beleg WHERE aspekt = 'inhaber' "
                 "AND register = (SELECT min(register) FROM register_beleg WHERE aspekt = 'inhaber')", "ohne Beleg für")):
            with self.subTest(sql=sql):
                fehler = _fehler(register_map.pruefen, sql)
                self.assertTrue(any(text in f for f in fehler), fehler[:5])


class Kennungen(TestCase):
    def test_real_data_passes(self):
        from citygov.core import kennungen
        self.assertEqual(_fehler(kennungen.pruefen), [])
        self.assertEqual(_fehler(kennungen.pruefen_aktuell), [])

    def test_fires_on_a_tampered_copy(self):
        from citygov.core import kennungen
        ohne_schutz = "".join(f"DROP TRIGGER {t};" for t in kennungen.TRIGGER)
        weg = ("DELETE FROM kennung WHERE kennung = (SELECT min(kennung) FROM kennung "
               "WHERE art = 'formular' AND status = 'aktiv');")
        for gate, sql, text in (
                (kennungen.pruefen, "DROP TRIGGER tg_kennung_nie_loeschen", "Trigger fehlen"),
                (kennungen.pruefen, ohne_schutz + weg, "veröffentlichte Kennungen fehlen"),
                (kennungen.pruefen_aktuell, ohne_schutz + weg, "ohne aktive Kennung")):
            with self.subTest(gate=gate.__name__, sql=sql):
                fehler = _fehler(gate, sql)
                self.assertTrue(any(text in f for f in fehler), fehler[:5])


class Gesetzesstand(TestCase):
    def test_real_data_passes(self):
        from citygov.domain import gesetz_stand, gesetz_titel
        self.assertEqual(_fehler(gesetz_stand.pruefen), [])
        self.assertEqual(_fehler(gesetz_titel.pruefen), [])

    def test_fires_on_a_tampered_copy(self):
        from citygov.domain import gesetz_stand, gesetz_titel
        conn = lesen()
        try:
            law = gesetz_titel.zeilen(conn)[0][0][0]           # the first law of the title corrections
        finally:
            conn.close()
        for gate, sql, text in (
                (gesetz_stand.pruefen, "UPDATE gesetz_stand SET grund = 'x' WHERE law_id = "
                                       "(SELECT min(law_id) FROM gesetz_stand WHERE status = 'belegt')",
                 "status belegt carries a grund"),
                (gesetz_titel.pruefen, f"UPDATE law SET short_title = 'anders' WHERE id = {law}",
                 "trägt weder den bisherigen noch den korrigierten Namen")):
            with self.subTest(gate=gate.__module__, sql=sql):
                fehler = _fehler(gate, sql)
                self.assertTrue(any(text in f for f in fehler), fehler[:5])


class SelbsttestsDerSchichten(TestCase):
    """The self-tests of the layers: each checks that the real data passes and that every one of
    its rules fires on a tampered copy (what `scripts/<name>.py --selbsttest` runs)."""

    def test_konzepte(self):
        from citygov.domain import konzepte
        conn, data = export_daten()
        self.assertEqual(konzepte.datei_pruefen(konzepte.lade()), [])
        with still() as out:
            ok = konzepte.selbsttest(conn, copy.deepcopy(data["forms"]))
        self.assertTrue(ok, out.getvalue()[-600:])

    def test_wirkung(self):
        from citygov.domain import wirkung
        conn = lesen()
        try:
            with still() as out:
                ok = wirkung.selbsttest(conn)
        finally:
            conn.close()
        self.assertTrue(ok, out.getvalue()[-600:])

    def test_gestaltung_export(self):
        from citygov.domain import gestaltung_export
        conn, data = export_daten()
        with still() as out:
            try:
                gestaltung_export._selbsttest(conn, copy.deepcopy(data["forms"]), copy.deepcopy(data["services"]),
                                              copy.deepcopy(data["dienststellen_uebersicht"]))
            except SystemExit as ende:                       # the self-test ends with sys.exit on a silent rule
                self.fail(f"{ende} — {out.getvalue()[-600:]}")
        self.assertIn("die echten Daten gehen auf", out.getvalue())


if __name__ == "__main__":
    unittest.main()
