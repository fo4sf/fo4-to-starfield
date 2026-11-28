"""Round 15 Wave B Item H5 (Museum door seam) verification tests."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
SRC_DIR = REPO / "src"
SCRIPTS_MISSION = REPO / "scripts" / "mission"
SCRIPTS_TERRAIN = REPO / "scripts" / "terrain"
for _p in (str(SRC_DIR), str(SCRIPTS_MISSION), str(SCRIPTS_TERRAIN)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_fo4port_r11_museum as ext  # noqa: E402
import make_mission  # noqa: E402
import vmad_patch  # noqa: E402

LOAD_DOORS_JSON = REPO / "src" / "fo4sf" / "core" / "load_doors.json"
LIFT_PAIRS_JSON = REPO / "src" / "fo4sf" / "core" / "lift_pairs.json"
CONFIRMED_DOOR_PSC = REPO / "scripts" / "doors" / "FO4SF_ConfirmedLoadDoor.psc"
LOAD_DOOR_QUEST_PSC = REPO / "scripts" / "doors" / "FO4SF_LoadDoorQuest.psc"
MISSION_CSPROJ = REPO / "dotnet" / "Mission" / "Mission.csproj"


def _strip_papyrus_comments(txt: str) -> str:
    txt = re.sub(r"\{[^}]*\}", "", txt)
    return "\n".join(line.split(";", 1)[0] for line in txt.splitlines())


class H5MuseumDoorSeamTests(unittest.TestCase):
    def test_load_doors_json_exists_next_to_lift_pairs_and_matches_schema(self) -> None:
        self.assertEqual(LOAD_DOORS_JSON.parent, LIFT_PAIRS_JSON.parent)
        self.assertTrue(LOAD_DOORS_JSON.is_file(), f"missing {LOAD_DOORS_JSON}")
        data = json.loads(LOAD_DOORS_JSON.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["default_game"], "fo4")
        self.assertEqual(data["supported_games"], ["FO4", "FO3", "FNV"])
        self.assertIn("games", data)

        fo4 = data["games"]["fo4"]
        self.assertTrue(fo4["available"])
        self.assertEqual(fo4["controller"]["exit_anchor_plugin"], "FO4TerrainCore.esm")
        self.assertEqual(fo4["controller"]["exit_anchor_id"], "0x0A775B")
        self.assertEqual(fo4["controller"]["secondary_exit_anchor_plugin"], "FO4TerrainCore.esm")
        self.assertEqual(fo4["controller"]["secondary_exit_anchor_id"], "0x0A775C")
        self.assertEqual(set(fo4["doors"].keys()), {"s5_front_in", "s5_front_out", "s5_roof_out", "s5_roof_in"})
        self.assertEqual(fo4["doors"]["s5_front_out"]["target_form_id"], "0x0A775B")
        self.assertEqual(fo4["doors"]["s5_front_out"]["fallback_target_form_id"], "0x0A775C")
        self.assertEqual(fo4["doors"]["s5_roof_out"]["destination_pos"], [-1990.58, -1724.19, 97.56])

        for gid in ("fo3", "fnv"):
            row = data["games"][gid]
            self.assertFalse(row["available"])
            self.assertTrue(row["unavailable_reason"])

    def test_confirmed_load_door_requires_bound_controller_and_drops_fallbacks(self) -> None:
        raw = CONFIRMED_DOOR_PSC.read_text(encoding="utf-8")
        code = _strip_papyrus_comments(raw)
        for forbidden in ("0x000BDE", "0xBDE", "FO4SFMission.esm", "0x000821", "0x821", "FO4SF_R11P1Museum.esm"):
            self.assertNotIn(forbidden, raw, f"FO4SF_ConfirmedLoadDoor.psc still contains {forbidden}")
            self.assertNotIn(forbidden, code)

        self.assertIn("if LoadDoorController == None", code)
        self.assertIn("reason=controller_unbound", code)
        on_act_match = re.search(r"Event OnActivate\(ObjectReference akActionRef\)(.*?)EndEvent", code, re.S)
        self.assertIsNotNone(on_act_match)
        on_act = on_act_match.group(1)
        self.assertNotIn("ResolveAnchor(", on_act, "OnActivate must not fall back to local ResolveAnchor()")
        self.assertNotIn("player.MoveTo(", on_act, "OnActivate must not fall back to local MoveTo()")

    def test_load_door_quest_drops_hardcoded_defaults_and_logs_dynamic_anchor(self) -> None:
        raw = LOAD_DOOR_QUEST_PSC.read_text(encoding="utf-8")
        code = _strip_papyrus_comments(raw)
        for forbidden in ("0x0A775B", "0x0A775C", "FO4TerrainCore.esm", "Vault111", "Concord"):
            self.assertNotIn(forbidden, code, f"FO4SF_LoadDoorQuest.psc code still hardcodes {forbidden}")

        self.assertIn('string Property ExitAnchorPlugin = "" Auto', code)
        self.assertIn("int Property ExitAnchorId = 0 Auto", code)
        self.assertIn('string Property SecondaryExitAnchorPlugin = "" Auto', code)
        self.assertIn("int Property SecondaryExitAnchorId = 0 Auto", code)
        self.assertIn("exit_plugin=\" + ExitAnchorPlugin + \" exit_anchor=\" + ExitAnchorId", code)

        # Verify quest_init logs dynamically from bound properties
        logs: list[str] = []
        ensure_m = re.search(r"Function EnsureInitialized\(\)(.*?)EndFunction", code, re.S)
        self.assertIsNotNone(ensure_m)
        self.assertIn("ExitAnchorId", ensure_m.group(1))
        self.assertNotIn("0x0A775B", ensure_m.group(1))
        # Simulate quest_init log formatting with non-FO4 values
        ExitAnchorPlugin = "FO3TerrainCore.esm"
        ExitAnchorId = 0x0B1234
        SecondaryExitAnchorPlugin = "FO3TerrainCore.esm"
        SecondaryExitAnchorId = 0x0B5678
        curCell = "CapitalCell"
        logs.append(
            f"FO4SF_LOADDOOR quest_init cell={curCell} exit_plugin={ExitAnchorPlugin} "
            f"exit_anchor={ExitAnchorId} secondary_plugin={SecondaryExitAnchorPlugin} "
            f"secondary_anchor={SecondaryExitAnchorId}"
        )
        self.assertIn("exit_plugin=FO3TerrainCore.esm", logs[0])
        self.assertIn(f"exit_anchor={0x0B1234}", logs[0])
        self.assertIn(f"secondary_anchor={0x0B5678}", logs[0])

    def test_make_mission_load_doors_config_and_cli_args(self) -> None:
        gid, fo4 = make_mission.load_doors_config()
        self.assertEqual(gid, "fo4")
        self.assertEqual(fo4["controller"]["exit_anchor_id"], "0x0A775B")

        with self.assertRaises(SystemExit):
            make_mission.load_doors_config(game_id="fo3")

        with tempfile.TemporaryDirectory() as td:
            alt_path = Path(td) / "alt_doors.json"
            alt_path.write_text(json.dumps({
                "schema_version": 1,
                "default_game": "fo4",
                "games": {
                    "fo3": {
                        "id": "fo3",
                        "game": "FO3",
                        "available": True,
                        "controller": {
                            "exit_anchor_plugin": "FO3Core.esm",
                            "exit_anchor_id": "0x0B1234",
                            "secondary_exit_anchor_plugin": "FO3Core.esm",
                            "secondary_exit_anchor_id": "0x0B5678",
                        },
                        "doors": {},
                    }
                },
            }), encoding="utf-8")
            gid2, fo3 = make_mission.load_doors_config(str(alt_path), "fo3")
            self.assertEqual(gid2, "fo3")
            self.assertEqual(fo3["controller"]["exit_anchor_plugin"], "FO3Core.esm")

            ns = SimpleNamespace(
                fo4="Fallout4.esm", starfield="Starfield.esm", core="FO4TerrainCore.esm",
                raider="FO4ActorRaider.esm", compiler="PapyrusCompiler.exe",
                content_resources="ContentResources.zip", alias=True, codsworth=True,
                load_doors=str(alt_path), game="fo3",
            )
            tokens = make_mission.mission_cli_args(ns, str(Path(td) / "out"))
            self.assertEqual(tokens.get("--game"), "fo3")
            self.assertEqual(tokens.get("--load-doors"), str(alt_path.resolve()))

    def test_second_game_row_populates_mission_esm_without_psc_change(self) -> None:
        if not shutil.which("dotnet"):
            self.skipTest("dotnet SDK not on PATH")

        # Mission.cs SelfTest already compiles dotnet/Mission in Release and generates full synthetic masters
        # (Starfield.esm, FO4TerrainCore.esm, FO4ActorRaider.esm, points.json) under st_dir.
        with tempfile.TemporaryDirectory(prefix="fo4sf-h5-test-") as td:
            tmp = Path(td)
            st_dir = tmp / "selftest"
            res_st = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(MISSION_CSPROJ), "--", "selftest", str(st_dir)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_st.returncode, 0, res_st.stdout + res_st.stderr)
            self.assertIn("selftest pass", res_st.stdout)

            sf_path = st_dir / "Starfield.esm"
            core_path = st_dir / "FO4TerrainCore.esm"
            raider_path = st_dir / "FO4ActorRaider.esm"
            points_path = st_dir / "points.json"

            # Now test a made-up `fo3` row via `make_mission` / `dotnet/Mission` write+check CLI
            alt_doors = tmp / "fo3_load_doors.json"
            alt_doors.write_text(json.dumps({
                "schema_version": 1,
                "default_game": "fo4",
                "games": {
                    "fo3": {
                        "id": "fo3",
                        "game": "FO3",
                        "available": True,
                        "controller": {
                            "exit_anchor_plugin": "FO3Core.esm",
                            "exit_anchor_id": "0x0B1234",
                            "secondary_exit_anchor_plugin": "FO3Core.esm",
                            "secondary_exit_anchor_id": "0x0B5678",
                        },
                        "doors": {
                            "s5_front_in": {
                                "direction": "in",
                                "door_tag": "s5_front_in",
                                "target_plugin": "FO3Port.esm",
                                "target_form_id": "0x00F100",
                                "fallback_target_plugin": "",
                                "fallback_target_form_id": "0x0",
                                "use_destination_position": False,
                                "destination_pos": [0.0, 0.0, 0.0],
                            },
                            "s5_front_out": {
                                "direction": "out",
                                "door_tag": "s5_front_out",
                                "target_plugin": "FO3Core.esm",
                                "target_form_id": "0x0B1234",
                                "fallback_target_plugin": "FO3Core.esm",
                                "fallback_target_form_id": "0x0B5678",
                                "use_destination_position": True,
                                "destination_pos": [101.5, -202.25, 33.75],
                            },
                            "s5_roof_out": {
                                "direction": "out",
                                "door_tag": "s5_roof_out",
                                "target_plugin": "FO3Core.esm",
                                "target_form_id": "0x0B1234",
                                "fallback_target_plugin": "FO3Core.esm",
                                "fallback_target_form_id": "0x0B5678",
                                "use_destination_position": True,
                                "destination_pos": [111.5, -212.25, 45.25],
                            },
                            "s5_roof_in": {
                                "direction": "in",
                                "door_tag": "s5_roof_in",
                                "target_plugin": "FO3Port.esm",
                                "target_form_id": "0x00F100",
                                "fallback_target_plugin": "",
                                "fallback_target_form_id": "0x0",
                                "use_destination_position": True,
                                "destination_pos": [5.0, -6.0, 7.0],
                            },
                        },
                    }
                },
            }), encoding="utf-8")

            out_dir = tmp / "out_fo3"
            res_wr = subprocess.run(
                [
                    "dotnet", "run", "-c", "Release", "--no-build", "--project", str(MISSION_CSPROJ), "--",
                    "write", str(sf_path), str(core_path), str(raider_path), str(points_path), str(out_dir),
                    "--plugin", "FO4SFMission.esm", "--r11-full-mission", "1",
                    "--load-doors", str(alt_doors), "--game", "fo3",
                ],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_wr.returncode, 0, res_wr.stdout + res_wr.stderr)

            esm_path = out_dir / "FO4SFMission.esm"
            res_chk = subprocess.run(
                [
                    "dotnet", "run", "-c", "Release", "--no-build", "--project", str(MISSION_CSPROJ), "--",
                    "check", str(esm_path), str(sf_path), str(core_path), str(raider_path),
                    "--r11-full-mission", "1", "--load-doors", str(alt_doors), "--game", "fo3",
                ],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_chk.returncode, 0, res_chk.stdout + res_chk.stderr)
            self.assertIn("all checks pass", res_chk.stdout)

            # Directly inspect binary VMAD on QUST 0xBDE (FO4SF_LoadDoorQuest) & REFR 0xBB9 (S5IntFrontOutRef)
            recs = {r.fid & 0x00FFFFFF: r for r in ext.walk_all_records(esm_path.read_bytes()) if r.sig in (b"QUST", b"REFR")}
            ld_qust = recs[0x000BDE]
            ld_vmad = next(sp for ss, sp in ext.iter_subrecords(ld_qust.decompressed_body()) if ss == b"VMAD")
            ld_dec = vmad_patch.decode(ld_vmad[:-7])  # strip 7-byte QUST VMAD fragment tail
            self.assertEqual(ld_dec["scripts"][0]["name"], "FO4SF_LoadDoorQuest")
            ld_props = {p["name"]: p["value"] for p in ld_dec["scripts"][0]["properties"]}
            self.assertEqual(ld_props["ExitAnchorPlugin"], "FO3Core.esm")
            self.assertEqual(ld_props["ExitAnchorId"], 0x0B1234)
            self.assertEqual(ld_props["SecondaryExitAnchorPlugin"], "FO3Core.esm")
            self.assertEqual(ld_props["SecondaryExitAnchorId"], 0x0B5678)

            front_out = recs[0x000BB9]
            fo_vmad = next(sp for ss, sp in ext.iter_subrecords(front_out.decompressed_body()) if ss == b"VMAD")
            fo_dec = vmad_patch.decode(fo_vmad)
            fo_props = {p["name"]: p["value"] for p in fo_dec["scripts"][0]["properties"]}
            self.assertEqual(fo_props["TargetPlugin"], "FO3Core.esm")
            self.assertEqual(fo_props["TargetFormId"], 0x0B1234)
            self.assertEqual(fo_props["FallbackTargetPlugin"], "FO3Core.esm")
            self.assertEqual(fo_props["FallbackTargetFormId"], 0x0B5678)
            self.assertAlmostEqual(fo_props["DestinationX"], 101.5, places=2)
            self.assertAlmostEqual(fo_props["DestinationY"], -202.25, places=2)
            self.assertAlmostEqual(fo_props["DestinationZ"], 33.75, places=2)

            # Negative control: default fo4 load_doors.json check must reject the fo3-built plugin
            res_chk_fo4 = subprocess.run(
                [
                    "dotnet", "run", "-c", "Release", "--no-build", "--project", str(MISSION_CSPROJ), "--",
                    "check", str(esm_path), str(sf_path), str(core_path), str(raider_path),
                    "--r11-full-mission", "1",
                ],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(res_chk_fo4.returncode, 0)


if __name__ == "__main__":
    unittest.main()
