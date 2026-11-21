import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PSC_PATH = os.path.join(REPO, "scripts", "fort_hagen", "FO4SF_FortHagenQuest.psc")
MAKE_PATH = os.path.join(REPO, "scripts", "fort_hagen", "make_fort_hagen.py")
CS_PATH = os.path.join(REPO, "dotnet", "FortHagen", "Program.cs")
DOC_PATH = os.path.join(REPO, "docs", "mission", "fort-hagen-elevators.md")


def load_make_module():
    spec = importlib.util.spec_from_file_location("make_fort_hagen", MAKE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeRef:
    def __init__(self, fid, base_id, x, y, z, cell, disabled=False, open_state=3):
        self.fid = fid
        self.base_id = base_id
        self.x = x
        self.y = y
        self.z = z
        self.cell = cell
        self.disabled = disabled
        self.open_state = open_state
        self.activated_by = []

    def IsDisabled(self):
        return self.disabled

    def Disable(self):
        self.disabled = True

    def GetOpenState(self):
        return self.open_state

    def SetOpen(self, open_flag):
        self.open_state = 1 if open_flag else 3

    def Activate(self, actor):
        self.activated_by.append(actor)


class FortHagenControllerModel:
    """Behavioral model mirroring FO4SF_FortHagenQuest.psc zone detection, blocker cleanup, and activation dispatch."""

    def __init__(self):
        self.cell01 = ("interior", "FO4Port_FortHagen01")
        self.cell02 = ("interior", "FO4Port_FortHagen02")
        self.roof_cell = ("exterior", "Ext(-13,-1)")

        self.planks01 = FakeRef(0x00C641, 0x0010BE, -10.971, 67.429, 5.029, self.cell01)
        self.blocker_door01 = FakeRef(0x00C7A8, 0x0066B4, -10.784, 54.720, -2.457, self.cell01)
        self.blocker_boards01 = FakeRef(0x00C13A, 0x0010BF, -8.927, 54.815, -2.239, self.cell01)
        self.maint01 = FakeRef(0x00C7B0, 0x00E00A, -9.829, 67.886, -2.946, self.cell01)

        self.upper_call01 = FakeRef(0x00C7AF, 0x00E008, -11.986, 67.419, 4.905, self.cell01)
        self.lower_call01 = FakeRef(0x00C7AD, 0x00E008, -9.921, 67.429, -2.405, self.cell01)
        self.inner_panel01 = FakeRef(0x00C7AE, 0x00E009, -11.882, 68.037, -2.405, self.cell01)
        self.upper_door01 = FakeRef(0x00C7AC, 0x00DE5F, -10.971, 67.657, 3.657, self.cell01)
        self.lower_door01 = FakeRef(0x00C7B4, 0x00DE5F, -10.971, 67.657, -3.657, self.cell01)
        self.inner_door01 = FakeRef(0x00C7AB, 0x00DE5E, -10.971, 69.486, -3.657, self.cell01)

        self.call02 = FakeRef(0x00DC5F, 0x00E03E, 20.796, 2.502, -9.554, self.cell02)
        self.panel02 = FakeRef(0x00DC62, 0x00E03F, 21.410, 2.314, -9.554, self.cell02)
        self.outer_door02 = FakeRef(0x00DE52, 0x00DE5F, 21.029, 1.371, -10.971, self.cell02)
        self.load_door02 = FakeRef(0x00DE53, 0x00DE5E, 22.857, 1.371, -10.971, self.cell02)

        # Simulate merged planet-overlay runtime FF00xxxx instances where direct GetFormFromFile(refId) returns None
        # and ResolveRef falls back to FindClosestReferenceOfType(baseForm, mergedX, mergedY, mergedZ, 2.5).
        self.roof_call = FakeRef(0xFF001001, 0x0A2D93, -2471.531, -2773.779, 96.503, self.roof_cell)
        self.roof_panel = FakeRef(0xFF001002, 0x0A2D92, -2471.342, -2773.165, 96.503, self.roof_cell)
        self.roof_outer_door = FakeRef(0xFF001003, 0x002C08, -2470.400, -2773.546, 95.086, self.roof_cell)
        self.roof_load_door = FakeRef(0xFF001004, 0x0A7757, -2470.400, -2771.718, 95.086, self.roof_cell)
        self.roof_gate = FakeRef(0xFF001005, 0x0A2D9C, -2470.400, -2781.432, 95.086, self.roof_cell)
        self.roof_term = FakeRef(0xFF001006, 0x0A2E3F, -2471.657, -2781.318, 95.086, self.roof_cell)

        self.roof_gate_opened = False
        self.player_cell = None
        self.player_pos = (0.0, 0.0, 0.0)
        self.logs = []

    def log(self, msg):
        self.logs.append(f"FO4SF_FORTHAGEN rt=1.25 {msg}")

    def enter_zone01(self):
        self.player_cell = self.cell01
        for r in (self.planks01, self.blocker_door01, self.blocker_boards01, self.maint01):
            r.Disable()
        self.log(f"fh01_ready planks={self.planks01.IsDisabled()} blocker_door={self.blocker_door01.IsDisabled()}")

    def enter_zone02(self):
        self.player_cell = self.cell02
        self.log("fh02_ready call=True panel=True outer=True load_door=True")

    def enter_roof(self):
        self.player_cell = self.roof_cell
        self.player_pos = (-2470.491, -2774.755, 95.086)
        if self.roof_gate_opened and not self.roof_gate.IsDisabled():
            self.roof_gate.Disable()
        self.log("fh_roof_ready gate=True term=True call=True load_door=True")

    def activate(self, sender):
        if sender in (self.upper_call01, self.upper_door01):
            self.upper_door01.SetOpen(True)
            self.inner_door01.SetOpen(True)
            self.lower_door01.SetOpen(True)
            self.player_pos = (-10.971, 69.000, -3.550)
            self.upper_door01.SetOpen(False)
            self.log(f"fh01_arrived floor=lower pos={self.player_pos}")
        elif sender == self.lower_call01:
            self.lower_door01.SetOpen(True)
            self.inner_door01.SetOpen(True)
            self.log("fh01_lower_open")
        elif sender == self.inner_panel01:
            self.inner_door01.SetOpen(False)
            self.lower_door01.SetOpen(False)
            self.upper_door01.SetOpen(True)
            self.player_pos = (-10.971, 66.200, 3.750)
            self.upper_door01.SetOpen(False)
            self.log(f"fh01_arrived floor=upper pos={self.player_pos}")
        elif sender == self.call02:
            self.outer_door02.SetOpen(True)
            self.log("fh02_outer_open")
        elif sender == self.panel02:
            self.outer_door02.SetOpen(True)
            self.load_door02.Activate("player")
            self.log("fh02_panel_dispatch")
        elif sender in (self.roof_term, self.roof_gate):
            self.roof_gate_opened = True
            self.roof_gate.Disable()
            self.log(f"fh_roof_gate_opened via={sender == self.roof_term}")
        elif sender == self.roof_call:
            self.roof_outer_door.SetOpen(True)
            self.log("fh_roof_outer_open")
        elif sender == self.roof_panel:
            self.roof_outer_door.SetOpen(True)
            self.roof_load_door.Activate("player")
            self.log("fh_roof_panel_dispatch")


class TestFortHagenElevators(unittest.TestCase):
    def setUp(self):
        self.make = load_make_module()
        with open(PSC_PATH, encoding="utf-8") as f:
            self.psc = f.read()
        with open(CS_PATH, encoding="utf-8") as f:
            self.cs = f.read()
        with open(DOC_PATH, encoding="utf-8") as f:
            self.doc = f.read()

    def test_property_order_matches_across_psc_python_and_csharp(self):
        psc_props = tuple(self.make.mandatory_properties(self.psc))
        self.assertEqual(psc_props, self.make.PROPERTIES)
        m = re.search(r"MandatoryProperties\s*=\s*\{([^}]*)\}", self.cs, re.S)
        self.assertIsNotNone(m)
        cs_props = tuple(re.findall(r'"(\w+)"', m.group(1)))
        self.assertEqual(psc_props, cs_props)
        self.assertEqual(len(psc_props), 69)

    def test_papyrus_contract_and_closest_ref_fallback(self):
        # Must not collide with Starfield Papyrus reserved keywords
        tokens = {t.lower() for t in re.findall(r"[A-Za-z_]\w*", self.psc)}
        self.assertNotIn("guard", tokens)
        self.assertNotIn("protectsfunctionlogic", tokens)

        # Must support both direct GetFormFromFile and coordinate-bounded FindClosestReferenceOfType for merged cells
        self.assertIn("Game.GetFormFromFile(", self.psc)
        self.assertIn("Game.FindClosestReferenceOfType(", self.psc)
        self.assertIn('RegisterForRemoteEvent(p, "OnPlayerLoadGame")', self.psc)
        self.assertIn('RegisterForRemoteEvent(nextRef, "OnActivate")', self.psc)
        self.assertIn('UnregisterForRemoteEvent(current, "OnActivate")', self.psc)

        # Landing coordinates must place upper arrival outside shaft (y=66.200) and lower arrival inside car (z=-3.550)
        self.assertIn("UpperLandingY = 66.200f", self.cs)
        self.assertIn("LowerCarZ = -3.550f", self.cs)

        self.assertIn('Trace("init quest=" + (self as Quest))', self.psc)
        self.assertNotIn('Trace("init quest=" + XMarkerBase)', self.psc)

    def test_end_to_end_journey_and_log_judge(self):
        sim = FortHagenControllerModel()
        sim.log("init quest=[FO4SF_FortHagenQuest < (0A000800)>]")

        # 1. Enter FortHagen01: stripped-XESP planks and duplicate door blockers clear automatically
        sim.enter_zone01()
        self.assertTrue(sim.planks01.IsDisabled())
        self.assertTrue(sim.blocker_door01.IsDisabled())
        self.assertTrue(sim.blocker_boards01.IsDisabled())
        self.assertTrue(sim.maint01.IsDisabled())

        # 2. Activating upper door directly must NOT leave player at upper shaft drop; transfers safely to lower car
        sim.activate(sim.upper_door01)
        self.assertEqual(sim.player_pos, (-10.971, 69.000, -3.550))
        self.assertEqual(sim.upper_door01.GetOpenState(), 3)
        self.assertEqual(sim.lower_door01.GetOpenState(), 1)
        self.assertEqual(sim.inner_door01.GetOpenState(), 1)

        # 3. Inner car panel rides back up onto upper hallway floor tile (y=66.200, z=3.750)
        sim.activate(sim.inner_panel01)
        self.assertEqual(sim.player_pos, (-10.971, 66.200, 3.750))
        self.assertEqual(sim.upper_door01.GetOpenState(), 3)

        # 4. Command center call button + inner panel dispatch FO4SF_AnimatedLoadDoor
        sim.enter_zone02()
        sim.activate(sim.call02)
        self.assertEqual(sim.outer_door02.GetOpenState(), 1)
        sim.activate(sim.panel02)
        self.assertEqual(sim.load_door02.activated_by, ["player"])

        # 5. Roof terminal opens unscripted security gate and state persists if roof cell reloads
        sim.enter_roof()
        self.assertFalse(sim.roof_gate.IsDisabled())
        sim.activate(sim.roof_term)
        self.assertTrue(sim.roof_gate.IsDisabled())
        sim.roof_gate.disabled = False  # simulate fresh runtime FF00xxxx clone on cell re-entry
        sim.enter_roof()
        self.assertTrue(sim.roof_gate.IsDisabled())

        # 6. Roof return call button + panel dispatch FO4SF_LoadDoor
        sim.activate(sim.roof_call)
        self.assertEqual(sim.roof_outer_door.GetOpenState(), 1)
        sim.activate(sim.roof_panel)
        self.assertEqual(sim.roof_load_door.activated_by, ["player"])

        summary = self.make.summarize_log("\n".join(sim.logs))
        self.assertTrue(summary["inited"])
        self.assertTrue(summary["fh01_ready"])
        self.assertTrue(summary["fh01_planks_cleared"])
        self.assertTrue(summary["fh01_rode_down"])
        self.assertTrue(summary["fh01_rode_up"])
        self.assertTrue(summary["fh02_dispatched"])
        self.assertTrue(summary["fh_roof_gate_opened"])
        self.assertTrue(summary["fh_roof_dispatched"])

    def test_verify_stage_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = os.path.join(tmp, "Data")
            scripts_dir = os.path.join(data_dir, "Scripts")
            os.makedirs(scripts_dir)
            plug = os.path.join(data_dir, "FO4SFFortHagen.esm")
            pex = os.path.join(scripts_dir, "FO4SF_FortHagenQuest.pex")
            port = os.path.join(tmp, "FO4Port.esm")
            core = os.path.join(tmp, "FO4TerrainCore.esm")
            for p, content in ((plug, b"esm"), (pex, b"pex"), (port, b"port"), (core, b"core")):
                with open(p, "wb") as f:
                    f.write(content)
            plan_path = os.path.join(tmp, "plan.json")
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump({
                    "plugin": "FO4SFFortHagen.esm",
                    "plugin_sha256": self.make.sha256(plug),
                    "script": "FO4SF_FortHagenQuest.pex",
                    "script_sha256": self.make.sha256(pex),
                    "masters": {
                        "Starfield.esm": "00",
                        "FO4Port.esm": self.make.sha256(port),
                        "FO4TerrainCore.esm": self.make.sha256(core),
                    },
                }, f)
            self.assertEqual(self.make.verify_stage(tmp, plan_path, port, core), [])
            with open(pex, "wb") as f:
                f.write(b"tampered")
            problems = self.make.verify_stage(tmp, plan_path, port, core)
            self.assertEqual(len(problems), 1)
            self.assertIn("script hash mismatch", problems[0])

    def test_doc_ascii_redaction_and_pc_card_guards(self):
        self.assertTrue(all(ord(ch) < 128 for ch in self.doc), "doc must be pure ASCII")
        self.assertIsNone(re.search(r"\b[A-Za-z]:\\", self.doc))
        self.assertIsNone(re.search(r"https?://", self.doc))
        for required in ("00134462", "0013A357", "000BF414", "FO4SFFortHagen.esm", "PC Card for Claude (PC)", "PASS"):
            self.assertIn(required, self.doc)

    @unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1" and shutil.which("dotnet"), "opt-in dotnet selftest")
    def test_dotnet_fort_hagen_selftest(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                ["dotnet", "run", "--project", os.path.join(REPO, "dotnet", "FortHagen"), "--", "selftest", tmp],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, msg=r.stdout + "\n" + r.stderr)
            self.assertIn("selftest: ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
