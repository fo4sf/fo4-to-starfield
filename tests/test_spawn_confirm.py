"""The handle of a placed item or actor (qstep.ps1 Self-Other, the movable spawn's second PickLastRef): GetSelf naming
00000000 is no other ref, and PickLastRef is read once more when it named no FFxxxxxx id (the movable queue of
2026-10-18 on build 1d4591b6: every test but the first INCONCLUSIVE SPAWN). Synthetic text; no game. The step itself
runs in tests/test_qstep_sandbox.py (opt-in, Windows)."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "scripts", "game")
sys.path.insert(0, GAME)
import testqueue as tq  # noqa: E402

QSTEP = os.path.join(GAME, "qstep.ps1")
PWSH = shutil.which("pwsh") or shutil.which("powershell")


def src():
    with open(QSTEP, encoding="utf-8") as f:
        return f.read()


class ParseTests(unittest.TestCase):
    def test_getself_zero_is_read_as_the_id_00000000(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "ocr.txt")
        with open(p, "w") as f:
            f.write("ClearConsole\nprid FF000801\nGetSelf\nGetSelf > > (00000000)\n")
        out = subprocess.run([sys.executable, os.path.join(GAME, "parse_npc.py"), p, "--expect=self",
                              "--typed=FF000801"], capture_output=True, text=True, check=True).stdout
        self.assertIn('"self": "00000000"', out)


class SourceTests(unittest.TestCase):
    def test_every_getself_check_uses_self_other(self):
        s = src()
        self.assertEqual(s.count("(Self-Other $pk['self'] $pk['ref'])"), 2)        # movable_control, npc_nav
        self.assertIn("$selfOk = -not (Self-Other $pk2['self'] $pk2['ref'])", s)    # npc_nav's removal
        self.assertNotIn("$pk['self'] -ne $pk['ref']", s)

    def test_the_movable_spawn_reads_plr_again(self):
        s = src()
        k = s.index("'spawn_plr'")
        self.assertLess(k, s.index("'spawn_plr2'"), "the second plr follows the first")
        self.assertIn("$pk['plr2_ocr'] = $r1.ocr", s)
        self.assertRegex(s[k:s.index("'spawn_plr2'")], r"Send 'key:grave\|wait:2000'")

    def test_the_timeout_counts_the_second_plr(self):
        with open(tq.__file__, encoding="utf-8") as f:
            body = f.read().split("def movable_timeout", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("+ NPC_SESSION_S + 2                                # plr again", body)


class NoBaseTests(unittest.TestCase):
    # the movable_1019 run's place_ocr of 0001_movable_control_C_trashcan (2026-10-18, both attempts), verbatim
    PLACE = ("player.getpos ... Clear Console player. placeatme 0200CEDF 1 Item '0200CEDF' not found for parameter "
             "Object ID. Compiled script not saved!")
    T = tq.movable_test(0, {"label": "C_trashcan", "travel": "coc QASmoke", "base": "0200CEDF", "mass_kg": 1.0,
                            "spot": [-10.2, 4.0, 0.0], "heading": 0})

    def obs(self, place):
        return {"player_spot": "-10.2 4.0 0.0", "spawn": {"confirmed": False, "why": "PickLastRef gave no FFxxxxxx id",
                                                          "place_ocr": place}}

    def test_an_unknown_base_is_nobase_and_final(self):
        v, cls, detail = tq.judge_movable_control(self.T, self.obs(self.PLACE), True)
        self.assertEqual((v, cls), ("INCONCLUSIVE", "NOBASE"))
        self.assertIn("plugin index 02", detail)
        self.assertIn("NOBASE", tq.FINAL_INCONCLUSIVE)

    def test_only_this_sessions_placeatme_counts(self):
        older = "Item '0200CE44' not found for parameter Object ID. ClearConsole player.placeatme 002A0D5B 1"
        self.assertEqual(tq.judge_movable_control(self.T, self.obs(older), True)[1], "SPAWN")
        self.assertEqual(tq.judge_movable_control(self.T, self.obs(""), True)[1], "SPAWN")


@unittest.skipUnless(PWSH, "PowerShell not installed")
class SelfOtherTests(unittest.TestCase):
    def test_zero_and_nothing_are_no_other_ref(self):
        fn = re.search(r"(?s)function Self-Other.*?\n}\n", src()).group(0)
        script = fn + ("'{0} {1} {2} {3} {4}' -f (Self-Other '00000000' 'FF000800'), (Self-Other '0024A824' 'FF000800'), "
                       "(Self-Other 'FF000800' 'FF000800'), (Self-Other '' 'FF000800'), (Self-Other $null 'FF000800')")
        out = subprocess.run([PWSH, "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=120)
        self.assertEqual(out.stdout.split(), ["False", "True", "False", "False", "False"], out.stderr)


if __name__ == "__main__":
    unittest.main()
