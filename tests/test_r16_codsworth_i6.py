"""Round 16 I6 Codsworth fixes verification tests:
(a) Talk with E at 2 m front & side via invisible Havok sphere proxy NIF (codsworth_talk_proxy.nif)
(b) Zero MiniBot legs on --codsworth-handy (no Skin_MiniBotA_Base or MiniBotARace ArmorRace/AdditionalRaces)
(c) No greeting replay on second talk (SayOnce + GLOB 0x00097C FO4SF_CodsworthGreeted + repeat INFO 0x943)
(d) Stage 24 / 30 / 32 -> 100 -> min00 given progression (PlaceCodsworth yields during Sanctuary house walk)
"""
import os
import struct
import sys
import unittest
from types import SimpleNamespace

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(ROOT, "scripts", "mission"))

from fo4sf import ba2, nif as nifmod, sfnif  # noqa: E402
import make_mission  # noqa: E402
from tests.test_mission import _translate_mission_psc, A1dRealTalkTests  # noqa: E402
from tests.test_r11_cell_independent_quest import (  # noqa: E402
    _build_codsworth_harness,
    _build_min00_harness,
    _compile_papyrus,
    _FakeActor,
)

CS_PATH = os.path.join(ROOT, "dotnet", "Mission", "Program.cs")
CODS_PSC = os.path.join(ROOT, "scripts", "mission", "FO4SF_Codsworth01Quest.psc")
MIN00_PSC = os.path.join(ROOT, "scripts", "mission", "FO4SF_Min00Quest.psc")
SF_MESHES01 = r"D:\SteamLibrary\steamapps\common\Starfield\Data\Starfield - Meshes01.ba2"
E2_NIF = r"D:\FO4SF-Owner-Tests\robot-anim\E2\Data\meshes\FO4SF\Actors\Handy\handy.nif"


def _make_synthetic_decorator_nif() -> bytes:
    """Build a minimal Starfield NIF matching SFBGS006_SBShipDecoratorMarker's material + collision block types."""
    n = nifmod.NifFile(
        endian=1, user_version=12, bs_version=175,
        author=b"\x00", unknown_int=0, export_script=b"\x00", sf_data=b"\x7a\x00",
    )
    s_matid = n.string_index(b"MaterialID")
    s_mat = n.string_index(b"materials\\effects\\utility\\editormarkerfx.mat")
    old_id = sfnif.material_id(r"materials\effects\utility\editormarkerfx.mat")
    n.add_block("NiNode", b"\x00" * 64)
    n.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 0, 0x80, 2, 0))
    n.add_block("bhkPhysicsSystem", struct.pack("<I", 4) + b"HAVK")
    n.add_block("NiIntegerExtraData", struct.pack("<iI", s_matid, old_id))
    n.add_block("BSLightingShaderProperty", struct.pack("<iIi", s_mat, 0, -1))
    return nifmod.serialize(n)


