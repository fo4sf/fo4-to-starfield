"""robot-anim: make_mission.py --codsworth-handy (Codsworth on the converted Mr. Handy body). Synthetic bundles only."""
import os
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "mission"))

from fo4sf import handy_race as hr  # noqa: E402
from fo4sf.planet import esm  # noqa: E402
import make_mission as mm  # noqa: E402

STRAF, FURN, ROOT = hr.STRAFING_GRAPH, hr.FURNITURE_GRAPH, hr.ROOT_GRAPH
CLIPS = "Actors\\FO4SF\\Handy\\Animations"


def write_bundle(root, mesh=True, gsd=True):
    """A stage_ra2_handy.py-shaped bundle: template plugin + Data with Handy files, a Mini Bot test race's files and
    manifests of another key."""
    subs = [(b"EDID", esm.zbytes(mm.HANDY_RACE_EDID)), (b"NAM6", esm.zbytes(ROOT)),
            (b"SGNM", esm.zbytes(STRAF)), (b"SAPT", esm.zbytes(CLIPS)),
            (b"SGNM", esm.zbytes(FURN)), (b"SAPT", esm.zbytes(CLIPS + "\\Furniture")), (b"SAPT", esm.zbytes(CLIPS))]
    w = esm.PluginWriter(["Starfield.esm"], author="test")
    w.add(esm.Record(b"RACE", 0x01000800, subs))
    w.write(os.path.join(root, mm.HANDY_TEMPLATE))
    keys = [hr.manifest_key(g, f) for g, f in ((STRAF, [CLIPS]), (FURN, [CLIPS + "\\Furniture", CLIPS]))]
    files = ["geometries/abc/0123456789abcdef.mesh",
             "meshes/Actors/FO4SF/Handy/Animations/idle.af",
             "meshes/fo4sf/actors/handy/characterassets/skeleton.rig",
             "meshes/Actors/FO4SF/RA2MiniBot/Animations/idle.af",
             "meshes/fo4sf/actors/RA2MiniBot/CharacterAssets/skeleton.rig",
             "meshes/AnimTextData/GeneratedSubgraphData/fo4sf_ra2minibotownfolderrace.txt",
             "meshes/AnimTextData/AnimationFileData/1234.txt"]
    files += [f"meshes/AnimTextData/{d}/{k}.txt" for k in keys for d in ("AnimationFileData", "AnimationOffsets")]
    if mesh:
        files.append("meshes/FO4SF/Actors/Handy/handy.nif")
    if gsd:
        files.append("meshes/AnimTextData/GeneratedSubgraphData/fo4sf_handyrace.txt")
    for rel in files:
        p = os.path.join(root, "Data", *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(rel.encode())
    return keys


class HandyBundleFiles(unittest.TestCase):
    def test_takes_handy_files_renames_subgraph_text_leaves_test_files(self):
        with tempfile.TemporaryDirectory() as d:
            keys = write_bundle(d)
            template, files = mm.handy_bundle_files(d)
            self.assertEqual(template, os.path.join(d, mm.HANDY_TEMPLATE))
            dst = {v.lower() for v in files.values()}        # Windows folders are case-insensitive
            self.assertIn("meshes/animtextdata/generatedsubgraphdata/fo4sf_codsworthrace.txt", dst)
            self.assertNotIn("meshes/animtextdata/generatedsubgraphdata/fo4sf_handyrace.txt", dst)
            for k in keys:
                self.assertIn(f"meshes/animtextdata/animationfiledata/{k}.txt", dst)
                self.assertIn(f"meshes/animtextdata/animationoffsets/{k}.txt", dst)
            self.assertIn("meshes/fo4sf/actors/handy/handy.nif", dst)
            self.assertIn("meshes/fo4sf/actors/handy/characterassets/skeleton.rig", dst)
            self.assertIn("geometries/abc/0123456789abcdef.mesh", dst)
            self.assertFalse([p for p in dst if "ra2minibot" in p.lower()])
            self.assertNotIn("meshes/animtextdata/animationfiledata/1234.txt", dst)
            self.assertEqual(len(dst), 9)

    def test_refuses_bundle_without_mesh_or_subgraph_text(self):
        for kw in ({"mesh": False}, {"gsd": False}):
            with tempfile.TemporaryDirectory() as d:
                write_bundle(d, **kw)
                with self.assertRaises(SystemExit):
                    mm.handy_bundle_files(d)

    def test_refuses_folder_without_template(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "Data"))
            with self.assertRaises(SystemExit):
                mm.handy_bundle_files(d)

    def test_copy_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as data:
            write_bundle(d)
            template, copied = mm.copy_handy_bundle(d, data)
            self.assertEqual(len(copied), 9)
            with open(os.path.join(data, "meshes", "AnimTextData", "GeneratedSubgraphData",
                                   "fo4sf_codsworthrace.txt"), "rb") as f:
                self.assertEqual(f.read(), b"meshes/AnimTextData/GeneratedSubgraphData/fo4sf_handyrace.txt")
            with self.assertRaises(SystemExit):
                mm.copy_handy_bundle(d, data)


