"""Synthetic binary TES4 + QUST + VMAD + PEX + BA2 save-safety unit tests."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
GAME_SCRIPTS = ROOT / "scripts" / "game"
TESTS_DIR = ROOT / "tests"
for p in (SRC, GAME_SCRIPTS, TESTS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ba2_fixture import general_archive  # noqa: E402
import exp_install as exp  # noqa: E402
from fo4sf.planet import esm  # noqa: E402
from fo4sf.save_safety import (  # noqa: E402
    PEX_MAGIC_LE,
    compare_builds,
    one_line_swap_warning,
    parse_pex_properties,
)


def _wstr_cp1252(text: str) -> bytes:
    raw = text.encode("cp1252")
    return struct.pack("<H", len(raw)) + raw


def _encode_vmad_prop(name: str, ptype: int, val) -> bytes:
    head = _wstr_cp1252(name) + struct.pack("<BB", ptype, 1)
    if ptype == 1:  # Object
        return head + struct.pack("<HhI", 0, -1, int(val))
    if ptype == 2:  # String
        return head + _wstr_cp1252(str(val))
    if ptype == 3:  # Int
        return head + struct.pack("<i", int(val))
    if ptype == 4:  # Float
        return head + struct.pack("<f", float(val))
    if ptype == 5:  # Bool
        return head + struct.pack("<B", 1 if val else 0)
    if ptype == 13:  # Int[]
        vals = list(val)
        return head + struct.pack("<I", len(vals)) + b"".join(struct.pack("<i", x) for x in vals)
    raise ValueError(f"unsupported test prop type {ptype}")


def _build_qust_vmad(
    scripts,
    *,
    alias_scripts=(),
    quest_formid: int = 0x01000800,
) -> bytes:
    """Build a synthetic Starfield v6/fmt2 QUST VMAD with optional alias scripts."""
    parts = [struct.pack("<hHH", 6, 2, len(scripts))]
    for sname, props in scripts:
        parts.append(_wstr_cp1252(sname) + struct.pack("<BH", 0, len(props)))
        for pname, ptype, pval in props:
            parts.append(_encode_vmad_prop(pname, ptype, pval))
    # ExtraBindDataVersion=3, 0 stage fragments, empty fragment script name, then alias scripts
    parts.append(struct.pack("<BHH", 3, 0, 0))
    parts.append(struct.pack("<H", len(alias_scripts)))
    for alias_id, sname, props in alias_scripts:
        parts.append(struct.pack("<HhI", 0, alias_id, quest_formid))
        parts.append(struct.pack("<hHH", 6, 2, 1))
        parts.append(_wstr_cp1252(sname) + struct.pack("<BH", 0, len(props)))
        for pname, ptype, pval in props:
            parts.append(_encode_vmad_prop(pname, ptype, pval))
    return b"".join(parts)


def _make_qust_record(
    formid: int,
    edid: str,
    *,
    stages=(10, 20, 200),
    aliases=((0, "ALST", "Target"),),
    vmad: bytes | None = None,
    start_game_enabled: bool = True,
) -> esm.Record:
    subs = [(b"EDID", esm.zbytes(edid))]
    if vmad is not None:
        subs.append((b"VMAD", vmad))
    qflags = 0x0001 if start_game_enabled else 0x0000
    subs.append((b"DNAM", struct.pack("<HBB8s", qflags, 50, 0, b"\0" * 8)))
    for st in stages:
        subs.append((b"INDX", struct.pack("<HBB", st, 0, 0)))
    for al_id, kind, al_name in aliases:
        subs.append((kind.encode("ascii"), struct.pack("<I", al_id)))
        subs.append((b"ALID", esm.zbytes(al_name)))
        subs.append((b"ALED", b""))
    return esm.Record(b"QUST", formid, subs)


def _write_plugin(path: Path, masters=("Starfield.esm",), records=()) -> Path:
    writer = esm.PluginWriter(masters)
    for rec in records:
        writer.add(rec)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer.write(str(path))
    return path


def _build_synthetic_pex(script_name: str, props: list[tuple[str, str]]) -> bytes:
    """Build a valid Starfield v3.12 little-endian PEX (`0xFA57C0DE`) with the given auto properties."""
    strings = [script_name, "Quest", "", "AutoState"]
    prop_indices = []
    for pname, ptype in props:
        av_name = f"::{pname}_var"
        for tok in (pname, ptype, av_name):
            if tok not in strings:
                strings.append(tok)
        prop_indices.append((strings.index(pname), strings.index(ptype), strings.index(av_name)))

    def pstr(s: str) -> bytes:
        b = s.encode("utf-8")
        return struct.pack("<H", len(b)) + b

    head = struct.pack("<IBBHQ", PEX_MAGIC_LE, 3, 12, 4, 0)
    head += pstr(f"{script_name}.psc") + pstr("<test>") + pstr("<host>")
    head += struct.pack("<H", len(strings)) + b"".join(pstr(s) for s in strings)
    head += b"\x00"  # has_debug = 0
    head += struct.pack("<H", 0)  # user_flags = 0
    head += struct.pack("<H", 1)  # 1 object

    # Object body (after name_idx): size(u32 includes size field itself) + parent(u16) + doc(u16) + const(u8) + uf(u32) + autoState(u16)
    body = struct.pack("<HHBIH", 1, 2, 0, 0, 3)
    body += struct.pack("<H", 0)  # structs = 0
    body += struct.pack("<H", len(prop_indices))  # backing variables
    for _pn, pt, av in prop_indices:
        body += struct.pack("<HHI", av, pt, 0) + b"\x00" + b"\x00"  # null var_data + const=0
    body += struct.pack("<H", 0)  # guards = 0 (v3.12)
    body += struct.pack("<H", len(prop_indices))  # properties
    for pn, pt, av in prop_indices:
        body += struct.pack("<HHHIBH", pn, pt, 2, 0, 0x07, av)
    body += struct.pack("<H", 0)  # states = 0

    obj = struct.pack("<HI", 0, 4 + len(body)) + body
    return head + obj


class SaveSafetyTests(unittest.TestCase):
    def _make_baseline_bundle(self, folder: Path) -> Path:
        vmad = _build_qust_vmad(
            [("FO4SF_AlphaQuest", [("Count", 3, 10), ("Label", 2, "start")])],
            alias_scripts=[(0, "FO4SF_AlphaAlias", [("Version", 4, 1.0)])],
        )
        q1 = _make_qust_record(
            0x01000800,
            "FO4SF_Alpha",
            stages=(10, 20, 200),
            aliases=((0, "ALST", "Player"), (1, "ALST", "Companion")),
            vmad=vmad,
        )
        _write_plugin(folder / "FO4SFAlpha.esm", masters=("Starfield.esm",), records=[q1])
        _write_plugin(folder / "FO4SFBeta.esm", masters=("Starfield.esm", "FO4SFAlpha.esm"), records=[])
        pex_dir = folder / "Data" / "Scripts"
        pex_dir.mkdir(parents=True, exist_ok=True)
        (pex_dir / "FO4SF_AlphaQuest.pex").write_bytes(
            _build_synthetic_pex("FO4SF_AlphaQuest", [("Count", "Int"), ("Label", "String")])
        )
        (pex_dir / "FO4SF_AlphaAlias.pex").write_bytes(
            _build_synthetic_pex("FO4SF_AlphaAlias", [("Version", "Float")])
        )
        return folder

    def test_identical_build_is_safe_and_has_no_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b1 = self._make_baseline_bundle(root / "b1")
            b2 = self._make_baseline_bundle(root / "b2")
            rep = compare_builds(str(b1), str(b2))
            self.assertEqual(rep["verdict"], "SAFE")
            self.assertTrue(rep["save_compatible"])
            self.assertEqual(rep["breaking"], [])
            self.assertIsNone(one_line_swap_warning(rep))

    def test_appended_plugin_is_safe_append_removed_breaks_and_inserted_or_reordered_emit_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = self._make_baseline_bundle(root / "before")

            # 1. Appended plugin at end -> SAFE_APPEND
            appended = self._make_baseline_bundle(root / "appended")
            _write_plugin(appended / "FO4SFZeta.esm", masters=("Starfield.esm",), records=[])
            rep_app = compare_builds(str(before), str(appended))
            self.assertEqual(rep_app["verdict"], "SAFE_APPEND")
            self.assertIsNone(one_line_swap_warning(rep_app))
            self.assertEqual(rep_app["plugin_diff"]["appended"], ["FO4SFZeta.esm"])

            # 2. Removed plugin -> BREAKING (removed_plugin)
            removed = self._make_baseline_bundle(root / "removed")
            (removed / "FO4SFBeta.esm").unlink()
            rep_rem = compare_builds(str(before), str(removed))
            self.assertEqual(rep_rem["verdict"], "BREAKING")
            self.assertFalse(rep_rem["save_compatible"])
            self.assertEqual(rep_rem["counts"]["removed_plugin"], 1)
            self.assertIn("removed_plugin=1", one_line_swap_warning(rep_rem))

            # 3. Inserted plugin before existing FO4SFBeta.esm -> NOTE (unverified, waits for a game test)
            inserted = self._make_baseline_bundle(root / "inserted")
            _write_plugin(inserted / "FO4SFAardvark.esm", masters=("Starfield.esm",), records=[])
            (inserted / "bundle_plan.json").write_text(
                json.dumps({"plugins": ["FO4SFAlpha.esm", "FO4SFAardvark.esm", "FO4SFBeta.esm"]}),
                encoding="utf-8",
            )
            rep_ins = compare_builds(str(before), str(inserted))
            self.assertEqual(rep_ins["verdict"], "NOTE")
            self.assertTrue(rep_ins["save_compatible"])
            self.assertEqual(rep_ins["breaking"], [])
            self.assertEqual(rep_ins["counts"]["inserted_plugin_shifts_indices"], 1)
            ins_note = one_line_swap_warning(rep_ins)
            self.assertIsNotNone(ins_note)
            self.assertTrue(ins_note.startswith("NOTE:"), ins_note)
            self.assertIn("inserted_plugin_shifts_indices=1", ins_note)
            self.assertIn("unverified, waits for a game test", ins_note)

            # 4. Reordered surviving plugins -> NOTE (unverified, waits for a game test)
            reord_before = root / "reord_before"
            _write_plugin(reord_before / "FO4SFA.esm", masters=("Starfield.esm",), records=[])
            _write_plugin(reord_before / "FO4SFB.esm", masters=("Starfield.esm",), records=[])
            (reord_before / "bundle_plan.json").write_text(
                json.dumps({"plugins": ["FO4SFA.esm", "FO4SFB.esm"]}), encoding="utf-8"
            )
            reord_after = root / "reord_after"
            _write_plugin(reord_after / "FO4SFA.esm", masters=("Starfield.esm",), records=[])
            _write_plugin(reord_after / "FO4SFB.esm", masters=("Starfield.esm",), records=[])
            (reord_after / "bundle_plan.json").write_text(
                json.dumps({"plugins": ["FO4SFB.esm", "FO4SFA.esm"]}), encoding="utf-8"
            )
            rep_reord = compare_builds(str(reord_before), str(reord_after))
            self.assertEqual(rep_reord["verdict"], "NOTE")
            self.assertTrue(rep_reord["save_compatible"])
            self.assertEqual(rep_reord["breaking"], [])
            self.assertGreaterEqual(rep_reord["counts"]["reordered_plugin"], 1)
            reord_note = one_line_swap_warning(rep_reord)
            self.assertIsNotNone(reord_note)
            self.assertTrue(reord_note.startswith("NOTE:"), reord_note)
            self.assertIn("reordered_plugin=", reord_note)
            self.assertIn("unverified, waits for a game test", reord_note)

    def test_changed_vmad_property_and_packed_ba2_pex_property_break(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = self._make_baseline_bundle(root / "before")

            # Mutate VMAD property Count from Int (3) to Float (4), and retype packed BA2 PEX property Version Float -> Int
            after = root / "after"
            bad_vmad = _build_qust_vmad(
                [("FO4SF_AlphaQuest", [("Count", 4, 10.0), ("Label", 2, "start")])],
                alias_scripts=[(0, "FO4SF_AlphaAlias", [("Version", 4, 1.0)])],
            )
            q1 = _make_qust_record(
                0x01000800,
                "FO4SF_Alpha",
                stages=(10, 20, 200),
                aliases=((0, "ALST", "Player"), (1, "ALST", "Companion")),
                vmad=bad_vmad,
            )
            _write_plugin(after / "FO4SFAlpha.esm", masters=("Starfield.esm",), records=[q1])
            _write_plugin(after / "FO4SFBeta.esm", masters=("Starfield.esm", "FO4SFAlpha.esm"), records=[])

            # Pack scripts into FO4SFAlpha - Main.ba2 (no loose Data/Scripts) to verify BA2 .pex inspection!
            pex_alpha = _build_synthetic_pex("FO4SF_AlphaQuest", [("Count", "Float")])  # Label deleted + Count retyped!
            pex_alias = _build_synthetic_pex("FO4SF_AlphaAlias", [("Version", "Int")])  # Version retyped!
            parsed_check = parse_pex_properties(pex_alpha, "synthetic")
            self.assertIn("fo4sf_alphaquest", parsed_check)
            ba2_bytes = general_archive(
                {
                    "Scripts/FO4SF_AlphaQuest.pex": pex_alpha,
                    "Scripts/FO4SF_AlphaAlias.pex": pex_alias,
                }
            )
            (after / "FO4SFAlpha - Main.ba2").write_bytes(ba2_bytes)

            rep = compare_builds(str(before), str(after))
            self.assertEqual(rep["verdict"], "BREAKING")
            # 1 VMAD retype + 1 PEX delete (Label) + 2 PEX retypes (Count, Version) = 4 changed_script_property findings
            self.assertEqual(rep["counts"]["changed_script_property"], 4)
            warn = one_line_swap_warning(rep)
            self.assertIsNotNone(warn)
            self.assertNotIn("\n", warn)
            self.assertIn("changed_script_property=4", warn)

    def test_removed_quest_stage_or_alias_breaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = self._make_baseline_bundle(root / "before")
            after = self._make_baseline_bundle(root / "after")

            # Rewrite FO4SFAlpha.esm with stage 20 removed and alias 1 renumbered to alias 5
            vmad = _build_qust_vmad(
                [("FO4SF_AlphaQuest", [("Count", 3, 10), ("Label", 2, "start")])],
                alias_scripts=[(0, "FO4SF_AlphaAlias", [("Version", 4, 1.0)])],
            )
            q1_mut = _make_qust_record(
                0x01000800,
                "FO4SF_Alpha",
                stages=(10, 200),  # stage 20 removed!
                aliases=((0, "ALST", "Player"), (5, "ALST", "Companion")),  # alias ID 1 -> 5!
                vmad=vmad,
            )
            _write_plugin(after / "FO4SFAlpha.esm", masters=("Starfield.esm",), records=[q1_mut])

            rep = compare_builds(str(before), str(after))
            self.assertEqual(rep["verdict"], "BREAKING")
            self.assertEqual(rep["counts"]["changed_quest_or_alias"], 2)
            self.assertIn("changed_quest_or_alias=2", one_line_swap_warning(rep))

    def test_exp_install_emits_one_line_swap_warning_explicitly_and_automatically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            (game / "Data").mkdir(parents=True)
            local = root / "local"
            (local / "Starfield").mkdir(parents=True)
            (local / "Starfield" / "Plugins.txt").write_bytes(b"*Starfield.esm\r\n")

            stage_v1 = self._make_baseline_bundle(root / "stage_v1")
            stage_v2 = self._make_baseline_bundle(root / "stage_v2")
            # Break stage_v2 by removing FO4SFBeta.esm and removing stage 20
            (stage_v2 / "FO4SFBeta.esm").unlink()
            q_broken = _make_qust_record(0x01000800, "FO4SF_Alpha", stages=(10, 200), aliases=((0, "ALST", "Player"),))
            _write_plugin(stage_v2 / "FO4SFAlpha.esm", masters=("Starfield.esm",), records=[q_broken])

            with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}):
                # 1. Install v1 cleanly (no warning)
                buf1 = io.StringIO()
                with patch("sys.stdout", buf1):
                    exp.main(
                        [
                            "install",
                            "--exp-dir",
                            str(stage_v1),
                            "--starfield",
                            str(game),
                            "--plugins",
                            "FO4SFAlpha.esm,FO4SFBeta.esm",
                        ]
                    )
                self.assertNotIn("WARNING: swapping builds will invalidate existing saves", buf1.getvalue())

                # 2. Uninstall v1 (preserves receipt), then install v2 WITHOUT flags -> automatic receipt swap warning!
                exp.uninstall(SimpleNamespace(starfield=str(game)))
                buf2 = io.StringIO()
                with patch("sys.stdout", buf2):
                    exp.main(
                        [
                            "install",
                            "--exp-dir",
                            str(stage_v2),
                            "--starfield",
                            str(game),
                            "--plugins",
                            "FO4SFAlpha.esm",
                        ]
                    )
                out2_lines = buf2.getvalue().splitlines()
                warn_lines = [ln for ln in out2_lines if ln.startswith("WARNING: swapping builds will invalidate existing saves")]
                self.assertEqual(len(warn_lines), 1)
                self.assertIn("removed_plugin=1", warn_lines[0])
                self.assertIn("changed_quest_or_alias=", warn_lines[0])
                self.assertTrue(out2_lines[-1].startswith("installed "), "final stdout line must stay 'installed ...'")

                # 3. Also verify CLI --check-save-swap via subprocess
                exp.uninstall(SimpleNamespace(starfield=str(game)))
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        str(GAME_SCRIPTS / "exp_install.py"),
                        "install",
                        "--exp-dir",
                        str(stage_v2),
                        "--starfield",
                        str(game),
                        "--plugins",
                        "FO4SFAlpha.esm",
                        "--check-save-swap",
                        str(stage_v1),
                    ],
                    env={**os.environ, "LOCALAPPDATA": str(local)},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("WARNING: swapping builds will invalidate existing saves", proc.stdout)

    def test_live_data_dir_ignores_starfield_misc_ba2_containing_pex(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            data = game / "Data"
            data.mkdir(parents=True)
            local = root / "local"
            (local / "Starfield").mkdir(parents=True)
            (local / "Starfield" / "Plugins.txt").write_bytes(b"*Starfield.esm\r\n")

            # Place a fake vanilla 'Starfield - Misc.ba2' holding a .pex inside live Data/
            vanilla_pex = _build_synthetic_pex("VanillaBaseQuestScript", [("BaseProp", "Int")])
            (data / "Starfield - Misc.ba2").write_bytes(
                general_archive({"Scripts/VanillaBaseQuestScript.pex": vanilla_pex})
            )

            stage_v1 = self._make_baseline_bundle(root / "stage_v1")
            with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}):
                exp.main(
                    [
                        "install",
                        "--exp-dir",
                        str(stage_v1),
                        "--starfield",
                        str(game),
                        "--plugins",
                        "FO4SFAlpha.esm,FO4SFBeta.esm",
                    ]
                )
                # Both <game> and <game>/Data (where plugin_root == data_root) must skip Starfield - Misc.ba2!
                rep_game = compare_builds(str(game), str(stage_v1))
                self.assertEqual(rep_game["verdict"], "SAFE", rep_game["breaking"])
                self.assertEqual(rep_game["before"]["summary"]["pex_script_count"], 2)

                rep_data = compare_builds(str(data), str(stage_v1))
                self.assertEqual(rep_data["verdict"], "SAFE", rep_data["breaking"])
                self.assertEqual(rep_data["before"]["summary"]["pex_script_count"], 2)


if __name__ == "__main__":
    unittest.main()
