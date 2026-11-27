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
from fo4sf.beginning_pilot import (  # noqa: E402
    B5_REQUIRED_ACTOR_NIFS,
    CODSWORTH_VOICE_DIR_REL,
    MIN_CODSWORTH_WEMS,
)
from fo4sf.core import bundle_log  # noqa: E402
from fo4sf.core.start_worlds import START_WORLD_TABLE, get_start_world  # noqa: E402
from fo4sf.planet.esm import ESM, PluginWriter, Record, zbytes  # noqa: E402


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_mission_esm(
    path: Path,
    masters: tuple[str, ...] = ("Starfield.esm", "FO4TerrainCore.esm", "FO4ActorRaider.esm"),
    omitted_nifs: tuple[str, ...] = (),
) -> str:
    """Write a minimal valid FO4SFMission.esm with ARMA MOD2 records for B5 actor NIFs."""
    w = PluginWriter(masters, flags=ESM, author="fo4-to-starfield Mission")
    omit_low = {o.casefold() for o in omitted_nifs}
    for idx, (_label, rel) in enumerate(B5_REQUIRED_ACTOR_NIFS):
        if rel.casefold() in omit_low:
            continue
        mod_rel = rel[len("meshes/"):] if rel.startswith("meshes/") else rel
        w.add(
            Record(
                b"ARMA",
                w.own(0x000812 + idx),
                [(b"EDID", zbytes(f"FO4_AA_B5_{idx}")), (b"MOD2", zbytes(mod_rel.replace("/", "\\")))],
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

        # Stale FO4SFNewGame.esm + 4 PEX + stale pre-folded FO4SFMission scripts/mats/voice that clean-core MUST strip
        _make_tes4_esm(owner / "FO4SFNewGame.esm", extra_tag=b"old-newgame")
        for s in ("Quest", "Looks", "Special", "Version"):
            (owner / "Data" / "Scripts" / f"FO4SF_NewGame{s}.pex").write_bytes(f"old-{s}".encode("ascii"))
        (owner / "Data" / "Scripts" / "FO4SF_Min00Quest.pex").write_bytes(b"old-min00")
        (owner / "Data" / "Scripts" / "FO4SF_COMPreston.pex").write_bytes(b"old-compreston")
        old_handy_dir = owner / "Data" / "materials" / "fo4port" / "texsets" / "actors" / "handy"
        old_handy_dir.mkdir(parents=True, exist_ok=True)
        (old_handy_dir / "handyarmor_d_8e98a175.mat").write_bytes(b"OLD_BLACK_STEEL_MAT")
        old_voice_dir = owner / "Data" / "sound" / "voice" / "fo4sfmission.esm" / "robotminibota"
        old_voice_dir.mkdir(parents=True, exist_ok=True)
        (old_voice_dir / "00f4c001.wem").write_bytes(b"OLD_MINIBOT_WEM")

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
        add_stage("02-exit-lift", "FO4SFExitLift.esm", masters=("Starfield.esm", "FO4Port.esm", "FO4TerrainCore.esm"),
                  extra_files={"Data/materials/fo4port/_neutral.mat": shared_mat,
                               "Data/meshes/fo4port/lift_anim.nif": b"LIFT_NIF"})

        pod_st = stages_root / "02c-vault-pod"
        pod_st.mkdir(parents=True, exist_ok=True)
        pod_w = PluginWriter(("Starfield.esm", "FO4Port.esm"), flags=ESM, author="fo4-to-starfield VaultPod")
        pod_w.add(
            Record(
                b"ACTI",
                pod_w.own(0x000800),
                [
                    (b"EDID", zbytes("FO4SF_PlayerCryoPod")),
                    (b"OBND", struct.pack("<6f", -1.0, -1.0, 0.0, 1.0, 1.0, 2.5)),
                    (b"MODL", zbytes(r"fo4port\pod\cryopod01.nif")),
                    (b"ANAM", zbytes(r"Actors\Character\Animation\StateMachines\ActivatorStateGraph01.agx")),
                    (b"BNAM", zbytes(r"fo4port\pod\rig.hkt")),
                    (b"CNAM", zbytes(r"fo4port\pod\clips")),
                ],
                0, 0, 581, 0,
            )
        )
        def _pod_sub(sig: bytes, data: bytes) -> bytes:
            return sig + struct.pack("<H", len(data)) + data
        def _pod_rec(sig: bytes, fid: int, subs: list[bytes], flags: int = 0) -> bytes:
            body = b"".join(subs)
            return sig + struct.pack("<IIIII", len(body), flags, fid, 0, 0) + body
        def _pod_grup(label: bytes, gtype: int, payload: bytes) -> bytes:
            return b"GRUP" + struct.pack("<I", 24 + len(payload)) + label + struct.pack("<III", gtype, 0, 0) + payload
        cell_fid = (1 << 24) | 0x0011F3
        cell_rec = _pod_rec(b"CELL", cell_fid, [_pod_sub(b"EDID", zbytes("FO4Port_Vault111Cryo"))], flags=0x00000401)
        refr_801 = _pod_rec(b"REFR", pod_w.own(0x000801), [_pod_sub(b"NAME", struct.pack("<I", pod_w.own(0x000800)))], flags=0x00000400)
        refr_1617 = _pod_rec(b"REFR", (1 << 24) | 0x001617, [_pod_sub(b"NAME", struct.pack("<I", (1 << 24) | 0x000855))], flags=0x00000800)
        pod_esm_bytes = pod_w.to_bytes(compress=False) + _pod_grup(b"CELL", 0, cell_rec + _pod_grup(struct.pack("<I", cell_fid), 6, refr_801 + refr_1617))
        (pod_st / "FO4SFVaultPod.esm").write_bytes(pod_esm_bytes)
        pod_outputs = {"FO4SFVaultPod.esm": _sha256_bytes(pod_esm_bytes)}
        pod_extra: dict[str, bytes] = {
            "Data/materials/fo4port/_neutral.mat": shared_mat,
            "Data/meshes/fo4port/pod/cryopod01.nif": b"POD_NIF",
            "Data/meshes/fo4port/pod/rig.hkt": b"POD_RIG",
        }
        for clip in ("statea_play.af", "statea_play.afx", "stateb_play.af", "stateb_play.afx",
                     "statea_idle.af", "statea_idle.afx", "stateb_idle.af", "stateb_idle.afx"):
            pod_extra[f"Data/meshes/fo4port/pod/clips/{clip}"] = f"POD_CLIP:{clip}".encode("ascii")
        for rel, raw in pod_extra.items():
            fp = pod_st / Path(*rel.split("/"))
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_bytes(raw)
            pod_outputs[rel] = _sha256_bytes(raw)
        (pod_st / "plan.json").write_text(
            json.dumps({"plugin": "FO4SFVaultPod.esm", "plugins": ["FO4SFVaultPod.esm"], "outputs": pod_outputs}, indent=1),
            encoding="utf-8",
        )
        mission_extra = {
            "Data/Scripts/FO4SF_COMPreston.pex": b"PEX:FO4SF_COMPreston",
            "Data/Scripts/FO4SF_Codsworth01Quest.pex": b"PEX:FO4SF_Codsworth01Quest",
            "Data/Scripts/FO4SF_Sanctuary01Quest.pex": b"PEX:FO4SF_Sanctuary01Quest",
            "Data/materials/fo4port/_neutral.mat": shared_mat,
            "Data/materials/fo4port/texsets/actors/handy/handyarmor_d_8e98a175.mat": b"PATCHED_BRUSHED_STEEL_MAT",
        }
        for _lbl, nif_rel in B5_REQUIRED_ACTOR_NIFS:
            mission_extra[f"Data/{nif_rel}"] = f"NIF:{nif_rel}".encode("ascii")
        for w_idx in range(1, MIN_CODSWORTH_WEMS + 1):
            mission_extra[f"Data/{CODSWORTH_VOICE_DIR_REL}/00f4c{w_idx:03x}.wem"] = f"WEM:{w_idx}".encode("ascii")

        ms_st = stages_root / "02b-mission"
        ms_st.mkdir(parents=True, exist_ok=True)
        ms_esm_sha = _make_mission_esm(ms_st / "FO4SFMission.esm")
        ms_outputs = {"FO4SFMission.esm": ms_esm_sha}
        ms_pex_bytes = b"PEX:FO4SF_Min00Quest"
        (ms_st / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
        (ms_st / "Data" / "Scripts" / "FO4SF_Min00Quest.pex").write_bytes(ms_pex_bytes)
        ms_outputs["Data/Scripts/FO4SF_Min00Quest.pex"] = _sha256_bytes(ms_pex_bytes)
        for rel, raw in mission_extra.items():
            fp = ms_st / Path(*rel.split("/"))
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_bytes(raw)
            ms_outputs[rel] = _sha256_bytes(raw)
        (ms_st / "plan.json").write_text(
            json.dumps({"plugin": "FO4SFMission.esm", "plugins": ["FO4SFMission.esm"], "outputs": ms_outputs}, indent=1),
            encoding="utf-8",
        )
        add_stage(
            "03-newgame",
            "FO4SFNewGame.esm",
            pex_name="FO4SF_NewGameQuest",
            masters=("Starfield.esm", "FO4SFCoreValues.esm"),
            extra_files={
                "Data/Scripts/FO4SF_NewGameLooks.pex": b"PEX:FO4SF_NewGameLooks",
                "Data/Scripts/FO4SF_NewGameSpecial.pex": b"PEX:FO4SF_NewGameSpecial",
            },
        )
        add_stage("04-rads", "FO4SFRads.esm", pex_name="FO4SF_RadsCoreQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        add_stage("05-hardcore", "FO4SFHardcore.esm", pex_name="FO4SF_HardcoreQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        add_stage("06-workshop", "FO4SFWorkshop.esm", pex_name="FO4SF_WorkshopCoreQuest",
                  masters=("Starfield.esm", "FO4SFCoreValues.esm"))
        rl_st = stages_root / "17-route-loot"
        rl_st.mkdir(parents=True, exist_ok=True)
        rl_sha = _make_tes4_esm(
            rl_st / "FO4SFRouteLoot.esm",
            masters=(
                "Starfield.esm",
                "FO4SFCoreValues.esm",
                "FO4SFRads.esm",
                "FO4SFWorkshop.esm",
                "FO4TerrainCore.esm",
                "FO4Port.esm",
            ),
            extra_tag=b"FO4SFRouteLoot.esm",
        )
        (rl_st / "census.json").write_text("{\"route_containers_with_non_credit_items\": 439}\n", encoding="utf-8")
        (rl_st / "plan.json").write_text(
            json.dumps({
                "kind": "route-loot",
                "plugin": "FO4SFRouteLoot.esm",
                "plugin_sha256": rl_sha,
            }, indent=1),
            encoding="utf-8",
        )
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

            # Source owner-set README.txt was NEVER mutated; stale NewGame & Mission files stripped from clean_out
            self.assertEqual((owner / "README.txt").read_bytes(), owner_readme_before)
            self.assertFalse((clean_out / "FO4SFNewGame.esm").exists())
            self.assertFalse((clean_out / "FO4SFMission.esm").exists())
            self.assertFalse((clean_out / "Data" / "Scripts" / "FO4SF_Min00Quest.pex").exists())
            self.assertFalse((clean_out / "Data" / "Scripts" / "FO4SF_COMPreston.pex").exists())
            self.assertFalse((clean_out / "Data" / "sound" / "voice" / "fo4sfmission.esm" / "robotminibota").exists())

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
            self.assertFalse(bplan["with_route_loot"])
            self.assertEqual(len(bplan["plugins"]), 23)
            self.assertEqual(bplan["plugins"], list(mcb.CORE_BUNDLE_PLUGINS))
            self.assertIn("FO4SFCoreValues.esm", bplan["plugins"])
            self.assertIn("FO4SFVaultPod.esm", bplan["plugins"])
            self.assertIn("FO4SFMission.esm", bplan["plugins"])
            self.assertNotIn("FO4SFRouteLoot.esm", bplan["plugins"])
            self.assertLess(bplan["plugins"].index("FO4SFCoreValues.esm"), bplan["plugins"].index("FO4SFNewGame.esm"))
            self.assertLess(bplan["plugins"].index("FO4TerrainCore.esm"), bplan["plugins"].index("FO4SFMission.esm"))
            self.assertEqual(
                bplan["plugins"][:3],
                ["FO4ActorRaider.esm", "FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm"],
            )
            self.assertEqual(
                (out / "Data" / "materials" / "fo4port" / "texsets" / "actors" / "handy" / "handyarmor_d_8e98a175.mat").read_bytes(),
                b"PATCHED_BRUSHED_STEEL_MAT",
            )
            for s_pex in ("FO4SF_Min00Quest.pex", "FO4SF_COMPreston.pex", "FO4SF_Codsworth01Quest.pex", "FO4SF_Sanctuary01Quest.pex"):
                self.assertTrue((out / "Data" / "Scripts" / s_pex).is_file())
            self.assertTrue((out / "Data" / "sound" / "voice" / "fo4sfmission.esm" / "fo4sf_codsworthvoice" / "00f4c001.wem").is_file())
            self.assertFalse((out / "Data" / "sound" / "voice" / "fo4sfmission.esm" / "robotminibota").exists())

            # SFSE DLLs & Reputation manifests kept outside Data/ so Archive2 never packs them into Main.ba2
            self.assertTrue((out / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").is_file())
            shipped_pb_ini = (out / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
            self.assertNotIn("[Kit]", shipped_pb_ini)
            self.assertNotIn("[Page ", shipped_pb_ini)
            self.assertIn("MapHeadingAt=88", shipped_pb_ini)
            self.assertTrue((out / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFCombat.dll").is_file())
            self.assertTrue((out / "sfse_sidecar" / "reputation" / "FO4SFPipboyKit.ini").is_file())
            self.assertFalse((out / "Data" / "SFSE").exists())

            # T1 opt-in on --profile test: --with-route-loot folds FO4SFRouteLoot.esm -> 24 plugins
            out_test_rl = root / "bundle-test-with-rl"
            rc_test_rl = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(out_test_rl), "--port", str(port_esm),
                "--profile", "test", "--with-route-loot", "--with-pipboy", "--pipboy-stage", str(pb),
            ], system=_FakeSystemClosed())
            self.assertEqual(rc_test_rl, 0)
            tplan_rl = json.loads((out_test_rl / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertTrue(tplan_rl["with_route_loot"])
            self.assertEqual(len(tplan_rl["plugins"]), 24)
            self.assertEqual(tplan_rl["plugins"], list(mcb.CORE_WITH_ROUTE_LOOT_PLUGINS))
            self.assertLess(tplan_rl["plugins"].index("FO4SFMission.esm"), tplan_rl["plugins"].index("FO4SFRouteLoot.esm"))

            # W1 + A17 + T1: Default profile for fold (when --profile is omitted) is Track-1 'player' -> 14 plugins
            out_player = root / "bundle-player"
            rc_player = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--mission-stage", str(stages_root / "02b-mission"),
                "--route-loot-stage", str(stages_root / "17-route-loot"),
                "--out", str(out_player), "--port", str(port_esm),
                "--with-pipboy", "--pipboy-stage", str(pb),
            ], system=_FakeSystemClosed())
            self.assertEqual(rc_player, 0)
            pplan = json.loads((out_player / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(pplan["profile"], "player")
            self.assertFalse(pplan["with_route_loot"])
            self.assertFalse(pplan["with_experimental_core"])
            self.assertEqual(len(pplan["plugins"]), 14)
            self.assertEqual(pplan["plugins"], list(mcb.PLAYER_BUNDLE_PLUGINS))
            self.assertNotIn("FO4SFCoreCandidate.esm", pplan["plugins"])
            self.assertNotIn("FO4SFRouteLoot.esm", pplan["plugins"])
            self.assertFalse((out_player / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFCombat.dll").exists())

            # Opt-in --with-experimental-core + --with-route-loot on player profile -> 23 plugins
            out_player_rl = root / "bundle-player-with-rl"
            rc_player_rl = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--mission-stage", str(stages_root / "02b-mission"),
                "--route-loot-stage", str(stages_root / "17-route-loot"),
                "--out", str(out_player_rl), "--port", str(port_esm),
                "--with-pipboy", "--pipboy-stage", str(pb), "--with-experimental-core", "--with-route-loot",
            ], system=_FakeSystemClosed())
            self.assertEqual(rc_player_rl, 0)
            pplan_rl = json.loads((out_player_rl / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertTrue(pplan_rl["with_route_loot"])
            self.assertTrue(pplan_rl["with_experimental_core"])
            self.assertEqual(len(pplan_rl["plugins"]), 23)
            self.assertEqual(pplan_rl["plugins"], list(mcb.PLAYER_WITH_ROUTE_LOOT_PLUGINS))
            # Tampering with_route_loot=False on a player bundle holding FO4SFRouteLoot.esm must fail verify
            pplan_rl["with_route_loot"] = False
            (out_player_rl / "bundle_plan.json").write_text(json.dumps(pplan_rl, indent=1), encoding="utf-8")
            v_probs_rl, _ = mcb.verify_bundle(str(out_player_rl), port_esm=str(port_esm))
            self.assertTrue(any("FO4SFRouteLoot.esm" in p for p in v_probs_rl))

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

    def test_refuses_output_inside_git_worktree_or_game_folder(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)

            # 1. Output inside Git worktree (REPO) must be refused (R4)
            in_repo_out = REPO / "forbidden-bundle-out"
            self.assertFalse(in_repo_out.exists())
            rc_git = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(in_repo_out), "--port", str(port_esm),
            ], system=_FakeSystemClosed())
            self.assertEqual(rc_git, 2)
            self.assertFalse(in_repo_out.exists())

            # 2. Output inside a Starfield game install folder must be refused (R4)
            fake_game = root / "FakeStarfield"
            fake_game.mkdir()
            (fake_game / "Starfield.exe").write_bytes(b"MZ")
            in_game_out = fake_game / "sub" / "bundle-out"
            rc_game = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(in_game_out), "--port", str(port_esm),
            ], system=_FakeSystemClosed())
            self.assertEqual(rc_game, 2)
            self.assertFalse(in_game_out.exists())

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
                        "out": str(root / "out-spy"),
                        "render_python": None,
                        "starfield_dir": str(root / "sf"),
                        "port": str(port_esm),
                        "owner_set": str(owner),
                        "profile": prof,
                        "commonlibsf": None,
                        "msvc_env": None,
                        "allow_starfield_standins": True,
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
                        "--with-experimental-core",
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


    def test_t0b_make_map_markers_stage_packs_archive_and_respects_no_archive(self) -> None:
        import subprocess
        import unittest.mock
        import make_core_bundle  # type: ignore

        mm_dir = Path(make_core_bundle.REPO) / "scripts" / "mapmarkers"
        if str(mm_dir) not in sys.path:
            sys.path.insert(0, str(mm_dir))
        import make_map_markers  # type: ignore
        try:
            from tests.ba2_fixture import general_archive
        except ModuleNotFoundError:
            from ba2_fixture import general_archive

        pex_bytes = _build_minimal_pex(
            "FO4SF_MapMarkers",
            ("PrepareKnownUndiscoveredSingle", "PrepareKnownUndiscoveredAll", "DiscoverSingleMarker", "SuppressArrivalDarkHold"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core_esm = root / "FO4TerrainCore.esm"
            _make_tes4_esm(core_esm)

            fake_sf = root / "FakeStarfield"
            archive2_exe = fake_sf / "Tools" / "Archive2" / "Archive2.exe"
            archive2_exe.parent.mkdir(parents=True, exist_ok=True)
            archive2_exe.write_bytes(b"fake-archive2")
            (fake_sf / "Data").mkdir(parents=True, exist_ok=True)

            import zipfile

            fake_compiler = root / "PapyrusCompiler.exe"
            fake_compiler.write_bytes(b"fake-compiler")
            cr_zip = root / "ContentResources.zip"
            with zipfile.ZipFile(cr_zip, "w") as zf:
                for rel in (
                    "Scripts/Source/Actor.psc",
                    "Scripts/Source/Cell.psc",
                    "Scripts/Source/Debug.psc",
                    "Scripts/Source/Form.psc",
                    "Scripts/Source/Game.psc",
                    "Scripts/Source/GlobalVariable.psc",
                    "Scripts/Source/Location.psc",
                    "Scripts/Source/ObjectReference.psc",
                    "Scripts/Source/Quest.psc",
                    "Scripts/Source/ScriptObject.psc",
                    "Scripts/Source/Starfield_Papyrus_Flags.flg",
                    "Scripts/Source/Utility.psc",
                    "Scripts/Source/WorldSpace.psc",
                ):
                    zf.writestr(rel, f"; stub {rel}\n")

            def _fake_build_ba2(_ns, data_root, ba2_out):
                pex_in = Path(data_root) / "Scripts" / "FO4SF_MapMarkers.pex"
                Path(ba2_out).write_bytes(general_archive({"Scripts/FO4SF_MapMarkers.pex": pex_in.read_bytes()}))
                return ba2_out

            def _fake_subprocess_run(cmd, *args, **kwargs):
                cmd_s = [str(x) for x in cmd]
                if Path(cmd_s[0]).name.lower().startswith("dotnet"):
                    if "--out" in cmd_s:
                        mm_out = Path(cmd_s[cmd_s.index("--out") + 1])
                        mm_out.mkdir(parents=True, exist_ok=True)
                        _make_tes4_esm(mm_out / "FO4SFMapMarkers.esm", masters=("Starfield.esm", "FO4TerrainCore.esm"))
                        core_sha_val = make_core_bundle.sha256_file(str(core_esm))
                        (mm_out / "core.json").write_text(
                            json.dumps({"schema_version": 1, "masters": {"FO4TerrainCore.esm": core_sha_val}}) + "\n",
                            encoding="utf-8",
                        )
                        return unittest.mock.Mock(returncode=0, stdout="built FO4SFMapMarkers.esm\n", stderr="")
                    return unittest.mock.Mock(returncode=0, stdout="check ok\n", stderr="")
                for i, s_tok in enumerate(cmd_s):
                    if s_tok.startswith(("-o=", "-output=")):
                        out_dir = Path(s_tok.split("=", 1)[1])
                        break
                    if s_tok in ("-o", "-output") and i + 1 < len(cmd_s):
                        out_dir = Path(cmd_s[i + 1])
                        break
                else:
                    raise AssertionError(f"unexpected subprocess cmd: {cmd}")
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "FO4SF_MapMarkers.pex").write_bytes(pex_bytes)
                return unittest.mock.Mock(returncode=0, stdout="Compilation succeeded.\n", stderr="")

            with unittest.mock.patch.object(subprocess, "run", side_effect=_fake_subprocess_run), \
                 unittest.mock.patch.object(make_core_bundle.exp_install, "build_ba2", side_effect=_fake_build_ba2):
                out_with_ba2 = root / "mm-stage-with-ba2"
                make_map_markers.main([
                    "stage",
                    "--core", str(core_esm),
                    "--out", str(out_with_ba2),
                    "--compiler", str(fake_compiler),
                    "--content-resources", str(cr_zip),
                    "--starfield", str(fake_sf),
                    "--no-reload",
                ])
                self.assertTrue((out_with_ba2 / "FO4SFMapMarkers.esm").is_file())
                self.assertTrue((out_with_ba2 / "FO4SFMapMarkers - Main.ba2").is_file())
                self.assertTrue((out_with_ba2 / "Data" / "Scripts" / "FO4SF_MapMarkers.pex").is_file())
                self.assertTrue((out_with_ba2 / "core.json").is_file())

                out_no_ba2 = root / "mm-stage-no-ba2"
                make_map_markers.main([
                    "stage",
                    "--core", str(core_esm),
                    "--out", str(out_no_ba2),
                    "--compiler", str(fake_compiler),
                    "--content-resources", str(cr_zip),
                    "--starfield", str(fake_sf),
                    "--no-archive",
                    "--no-reload",
                ])
                self.assertTrue((out_no_ba2 / "FO4SFMapMarkers.esm").is_file())
                self.assertFalse((out_no_ba2 / "FO4SFMapMarkers - Main.ba2").exists())

    def test_t0b_fold_and_verify_stages_map_markers_keeps_plugins_and_checks_compatibility(self) -> None:
        import subprocess
        import make_core_bundle  # type: ignore
        try:
            from tests.ba2_fixture import general_archive
        except ModuleNotFoundError:
            from ba2_fixture import general_archive

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            owner, stages_root, *_rest = self._build_synthetic_owner_and_stages(root)
            core_sha = make_core_bundle.sha256_file(str(owner / "FO4TerrainCore.esm"))
            fresh_clean = root / "fresh-clean-core"

            # Baseline fold without map_markers (--no-map-markers) to assert plugins list is unchanged.
            out_base = root / "bundle-no-mm"
            self.assertEqual(
                make_core_bundle.main([
                    "fold",
                    "--owner-set", str(owner),
                    "--stages-root", str(stages_root),
                    "--out", str(out_base),
                    "--clean-core-out", str(fresh_clean),
                    "--profile", "player",
                    "--no-map-markers",
                ]),
                0,
            )
            base_plan = json.loads((out_base / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertNotIn("map_markers", base_plan["components"])
            missing_mm_probs, _ = make_core_bundle.verify_bundle(str(out_base), require_map_markers=True)
            self.assertTrue(any("missing map-markers/" in p for p in missing_mm_probs), missing_mm_probs)

            # Build valid 18-map-markers inside stages_root matching owner FO4TerrainCore.esm.
            mm_stage = stages_root / "18-map-markers"
            (mm_stage / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
            _make_tes4_esm(mm_stage / "FO4SFMapMarkers.esm", masters=("Starfield.esm", "FO4TerrainCore.esm"))
            mm_pex = _build_minimal_pex(
                "FO4SF_MapMarkers",
                ("PrepareKnownUndiscoveredSingle", "PrepareKnownUndiscoveredAll", "DiscoverSingleMarker", "DiscoverSingleMarkerSilent", "SuppressArrivalDarkHold"),
            )
            (mm_stage / "Data" / "Scripts" / "FO4SF_MapMarkers.pex").write_bytes(mm_pex)
            (mm_stage / "FO4SFMapMarkers - Main.ba2").write_bytes(
                general_archive({"Scripts/FO4SF_MapMarkers.pex": mm_pex})
            )
            (mm_stage / "core.json").write_text(
                json.dumps({"schema_version": 1, "masters": {"FO4TerrainCore.esm": core_sha}}, indent=2) + "\n",
                encoding="utf-8",
            )
            (mm_stage / "offline_check.txt").write_text("ok\n", encoding="utf-8")
            (mm_stage / "README.txt").write_text("readme\n", encoding="utf-8")

            out_with_mm = root / "bundle-with-mm"
            fresh_clean2 = root / "fresh-clean-core-2"
            self.assertEqual(
                make_core_bundle.main([
                    "fold",
                    "--owner-set", str(owner),
                    "--stages-root", str(stages_root),
                    "--out", str(out_with_mm),
                    "--clean-core-out", str(fresh_clean2),
                    "--profile", "player",
                ]),
                0,
            )
            mm_plan = json.loads((out_with_mm / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(mm_plan["plugins"], base_plan["plugins"])
            self.assertNotIn("FO4SFMapMarkers.esm", mm_plan["plugins"])
            self.assertEqual(mm_plan["components"]["map_markers"]["folder"], "map-markers")
            self.assertEqual(mm_plan["components"]["map_markers"]["plugins"], [])
            self.assertIn("map-markers", mm_plan["map_markers_install_command"])
            self.assertTrue((out_with_mm / "map-markers" / "FO4SFMapMarkers.esm").is_file())
            self.assertTrue((out_with_mm / "map-markers" / "FO4SFMapMarkers - Main.ba2").is_file())

            readme_lines = (out_with_mm / "README.txt").read_text(encoding="utf-8").splitlines()
            exp_install_lines = [ln for ln in readme_lines if "exp_install.py install" in ln]
            self.assertEqual(len(exp_install_lines), 1, readme_lines)
            self.assertTrue(any("map_markers_install.py install" in ln for ln in readme_lines), readme_lines)

            ok_probs, _ = make_core_bundle.verify_bundle(str(out_with_mm), require_map_markers=True)
            self.assertEqual(ok_probs, [])

            # CLI verify --require-map-markers passes.
            cli_ok = subprocess.run(
                [sys.executable, str(Path(make_core_bundle.REPO) / "scripts" / "core" / "make_core_bundle.py"),
                 "verify", "--bundle-dir", str(out_with_mm), "--require-map-markers"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(cli_ok.returncode, 0, cli_ok.stdout + cli_ok.stderr)

            # Outdated map-markers PEX lacking PrepareKnownUndiscoveredAll fails verify_bundle.
            old_pex = _build_minimal_pex("FO4SF_MapMarkers", ("DiscoverSingleMarker",))
            (out_with_mm / "map-markers" / "Data" / "Scripts" / "FO4SF_MapMarkers.pex").write_bytes(old_pex)
            (out_with_mm / "map-markers" / "FO4SFMapMarkers - Main.ba2").write_bytes(
                general_archive({"Scripts/FO4SF_MapMarkers.pex": old_pex})
            )
            bad_probs, _ = make_core_bundle.verify_bundle(str(out_with_mm), require_map_markers=True)
            self.assertTrue(
                any("PrepareKnownUndiscoveredAll" in p for p in bad_probs),
                bad_probs,
            )

            # _fold_map_markers_stage refuses stale core.json pin in 18-map-markers.
            (mm_stage / "core.json").write_text(
                json.dumps({"schema_version": 1, "masters": {"FO4TerrainCore.esm": "f" * 64}}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(make_core_bundle.BundleRefused) as ctx:
                make_core_bundle._fold_map_markers_stage(str(mm_stage), str(out_base))
            self.assertIn("core.json pins", str(ctx.exception))

    def test_t0b_resolve_map_markers_options_matches_core_sha_and_rejects_mismatch(self) -> None:
        import argparse
        import make_core_bundle  # type: ignore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            owner = root / "staging" / "owner"
            sibling_cs = root / "staging" / "terrain_core64v6i_l125"
            cw_json = root / "scratch" / "mapmarkers" / "cw_markers.json"
            owner.mkdir(parents=True)
            sibling_cs.mkdir(parents=True)
            cw_json.parent.mkdir(parents=True)

            core_esm = owner / "FO4TerrainCore.esm"
            _make_tes4_esm(core_esm)
            core_sha = make_core_bundle.sha256_file(str(core_esm))

            (sibling_cs / "FO4TerrainCore.esm").write_bytes(core_esm.read_bytes())
            (sibling_cs / "Data" / "terrain").mkdir(parents=True)
            (sibling_cs / "Data" / "terrain" / "fo4core.btd").write_bytes(b"btd")
            (sibling_cs / "overlays_params.json").write_text(
                json.dumps({
                    "overlays": [{
                        "btd_file": "Data/terrain/fo4core.btd",
                        "bounds_min_m": -2000.0,
                        "bounds_max_m": 4000.0,
                        "map_markers": [],
                    }]
                }),
                encoding="utf-8",
            )
            cw_json.write_text('{"markers": []}\n', encoding="utf-8")

            ns = argparse.Namespace(
                owner_set=str(owner),
                map_markers_core_stage=None,
                fo4_map_markers=None,
                map_markers_landing=None,
            )
            cs, mm_json, landing = make_core_bundle._resolve_map_markers_options(ns, str(core_esm), core_sha)
            self.assertEqual(Path(cs), sibling_cs)
            self.assertEqual(Path(mm_json), cw_json)
            self.assertEqual(landing, (-1959.0, -493.0))

            # Explicit mismatching core stage refuses clearly.
            (sibling_cs / "FO4TerrainCore.esm").write_bytes(b"different-core")
            ns_bad = argparse.Namespace(
                owner_set=str(owner),
                map_markers_core_stage=str(sibling_cs),
                fo4_map_markers=None,
                map_markers_landing=None,
            )
            with self.assertRaises(make_core_bundle.BundleRefused):
                make_core_bundle._resolve_map_markers_options(ns_bad, str(core_esm), core_sha)

    def test_g2_b5_missing_nifs_and_mat_textures_refuse_verify_and_fold(self) -> None:
        from unittest import mock
        try:
            from tests.ba2_fixture import general_archive
        except ModuleNotFoundError:
            from ba2_fixture import general_archive

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)

            # 1. Baseline player fold succeeds when all 4 canonical B5 NIFs are in FO4SFMission.esm + Data/
            out_ok = root / "bundle-b5-ok"
            rc_ok = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(out_ok), "--port", str(port_esm), "--profile", "player",
            ], system=_FakeSystemClosed())
            self.assertEqual(rc_ok, 0)

            # verify_bundle directly invokes verify_bundle_beginning_readiness for player + mission
            with mock.patch.object(mcb, "verify_bundle_beginning_readiness", wraps=mcb.verify_bundle_beginning_readiness) as spy:
                probs_ok, _ = mcb.verify_bundle(str(out_ok), port_esm=str(port_esm))
                self.assertEqual(probs_ok, [])
                self.assertEqual(spy.call_count, 1)

            # 2. Removing each canonical B5 NIF from Data/ or omitting it from FO4SFMission.esm refuses fold before os.replace
            ms_dir = stages_root / "02b-mission"
            orig_plan_txt = (ms_dir / "plan.json").read_text(encoding="utf-8")
            orig_esm_bytes = (ms_dir / "FO4SFMission.esm").read_bytes()

            for _label, nif_rel in B5_REQUIRED_ACTOR_NIFS:
                # 2a. Missing file on disk in mission stage
                plan_obj = json.loads(orig_plan_txt)
                data_rel = f"Data/{nif_rel}"
                saved_nif = (ms_dir / Path(*data_rel.split("/"))).read_bytes()
                (ms_dir / Path(*data_rel.split("/"))).unlink()
                plan_obj["outputs"].pop(data_rel, None)
                (ms_dir / "plan.json").write_text(json.dumps(plan_obj, indent=1), encoding="utf-8")

                out_miss = root / f"bundle-miss-{Path(nif_rel).stem}"
                rc_miss = mcb.main([
                    "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                    "--out", str(out_miss), "--port", str(port_esm), "--profile", "player",
                ], system=_FakeSystemClosed())
                self.assertEqual(rc_miss, 2, nif_rel)
                self.assertFalse(out_miss.exists(), f"fold must refuse before os.replace for missing {nif_rel}")

                # Restore file & plan
                (ms_dir / Path(*data_rel.split("/"))).write_bytes(saved_nif)
                (ms_dir / "plan.json").write_text(orig_plan_txt, encoding="utf-8")

                # 2b. Present on disk, omitted from FO4SFMission.esm ARMA records
                new_sha = _make_mission_esm(ms_dir / "FO4SFMission.esm", omitted_nifs=(nif_rel,))
                plan_esm = json.loads(orig_plan_txt)
                plan_esm["outputs"]["FO4SFMission.esm"] = new_sha
                (ms_dir / "plan.json").write_text(json.dumps(plan_esm, indent=1), encoding="utf-8")

                out_noref = root / f"bundle-noref-{Path(nif_rel).stem}"
                rc_noref = mcb.main([
                    "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                    "--out", str(out_noref), "--port", str(port_esm), "--profile", "player",
                ], system=_FakeSystemClosed())
                self.assertEqual(rc_noref, 2, nif_rel)
                self.assertFalse(out_noref.exists())

                (ms_dir / "FO4SFMission.esm").write_bytes(orig_esm_bytes)
                (ms_dir / "plan.json").write_text(orig_plan_txt, encoding="utf-8")

            # 3. Staged JSON .mat texture check catches missing _neutral_color.dds and accepts Data/ or FO4Port*.ba2
            mat_p = out_ok / "Data" / "materials" / "fo4port" / "_neutral.mat"
            mat_p.write_text(
                json.dumps({"Objects": [], "Summary": {"Layer1": {"Textures": {"Albedo": {"File": "Data\\textures\\fo4port\\_neutral_color.dds"}}}}}),
                encoding="utf-8",
            )
            bplan = json.loads((out_ok / "bundle_plan.json").read_text(encoding="utf-8"))
            bplan["components"]["cog_door"]["outputs"]["Data/materials/fo4port/_neutral.mat"] = _sha256_bytes(mat_p.read_bytes())
            bplan["components"]["exit_lift"]["outputs"]["Data/materials/fo4port/_neutral.mat"] = _sha256_bytes(mat_p.read_bytes())
            bplan["components"]["vault_pod"]["outputs"]["Data/materials/fo4port/_neutral.mat"] = _sha256_bytes(mat_p.read_bytes())
            bplan["components"]["mission"]["outputs"]["Data/materials/fo4port/_neutral.mat"] = _sha256_bytes(mat_p.read_bytes())
            (out_ok / "bundle_plan.json").write_text(json.dumps(bplan, indent=1), encoding="utf-8")

            probs_tex_miss, _ = mcb.verify_bundle(str(out_ok), port_esm=str(port_esm))
            self.assertTrue(any("_neutral_color.dds" in p for p in probs_tex_miss), probs_tex_miss)

            # Satisfied via FO4Port - Textures.ba2 beside port_esm
            port_ba2 = Path(port_esm).parent / "FO4Port - Textures.ba2"
            port_ba2.write_bytes(general_archive({"textures/fo4port/_neutral_color.dds": b"DDS "}))
            probs_tex_ba2, _ = mcb.verify_bundle(str(out_ok), port_esm=str(port_esm))
            self.assertEqual(probs_tex_ba2, [])

    def test_g2_player_build_refuses_without_look_assets_and_forwards_look_flags(self) -> None:
        from types import SimpleNamespace
        import zipfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)
            port_ids = root / "ids.json"
            port_ids.write_text("{}", encoding="utf-8")
            cw_assets = root / "codsworth_assets"
            looks_assets = root / "actor_looks"
            (cw_assets / "meshes").mkdir(parents=True)
            (cw_assets / "meshes" / "a.nif").write_bytes(b"nif")
            (looks_assets / "meshes").mkdir(parents=True)
            (looks_assets / "meshes" / "b.nif").write_bytes(b"nif")

            base_kw = dict(
                work=str(root / "work-refuse"),
                out=str(root / "out-refuse"),
                render_python=None,
                starfield_dir=str(root / "sf"),
                fo4_data=str(root / "fo4"),
                port=str(port_esm),
                port_ids=str(port_ids),
                door_anim_dll=str(root / "calumi.dll"),
                collision_template=str(root / "col.nif"),
                texconv=str(root / "texconv.exe"),
                owner_set=str(owner),
                profile="player",
                commonlibsf=None,
                msvc_env=None,
                no_walk_harness=True,
            )

            # 1. Missing look assets on player build without --allow-starfield-standins must refuse
            with self.assertRaises(mcb.BundleRefused) as ctx:
                mcb.stage_from_checkout(SimpleNamespace(**base_kw))
            self.assertIn("--allow-starfield-standins", str(ctx.exception))

            # 2. Missing only one of the two look asset dirs still refuses
            with self.assertRaises(mcb.BundleRefused):
                mcb.stage_from_checkout(SimpleNamespace(**base_kw, codsworth_assets=str(cw_assets)))

            # 3. Passing --codsworth-assets, --actor-looks-assets, --codsworth-race-framing forwards all 3 to make_mission.py
            mission_calls: list[list[str]] = []
            orig_run_py = mcb._run_py

            def _spy_run(py_exe, script_rel, args):
                arg_l = list(args)
                out_flag = "--out" if "--out" in arg_l else "--staging"
                out_d = Path(arg_l[arg_l.index(out_flag) + 1])
                out_d.mkdir(parents=True, exist_ok=True)
                if script_rel == "scripts/mission/make_mission.py":
                    mission_calls.append(arg_l)
                    (out_d / "plan.json").write_text(json.dumps({"plugin": "FO4SFMission.esm", "outputs": {}}), encoding="utf-8")
                elif script_rel == "scripts/newgame/make_newgame.py":
                    (out_d / "plan.json").write_text(
                        json.dumps({
                            "options": {"hold": ",".join(f"Q{i}" for i in range(199)), "fade_hold": False},
                            "points": {"pod": {"step_m": -2.5}},
                        }),
                        encoding="utf-8",
                    )

            mcb._run_py = _spy_run
            try:
                wk_fwd = root / "work-fwd"
                stages = mcb.stage_from_checkout(
                    SimpleNamespace(
                        **{**base_kw, "work": str(wk_fwd), "out": str(root / "out-fwd")},
                        codsworth_assets=str(cw_assets),
                        actor_looks_assets=str(looks_assets),
                        codsworth_race_framing=True,
                    )
                )
                self.assertEqual(len(mission_calls), 1)
                ms_cmd = mission_calls[0]
                self.assertIn("--codsworth-assets", ms_cmd)
                self.assertEqual(ms_cmd[ms_cmd.index("--codsworth-assets") + 1], str(cw_assets.resolve()))
                self.assertIn("--actor-looks-assets", ms_cmd)
                self.assertEqual(ms_cmd[ms_cmd.index("--actor-looks-assets") + 1], str(looks_assets.resolve()))
                self.assertIn("--codsworth-race-framing", ms_cmd)

                # Verify provenance fields in every staged plan.json
                for st_name in ("00-core-values-player", "01-cog-door", "02a-surface-lift-cog", "02-exit-lift", "02b-mission", "03a-pipboy-wrist", "03-newgame"):
                    pjson = json.loads((wk_fwd / st_name / "plan.json").read_text(encoding="utf-8"))
                    for req_k in ("build_head", "dirty", "args", "asset_dirs", "codsworth_race_framing", "FO4SF_C5_ACTOR_LOOKS_DIR"):
                        self.assertIn(req_k, pjson, f"{st_name}/plan.json missing {req_k}")
                    self.assertTrue(pjson["codsworth_race_framing"])
                    self.assertIn("codsworth_assets", pjson["asset_dirs"])
                    self.assertTrue(pjson["asset_dirs"]["codsworth_assets"]["sha256"])

                # 4. --allow-starfield-standins permits player build without look assets and records flag in bundle_plan.json
                wk_standin = root / "work-standin"
                mcb.stage_from_checkout(
                    SimpleNamespace(
                        **{**base_kw, "work": str(wk_standin), "out": str(root / "out-standin")},
                        allow_starfield_standins=True,
                    )
                )
                ms_standin_plan = json.loads((wk_standin / "02b-mission" / "plan.json").read_text(encoding="utf-8"))
                self.assertTrue(ms_standin_plan["allow_starfield_standins"])

                # 5. --codsworth-handy + --actor-looks-assets (+ optional --codsworth-assets) forwards cleanly;
                #    --codsworth-race-framing + --codsworth-handy refuses cleanly
                handy_dir = root / "handy_bundle"
                (handy_dir / "Data").mkdir(parents=True)
                (handy_dir / "FO4SF_RA2Handy.esm").write_bytes(b"TES4")
                with self.assertRaises(mcb.BundleRefused) as ctx_excl:
                    mcb.stage_from_checkout(
                        SimpleNamespace(
                            **{**base_kw, "work": str(root / "work-excl"), "out": str(root / "out-excl")},
                            codsworth_handy=str(handy_dir),
                            actor_looks_assets=str(looks_assets),
                            codsworth_race_framing=True,
                        )
                    )
                self.assertIn("--codsworth-race-framing", str(ctx_excl.exception))

                mission_calls.clear()
                wk_handy = root / "work-handy"
                mcb.stage_from_checkout(
                    SimpleNamespace(
                        **{**base_kw, "work": str(wk_handy), "out": str(root / "out-handy")},
                        codsworth_assets=str(cw_assets),
                        codsworth_handy=str(handy_dir),
                        actor_looks_assets=str(looks_assets),
                    )
                )
                self.assertEqual(len(mission_calls), 1)
                h_cmd = mission_calls[0]
                self.assertIn("--codsworth-handy", h_cmd)
                self.assertEqual(h_cmd[h_cmd.index("--codsworth-handy") + 1], str(handy_dir.resolve()))
                self.assertIn("--codsworth-assets", h_cmd)
                self.assertNotIn("--codsworth-race-framing", h_cmd)
                h_plan = json.loads((wk_handy / "02b-mission" / "plan.json").read_text(encoding="utf-8"))
                self.assertFalse(h_plan["codsworth_race_framing"])
                self.assertIn("codsworth_handy", h_plan["asset_dirs"])
            finally:
                mcb._run_py = orig_run_py

            # Fold with --allow-starfield-standins records allow_starfield_standins=True and allows missing B5 NIFs
            ms_dir = stages_root / "02b-mission"
            (ms_dir / "Data" / "meshes" / "fo4port" / "actors" / "codsworth" / "codsworth.nif").unlink()
            plan_obj = json.loads((ms_dir / "plan.json").read_text(encoding="utf-8"))
            plan_obj["outputs"].pop("Data/meshes/fo4port/actors/codsworth/codsworth.nif", None)
            (ms_dir / "plan.json").write_text(json.dumps(plan_obj, indent=1), encoding="utf-8")
            out_si = root / "bundle-standin"
            rc_si = mcb.main([
                "fold", "--owner-set", str(owner), "--stages-root", str(stages_root),
                "--out", str(out_si), "--port", str(port_esm), "--profile", "player",
                "--allow-starfield-standins",
            ], system=_FakeSystemClosed())
            self.assertEqual(rc_si, 0)
            si_bplan = json.loads((out_si / "bundle_plan.json").read_text(encoding="utf-8"))
            self.assertTrue(si_bplan["allow_starfield_standins"])
            self.assertIn("dirty", si_bplan)
            self.assertIn("args", si_bplan)
            self.assertIn("asset_dirs", si_bplan)

    def test_g2_stage_reuse_refused_on_differing_args_across_stage_sites(self) -> None:
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner, stages_root, port_esm, _ = self._build_synthetic_owner_and_stages(root)
            port_ids = root / "ids.json"
            port_ids.write_text("{}", encoding="utf-8")
            cw_assets = root / "cw"
            looks_assets = root / "looks"
            cw_assets.mkdir()
            looks_assets.mkdir()
            pb_src = root / "pb-src"
            (pb_src / "Data" / "Interface").mkdir(parents=True)
            (pb_src / "Data" / "Scripts").mkdir(parents=True)
            (pb_src / "SFSE" / "Plugins").mkdir(parents=True)
            p1_sha = _make_tes4_esm(pb_src / "FO4SFPipboyProbe.esm", extra_tag=b"pbp")
            (pb_src / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").write_bytes(b"DLL")
            (pb_src / "plan.json").write_text(json.dumps({"plugins": ["FO4SFPipboyProbe.esm"], "outputs": {"FO4SFPipboyProbe.esm": p1_sha}}), encoding="utf-8")

            orig_run_py = mcb._run_py
            orig_refresh = mcb.refresh_pipboy_stage_for_bundle

            def _spy_run(py_exe, script_rel, args):
                arg_l = list(args)
                out_flag = "--out" if "--out" in arg_l else "--staging"
                out_d = Path(arg_l[arg_l.index(out_flag) + 1])
                out_d.mkdir(parents=True, exist_ok=True)
                if script_rel == "scripts/newgame/make_newgame.py":
                    (out_d / "plan.json").write_text(
                        json.dumps({
                            "options": {"hold": ",".join(f"Q{i}" for i in range(199)), "fade_hold": False},
                            "points": {"pod": {"step_m": -2.5}},
                        }),
                        encoding="utf-8",
                    )

            def _spy_refresh(src_st, out_st, fo4_d, *, setup_show_unavailable=0, require_pickup=1, sf_data_dir=None):
                Path(out_st).mkdir(parents=True, exist_ok=True)

            mcb._run_py = _spy_run
            mcb.refresh_pipboy_stage_for_bundle = _spy_refresh
            try:
                work_dir = root / "work-reuse"
                kw = dict(
                    work=str(work_dir),
                    out=str(root / "out-reuse"),
                    render_python=None,
                    starfield_dir=str(root / "sf"),
                    fo4_data=str(root / "fo4"),
                    port=str(port_esm),
                    port_ids=str(port_ids),
                    door_anim_dll=str(root / "calumi.dll"),
                    collision_template=str(root / "col.nif"),
                    texconv=str(root / "texconv.exe"),
                    owner_set=str(owner),
                    profile="player",
                    commonlibsf=None,
                    msvc_env=None,
                    no_walk_harness=True,
                    codsworth_assets=str(cw_assets),
                    actor_looks_assets=str(looks_assets),
                    with_pipboy=True,
                    pipboy_stage=str(pb_src),
                    show_unavailable_starts=0,
                )
                mcb.stage_from_checkout(SimpleNamespace(**kw))

                # Identical args reuse existing stages cleanly
                mcb.stage_from_checkout(SimpleNamespace(**kw))

                # 1. Differing args at :1272 (02b-mission) via --codsworth-race-framing refuses reuse
                with self.assertRaises(mcb.BundleRefused) as ctx_ms:
                    mcb.stage_from_checkout(SimpleNamespace(**{**kw, "codsworth_race_framing": True}))
                self.assertIn("02b-mission", str(ctx_ms.exception))

                # 2. Differing args at :1309 (03-newgame) and :1458 (16-pipboy-refreshed) via --show-unavailable-starts refuses reuse
                with self.assertRaises(mcb.BundleRefused) as ctx_ng:
                    mcb.stage_from_checkout(SimpleNamespace(**{**kw, "show_unavailable_starts": 1}))
                self.assertIn("03-newgame", str(ctx_ng.exception))

                # Tamper only 03-newgame/plan.json back and verify 16-pipboy-refreshed also refuses differing args
                pb_plan_p = work_dir / "16-pipboy-refreshed" / "plan.json"
                pb_plan_orig = pb_plan_p.read_text(encoding="utf-8")
                pb_plan_mod = json.loads(pb_plan_orig)
                pb_plan_mod["args"]["setup_show_unavailable"] = 1
                pb_plan_p.write_text(json.dumps(pb_plan_mod, indent=1), encoding="utf-8")
                with self.assertRaises(mcb.BundleRefused) as ctx_pb:
                    mcb.stage_from_checkout(SimpleNamespace(**kw))
                self.assertIn("16-pipboy-refreshed", str(ctx_pb.exception))
                pb_plan_p.write_text(pb_plan_orig, encoding="utf-8")

                # 3. Tampered args on 02a-surface-lift-cog (:1232), 02-exit-lift (:1246), 03a-pipboy-wrist (:1294) each refuse reuse
                for folder in ("02a-surface-lift-cog", "02-exit-lift", "03a-pipboy-wrist"):
                    p_path = work_dir / folder / "plan.json"
                    orig_txt = p_path.read_text(encoding="utf-8")
                    mod = json.loads(orig_txt)
                    mod["args"]["--tampered"] = "1"
                    p_path.write_text(json.dumps(mod, indent=1), encoding="utf-8")
                    with self.assertRaises(mcb.BundleRefused) as ctx_site:
                        mcb.stage_from_checkout(SimpleNamespace(**kw))
                    self.assertIn(folder, str(ctx_site.exception))
                    p_path.write_text(orig_txt, encoding="utf-8")

                # 4. Legacy plan.json without recorded "args" also refuses reuse
                legacy_p = work_dir / "02b-mission" / "plan.json"
                legacy_obj = json.loads(legacy_p.read_text(encoding="utf-8"))
                legacy_obj.pop("args", None)
                legacy_p.write_text(json.dumps(legacy_obj, indent=1), encoding="utf-8")
                with self.assertRaises(mcb.BundleRefused) as ctx_leg:
                    mcb.stage_from_checkout(SimpleNamespace(**kw))
                self.assertIn("02b-mission", str(ctx_leg.exception))
            finally:
                mcb._run_py = orig_run_py
                mcb.refresh_pipboy_stage_for_bundle = orig_refresh


def _build_minimal_pex(script_name: str, functions: tuple[str, ...]) -> bytes:
    """Build a minimal valid little-endian Starfield v3.12 PEX binary with `functions` in default state."""
    import struct
    strings = ["", "None", "ScriptObject", script_name]
    smap = {s: i for i, s in enumerate(strings)}

    def sidx(text: str) -> int:
        if text not in smap:
            smap[text] = len(strings)
            strings.append(text)
        return smap[text]

    fn_blobs = bytearray()
    for fn_name in functions:
        fn_blobs += struct.pack("<H", sidx(fn_name))
        fn_blobs += struct.pack("<HHIBHHH", sidx("None"), sidx(""), 0, 0, 0, 0, 0)

    obj_body = bytearray()
    obj_body += struct.pack("<HHBIH", sidx("ScriptObject"), sidx(""), 0, 0, sidx(""))
    obj_body += struct.pack("<HHHHH", 0, 0, 0, 0, 1)
    obj_body += struct.pack("<HH", sidx(""), len(functions)) + fn_blobs
    obj_bytes = struct.pack("<HI", sidx(script_name), len(obj_body) + 4) + bytes(obj_body)

    buf = bytearray(struct.pack("<IBBHQ", 0xFA57C0DE, 3, 12, 4, 0))
    buf += b"\x00\x00" * 3
    buf += struct.pack("<H", len(strings))
    for s in strings:
        raw = s.encode("utf-8")
        buf += struct.pack("<H", len(raw)) + raw
    buf += b"\x00"
    buf += struct.pack("<HH", 0, 1)
    buf += obj_bytes
    return bytes(buf)


if __name__ == "__main__":
    unittest.main()
