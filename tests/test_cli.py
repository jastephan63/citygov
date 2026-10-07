"""The one entry point, python3 -m citygov (citygov/cli.py): every build step names a command
under scripts/, `list` names every command, `load` and `validate` run exactly the old command
(same output and exit code), and a wrong call stops before anything runs.
"""
import os
import subprocess
import sys
from unittest import mock

from tests import ROOT, TestCase, still

from citygov import cli


def citygov(*args):
    return subprocess.run([sys.executable, "-m", "citygov", *args], cwd=ROOT, capture_output=True, timeout=120)


def script(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, timeout=120)


class Build(TestCase):
    def test_every_step_is_a_command(self):
        commands = cli.commands()
        for name, args, only_with, passes in cli.BUILD:
            with self.subTest(step=name):
                self.assertIn(name, commands)
                self.assertTrue(os.path.isfile(os.path.join(ROOT, "scripts", name + ".py")))
                self.assertIn(only_with, (None,) + cli.WORDS)
                self.assertIn(passes, (None,) + cli.WORDS)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, *cli.PAGE_CHECK)))

    def test_steps_in_order_and_the_words_of_build_sh(self):
        """What the build starts, step by step (nothing is run here), for the words ./build.sh
        passes after «--»: only --tresor and --pdf count, wherever they stand; every other word,
        --help included, is ignored, as build.sh always did."""
        def started(words):
            seen = []
            with mock.patch.object(cli, "_run", lambda argv: seen.append(argv) or 0), \
                    mock.patch.object(cli.shutil, "which", lambda name: "/bin/" + name), \
                    mock.patch.object(cli.os, "chdir", lambda path: None), still():
                code = cli.build(words)
            return code, seen

        py = cli._python()
        steps = [[py, "scripts/init_register.py"], [py, "scripts/kennungen.py"], [py, "scripts/rollen.py", "ableiten"],
                 [py, "scripts/export_json.py"], [py, "scripts/theme.py", "--check"], [py, "scripts/build_flows.py"],
                 [py, "scripts/export_llm.py"], [py, "scripts/export_ech_schema.py"],
                 [py, "scripts/build_dashboard.py"], [py, "scripts/export_vertrag.py"],
                 [py, "scripts/kennungen.py", "--pruefen"], [py, "scripts/export_dossiers.py"],
                 [py, "scripts/build_index.py"], [py, "scripts/validate_db.py"]]
        tail = [["bash", "-o", "pipefail", "-c", "ls -lh dashboard.html flows.html data_export.json citygov_llm.json"
                 " | awk '{print \"  \" $5 \"\\t\" $9}'"], [py, "-m", "unittest"], ["node", "scripts/check_pages.mjs"]]
        self.assertEqual(started(["--"]), (0, steps + tail))
        self.assertEqual(started(["--", "--help", "egal"]), (0, steps + tail))
        mit = steps[:3] + [[py, "scripts/build_datentresor.py"]] + steps[3:11] + \
            [[py, "scripts/export_dossiers.py", "--pdf"]] + steps[12:]
        self.assertEqual(started(["--", "x --pdf", "--tresor"]), (0, mit + tail))
        self.assertEqual(started(["--help"]), (0, []))
        self.assertEqual(started(["--tresr"]), (2, []))
        self.assertEqual(started(["--pdf", "--tresor"]), (0, mit + tail))

    def test_build_sh_runs_the_entry_point(self):
        with open(os.path.join(ROOT, "build.sh"), encoding="utf-8") as fh:
            lines = [x for x in fh.read().splitlines() if x.strip() and not x.lstrip().startswith("#")]
        self.assertEqual(lines[-1], 'exec "$PY" -m citygov build -- "$@"')

    def test_a_wrong_call_runs_nothing(self):
        r = citygov("build", "--tresr")
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"unknown argument --tresr", r.stderr)
        r = citygov("build", "--help")
        self.assertEqual((r.returncode, r.stderr), (0, b""))
        self.assertIn(b"--tresor", r.stdout)


class Commands(TestCase):
    def test_list_names_every_command(self):
        r = citygov("list")
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        out = r.stdout.decode()
        names = sorted(f[:-3] for f in os.listdir(os.path.join(ROOT, "scripts")) if f.endswith(".py"))
        self.assertEqual(sorted(cli.commands()), names)
        for name in names:
            self.assertIn(f"\n  {name} ", out)

    def test_load_is_the_old_command(self):
        for args in (["kennungen", "--aufloesen", "sh:formular:gibt-es-nicht"], ["wirkung", "--help"],
                     ["theme", "--check"]):
            with self.subTest(args=args):
                neu = citygov("load", *args)
                alt = script(f"scripts/{args[0]}.py", *args[1:])
                self.assertEqual((neu.returncode, neu.stdout, neu.stderr), (alt.returncode, alt.stdout, alt.stderr))

    def test_validate_is_the_old_command(self):
        neu, alt = citygov("validate"), script("scripts/validate_db.py")
        self.assertEqual(alt.returncode, 0, alt.stderr[-400:])
        self.assertEqual((neu.returncode, neu.stdout, neu.stderr), (alt.returncode, alt.stdout, alt.stderr))

    def test_unknown_names(self):
        r = citygov("load", "kennungn")
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"kennungen", r.stderr)
        self.assertEqual(citygov("gibt-es-nicht").returncode, 2)
        self.assertEqual(citygov().returncode, 2)
        self.assertEqual(citygov("--help").returncode, 0)