class MissionBuilderOption(unittest.TestCase):
    def test_dotnet_mission_has_the_option_and_local_body_parts(self):
        with open(os.path.join(REPO, "dotnet", "Mission", "Program.cs"), encoding="utf-8") as f:
            cs = f.read()
        self.assertEqual(cs.count('ArgOrNull(args, "--codsworth-handy")'), 2)          # write and check
        self.assertIn("CodsworthBptdId = 0x81A", cs)
        self.assertIn('CodsworthBptdEdid = "FO4SF_CodsworthBodyPartData"', cs)
        self.assertIn(f'HandyRaceEdid = "{mm.HANDY_RACE_EDID}"', cs)
        self.assertIn("codsRace = HandyCodsworthRace(codsworthHandy, mod, baseBotRace);", cs)
        self.assertIn("links into the template left after the copy", cs)
        self.assertIn("--codsworth-race-framing cannot be used together with --codsworth-handy", cs)
        self.assertIn("refusal verified: --codsworth-race-framing with --codsworth-handy", cs)
        self.assertIn("BodyPartData cleared", cs)

    def test_make_mission_rejects_framing_with_handy_and_tracks_args(self):
        from types import SimpleNamespace
        ns = SimpleNamespace(
            fo4="x/Fallout4.esm",
            starfield="x/Starfield.esm",
            core="x/FO4TerrainCore.esm",
            raider="x/FO4ActorRaider.esm",
            compiler="x/PapyrusCompiler.exe",
            content_resources="x/ContentResources.zip",
            codsworth_handy="x/E2",
            codsworth_race_framing=True,
            codsworth=True,
            alias=True,
        )
        args = mm.mission_cli_args(ns, "x/out")
        self.assertIn("--codsworth-handy", args)
        _p, _r, cods_desc = mm.build_look_descriptions(ns)
        self.assertIn("handy.nif", cods_desc)
        self.assertIn("--codsworth-handy", cods_desc)
        with self.assertRaises(SystemExit) as ctx:
            mm.stage(ns)
        self.assertIn("--codsworth-race-framing", str(ctx.exception))

    def test_beginning_pilot_accepts_handy_nif(self):
        import json
        from fo4sf.beginning_pilot import CODSWORTH_HANDY_NIF_REL, verify_bundle_beginning_readiness
        with tempfile.TemporaryDirectory() as td:
            bdir = os.path.join(td, "bundle")
            handy_p = os.path.join(bdir, "Data", *CODSWORTH_HANDY_NIF_REL.split("/"))
            os.makedirs(os.path.dirname(handy_p), exist_ok=True)
            with open(handy_p, "wb") as f:
                f.write(b"NIF")
            w = esm.PluginWriter(("Starfield.esm",), flags=esm.ESM, author="test")
            w.add(esm.Record(b"ARMA", w.own(0x812), [(b"EDID", esm.zbytes("FO4_AA_Codsworth")), (b"MOD2", esm.zbytes(mm.HANDY_MESH))], 0, 0, 581, 0))
            w.write(os.path.join(bdir, "FO4SFMission.esm"))
            with open(os.path.join(bdir, "bundle_plan.json"), "w", encoding="utf-8") as f:
                json.dump({"plugins": ["FO4SFMission.esm"], "asset_dirs": {"codsworth_handy": {"path": "x"}}}, f)
            res = verify_bundle_beginning_readiness(bdir, require_map_markers=False)
            b5_issues = res["steps"]["B5_codsworth_sanctuary"]["issues"]
            self.assertFalse(any("Codsworth" in i and "NIF" in i for i in b5_issues), b5_issues)

    def test_handy_names_match_the_converter(self):
        self.assertEqual(mm.HANDY_RACE_EDID, hr.HANDY_EDID)
        sys.path.insert(0, os.path.join(REPO, "scripts", "probes"))
        import stage_ra2_handy as ra2
        self.assertEqual(mm.HANDY_TEMPLATE, ra2.PLUGIN)
        self.assertEqual(mm.HANDY_MESH, ra2.HANDY_MODEL)


if __name__ == "__main__":
    unittest.main()
