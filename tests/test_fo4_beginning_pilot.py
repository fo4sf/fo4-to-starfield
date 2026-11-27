"""Unit tests for `fo4sf.beginning_pilot`, `scripts/testing/check_beginning_pilot.py`, and `docs/testing/fo4-beginning-pilot.md` (`V1`).

Per Rule R4, all log fixtures are hand-written FO4SF state lines only (zero copied game logs or PC paths).
"""
from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fo4sf.beginning_pilot import (  # noqa: E402
    B5_REQUIRED_ACTOR_NIFS,
    BEGINNING_STEPS,
    CODSWORTH_NIF_REL,
    CODSWORTH_VOICE_DIR_REL,
    MIN_CODSWORTH_WEMS,
    NOT_BUILT_MUSEUM_CONTENT,
    discover_rotated_logs,
    evaluate_beginning_logs,
    verify_bundle_beginning_readiness,
)
from fo4sf.planet.esm import ESM, PluginWriter, Record, zbytes  # noqa: E402


def _dummy_tes4() -> bytes:
    return b"TES4" + struct.pack("<IIII", 0, 1, 0, 0) + b"\x00\x00\x00\x00"


def _dummy_mission_esm_with_b5(nifs: Sequence[str] | None = None) -> bytes:
    w = PluginWriter(("Starfield.esm", "FO4TerrainCore.esm", "FO4ActorRaider.esm"), flags=ESM)
    rel_list = list(nifs) if nifs is not None else [rel for _, rel in B5_REQUIRED_ACTOR_NIFS]
    for idx, rel in enumerate(rel_list):
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
    return w.to_bytes(compress=False)


def _handwritten_newgame_lines() -> list[str]:
    return [
        "FO4SF_NEWGAME rt=10.0 mode choice mode=story survival=0",
        "FO4SF_NEWGAME rt=12.0 hold-off pass 1 stopped=60 of 199",
        "FO4SF_NEWGAME rt=14.0 hold-off pass 2 stopped=136 of 199",
        "FO4SF_NEWGAME rt=14.5 stage 10 by=trigger",
        "FO4SF_NEWGAME rt=15.0 pod settle ok=true drop=0.12",
        "FO4SF_NEWGAME rt=20.0 stage 20 by=scene",
        "FO4SF_NEWGAME rt=30.0 pistol picked count=1 base=0x000807",
        "FO4SF_NEWGAME rt=35.0 pipboy pickup equipped flag=1",
        "FO4SF_NEWGAME rt=42.0 cog door console activated ref=0x000818 door=0x000808 before=3 after=2",
        "FO4SF_NEWGAME rt=44.1 stage 30 by=vault_console",
        "FO4SF_NEWGAME rt=70.0 elevator prompt button=1",
        "FO4SF_NEWGAME rt=75.0 special set S=6 P=6 E=6 C=5 I=6 A=6 L=5 sum=40 source=lift",
        "FO4SF_NEWGAME rt=78.0 elevator prompt button=0",
        "FO4SF_NEWGAME rt=79.0 ascent play accepted=true rise=21.6 seconds=9.87",
        "FO4SF_NEWGAME rt=83.0 map setup done markers=309 elapsed=2.1",
        "FO4SF_NEWGAME rt=89.0 ascent carried confirmed elapsed=9.9 z=19.81",
        "FO4SF_NEWGAME rt=94.0 surface setposition ok=true core_cell=true",
        "FO4SF_NEWGAME rt=94.1 stage 40 by=trigger",
        "FO4SF_NEWGAME rt=98.0 landed z=127.45 confirmed=True fallback=false",
        "FO4SF_NEWGAME rt=98.2 stage 200 by=trigger",
    ]


def _handwritten_mission_lines() -> list[str]:
    return [
        "FO4SF_MISSION rt=100.0 mission gate mode=1 started=true",
        "FO4SF_MISSION rt=100.1 init raiders=5",
        "FO4SF_MISSION rt=100.2 codsworth01 stage 10 by=trigger",
        "FO4SF_MISSION rt=120.0 hold codsworth by=keeper off=0.2 ok=true",
        "FO4SF_MISSION rt=134.9 codsworth01 stage 100 by=info",
        "FO4SF_MISSION rt=135.0 min00 given by=codsworth",
        "FO4SF_MISSION rt=135.1 stage 10 by=info",
        "FO4SF_MISSION rt=135.2 codsworth talk end -> min00 stage 10",
        "FO4SF_MISSION rt=135.3 codsworth01 complete choices=4 concord_pointed=true",
        "FO4SF_MISSION rt=210.0 startcombat raider 0 d=48.0",
        "FO4SF_MISSION rt=210.1 stage 20 by=trigger",
        "FO4SF_MISSION rt=225.0 reload mission stage=20 relocate_fails=0",
        "FO4SF_MISSION rt=290.0 wfc01 raider cleared absent id=2055 raider=4 elapsed=61.0 disabled=true",
        "FO4SF_MISSION rt=291.0 stage 30 by=trigger",
        "FO4SF_MISSION rt=305.0 preston activated at stage 30",
        "FO4SF_MISSION rt=305.1 preston talk scene triggered stage=30",
        "FO4SF_MISSION rt=318.0 stage 35 by=info",
        "FO4SF_MISSION rt=318.0 preston talk end info=0x092A -> stage 40",
        "FO4SF_MISSION rt=318.1 stage 40 by=info",
        "FO4SF_MISSION rt=318.2 reward credits=100",
        "FO4SF_MISSION rt=319.0 stage 200 by=trigger",
        "FO4SF_MISSION rt=319.5 sanctuary01 stage 10 by=trigger",
        "FO4SF_MISSION rt=319.6 min01 stage 10 objective bench",
        "FO4SF_MISSION rt=379.9 sanctuary01 stage 100 by=bench",
        "FO4SF_MISSION rt=380.0 min01 bench activated -> stage 100",
    ]


