"""The self-tests of the measuring modules of the Gestaltung (what `python3 scripts/<name>.py`
runs without arguments, and what scan_gestaltung.py runs before it measures): assertions on
built-in example lines and on small files built in memory. gestaltung_pdf checks its PDF part
only with pypdf; without it the rest still runs, as on the command line.
"""

from tests import TestCase, still


class Gestaltung(TestCase):
    def test_gestaltung_text(self):
        from citygov.domain import gestaltung_text
        with still():
            self.assertGreater(gestaltung_text._selbsttest(), 0)

    def test_gestaltung_office(self):
        from citygov.domain import gestaltung_office
        with still():
            self.assertGreater(gestaltung_office._selbsttest(), 0)

    def test_gestaltung_pdf(self):
        from citygov.domain import gestaltung_pdf
        with still() as out:
            gestaltung_pdf._selbsttest()
        self.assertIn("checks passed", out.getvalue())