class R16CodsworthI6Tests(unittest.TestCase):
    def test_a_talk_proxy_nif_keeps_collision_swaps_to_invisible_mat_and_covers_torso_sides(self):
        # 1. Synthetic NIF test (always runs cleanly offline)
        raw = _make_synthetic_decorator_nif()
        patched = sfnif.build_codsworth_talk_proxy_nif(raw)
        pn = nifmod.parse(patched)
        self.assertTrue(any(s == sfnif.INVISIBLE_MATERIAL_PATH.encode("latin-1") for s in pn.strings))
        self.assertFalse(any(b"editormarkerfx.mat" in s.lower() for s in pn.strings))
        mat_id_idx = pn.strings.index(b"MaterialID")
        want_id = sfnif.material_id(sfnif.INVISIBLE_MATERIAL_PATH)
        self.assertEqual(want_id, 0x242EBC61)
        mat_ids = [
            struct.unpack_from("<I", pn.blocks[i], 4)[0]
            for i in range(len(pn.blocks))
            if pn.type_of(i) == "NiIntegerExtraData"
            and struct.unpack_from("<i", pn.blocks[i], 0)[0] == mat_id_idx
        ]
        self.assertEqual(mat_ids, [want_id])
        self.assertTrue(any(pn.type_of(i) == "bhkPhysicsSystem" for i in range(len(pn.blocks))))

        # 2. Real Starfield - Meshes01.ba2 SFBGS006_SBShipDecoratorMarker check when installed
        if os.path.isfile(SF_MESHES01):
            real_raw = ba2.Ba2(SF_MESHES01).read(make_mission.DECORATOR_MARKER_NIF)
            real_patched = sfnif.build_codsworth_talk_proxy_nif(real_raw)
            rn = nifmod.parse(real_patched)
            self.assertEqual(len(rn.blocks), len(nifmod.parse(real_raw).blocks))
            self.assertFalse(any(b"editormarkerfx.mat" in s.lower() for s in rn.strings))
            self.assertIn(sfnif.INVISIBLE_MATERIAL_PATH.encode("latin-1"), rn.strings)
            r_mat_idx = rn.strings.index(b"MaterialID")
            r_vals = [
                struct.unpack_from("<I", rn.blocks[i], 4)[0]
                for i in range(len(rn.blocks))
                if rn.type_of(i) == "NiIntegerExtraData"
                and struct.unpack_from("<i", rn.blocks[i], 0)[0] == r_mat_idx
            ]
            self.assertEqual(r_vals, [0x242EBC61])
            geom = next(
                sfnif.parse_bsgeometry(rn.blocks[i])
                for i in range(len(rn.blocks))
                if rn.type_of(i) == "BSGeometry"
            )
            # ProxyScale = 2.2 * half-extent (0.25 m) = 0.55 m wraps Torso (X=0.523 m, Y=0.408 m) front and side
            proxy_half_extent = geom.box[3] * 2.2
            self.assertGreater(proxy_half_extent, 0.525)

        # 3. ESM & PSC contract + live E-activation via proxy
        with open(CS_PATH, encoding="utf-8") as f:
            cs = f.read()
        with open(CODS_PSC, encoding="utf-8") as f:
            c_psc = f.read()
        self.assertIn('CodsworthTalkProxyModel = "FO4SF\\\\Actors\\\\Handy\\\\codsworth_talk_proxy.nif"', cs)
        self.assertIn("First = new P3Float(-0.55f, -0.55f, -0.55f)", cs)
        self.assertIn("Second = new P3Float(0.55f, 0.55f, 0.55f)", cs)
        self.assertIn("float ProxyZOffset = 1.38", c_psc)
        self.assertIn("float ProxyScale = 2.2", c_psc)

        h = A1dRealTalkTests()._build_harnesses(glob_val=0.0)
        h.c_ns["BindCodsworthActivation"]()
        h.c_ns["OnActivate"](h.c_ns["talkProxy"], h.player)
        self.assertTrue(any("via=proxy" in ln and "codsworth scene talk requested" in ln for ln in h.logs), h.logs)

    def test_b_handy_codsworth_has_zero_minibot_legs_race_armor_or_skin(self):
        with open(CS_PATH, encoding="utf-8") as f:
            cs = f.read()
        # HandyCodsworthRace clears Skin (never inherits Skin_MiniBotA_Base); Write clears ArmorRace and AdditionalRaces
        handy_fn = cs[cs.index("public static SF.Race HandyCodsworthRace("):cs.index("public static int Check(")]
        self.assertIn("race.Skin.Clear();", handy_fn)
        self.assertNotIn("baseBotRace.Skin", handy_fn)
        self.assertIn("if (codsworthHandy is null)\n                codsRace.ArmorRace.SetTo(baseBotRace.FormKey);\n            else\n                codsRace.ArmorRace.Clear();", cs)
        self.assertIn("arma.AdditionalRaces.Clear();", cs)
        self.assertIn("skin.Race.SetTo(codsRace.FormKey);", cs)
        self.assertIn("codsRace.Skin.SetTo(skin.FormKey);", cs)

        if os.path.isfile(E2_NIF):
            with open(E2_NIF, "rb") as f:
                hn = nifmod.parse(f.read())
            shapes = [
                hn.strings[sfnif.parse_bsgeometry(hn.blocks[i]).name_idx]
                for i in range(len(hn.blocks))
                if hn.type_of(i) == "BSGeometry"
            ]
            self.assertEqual(shapes, [b"Torso", b"Legs", b"HandyShell", b"Arms:0", b"Arms:1"])

    def test_c_greeting_does_not_replay_on_second_talk(self):
        with open(CS_PATH, encoding="utf-8") as f:
            cs = f.read()
        self.assertIn("CodsworthGreetRepeatInfoId = 0x943", cs)
        self.assertIn("CodsworthGreetedGlobId = 0x97C", cs)
        self.assertIn("SF.DialogResponses.Flag.SayOnce", cs)
        self.assertIn("GlobalIsZero(ggKey)", cs)
        self.assertIn("greetedOnceGlobKey: new FormKey(modKey, CodsworthGreetedGlobId)", cs)

        h = A1dRealTalkTests()._build_harnesses(glob_val=0.0)
        greeted_glob = SimpleNamespace(val=0.0)
        greeted_glob.GetValue = lambda: greeted_glob.val
        greeted_glob.SetValue = lambda v: setattr(greeted_glob, "val", float(v))
        orig_get = h.c_ns["Game"].GetFormFromFile
        h.c_ns["Game"] = SimpleNamespace(
            GetPlayer=h.c_ns["Game"].GetPlayer,
            GetFormFromFile=lambda fid, plg: greeted_glob if (fid, plg) == (0x00097C, "FO4SFMission.esm") else orig_get(fid, plg),
            StartDialogueCameraOrCenterOnTarget=lambda *_: None,
        )
        # First talk plays 0x942, opens DialogueMenu, and flips GLOB 0x00097C -> 1.0
        h.c_ns["BindCodsworthActivation"]()
        h.c_ns["OnActivate"](h.c_ns["talkProxy"], h.player)
        h.c_ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertEqual(greeted_glob.GetValue(), 1.0)
        self.assertTrue(any("codsworth01 greeting_played=1" in ln for ln in h.logs), h.logs)

        # Choice 3 sets stage 24 and DialogueMenu closes; second talk still sees GLOB 0x00097C == 1.0 (0x942 gated)
        h.c_ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
        self.assertEqual(greeted_glob.GetValue(), 1.0)

    def test_d_stage_24_30_32_walk_yields_keeper_and_completes_to_stage_100_min00_given(self):
        # 1. Codsworth01 S3 harness: Choice 3 (stage 24) -> Choice 4 (stage 30) -> H1 walk (32) -> 34 -> H2 (36/38) -> 40 -> 50 -> 100 -> min00
        stage50_scene = SimpleNamespace(
            is_playing=False,
            Start=lambda: setattr(stage50_scene, "is_playing", True),
            ForceStart=lambda: setattr(stage50_scene, "is_playing", True),
            Stop=lambda: setattr(stage50_scene, "is_playing", False),
            IsPlaying=lambda: stage50_scene.is_playing,
        )
        h = _build_codsworth_harness(enable_s3=True, creature_slot_ready=False, stage50_scene=stage50_scene)
        with open(CODS_PSC, encoding="utf-8") as f:
            _compile_papyrus(
                f.read(),
                ["IsS3HouseWalkActive"],
                {"EnableS3HouseSearch", "completed", "s3House1Started"},
                h.ns,
            )

        # Before stage 30: S3 house walk is not active
        self.assertFalse(h.ns["IsS3HouseWalkActive"]())

        # Choice 3 sets stage 24
        h.ns["SetStage"](24)
        h.ns["SyncProgress"]()
        self.assertTrue(any("codsworth01 stage 24 by=" in ln for ln in h.logs), h.logs)
        self.assertTrue(h.ns["choice3Seen"])

        # Choice 4 sets stage 30 -> UpdateS3HouseSearchProgress starts House 1 walk (stage 32)
        h.ns["SetStage"](30)
        h.ns["UpdateS3HouseSearchProgress"]()
        self.assertIn(32, h.stages)
        self.assertTrue(h.ns["s3House1Started"])
        self.assertTrue(h.ns["IsS3HouseWalkActive"]())

        # 2. Verify Min00 PlaceCodsworth yields while Codsworth01 is in S3 house walk (stages 30..99)
        mh = _build_min00_harness(keeper_only=True)
        with open(MIN00_PSC, encoding="utf-8") as f:
            _compile_papyrus(
                f.read(),
                ["PlaceCodsworth", "HeldState"],
                {
                    "CodsworthLocalX", "CodsworthLocalY", "CodsworthLocalZ",
                    "MergeOffsetX", "MergeOffsetY", "Codsworth", "codsworthHeld", "codsworthState",
                },
                mh.ns,
            )
        cods01_proxy = SimpleNamespace(IsS3HouseWalkActive=h.ns["IsS3HouseWalkActive"])
        orig_m_get = mh.ns["Game"].GetFormFromFile
        mh.ns["Game"] = SimpleNamespace(
            GetFormFromFile=lambda fid, plg: cods01_proxy if (fid, plg) == (0x000816, "FO4SFMission.esm") else orig_m_get(fid, plg),
            GetPlayer=mh.ns["Game"].GetPlayer,
        )
        placed = []
        mh.ns["PlaceAt"] = lambda *a, **kw: (placed.append(a), "keep")[1]
        mh.ns["HeldRadius"] = 25.0
        mh.ns["CodsworthLocalX"] = -1146.709
        mh.ns["CodsworthLocalY"] = 1293.837
        mh.ns["CodsworthLocalZ"] = 111.734
        mh.ns["MergeOffsetX"] = -1200.0
        mh.ns["MergeOffsetY"] = -2700.0
        mh.ns["Codsworth"] = h.cods
        mh.ns["codsworthHeld"] = True
        self.assertFalse(mh.ns["PlaceCodsworth"](mh.player))
        self.assertFalse(mh.ns["codsworthHeld"])
        self.assertEqual(mh.ns["codsworthState"], "s3_house_walk")
        self.assertEqual(placed, [])  # Never teleports Codsworth back inside HoldRadius=25 m!

        # 3. Complete House 1 (34) -> House 2 (36, 38) -> Stage 40/50 -> Stage 100 -> min00.GiveFromCodsworth()
        h.cods.SetPosition(-2313.44, -1372.02, 112.66)
        h.ns["UpdateS3HouseSearchProgress"]()
        self.assertIn(34, h.stages)
        self.assertIn(38, h.stages)
        self.assertTrue(h.ns["IsS3HouseWalkActive"]())

        h.cods.SetPosition(-2296.17, -1424.97, 111.77)
        h.ns["UpdateS3HouseSearchProgress"]()
        self.assertIn(40, h.stages)
        self.assertIn(50, h.stages)

        # Simulate Stage 50 DialogueMenu finishing -> stage 100 -> CompleteS3AndPointToConcord -> GiveFromCodsworth
        h.ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        h.ns["SetStage"](100)
        h.ns["Scene_OnEnd"](stage50_scene)
        self.assertIn(100, h.stages)
        self.assertTrue(h.ns["completed"])
        self.assertFalse(h.ns["IsS3HouseWalkActive"]())
        self.assertEqual(h.min00.codsworth_given, 1)
        self.assertTrue(any("codsworth01 stage 100 concord_pointed=true" in ln for ln in h.logs), h.logs)


if __name__ == "__main__":
    unittest.main()
