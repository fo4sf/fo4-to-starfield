"""Unit tests for scripts/core/make_core_bundle.py and src/fo4sf/core/bundle_log.py."""
from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (
    str(REPO / "src"),
    str(REPO / "scripts" / "core"),
    str(REPO / "scripts" / "game"),
    str(REPO / "scripts" / "newgame"),
    str(REPO / "scripts" / "planet"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_core_bundle as mcb  # noqa: E402
from fo4sf.core import bundle_log  # noqa: E402
from fo4sf.core.start_worlds import START_WORLD_TABLE, get_start_world  # noqa: E402
from fo4sf.planet.esm import ESM, PluginWriter, Record, zbytes  # noqa: E402


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_tes4_esm(path: Path, masters: tuple[str, ...] = ("Starfield.esm",), extra_tag: bytes = b"") -> str:
    """Write a minimal valid TES4 Master plugin header understood by exp_install.plugin_masters."""
    subrecords = bytearray()
    # HEDR (12 bytes)
    subrecords += b"HEDR" + struct.pack("<HfII", 12, 0.96, 0, 0x800)
    for m in masters:
        raw_m = m.encode("utf-8") + b"\x00"
        subrecords += b"MAST" + struct.pack("<H", len(raw_m)) + raw_m
        subrecords += b"DATA" + struct.pack("<HQ", 8, 0)
    if extra_tag:
        subrecords += b"CNAM" + struct.pack("<H", len(extra_tag) + 1) + extra_tag + b"\x00"
    # TES4 24-byte header: type(4), dataSize(I), flags(I=0x01 Master), formId(I=0), vc1(I=0), formVer(H=581), vc2(H=0)
    header = b"TES4" + struct.pack("<IIIIHH", len(subrecords), 0x00000001, 0, 0, 581, 0)
    blob = header + bytes(subrecords)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return _sha256_bytes(blob)


def _make_core_values_esm(path: Path, test_mode: float) -> str:
    """Write a minimal valid FO4SFCoreValues.esm containing GLOB 0x000860 (FO4SF_TestModeEnabled) and 0x000865."""
    w = PluginWriter(("Starfield.esm",), flags=ESM, author="fo4-to-starfield CoreValues")
    w.add(
        Record(
            b"GLOB",
            w.own(0x000860),
            [(b"EDID", zbytes("FO4SF_TestModeEnabled")), (b"FLTV", struct.pack("<f", float(test_mode)))],
            0,
            0,
            581,
            0,
        )
    )
    w.add(
        Record(
            b"GLOB",
            w.own(0x000865),
            [(b"EDID", zbytes("FO4SF_PipboyAcquired")), (b"FLTV", struct.pack("<f", 0.0))],
            0,
            0,
            581,
            0,
        )
    )
    blob = w.to_bytes(compress=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return _sha256_bytes(blob)


class _FakeSystemOpen:
    def pids(self, image: str = "Starfield.exe"):
        return [4242]


class _FakeSystemClosed:
    def pids(self, image: str = "Starfield.exe"):
        return []


class _FakeSystemBroken:
    def pids(self, image: str = "Starfield.exe"):
        raise ValueError("tasklist unavailable")


class CoreBundleTests(unittest.TestCase):
    def _build_synthetic_owner_and_stages(self, root: Path):
        owner = root / "owner-set"
        (owner / "Data" / "Scripts").mkdir(parents=True)
        (owner / "Data" / "materials" / "fo4port").mkdir(parents=True)

        for base_esm in ("FO4ActorRaider.esm", "FO4SFMission.esm", "FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm"):
            if base_esm == "FO4SFMission.esm":
                masters = ("Starfield.esm", "FO4TerrainCore.esm", "FO4ActorRaider.esm")
            elif base_esm == "FO4TerrainCore_Mars.esm":
                masters = ("Starfield.esm", "FO4TerrainCore.esm")
            else:
                masters = ("Starfield.esm",)
            _make_tes4_esm(owner / base_esm, masters=masters, extra_tag=base_esm.encode("ascii"))

        # Stale FO4SFNewGame.esm + 4 PEX inside owner-set that clean-core MUST strip
        _make_tes4_esm(owner / "FO4SFNewGame.esm", extra_tag=b"old-newgame")
        for s in ("Quest", "Looks", "Special", "Version"):
            (owner / "Data" / "Scripts" / f"FO4SF_NewGame{s}.pex").write_bytes(f"old-{s}".encode("ascii"))

        # Shared _neutral.mat already in owner-set (same bytes as cog_door & exit_lift)
        shared_mat = b"SHARED_NEUTRAL_MAT_BYTES"
        shared_mat_sha = _sha256_bytes(shared_mat)
        (owner / "Data" / "materials" / "fo4port" / "_neutral.mat").write_bytes(shared_mat)

        readme_orig = (
            "Synthetic owner set\n"
            "  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> "
            "--plugins FO4ActorRaider.esm,FO4SFMission.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFNewGame.esm --pack\n"
        )
        (owner / "README.txt").write_text(readme_orig, encoding="utf-8", newline="\n")

        port_esm = root / "port" / "FO4Port.esm"
        _make_tes4_esm(port_esm, extra_tag=b"port")

        stages_root = root / "stages"

        def add_stage(folder: str, plugin: str, pex_name: str | None = None, extra_files: dict[str, bytes] | None = None, masters=("Starfield.esm",)):
            st = stages_root / folder
            st.mkdir(parents=True, exist_ok=True)
            p_sha = _make_tes4_esm(st / plugin, masters=masters, extra_tag=plugin.encode("ascii"))
            outputs = {plugin: p_sha}
            if pex_name:
                pex_rel = f"Data/Scripts/{pex_name}.pex"
                pex_bytes = f"PEX:{pex_name}".encode("ascii")
                (st / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
                (st / "Data" / "Scripts" / f"{pex_name}.pex").write_bytes(pex_bytes)
                outputs[pex_rel] = _sha256_bytes(pex_bytes)
            for rel, raw in (extra_files or {}).items():
                fp = st / Path(*rel.split("/"))
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_bytes(raw)
                outputs[rel] = _sha256_bytes(raw)
            (st / "plan.json").write_text(json.dumps({"plugin": plugin, "plugins": [plugin], "outputs": outputs}, indent=1), encoding="utf-8")

        def add_core_values_stage(folder: str, test_mode: float):
            st = stages_root / folder
            st.mkdir(parents=True, exist_ok=True)
            cv_sha = _make_core_values_esm(st / "FO4SFCoreValues.esm", test_mode=test_mode)
            (st / "plan.json").write_text(
                json.dumps(
                    {
                        "plugin": "FO4SFCoreValues.esm",
                        "plugins": ["FO4SFCoreValues.esm"],
                        "outputs": {"FO4SFCoreValues.esm": cv_sha},
                    },
                    indent=1,
                ),
                encoding="utf-8",
            )

        add_core_values_stage("00-core-values", test_mode=1.0)
        add_core_values_stage("00-core-values-test", test_mode=1.0)
        add_core_values_stage("00-core-values-player", test_mode=0.0)
        add_stage("01-cog-door", "FO4SFVaultGearDoor.esm", masters=("Starfield.esm", "FO4Port.esm"),
                  extra_files={"Data/materials/fo4port/_neutral.mat": shared_mat,
                               "Data/meshes/fo4port/door_anim.nif": b"DOOR_NIF"})
        add_stage("02-exit-lift", "FO4SFExitLift.esm", masters=("Starfield.esm", "FO4Port.esm"),
                  extra_files={"Data/materials/fo4port/_neutral.mat": shared_mat,
                               "Data/meshes/fo4port/lift_anim.nif": b"LIFT_NIF"})
        add_stage("03-newgame", "FO4SFNewGame.esm", pex_name="FO4SF_NewGameQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        add_stage("04-rads", "FO4SFRads.esm", pex_name="FO4SF_RadsCoreQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        add_stage("05-hardcore", "FO4SFHardcore.esm", pex_name="FO4SF_HardcoreQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        add_stage("06-workshop", "FO4SFWorkshop.esm", pex_name="FO4SF_WorkshopCoreQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        add_stage("07-powerarmor", "FO4SFPowerArmor.esm", pex_name="FO4SF_PowerArmorCoreQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        add_stage("08-progression", "FO4SFProgression.esm", pex_name="FO4SF_ProgressionQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        add_stage("09-list-dialogue", "FO4SFListDialogue.esm", pex_name="FO4SF_ListDialogueQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm", "FO4SFProgression.esm"))

        # 10-combat with FO4SFCombat.dll SFSE sidecar
        add_stage("10-combat", "FO4SFCombat.esm", pex_name="FO4SF_CombatQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"),
                  extra_files={"Data/Scripts/FO4SF_CombatInput.pex": b"PEX:FO4SF_CombatInput"})
        combat_sc = stages_root / "10-combat" / "sfse_sidecar"
        combat_sc.mkdir(parents=True, exist_ok=True)
        (combat_sc / "FO4SFCombat.dll").write_bytes(b"MZ_SYNTHETIC_COMBAT_DLL")

        # 11-reputation with Pip-Boy INI/JSON/TSV sidecar manifests
        add_stage("11-reputation", "FO4SFReputation.esm", pex_name="FO4SF_ReputationQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        (stages_root / "11-reputation" / "FO4SFPipboyKit.ini").write_text("[Page STAT/KARMA]\n", encoding="utf-8")

        # 12-companions & 13-alife
        add_stage("12-companions", "FO4SFCompanions.esm", pex_name="FO4SF_CompanionsQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        add_stage("13-alife", "FO4SFALife.esm", pex_name="FO4SF_ALifeControllerQuest",
                  masters=("Starfield.esm", "FO4TerrainCore.esm", "FO4ActorRaider.esm"))

        # Mirror make_fort_hagen.py's exact stage layout (Data/FO4SFFortHagen.esm + script ending in .pex)
        fh_st = stages_root / "14-fort-hagen"
        (fh_st / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
        fh_esm_sha = _make_tes4_esm(
            fh_st / "Data" / "FO4SFFortHagen.esm",
            masters=("Starfield.esm", "FO4Port.esm", "FO4TerrainCore.esm"),
            extra_tag=b"FO4SFFortHagen.esm",
        )
        fh_pex = b"PEX:FO4SF_FortHagenQuest"
        (fh_st / "Data" / "Scripts" / "FO4SF_FortHagenQuest.pex").write_bytes(fh_pex)
        (fh_st / "plan.json").write_text(
            json.dumps({
                "plugin": "FO4SFFortHagen.esm",
                "plugin_sha256": fh_esm_sha,
                "script": "FO4SF_FortHagenQuest.pex",
                "script_sha256": _sha256_bytes(fh_pex),
            }, indent=1),
            encoding="utf-8",
        )
        add_stage("15-candidate-walk", "FO4SFCoreCandidate.esm", pex_name="FO4SF_CoreCandidateWalk",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))

        return owner, stages_root, port_esm, shared_mat_sha

    def test_refuses_when_game_open_or_process_query_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)
            out = root / "bundle-open"
            rc = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(out), "--port", str(port_esm),
            ], system=_FakeSystemOpen())
            self.assertEqual(rc, 2)
            self.assertFalse(out.exists())

            rc_err = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(out), "--port", str(port_esm),
            ], system=_FakeSystemBroken())
            self.assertEqual(rc_err, 2)
            self.assertFalse(out.exists())

    def test_clean_core_fold_verify_and_pipboy_option(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)
            owner_readme_before = (owner / "README.txt").read_bytes()

            # Add synthetic pipboy-stack stage matching Job 2 plan.json layout
            pb = stages_root / "pipboy-stage"
            (pb / "Data" / "Interface").mkdir(parents=True)
            (pb / "Data" / "Scripts").mkdir(parents=True)
            (pb / "SFSE" / "Plugins").mkdir(parents=True)
            p1_sha = _make_tes4_esm(pb / "FO4SFPipboyProbe.esm", extra_tag=b"pbprobe")
            p2_sha = _make_tes4_esm(pb / "FO4SFPipboyTravel.esm", extra_tag=b"pbtravel")
            swf_bytes = b"FWS_SYNTHETIC_PIPBOY"
            (pb / "Data" / "Interface" / "FO4SF_Fo4Shell.swf").write_bytes(swf_bytes)
            pex_bytes = b"PEX_TRAVEL"
            (pb / "Data" / "Scripts" / "FO4SF_PipboyTravel.pex").write_bytes(pex_bytes)
            dll_bytes = b"MZ_SYNTHETIC_PIPBOY_DLL"
            (pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").write_bytes(dll_bytes)
            (pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").write_text(
                "[FO4SFPipboyMenu]\nStage=2\n\n[Kit]\nHeadingAt=88\n\n[Page STAT/STATUS]\nRow=HP|{health}\n",
                encoding="utf-8",
            )
            pb_plan = {
                "kind": "pipboy-stack-stage",
                "plugins": ["FO4SFPipboyProbe.esm", "FO4SFPipboyTravel.esm"],
                "files": {
                    "FO4SFPipboyProbe.esm": {"sha256": p1_sha},
                    "FO4SFPipboyTravel.esm": {"sha256": p2_sha},
                    "Data/Interface/FO4SF_Fo4Shell.swf": {"sha256": _sha256_bytes(swf_bytes)},
                    "Data/Scripts/FO4SF_PipboyTravel.pex": {"sha256": _sha256_bytes(pex_bytes)},
                },
            }
            (pb / "plan.json").write_text(json.dumps(pb_plan, indent=1), encoding="utf-8")

            out = root / "bundle-ok"
            clean_out = root / "clean-core"
            rc = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--clean-core-out", str(clean_out), "--out", str(out), "--port", str(port_esm),
                "--profile", "test", "--with-pipboy", "--pipboy-stage", str(pb),
            ], system=_FakeSystemClosed())
            self.assertEqual(rc, 0)

            # Source owner-set README.txt was NEVER mutated
            self.assertEqual((owner / "README.txt").read_bytes(), owner_readme_before)
            self.assertFalse((clean_out / "FO4SFNewGame.esm").exists())

            # Verify standalone verify command passes and README has exactly ONE install line
            rc_v = mcb.main(["verify", "--bundle-dir", str(out), "--port", str(port_esm)])
            self.assertEqual(rc_v, 0)

            readme_txt = (out / "README.txt").read_text(encoding="utf-8")
            install_lines = [ln for ln in readme_txt.splitlines() if "exp_install.py install" in ln]
            rollback_lines = [ln for ln in readme_txt.splitlines() if "exp_install.py uninstall" in ln]
            self.assertEqual(len(install_lines), 1)
            self.assertEqual(len(rollback_lines), 1)
            self.assertIn("--pack", install_lines[0])

            bplan = json.loads((out / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(len(bplan["plugins"]), 22)
            self.assertIn("FO4SFCoreValues.esm", bplan["plugins"])
            self.assertLess(bplan["plugins"].index("FO4SFCoreValues.esm"), bplan["plugins"].index("FO4SFNewGame.esm"))
            self.assertEqual(
                bplan["plugins"][:4],
                ["FO4ActorRaider.esm", "FO4TerrainCore.esm", "FO4SFMission.esm", "FO4TerrainCore_Mars.esm"],
            )
            # SFSE DLLs & Reputation manifests kept outside Data/ so Archive2 never packs them into Main.ba2
            self.assertTrue((out / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").is_file())
            shipped_pb_ini = (out / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
            self.assertNotIn("[Kit]", shipped_pb_ini)
            self.assertNotIn("[Page ", shipped_pb_ini)
            self.assertIn("MapHeadingAt=88", shipped_pb_ini)
            self.assertTrue((out / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFCombat.dll").is_file())
            self.assertTrue((out / "sfse_sidecar" / "reputation" / "FO4SFPipboyKit.ini").is_file())
            self.assertFalse((out / "Data" / "SFSE").exists())

            # A17: Default profile for fold (when --profile is omitted) is 'player', omitting FO4SFCoreCandidate.esm
            out_player = root / "bundle-player"
            rc_player = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(out_player), "--port", str(port_esm),
                "--with-pipboy", "--pipboy-stage", str(pb),
            ], system=_FakeSystemClosed())
            self.assertEqual(rc_player, 0)
            pplan = json.loads((out_player / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(pplan["profile"], "player")
            self.assertEqual(len(pplan["plugins"]), 21)
            self.assertNotIn("FO4SFCoreCandidate.esm", pplan["plugins"])

            # Empty/wrong --pipboy-stage is refused (never silently folds 0 Pip-Boy plugins)
            empty_pb = root / "empty-pb"
            empty_pb.mkdir()
            rc_bad_pb = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(root / "bundle-bad-pb"), "--port", str(port_esm),
                "--with-pipboy", "--pipboy-stage", str(empty_pb),
            ], system=_FakeSystemClosed())
            self.assertEqual(rc_bad_pb, 2)

    def test_refuses_differing_core_asset_plugin_limit_and_4gib_archive_limit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)

            out = root / "bundle-limits"
            rc = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(out), "--port", str(port_esm),
            ], system=_FakeSystemClosed())
            self.assertEqual(rc, 0)

            # Plugin count cap refusal
            self.assertEqual(mcb.main(["verify", "--bundle-dir", str(out), "--max-plugins", "10"]), 1)
            # 4 GiB BA2 archive cap refusal (tested against tight byte ceiling)
            self.assertEqual(mcb.main(["verify", "--bundle-dir", str(out), "--max-ba2-bytes", "100"]), 1)

            # Differing shared asset in owner-set must refuse fold
            (owner / "Data" / "materials" / "fo4port" / "_neutral.mat").write_bytes(b"DIFFERENT_BYTES")
            rc_diff = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(root / "bundle-bad-asset"), "--port", str(port_esm),
            ], system=_FakeSystemClosed())
            self.assertEqual(rc_diff, 2)

    def test_bundle_log_evaluates_all_eight_steps_independently(self):
        with tempfile.TemporaryDirectory() as td:
            ldir = Path(td)
            held_lines = [f"FO4SF_NEWGAME rt=1.5 held off Quest_{i:03d} running_after=False pass={(1 if i < 41 else 2)}"
                          for i in range(196)]
            ng_lines = [
                "FO4SF_NEWGAME rt=0.5 init v=1",
                "FO4SF_NEWGAME rt=1.0 stage 10",
                "FO4SF_NEWGAME rt=1.2 pod settle ok=True pos=(9.1,-6.6,-0.9) dx=0.0 dy=0.0 drop=0.12",
                *held_lines,
                "FO4SF_NEWGAME rt=2.0 stage 20",
                "FO4SF_NEWGAME rt=3.0 stage 30",
                "FO4SF_NEWGAME rt=4.0 ascent play accepted=True",
                "FO4SF_NEWGAME rt=14.0 ascent carried confirmed elapsed=9.8 z=19.88",
                "FO4SF_NEWGAME rt=15.0 stage 40",
                "FO4SF_NEWGAME rt=16.0 surface setposition ok=True set=1 pos=(-2467,-1406,128) target=(-2467,-1406,128) core_cell=True cell=Cell <Surface (03000CF0)>",
                "FO4SF_NEWGAME rt=19.0 landed ok=True",
                "FO4SF_NEWGAME rt=19.5 stage 200",
            ]
            (ldir / "fo4sf_newgame.0.log").write_text("\n".join(ng_lines), encoding="utf-8")
            (ldir / "FO4SFRadsCore.0.log").write_text("rads=150.0 source=emitter\nradaway delta=-300 rads=0.0\n", encoding="utf-8")
            (ldir / "FO4SFHardcore.0.log").write_text("enabled=true reason=gpof sq_env_running=false\nenabled=false reason=gpof sq_env_running=false\n", encoding="utf-8")
            (ldir / "FO4SFWorkshopCore.1.log").write_text("cmpo_scrap items=16\ncamp_deployed ok=true\n", encoding="utf-8")
            (ldir / "FO4SFWorkshopCore.0.log").write_text("reload_audit when=reload tracked_beacons=1\n", encoding="utf-8")
            (ldir / "FO4SFPACore.0.log").write_text("enter_complete inpa=true\nexit_complete frame_standing=true\n", encoding="utf-8")
            (ldir / "FO4SFListDialogue.0.log").write_text("choice stage=20 speech_pass=true\n", encoding="utf-8")
            (ldir / "FO4SFCoreCandidate.0.log").write_text(
                "FO4SFCANDIDATE rt=50.0 chargen_applied run=1 trigger=kiosk_activate bg=VaultDweller trait1=GoodNatured trait2=SmallFrame traits_count=2 special_sum=40 speech=52 science=52 str=7 end=true\n",
                encoding="utf-8",
            )
            (ldir / "FO4SFProgression.0.log").write_text(
                "FO4SFPROG rt=50.5 creation_applied source=lift_prompt bg=0 traits=2 special_sum=40 skills_count=13 tags=10,3,4 carry_mod=45.0 end=true\n",
                encoding="utf-8",
            )
            (ldir / "FO4SFCombat.0.log").write_text(
                "\n".join([
                    "[FO4SF_Combat] PASS step=zone_hit zone=head mult=2.0 applied=48.0 subtype=standard",
                    "[FO4SF_Combat] PASS step=zone_hit zone=torso mult=1.0 applied=24.0 subtype=standard",
                    "[FO4SF_Combat] PASS step=zone_hit zone=left_arm mult=0.85 applied=20.4 subtype=standard",
                    "[FO4SF_Combat] PASS step=zone_hit zone=right_arm mult=0.85 applied=20.4 subtype=standard",
                    "[FO4SF_Combat] PASS step=zone_hit zone=left_leg mult=0.85 applied=20.4 subtype=standard",
                    "[FO4SF_Combat] PASS step=zone_hit zone=right_leg mult=0.85 applied=20.4 subtype=standard",
                    "[FO4SF_Combat] PASS step=high_dt_hit subtype=standard target_dt=18.0 eff_dt=18.0 damage=4.8",
                    "[FO4SF_Combat] PASS step=high_dt_hit subtype=ap target_dt=18.0 eff_dt=3.0 damage=16.38",
                    "[FO4SF_Combat] PASS step=limb_crippled zone=left_leg speed_delta=-40.0 sway=0.0",
                    "[FO4SF_Combat] PASS step=limb_cure item=doctors_bag hardcore=1 cured=1",
                    "[FO4SF_Combat] PASS step=vats_shot slow_time=1 zone=head ap_cost=32 chance=54 queued=1",
                ]),
                encoding="utf-8",
            )
            (ldir / "FO4SFReputation.1.log").write_text(
                "token_hook token=theft count=3 karma=-1000 tier=-2 buy_mult=1.0 fac0_react=0 states=0,0,0,0,0,0,0,0\n"
                "token_hook token=faction_aid count=1 karma=-1000 tier=-2 buy_mult=0.75 fac0_react=2 states=3,0,0,0,0,0,0,0\n",
                encoding="utf-8",
            )
            (ldir / "FO4SFReputation.0.log").write_text(
                "reload_audit karma=-1000 tier=-2 buy_mult=0.75 fac0_react=2 states=3,0,0,0,0,0,0,0 ok=true\n",
                encoding="utf-8",
            )
            (ldir / "FO4SFCompanions.1.log").write_text(
                "stage_result stage=20 cap=4 active=4 wait_all=4 follow_all=4 pass=true\n"
                "teleport reason=manual_radio_sync moved=4 skipped_waiting=0 active=4\n",
                encoding="utf-8",
            )
            (ldir / "FO4SFCompanions.0.log").write_text(
                "reload_audit when=reload reload_count=1 squad_ok=4/4 following=4 waiting=0 pass=true\n",
                encoding="utf-8",
            )
            sfse_logs = ldir / "sfse_logs"
            sfse_logs.mkdir()
            (sfse_logs / "FO4SFPipboyMenu.log").write_text(
                "\n".join([
                    "step=code_obj_special n=1 when=late mode=fill found=1 type=object cleared_by=length pushed=7 length=#7",
                    "step=map_key n=1 vk=0x4D was_open=0 page=3 sent=show",
                    "step=map_texture loaded=1 children=1",
                    "step=map_markers n=309 discovered=2 undiscovered=307 player_idx=309 corners_set=3/3 read_back=match",
                    "step=map_key n=2 vk=0x4D was_open=1 on_map=1 sent=hide",
                    "step=starmap_blocked n=1 route=create",
                ]),
                encoding="utf-8",
            )

            self.assertEqual(
                mcb.main(["log", "--log-dir", str(ldir), "--sfse-log-dir", str(sfse_logs), "--step", "all"]),
                0,
            )
            results = bundle_log.evaluate_walk_logs(
                str(ldir), mcb.make_newgame.summarize, sfse_log_dir=str(sfse_logs)
            )
            self.assertEqual(len(results), 12)
            self.assertTrue(all(r["ok"] for r in results.values()))

            # --no-pipboy allows evaluating a 19-plugin non-Pip-Boy run cleanly
            self.assertEqual(mcb.main(["log", "--log-dir", str(ldir), "--no-pipboy", "--step", "all"]), 0)

            # A refusal line in FO4SFPipboyMenu.log fails only step 'pipboy' without breaking steps 1..11
            (sfse_logs / "FO4SFPipboyMenu.log").write_text("refuse step=ini reason=bad\n", encoding="utf-8")
            results_bad_pb = bundle_log.evaluate_walk_logs(
                str(ldir), mcb.make_newgame.summarize, sfse_log_dir=str(sfse_logs)
            )
            self.assertFalse(results_bad_pb["pipboy"]["ok"])
            self.assertTrue(all(results_bad_pb[k]["ok"] for k in bundle_log.STEP_NAMES if k != "pipboy"))

    def test_walk_harness_script_wires_station_g_fireteam_muster(self):
        psc_txt = (REPO / "scripts" / "core" / "FO4SF_CoreCandidateWalk.psc").read_text(encoding="utf-8")
        self.assertIn("PlacedFireteamRefs = new ObjectReference[4]", psc_txt)
        self.assertIn('RegisterForRemoteEvent(ftRef, "OnActivate")', psc_txt)
        self.assertIn("compQuest.SetStage(20)", psc_txt)
        self.assertIn("walk_refused reason=test_mode_disabled", psc_txt)
        self.assertIn("progQ.ApplyCreationSheet(", psc_txt)
        self.assertNotIn("DlgSpeechAvId", psc_txt)

    def test_cf1_start_world_descriptor_table_covers_all_titles_and_faction_starts(self):
        for required in ("vault111", "vault101", "goodsprings", "vault76", "vault13", "arroyo", "bunkeralpha"):
            self.assertIn(required, START_WORLD_TABLE)
        v111 = get_start_world("vault111")
        self.assertEqual(v111.squad_base_cap, 2)
        self.assertEqual(v111.initial_karma, 0)
        bunker = get_start_world("bunkeralpha")
        self.assertEqual(bunker.squad_base_cap, 4)
        self.assertIn("Brotherhood", bunker.initial_fame)
        mm = get_start_world("minuteman_volunteer")
        self.assertEqual(mm.squad_base_cap, 4)
        self.assertIn("Minutemen", mm.initial_fame)

    def test_a1_pipboy_boot_movie_copied_from_stage_and_verify_refuses_when_absent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)

            pb = stages_root / "16-pipboy-cand2"
            (pb / "Data" / "Interface").mkdir(parents=True)
            (pb / "Data" / "Scripts").mkdir(parents=True)
            (pb / "SFSE" / "Plugins").mkdir(parents=True)
            p1_sha = _make_tes4_esm(pb / "FO4SFPipboyProbe.esm", extra_tag=b"pbprobe")
            p2_sha = _make_tes4_esm(pb / "FO4SFPipboyTravel.esm", extra_tag=b"pbtravel")
            shell_swf = b"FWS_SYNTHETIC_SHELL"
            boot_swf = b"CWS_SYNTHETIC_BOOT_SEQUENCE"
            pex_bytes = b"PEX_TRAVEL"
            (pb / "Data" / "Interface" / "FO4SF_Fo4Shell.swf").write_bytes(shell_swf)
            (pb / "Data" / "Interface" / "pipboybootsequence.swf").write_bytes(boot_swf)
            (pb / "Data" / "Scripts" / "FO4SF_PipboyTravel.pex").write_bytes(pex_bytes)
            (pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").write_bytes(b"MZ_SYNTHETIC_PIPBOY_DLL")
            (pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").write_text(
                "[FO4SFPipboyMenu]\nStage=2\nMovie=FO4SF_Fo4Shell\nBootMovie=pipboybootsequence\nBootOnFirstOpen=1\n",
                encoding="utf-8",
            )
            # Reproduce Candidate 2 bug: stage plan.json omitted pipboybootsequence.swf even though INI named it
            (pb / "plan.json").write_text(
                json.dumps(
                    {
                        "kind": "pipboy-stack-stage",
                        "plugins": ["FO4SFPipboyProbe.esm", "FO4SFPipboyTravel.esm"],
                        "files": {
                            "FO4SFPipboyProbe.esm": {"sha256": p1_sha},
                            "FO4SFPipboyTravel.esm": {"sha256": p2_sha},
                            "Data/Interface/FO4SF_Fo4Shell.swf": {"sha256": _sha256_bytes(shell_swf)},
                            "Data/Scripts/FO4SF_PipboyTravel.pex": {"sha256": _sha256_bytes(pex_bytes)},
                        },
                    },
                    indent=1,
                ),
                encoding="utf-8",
            )

            out_ok = root / "bundle-with-boot"
            rc = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(out_ok), "--port", str(port_esm),
                "--profile", "player", "--with-pipboy", "--pipboy-stage", str(pb),
            ], system=_FakeSystemClosed())
            self.assertEqual(rc, 0)
            self.assertTrue((out_ok / "Data" / "Interface" / "pipboybootsequence.swf").is_file())
            bplan = json.loads((out_ok / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertIn(
                "Data/Interface/pipboybootsequence.swf",
                bplan["components"]["pipboy"]["outputs"],
            )
            self.assertEqual(mcb.main(["verify", "--bundle-dir", str(out_ok), "--port", str(port_esm)]), 0)

            # Removing pipboybootsequence.swf from both disk and manifest (the Candidate 2 failure state) MUST fail verify!
            (out_ok / "Data" / "Interface" / "pipboybootsequence.swf").unlink()
            bplan["components"]["pipboy"]["outputs"].pop("Data/Interface/pipboybootsequence.swf", None)
            (out_ok / "bundle_plan.json").write_text(json.dumps(bplan, indent=1), encoding="utf-8")
            probs, _ = mcb.verify_bundle(str(out_ok), port_esm=str(port_esm))
            self.assertTrue(any("BootMovie" in p and "pipboybootsequence.swf" in p for p in probs), probs)
            self.assertEqual(mcb.main(["verify", "--bundle-dir", str(out_ok), "--port", str(port_esm)]), 1)

    def test_a5_test_vs_player_profile_core_values_fltv_and_pinned_hashes(self):
        # parity not applicable: ordered by A5
        PINNED_SYNTH_TEST_ESM_SHA256 = "a400f17ef6e4be0689d393719e8208b937774c1df795555c83ac2f97637af4ef"
        PINNED_SYNTH_PLAYER_ESM_SHA256 = "e18bd6f628b3246b88ab209a263b4cc1b0b435f8dc296c11d43516d46dc45b4a"

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)

            # Verify stage_from_checkout passes --test-mode 1 for test profile and --test-mode 0 for player profile
            recorded_cv_calls: list[tuple[str, list[str]]] = []
            orig_run_py = mcb._run_py

            def _spy_run_py(py_exe, script_rel, args):
                if script_rel == "scripts/core/make_core_values.py":
                    recorded_cv_calls.append((script_rel, list(args)))
                    out_idx = list(args).index("--out") + 1
                    Path(args[out_idx]).mkdir(parents=True, exist_ok=True)
                    raise StopIteration("stop-after-core-values")
                return orig_run_py(py_exe, script_rel, args)

            mcb._run_py = _spy_run_py
            try:
                for prof in ("test", "player"):
                    ns = type("Args", (), {
                        "work": str(root / "work-spy"),
                        "render_python": None,
                        "starfield_dir": str(root / "sf"),
                        "port": str(port_esm),
                        "owner_set": str(owner),
                        "profile": prof,
                        "commonlibsf": None,
                        "msvc_env": None,
                    })()
                    with self.assertRaises(StopIteration):
                        mcb.stage_from_checkout(ns)
            finally:
                mcb._run_py = orig_run_py

            self.assertEqual(len(recorded_cv_calls), 2)
            self.assertEqual(recorded_cv_calls[0][1][-2:], ["--test-mode", "1"])
            self.assertEqual(recorded_cv_calls[1][1][-2:], ["--test-mode", "0"])

            out_test = root / "bundle-test"
            self.assertEqual(
                mcb.main([
                    "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                    "--out", str(out_test), "--port", str(port_esm), "--profile", "test",
                ], system=_FakeSystemClosed()),
                0,
            )
            out_player = root / "bundle-player"
            self.assertEqual(
                mcb.main([
                    "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                    "--out", str(out_player), "--port", str(port_esm), "--profile", "player",
                ], system=_FakeSystemClosed()),
                0,
            )

            test_val, test_err = mcb.read_core_values_test_mode_fltv(str(out_test / "FO4SFCoreValues.esm"))
            player_val, player_err = mcb.read_core_values_test_mode_fltv(str(out_player / "FO4SFCoreValues.esm"))
            self.assertIsNone(test_err)
            self.assertIsNone(player_err)
            self.assertAlmostEqual(test_val, 1.0, places=5)
            self.assertAlmostEqual(player_val, 0.0, places=5)

            self.assertEqual(mcb.sha256_file(str(out_test / "FO4SFCoreValues.esm")), PINNED_SYNTH_TEST_ESM_SHA256)
            self.assertEqual(mcb.sha256_file(str(out_player / "FO4SFCoreValues.esm")), PINNED_SYNTH_PLAYER_ESM_SHA256)

            # Swapping player (0.0) FO4SFCoreValues.esm into test bundle (even updating hash) MUST fail verify!
            player_bytes = (out_player / "FO4SFCoreValues.esm").read_bytes()
            test_bytes = (out_test / "FO4SFCoreValues.esm").read_bytes()

            (out_test / "FO4SFCoreValues.esm").write_bytes(player_bytes)
            tplan = json.loads((out_test / "bundle_plan.json").read_text(encoding="utf-8"))
            tplan["components"]["core_values"]["outputs"]["FO4SFCoreValues.esm"] = _sha256_bytes(player_bytes)
            (out_test / "bundle_plan.json").write_text(json.dumps(tplan, indent=1), encoding="utf-8")
            t_probs, _ = mcb.verify_bundle(str(out_test), port_esm=str(port_esm))
            self.assertTrue(any("--profile test requires FO4SF_TestModeEnabled" in p for p in t_probs), t_probs)
            self.assertEqual(mcb.main(["verify", "--bundle-dir", str(out_test), "--port", str(port_esm)]), 1)

            # Swapping test (1.0) FO4SFCoreValues.esm into player bundle (even updating hash) MUST fail verify!
            (out_player / "FO4SFCoreValues.esm").write_bytes(test_bytes)
            pplan = json.loads((out_player / "bundle_plan.json").read_text(encoding="utf-8"))
            pplan["components"]["core_values"]["outputs"]["FO4SFCoreValues.esm"] = _sha256_bytes(test_bytes)
            (out_player / "bundle_plan.json").write_text(json.dumps(pplan, indent=1), encoding="utf-8")
            p_probs, _ = mcb.verify_bundle(str(out_player), port_esm=str(port_esm))
            self.assertTrue(any("--profile player requires FO4SF_TestModeEnabled" in p for p in p_probs), p_probs)
            self.assertEqual(mcb.main(["verify", "--bundle-dir", str(out_player), "--port", str(port_esm)]), 1)

    def test_a16_verify_refuses_newgame_mastering_core_values_without_store_or_out_of_order(self):
        # parity not applicable: ordered by A16
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)

            out = root / "bundle-a16"
            self.assertEqual(
                mcb.main([
                    "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                    "--out", str(out), "--port", str(port_esm), "--profile", "player",
                ], system=_FakeSystemClosed()),
                0,
            )

            # 1. Ordering FO4SFNewGame.esm BEFORE FO4SFCoreValues.esm in Plugins.txt / bundle_plan.json must fail verify
            bplan = json.loads((out / "bundle_plan.json").read_text(encoding="utf-8"))
            orig_plugins = list(bplan["plugins"])
            reordered = [p for p in orig_plugins if p != "FO4SFCoreValues.esm"] + ["FO4SFCoreValues.esm"]
            bplan["plugins"] = reordered
            (out / "bundle_plan.json").write_text(json.dumps(bplan, indent=1), encoding="utf-8")
            readme_txt = (out / "README.txt").read_text(encoding="utf-8").replace(
                ",".join(orig_plugins), ",".join(reordered)
            )
            (out / "README.txt").write_text(readme_txt, encoding="utf-8", newline="\n")
            probs_order, _ = mcb.verify_bundle(str(out), port_esm=str(port_esm))
            self.assertTrue(
                any("FO4SFNewGame.esm is ordered before its required master FO4SFCoreValues.esm" in p for p in probs_order),
                probs_order,
            )

            # 2. Removing FO4SFCoreValues.esm from the bundle completely while FO4SFNewGame.esm masters it must fail verify
            without_cv = [p for p in orig_plugins if p != "FO4SFCoreValues.esm"]
            bplan["plugins"] = without_cv
            bplan["components"].pop("core_values", None)
            (out / "bundle_plan.json").write_text(json.dumps(bplan, indent=1), encoding="utf-8")
            (out / "README.txt").write_text(
                readme_txt.replace(",".join(reordered), ",".join(without_cv)),
                encoding="utf-8",
                newline="\n",
            )
            (out / "FO4SFCoreValues.esm").unlink()
            probs_missing, _ = mcb.verify_bundle(str(out), port_esm=str(port_esm))
            self.assertTrue(
                any("FO4SFNewGame.esm masters FO4SFCoreValues.esm, but bundle lacks FO4SFCoreValues.esm" in p for p in probs_missing),
                probs_missing,
            )
            self.assertEqual(mcb.main(["verify", "--bundle-dir", str(out), "--port", str(port_esm)]), 1)

    def test_a15_verify_binary_esm_rejects_rogue_duplicate_editor_id_plugin(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)

            out = root / "bundle-a15"
            self.assertEqual(
                mcb.main([
                    "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                    "--out", str(out), "--port", str(port_esm),
                ], system=_FakeSystemClosed()),
                0,
            )
            self.assertEqual(mcb.main(["verify", "--bundle-dir", str(out), "--port", str(port_esm)]), 0)

            # Inject a rogue binary .esm redefining FO4SF_Rads (already owned by FO4SFCoreValues.esm:0x000800)
            rogue_w = PluginWriter(("Starfield.esm",), flags=ESM, author="rogue")
            rogue_w.add(
                Record(
                    b"AVIF",
                    rogue_w.own(0x000899),
                    [(b"EDID", zbytes("FO4SF_Rads"))],
                    0,
                    0,
                    581,
                    0,
                )
            )
            rogue_bytes = rogue_w.to_bytes(compress=False)
            (out / "FO4SFRogueDup.esm").write_bytes(rogue_bytes)

            bplan = json.loads((out / "bundle_plan.json").read_text(encoding="utf-8"))
            orig_plugins = list(bplan["plugins"])
            new_plugins = [*orig_plugins, "FO4SFRogueDup.esm"]
            bplan["plugins"] = new_plugins
            bplan["components"]["rogue"] = {
                "plugins": ["FO4SFRogueDup.esm"],
                "outputs": {"FO4SFRogueDup.esm": _sha256_bytes(rogue_bytes)},
            }
            (out / "bundle_plan.json").write_text(json.dumps(bplan, indent=1), encoding="utf-8")
            (out / "README.txt").write_text(
                (out / "README.txt").read_text(encoding="utf-8").replace(",".join(orig_plugins), ",".join(new_plugins)),
                encoding="utf-8",
                newline="\n",
            )

            probs, _ = mcb.verify_bundle(str(out), port_esm=str(port_esm))
            self.assertTrue(
                any("Binary stage duplicate EditorID across plugins" in p and "FO4SF_Rads" in p for p in probs),
                probs,
            )
            self.assertEqual(mcb.main(["verify", "--bundle-dir", str(out), "--port", str(port_esm)]), 1)

    def test_a17_build_and_fold_both_default_profile_to_player(self):
        # Capture parsed args for both `build` and `fold` when `--profile` is omitted
        captured: list[tuple[str, str]] = []
        orig_build = mcb.cmd_build
        orig_fold = mcb.cmd_fold
        try:
            mcb.cmd_build = lambda a, system=None: (captured.append(("build", a.profile)), 0)[1]
            mcb.cmd_fold = lambda a, system=None: (captured.append(("fold", a.profile)), 0)[1]
            rc_b = mcb.main([
                "build",
                "--owner-set", "ow",
                "--out", "out",
                "--work", "wk",
                "--starfield-dir", "sf",
                "--fo4-data", "fo4",
                "--port", "port.esm",
                "--port-ids", "ids.json",
                "--door-anim-dll", "calumi.dll",
                "--collision-template", "col.nif",
                "--texconv", "texconv.exe",
            ])
            rc_f = mcb.main([
                "fold",
                "--owner-set", "ow",
                "--stages-root", "st",
                "--out", "out",
            ])
        finally:
            mcb.cmd_build = orig_build
            mcb.cmd_fold = orig_fold

        self.assertEqual(rc_b, 0)
        self.assertEqual(rc_f, 0)
        self.assertEqual(captured, [("build", "player"), ("fold", "player")])

    def test_h2_verify_refuses_cross_head_bundle_with_single_clear_line(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)
            out = root / "bundle-h2"
            rc = mcb.main(
                [
                    "fold",
                    "--owner-set", str(owner),
                    "--stages-root", str(stages_root),
                    "--out", str(out),
                    "--port", str(port_esm),
                ],
                system=_FakeSystemClosed(),
            )
            self.assertEqual(rc, 0)

            tool_head = mcb.current_git_head(str(REPO))
            self.assertIsNotNone(tool_head)
            bplan_p = out / "bundle_plan.json"
            bplan = json.loads(bplan_p.read_text(encoding="utf-8"))
            self.assertEqual(bplan["build_head"], tool_head)

            # Simulate a bundle built at a different commit head (#833 8bdafe6f...)
            other_head = "8bdafe6f3895d7ce6641f7677496a38d571dadac"
            if tool_head.startswith("8bdafe6f"):
                other_head = "b03a534da17d830eaf3a47512849aceb56cd2ba6"
            bplan["build_head"] = other_head
            bplan_p.write_text(json.dumps(bplan, indent=1), encoding="utf-8")

            r_sub = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts" / "core" / "make_core_bundle.py"),
                    "verify",
                    "--bundle-dir", str(out),
                    "--port", str(port_esm),
                ],
                cwd=str(REPO),
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_sub.returncode, 1)
            out_lines = [ln for ln in r_sub.stdout.splitlines() if ln.strip()]
            self.assertEqual(
                out_lines,
                [f"this bundle was built at {other_head[:8]}; this tool is at {tool_head[:8]}"],
            )
            self.assertNotIn("FAIL", r_sub.stdout)
            self.assertNotIn("missing in catalog", r_sub.stdout)

            # Also verify pre-H2 bundles lacking build_head with cross-branch component keys refuse in 1 line
            bplan.pop("build_head", None)
            bplan["components"]["__future_branch_component__"] = {"plugins": [], "outputs": {}}
            bplan_p.write_text(json.dumps(bplan, indent=1), encoding="utf-8")
            probs_legacy, _ = mcb.verify_bundle(str(out), port_esm=str(port_esm), tool_head=tool_head)
            self.assertEqual(
                probs_legacy,
                [f"this bundle was built at <other-head (__future_branch_component__)>; this tool is at {tool_head[:8]}"],
            )

    def test_h3_sidecar_install_and_undo_backup_refusals_and_byte_restore(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)

            pb = stages_root / "pipboy-stage"
            (pb / "Data" / "Interface").mkdir(parents=True)
            (pb / "Data" / "Scripts").mkdir(parents=True)
            (pb / "SFSE" / "Plugins").mkdir(parents=True)
            p1_sha = _make_tes4_esm(pb / "FO4SFPipboyProbe.esm", extra_tag=b"pbprobe")
            p2_sha = _make_tes4_esm(pb / "FO4SFPipboyTravel.esm", extra_tag=b"pbtravel")
            shell_bytes = b"FWS_SYNTHETIC_PIPBOY"
            boot_bytes = b"FWS_SYNTHETIC_BOOT"
            pex_bytes = b"PEX_TRAVEL"
            bundle_pb_dll = b"MZ_BUNDLE_NEW_PIPBOY_DLL"
            bundle_pb_ini = b"[FO4SFPipboyMenu]\nStage=2\nMovie=FO4SF_Fo4Shell\nBootMovie=pipboybootsequence\n"
            bundle_markers = b"edid\tx\ty\n"
            bundle_build_json = b"{\"built\":true}\n"
            (pb / "Data" / "Interface" / "FO4SF_Fo4Shell.swf").write_bytes(shell_bytes)
            (pb / "Data" / "Interface" / "pipboybootsequence.swf").write_bytes(boot_bytes)
            (pb / "Data" / "Scripts" / "FO4SF_PipboyTravel.pex").write_bytes(pex_bytes)
            (pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").write_bytes(bundle_pb_dll)
            (pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").write_bytes(bundle_pb_ini)
            (pb / "SFSE" / "Plugins" / "FO4SFPipboyMapMarkers.tsv").write_bytes(bundle_markers)
            (pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.build.json").write_bytes(bundle_build_json)
            (pb / "plan.json").write_text(
                json.dumps(
                    {
                        "kind": "pipboy-stack-stage",
                        "plugins": ["FO4SFPipboyProbe.esm", "FO4SFPipboyTravel.esm"],
                        "files": {
                            "FO4SFPipboyProbe.esm": {"sha256": p1_sha},
                            "FO4SFPipboyTravel.esm": {"sha256": p2_sha},
                            "Data/Interface/FO4SF_Fo4Shell.swf": {"sha256": _sha256_bytes(shell_bytes)},
                            "Data/Interface/pipboybootsequence.swf": {"sha256": _sha256_bytes(boot_bytes)},
                            "Data/Scripts/FO4SF_PipboyTravel.pex": {"sha256": _sha256_bytes(pex_bytes)},
                        },
                    },
                    indent=1,
                ),
                encoding="utf-8",
            )

            bundle_dir = root / "bundle-h3"
            self.assertEqual(
                mcb.main(
                    [
                        "fold",
                        "--owner-set", str(owner),
                        "--stages-root", str(stages_root),
                        "--out", str(bundle_dir),
                        "--port", str(port_esm),
                        "--with-pipboy",
                        "--pipboy-stage", str(pb),
                    ],
                    system=_FakeSystemClosed(),
                ),
                0,
            )

            # Synthetic game fixture with pre-existing owner Pip-Boy DLL/INI + unrelated Border/AddressLibrary files
            fake_sf = root / "FakeStarfield"
            sf_plugins = fake_sf / "Data" / "SFSE" / "Plugins"
            sf_plugins.mkdir(parents=True)
            owner_pb_dll = b"MZ_OWNER_ORIGINAL_PIPBOY_DLL_BYTES"
            owner_pb_ini = b"[FO4SFPipboyMenu]\nOwnerCustomKey=1\n"
            owner_border_dll = b"MZ_OWNER_BORDER_DLL"
            owner_addrlib = b"ADDRLIB_1_16_244_0_BIN"
            (sf_plugins / "FO4SFPipboyMenu.dll").write_bytes(owner_pb_dll)
            (sf_plugins / "FO4SFPipboyMenu.ini").write_bytes(owner_pb_ini)
            (sf_plugins / "FO4SFBorder.dll").write_bytes(owner_border_dll)
            (sf_plugins / "versionlib-1-16-244-0.bin").write_bytes(owner_addrlib)

            # 1. Refuses when Starfield.exe is running or process check fails
            self.assertEqual(
                mcb.main(
                    ["sidecar-install", "--bundle-dir", str(bundle_dir), "--starfield", str(fake_sf)],
                    system=_FakeSystemOpen(),
                ),
                2,
            )
            self.assertEqual(
                mcb.main(
                    ["sidecar-install", "--bundle-dir", str(bundle_dir), "--starfield", str(fake_sf)],
                    system=_FakeSystemBroken(),
                ),
                2,
            )
            self.assertFalse((fake_sf / "Data" / mcb.SIDECAR_RECEIPT_NAME).exists())
            self.assertEqual((sf_plugins / "FO4SFPipboyMenu.dll").read_bytes(), owner_pb_dll)

            # 2. Installs sidecar, backs up overwritten files outside SFSE/Plugins, skips reputation/
            self.assertEqual(
                mcb.main(
                    ["sidecar-install", "--bundle-dir", str(bundle_dir), "--starfield", str(fake_sf)],
                    system=_FakeSystemClosed(),
                ),
                0,
            )
            rec_path = fake_sf / "Data" / mcb.SIDECAR_RECEIPT_NAME
            bak_dir = fake_sf / "Data" / "SFSE" / mcb.SIDECAR_BACKUP_DIRNAME
            self.assertTrue(rec_path.is_file())
            self.assertTrue(bak_dir.is_dir())
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
            self.assertTrue(rec["complete"])
            self.assertEqual(len(rec["overwritten"]), 2)
            self.assertEqual(len(rec["added"]), 3)  # FO4SFCombat.dll,MapMarkers.tsv,build.json
            self.assertIn("reputation/FO4SFPipboyKit.ini", rec["not_installed_reference_only"])
            self.assertFalse((sf_plugins / "FO4SFPipboyKit.ini").exists())
            self.assertFalse((fake_sf / "Data" / "reputation").exists())
            self.assertEqual([p.name for p in sf_plugins.glob("*.bak")], [])
            self.assertEqual((sf_plugins / "FO4SFPipboyMenu.dll").read_bytes(), bundle_pb_dll)
            self.assertEqual((sf_plugins / "FO4SFCombat.dll").read_bytes(), b"MZ_SYNTHETIC_COMBAT_DLL")
            self.assertEqual((sf_plugins / "FO4SFBorder.dll").read_bytes(), owner_border_dll)
            self.assertEqual((sf_plugins / "versionlib-1-16-244-0.bin").read_bytes(), owner_addrlib)

            # 3. Second sidecar-install refuses when receipt already exists
            self.assertEqual(
                mcb.main(
                    ["sidecar-install", "--bundle-dir", str(bundle_dir), "--starfield", str(fake_sf)],
                    system=_FakeSystemClosed(),
                ),
                2,
            )

            # 4. Simulate mid-session INI edit (Card B / Card C) and verify undo refuses running game
            (sf_plugins / "FO4SFPipboyMenu.ini").write_bytes(b"[FO4SFPipboyMenu]\nRequirePickup=0\n")
            self.assertEqual(
                mcb.main(["sidecar-undo", "--starfield", str(fake_sf)], system=_FakeSystemOpen()),
                2,
            )
            self.assertTrue(rec_path.is_file())

            # 5. Corrupting backup sha256 refuses undo BEFORE mutating target files
            first_bak = bak_dir / rec["overwritten"][0]["backup_file"]
            orig_bak_bytes = first_bak.read_bytes()
            first_bak.write_bytes(b"CORRUPTED_BACKUP")
            self.assertEqual(
                mcb.main(["sidecar-undo", "--starfield", str(fake_sf)], system=_FakeSystemClosed()),
                2,
            )
            self.assertEqual((sf_plugins / "FO4SFCombat.dll").read_bytes(), b"MZ_SYNTHETIC_COMBAT_DLL")
            first_bak.write_bytes(orig_bak_bytes)

            # 6. Clean sidecar-undo restores backed-up owner bytes, removes only added files, keeps neighbors
            self.assertEqual(
                mcb.main(["sidecar-undo", "--starfield", str(fake_sf)], system=_FakeSystemClosed()),
                0,
            )
            self.assertFalse(rec_path.exists())
            self.assertFalse(bak_dir.exists())
            self.assertEqual((sf_plugins / "FO4SFPipboyMenu.dll").read_bytes(), owner_pb_dll)
            self.assertEqual((sf_plugins / "FO4SFPipboyMenu.ini").read_bytes(), owner_pb_ini)
            self.assertFalse((sf_plugins / "FO4SFCombat.dll").exists())
            self.assertFalse((sf_plugins / "FO4SFPipboyMapMarkers.tsv").exists())
            self.assertFalse((sf_plugins / "FO4SFPipboyMenu.build.json").exists())
            self.assertEqual((sf_plugins / "FO4SFBorder.dll").read_bytes(), owner_border_dll)
            self.assertEqual((sf_plugins / "versionlib-1-16-244-0.bin").read_bytes(), owner_addrlib)
            self.assertEqual(
                mcb.main(["sidecar-undo", "--starfield", str(fake_sf)], system=_FakeSystemClosed()),
                2,
            )

    def test_s1_refresh_pipboy_stage_stages_setup_screen_start_card_and_start_places_json(self):
        ui_dir = str(REPO / "scripts" / "ui")
        if ui_dir not in sys.path:
            sys.path.insert(0, ui_dir)
        import make_probe_swf  # type: ignore

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src_pb = root / "src-pb"
            (src_pb / "Data" / "Interface").mkdir(parents=True)
            (src_pb / "Data" / "Scripts").mkdir(parents=True)
            (src_pb / "SFSE" / "Plugins").mkdir(parents=True)
            p1_sha = _make_tes4_esm(src_pb / "FO4SFPipboyProbe.esm", extra_tag=b"pbprobe")
            p2_sha = _make_tes4_esm(src_pb / "FO4SFPipboyTravel.esm", extra_tag=b"pbtravel")
            shell_swf = make_probe_swf.movie_bytes()
            (src_pb / "Data" / "Interface" / "FO4SF_Fo4Shell.swf").write_bytes(shell_swf)
            pex_bytes = b"PEX_TRAVEL"
            (src_pb / "Data" / "Scripts" / "FO4SF_PipboyTravel.pex").write_bytes(pex_bytes)
            (src_pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").write_bytes(b"MZ_SYNTHETIC_PIPBOY_DLL")
            (src_pb / "plan.json").write_text(
                json.dumps(
                    {
                        "kind": "pipboy-stack-stage",
                        "plugins": ["FO4SFPipboyProbe.esm", "FO4SFPipboyTravel.esm"],
                        "files": {
                            "FO4SFPipboyProbe.esm": {"sha256": p1_sha},
                            "FO4SFPipboyTravel.esm": {"sha256": p2_sha},
                            "Data/Interface/FO4SF_Fo4Shell.swf": {"sha256": _sha256_bytes(shell_swf)},
                            "Data/Scripts/FO4SF_PipboyTravel.pex": {"sha256": _sha256_bytes(pex_bytes)},
                        },
                    },
                    indent=1,
                ),
                encoding="utf-8",
            )

            refreshed = root / "16-pipboy-refreshed"
            mcb.refresh_pipboy_stage_for_bundle(str(src_pb), str(refreshed), str(root / "no-fo4-data"))
            self.assertTrue((refreshed / "Data" / "Interface" / "FO4SF_StartCard.swf").is_file())
            self.assertTrue((refreshed / "Data" / "Interface" / "FO4SF_SetupScreen.swf").is_file())
            self.assertTrue((refreshed / "SFSE" / "Plugins" / "FO4SFStartPlaces.json").is_file())
            ini_txt = (refreshed / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
            self.assertIn("SetupShowUnavailable=0", ini_txt)

            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)
            out_b = root / "bundle-s1"
            self.assertEqual(
                mcb.main(
                    [
                        "fold",
                        "--owner-set", str(owner),
                        "--stages-root", str(stages_root),
                        "--out", str(out_b),
                        "--port", str(port_esm),
                        "--with-pipboy",
                        "--pipboy-stage", str(refreshed),
                    ],
                    system=_FakeSystemClosed(),
                ),
                0,
            )
            self.assertTrue((out_b / "Data" / "Interface" / "FO4SF_SetupScreen.swf").is_file())
            self.assertTrue((out_b / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFStartPlaces.json").is_file())
            bplan = json.loads((out_b / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertIn("Data/Interface/FO4SF_SetupScreen.swf", bplan["components"]["pipboy"]["outputs"])
            self.assertIn("SFSE/Plugins/FO4SFStartPlaces.json", bplan["sfse_sidecar"])
            self.assertEqual(mcb.main(["verify", "--bundle-dir", str(out_b), "--port", str(port_esm)]), 0)

    @unittest.skipUnless(os.environ.get("FO4SF_DOTNET_TESTS") == "1", "FO4SF_DOTNET_TESTS!=1")
    def test_dotnet_core_candidate_selftest(self):
        with tempfile.TemporaryDirectory() as td:
            proj = REPO / "dotnet" / "CoreCandidate"
            r = subprocess.run(["dotnet", "run", "--project", str(proj), "--", "selftest", td],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, msg=r.stderr + "\n" + r.stdout)
            self.assertIn("selftest: ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
