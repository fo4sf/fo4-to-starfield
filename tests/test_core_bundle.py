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

        add_stage("01-cog-door", "FO4SFVaultGearDoor.esm", masters=("Starfield.esm", "FO4Port.esm"),
                  extra_files={"Data/materials/fo4port/_neutral.mat": shared_mat,
                               "Data/meshes/fo4port/door_anim.nif": b"DOOR_NIF"})
        add_stage("02-exit-lift", "FO4SFExitLift.esm", masters=("Starfield.esm", "FO4Port.esm"),
                  extra_files={"Data/materials/fo4port/_neutral.mat": shared_mat,
                               "Data/meshes/fo4port/lift_anim.nif": b"LIFT_NIF"})
        add_stage("03-newgame", "FO4SFNewGame.esm", pex_name="FO4SF_NewGameQuest")
        add_stage("04-rads", "FO4SFRads.esm", pex_name="FO4SF_RadsCoreQuest")
        add_stage("05-hardcore", "FO4SFHardcore.esm", pex_name="FO4SF_HardcoreQuest")
        add_stage("06-workshop", "FO4SFWorkshop.esm", pex_name="FO4SF_WorkshopCoreQuest")
        add_stage("07-powerarmor", "FO4SFPowerArmor.esm", pex_name="FO4SF_PowerArmorCoreQuest")
        add_stage("08-progression", "FO4SFProgression.esm", pex_name="FO4SF_ProgressionQuest")
        add_stage("09-list-dialogue", "FO4SFListDialogue.esm", pex_name="FO4SF_ListDialogueQuest")

        # 10-combat with FO4SFCombat.dll SFSE sidecar
        add_stage("10-combat", "FO4SFCombat.esm", pex_name="FO4SF_CombatQuest",
                  extra_files={"Data/Scripts/FO4SF_CombatInput.pex": b"PEX:FO4SF_CombatInput"})
        combat_sc = stages_root / "10-combat" / "sfse_sidecar"
        combat_sc.mkdir(parents=True, exist_ok=True)
        (combat_sc / "FO4SFCombat.dll").write_bytes(b"MZ_SYNTHETIC_COMBAT_DLL")

        # 11-reputation with Pip-Boy INI/JSON/TSV sidecar manifests
        add_stage("11-reputation", "FO4SFReputation.esm", pex_name="FO4SF_ReputationQuest")
        (stages_root / "11-reputation" / "FO4SFPipboyMenu.reputation.ini").write_text("[Page STAT/KARMA]\n", encoding="utf-8")

        # 12-companions & 13-alife
        add_stage("12-companions", "FO4SFCompanions.esm", pex_name="FO4SF_CompanionsQuest")
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
        add_stage("15-candidate-walk", "FO4SFCoreCandidate.esm", pex_name="FO4SF_CoreCandidateWalk")

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
                "--with-pipboy", "--pipboy-stage", str(pb),
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
            self.assertEqual(len(bplan["plugins"]), 21)
            self.assertEqual(
                bplan["plugins"][:4],
                ["FO4ActorRaider.esm", "FO4TerrainCore.esm", "FO4SFMission.esm", "FO4TerrainCore_Mars.esm"],
            )
            # SFSE DLLs & Reputation manifests kept outside Data/ so Archive2 never packs them into Main.ba2
            self.assertTrue((out / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").is_file())
            self.assertTrue((out / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFCombat.dll").is_file())
            self.assertTrue((out / "sfse_sidecar" / "reputation" / "FO4SFPipboyMenu.reputation.ini").is_file())
            self.assertFalse((out / "Data" / "SFSE").exists())

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
            held_lines = [f"FO4SF_NEWGAME rt=1.5 held off Quest_{i:03d} running_after=False pass={(1 if i < 100 else 2)}"
                          for i in range(195)]
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