def _build_synthetic_pex(
    script_name: str,
    functions: Sequence[str],
    *,
    non_default_functions: Sequence[str] = (),
    cast_calls: Sequence[Tuple[str, str]] = (),
    direct_calls: Sequence[str] = (),
    direct_target: str = "FO4SF_MapMarkers",
) -> bytes:
    """Build a minimal valid little-endian Starfield v3.12 (`.pex`) binary for offline tests."""
    import struct as _struct

    strings: list[str] = ["", "None", "ScriptObject", script_name]
    str_idx_map: dict[str, int] = {s: i for i, s in enumerate(strings)}

    def sidx(text: str) -> int:
        if text not in str_idx_map:
            str_idx_map[text] = len(strings)
            strings.append(text)
        return str_idx_map[text]

    def emit_fn_body(fn_name: str, include_calls: bool) -> bytes:
        out = bytearray(_struct.pack("<HHIBH", sidx("None"), sidx(""), 0, 0, 0))
        if include_calls and (cast_calls or direct_calls):
            locals_list = [
                ("mmForm", "Form"),
                ("mm", "ScriptObject"),
                ("typed_mm", direct_target),
            ]
            out += _struct.pack("<H", len(locals_list))
            for ln, lt in locals_list:
                out += _struct.pack("<HH", sidx(ln), sidx(lt))
            insns: list[bytes] = []
            for target_script, method_name in cast_calls:
                insns.append(
                    b"\x17"
                    + b"\x01" + _struct.pack("<H", sidx("CastAs"))
                    + b"\x01" + _struct.pack("<H", sidx("mmForm"))
                    + b"\x01" + _struct.pack("<H", sidx("mm"))
                    + b"\x03" + _struct.pack("<i", 1)
                    + b"\x02" + _struct.pack("<H", sidx(target_script))
                )
                insns.append(
                    b"\x17"
                    + b"\x01" + _struct.pack("<H", sidx("CallFunction"))
                    + b"\x01" + _struct.pack("<H", sidx("mm"))
                    + b"\x01" + _struct.pack("<H", sidx("mmForm"))
                    + b"\x03" + _struct.pack("<i", 1)
                    + b"\x02" + _struct.pack("<H", sidx(method_name))
                )
            for method_name in direct_calls:
                insns.append(
                    b"\x17"
                    + b"\x01" + _struct.pack("<H", sidx(method_name))
                    + b"\x01" + _struct.pack("<H", sidx("typed_mm"))
                    + b"\x01" + _struct.pack("<H", sidx("mmForm"))
                    + b"\x03" + _struct.pack("<i", 0)
                )
            out += _struct.pack("<H", len(insns)) + b"".join(insns)
        else:
            out += _struct.pack("<HH", 0, 0)
        return _struct.pack("<H", sidx(fn_name)) + bytes(out)

    states: list[tuple[str, Sequence[str]]] = [("", functions)]
    if non_default_functions:
        states.append(("Busy", non_default_functions))

    state_blobs = bytearray()
    for st_name, st_fns in states:
        st_idx = sidx(st_name)
        fn_blobs = b"".join(
            emit_fn_body(fn_nm, include_calls=(st_name == "" and i == 0))
            for i, fn_nm in enumerate(st_fns)
        )
        state_blobs += _struct.pack("<HH", st_idx, len(st_fns)) + fn_blobs

    obj_body = bytearray()
    obj_body += _struct.pack("<HHBIH", sidx("ScriptObject"), sidx(""), 0, 0, sidx(""))
    obj_body += _struct.pack("<H", 0)  # structs (v3.9+)
    obj_body += _struct.pack("<H", 0)  # vars
    obj_body += _struct.pack("<H", 0)  # guards (v3.10+)
    obj_body += _struct.pack("<H", 0)  # props
    obj_body += _struct.pack("<H", len(states)) + bytes(state_blobs)
    obj_bytes = _struct.pack("<HI", sidx(script_name), len(obj_body) + 4) + bytes(obj_body)

    buf = bytearray(_struct.pack("<IBBHQ", 0xFA57C0DE, 3, 12, 4, 0))
    buf += b"\x00\x00" * 3  # source, user, machine
    buf += _struct.pack("<H", len(strings))
    for s in strings:
        raw = s.encode("utf-8")
        buf += _struct.pack("<H", len(raw)) + raw
    buf += b"\x00"  # has_debug = 0
    buf += _struct.pack("<HH", 0, 1)  # userFlags=0, objectCount=1
    buf += obj_bytes
    return bytes(buf)


def _dummy_tes4_with_masters(masters: Sequence[str]) -> bytes:
    """Build a minimal valid TES4 header declaring `masters`."""
    import struct as _struct

    payload = bytearray(b"HEDR" + _struct.pack("<HfII", 12, 1.0, 0, 0x800))
    for master in masters:
        m_raw = master.encode("utf-8") + b"\x00"
        payload += b"MAST" + _struct.pack("<H", len(m_raw)) + m_raw
        payload += b"DATA" + _struct.pack("<HQ", 8, 0)
    return b"TES4" + _struct.pack("<IIIIHH", len(payload), 0x01, 0, 0, 0, 0) + bytes(payload)


def _populate_synthetic_map_markers(
    bundle: Path,
    *,
    defined_fns: Sequence[str] = (
        "PrepareKnownUndiscoveredSingle",
        "PrepareKnownUndiscoveredAll",
        "DiscoverSingleMarker",
        "DiscoverSingleMarkerSilent",
        "SuppressArrivalDarkHold",
    ),
    non_default_fns: Sequence[str] = (),
    root_fallback: bool = False,
    write_loose_pex: bool = True,
    core_sha_override: str | None = None,
) -> Path:
    """Write a valid (or customized) synthetic map-markers build into `bundle`."""
    import hashlib as _hashlib
    import json as _json
    try:
        from tests.ba2_fixture import general_archive as _general_archive
    except ModuleNotFoundError:
        from ba2_fixture import general_archive as _general_archive

    mm_root = bundle if root_fallback else (bundle / "map-markers")
    mm_root.mkdir(parents=True, exist_ok=True)
    (mm_root / "FO4SFMapMarkers.esm").write_bytes(
        _dummy_tes4_with_masters(["Starfield.esm", "FO4TerrainCore.esm"])
    )
    core_sha = core_sha_override or _hashlib.sha256((bundle / "FO4TerrainCore.esm").read_bytes()).hexdigest()
    if not root_fallback:
        (mm_root / "core.json").write_text(
            _json.dumps({"schema_version": 1, "masters": {"FO4TerrainCore.esm": core_sha}}, indent=2) + "\n",
            encoding="utf-8",
        )
    pex_bytes = _build_synthetic_pex(
        "FO4SF_MapMarkers",
        defined_fns,
        non_default_functions=non_default_fns,
    )
    (mm_root / "FO4SFMapMarkers - Main.ba2").write_bytes(
        _general_archive({"Scripts/FO4SF_MapMarkers.pex": pex_bytes})
    )
    if write_loose_pex:
        scripts_dir = mm_root / "Data" / "Scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "FO4SF_MapMarkers.pex").write_bytes(pex_bytes)
    return mm_root


