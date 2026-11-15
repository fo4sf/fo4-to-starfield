"""scripts/dialogue/concord_talk_install.py: stage check and one ride-along install on a temp game folder."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts" / "dialogue"))
sys.path.insert(0, str(ROOT / "scripts" / "ui"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
sys.path.insert(0, str(ROOT / "src"))
from ba2_fixture import archive_from_tree  # noqa: E402
import concord_talk_install as cti  # noqa: E402
import exp_install  # noqa: E402
import make_concord_talk as mct  # noqa: E402

PLUGIN = "FO4SFConcordTalk.esm"
EXP_RECORD = b'{"exp_dir": "C:/stage/core", "files": {}, "complete": true}'
BEFORE = ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm"]


def write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


class ConcordTalkInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.game = os.path.join(root, "game")
        self.data = os.path.join(self.game, "Data")
        os.makedirs(self.data)
        write(os.path.join(self.data, exp_install.RECORD), EXP_RECORD)
        self.staged = os.path.join(root, "concord_talk")
        mct.stage(self.staged)
        self.local = os.path.join(root, "local")
        self.plugins = os.path.join(self.local, "Starfield", "Plugins.txt")
        write(self.plugins, ("\r\n".join(BEFORE) + "\r\n").encode())
        self.old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.local
        self.saved = exp_install.build_ba2

        def stub_build(a, root_dir, out):
            write(out, archive_from_tree(Path(root_dir)))
            return out
        exp_install.build_ba2 = stub_build

    def tearDown(self):
        exp_install.build_ba2 = self.saved
        if self.old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.old_local
        self.tmp.cleanup()

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                code = cti.main(list(argv) + ["--starfield", self.game]) or 0
            except SystemExit as e:
                code = 0 if e.code in (None, 0) else e.code
        return code, out.getvalue()

    def test_stage_problems_empty_when_staged(self):
        self.assertEqual(cti.stage_problems(self.staged), [])

    def test_stage_problems_if_twin_missing(self):
        os.remove(os.path.join(self.staged, "Data", "Interface", "DialogueMenu.swf"))
        problems = cti.stage_problems(self.staged)
        self.assertTrue(problems)
        self.assertTrue(any("DialogueMenu" in p or "expected" in p for p in problems))

    def test_names_match(self):
        self.assertEqual(mct.PLUGIN, PLUGIN)
        self.assertEqual(mct.TWIN, "Interface/DialogueMenu.swf")
        self.assertNotEqual(cti.RECORD, exp_install.RECORD)

    def test_install_rides_along_and_uninstall_restores(self):
        code, out = self.run_main("install", "--dir", self.staged)
        self.assertEqual(code, 0, out)
        self.assertEqual(exp_install.RECORD, "FO4SFExp.install.json")
        self.assertTrue(os.path.exists(os.path.join(self.data, cti.RECORD)))
        self.assertTrue(os.path.exists(os.path.join(self.data, PLUGIN)))
        self.assertTrue(os.path.exists(os.path.join(self.data, mct.ARCHIVE)))
        with open(self.plugins, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
        self.assertIn("*" + PLUGIN, lines)
        with open(os.path.join(self.data, exp_install.RECORD), "rb") as f:
            self.assertEqual(f.read(), EXP_RECORD)
        code, out = self.run_main("uninstall")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.exists(os.path.join(self.data, cti.RECORD)))
        self.assertFalse(os.path.exists(os.path.join(self.data, PLUGIN)))
        with open(self.plugins, encoding="utf-8-sig") as f:
            self.assertEqual(f.read().splitlines(), BEFORE)

    def test_refuses_existing_loose_dialogue_menu(self):
        write(os.path.join(self.data, "Interface", "DialogueMenu.swf"), b"not-ours")
        with open(self.plugins, "rb") as f:
            before = f.read()
        code, out = self.run_main("install", "--dir", self.staged)
        self.assertNotEqual(code, 0, out)
        self.assertIn("loose", out)
        self.assertFalse(os.path.exists(os.path.join(self.data, cti.RECORD)))
        with open(self.plugins, "rb") as f:
            self.assertEqual(f.read(), before)


if __name__ == "__main__":
    unittest.main()
