"""Tests for S1 beats/Stage 20/Skip Pre-War preservation, Handy Codsworth bundle, MQ101 filter, dotnet Prewar & Papyrus."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
for sub in ("src", "scripts/prewar", "scripts/newgame"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from fo4sf.planet import esm  # noqa: E402
from fo4sf.prewar import handy_codsworth, mq101_census, s1_spec  # noqa: E402
import build_prewar_quest  # noqa: E402
import make_newgame  # noqa: E402


def _make_synthetic_handy_bundle(bundle_dir: Path) -> None:
    """Create a valid synthetic `--codsworth-handy` bundle matching #854 (`FO4SF_RA2Handy.esm` + `Data/`)."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    data = bundle_dir / "Data"
    (data / "meshes" / "fo4sf" / "actors" / "handy").mkdir(parents=True, exist_ok=True)
    (data / "meshes" / "fo4sf" / "actors" / "handy" / "handy.nif").write_bytes(b"NIF_SYNTH")
    (data / "geometries" / "fo4sf").mkdir(parents=True, exist_ok=True)
    (data / "geometries" / "fo4sf" / "handy.mesh").write_bytes(b"MESH_SYNTH")

    graph = "Actors\\FO4SF\\Handy\\HandyGraph.agx"
    key_hex = f"{handy_codsworth.manifest_key(graph, ['Neutral'])}.txt"
    for d in handy_codsworth.HANDY_MANIFEST_DIRS:
        p = data / "meshes" / "AnimTextData" / d / key_hex
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("synth manifest\n", encoding="utf-8")

    gsd = data / "meshes" / "AnimTextData" / "GeneratedSubgraphData" / "fo4sf_handyrace.txt"
    gsd.parent.mkdir(parents=True, exist_ok=True)
    gsd.write_text("synth gsd\n", encoding="utf-8")

    # Synthetic FO4SF_RA2Handy.esm with BPTD 0x801, ARMA 0x802, ARMO 0x803, RACE 0x800 (matching E2!)
    w = esm.PluginWriter(["Starfield.esm"], esm.ESM)
    w.add(esm.Record(b"BPTD", 0x000801, [(b"EDID", esm.zbytes(handy_codsworth.HANDY_BPTD_EDID))]))
    w.add(esm.Record(b"ARMA", 0x000802, [(b"EDID", esm.zbytes("FO4SF_RA2Handy_AA")), (b"MOD2", esm.zbytes(r"FO4SF\Actors\Handy\handy.nif"))]))
    w.add(esm.Record(b"ARMO", 0x000803, [(b"EDID", esm.zbytes("FO4SF_RA2Handy_Skin")), (b"MODL", struct.pack("<I", 0x000802))]))
    w.add(
        esm.Record(
            b"RACE",
            0x000800,
            [
                (b"EDID", esm.zbytes(handy_codsworth.HANDY_RACE_EDID)),
                (b"GNAM", struct.pack("<I", 0x000801)),
                (b"SGNM", esm.zbytes(graph)),
                (b"SAPT", esm.zbytes("Neutral")),
            ],
        )
    )
    w.write(str(bundle_dir / handy_codsworth.HANDY_TEMPLATE_PLUGIN), compress=False)