def _dummy_vault_pod_esm(
    *,
    include_acti: bool = True,
    include_refr801: bool = True,
    refr801_persistent: bool = True,
    include_1617: bool = True,
    disabled_1617: bool = True,
) -> bytes:
    def _sub(sig: bytes, data: bytes) -> bytes:
        return sig + struct.pack("<H", len(data)) + data

    def _rec(sig: bytes, fid: int, subs: list[bytes], flags: int = 0) -> bytes:
        body = b"".join(subs)
        return sig + struct.pack("<IIIII", len(body), flags, fid, 0, 0) + body

    def _grup(label: bytes, gtype: int, payload: bytes) -> bytes:
        return b"GRUP" + struct.pack("<I", 24 + len(payload)) + label + struct.pack("<III", gtype, 0, 0) + payload

    w = PluginWriter(("Starfield.esm", "FO4Port.esm"), flags=ESM, author="fo4-to-starfield VaultPod")
    if include_acti:
        acti_subs = [
            (b"EDID", zbytes("FO4SF_PlayerCryoPod")),
            (b"OBND", struct.pack("<6f", -1.0, -1.0, 0.0, 1.0, 1.0, 2.5)),
            (b"MODL", zbytes(r"fo4port\pod\cryopod01.nif")),
            (b"ANAM", zbytes(r"Actors\Character\Animation\StateMachines\ActivatorStateGraph01.agx")),
            (b"BNAM", zbytes(r"fo4port\pod\rig.hkt")),
            (b"CNAM", zbytes(r"fo4port\pod\clips")),
        ]
        w.add(Record(b"ACTI", w.own(0x000800), acti_subs, 0, 0, 581, 0))
    blob = w.to_bytes(compress=False)
    cell_children = bytearray()
    if include_refr801:
        cell_children += _rec(
            b"REFR",
            w.own(0x000801),
            [_sub(b"NAME", struct.pack("<I", w.own(0x000800)))],
            flags=0x00000400 if refr801_persistent else 0,
        )
    if include_1617:
        cell_children += _rec(
            b"REFR",
            (1 << 24) | 0x001617,
            [_sub(b"NAME", struct.pack("<I", (1 << 24) | 0x000855))],
            flags=0x00000800 if disabled_1617 else 0,
        )
    if cell_children:
        cell_fid = (1 << 24) | 0x0011F3
        cell_rec = _rec(b"CELL", cell_fid, [_sub(b"EDID", zbytes("FO4Port_Vault111Cryo"))], flags=0x00000401)
        blob += _grup(b"CELL", 0, cell_rec + _grup(struct.pack("<I", cell_fid), 6, bytes(cell_children)))
    return blob


def _populate_synthetic_vault_pod(
    bundle: Path,
    *,
    write_esm: bool = True,
    include_acti: bool = True,
    include_refr801: bool = True,
    refr801_persistent: bool = True,
    include_1617: bool = True,
    disabled_1617: bool = True,
    omit_clip: str | None = None,
) -> None:
    if write_esm:
        (bundle / "FO4SFVaultPod.esm").write_bytes(
            _dummy_vault_pod_esm(
                include_acti=include_acti,
                include_refr801=include_refr801,
                refr801_persistent=refr801_persistent,
                include_1617=include_1617,
                disabled_1617=disabled_1617,
            )
        )
    pod_dir = bundle / "Data" / "meshes" / "fo4port" / "pod"
    clips_dir = pod_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    (pod_dir / "cryopod01.nif").write_bytes(b"NIF_POD")
    (pod_dir / "rig.hkt").write_bytes(b"RIG_POD")
    for clip in ("statea_play.af", "statea_play.afx", "stateb_play.af", "stateb_play.afx",
                 "statea_idle.af", "statea_idle.afx", "stateb_idle.af", "stateb_idle.afx"):
        if omit_clip and clip.casefold() == omit_clip.casefold():
            continue
        (clips_dir / clip).write_bytes(b"CLIP_POD")


