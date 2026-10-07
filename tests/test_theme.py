"""The shared look (citygov/core/theme.py): every text colour reaches 4.5:1 on every surface it is
used on (theme.check), no colour, size or font literal is left in the page generators or their
files under citygov/present/assets/ (theme.problems, what `theme.py --check` runs in the build),
and both checks fire when a colour or a literal is wrong.
"""
import os
import tempfile
from unittest import mock

from tests import TestCase

from citygov.core import theme


class Contrast(TestCase):
    def test_every_pair_reaches_4_5(self):
        pairs = theme.check()
        self.assertGreaterEqual(len(pairs), 50)
        self.assertEqual([p for p in pairs if not p[3]], [])

    def test_the_formula(self):
        self.assertAlmostEqual(theme.contrast("#000000", "#FFFFFF"), 21.0, places=6)
        self.assertAlmostEqual(theme.contrast("#777", "#777777"), 1.0, places=6)

    def test_fires_on_a_pale_text_colour(self):
        with mock.patch.dict(theme.COLOR, {"ink-faint": "#BBBBBB"}):
            low = [(fg, bg) for fg, bg, _r, ok in theme.check() if not ok]
            self.assertIn(("ink-faint", "card"), low)
            self.assertTrue(any(p.startswith("contrast ") and "--ink-faint" in p for p in theme.problems()))


class Literals(TestCase):
    def test_no_finding_in_the_generators_and_their_files(self):
        self.assertEqual(theme.problems(), [])

    def test_reads_the_four_generators_and_the_assets(self):
        here = os.path.join(theme.ROOT, "citygov", "present")
        for g in theme.GENERATORS:
            self.assertTrue(os.path.isfile(os.path.join(here, g)), g)     # a missing one would be skipped silently
        self.assertTrue(os.path.isdir(os.path.join(here, "assets")))

    def test_fires_on_a_loose_literal(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "probe.css")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(".a{color:#ff0000}\n.b{font-size:11px}\n.c{font-family:Arial}\n"
                         ".d{color:#ff0000} /* theme:keep — on purpose */\n<a href=\"#main\">x</a>\n")
            kinds = [k for _no, k, _t in theme.loose(p)]
        self.assertEqual(sorted(kinds), ["colour", "font", "size"])

