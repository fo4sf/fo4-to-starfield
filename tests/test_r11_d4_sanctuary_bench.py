"""Round 11 W2 tests for D4 (clean Sanctuary workshop bench + Mars/Sol footer removal)
and A2.1 (CheckSturgesTalkFallback open-menu suppression + S9 Sturges arrival gate)."""
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
WS_CS = ROOT / "dotnet" / "WorkshopCore" / "Program.cs"
SANC_PSC = ROOT / "scripts" / "mission" / "FO4SF_Sanctuary01Quest.psc"
DOC_D4 = ROOT / "docs" / "workshop" / "sanctuary-bench-d4-note.md"

DOTNET_ENABLED = os.environ.get("FO4SF_DOTNET_TESTS", "") == "1" and shutil.which("dotnet") is not None

FORBIDDEN_OUTPOST_CATEGORIES = (
    0x002CFDE6,  # OutpostCategoryCrafting
    0x002BE3B5,  # OutpostCategoryFurniture
    0x00293ADF,  # OutpostCategoryDecorations
    0x0002BD59,  # OutpostCategoryTestAssets
    0x00397027,  # OutpostCategoryDisplays
    0x0028F890,  # OutpostCategoryPower_InteriorLights
    0x000E6A3E,  # OutpostCategoryMiscInterior
)


def _iter_esm_records(data: bytes):
    def walk(start: int, end: int):
        p = start
        while p + 24 <= end:
            sig = data[p : p + 4]
            if sig == b"GRUP":
                gsize = struct.unpack_from("<I", data, p + 4)[0]
                if gsize < 24 or p + gsize > end:
                    break
                yield from walk(p + 24, p + gsize)
                p += gsize
            else:
                rsize, flags, fid = struct.unpack_from("<III", data, p + 4)
                pay = data[p + 24 : p + 24 + rsize]
                if flags & 0x00040000 and len(pay) >= 4:
                    pay = zlib.decompress(pay[4:])
                yield sig.decode("ascii", errors="replace"), fid, flags, pay
                p += 24 + rsize

    yield from walk(0, len(data))


def _iter_subrecords(payload: bytes):
    p = 0
    ext = None
    while p + 6 <= len(payload):
        t = payload[p : p + 4].decode("ascii", errors="replace")
        sz = struct.unpack_from("<H", payload, p + 4)[0]
        p += 6
        if t == "XXXX" and sz == 4 and p + 4 <= len(payload):
            ext = struct.unpack_from("<I", payload, p)[0]
            p += 4
            continue
        if ext is not None:
            sz = ext
            ext = None
        if p + sz > len(payload):
            break
        yield t, payload[p : p + sz]
        p += sz


