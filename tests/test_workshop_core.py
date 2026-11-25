"""Unit, contract, log-stitching, binary-layout, stage/fold/verify, and ride-along installer tests for
CF-9 Settlements, Junk Scrapping (CMPO -> IRES), Bench Recipes (FO4 COBJ + FNV RCPE), and Portable C.A.M.P.s."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "workshop"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
sys.path.insert(0, str(ROOT / "src"))

from ba2_fixture import archive_from_tree  # noqa: E402
import exp_install  # noqa: E402
import make_workshop_core as mwc  # noqa: E402
import workshop_core_install as wci  # noqa: E402
from fo4sf.core.core_values import CORE_VALUES_PLUGIN, core_form_id  # noqa: E402
from fo4sf.workshop import core_log  # noqa: E402

PSC_PATH = ROOT / "scripts" / "workshop" / "FO4SF_WorkshopCoreQuest.psc"
CS_PATH = ROOT / "dotnet" / "WorkshopCore" / "Program.cs"
DOC_PATH = ROOT / "docs" / "workshop" / "workshop-camps.md"

PSC_TEXT = PSC_PATH.read_text(encoding="utf-8")
CS_TEXT = CS_PATH.read_text(encoding="utf-8")
DOC_TEXT = DOC_PATH.read_text(encoding="utf-8")

DOTNET_ENABLED = os.environ.get("FO4SF_DOTNET_TESTS", "") == "1" and shutil.which("dotnet") is not None

PAPYRUS_RESERVED_TYPES = {
    "race", "cell", "form", "actor", "quest", "furniture", "keyword", "spell", "game", "debug",
    "utility", "int", "float", "string", "bool", "math", "location", "activator", "message",
    "armor", "weapon", "formlist", "objectreference", "globalvariable", "worldspace",
}


def cs_const_uints(text):
    out = {}
    for m in re.finditer(r"\bconst\s+uint\s+(\w+)\s*=\s*(0x[0-9A-Fa-f]+)\s*;", text):
        out[m.group(1)] = int(m.group(2), 16)
    return out


def parse_tes4_header(plugin_bytes):
    sig, size, flags = struct.unpack_from("<4sII", plugin_bytes, 0)
    assert sig == b"TES4", f"unexpected header signature {sig!r}"
    pos = 24
    end = 24 + size
    masters = []
    while pos < end:
        sub_sig, sub_len = struct.unpack_from("<4sH", plugin_bytes, pos)
        pos += 6
        payload = plugin_bytes[pos : pos + sub_len]
        pos += sub_len
        if sub_sig == b"MAST":
            masters.append(payload.rstrip(b"\x00").decode("utf-8"))
    return flags, masters


def make_fake_content_resources(zip_path):
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "Flags {\n}\n")
        z.writestr(
            "Scripts/Source/ScriptObject.psc",
            "\n".join(
                [
                    "Scriptname ScriptObject Native",
                    "Function StartTimer(float afInterval, int aiTimerID = 0) native",
                    "bool Function RegisterForRemoteEvent(ScriptObject akEventSource, string asEventName) native",
                    "Function UnregisterForRemoteEvent(ScriptObject akEventSource, string asEventName) native",
                    "Function AddInventoryEventFilter(Form akFilter) native",
                    "Function RemoveAllInventoryEventFilters() native",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/Form.psc",
            "\n".join(
                [
                    "Scriptname Form extends ScriptObject Native",
                    "int Function GetFormID() native",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/Quest.psc",
            "\n".join(
                [
                    "Scriptname Quest extends Form Native",
                    "bool Function GetStageDone(int aiStage)",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/ObjectReference.psc",
            "\n".join(
                [
                    "Scriptname ObjectReference extends Form Native",
                    "int Function GetItemCount(Form akItem = None) native",
                    "Function AddItem(Form akItemToAdd, int aiCount = 1, bool abSilent = false) native",
                    "int Function RemoveItem(Form akItemToRemove, int aiCount = 1, bool abSilent = false, ObjectReference akOtherContainer = None) native",
                    "ObjectReference Function PlaceAtMe(Form akFormToPlace, int aiCount = 1, bool abForcePersist = false, bool abInitiallyDisabled = false, bool abDeleteWhenAble = true) native",
                    "float Function GetPositionX() native",
                    "float Function GetPositionY() native",
                    "float Function GetPositionZ() native",
                    "float Function GetDistance(ObjectReference akOther) native",
                    "Cell Function GetParentCell() native",
                    "WorldSpace Function GetWorldSpace() native",
                    "float Function GetAngleZ() native",
                    "bool Function Is3DLoaded() native",
                    "bool Function IsDisabled() native",
                    "bool Function IsDeleted() native",
                    "Function DisableNoWait(bool abFadeOut = false) native",
                    "Function Delete() native",
                    "Function MoveTo(ObjectReference akTarget, float afXOffset = 0.0, float afYOffset = 0.0, float afZOffset = 0.0, bool abMatchRotation = true) native",
                    "Form Function GetBaseObject() native",
                    "ObjectReference[] Function FindAllReferencesWithKeyword(Form akKeywordOrList, float afRadius) native",
                    "bool Function HasKeyword(Keyword apKeyword) native",
                    "Event OnItemRemoved(Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akDestContainer, int aiTransferReason)",
                    "Event OnWorkshopMode(bool aStart)",
                    "Event OnWorkshopObjectPlaced(ObjectReference akReference)",
                    "Event OnWorkshopObjectRemoved(ObjectReference akReference)",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/Actor.psc",
            "\n".join(
                [
                    "Scriptname Actor extends ObjectReference Native",
                    "Event OnPlayerLoadGame()",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/FormList.psc",
            "\n".join(
                [
                    "Scriptname FormList extends Form Native",
                    "int Function GetSize() native",
                    "Form Function GetAt(int aiIndex) native",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/GlobalVariable.psc",
            "\n".join(
                [
                    "Scriptname GlobalVariable extends Form Native",
                    "float Function GetValue() native",
                    "Function SetValue(float afNewValue) native",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/Math.psc",
            "\n".join(
                [
                    "Scriptname Math Native",
                    "float Function Sin(float afValue) native global",
                    "float Function Cos(float afValue) native global",
                    "float Function Sqrt(float afValue) native global",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/Game.psc",
            "\n".join(
                [
                    "Scriptname Game Native",
                    "Actor Function GetPlayer() native global",
                    "Form Function GetFormFromFile(int aiFormID, string asFilename) native global",
                    "bool Function IsPluginInstalled(string asName) native global",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/Debug.psc",
            "\n".join(
                [
                    "Scriptname Debug Native",
                    "bool Function OpenUserLog(string asLogName) native global",
                    "bool Function TraceUser(string asUserLog, string asTextToPrint, int aiSeverity = 0) native global",
                    "Function Notification(string asNotificationText) native global",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/Utility.psc",
            "\n".join(
                [
                    "Scriptname Utility Native",
                    "float Function GetCurrentRealTime() native global",
                ]
            )
            + "\n",
        )


def make_fake_compiler(work_dir):
    py_script = Path(work_dir) / "fake_papyrus_compiler.py"
    py_script.write_text(
        "import os, pathlib, sys\n"
        "psc = sys.argv[1]\n"
        "out = [a[3:] for a in sys.argv[2:] if a.startswith('-o=')][0]\n"
        "os.makedirs(out, exist_ok=True)\n"
        "stem = os.path.splitext(os.path.basename(psc))[0]\n"
        "pathlib.Path(out, stem + '.pex').write_bytes(b'FAKAPEX-WORKSHOPCORE')\n"
        "print('Compilation succeeded.')\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        cmd = Path(work_dir) / "fake_compiler.cmd"
        cmd.write_text(f'@"{sys.executable}" "{py_script}" %*\r\n', encoding="utf-8")
        return str(cmd)
    sh = Path(work_dir) / "fake_compiler.sh"
    sh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{py_script}" "$@"\n', encoding="utf-8")
    sh.chmod(0o755)
    return str(sh)


class ScriptAndContractTests(unittest.TestCase):
    def test_form_ids_match_across_csharp_papyrus_and_docs(self):
        ids = cs_const_uints(CS_TEXT)
        expected = {
            "QuestId": 0x800,
            "CampExclusionRadiusGlobId": 0x801,
            "ActiveCampCountGlobId": 0x802,
            "TrackedWorkshopCountGlobId": 0x803,
            "TrackedStationCountGlobId": 0x804,
            "CampKitId": 0x810,
            "CampPackTokenId": 0x811,
            "SettlementKitId": 0x812,
            "CmpoIresListId": 0x818,
            "CmpoMiscListId": 0x819,
            "ScrapJunkListId": 0x81A,
            "ScrapTokenId": 0x81B,
            "BenchRecipesListId": 0x81C,
            "KitFilterListId": 0x81D,
            "JunkDeskFanId": 0x820,
            "JunkDuctTapeId": 0x821,
            "JunkHotPlateId": 0x822,
            "JunkTinCanId": 0x823,
            "CraftFieldMedkitId": 0x830,
            "CraftWeaponPartsKitId": 0x831,
            "CraftSensorModuleId": 0x832,
            "CraftSurgicalBagId": 0x833,
            "CraftCombatBlendId": 0x834,
            "CraftTrailRationId": 0x835,
            "CobjFo4FieldMedkitId": 0x840,
            "CobjFo4WeaponPartsKitId": 0x841,
            "CobjFo4SensorModuleId": 0x842,
            "CobjFo4PortableCampKitId": 0x843,
            "RcpeNvSurgicalBagId": 0x844,
            "RcpeNvCombatBlendId": 0x845,
            "RcpeNvHandLoad777Id": 0x846,
            "RcpeNvTrailRationId": 0x847,
        }
        for k, v in expected.items():
            self.assertEqual(ids.get(k), v, k)

        psc_map = {
            "CampExclGlobId": 0x801,
            "ActiveCampGlobId": 0x802,
            "TrackedWsGlobId": 0x803,
            "TrackedStGlobId": 0x804,
            "CampKitId": 0x810,
            "CampPackTokenId": 0x811,
            "SettlementKitId": 0x812,
            "CmpoIresListId": 0x818,
            "CmpoMiscListId": 0x819,
            "ScrapJunkListId": 0x81A,
            "ScrapTokenId": 0x81B,
            "BenchRecipesListId": 0x81C,
            "KitFilterListId": 0x81D,
            "JunkDeskFanId": 0x820,
            "JunkDuctTapeId": 0x821,
            "JunkHotPlateId": 0x822,
            "JunkTinCanId": 0x823,
            "CoreBenchBaseId": 0x0A2ECD,
            "BeaconBaseId": 0x2C60E9,
            "WorkshopKwId": 0x054BA7,
            "StationFurnKwId": 0x01A21C,
        }
        for psc_name, want in psc_map.items():
            m = re.search(rf"^int\s+{psc_name}\s*=\s*(0x[0-9A-Fa-f]+)", PSC_TEXT, re.M)
            self.assertIsNotNone(m, f"missing {psc_name} in PSC")
            self.assertEqual(int(m.group(1), 16), want, psc_name)

        for hex_str in ("0x000800", "0x000810", "0x000818", "0x000820", "0x000840", "0x000847"):
            self.assertIn(hex_str, DOC_TEXT)

    def test_core_values_test_mode_property_and_masters_contract(self):
        props = re.findall(r"^\s*(\w+)\s+Property\s+(\w+)\s+Auto\s+Const\b", PSC_TEXT, re.M)
        self.assertEqual(props, [("GlobalVariable", "TestModeGlobal")])
        all_props = re.findall(r"\bProperty\s+(\w+)\b", PSC_TEXT)
        self.assertEqual(all_props, ["TestModeGlobal"])
        self.assertIn("if TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0", PSC_TEXT)
        self.assertIn("1 property (TestModeGlobal)", CS_TEXT)
        self.assertIn("expected [Starfield.esm, FO4SFCoreValues.esm]", CS_TEXT)
        self.assertIn('string WorkshopPlugin = "FO4SFWorkshop.esm"', PSC_TEXT)
        self.assertEqual(CORE_VALUES_PLUGIN, "FO4SFCoreValues.esm")
        self.assertEqual(mwc.TEST_MODE_GLOBAL_ID, core_form_id("FO4SF_TestModeEnabled"))
        self.assertEqual(mwc.TEST_MODE_GLOBAL_ID, 0x860)

    def test_no_papyrus_variable_or_param_shadows_a_base_type(self):
        decls = re.findall(r"^\s*(?:[A-Za-z0-9_]+(?:\[\])?)\s+([A-Za-z0-9_]+)\s*(?:=|$)", PSC_TEXT, re.M)
        params = [
            p
            for sig in re.findall(r"(?:Function|Event)\s+[A-Za-z0-9_.]+\(([^)]*)\)", PSC_TEXT)
            for p in re.findall(r"\s([A-Za-z0-9_]+)\s*(?:,|=|$)", " " + sig)
        ]
        bad = [name for name in decls + params if name.lower() in PAPYRUS_RESERVED_TYPES]
        self.assertEqual(bad, [])

    def test_stages_and_events_align_between_script_writer_and_log_parser(self):
        ran = {int(s) for s in re.findall(r"StageList\[\d+\]\s*=\s*(\d+)", PSC_TEXT)} | {
            int(s) for s in re.findall(r"GetStageDone\((\d+)\)", PSC_TEXT)
        }
        m = re.search(r"Stages\s*=\s*\{\s*([\d,\s]+)\s*\}", CS_TEXT)
        self.assertIsNotNone(m)
        cs_stages = [int(x.strip()) for x in m.group(1).split(",")]
        self.assertEqual(sorted(ran), cs_stages)
        self.assertEqual(cs_stages, [5, 10, 15, 20, 30, 40, 50, 60])

        for ev in core_log.EVENTS:
            self.assertRegex(PSC_TEXT, rf'Trace\("{ev}[ "]')

    def test_all_18_cmpo_archetypes_and_8_recipes_match(self):
        self.assertEqual(len(core_log.CMPO_TABLE), 18)
        for idx, arch, ires_edid, misc_edid in core_log.CMPO_TABLE:
            self.assertIn(f'"{arch}"', CS_TEXT)
            self.assertIn(f'"{ires_edid}"', CS_TEXT)
            self.assertIn(f'"{misc_edid}"', CS_TEXT)
            self.assertIn(ires_edid, DOC_TEXT)
            self.assertIn(misc_edid, DOC_TEXT)

        for edid in (
            "FO4SF_COBJ_FO4_FieldMedkit",
            "FO4SF_COBJ_FO4_WeaponPartsKit",
            "FO4SF_COBJ_FO4_SensorModule",
            "FO4SF_COBJ_FO4_PortableCAMPKit",
            "FO4SF_RCPE_NV_SurgicalBag",
            "FO4SF_RCPE_NV_CombatBlend",
            "FO4SF_RCPE_NV_HandLoad777",
            "FO4SF_RCPE_NV_TrailRation",
        ):
            self.assertIn(edid, CS_TEXT)
            self.assertIn(edid, DOC_TEXT)

    def test_pc_card_names_throwaway_save_and_deletion_step(self):
        self.assertIn("FO4SF_Throwaway_WorkshopCAMP_DeleteMe", DOC_TEXT)
        self.assertIn("Delete the throwaway save `FO4SF_Throwaway_WorkshopCAMP_DeleteMe`", DOC_TEXT)
        for check_key in (
            "PASS settlement_bench",
            "PASS portable_camp",
            "PASS camp_exclusion",
            "PASS cmpo_scrap",
            "PASS bench_recipes",
            "PASS save_reload_persistence",
            "PASS camp_packup",
            "VERDICT: PASS",
        ):
            self.assertIn(check_key, DOC_TEXT)

    def test_zero_drive_paths_in_workshop_core_files(self):
        drive_rx = re.compile(r"\b[A-Za-z]:[\\/]")
        checked = [
            ROOT / "dotnet" / "WorkshopCore" / "WorkshopCore.csproj",
            CS_PATH,
            PSC_PATH,
            ROOT / "scripts" / "workshop" / "make_workshop_core.py",
            ROOT / "scripts" / "workshop" / "workshop_core_install.py",
            ROOT / "src" / "fo4sf" / "workshop" / "core_log.py",
            DOC_PATH,
            Path(__file__),
        ]
        for path in checked:
            txt = path.read_text(encoding="utf-8")
            self.assertIsNone(drive_rx.search(txt), f"drive path found in {path.name}")


class CoreLogTests(unittest.TestCase):
    def test_expected_scrap_yields_for_stage20_batch(self):
        batch = {
            "FO4SF_Junk_DeskFan": 4,
            "FO4SF_Junk_DuctTape": 4,
            "FO4SF_Junk_HotPlate": 4,
            "FO4SF_Junk_TinCan": 4,
        }
        yields = core_log.expected_scrap_yields(batch)
        self.assertEqual(
            yields,
            {
                0: 16,   # Steel -> Iron
                2: 8,    # Aluminum
                3: 8,    # Adhesive
                4: 12,   # Screws -> Tungsten
                5: 8,    # Copper
                6: 4,    # Circuitry -> ZeroWire
                9: 8,    # Gears -> AdaptiveFrame
                12: 4,   # Cloth -> Fiber
            },
        )
        self.assertEqual(sum(yields.values()), 68)

    def test_rotated_log_stitching_across_save_quit_reload_passes_all_7_checks(self):
        pre_reload = [
            "[17:20:01] FO4SFWSCORE rt=10.0 init version=1 quest=167774208 installed=true core=FO4TerrainCore.esm benchbase=67399713 beaconbase=2908393 workshopkw=347047 stationkw=107036 cmpo_ires=18 cmpo_misc=18 recipes=8 end=true\n",
            "[17:20:05] FO4SFWSCORE rt=14.0 camp_deployed stage=15 mode=console ref=-2140000001 base=2908393 moved=true loaded=true haskw=false cell=100 dist=2.5 active_camps=1 end=true\n",
            "[17:20:05] FO4SFWSCORE rt=14.1 camp_blocked stage=15 mode=console reason=exclusion_zone nearest_dist=0.0 min_dist=45.0 refunded=true end=true\n",
            "[17:20:08] FO4SFWSCORE rt=17.0 bench_placed stage=10 mode=console ref=-2140000002 base=67399713 moved=true loaded=true haskw=true cell=100 dist=4.3 count=1 end=true\n",
            "[17:20:11] FO4SFWSCORE rt=20.0 scrap_run stage=20 mode=console junk_removed=16 components_added=68 steel_iron=16 aluminum=8 adhesive=8 copper=8 screws_tungsten=12 gears_frame=8 circuitry_wire=4 cloth_fiber=4 pass=true end=true\n",
            "[17:20:13] FO4SFWSCORE rt=22.0 recipe_audit stage=30 cmpo_pairs=18 recipes_total=8 fo4_cobj=4 fnv_rcpe=4 valid_forms=8 can_craft_medkit=false can_craft_parts=true can_craft_camp=true pass=true end=true\n",
            "[17:20:25] FO4SFWSCORE rt=34.0 station_placed ref=-2140000003 base=2052269 workshop=-2140000001 loaded=true count=1 end=true\n",
            "[17:20:26] FO4SFWSCORE rt=35.0 read when=truncated kind=bench idx=0\n",
        ]
        post_reload = [
            "[17:22:02] FO4SFWSCORE rt=5.0 reload_audit when=reload reload_count=1 benches_ok=1/1 beacons_ok=1/1 stations_ok=1/1 pass=true end=true\n",
            "[17:22:04] FO4SFWSCORE rt=7.0 reload_audit when=reload+2s reload_count=1 benches_ok=1/1 beacons_ok=1/1 stations_ok=1/1 pass=true end=true\n",
            "[17:22:10] FO4SFWSCORE rt=13.0 reload_audit when=stage50 reload_count=1 benches_ok=1/1 beacons_ok=1/1 stations_ok=1/1 pass=true end=true\n",
            "[17:22:14] FO4SFWSCORE rt=17.0 camp_packed stage=40 mode=console ref=-2140000001 refunded_kit=true active_camps=0 end=true\n",
            "[17:22:18] FO4SFWSCORE rt=21.0 cleanup benches_removed=1 beacons_removed=0 stations_cleared=1 end=true\n",
        ]
        with tempfile.TemporaryDirectory(prefix="wscore-log-") as tmp:
            log0 = Path(tmp) / "FO4SFWorkshopCore.0.log"
            log1 = Path(tmp) / "FO4SFWorkshopCore.1.log"
            log1.write_text("".join(pre_reload), encoding="utf-8")
            log0.write_text("".join(post_reload), encoding="utf-8")

            stitched = core_log.load_session_lines(str(log0), include_rotated=True)
            s = core_log.summarize(stitched)
            self.assertTrue(s["passed"])
            self.assertEqual(s["cut"], 1)
            for k, ok in s["checks"].items():
                self.assertTrue(ok, k)
            rep = "\n".join(core_log.report(s))
            self.assertIn("PASS save_reload_persistence", rep)
            self.assertIn("VERDICT: PASS", rep)

            # Without rotated log stitching, pre-reload checks are absent -> FAIL
            only_post = core_log.load_session_lines(str(log0), include_rotated=False)
            s_post = core_log.summarize(only_post)
            self.assertFalse(s_post["passed"])
            self.assertTrue(s_post["checks"]["save_reload_persistence"])
            self.assertFalse(s_post["checks"]["cmpo_scrap"])

            # Console helper emits throwaway save command from quest FormID in .1.log
            rc = mwc.main(["console", "--file", str(log0)])
            self.assertEqual(rc, 0)


class StageFoldAndInstallTests(unittest.TestCase):
    def test_precheck_detects_missing_required_native(self):
        with tempfile.TemporaryDirectory(prefix="wscore-pre-") as tmp:
            cr = Path(tmp) / "ContentResources.zip"
            make_fake_content_resources(cr)
            sources = mwc.read_sources(str(cr))
            res = mwc.precheck_sources(sources)
            self.assertEqual(res["missing"], [])

            sources["actor"] = "Scriptname Actor extends ObjectReference Native\n"
            bad = mwc.precheck_sources(sources)
            self.assertIn("Actor.OnPlayerLoadGame", bad["missing"])

    @unittest.skipUnless(DOTNET_ENABLED, "requires FO4SF_DOTNET_TESTS=1 and dotnet")
    def test_dotnet_selftest_binary_header_stage_hardlink_fold_and_ridealong_install(self):
        with tempfile.TemporaryDirectory(prefix="wscore-e2e-") as tmp:
            tmp_path = Path(tmp)

            # 1. WorkshopCore selftest (full + minimal fixtures + options + 7 tamper negative controls)
            selftest_dir = tmp_path / "selftest"
            r = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(ROOT / "dotnet" / "WorkshopCore"), "--", "selftest", str(selftest_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("selftest: ok", r.stdout)

            # 2. Raw binary verification of FO4SFWorkshop.esm
            plugin_bytes = (selftest_dir / "b_full" / "FO4SFWorkshop.esm").read_bytes()
            flags, masters = parse_tes4_header(plugin_bytes)
            self.assertTrue(flags & 0x01, "TES4 Master flag 0x01 not set")
            self.assertEqual(masters, ["Starfield.esm", "FO4SFCoreValues.esm"])
            for grup_sig in (b"QUST", b"GLOB", b"MISC", b"ALCH", b"COBJ", b"FLST"):
                self.assertIn(b"GRUP" + plugin_bytes[plugin_bytes.index(b"GRUP") + 4 : plugin_bytes.index(b"GRUP") + 4], plugin_bytes)
                self.assertIn(grup_sig, plugin_bytes)

            # 3. Stage with fake ContentResources.zip + fake Papyrus compiler
            sf_esm = selftest_dir / "m_full" / "Starfield.esm"
            cr_zip = tmp_path / "ContentResources.zip"
            make_fake_content_resources(cr_zip)
            fake_comp = make_fake_compiler(tmp_path)
            stage_dir = tmp_path / "stage_out"

            rc = mwc.main(
                [
                    "stage",
                    "--out",
                    str(stage_dir),
                    "--starfield",
                    str(sf_esm),
                    "--compiler",
                    fake_comp,
                    "--content-resources",
                    str(cr_zip),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertTrue((stage_dir / "FO4SFWorkshop.esm").is_file())
            self.assertTrue((stage_dir / "Data" / "Scripts" / "FO4SF_WorkshopCoreQuest.pex").is_file())

            # 4. Hardlink fold into synthetic clean_core without mutating source README.txt
            core_dir = tmp_path / "clean_core"
            (core_dir / "Data" / "Scripts").mkdir(parents=True)
            (core_dir / "FO4TerrainCore.esm").write_bytes(b"CORE-ESM")
            (core_dir / "FO4SFNewGame.esm").write_bytes(b"NEWGAME-ESM")
            core_readme = (
                "Clean core set.\n"
                "  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> "
                "--plugins FO4SFNewGame.esm,FO4TerrainCore.esm --pack\n"
            )
            (core_dir / "README.txt").write_text(core_readme, encoding="utf-8")
            before_sha = hashlib.sha256((core_dir / "README.txt").read_bytes()).hexdigest()

            folded_dir = tmp_path / "folded_core"
            rc_fold = mwc.main(
                [
                    "fold",
                    "--stage",
                    str(stage_dir),
                    "--core-dir",
                    str(core_dir),
                    "--out",
                    str(folded_dir),
                    "--starfield",
                    str(sf_esm),
                    "--hardlink",
                ]
            )
            self.assertEqual(rc_fold, 0)
            after_sha = hashlib.sha256((core_dir / "README.txt").read_bytes()).hexdigest()
            self.assertEqual(before_sha, after_sha, "source clean_core README.txt was mutated during --hardlink fold")
            folded_readme_txt = (folded_dir / "README.txt").read_text(encoding="utf-8")
            self.assertIn("FO4SFNewGame.esm,FO4TerrainCore.esm,FO4SFWorkshop.esm", folded_readme_txt)

            rc_ver = mwc.main(
                [
                    "verify",
                    "--exp-dir",
                    str(folded_dir),
                    "--plan",
                    str(stage_dir / "plan.json"),
                    "--starfield",
                    str(sf_esm),
                ]
            )
            self.assertEqual(rc_ver, 0)

            # 5. Ride-along installer preserves Data/FO4SFExp.install.json in isolated temp LOCALAPPDATA
            game_dir = tmp_path / "fake_game"
            (game_dir / "Data").mkdir(parents=True)
            (game_dir / "Starfield.exe").write_bytes(b"MZ")
            shutil.copy2(sf_esm, game_dir / "Data" / "Starfield.esm")
            (game_dir / "Data" / "FO4SFCoreValues.esm").write_bytes(struct.pack("<4sIIIII", b"TES4", 0, 0x01, 0, 0, 0))
            (game_dir / "Data" / "FO4TerrainCore.esm").write_bytes(struct.pack("<4sIIIII", b"TES4", 0, 0x01, 0, 0, 0))
            existing_exp = game_dir / "Data" / "FO4SFExp.install.json"
            existing_exp.write_text('{"keep": true}\n', encoding="utf-8")
            local_dir = tmp_path / "localappdata"
            (local_dir / "Starfield").mkdir(parents=True)
            plugins_txt = local_dir / "Starfield" / "Plugins.txt"
            plugins_txt.write_text(
                "# This file is used by Starfield\r\n*FO4SFCoreValues.esm\r\n*FO4TerrainCore.esm\r\n",
                encoding="utf-8",
            )

            old_local = os.environ.get("LOCALAPPDATA")
            old_build = exp_install.build_ba2

            def stub_build(args_ns, root_dir, out_ba2):
                Path(out_ba2).write_bytes(archive_from_tree(Path(root_dir)))
                return out_ba2

            def run_wci(*argv):
                try:
                    return wci.main(list(argv)) or 0
                except SystemExit as exc:
                    return exc.code if isinstance(exc.code, int) else 1

            os.environ["LOCALAPPDATA"] = str(local_dir)
            exp_install.build_ba2 = stub_build
            try:
                self.assertEqual(run_wci("install", "--dir", str(stage_dir), "--starfield", str(game_dir)), 0)
                self.assertTrue((game_dir / "Data" / "FO4SFWorkshop.install.json").is_file())
                self.assertTrue((game_dir / "Data" / "FO4SFWorkshop.esm").is_file())
                self.assertTrue((game_dir / "Data" / "FO4SFWorkshop - Main.ba2").is_file())
                self.assertEqual(existing_exp.read_text(encoding="utf-8"), '{"keep": true}\n')
                self.assertIn("*FO4SFWorkshop.esm", plugins_txt.read_text(encoding="utf-8"))
                self.assertEqual(run_wci("active", "--starfield", str(game_dir)), 0)
                self.assertEqual(run_wci("uninstall", "--starfield", str(game_dir)), 0)
                self.assertFalse((game_dir / "Data" / "FO4SFWorkshop.esm").exists())
                self.assertEqual(existing_exp.read_text(encoding="utf-8"), '{"keep": true}\n')
            finally:
                exp_install.build_ba2 = old_build
                if old_local is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = old_local

    def test_e6_make_workshop_core_stages_verifies_and_folds_strings_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sf_esm = root / "Starfield.esm"
            core_esm = root / "FO4TerrainCore.esm"
            sf_esm.write_bytes(b"SF")
            core_esm.write_bytes(b"CORE")
            src = root / "Scripts" / "Source"
            src.mkdir(parents=True)
            (src / "Starfield_Papyrus_Flags.flg").write_text("", encoding="utf-8")

            stage_dir = root / "stage"
            stage_dir.mkdir()
            (stage_dir / "FO4SFWorkshop.esm").write_bytes(b"MOD")
            (stage_dir / "Data" / "Scripts").mkdir(parents=True)
            (stage_dir / "Data" / "Scripts" / "FO4SF_WorkshopCoreQuest.pex").write_bytes(b"PEX")
            strings_dir = stage_dir / "Data" / "Strings"
            strings_dir.mkdir(parents=True)
            (stage_dir / "README.txt").write_text("stage\n", encoding="utf-8")
            rel_strings = []
            for ext in ("STRINGS", "DLSTRINGS", "ILSTRINGS"):
                fn = f"FO4SFWorkshop_en.{ext}"
                (strings_dir / fn).write_bytes(b"STR\x00")
                rel_strings.append(f"Data/Strings/{fn}")

            plan = {
                "kind": "workshop-core",
                "version": 1,
                "plugin": "FO4SFWorkshop.esm",
                "plugin_sha256": mwc.sha256(stage_dir / "FO4SFWorkshop.esm"),
                "plugins": ["FO4SFWorkshop.esm"],
                "script": "FO4SF_WorkshopCoreQuest",
                "scripts": {
                    "FO4SF_WorkshopCoreQuest": mwc.sha256(
                        stage_dir / "Data" / "Scripts" / "FO4SF_WorkshopCoreQuest.pex"
                    ),
                },
                "inputs": {"Starfield.esm": {"sha256": mwc.sha256(sf_esm)}},
                "outputs": {
                    "FO4SFWorkshop.esm": mwc.sha256(stage_dir / "FO4SFWorkshop.esm"),
                    "Data/Scripts/FO4SF_WorkshopCoreQuest.pex": mwc.sha256(
                        stage_dir / "Data" / "Scripts" / "FO4SF_WorkshopCoreQuest.pex"
                    ),
                    **{rel: mwc.sha256(stage_dir / rel) for rel in rel_strings},
                },
            }
            (stage_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
            problems = mwc.verify_dir(str(stage_dir), plan)
            self.assertEqual(problems, [])

            core_dir = root / "clean_core"
            core_dir.mkdir()
            (core_dir / "FO4TerrainCore.esm").write_bytes(b"CORE")
            (core_dir / "README.txt").write_text("core\n", encoding="utf-8")
            (core_dir / "Data" / "Scripts").mkdir(parents=True)
            folded_dir = root / "folded"
            rc = mwc.main(["fold", "--stage", str(stage_dir), "--core-dir", str(core_dir), "--out", str(folded_dir)]) or 0
            self.assertEqual(rc, 0)
            for rel in rel_strings:
                self.assertTrue((folded_dir / rel).is_file(), rel)


if __name__ == "__main__":
    unittest.main()
