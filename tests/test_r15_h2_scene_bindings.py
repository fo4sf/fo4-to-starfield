"""Round 15 Wave B Item H2 tests: Scene VMAD property removal, Mission check/selftest,
dynamic GetFormFromFile resolution for 0xB9A / 0xBC9 / 0xBD0, and Min00 stage-35 fallback."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests"))
if str(REPO_ROOT / "scripts" / "core") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "core"))

import test_r11_cell_independent_quest as s2s6  # noqa: E402


CODS_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_Codsworth01Quest.psc"
MIN00_PSC = REPO_ROOT / "scripts" / "mission" / "FO4SF_Min00Quest.psc"
S2S6_CS = REPO_ROOT / "dotnet" / "Mission" / "NextStoryMissionsS2S6.cs"


def _make_fake_scene(name: str):
    state = {"playing": False, "starts": 0, "stops": 0}

    def _start():
        state["playing"] = True
        state["starts"] += 1

    def _stop():
        state["playing"] = False
        state["stops"] += 1

    scn = SimpleNamespace(
        name=name,
        state=state,
        IsPlaying=lambda: state["playing"],
        Start=_start,
        ForceStart=_start,
        Stop=_stop,
    )
    return scn


class TestR15H2SceneBindings(unittest.TestCase):
    def test_zero_scene_vmad_properties_in_source_and_built_plugin_with_selftest(self):
        cods_src = CODS_PSC.read_text(encoding="utf-8")
        min00_src = MIN00_PSC.read_text(encoding="utf-8")
        s2s6_src = S2S6_CS.read_text(encoding="utf-8")

        self.assertNotIn("Scene Property S3Stage50Scene", cods_src)
        self.assertNotIn("Scene Property S6PrestonRoomScene", min00_src)
        self.assertNotIn("Scene Property S6SturgesRoomScene", min00_src)
        self.assertNotIn('ObjProp("S3Stage50Scene"', s2s6_src)
        self.assertNotIn('ObjProp("S6PrestonRoomScene"', s2s6_src)
        self.assertNotIn('ObjProp("S6SturgesRoomScene"', s2s6_src)
        # H5 owns LoadDoorController; ensure it was not touched.
        self.assertIn("LoadDoorController", s2s6_src)

        import build_fo4port_r11_museum as ext

        with tempfile.TemporaryDirectory(prefix="r15_h2_selftest_") as tmpdir:
            env = dict(os.environ)
            env.setdefault("DOTNET_ROLL_FORWARD", "Major")
            proc = subprocess.run(
                [
                    "dotnet",
                    "run",
                    "-c",
                    "Release",
                    "--project",
                    str(REPO_ROOT / "dotnet" / "Mission" / "Mission.csproj"),
                    "--",
                    "selftest",
                    tmpdir,
                ],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=f"selftest failed:\n{proc.stdout}\n{proc.stderr}")
            self.assertIn("selftest pass", proc.stdout)
            self.assertIn("mutation rejected: Sanctuary01 binds arbitrary SCEN-targeting VMAD property", proc.stdout)
            self.assertIn("mutation rejected: Min00 binds SCEN-targeting VMAD list property", proc.stdout)
            self.assertIn("mutation rejected: H2 Codsworth01 binds S3Stage50Scene (0xB9A) VMAD property", proc.stdout)
            self.assertIn("mutation rejected: H2 Min00 binds S6PrestonRoomScene (0xBC9) VMAD property", proc.stdout)
            self.assertIn("mutation rejected: H2 Min00 binds S6SturgesRoomScene (0xBD0) VMAD property", proc.stdout)

            full_esm = Path(tmpdir) / "out" / "r11_full_mission" / "FO4SFMission.esm"
            self.assertTrue(full_esm.is_file())
            raw = full_esm.read_bytes()
            for rec in ext.walk_all_records(raw):
                if rec.sig != b"QUST":
                    continue
                for sub_sig, sub_payload in ext.iter_subrecords(rec.decompressed_body()):
                    if sub_sig == b"VMAD":
                        for forbidden in (
                            b"S3Stage50Scene",
                            b"S6PrestonRoomScene",
                            b"S6SturgesRoomScene",
                            b"PrestonTalkScene",
                            b"PrestonPostTalkScene",
                            b"CodsworthScene",
                            b"CodsworthPostScene",
                        ):
                            self.assertNotIn(
                                forbidden,
                                sub_payload,
                                f"QUST 0x{rec.fid:08X} VMAD still contains {forbidden!r}",
                            )

    def test_all_three_scene_resolvers_resolve_via_file_and_register_events_dynamically(self):
        scn_b9a = _make_fake_scene("FO4SF_S3_Stage50Scene")
        cods = s2s6._FakeActor("Codsworth", -2313.44, -1372.02, 112.66)
        ch = s2s6._build_codsworth_harness(
            enable_s3=True,
            r11_glob_val=1.0,
            codsworth_actor=cods,
            stage50_scene=scn_b9a,
        )
        cods_regs = []
        ch.ns["RegisterForRemoteEvent"] = lambda obj, ev: cods_regs.append((obj, ev))

        resolved_b9a = ch.ns["ResolveActiveCodsworthScene"](False, 0x000B9A, True)
        self.assertIs(resolved_b9a, scn_b9a)
        self.assertTrue(any("scene resolved via=file id=0x000B9A scene=" in ln for ln in ch.logs), ch.logs)

        ch.ns["StartS3Stage50Scene"]()
        self.assertEqual(scn_b9a.state["starts"], 1)
        self.assertIn((scn_b9a, "OnBegin"), cods_regs)
        self.assertIn((scn_b9a, "OnEnd"), cods_regs)

        ch.ns["Scene_OnBegin"](scn_b9a)
        self.assertIn("codsworth01 s3_stage50 scene started", ch.logs)

        s6_preston = _make_fake_scene("FO4SF_S6_PrestonRoomScene")
        s6_sturges = _make_fake_scene("FO4SF_S6_SturgesRoomScene")
        mh = s2s6._build_min00_harness(
            enable_s4=True,
            enable_s6_s9=True,
            s6_preston_scene=s6_preston,
            s6_sturges_scene=s6_sturges,
        )
        min00_regs = []
        mh.ns["RegisterForRemoteEvent"] = lambda obj, ev: min00_regs.append((obj, ev))

        resolved_bc9 = mh.ns["ResolveActivePrestonScene"](False, 0x000BC9, True)
        resolved_bd0 = mh.ns["ResolveActivePrestonScene"](False, 0x000BD0, True)
        self.assertIs(resolved_bc9, s6_preston)
        self.assertIs(resolved_bd0, s6_sturges)
        self.assertTrue(any("scene resolved via=file id=0x000BC9 scene=" in ln for ln in mh.logs), mh.logs)
        self.assertTrue(any("scene resolved via=file id=0x000BD0 scene=" in ln for ln in mh.logs), mh.logs)

        mh.ns["applied"] = 35
        mh.ns["TriggerS6RoomScene"](False, "activate")
        self.assertEqual(s6_preston.state["starts"], 1)
        self.assertIn((s6_preston, "OnBegin"), min00_regs)
        self.assertIn((s6_preston, "OnEnd"), min00_regs)

        mh.ns["TriggerS6RoomScene"](True, "activate")
        self.assertEqual(s6_sturges.state["starts"], 1)
        self.assertIn((s6_sturges, "OnBegin"), min00_regs)
        self.assertIn((s6_sturges, "OnEnd"), min00_regs)

    def test_missing_s6_scene_falls_back_to_40_then_reaches_200_and_starts_sanctuary01(self):
        mh = s2s6._build_min00_harness(
            enable_s4=True,
            enable_s6_s9=True,
            stop_at_core=False,
            s6_preston_scene=None,
            s6_sturges_scene=None,
            basement_gate=s2s6._FakeMarker("FO4Port_MQ03SecurityGateREF", 0.0, 0.0, 0.0),
        )
        s2s6._compile_papyrus(
            MIN00_PSC.read_text(encoding="utf-8"),
            ["ObjectReference.OnActivate"],
            set(),
            mh.ns,
        )
        mh.ns["s5MuseumCleared"] = True
        mh.ns["applied"] = 35
        mh.ns["SetStage"](35)

        mh.ns["ObjectReference_OnActivate"](mh.preston, mh.player)

        self.assertIn("scene missing id=0x000BC9", mh.logs)
        self.assertIn("s6 preston fallback stage=40 reason=no_scene", mh.logs)
        self.assertIn("s6 stage 40 preston_group talk", mh.logs)
        self.assertEqual(mh.ns["s6FullStage"], 40)
        self.assertEqual(mh.ns["applied"], 40)
        self.assertFalse(mh.state["completed"])

        # Complete S6 -> S9 -> 200 -> FO4SF_Sanctuary01 (0x000817)
        self.assertTrue(mh.ns["TryOpenS6BasementGate"]("terminal"))
        self.assertTrue(mh.ns["AdvanceS6FusionCorePicked"]())
        self.assertTrue(mh.ns["CompleteS9LobbyTalkAndReward"](mh.player))
        self.assertTrue(mh.ns["BeginS9MuseumExitAndPatrol"](mh.player))
        self.assertTrue(mh.ns["CheckS9SanctuaryArrival"](mh.player, 181.0))

        self.assertEqual(mh.ns["s6FullStage"], 200)
        self.assertEqual(mh.ns["applied"], 200)
        self.assertIn(200, mh.stages)
        self.assertTrue(mh.state["completed"])
        self.assertTrue(mh.sanctuary.running)
        self.assertEqual(mh.sanctuary.sturges_arrived, 1)
        self.assertIn((1000, "s9_arrival"), mh.sanctuary.advance_calls)
        self.assertIn(1000, mh.sanctuary.stages)


if __name__ == "__main__":
    unittest.main()