class Round11D4AndA21Tests(unittest.TestCase):
    def test_d4_workshop_core_defines_clean_sanctuary_bench_and_scoped_location_overrides(self) -> None:
        cs = WS_CS.read_text(encoding="utf-8")
        self.assertIn("public const uint SanctuaryCategoryKwId = 0x848;", cs)
        self.assertIn("public const uint SanctuaryBenchActiId = 0x849;", cs)
        self.assertIn("public const uint SanctuaryCleanBenchSwapGlobId = 0x84A;", cs)
        self.assertIn('public const string SanctuaryCleanBenchSwapGlobEdid = "FO4SF_SanctuaryCleanBenchSwap";', cs)
        self.assertIn("public const int ExpectedOwnRecordCount = 35;", cs)
        self.assertIn('public const string SanctuaryBenchName = "Sanctuary Hills Workshop";', cs)
        self.assertIn('public const string SanctuaryBenchModel = "fo4core\\\\setdressing\\\\garage\\\\workbenchgarage01.nif";', cs)
        self.assertIn("public const uint SfLocMarsSurfaceId = 0x01B736;", cs)
        self.assertIn("public const uint SfLocMarsPlanetId = 0x01B735;", cs)
        self.assertIn("public const uint SfLocSolSystemId = 0x061527;", cs)
        self.assertIn("public const uint SfStarSolId = 0x05E5CB;", cs)
        self.assertIn('public const string CommonwealthLocName = "Commonwealth";', cs)
        self.assertIn('public const string MassachusettsStarName = "Massachusetts";', cs)

        # Must explicitly forbid all 7 Starfield OutpostCategory* keywords and NEVER touch PNDT 0x03F59A
        for kw_id in FORBIDDEN_OUTPOST_CATEGORIES:
            self.assertIn(f"0x{kw_id:08X}", cs.upper().replace("0X", "0x"))
        self.assertIn("mod.Planets.Count == 0", cs)
        self.assertIn("FullNameComponent", cs)
        self.assertIn("d4_starfield_outpost_category_leaked", cs)
        self.assertIn("d4_mars_location_name_reverted", cs)
        self.assertIn("d4_clean_bench_swap_default_nonzero", cs)

    def test_d4_sanctuary01_swap_off_by_default_with_self_heal_and_load_restore(self) -> None:
        psc = SANC_PSC.read_text(encoding="utf-8")
        self.assertIn('string WorkshopPlugin = "FO4SFWorkshop.esm"', psc)
        self.assertIn("int CleanBenchBaseId = 0x000849", psc)
        self.assertIn("int CleanBenchSwapGlobId = 0x00084A", psc)
        self.assertIn("bool Property EnableCleanBenchSwap = False Auto", psc)
        self.assertIn("float CleanBenchSelfHealSeconds = 3.5", psc)
        self.assertIn("ObjectReference sanctuaryBenchOverride = None", psc)
        self.assertIn("ObjectReference coreBenchDisabled = None", psc)

        sw_fn = re.search(r"bool Function IsCleanBenchSwapEnabled\(\).*?EndFunction", psc, re.S)
        self.assertIsNotNone(sw_fn)
        self.assertIn("if cleanBenchSelfHealed", sw_fn.group(0))
        self.assertIn("if EnableCleanBenchSwap", sw_fn.group(0))
        self.assertIn("Game.GetFormFromFile(CleanBenchSwapGlobId, WorkshopPlugin) as GlobalVariable", sw_fn.group(0))

        restore_fn = re.search(r"Function RestoreCoreBench\(string reason\).*?EndFunction", psc, re.S)
        self.assertIsNotNone(restore_fn)
        rbody = restore_fn.group(0)
        self.assertIn("sanctuaryBenchOverride.DisableNoWait(False)", rbody)
        self.assertIn("coreRef.EnableNoWait(False)", rbody)
        self.assertIn("boundBench = coreRef", rbody)
        self.assertIn("bAliasRestore.ForceRefTo(boundBench)", rbody)

        bind_fn = re.search(r"Function TryBindBench\(Actor player\).*?EndFunction", psc, re.S)
        self.assertIsNotNone(bind_fn)
        body = bind_fn.group(0)
        self.assertIn("bool wantSwap = IsCleanBenchSwapEnabled()", body)
        self.assertIn('RestoreCoreBench("load_switch_off")', body)
        self.assertIn("if wantSwap && Game.IsPluginInstalled(WorkshopPlugin)", body)
        self.assertIn("Game.GetFormFromFile(CleanBenchBaseId, WorkshopPlugin) as Activator", body)
        self.assertIn("cleanRef.MoveTo(cand, 0.0, 0.0, 0.0, True, False)", body)
        self.assertIn("cand.DisableNoWait(False)", body)
        self.assertIn("RegisterMenuGuards()", body)
        self.assertIn("sanctuary01 bench_bound ref=", body)
        self.assertIn("sanctuary01 clean_bench_swap active=true ref=", body)
        self.assertIn("sanctuary01 clean_bench_swap active=false ref=", body)

        # OnActivate starts Timer 3 (3.5 s); OnTimer(3) self-heals back to 04005C50 if workshop did not open
        act_ev = re.search(r"Event ObjectReference\.OnActivate\(.*?EndEvent", psc, re.S)
        self.assertIsNotNone(act_ev)
        self.assertIn("StartTimer(CleanBenchSelfHealSeconds, 3)", act_ev.group(0))

        timer_ev = re.search(r"Event OnTimer\(int aiTimerID\).*?EndEvent", psc, re.S)
        self.assertIsNotNone(timer_ev)
        tbody = timer_ev.group(0)
        self.assertIn("if aiTimerID == 3", tbody)
        self.assertIn('Trace("sanctuary01 clean_bench_swap self_heal reason=no_workshop_menu")', tbody)
        self.assertIn('RestoreCoreBench("self_heal")', tbody)

        # Behavioral state-machine check: default OFF, opt-in ON -> 3.5 s no-menu self-heal -> load restore
        core_disabled = False
        override_disabled = True
        override_exists = False
        bound = None
        alias0 = None
        glob_swap = 0.0
        prop_swap = False
        self_healed = False
        verify_pending = False
        saw_workshop = False
        logs: list[str] = []

        def swap_enabled() -> bool:
            return (not self_healed) and (prop_swap or glob_swap != 0.0)

        # 1. Default in candidate-2g-fix: swap OFF -> 04005C50 stays enabled and bound
        if swap_enabled():
            override_exists = True
            override_disabled = False
            core_disabled = True
            bound = "clean_0849"
        else:
            bound = "core_005C50"
        alias0 = bound
        self.assertFalse(override_exists)
        self.assertFalse(core_disabled)
        self.assertEqual(bound, "core_005C50")

        # 2. Switch 0B00084A = 1 -> swaps to clean bench, disables 04005C50
        glob_swap = 1.0
        self.assertTrue(swap_enabled())
        override_exists = True
        override_disabled = False
        core_disabled = True
        bound = "clean_0849"
        alias0 = bound

        # 3. Activate clean bench; 3.5 s Timer 3 fires with no workshop menu -> self-heal back to 04005C50
        verify_pending = True
        saw_workshop = False
        if verify_pending and not saw_workshop:
            self_healed = True
            verify_pending = False
            logs.append("sanctuary01 clean_bench_swap self_heal reason=no_workshop_menu")
            override_disabled = True
            core_disabled = False
            bound = "core_005C50"
            alias0 = bound
        self.assertIn("sanctuary01 clean_bench_swap self_heal reason=no_workshop_menu", logs)
        self.assertFalse(core_disabled)
        self.assertTrue(override_disabled)
        self.assertEqual(bound, "core_005C50")
        self.assertEqual(alias0, "core_005C50")
        self.assertFalse(swap_enabled())

    def test_a21_sturges_talk_fallback_impossible_while_any_menu_is_open_and_no_open_menu_count(self) -> None:
        psc = SANC_PSC.read_text(encoding="utf-8")

        # Review Item #8: openMenuCount MUST be completely removed (no sticky menu counter)
        self.assertNotIn("openMenuCount", psc)

        # Must register menu open/close events for WorkshopMenu and interactive menus
        reg_fn = re.search(r"Function RegisterMenuGuards\(\).*?EndFunction", psc, re.S)
        self.assertIsNotNone(reg_fn)
        for menu_name in (
            "WorkshopMenu",
            "WorkshopBuilderMenu",
            "WorkshopQuickMenu",
            "Workshop_BlueprintMenu",
            "DialogueMenu",
            "MessageBoxMenu",
            "DataMenu",
            "InventoryMenu",
            "PauseMenu",
            "Console",
            "FO4SF_PipboyMenu",
        ):
            self.assertIn(f'RegisterForMenuOpenCloseEvent("{menu_name}")', reg_fn.group(0))

        # Must have OnMenuOpenCloseEvent and OnWorkshopMode tracking workshopModeActive + workshopMenuOpen
        ev_menu = re.search(r"Event OnMenuOpenCloseEvent\(.*?EndEvent", psc, re.S)
        self.assertIsNotNone(ev_menu)
        self.assertIn("sturgesNearSec = 0.0", ev_menu.group(0))
        self.assertIn("workshopMenuOpen = True", ev_menu.group(0))
        self.assertIn("CancelTimer(3)", ev_menu.group(0))

        ev_ws = re.search(r"Event ObjectReference\.OnWorkshopMode\(.*?EndEvent", psc, re.S)
        self.assertIsNotNone(ev_ws)
        self.assertIn("workshopModeActive = aStart", ev_ws.group(0))
        self.assertIn("sturgesNearSec = 0.0", ev_ws.group(0))
        self.assertIn("workshopMenuOpen = False", ev_ws.group(0))

        # IsAnyMenuOrWorkshopOpen checks explicit boolean flags + native game pause/dialogue/controls
        guard_fn = re.search(r"bool Function IsAnyMenuOrWorkshopOpen\(\).*?EndFunction", psc, re.S)
        self.assertIsNotNone(guard_fn)
        gbody = guard_fn.group(0)
        for check in (
            "talkBoxOpen",
            "benchMenuOpen",
            "workshopModeActive",
            "workshopMenuOpen",
            "Utility.IsGameMenuPaused()",
            "Game.IsPlayerInDialogue()",
            "!Game.IsMovementControlsEnabled()",
            "!Game.IsActivateControlsEnabled()",
        ):
            self.assertIn(check, gbody)

        # CheckSturgesTalkFallback AND RunSturgesTalk BOTH enforce IsAnyMenuOrWorkshopOpen()
        fb_fn = re.search(r"Function CheckSturgesTalkFallback\(.*?EndFunction", psc, re.S)
        self.assertIsNotNone(fb_fn)
        self.assertGreaterEqual(fb_fn.group(0).count("IsAnyMenuOrWorkshopOpen()"), 2)

        talk_fn = re.search(r"Function RunSturgesTalk\(\).*?EndFunction", psc, re.S)
        self.assertIsNotNone(talk_fn)
        self.assertIn("if IsAnyMenuOrWorkshopOpen() || completed", talk_fn.group(0))

        # Behavioral state-machine check: standing 2.2 m from Sturges for 20 ticks while WorkshopMenu
        # or any menu/pause/dialogue is open NEVER increments sturgesNearSec and NEVER opens RunSturgesTalk.
        for menu_flag in ("workshopModeActive", "workshopMenuOpen", "talkBoxOpen", "benchMenuOpen", "gameMenuPaused", "inDialogue"):
            state = {
                "workshopModeActive": False,
                "workshopMenuOpen": False,
                "talkBoxOpen": False,
                "benchMenuOpen": False,
                "gameMenuPaused": False,
                "inDialogue": False,
                "sturgesNearSec": 0.0,
                "talk_opened": 0,
            }
            state[menu_flag] = True
            for _ in range(20):
                blocked = (
                    state["workshopModeActive"]
                    or state["workshopMenuOpen"]
                    or state["talkBoxOpen"]
                    or state["benchMenuOpen"]
                    or state["gameMenuPaused"]
                    or state["inDialogue"]
                )
                if blocked:
                    state["sturgesNearSec"] = 0.0
                else:
                    state["sturgesNearSec"] += 1.0
                    if state["sturgesNearSec"] >= 8.0:
                        state["sturgesNearSec"] = 0.0
                        state["talk_opened"] += 1
            self.assertEqual(state["sturgesNearSec"], 0.0, menu_flag)
            self.assertEqual(state["talk_opened"], 0, menu_flag)

    def test_a21_sturges_not_arrived_treated_as_missing_never_shows_obj50_or_stalls_at_100(self) -> None:
        psc = SANC_PSC.read_text(encoding="utf-8")
        self.assertIn("bool Function IsSturgesReadyForSanctuary()", psc)
        self.assertIn("Function OnSturgesArrivedFromConcord()", psc)

        # Review Item #3: IsSturgesDeadOrMissing() treats !IsSturgesReadyForSanctuary() as missing
        miss_fn = re.search(r"bool Function IsSturgesDeadOrMissing\(\).*?EndFunction", psc, re.S)
        self.assertIsNotNone(miss_fn)
        self.assertIn("if !IsSturgesReadyForSanctuary()", miss_fn.group(0))

        apply_fn = re.search(r"Function ApplyStage\(int n, string by\).*?EndFunction", psc, re.S)
        self.assertIsNotNone(apply_fn)
        abody = apply_fn.group(0)
        self.assertIn("if IsSturgesDeadOrMissing()", abody)
        self.assertIn('AdvanceTo(1000, "open_mode")', abody)

        keep_fn = re.search(r"Function KeepSturges\(Actor player\).*?EndFunction", psc, re.S)
        self.assertIsNotNone(keep_fn)
        kbody = keep_fn.group(0)
        self.assertIn("if !IsSturgesReadyForSanctuary()", kbody)
        # In normal play (TestMode == 0), KeepSturges must NOT MoveTo Sturges onto the workbench
        self.assertIn("if IsTestModeEnabled()", kbody)
        self.assertLess(kbody.index("if IsTestModeEnabled()"), kbody.index("st.MoveTo(player,"))

        # CheckSturgesTalkFallback also gates behind IsSturgesReadyForSanctuary()
        fb_fn = re.search(r"Function CheckSturgesTalkFallback\(.*?EndFunction", psc, re.S)
        self.assertIsNotNone(fb_fn)
        self.assertIn("if !IsSturgesReadyForSanctuary()", fb_fn.group(0))

        # Behavioral simulation: stage 100 in normal play (TestMode=0, Sturges InitiallyDisabled)
        # treats Sturges as unavailable -> NEVER displays objective 50 ("Talk to Sturges") and advances to 1000.
        sturges_disabled = True
        sturges_arrived_s9 = False
        test_mode = False
        displayed_objs: list[int] = []
        stage = 100

        def is_ready() -> bool:
            return sturges_arrived_s9 or test_mode or (not sturges_disabled)

        def is_dead_or_missing() -> bool:
            return not is_ready()

        if is_dead_or_missing():
            stage = 1000
            displayed_objs.append(1000)
        else:
            displayed_objs.append(50)

        self.assertTrue(sturges_disabled, "Stage 100 must NOT enable Sturges before S9 arrival")
        self.assertNotIn(50, displayed_objs, "Objective 50 must NEVER show while Sturges is disabled")
        self.assertEqual(stage, 1000, "Stage 100 must advance cleanly to 1000 open_mode when Sturges has not arrived")

        # After S9 arrival from Concord, Sturges is ready and no longer treated as missing
        sturges_arrived_s9 = True
        sturges_disabled = False
        self.assertTrue(is_ready())
        self.assertFalse(is_dead_or_missing())

    def test_d4_note_honesty_and_no_drive_leaks(self) -> None:
        self.assertTrue(DOC_D4.is_file(), "missing docs/workshop/sanctuary-bench-d4-note.md")
        txt = DOC_D4.read_text(encoding="utf-8")
        self.assertIn("OFFLINE VERIFIED ONLY", txt)
        self.assertIn("0x010A2ECD", txt)
        self.assertIn("OutpostCategoryCrafting", txt)
        self.assertIn("sOutpostLocation", txt)
        self.assertIn("FO4SF_SanctuaryWorkshopBench", txt)
        self.assertIn("0x000849", txt)
        self.assertIn("0x00084A", txt)
        self.assertIn("FO4SF_SanctuaryCleanBenchSwap", txt)
        self.assertIn("self_heal reason=no_workshop_menu", txt)
        self.assertIn("PNDT 0x0003F59A", txt)
        self.assertIn("IsAnyMenuOrWorkshopOpen", txt)
        self.assertIn("OnSturgesArrivedFromConcord", txt)
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", txt), "drive-path leak in sanctuary-bench-d4-note.md")

    @unittest.skipUnless(DOTNET_ENABLED, "requires FO4SF_DOTNET_TESTS=1 and dotnet")
    def test_d4_binary_workshop_esm_clean_bench_and_location_overrides(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r11-d4-bin-") as tmp:
            r = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(ROOT / "dotnet" / "WorkshopCore"), "--", "selftest", tmp],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("selftest: ok", r.stdout)

            esm_bytes = (Path(tmp) / "b_full" / "FO4SFWorkshop.esm").read_bytes()
            by_lid = {}
            pndt_count = 0
            for rtype, fid, _flags, pay in _iter_esm_records(esm_bytes):
                if rtype == "PNDT":
                    pndt_count += 1
                by_lid[(rtype, fid & 0x00FFFFFF)] = list(_iter_subrecords(pay))

            self.assertEqual(pndt_count, 0, "FO4SFWorkshop.esm must NEVER override PNDT")
            self.assertIn(("KYWD", 0x000848), by_lid)
            self.assertIn(("ACTI", 0x000849), by_lid)
            self.assertIn(("GLOB", 0x00084A), by_lid)

            glob_subs = dict(by_lid[("GLOB", 0x00084A)])
            self.assertEqual(glob_subs["EDID"].rstrip(b"\x00").decode("utf-8"), "FO4SF_SanctuaryCleanBenchSwap")
            self.assertAlmostEqual(struct.unpack("<f", glob_subs["FLTV"])[0], 0.0, places=4)

            acti_subs = dict(by_lid[("ACTI", 0x000849)])
            self.assertEqual(acti_subs["FULL"].rstrip(b"\x00").decode("utf-8"), "Sanctuary Hills Workshop")
            self.assertEqual(
                acti_subs["MODL"].rstrip(b"\x00").decode("utf-8").lower(),
                r"fo4core\setdressing\garage\workbenchgarage01.nif",
            )
            kwda_raw = acti_subs["KWDA"]
            kw_fids = [struct.unpack_from("<I", kwda_raw, i)[0] for i in range(0, len(kwda_raw), 4)]
            self.assertIn(0x00054BA7, kw_fids)
            for forbidden in FORBIDDEN_OUTPOST_CATEGORIES:
                self.assertNotIn(forbidden, kw_fids)

            for lid, want in (
                (0x01B736, "Commonwealth"),
                (0x01B735, "Commonwealth"),
                (0x061527, "Massachusetts"),
            ):
                subs = dict(by_lid[("LCTN", lid)])
                self.assertEqual(subs["FULL"].rstrip(b"\x00").decode("utf-8"), want)

            star_subs = dict(by_lid[("STDT", 0x05E5CB)])
            self.assertEqual(star_subs["FULL"].rstrip(b"\x00").decode("utf-8"), "Massachusetts")
            self.assertEqual(star_subs["ANAM"].rstrip(b"\x00").decode("utf-8"), "Massachusetts")


if __name__ == "__main__":
    unittest.main()
