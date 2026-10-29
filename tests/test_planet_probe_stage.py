"""scripts/planet/make_planet_probe.py: precheck, stage and check on synthetic inputs only (tests/planet_fixture.py's
Starfield.esm with its worlds, a synthetic Creation, Terrain01 / PlanetData archives from tests/ba2_fixture.py, a
synthetic ContentResources.zip). The two .NET tools and the Papyrus compiler are replaced by stand-ins that write
what they would: the probe plugin in dotnet/PlanetProbe's layout (planet_fixture.probe_plugin), a small merge probe
plugin and a .pex. No game, no .NET, no compiler."""
import contextlib
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
from types import SimpleNamespace

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "planet"))
import planet_fixture as pf  # noqa: E402
from ba2_fixture import general_archive  # noqa: E402
from fo4sf import btd  # noqa: E402
from fo4sf.planet import biom, esm, probe, records  # noqa: E402
import make_planet_probe as mpp  # noqa: E402

BASE_SOURCES = {
    "ScriptObject": "Scriptname ScriptObject Native Hidden\nFunction StartTimer(float afInterval, int aiTimerID = 0) "
                    "native\nEvent OnTimer(int aiTimerID)\nEndEvent\nEvent OnInit()\nEndEvent\n",
    "Form": "Scriptname Form extends ScriptObject Native Hidden\nInt Function GetFormID() native\n",
    "Quest": "Scriptname Quest extends Form Native Hidden\n",
    "Debug": "Scriptname Debug Native Hidden\nbool Function OpenUserLog(string a) native global\n"
             "bool Function TraceUser(string a, string b, int c = 0) native global\n",
    "Game": "Scriptname Game Native Hidden\nActor Function GetPlayer() native global\n"
            "Form Function GetFormFromFile(int a, string b) native global\nbool Function IsPluginInstalled(string a) native global\n",
    "Location": "Scriptname Location extends Form Native Hidden\n" + "".join(
        f"bool Function {n}() native\n" for n in ("IsChild", "GetCurrentPlanet", "IsLoaded", "CountActors")),
    "ObjectReference": "Scriptname ObjectReference extends Form Native Hidden\n" + "".join(
        f"float Function {n}() native\n" for n in mpp.NATIVES["ObjectReference"]),
    "Planet": "Scriptname Planet extends Form Native Hidden\n" + "".join(
        f"float Function {n}() native\n" for n in mpp.NATIVES["Planet"]),
    "Utility": "Scriptname Utility Native Hidden\nfloat Function GetCurrentRealTime() native global\n",
}


def content_resources(path, sources=BASE_SOURCES):
    with zipfile.ZipFile(path, "w") as z:
        for name, text in sources.items():
            z.writestr(f"Scripts/Source/{name}.psc", text)
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "flags")


def template_btd():
    h = np.full((128, 128), 30000, np.uint16)
    w = np.full((128, 128), 7, np.uint16)
    quad = np.zeros((2, 2, 8), np.uint8)
    quad[..., 0] = 1
    return btd.write(btd.Btd(6, -500.0, 1000.0, [0x001235C2], h, w, quad))


class Tools:
    """Stand-ins for `dotnet run` (PlanetProbe and MergeProbe) and the Papyrus compiler."""

    def __init__(self, check_text="all checks pass"):
        self.calls = []
        self.check_text = check_text

    def run(self, cmd, cwd=None, check=True):
        self.calls.append(cmd)
        project = os.path.basename(cmd[cmd.index("--project") + 1])
        verb = cmd[cmd.index("--") + 1]
        if project == "PlanetProbe" and verb == "build":
            with open(cmd[-2], encoding="utf-8") as f:
                prm = json.load(f)
            pf.probe_plugin(os.path.join(cmd[-1], probe.PLUGIN), prm)
            return SimpleNamespace(stdout="wrote\n", returncode=0)
        if project == "PlanetProbe":
            return SimpleNamespace(stdout=self.check_text + "\n", returncode=0)
        if verb == "build":
            w = esm.PluginWriter(["Starfield.esm"], esm.ESM)
            w.add(esm.Record(b"STAT", w.own(0x800), [(b"EDID", b"MergeStandIn\0")]))
            w.write(os.path.join(cmd[-1], mpp.MERGE_PLUGIN))
            return SimpleNamespace(stdout="wrote merge\n", returncode=0)
        return SimpleNamespace(stdout="merge check ok\n", returncode=0)

    def compile(self, compiler, name, src_dir, out_dir):
        self.calls.append(["compile", name, sorted(os.listdir(src_dir))])
        os.makedirs(out_dir, exist_ok=True)
        pex = os.path.join(out_dir, name + ".pex")
        with open(pex, "wb") as f:
            f.write(b"\xfa\x57\xc0\xde pex stand-in")
        return pex


class StageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="fo4sf-planetstage-")
        cls.data = os.path.join(cls.root, "Data")
        os.makedirs(cls.data)
        pf.write_starfield(os.path.join(cls.data, "Starfield.esm"), census=True)
        pf.write_creation(os.path.join(cls.data, "SFBGS00X.esm"))
        with open(os.path.join(cls.data, mpp.TERRAIN_ARCHIVE), "wb") as f:
            f.write(general_archive({mpp.BTD_TEMPLATE: template_btd()}))
        biome_map = struct.pack("<HI2I", biom.MAGIC, 2, 0x0007F88A, 0x000FD00D) + b"\x22" * 32
        with open(os.path.join(cls.data, biom.ARCHIVE), "wb") as f:
            f.write(general_archive({"planetdata/biomemaps/jemison.biom": biome_map}))
        cls.cr = os.path.join(cls.root, "ContentResources.zip")
        content_resources(cls.cr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root)

    def setUp(self):
        self.tools = Tools()
        self.saved = (mpp.run, mpp.compile_script)
        mpp.run, mpp.compile_script = self.tools.run, self.tools.compile
        self.out = tempfile.mkdtemp(prefix="stage-", dir=self.root)
        os.rmdir(self.out)

    def tearDown(self):
        mpp.run, mpp.compile_script = self.saved

    def main(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                code = mpp.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, buf.getvalue()

    def stage(self, *extra):
        return self.main("stage", "--data", self.data, "--out", self.out, "--content-resources", self.cr,
                         "--compiler", "PapyrusCompiler.exe", "--mask-writer", "builtin", *extra)

    def plan(self):
        with open(os.path.join(self.out, "plan.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_stage_writes_every_part_and_check_passes(self):
        code, text = self.stage()
        self.assertEqual(code, 0, text)
        plan = self.plan()
        self.assertEqual(plan["plugins"], [records.MASTER, probe.PLUGIN, records.REGISTRATION, mpp.MERGE_PLUGIN])
        self.assertEqual(plan["archive"], "FO4SFPlanet - Main.ba2")
        self.assertEqual(sorted(plan["outputs"]), sorted(
            plan["plugins"] + [probe.BTD_REL, "Data/textures/terrain/overlaymasks/fo4sf_planetprobeworld.dds",
                               "Data/PlanetData/BiomeMaps/fo4sf probe.biom",
                               "Data/PlanetData/BiomeMaps/fo4sfplanet.esm/fo4sf probe.biom",
                               f"Data/Scripts/{probe.SCRIPT}.pex"]))
        self.assertEqual([a["label"] for a in plan["arrivals"]], ["lc172", "probe", "temp_jemison", "new_atlantis"])
        self.assertEqual(plan["arrivals"][1]["coc"], probe.SPAWN_EDID)
        self.assertEqual(plan["options"]["world_biome_id"], "07F88A:Starfield.esm")
        merge = plan["merge"]["local"]
        self.assertAlmostEqual(merge[0], pf.LC172_COC_POS[0] + mpp.MERGE_OFFSET, places=4)
        self.assertEqual(plan["known_ids"]["Mars"], "0003F59A")
        self.assertEqual(plan["known_ids"]["Jemison"], f"{pf.JEMISON:08X}")
        for name in ("README.txt", "census.json", "probe_params.json", "offline_check.json", "offline_check_mutagen.txt",
                     "offline_check_merge.txt", probe.SCRIPT + ".psc"):
            self.assertTrue(os.path.isfile(os.path.join(self.out, name)), name)
        self.assertFalse(os.path.exists(os.path.join(self.out, "work")))
        with open(os.path.join(self.out, "README.txt"), encoding="utf-8") as f:
            readme = f.read()
        self.assertIn("planet_probe_install.py install", readme)
        self.assertIn(f"2. coc {probe.SPAWN_EDID}", readme)
        compiled = [c for c in self.tools.calls if c[0] == "compile"]
        self.assertEqual(compiled[0][1], probe.SCRIPT)
        self.assertIn("Starfield_Papyrus_Flags.flg", compiled[0][2])
        code, text = self.main("check", "--stage", self.out, "--data", self.data)
        self.assertEqual(code, 0, text)
        # the stage is never overwritten
        code, text = self.stage()
        self.assertNotEqual(code, 0)
        self.assertIn("exists", str(code) + text)

    def test_check_finds_changed_and_extra_files(self):
        self.assertEqual(self.stage()[0], 0)
        btd_path = os.path.join(self.out, *probe.BTD_REL.split("/"))
        with open(btd_path, "ab") as f:
            f.write(b"\0")
        code, text = self.main("check", "--stage", self.out)
        self.assertEqual(code, 1)
        self.assertIn("changed after the stage", text)
        with open(os.path.join(self.out, "Data", "extra.txt"), "w") as f:
            f.write("x")
        code, text = self.main("check", "--stage", self.out)
        self.assertIn("files not in plan.json", text)

    def test_no_merge_probe_and_keep_biome(self):
        code, text = self.stage("--no-merge-probe", "--world-biome", "keep")
        self.assertEqual(code, 0, text)
        plan = self.plan()
        self.assertEqual(plan["plugins"], [records.MASTER, probe.PLUGIN, records.REGISTRATION])
        self.assertIsNone(plan["merge"])
        self.assertIsNone(plan["options"]["world_biome_id"])
        with open(os.path.join(self.out, "probe_params.json"), encoding="utf-8") as f:
            self.assertIsNone(json.load(f)["world_biome"])

    def test_a_failed_tool_check_publishes_nothing(self):
        mpp.run = Tools(check_text="1 problem(s)").run
        code, text = self.stage()
        self.assertNotEqual(code, 0)
        self.assertFalse(os.path.exists(self.out))
        self.assertTrue(any(n.startswith(os.path.basename(self.out) + ".partial-") for n in os.listdir(self.root)))


class PrecheckTests(unittest.TestCase):
    def test_every_native_found_through_parents(self):
        r = mpp.precheck_sources({k.lower(): v for k, v in BASE_SOURCES.items()})
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["natives"]["Quest.GetFormID"])                 # declared on Form
        self.assertTrue(r["natives"]["ScriptObject.OnTimer"])

    def test_a_missing_native_fails(self):
        src = dict(BASE_SOURCES)
        src["Planet"] = "Scriptname Planet extends Form Native Hidden\n"
        with tempfile.TemporaryDirectory() as d:
            zp = os.path.join(d, "cr.zip")
            content_resources(zp, src)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(mpp.main(["precheck", "--content-resources", zp]), 1)

    def test_world_biome_choice(self):
        rep = {"planet_biomes": ["0007F88A", "000FD00D"],
               "new_atlantis": {"biome_in_planet_biomes": True, "world": {"biome": "000FD00D"}}}
        self.assertEqual(mpp.world_biome(rep, "planet")[0], ("Starfield.esm", 0xFD00D))
        rep["new_atlantis"]["biome_in_planet_biomes"] = False
        self.assertEqual(mpp.world_biome(rep, "planet")[0], ("Starfield.esm", 0x7F88A))
        self.assertIsNone(mpp.world_biome(rep, "keep")[0])
        with self.assertRaises(SystemExit):
            mpp.world_biome({"planet_biomes": []}, "planet")


if __name__ == "__main__":
    unittest.main()