class BeginningPilotTests(unittest.TestCase):
    def _build_synthetic_bundle(self, root: Path) -> Path:
        bundle = root / "candidate"
        (bundle / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
        req_plugins = {
            "FO4SFCoreValues.esm",
            "FO4ActorRaider.esm",
            "FO4TerrainCore.esm",
            "FO4SFMission.esm",
            "FO4SFVaultGearDoor.esm",
            "FO4SFExitLift.esm",
            "FO4SFVaultPod.esm",
            "FO4SFNewGame.esm",
            "FO4SFProgression.esm",
        }
        for p in sorted(req_plugins):
            if p == "FO4SFVaultPod.esm":
                continue
            (bundle / p).write_bytes(_dummy_mission_esm_with_b5() if p == "FO4SFMission.esm" else _dummy_tes4())
        _populate_synthetic_vault_pod(bundle)
        _populate_synthetic_map_markers(bundle)

        for sc in (
            "FO4SF_NewGameQuest.pex",
            "FO4SF_NewGameLooks.pex",
            "FO4SF_ProgressionQuest.pex",
            "FO4SF_Min00Quest.pex",
            "FO4SF_COMPreston.pex",
            "FO4SF_Codsworth01Quest.pex",
            "FO4SF_Sanctuary01Quest.pex",
        ):
            (bundle / "Data" / "Scripts" / sc).write_bytes(b"PEX_SYNTHETIC_BINARY_PAYLOAD")

        for _label, nif_rel in B5_REQUIRED_ACTOR_NIFS:
            nif = bundle / "Data" / Path(*nif_rel.split("/"))
            nif.parent.mkdir(parents=True, exist_ok=True)
            nif.write_bytes(b"NIF_SYNTHETIC")

        vdir = bundle / "Data" / Path(CODSWORTH_VOICE_DIR_REL)
        vdir.mkdir(parents=True, exist_ok=True)
        for idx in range(MIN_CODSWORTH_WEMS):
            (vdir / f"00f4c{idx:03x}.wem").write_bytes(b"RIFF_WEM")

        (bundle / "bundle_plan.json").write_text(
            json.dumps(
                {
                    "plugins": sorted(req_plugins),
                    "components": {
                        "cog_door": {"outputs": {"FO4SFVaultGearDoor.esm": "aa", "Data/meshes/door.nif": "bb"}},
                        "exit_lift": {"outputs": {"FO4SFExitLift.esm": "cc", "Data/meshes/lift.nif": "dd"}},
                    },
                }
            ),
            encoding="utf-8",
        )
        return bundle

    def test_map_markers_compatibility_rejects_old_pex_and_checks_compiled_newgame_pex(self) -> None:
        from fo4sf.beginning_pilot import extract_mapmarker_calls_from_pex, verify_map_markers_bundle_compatibility
        try:
            from tests.ba2_fixture import general_archive as _general_archive
        except ModuleNotFoundError:
            from ba2_fixture import general_archive as _general_archive

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = self._build_synthetic_bundle(root)

            # Case 1: older 14-Nov FO4SF_MapMarkers.pex lacking PrepareKnownUndiscoveredAll fails check-bundle + CLI.
            _populate_synthetic_map_markers(
                bundle,
                defined_fns=("DiscoverSingleMarker",),
                write_loose_pex=True,
            )
            bad_res = verify_bundle_beginning_readiness(str(bundle))
            self.assertFalse(bad_res["ok"])
            self.assertEqual(bad_res["steps"]["B3_exit_lift"]["status"], "FAIL")
            self.assertTrue(
                any("lacks FO4SF_MapMarkers.PrepareKnownUndiscoveredAll()" in msg for msg in bad_res["problems"]),
                bad_res["problems"],
            )
            cli_fail = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "testing" / "check_beginning_pilot.py"), "check-bundle", "--bundle-dir", str(bundle)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(cli_fail.returncode, 1, cli_fail.stdout + cli_fail.stderr)
            self.assertIn("PrepareKnownUndiscoveredAll", cli_fail.stdout)

            # Case 2: compiled PEX FO4SF_NewGameQuest issuing CastAs("FO4SF_MapMarkers") + CallFunction(customFn)
            # enforces that customFn exists in FO4SF_MapMarkers.pex's default state.
            ng_pex = _build_synthetic_pex(
                "FO4SF_NewGameQuest",
                ["RunSharedMapSetup"],
                cast_calls=[
                    ("FO4SF_MapMarkers", "PrepareKnownUndiscoveredAll"),
                    ("FO4SF_MapMarkers", "CheckCustomMarkerHook"),
                ],
                direct_calls=["DiscoverSingleMarker"],
            )
            self.assertEqual(
                set(extract_mapmarker_calls_from_pex(ng_pex)),
                {"PrepareKnownUndiscoveredAll", "CheckCustomMarkerHook", "DiscoverSingleMarker"},
            )
            (bundle / "Data" / "Scripts" / "FO4SF_NewGameQuest.pex").write_bytes(ng_pex)
            _populate_synthetic_map_markers(
                bundle,
                defined_fns=("PrepareKnownUndiscoveredAll", "DiscoverSingleMarker"),
                non_default_fns=("CheckCustomMarkerHook",),
                write_loose_pex=True,
            )
            non_def_issues = verify_map_markers_bundle_compatibility(str(bundle))
            self.assertTrue(
                any("only in a non-default state" in msg and "CheckCustomMarkerHook" in msg for msg in non_def_issues),
                non_def_issues,
            )

            # Moving CheckCustomMarkerHook to the default state resolves compatibility.
            _populate_synthetic_map_markers(
                bundle,
                defined_fns=("PrepareKnownUndiscoveredAll", "DiscoverSingleMarker", "CheckCustomMarkerHook"),
                write_loose_pex=True,
            )
            self.assertEqual(verify_map_markers_bundle_compatibility(str(bundle)), [])
            ok_compiled = verify_bundle_beginning_readiness(str(bundle))
            self.assertTrue(ok_compiled["ok"], ok_compiled["problems"])

            # Bad magic in BA2 PEX also fails cleanly.
            (bundle / "map-markers" / "FO4SFMapMarkers - Main.ba2").write_bytes(
                _general_archive({"Scripts/FO4SF_MapMarkers.pex": b"not-a-pex"})
            )
            (bundle / "map-markers" / "Data" / "Scripts" / "FO4SF_MapMarkers.pex").write_bytes(b"not-a-pex")
            self.assertTrue(
                any("not a valid compiled PEX" in msg for msg in verify_map_markers_bundle_compatibility(str(bundle)))
            )

    def test_map_markers_compatibility_checks_esm_ba2_core_pin_loose_pex_and_root_fallback(self) -> None:
        import shutil
        from fo4sf.beginning_pilot import verify_map_markers_bundle_compatibility

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = self._build_synthetic_bundle(root)

            # Stale core.json pin fails.
            _populate_synthetic_map_markers(bundle, core_sha_override="0" * 64)
            stale_issues = verify_map_markers_bundle_compatibility(str(bundle))
            self.assertTrue(any("core.json pins FO4TerrainCore.esm" in msg for msg in stale_issues), stale_issues)

            # Restore valid map-markers, then introduce mismatched loose PEX.
            _populate_synthetic_map_markers(bundle)
            (bundle / "map-markers" / "Data" / "Scripts" / "FO4SF_MapMarkers.pex").write_bytes(
                _build_synthetic_pex("FO4SF_MapMarkers", ["PrepareKnownUndiscoveredAll"])
            )
            mismatch_issues = verify_map_markers_bundle_compatibility(str(bundle))
            self.assertTrue(any("differs from Scripts/FO4SF_MapMarkers.pex" in msg for msg in mismatch_issues), mismatch_issues)

            # Missing map-markers directory and no root-level FO4SFMapMarkers fails.
            shutil.rmtree(bundle / "map-markers")
            missing_issues = verify_map_markers_bundle_compatibility(str(bundle))
            self.assertTrue(any("missing map-markers/FO4SFMapMarkers.esm" in msg for msg in missing_issues), missing_issues)

            # Root-level FO4SFMapMarkers fallback works when complete, and fails if old PEX.
            _populate_synthetic_map_markers(bundle, root_fallback=True, write_loose_pex=False)
            self.assertEqual(verify_map_markers_bundle_compatibility(str(bundle)), [])
            _populate_synthetic_map_markers(bundle, root_fallback=True, write_loose_pex=False, defined_fns=("DiscoverSingleMarker",))
            root_old_issues = verify_map_markers_bundle_compatibility(str(bundle))
            self.assertTrue(
                any("lacks FO4SF_MapMarkers.PrepareKnownUndiscoveredAll()" in msg for msg in root_old_issues),
                root_old_issues,
            )

    def test_verify_bundle_beginning_readiness_passes_and_catches_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._build_synthetic_bundle(Path(tmp))
            ok_res = verify_bundle_beginning_readiness(str(bundle))
            self.assertTrue(ok_res["ok"], ok_res["problems"])
            self.assertEqual(len(ok_res["steps"]), 8)

            first_wem = sorted((bundle / "Data" / Path(CODSWORTH_VOICE_DIR_REL)).glob("*.wem"))[0]
            first_wem.unlink()
            bad_res = verify_bundle_beginning_readiness(str(bundle))
            self.assertFalse(bad_res["ok"])
            self.assertEqual(bad_res["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")

            # Removing any one of the 4 canonical B5 NIFs or dropping its ARMA ref in FO4SFMission.esm fails B5
            for _label, nif_rel in B5_REQUIRED_ACTOR_NIFS:
                b2 = self._build_synthetic_bundle(Path(tmp) / ("miss-" + Path(nif_rel).stem))
                (b2 / "Data" / Path(*nif_rel.split("/"))).unlink()
                r_miss = verify_bundle_beginning_readiness(str(b2))
                self.assertFalse(r_miss["ok"])
                self.assertEqual(r_miss["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")
                b2_esm = self._build_synthetic_bundle(Path(tmp) / ("noref-" + Path(nif_rel).stem))
                kept = [r for _, r in B5_REQUIRED_ACTOR_NIFS if r != nif_rel]
                (b2_esm / "FO4SFMission.esm").write_bytes(_dummy_mission_esm_with_b5(kept))
                r_noref = verify_bundle_beginning_readiness(str(b2_esm))
                self.assertFalse(r_noref["ok"])
                self.assertEqual(r_noref["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")

    def test_full_handwritten_story_walk_passes_all_eight_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            ng_log.write_text("\n".join(_handwritten_newgame_lines()) + "\n", encoding="utf-8")
            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")

            res = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertTrue(res["ok"], res)
            self.assertTrue(res["all_pass"], res)
            for spec in BEGINNING_STEPS:
                self.assertEqual(res["steps"][spec.step_id]["status"], "PASS", spec.step_id)

    def test_negative_special_skipped_and_wrong_sum_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")

            # 1. 'special skipped' must FAIL B3_exit_lift
            skipped_lines = [
                "FO4SF_NEWGAME rt=76.0 special skipped: left the vault with SPECIAL unset"
                if "special set" in ln
                else ln
                for ln in _handwritten_newgame_lines()
            ]
            ng_log.write_text("\n".join(skipped_lines) + "\n", encoding="utf-8")
            r_skip = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_skip["ok"])
            self.assertEqual(r_skip["steps"]["B3_exit_lift"]["status"], "FAIL")

            # 2. 28-point S.P.E.C.I.A.L. sum (instead of 40) must FAIL B3_exit_lift
            sum28_lines = [
                "FO4SF_NEWGAME rt=75.0 special set S=4 P=4 E=4 C=4 I=4 A=4 L=4"
                if "special set" in ln
                else ln
                for ln in _handwritten_newgame_lines()
            ]
            ng_log.write_text("\n".join(sum28_lines) + "\n", encoding="utf-8")
            r_sum = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_sum["ok"])
            self.assertEqual(r_sum["steps"]["B3_exit_lift"]["status"], "FAIL")

            # 3. Missing 'map setup done' must FAIL B3_exit_lift
            no_map = [ln for ln in _handwritten_newgame_lines() if "map setup done" not in ln]
            ng_log.write_text("\n".join(no_map) + "\n", encoding="utf-8")
            r_map = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_map["ok"])
            self.assertEqual(r_map["steps"]["B3_exit_lift"]["status"], "FAIL")

    def test_negative_missing_console_activation_pipboy_order_and_pistol_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")

            # 1. Missing 'cog door console activated' when reaching stage 30 must FAIL B2_gear_door
            no_console = [
                "FO4SF_NEWGAME rt=42.0 cog door open_state before=3 after=2"
                if "cog door console activated" in ln
                else ln
                for ln in _handwritten_newgame_lines()
            ]
            ng_log.write_text("\n".join(no_console) + "\n", encoding="utf-8")
            r_no_con = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_no_con["ok"])
            self.assertEqual(r_no_con["steps"]["B2_gear_door"]["status"], "FAIL")

            # 2. Direct door open ('cog door opened directly') must FAIL B2_gear_door
            direct = _handwritten_newgame_lines() + ["FO4SF_NEWGAME rt=41.0 cog door opened directly"]
            ng_log.write_text("\n".join(direct) + "\n", encoding="utf-8")
            r_dir = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_dir["ok"])
            self.assertEqual(r_dir["steps"]["B2_gear_door"]["status"], "FAIL")

            # 3. Console activated before 'pipboy pickup equipped flag=1' must FAIL B2_gear_door
            swapped = []
            for ln in _handwritten_newgame_lines():
                if "pipboy pickup equipped flag=1" in ln:
                    continue
                swapped.append(ln)
                if "cog door console activated" in ln:
                    swapped.append("FO4SF_NEWGAME rt=42.1 pipboy pickup equipped flag=1")
            ng_log.write_text("\n".join(swapped) + "\n", encoding="utf-8")
            r_ord = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_ord["ok"])
            self.assertEqual(r_ord["steps"]["B2_gear_door"]["status"], "FAIL")

            # 4. Missing 'pistol picked' before stage 30 must FAIL B2_gear_door
            no_pistol = [ln for ln in _handwritten_newgame_lines() if "pistol picked" not in ln]
            ng_log.write_text("\n".join(no_pistol) + "\n", encoding="utf-8")
            r_pis = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_pis["ok"])
            self.assertEqual(r_pis["steps"]["B2_gear_door"]["status"], "FAIL")

    def test_negative_stage40_fallback_warfare_gate_and_early_vault_mission_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            ng_log.write_text("\n".join(_handwritten_newgame_lines()) + "\n", encoding="utf-8")

            # 1. 'stage 40 by=fallback' counts as FAIL for REACHABLE on B7_preston_turnin
            fb_lines = [
                "FO4SF_MISSION rt=318.0 stage 40 by=fallback"
                if "preston talk end" in ln
                else ln
                for ln in _handwritten_mission_lines()
            ]
            ms_log.write_text("\n".join(fb_lines) + "\n", encoding="utf-8")
            r_fb = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_fb["ok"])
            self.assertEqual(r_fb["steps"]["B7_preston_turnin"]["status"], "FAIL")

            # 2. Warfare gate ('mission gate mode=2 started=false') fails Story B5_codsworth_sanctuary
            wf_lines = ["FO4SF_MISSION rt=100.0 mission gate mode=2 started=false"]
            ms_log.write_text("\n".join(wf_lines) + "\n", encoding="utf-8")
            r_wf = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_wf["ok"])
            self.assertEqual(r_wf["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")

            # 3. Mission starting in Vault 111 before NewGame stage 200 (rt=40.0 < rt=98.2) fails B5
            early_lines = [ln.replace("rt=100.0", "rt=40.0", 1) for ln in _handwritten_mission_lines()]
            ms_log.write_text("\n".join(early_lines) + "\n", encoding="utf-8")
            r_early = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_early["ok"])
            self.assertEqual(r_early["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")

    def test_cli_check_bundle_and_check_logs_exit_codes(self) -> None:
        cli = ROOT / "scripts" / "testing" / "check_beginning_pilot.py"
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            bundle = self._build_synthetic_bundle(tdir)
            r_bun = subprocess.run(
                [sys.executable, str(cli), "check-bundle", "--bundle-dir", str(bundle)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_bun.returncode, 0, r_bun.stdout + r_bun.stderr)

            ng_log = tdir / "ng.log"
            ms_log = tdir / "ms.log"
            ng_log.write_text("\n".join(_handwritten_newgame_lines()) + "\n", encoding="utf-8")
            ms_log.write_text("\n".join(_handwritten_mission_lines()[:-1]) + "\n", encoding="utf-8")

            # Without --require-all-pass, IN_PROGRESS on B8 exits 0; with --require-all-pass, exits 2
            r_prog = subprocess.run(
                [sys.executable, str(cli), "check-logs", "--newgame-log", str(ng_log), "--mission-log", str(ms_log)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_prog.returncode, 0, r_prog.stdout)
            r_req = subprocess.run(
                [
                    sys.executable,
                    str(cli),
                    "check-logs",
                    "--newgame-log",
                    str(ng_log),
                    "--mission-log",
                    str(ms_log),
                    "--require-all-pass",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_req.returncode, 2, r_req.stdout)

            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")
            r_ok = subprocess.run(
                [
                    sys.executable,
                    str(cli),
                    "check-logs",
                    "--newgame-log",
                    str(ng_log),
                    "--mission-log",
                    str(ms_log),
                    "--require-all-pass",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_ok.returncode, 0, r_ok.stdout)

    def test_docs_cover_labels_and_not_built_museum_content(self) -> None:
        pilot_doc = (ROOT / "docs" / "testing" / "fo4-beginning-pilot.md").read_text(encoding="utf-8")
        for spec in BEGINNING_STEPS:
            self.assertIn(spec.step_id, pilot_doc)
        for label in ("REACHABLE", "TEST-STATION", "RECORDS ONLY", "TOOLING", "NOT BUILT"):
            self.assertIn(label, pilot_doc)
        for cut_item in NOT_BUILT_MUSEUM_CONTENT:
            self.assertIn(cut_item, pilot_doc.lower())
        self.assertIn("placeholder", pilot_doc.lower())

    def test_b6_negative_bare_stage40_other_cause_early_scene_end_exit_fallback_and_special_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            pr_log = tdir / "FO4SFProgression.0.log"

            # (a1) Bare 'stage 40' (missing by= cause) on Min00 must FAIL B7_preston_turnin
            ng_log.write_text("\n".join(_handwritten_newgame_lines()) + "\n", encoding="utf-8")
            bare_stage40 = [
                "FO4SF_MISSION rt=318.1 stage 40"
                if "stage 40 by=info" in ln
                else ln
                for ln in _handwritten_mission_lines()
                if "stage 35 by=info" not in ln
            ]
            ms_log.write_text("\n".join(bare_stage40) + "\n", encoding="utf-8")
            r_bare = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_bare["ok"])
            self.assertEqual(r_bare["steps"]["B7_preston_turnin"]["status"], "FAIL")

            # (a2) Console setstage -> 'stage 40 by=other' must FAIL B7_preston_turnin
            other_stage40 = [
                "FO4SF_MISSION rt=318.1 stage 40 by=other"
                if "stage 40 by=info" in ln
                else ln
                for ln in _handwritten_mission_lines()
                if "stage 35 by=info" not in ln and "preston talk end" not in ln
            ]
            ms_log.write_text("\n".join(other_stage40) + "\n", encoding="utf-8")
            r_other = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_other["ok"])
            self.assertEqual(r_other["steps"]["B7_preston_turnin"]["status"], "FAIL")

            # (b) Preston scene ended before final exchange (stage 35 not reached) must FAIL B7_preston_turnin
            early_scene_end = [
                ln for ln in _handwritten_mission_lines()
                if not any(tok in ln for tok in ("stage 35", "preston talk end", "stage 40", "reward credits", "stage 200", "sanctuary01", "min01"))
            ] + [
                "FO4SF_MISSION rt=309.0 preston talk scene ended stage=30 end_info=false",
                "FO4SF_MISSION rt=309.0 preston talk retry n=1 reason=scene_incomplete",
            ]
            ms_log.write_text("\n".join(early_scene_end) + "\n", encoding="utf-8")
            r_inc = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_inc["ok"])
            self.assertEqual(r_inc["steps"]["B7_preston_turnin"]["status"], "FAIL")

            # (c) 'exit fallback by=move' must FAIL B3_exit_lift and B4_surface_landing
            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")
            exit_fb_ng = [
                "FO4SF_NEWGAME rt=94.1 stage 40 by=fallback" if "stage 40 by=trigger" in ln else ln
                for ln in _handwritten_newgame_lines()
            ] + ["FO4SF_NEWGAME rt=93.5 exit fallback by=move failures=3"]
            ng_log.write_text("\n".join(exit_fb_ng) + "\n", encoding="utf-8")
            r_exfb = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_exfb["ok"])
            self.assertEqual(r_exfb["steps"]["B3_exit_lift"]["status"], "FAIL")
            self.assertEqual(r_exfb["steps"]["B4_surface_landing"]["status"], "FAIL")

            # (d) 'special default sum=40 source=lift' (in NewGame or Progression log) must FAIL B3_exit_lift
            ng_log.write_text(
                "\n".join(_handwritten_newgame_lines() + ["FO4SF_NEWGAME rt=75.1 special default sum=40 source=lift"]) + "\n",
                encoding="utf-8",
            )
            r_spdef = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_spdef["ok"])
            self.assertEqual(r_spdef["steps"]["B3_exit_lift"]["status"], "FAIL")

            ng_log.write_text("\n".join(_handwritten_newgame_lines()) + "\n", encoding="utf-8")
            pr_log.write_text("[FO4SF_Progression] step=special_default sum=40 source=lift\n", encoding="utf-8")
            r_prdef = evaluate_beginning_logs(str(ng_log), str(ms_log), progression_log_path=str(pr_log))
            self.assertFalse(r_prdef["ok"])
            self.assertEqual(r_prdef["steps"]["B3_exit_lift"]["status"], "FAIL")

    def test_b7_multi_session_rotated_desktop_quit_logs_pass_and_fail(self) -> None:
        cli = ROOT / "scripts" / "testing" / "check_beginning_pilot.py"
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            # Session 1 (.1.log): Vault -> Hilltop -> Codsworth -> Concord stage 20 -> Quit to Desktop
            ng_s1 = tdir / "fo4sf_newgame.1.log"
            ng_s2 = tdir / "fo4sf_newgame.0.log"
            ms_s1 = tdir / "fo4sf_mission.1.log"
            ms_s2 = tdir / "fo4sf_mission.0.log"

            ng_s1.write_text("\n".join(_handwritten_newgame_lines()) + "\n", encoding="utf-8")
            ng_s2.write_text("FO4SF_NEWGAME rt=4.2 reload stage=200\n", encoding="utf-8")

            ms_all = _handwritten_mission_lines()
            split_idx = next(i for i, ln in enumerate(ms_all) if "reload mission stage=20" in ln)
            ms_s1.write_text("\n".join(ms_all[:split_idx]) + "\n", encoding="utf-8")
            # Session 2 starts with fresh rt=5.0 after Quit to Desktop & relaunch!
            ms_s2_lines = [
                ln.replace("rt=225.0", "rt=5.0")
                .replace("rt=290.0", "rt=68.0")
                .replace("rt=291.0", "rt=69.0")
                .replace("rt=305.0", "rt=80.0")
                .replace("rt=305.1", "rt=80.1")
                .replace("rt=318.0", "rt=92.0")
                .replace("rt=318.1", "rt=92.1")
                .replace("rt=318.2", "rt=92.2")
                .replace("rt=319.0", "rt=93.0")
                .replace("rt=319.5", "rt=93.5")
                .replace("rt=319.6", "rt=93.6")
                .replace("rt=379.9", "rt=140.0")
                .replace("rt=380.0", "rt=140.1")
                for ln in ms_all[split_idx:]
            ]
            ms_s2.write_text("\n".join(ms_s2_lines) + "\n", encoding="utf-8")

            self.assertEqual(discover_rotated_logs(str(tdir), "fo4sf_mission"), [str(ms_s1), str(ms_s2)])

            # Directory auto-discovery passes all 8 steps across rotated .1.log -> .0.log
            res_dir = evaluate_beginning_logs(log_dir=str(tdir))
            self.assertTrue(res_dir["ok"], res_dir)
            self.assertTrue(res_dir["all_pass"], res_dir)
            self.assertEqual(res_dir["files_read"]["mission"], 2)

            # CLI explicit multi-file --newgame-log and --mission-log in chronological order also passes
            r_cli = subprocess.run(
                [
                    sys.executable,
                    str(cli),
                    "check-logs",
                    "--newgame-log",
                    str(ng_s1),
                    str(ng_s2),
                    "--mission-log",
                    str(ms_s1),
                    str(ms_s2),
                    "--require-all-pass",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_cli.returncode, 0, r_cli.stdout + r_cli.stderr)

            # Negative multi-session check: console setstage in session 2 ('stage 40 by=other') fails!
            bad_s2 = [ln.replace("stage 40 by=info", "stage 40 by=other") for ln in ms_s2_lines]
            ms_s2.write_text("\n".join(bad_s2) + "\n", encoding="utf-8")
            res_bad = evaluate_beginning_logs(log_dir=str(tdir))
            self.assertFalse(res_bad["ok"])
            self.assertEqual(res_bad["steps"]["B7_preston_turnin"]["status"], "FAIL")

            # H0 check: 'mode fade lifted by=timeout s=15' marks B1_pod FAIL for REACHABLE even if later walk continues
            ng_timeout = [
                "FO4SF_NEWGAME rt=5.0 mode fade lifted by=timeout s=15",
                *_handwritten_newgame_lines(),
            ]
            ng_s1.write_text("\n".join(ng_timeout[:12]) + "\n", encoding="utf-8")
            ms_s2.write_text("\n".join(ms_s2_lines) + "\n", encoding="utf-8")
            res_to = evaluate_beginning_logs(log_dir=str(tdir))
            self.assertFalse(res_to["ok"])
            self.assertEqual(res_to["steps"]["B1_pod"]["status"], "FAIL")
            self.assertIn("mode fade lifted by=timeout", res_to["steps"]["B1_pod"]["detail"])

    def test_player_profile_13_plugin_bundle_and_40pt_special_fallback_pass_and_28pt_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            bundle = self._build_synthetic_bundle(tdir)
            (bundle / "FO4SFProgression.esm").unlink()
            (bundle / "Data" / "Scripts" / "FO4SF_ProgressionQuest.pex").unlink()
            (bundle / "Data" / "Scripts" / "FO4SF_NewGameSpecial.pex").write_bytes(b"PEX_SYNTHETIC_SPECIAL_PAYLOAD")
            player_plan = json.loads((bundle / "bundle_plan.json").read_text(encoding="utf-8"))
            player_plan["plugins"] = [p for p in player_plan["plugins"] if p != "FO4SFProgression.esm"]
            (bundle / "bundle_plan.json").write_text(json.dumps(player_plan), encoding="utf-8")

            ok_player = verify_bundle_beginning_readiness(str(bundle))
            self.assertTrue(ok_player["ok"], ok_player["problems"])

            (bundle / "Data" / "Scripts" / "FO4SF_NewGameSpecial.pex").unlink()
            missing_spec = verify_bundle_beginning_readiness(str(bundle))
            self.assertFalse(missing_spec["ok"])
            self.assertEqual(missing_spec["steps"]["B3_exit_lift"]["status"], "FAIL")

            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")
            player_ng: list[str] = []
            for ln in _handwritten_newgame_lines():
                if "special set" in ln:
                    player_ng.append(
                        "FO4SF_NEWGAME rt=75.0 special set S=6 P=6 E=6 C=5 I=6 A=6 L=5 sum=40 source=Lift readback=6.0 5.0"
                    )
                    player_ng.append(
                        "FO4SF_NEWGAME rt=75.2 elevator attribute_allocation fallback=FO4SF_NewGameSpecial edited=True confirmed=True"
                    )
                else:
                    player_ng.append(ln)
            ng_log.write_text("\n".join(player_ng) + "\n", encoding="utf-8")
            res_player_log = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertTrue(res_player_log["ok"], res_player_log)
            self.assertTrue(res_player_log["all_pass"], res_player_log)
            self.assertEqual(res_player_log["steps"]["B3_exit_lift"]["status"], "PASS")

            # Legacy 28-pt sum on FO4SF_NewGameSpecial fallback must now FAIL B3_exit_lift ("40 for all")
            player_ng_28 = [
                "FO4SF_NEWGAME rt=75.0 special set S=4 P=4 E=4 C=4 I=4 A=4 L=4 sum=28 source=Lift readback=4.0 4.0"
                if "special set" in ln
                else ln
                for ln in player_ng
            ]
            ng_log.write_text("\n".join(player_ng_28) + "\n", encoding="utf-8")
            res_28_fail = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(res_28_fail["ok"])
            self.assertEqual(res_28_fail["steps"]["B3_exit_lift"]["status"], "FAIL")

    def test_verify_bundle_skips_base_terrain_zero_obnd_acti_but_checks_mission(self) -> None:
        def _sub(sig: bytes, data: bytes) -> bytes:
            return sig + struct.pack("<H", len(data)) + data

        def _rec(sig: bytes, fid: int, subs: list[bytes]) -> bytes:
            body = b"".join(subs)
            return sig + struct.pack("<IIIII", len(body), 0, fid, 0, 0) + body

        def _grup(label: bytes, gtype: int, payload: bytes) -> bytes:
            return b"GRUP" + struct.pack("<I", 24 + len(payload)) + label + struct.pack("<III", gtype, 0, 0) + payload

        acti_zero_obnd = _rec(
            b"ACTI",
            0x00193B42,
            [_sub(b"EDID", b"FO4Core_ZeroObndTestActi\x00"), _sub(b"OBND", b"\x00" * 24)],
        )
        refr_placed = _rec(
            b"REFR",
            0x00193B43,
            [_sub(b"EDID", b"FO4Core_ZeroObndTestRef\x00"), _sub(b"NAME", struct.pack("<I", 0x00193B42))],
        )
        bad_plugin_bytes = (
            _dummy_tes4()
            + _grup(b"ACTI", 0, acti_zero_obnd)
            + _grup(b"CELL", 0, _rec(b"CELL", 0x00000D30, []) + _grup(struct.pack("<I", 0x00000D30), 6, refr_placed))
        )

        with tempfile.TemporaryDirectory() as tmp:
            import hashlib as _hashlib
            import json as _json

            bundle = self._build_synthetic_bundle(Path(tmp))
            (bundle / "FO4TerrainCore.esm").write_bytes(bad_plugin_bytes)
            core_sha = _hashlib.sha256(bad_plugin_bytes).hexdigest()
            (bundle / "map-markers" / "core.json").write_text(
                _json.dumps({"schema_version": 1, "masters": {"FO4TerrainCore.esm": core_sha}}, indent=2) + "\n",
                encoding="utf-8",
            )
            ok_res = verify_bundle_beginning_readiness(str(bundle))
            self.assertTrue(ok_res["ok"], ok_res["problems"])

            (bundle / "FO4SFMission.esm").write_bytes(bad_plugin_bytes)
            bad_res = verify_bundle_beginning_readiness(str(bundle))
            self.assertFalse(bad_res["ok"])
            self.assertEqual(bad_res["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")
            self.assertTrue(any("FO4Core_ZeroObndTestActi" in msg for msg in bad_res["problems"]))

    def test_cryopod_anim_check_bundle_enforces_pod_assets_and_records(self) -> None:
        cli = ROOT / "scripts" / "testing" / "check_beginning_pilot.py"
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._build_synthetic_bundle(Path(tmp))
            r_ok = subprocess.run(
                [sys.executable, str(cli), "check-bundle", "--bundle-dir", str(bundle)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_ok.returncode, 0, r_ok.stdout)
            self.assertIn("PASS  pod_anim", r_ok.stdout)

            # Missing FO4SFVaultPod.esm -> FAIL (never pass silently into fallback)
            (bundle / "FO4SFVaultPod.esm").unlink()
            res_no_esm = verify_bundle_beginning_readiness(str(bundle), pod_exit_mode="cryopod_anim")
            self.assertFalse(res_no_esm["ok"])
            self.assertEqual(res_no_esm["pod_anim"]["status"], "FAIL")
            self.assertEqual(res_no_esm["steps"]["B1_pod"]["status"], "FAIL")

            # Missing clip -> FAIL
            _populate_synthetic_vault_pod(bundle)
            (bundle / "Data" / "meshes" / "fo4port" / "pod" / "clips" / "statea_play.afx").unlink()
            res_no_clip = verify_bundle_beginning_readiness(str(bundle), pod_exit_mode="cryopod_anim")
            self.assertFalse(res_no_clip["ok"])
            self.assertEqual(res_no_clip["pod_anim"]["status"], "FAIL")
            self.assertTrue(any("statea_play.afx" in p for p in res_no_clip["problems"]))

            # Missing Disabled flag on 0x001617 -> FAIL
            _populate_synthetic_vault_pod(bundle, disabled_1617=False)
            res_not_dis = verify_bundle_beginning_readiness(str(bundle), pod_exit_mode="cryopod_anim")
            self.assertFalse(res_not_dis["ok"])
            self.assertTrue(any("0x001617" in p and "Initially Disabled" in p for p in res_not_dis["problems"]))

            # Missing Persistent flag on 0x801 -> FAIL
            _populate_synthetic_vault_pod(bundle, refr801_persistent=False)
            res_not_pers = verify_bundle_beginning_readiness(str(bundle), pod_exit_mode="cryopod_anim")
            self.assertFalse(res_not_pers["ok"])
            self.assertTrue(any("0x801" in p and "Persistent" in p for p in res_not_pers["problems"]))


if __name__ == "__main__":
    unittest.main()