class PrewarScenesAndHandyTests(unittest.TestCase):
    def test_standin_beats_and_skip_prewar_preservation(self) -> None:
        self.assertEqual([b.code for b in s1_spec.STANDIN_BEATS], ["a", "b", "c", "d", "e"])
        self.assertTrue(all(b.status_label == "animation stand-in" for b in s1_spec.STANDIN_BEATS))

        # Fixed IDs must stay cleanly below PREWAR_VOICE_START_ID (0x900) and distinct
        fids = [fid for _sig, fid in s1_spec.PREWAR_FORMS.values()]
        self.assertEqual(len(fids), len(set(fids)))
        self.assertTrue(all(0x000800 <= fid < s1_spec.PREWAR_VOICE_START_ID for fid in fids))

        # Verify actual repo start_places.json preserves fo4_vault111 (Skip Pre-War)
        sp_path = ROOT / "src" / "fo4sf" / "core" / "start_places.json"
        sp_doc = json.loads(sp_path.read_text(encoding="utf-8"))
        s1_spec.validate_start_places_preserves_skip_prewar(sp_doc)

        # Verify FO4SF_NewGame STAGE_CONTRACT keeps Stage 20 + Vault 111 / S2 chain intact
        s1_spec.validate_stage20_handoff_contract(make_newgame.STAGE_CONTRACT)

    def test_mq101_fuz_duration_parser_and_tile_spec(self) -> None:
        fmt_payload = struct.pack("<HHIIIHH", 0x0161, 1, 22050, 4000, 1, 16, 0)
        fmt_chunk = b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload
        data_chunk = b"data" + struct.pack("<I", 8000) + (b"\x00" * 8000)
        xwma = b"RIFF" + struct.pack("<I", 4 + len(fmt_chunk) + len(data_chunk)) + b"XWMA" + fmt_chunk + data_chunk
        fuz = b"FUZE" + struct.pack("<II", 1, 4) + b"LIPS" + xwma
        self.assertEqual(mq101_census.split_fuz_xwma(fuz), xwma)
        self.assertAlmostEqual(mq101_census.parse_fuz_duration_s(fuz), 2.0, places=5)

        spec = build_prewar_quest.build_tile_local_spec()
        self.assertIn("FO4SF_PrewarHouseSpawnMarker", spec["markers"])
        self.assertIn("FO4SF_PrewarVaultArrivalMarker", spec["markers"])
        self.assertIn("FO4SF_PrewarCrowdBridgeMarkRef", spec["markers"])
        pod_coords = {
            tuple(spec["markers"][k][:2])
            for k in (
                "FO4SF_PrewarPlayerPodMarkRef",
                "FO4SF_PrewarSpousePodMarkRef",
                "FO4SF_PrewarKelloggMarkRef",
                "FO4SF_PrewarInstMalePodMarkRef",
                "FO4SF_PrewarInstFemalePodMarkRef",
            )
        }
        self.assertEqual(len(pod_coords), 5)
        hx, hy, _hz, _hr = spec["markers"]["FO4SF_PrewarHouseSpawnMarker"]
        self.assertTrue(-200.0 <= hx < 200.0 and -200.0 <= hy < 200.0)

    def test_synthetic_handy_bundle_inspect_and_no_overwrite_copy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = root / "E2_synth"
            _make_synthetic_handy_bundle(bundle)
            dest = root / "OutData"

            spec, copied = handy_codsworth.copy_handy_assets(str(bundle), str(dest))
            self.assertEqual(spec.subgraph_count, 1)
            self.assertTrue((dest / "meshes" / "fo4sf" / "actors" / "handy" / "handy.nif").is_file())
            self.assertTrue(
                (dest / "meshes" / "AnimTextData" / "GeneratedSubgraphData" / "fo4sf_prewarcodsworthrace.txt").is_file()
            )
            self.assertGreaterEqual(len(copied), 7)

            with self.assertRaises(FileExistsError):
                handy_codsworth.copy_handy_assets(str(bundle), str(dest))

    def test_dotnet_prewar_selftest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            proj = ROOT / "dotnet" / "Prewar" / "Prewar.csproj"
            res = subprocess.run(
                ["dotnet", "run", "--project", str(proj), "-c", "Release", "--", "selftest", td],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, res.stdout + "\n" + res.stderr)
            self.assertIn("selftest ok", res.stdout)

    def test_optional_live_e2_handy_inspect_and_papyrus_compile(self) -> None:
        e2_dir = Path(r"D:\FO4SF-Owner-Tests\robot-anim\E2")
        if e2_dir.is_dir():
            spec = handy_codsworth.inspect_handy_bundle(str(e2_dir))
            self.assertGreaterEqual(spec.subgraph_count, 1)
            self.assertIn("meshes/fo4sf/actors/handy/handy.nif", {v.lower() for v in spec.files_to_copy.values()})

        compiler = Path(build_prewar_quest.DEFAULT_PAPYRUS_COMPILER)
        res_zip = Path(build_prewar_quest.DEFAULT_CONTENT_RES)
        if compiler.is_file() and res_zip.is_file():
            with tempfile.TemporaryDirectory() as td:
                pex_list = build_prewar_quest.compile_prewar_scripts(td)
                self.assertEqual(len(pex_list), 2)
                for pex in pex_list:
                    self.assertTrue(os.path.isfile(pex), f"Missing compiled {pex}")

    def test_prewar_quest_progression_and_reload_rearm(self) -> None:
        """Offline Papyrus simulation of FO4SF_PrewarQuest 10 -> 20 -> 30 -> 40 -> 50 -> 60/200 and OnPlayerLoadGame re-arm."""
        psc = (ROOT / "scripts" / "prewar" / "FO4SF_PrewarQuest.psc").read_text(encoding="utf-8")
        # Wrap remote/event blocks as callable Functions
        wrapped = re.sub(
            r"Event Actor\.OnPlayerLoadGame\(([^)]*)\)",
            r"Function OnPlayerLoadGameEvent(\1)",
            psc,
        )
        wrapped = re.sub(r"Event OnTimer\(([^)]*)\)", r"Function OnTimerEvent(\1)", wrapped)
        wrapped = wrapped.replace("EndEvent", "EndFunction")

        names = (
            "EnsurePrewarLoadHook",
            "BeginPrewarSanctuary",
            "StartEvacuationSequence",
            "StartElevatorAndNukeBeat",
            "MoveIntoPrewarVaultConfirmed",
            "StartKelloggPodBeat",
            "StepPrewarProgression",
            "HandoffToVault111CryoStage20",
            "OnPlayerLoadGameEvent",
            "OnTimerEvent",
        )
        state_vars = (
            "LogName",
            "enteredPrewarVault",
            "vaultEntryTries",
            "handoffDone",
            "kelloggElapsedS",
            "loadHookRegistered",
            "evacStarted",
            "elevatorStarted",
            "kelloggStarted",
            "exteriorElapsedS",
            "vaultElapsedS",
        )
        py_chunks = []
        type_pat = r"\b(?:bool|int|float|string|Actor|ObjectReference|Quest|Cell|ScriptObject|GlobalVariable|Var)\b"
        fn_set = set(names)
        for fn_name in names:
            m = re.search(rf"(?:[A-Za-z]+\s+)?Function\s+{fn_name}\(([^)]*)\)\n(.*?)\nEndFunction", wrapped, re.S)
            self.assertIsNotNone(m, f"Missing Function {fn_name} in FO4SF_PrewarQuest.psc")
            params_raw = m.group(1).strip()
            params = [p.strip().split()[-1] for p in params_raw.split(",") if p.strip()] if params_raw else []
            out = [f"def {fn_name}({', '.join(params)}):", f"    global {', '.join(state_vars)}"]
            indent = 1
            in_doc = False
            for raw in m.group(2).splitlines():
                line = raw.strip()
                if in_doc:
                    if "}" in line:
                        in_doc = False
                    continue
                if line.startswith("{"):
                    if "}" not in line:
                        in_doc = True
                    continue
                line = line.split(";", 1)[0].strip()
                if not line:
                    continue
                if line in ("endif", "endwhile"):
                    indent -= 1
                    continue
                if line.startswith(("elseif ", "else")):
                    indent -= 1
                line = re.sub(r"\belseif\b", "elif", line)
                line = re.sub(r"\btrue\b", "True", line, flags=re.I)
                line = re.sub(r"\bfalse\b", "False", line, flags=re.I)
                line = re.sub(r"\bNone\b", "None", line)
                line = line.replace("&&", " and ").replace("||", " or ")
                line = re.sub(r"!([^=])", r"not \1", line)
                line = line.replace("Var[] args = new Var[1]", "args = [None]")
                # Strip type declarations in local variable declarations
                if not line.startswith(("if ", "elif ", "else:")):
                    line = re.sub(rf"^\s*{type_pat}\s+([A-Za-z_]\w*)\s*=", r"\1 =", line)
                line = re.sub(r"\s+as\s+[A-Za-z_]\w*\b", "", line)
                # Quoted + concat with ints/floats
                if line.startswith("Trace("):
                    line = "Trace('trace')"
                if re.match(r"^(if |elif |else$|while )", line):
                    line = (line + ":") if not line.endswith(":") else line
                out.append(("    " * indent) + line)
                if re.match(r"^(if |elif |else:|while )", line):
                    indent += 1
            py_chunks.append("\n".join(out))

        code = compile("\n\n".join(py_chunks), "FO4SF_PrewarQuest.psc", "exec")

        def make_harness(scene_playing: bool = False):
            timers: list[tuple[float, int]] = []
            calls: list[str] = []
            cur_stage = [0]
            in_cell = ["FO4SF_PrewarSanctuaryWorldCell"]
            player_pos = [52.82, -2.46]
            house_pos = (52.82, -2.46)
            gate_pos = (-60.0, 0.0)
            lift_pos = (-77.62, -3.81)
            pod_pos = (-95.0, -5.0)
            prewar_active = [0.0]

            def dist(ax, ay, bx, by):
                return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

            house_ref = SimpleNamespace(
                pos=house_pos,
                GetDistance=lambda o: dist(house_pos[0], house_pos[1], o.pos[0], o.pos[1]),
            )
            soldier_ref = SimpleNamespace(
                pos=gate_pos,
                EnableNoWait=lambda: calls.append("EnableSoldier"),
                GetDistance=lambda o: dist(gate_pos[0], gate_pos[1], o.pos[0], o.pos[1]),
            )
            lift_ref = SimpleNamespace(pos=lift_pos)
            pod_ref = SimpleNamespace(pos=pod_pos)
            arrival_ref = SimpleNamespace(GetParentCell=lambda: "FO4Port_PrewarVault111S1")

            def _player_dist(target):
                tx, ty = target.pos
                return dist(player_pos[0], player_pos[1], tx, ty)

            player = SimpleNamespace(
                pos=player_pos,
                MoveTo=lambda *a: calls.append("MoveTo"),
                GetParentCell=lambda: in_cell[0],
                GetDistance=_player_dist,
            )

            def _on_move_to(target, *a):
                calls.append("MoveTo")
                if target is arrival_ref:
                    in_cell[0] = "FO4Port_PrewarVault111S1"

            player.MoveTo = _on_move_to

            ng_script = SimpleNamespace(
                CallFunction=lambda fn, args: calls.append(f"NG.{fn}")
            )
            ng_quest = SimpleNamespace(
                CastAs=lambda cls: ng_script,
                SetStage=lambda n: calls.append(f"NG.SetStage({n})"),
            )
            stand_ins = SimpleNamespace(
                ExtElevatorPlatform=lift_ref,
                PlayerPodHoldMarker=pod_ref,
                KelloggSequenceScene=SimpleNamespace(IsPlaying=lambda: scene_playing),
                StartCrowdBeat=lambda: calls.append("StartCrowdBeat"),
                StartVertibirdBeat=lambda: calls.append("StartVertibirdBeat"),
                StartElevatorDescentWithNuke=lambda: calls.append("StartElevatorDescentWithNuke"),
                StartKelloggPodSequence=lambda: calls.append("StartKelloggPodSequence"),
                FireKelloggGunshotAndRefreeze=lambda: calls.append("FireKelloggGunshotAndRefreeze"),
            )
            ns = dict(
                LogName="fo4sf_prewar",
                enteredPrewarVault=False,
                vaultEntryTries=0,
                handoffDone=False,
                kelloggElapsedS=0.0,
                loadHookRegistered=False,
                evacStarted=False,
                elevatorStarted=False,
                kelloggStarted=False,
                exteriorElapsedS=0.0,
                vaultElapsedS=0.0,
                HouseSpawnMarker=house_ref,
                PrewarVaultArrivalMarker=arrival_ref,
                CodsworthActor=SimpleNamespace(EnableNoWait=lambda: calls.append("EnableCodsworth")),
                SpouseActor=SimpleNamespace(EnableNoWait=lambda: calls.append("EnableSpouse")),
                VaultTecRepActor=SimpleNamespace(EnableNoWait=lambda: calls.append("EnableRep")),
                SoldierCheckerActor=soldier_ref,
                VaultDoctorActor=SimpleNamespace(EnableNoWait=lambda: calls.append("EnableDoc")),
                StandIns=stand_ins,
                NewGameQuest=ng_quest,
                NewGameQuestId=0x800,
                NewGamePlugin="FO4SFNewGame.esm",
                Stage20LooksDone=20,
                KelloggSceneTimeoutS=6.0,
                PrewarActiveGlobal=SimpleNamespace(SetValue=lambda v: prewar_active.__setitem__(0, v)),
                Game=SimpleNamespace(
                    GetPlayer=lambda: player,
                    FadeOutGame=lambda *a: None,
                    GetFormFromFile=lambda *a: None,
                ),
                Debug=SimpleNamespace(OpenUserLog=lambda n: calls.append("OpenUserLog")),
                RegisterForRemoteEvent=lambda src, ev: calls.append(f"Reg:{ev}"),
                StartTimer=lambda s, tid: timers.append((s, tid)),
                SetStage=lambda n: cur_stage.__setitem__(0, n),
                GetStage=lambda: cur_stage[0],
                CompleteQuest=lambda: calls.append("CompleteQuest"),
                Trace=lambda msg: None,
            )
            exec(code, ns)
            return ns, player, player_pos, timers, calls, cur_stage, prewar_active

        # Case A: distance-driven progression 10 -> 20 -> 30 -> 40 -> 50 -> 60/200
        ns, player, pos, timers, calls, stage, pw_glob = make_harness(scene_playing=False)
        ns["BeginPrewarSanctuary"]()
        self.assertEqual(stage[0], 10)
        self.assertEqual(pw_glob[0], 1.0)
        self.assertIn("Reg:OnPlayerLoadGame", calls)
        self.assertEqual(timers[-1], (2.0, 22))

        pos[:] = [70.0, -2.46]  # >12m from HouseSpawnMarker -> 10 -> 20
        timers.clear()
        ns["OnTimerEvent"](22)
        self.assertEqual(stage[0], 20)
        self.assertEqual(calls.count("StartCrowdBeat"), 1)
        self.assertEqual(calls.count("StartVertibirdBeat"), 1)
        self.assertEqual(timers[-1], (2.0, 22))

        pos[:] = [-72.0, -3.0]  # within 18m of ExtElevatorPlatform -> 20 -> 30
        timers.clear()
        ns["OnTimerEvent"](22)
        self.assertEqual(stage[0], 30)
        self.assertEqual(calls.count("StartElevatorDescentWithNuke"), 1)
        self.assertIn((7.5, 20), timers)
        self.assertIn((2.0, 22), timers)

        # Reload during stage 30 before arrival re-arms BOTH timer 22 and timer 20
        timers.clear()
        ns["OnPlayerLoadGameEvent"](player)
        self.assertIn((2.0, 22), timers)
        self.assertIn((0.5, 20), timers)

        # Timer 20 confirms cell arrival -> stage 40
        timers.clear()
        ns["OnTimerEvent"](20)
        self.assertEqual(stage[0], 40)
        self.assertIn((2.0, 22), timers)

        # Reload at stage 40 re-arms timer 22
        timers.clear()
        ns["OnPlayerLoadGameEvent"](player)
        self.assertEqual(timers, [(2.0, 22)])

        # Approach PlayerPodHoldMarker -> stage 50
        pos[:] = [-93.0, -5.0]
        timers.clear()
        ns["OnTimerEvent"](22)
        self.assertEqual(stage[0], 50)
        self.assertEqual(calls.count("StartKelloggPodSequence"), 1)
        self.assertEqual(timers, [(2.0, 21)])

        # Reload at stage 50 re-arms timer 21
        timers.clear()
        ns["OnPlayerLoadGameEvent"](player)
        self.assertEqual(timers, [(2.0, 21)])

        # Timer 21 completes handoff -> stage 60/200 and FO4SF_NewGame.CompletePrewarHandoffStage20
        timers.clear()
        ns["OnTimerEvent"](21)
        self.assertEqual(stage[0], 200)
        self.assertEqual(pw_glob[0], 0.0)
        self.assertIn("NG.CompletePrewarHandoffStage20", calls)
        self.assertIn("CompleteQuest", calls)

        # Reload after handoffDone must NOT re-arm timers
        timers.clear()
        ns["OnPlayerLoadGameEvent"](player)
        self.assertEqual(timers, [])

        # Case B: elapsed-timer fallback if player stands still
        ns_idle, _p, _pos, _t, _c, stage_idle, _pw = make_harness(scene_playing=False)
        ns_idle["BeginPrewarSanctuary"]()
        for _ in range(4):
            ns_idle["OnTimerEvent"](22)
        self.assertEqual(stage_idle[0], 20)
        for _ in range(8):
            ns_idle["OnTimerEvent"](22)
        self.assertEqual(stage_idle[0], 30)
        ns_idle["OnTimerEvent"](20)
        self.assertEqual(stage_idle[0], 40)
        for _ in range(3):
            ns_idle["OnTimerEvent"](22)
        self.assertEqual(stage_idle[0], 50)

    def test_mq101_localized_ilstrings_lookup(self) -> None:
        """Localized INFO.NAM1 4-byte StringIDs must resolve from ILSTRINGS, never emit raw binary bytes."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            strings_dir = root / "Strings"
            strings_dir.mkdir(parents=True, exist_ok=True)
            # Minimal ILSTRINGS table mapping 0x00012345 -> "Time to wake up."
            sid_hit = 0x00012345
            text_bytes = b"Time to wake up.\x00"
            data_blob = struct.pack("<I", len(text_bytes)) + text_bytes
            il_bytes = struct.pack("<II", 1, len(data_blob)) + struct.pack("<II", sid_hit, 0) + data_blob
            (strings_dir / "Fallout4_en.ILSTRINGS").write_bytes(il_bytes)

            # Build localized TES4 plugin containing QUST 0x000CF918 -> GRUP -> INFO 0x000CF920 (hit) & 0x000CF921 (miss)
            info_hit = esm.Record(b"INFO", 0x000CF920, [(b"NAM1", struct.pack("<I", sid_hit))]).to_bytes(compress=False)
            info_miss = esm.Record(b"INFO", 0x000CF921, [(b"NAM1", struct.pack("<I", 0x00099999))]).to_bytes(compress=False)
            # Child GRUP type 1 (Quest children) labeled with parent QUST FormID
            qust_rec = esm.Record(b"QUST", s1_spec.MQ101_KELLOGG_QUEST_FID, [(b"EDID", esm.zbytes("MQ101KelloggSequence"))]).to_bytes(compress=False)
            quest_child_grup = esm.group_bytes(struct.pack("<I", s1_spec.MQ101_KELLOGG_QUEST_FID), info_hit + info_miss, gtype=1)
            top_qust = esm.group_bytes(b"QUST", qust_rec + quest_child_grup, gtype=0)
            tes4_hdr = esm.Record(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 0.95, 2, 0x800))], flags=0x81).to_bytes(compress=False)
            fo4_path = root / "Fallout4.esm"
            fo4_path.write_bytes(tes4_hdr + top_qust)

            wem_dir = root / "wem_src"
            wem_dir.mkdir(parents=True, exist_ok=True)
            wem_hit = wem_dir / "hit.wem"
            wem_miss = wem_dir / "miss.wem"
            wem_hit.write_bytes(b"WEM")
            wem_miss.write_bytes(b"WEM")
            stem_to_wem = {
                "npcmkellogg/000cf920_1": str(wem_hit),
                "npcmkellogg/000cf921_1": str(wem_miss),
            }
            rows, copied = mq101_census.build_local_kellogg_voices_payload(
                str(fo4_path),
                {"npcmkellogg/000cf920_1": 1.8, "npcmkellogg/000cf921_1": 1.5},
                str(root / "voice_out"),
                stem_to_wem,
            )
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(copied), 2)
            self.assertEqual(rows[0][1], "Time to wake up.")
            self.assertEqual(rows[1][1], "Line 00099999")
            self.assertTrue(all(r[1].isprintable() for r in rows))


if __name__ == "__main__":
    unittest.main()
