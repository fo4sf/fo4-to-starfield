"""coc.ps1's retries (v6e stairs retests 2026-10-21): a coc into BostonPublicLibrary02 from another cell landed 54 m from
the COC marker, at its load door's arrival, and the stairs queue stopped on its first test; the same coc typed again from
inside landed on the marker (stairs_watcher2). coc.ps1 types it again, then hops through another cell. coc_hop.py picks
the cell to hop through; the sandbox run (Windows, PowerShell) drives the copied coc.ps1 against tests/qstep_sandbox's
simulated console, so nothing in scripts/game but coc.ps1 and coc_hop.py runs and no key is sent."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "scripts", "game")
SANDBOX = os.path.join(ROOT, "tests", "qstep_sandbox")
sys.path.insert(0, GAME)
import coc_hop  # noqa: E402

POWERSHELL = shutil.which("powershell") if os.name == "nt" else None
MARKER = {"base_editor_id": "COCMarkerHeading", "pos": [2048.2, 4207.7, -126.7]}   # 29.26 60.11 in metres
DOOR_ARRIVAL = [-9.14, 97.37, 11.88]


def cell(name, marker=True, extra=(), at=None):
    refs = [dict(MARKER, pos=at or [0.0, 0.0, 0.0])] if marker else []
    return {"cell": name, "refs": refs + list(extra)}


class StagingCase(unittest.TestCase):
    def staging(self, docs):
        d = tempfile.mkdtemp(prefix="coc_hop_")
        self.addCleanup(shutil.rmtree, d, True)
        for name, doc in docs.items():
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                f.write(doc if isinstance(doc, str) else json.dumps(doc))
        return d


class HopCellTest(StagingCase):
    def test_skips_merged_helpers_the_target_and_cells_without_a_marker(self):
        # Codex on #450: merged.json aggregates refs and can hold a COC marker; FO4Port_merged is not a cell
        d = self.staging({"BostonPublicLibrary02.json": cell("BostonPublicLibrary02", at=MARKER["pos"]),
                          "AAA.json": cell("AAA", marker=False),
                          "BB_broken.json": "{not json",
                          "Abc.json": cell("BostonPublicLibrary02"),     # another export of the target itself
                          "editorids.json": cell("editorids"), "formids.json": {"refs": [MARKER]},
                          "build_x.json": cell("build_x"), "routes_y.json": cell("routes_y"),
                          "manifest.json": {"items": []},
                          "merged.json": cell("merged"), "a_merged_copy.json": cell("merged"),
                          "Vault111.json": cell("Vault111", at=[2048.2 + 700.0, 4207.7, 0.0]),   # 10 m away: too close
                          "Vault111Cryo.json": cell("Vault111Cryo"), "Vault114.json": cell("Vault114")})
        self.assertEqual(coc_hop.hop_cell(os.path.join(d, "BostonPublicLibrary02.json")), "Vault111Cryo")

    def test_a_marker_near_the_targets_is_never_the_hop(self):
        # Codex on #450: a return coc the game ignored would leave the player at the hop cell's marker, and the
        # position-only check would take that for the target's
        d = self.staging({"BostonPublicLibrary02.json": cell("BostonPublicLibrary02", at=MARKER["pos"]),
                          "Vault111Cryo.json": cell("Vault111Cryo", at=MARKER["pos"])})
        self.assertIsNone(coc_hop.hop_cell(os.path.join(d, "BostonPublicLibrary02.json")))

    def test_none_when_the_target_is_the_only_cell(self):
        d = self.staging({"BostonPublicLibrary02.json": cell("BostonPublicLibrary02", at=MARKER["pos"]),
                          "merged.json": cell("merged")})
        self.assertIsNone(coc_hop.hop_cell(os.path.join(d, "BostonPublicLibrary02.json")))
        self.assertEqual(coc_hop.main([os.path.join(d, "BostonPublicLibrary02.json")]), 1)

    def test_coc_ps1_tries_again_from_inside_then_hops_and_checks_again(self):
        src = open(os.path.join(GAME, "coc.ps1"), encoding="utf-8").read()
        self.assertIn("[string]$Via = ''", src)
        self.assertIn("& $py -I (Join-Path $PSScriptRoot 'coc_hop.py') $CellJson", src)   # isolated: it reads game data
        tail = src[src.index("Enter-Cell $Cell\nTest-Arrival"):]
        check = "Test-Arrival\nif ($script:arrived) { exit 0 }\n"
        self.assertTrue(tail.startswith("Enter-Cell $Cell\n" + check + '"again: coc FO4Port_$Cell from inside"\n'
                                        "Enter-Cell $Cell\n" + check))
        hop = tail[tail.index("Enter-Cell $Via"):]
        self.assertEqual(hop, "Enter-Cell $Via\nEnter-Cell $Cell\nEnter-Cell $Cell\n" + check + "exit 1\n")
        self.assertNotIn("if (Test-Arrival)", src)        # its printed lines would make the if always true


@unittest.skipUnless(POWERSHELL, "runs the copied coc.ps1 against the simulated console on Windows only")
class CocSandboxTest(StagingCase):
    def run_coc(self, world, docs):
        stg = self.staging(docs)
        d = tempfile.mkdtemp(prefix="coc_sandbox_")
        self.addCleanup(shutil.rmtree, d, True)
        game = os.path.join(d, "game")
        shutil.copytree(SANDBOX, game)
        for f in ("coc.ps1", "coc_hop.py"):
            shutil.copy(os.path.join(GAME, f), game)
        state = os.path.join(d, "state.json")
        base = {"player": [0, 0, 0], "arrival": [29.26, 60.11, -1.81], "actors": {}, "log": [], "sel": None,
                "crosshair": None}
        with open(state, "w") as f:
            json.dump(dict(base, **world), f)
        env = dict(os.environ, FAKE_STATE=state, FO4SF_PYTHON=sys.executable, FO4SF_NO_FOCUS_STEAL="1")
        r = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(game, "coc.ps1"),
                            "-Cell", "BostonPublicLibrary02", "-CellJson", os.path.join(stg, "BostonPublicLibrary02.json"),
                            "-Wait", "0"], capture_output=True, text=True, env=env, timeout=480)
        with open(state) as f:
            st = json.load(f)
        return r, [c for c in st.get("typed", []) if c.startswith("coc ")]

    def test_a_save_inside_the_target_hops_and_arrives(self):
        r, cocs = self.run_coc({"cell": "FO4Port_BostonPublicLibrary02", "player": DOOR_ARRIVAL, "coc_same_cell_stays": True},
                               {"BostonPublicLibrary02.json": cell("BostonPublicLibrary02", at=MARKER["pos"]), "merged.json": cell("merged"),
                                "Vault111Cryo.json": cell("Vault111Cryo")})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(cocs, ["coc FO4Port_BostonPublicLibrary02"] * 2 + ["coc FO4Port_Vault111Cryo"] +
                         ["coc FO4Port_BostonPublicLibrary02"] * 2)
        self.assertIn("hop: coc FO4Port_Vault111Cryo", r.stdout)

    def test_a_coc_from_another_cell_off_the_marker_is_typed_again_from_inside(self):
        # stairs_watcher2 2026-10-21: from Vault111Cryo the coc landed at the door spot, the next one on the marker
        r, cocs = self.run_coc({"cell": "FO4Port_Vault111Cryo", "coc_from_outside": DOOR_ARRIVAL},
                               {"BostonPublicLibrary02.json": cell("BostonPublicLibrary02", at=MARKER["pos"]),
                                "Vault111Cryo.json": cell("Vault111Cryo")})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(cocs, ["coc FO4Port_BostonPublicLibrary02"] * 2)
        self.assertIn("again: coc FO4Port_BostonPublicLibrary02 from inside", r.stdout)
        self.assertNotIn("hop:", r.stdout)

    def test_a_first_arrival_needs_no_hop(self):
        r, cocs = self.run_coc({"cell": "Elsewhere", "coc_same_cell_stays": True},
                               {"BostonPublicLibrary02.json": cell("BostonPublicLibrary02", at=MARKER["pos"]),
                                "Vault111Cryo.json": cell("Vault111Cryo")})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(cocs, ["coc FO4Port_BostonPublicLibrary02"])

    def test_no_other_cell_fails_without_a_hop(self):
        r, cocs = self.run_coc({"cell": "FO4Port_BostonPublicLibrary02", "player": DOOR_ARRIVAL, "coc_same_cell_stays": True},
                               {"BostonPublicLibrary02.json": cell("BostonPublicLibrary02", at=MARKER["pos"]), "merged.json": cell("merged")})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(cocs, ["coc FO4Port_BostonPublicLibrary02"] * 2)


if __name__ == "__main__":
    unittest.main()
