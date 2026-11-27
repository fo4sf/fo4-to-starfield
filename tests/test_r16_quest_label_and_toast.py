"""Round 16 (2h-4 / #853) tests:
1. Interface/Translate_en.txt is packed inside candidate's Main.ba2 archive (not loose sfse_sidecar)
   with "MISSION STATUS" -> "QUEST STATUS" and G12(d) "Quest", "Quests", "Quest Log" keys.
2. Real-BA2 offline proof: build a real .ba2 archive, open it with fo4sf.ba2.Ba2, read back
   interface/translate_en.txt, verify all required keys, and (when MSVC cl.exe is present) verify
   sfse/FO4SFPipboyMenu/src/hud_quest_label.h VerifyTranslateEnFile reads it directly from Main.ba2.
3. check-bundle (check_beginning_pilot.py) FAILS when quest-label mode is quest and Translate_en.txt
   is missing from bundle archive inputs (or only in sfse_sidecar), and PASSES when staged in Data/.
4. Landing "Out of Time" quest-complete toast spam eliminated:
   - stage 40 -> 200 -> Codsworth01 start under single_quest has <= 1 HUD-visible "Out of Time" quest event
     (ZERO quest-complete toast at landing, ONE objective-complete toast for vault exit, ONE "Go home"
     new-objective toast under Codsworth01).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
for _p in (
    str(TESTS_DIR),
    str(REPO / "src"),
    str(REPO / "scripts"),
    str(REPO / "scripts" / "core"),
    str(REPO / "scripts" / "game"),
    str(REPO / "scripts" / "ui"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ba2_fixture  # noqa: E402
from fo4sf import ba2  # noqa: E402
from fo4sf.beginning_pilot import verify_bundle_beginning_readiness  # noqa: E402
import exp_install  # noqa: E402
import make_core_bundle  # noqa: E402
import make_pipboy_stage_ini  # noqa: E402
import make_probe_swf  # noqa: E402
import make_quest_translate  # noqa: E402
import test_core_bundle  # noqa: E402
import verify_packed_experiment  # noqa: E402
from tests.test_exit_arrival import translated_functions  # noqa: E402
from tests.test_fo4_beginning_pilot import BeginningPilotTests  # noqa: E402
from tests.test_r15_toasts_and_label import MakeQuestTranslateTests, _build_codsworth_harness  # noqa: E402

REAL_STARFIELD_DIR = Path(r"D:\SteamLibrary\steamapps\common\Starfield")
REAL_ARCHIVE2 = REAL_STARFIELD_DIR / "Tools" / "Archive2" / "Archive2.exe"
REAL_INTERFACE_BA2 = REAL_STARFIELD_DIR / "Data" / "Starfield - Interface.ba2"
MSVC_ENV_PS1 = Path(r"D:\Modding\tools\msvc_env.ps1")
HUD_HEADER = REPO / "sfse" / "FO4SFPipboyMenu" / "src" / "hud_quest_label.h"
NEWGAME_PSC = REPO / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc"
CODS_PSC = REPO / "scripts" / "mission" / "FO4SF_Codsworth01Quest.psc"


class ArchiveTranslatePackingAndGuardTests(unittest.TestCase):
    def _build_synthetic_bundle_with_pipboy(self, root: Path, sf_dir: Path) -> tuple[Path, Path, Path]:
        owner, stages_root, port_esm, _ = test_core_bundle.CoreBundleTests()._build_synthetic_owner_and_stages(root)

        src_pb = root / "src_pb"
        (src_pb / "Data" / "Interface").mkdir(parents=True)
        (src_pb / "SFSE" / "Plugins").mkdir(parents=True)
        p1_sha = test_core_bundle._make_tes4_esm(src_pb / "FO4SFPipboyProbe.esm", extra_tag=b"pbprobe")
        shell_swf = make_probe_swf.movie_bytes()
        (src_pb / "Data" / "Interface" / "FO4SF_Fo4Shell.swf").write_bytes(shell_swf)
        (src_pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").write_bytes(b"MZ_SYNTHETIC_PIPBOY_DLL")
        (src_pb / "plan.json").write_text(
            json.dumps(
                {
                    "kind": "pipboy-stack-stage",
                    "plugins": ["FO4SFPipboyProbe.esm"],
                    "files": {
                        "FO4SFPipboyProbe.esm": {"sha256": p1_sha},
                        "Data/Interface/FO4SF_Fo4Shell.swf": {"sha256": test_core_bundle._sha256_bytes(shell_swf)},
                    },
                }
            ),
            encoding="utf-8",
        )

        refreshed = root / "16-pipboy-refreshed"
        make_core_bundle.refresh_pipboy_stage_for_bundle(
            str(src_pb),
            str(refreshed),
            str(root / "no-fo4-data"),
            sf_data_dir=str(sf_dir / "Data"),
        )
        out_b = root / "bundle-2h4"
        rc = make_core_bundle.main(
            [
                "fold",
                "--owner-set", str(owner),
                "--stages-root", str(stages_root),
                "--out", str(out_b),
                "--port", str(port_esm),
                "--starfield-dir", str(sf_dir),
                "--with-pipboy",
                "--pipboy-stage", str(refreshed),
            ],
            system=test_core_bundle._FakeSystemClosed(),
        )
        self.assertEqual(rc, 0)
        return out_b, port_esm, refreshed

    def test_fold_stages_translate_en_in_data_for_ba2_and_not_loose_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sf_dir = root / "FakeSf"
            (sf_dir / "Data").mkdir(parents=True)
            raw = b"\xff\xfe" + "\r\n".join(MakeQuestTranslateTests.SAMPLE_LINES).encode("utf-16-le")
            (sf_dir / "Data" / "Starfield - Interface.ba2").write_bytes(
                ba2_fixture.general_archive({"interface\\translate_en.txt": raw}, compressed=True, version=2)
            )
            out_b, _port, _refreshed = self._build_synthetic_bundle_with_pipboy(root, sf_dir)

            # Must be in Data/Interface/Translate_en.txt (archive input) and NOT in sfse_sidecar/
            self.assertTrue((out_b / "Data" / "Interface" / "Translate_en.txt").is_file())
            self.assertFalse((out_b / "sfse_sidecar" / "Interface" / "Translate_en.txt").exists())

            bplan = json.loads((out_b / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertIn("Data/Interface/Translate_en.txt", bplan["components"]["pipboy"]["outputs"])
            self.assertNotIn("Interface/Translate_en.txt", bplan["sfse_sidecar"])

            # Verify exp_install.source_inventory picks up Data/Interface/Translate_en.txt for Main.ba2 packing
            inv = exp_install.source_inventory(str(out_b), bplan["plugins"])
            self.assertIn("Data/Interface/Translate_en.txt", inv)

    def test_real_ba2_archive_contains_quest_status_and_g12d_menu_words(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sf_dir = root / "StarfieldMock"
            (sf_dir / "Data").mkdir(parents=True)
            if REAL_INTERFACE_BA2.is_file():
                # Read real vanilla Starfield - Interface.ba2 (read-only) to generate full Translate_en.txt
                qt_stage = root / "qt_stage"
                make_quest_translate.generate_quest_translate(
                    REAL_INTERFACE_BA2.parent, qt_stage, mode="quest", label="QUEST"
                )
                translate_bytes = (qt_stage / "Data" / "Interface" / "Translate_en.txt").read_bytes()
            else:
                raw = b"\xff\xfe" + "\r\n".join(MakeQuestTranslateTests.SAMPLE_LINES).encode("utf-16-le")
                (sf_dir / "Data" / "Starfield - Interface.ba2").write_bytes(
                    ba2_fixture.general_archive({"interface\\translate_en.txt": raw}, compressed=True, version=2)
                )
                qt_stage = root / "qt_stage"
                make_quest_translate.generate_quest_translate(
                    sf_dir / "Data", qt_stage, mode="quest", label="QUEST"
                )
                translate_bytes = (qt_stage / "Data" / "Interface" / "Translate_en.txt").read_bytes()

            # Stage Data/ tree and pack a real FO4ActorRaider - Main.ba2 (with Archive2.exe if available, and via ba2_fixture)
            exp_dir = root / "exp_stage"
            (exp_dir / "Data" / "Interface").mkdir(parents=True)
            (exp_dir / "Data" / "Interface" / "Translate_en.txt").write_bytes(translate_bytes)
            (exp_dir / "Data" / "Interface" / "FO4SF_Fo4Shell.swf").write_bytes(make_probe_swf.movie_bytes())
            (exp_dir / "FO4ActorRaider.esm").write_bytes(b"TES4\x00\x00\x00\x00")

            inputs = exp_install.source_inventory(str(exp_dir), ["FO4ActorRaider.esm"])
            main_ba2_path = root / "FO4ActorRaider - Main.ba2"
            if REAL_ARCHIVE2.is_file():
                r = subprocess.run(
                    [
                        str(REAL_ARCHIVE2),
                        "Interface",
                        f"-create={main_ba2_path}",
                        f"-root={exp_dir / 'Data'}",
                        "-format=General",
                        "-compression=None",
                    ],
                    cwd=str(exp_dir / "Data"),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(r.returncode, 0, r.stdout + "\n" + r.stderr)
            else:
                entries = {
                    rel[5:].replace("/", "\\"): (exp_dir / "Data" / Path(*rel[5:].split("/"))).read_bytes()
                    for rel in inputs
                    if rel.startswith("Data/")
                }
                main_ba2_path.write_bytes(ba2_fixture.general_archive(entries, compressed=False, version=2))

            # Verify archive structurally against exp_install's verifier, then open with fo4sf.ba2.Ba2
            verify_packed_experiment.verify_archive(str(main_ba2_path), inputs)
            arch = ba2.Ba2(str(main_ba2_path))
            self.assertIsNotNone(arch.find("interface/translate_en.txt"))
            read_back = arch.read("interface/translate_en.txt")
            self.assertTrue(read_back.startswith(b"\xff\xfe"))
            kv = dict(
                ln.split("\t", 1)
                for ln in read_back[2:].decode("utf-16-le").splitlines()
                if "\t" in ln
            )
            self.assertEqual(kv.get("$MISSION STATUS"), "QUEST STATUS")
            self.assertEqual(kv.get("$MissionNew"), "NEW QUEST")
            # G12(d) menu words: "Quest", "Quests", "Quest Log"
            self.assertEqual(kv.get("$Quest"), "Quest")
            self.assertEqual(kv.get("$QUESTS"), "QUESTS")
            self.assertEqual(kv.get("$MISSIONS"), "QUESTS")
            self.assertEqual(kv.get("$MissionMenu"), "QUEST LOG")
            self.assertEqual(kv.get("$MissionAdded"), "ADDED TO QUEST LOG")

            # If MSVC host compiler is available, verify hud_quest_label.h reads FO4ActorRaider - Main.ba2 directly
            if MSVC_ENV_PS1.is_file():
                cpp_test_dir = root / "cpp_host"
                cpp_test_dir.mkdir()
                (cpp_test_dir / "Data").mkdir()
                shutil.copy2(main_ba2_path, cpp_test_dir / "Data" / "FO4ActorRaider - Main.ba2")
                cpp_src = cpp_test_dir / "test_ba2_label.cpp"
                cpp_src.write_text(
                    '#include <cassert>\n'
                    '#include <iostream>\n'
                    f'#include "{HUD_HEADER.as_posix()}"\n'
                    'int main(int argc, char** argv) {\n'
                    '    fo4sf::hud::QuestLabelConfig cfg;\n'
                    '    auto st = fo4sf::hud::VerifyTranslateEnFile(argv[1], cfg);\n'
                    '    std::cout << fo4sf::hud::FormatStartupLog(cfg, st) << " keys=" << st.keysMatched << "\\n";\n'
                    '    assert(st.filePresent);\n'
                    '    assert(st.fileOk);\n'
                    '    assert(st.keysMatched == fo4sf::hud::kTranslateTargetKeyCount);\n'
                    '    return 0;\n'
                    '}\n',
                    encoding="utf-8",
                )
                exe_path = cpp_test_dir / "test_ba2_label.exe"
                ps_script = cpp_test_dir / "run_cpp_test.ps1"
                ps_script.write_text(
                    f'. "{MSVC_ENV_PS1}"\n'
                    f'& cl.exe /nologo /std:c++20 /EHsc "{cpp_src}" /Fe:"{exe_path}"\n'
                    f'if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}\n'
                    f'& "{exe_path}" "{cpp_test_dir / "Data"}"\n'
                    f'exit $LASTEXITCODE\n',
                    encoding="utf-8",
                )
                rc_cpp = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_script)],
                    cwd=str(cpp_test_dir),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(rc_cpp.returncode, 0, rc_cpp.stdout + "\n" + rc_cpp.stderr)
                self.assertIn("step=hud_quest_label mode=quest label=QUEST active=1 file=present file_ok=1 keys=20", rc_cpp.stdout)

    def test_check_bundle_fails_when_quest_mode_lacks_archive_translate_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = BeginningPilotTests()._build_synthetic_bundle(root)
            bplan = json.loads((bundle / "bundle_plan.json").read_text(encoding="utf-8"))
            bplan["hud_label"] = {"mode": "quest", "label": "QUEST"}
            bplan["components"]["pipboy"] = {"plugins": [], "outputs": {"Data/Interface/FO4SF_Fo4Shell.swf": "ee"}}
            (bundle / "bundle_plan.json").write_text(json.dumps(bplan), encoding="utf-8")

            # 1. Missing Data/Interface/Translate_en.txt under mode=quest MUST fail check-bundle
            cli_fail = subprocess.run(
                [sys.executable, str(REPO / "scripts" / "testing" / "check_beginning_pilot.py"), "check-bundle", "--bundle-dir", str(bundle)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(cli_fail.returncode, 1, cli_fail.stdout + cli_fail.stderr)
            self.assertIn("FAIL  quest_translate", cli_fail.stdout)

            # 2. Loose-only in sfse_sidecar/Interface/Translate_en.txt MUST also fail check-bundle
            (bundle / "sfse_sidecar" / "Interface").mkdir(parents=True, exist_ok=True)
            (bundle / "sfse_sidecar" / "Interface" / "Translate_en.txt").write_bytes(b"\xff\xfe")
            res_loose = verify_bundle_beginning_readiness(str(bundle), require_quest_translate=True)
            self.assertFalse(res_loose["ok"])
            self.assertEqual(res_loose["quest_translate"]["status"], "FAIL")
            shutil.rmtree(bundle / "sfse_sidecar")

            # 3. Staging valid Translate_en.txt in Data/Interface/ without listing in components outputs fails
            sf_data = root / "FakeSfData"
            sf_data.mkdir()
            raw = b"\xff\xfe" + "\r\n".join(MakeQuestTranslateTests.SAMPLE_LINES).encode("utf-16-le")
            (sf_data / "Starfield - Interface.ba2").write_bytes(
                ba2_fixture.general_archive({"interface\\translate_en.txt": raw}, compressed=True, version=2)
            )
            make_quest_translate.generate_quest_translate(sf_data, bundle, mode="quest", label="QUEST")
            res_unlisted = verify_bundle_beginning_readiness(str(bundle), require_quest_translate=True)
            self.assertFalse(res_unlisted["ok"])
            self.assertEqual(res_unlisted["quest_translate"]["status"], "FAIL")

            # 4. Recording Data/Interface/Translate_en.txt in pipboy component outputs makes check-bundle PASS
            import hashlib
            t_sha = hashlib.sha256((bundle / "Data" / "Interface" / "Translate_en.txt").read_bytes()).hexdigest()
            bplan["components"]["pipboy"]["outputs"]["Data/Interface/Translate_en.txt"] = t_sha
            (bundle / "bundle_plan.json").write_text(json.dumps(bplan), encoding="utf-8")
            cli_pass = subprocess.run(
                [sys.executable, str(REPO / "scripts" / "testing" / "check_beginning_pilot.py"), "check-bundle", "--bundle-dir", str(bundle)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(cli_pass.returncode, 0, cli_pass.stdout + cli_pass.stderr)
            self.assertIn("PASS  quest_translate", cli_pass.stdout)


class LandingOutOfTimeToastTests(unittest.TestCase):
    def test_at_most_one_out_of_time_quest_event_between_stage40_and_codsworth01_start(self) -> None:
        ng_psc = NEWGAME_PSC.read_text(encoding="utf-8")
        cw = _build_codsworth_harness(mute_duplicates=True, landing_handoff="single_quest")
        ng_logs = []
        ng_complete_calls = []
        ng_obj_completed = []
        ng_obj_displayed = []
        ng_active_calls = []

        quest_map = {
            (0x000800, "FO4SFMission.esm"): SimpleNamespace(IsRunning=lambda: False, StartNoWait=lambda: True),
            (0x000814, "FO4SFMission.esm"): SimpleNamespace(IsRunning=lambda: False, StartNoWait=lambda: True),
            (0x000816, "FO4SFMission.esm"): SimpleNamespace(
                IsRunning=lambda: False,
                StartNoWait=lambda: (cw.ns["StartQuestInstance"](), True)[1],
            ),
        }
        ng_ns = {
            "Trace": lambda m: ng_logs.append(str(m)),
            "LandingHandoff": "single_quest",
            "h00SkipQuests": False,
            "GameModeGlobal": SimpleNamespace(GetValue=lambda: 1.0),
            "applied": 20,
            "GetStage": lambda: 200,
            "GetStageDone": lambda s: int(s) in (40, 200),
            "CompleteQuest": lambda: ng_complete_calls.append("NewGame:OutOfTime"),
            "ClearVaultSaveLock": lambda: None,
            "ReleaseStoryLandingFade": lambda: None,
            "SetObjectiveDisplayed": lambda o, d=True: ng_obj_displayed.append((int(o), bool(d))),
            "SetObjectiveCompleted": lambda o: ng_obj_completed.append(int(o)),
            "SetActive": lambda a=True: ng_active_calls.append(bool(a)),
            "RunPodExitHook": lambda *_a: None,
            "TriggerVaultPodRecoveryAutosave": lambda *_a: None,
            "Game": SimpleNamespace(
                GetPlayer=lambda: None,
                GetFormFromFile=lambda fid, plg: quest_map.get((int(fid), str(plg))),
            ),
        }
        ng_code = translated_functions(ng_psc, ("ApplyStage", "StartOptionalMissionQuest", "StartLandingQuests"), "applied")
        exec(compile(ng_code, "FO4SF_NewGameQuest.psc", "exec"), ng_ns)

        ng_ns["ApplyStage"](40, "Trigger")
        ng_ns["ApplyStage"](200, "Trigger")

        # Stage 40 fires ONE objective-complete toast for Leave Vault 111
        self.assertEqual(ng_obj_completed, [10])
        # Stage 200 fires ZERO quest-complete toast at landing
        self.assertEqual(ng_complete_calls, [])
        self.assertIn((10, False), ng_obj_displayed)
        self.assertIn(False, ng_active_calls)
        # Codsworth01 shows ONE new-objective toast ("Go home")
        self.assertEqual(cw.obj_calls, [(10, True, False)])
        # At most ONE HUD-visible "Out of Time" quest-level event between stage 40 and Codsworth01 start
        hud_quest_events = len(ng_complete_calls) + len(cw.obj_calls)
        self.assertLessEqual(hud_quest_events, 1)
        self.assertEqual(hud_quest_events, 1)
        self.assertIn("landing handoff mode=single_quest newgame_completed=False codsworth01_displayed=True", ng_logs)


if __name__ == "__main__":
    unittest.main()
