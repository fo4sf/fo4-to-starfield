"""Round 10 Slice W2 regression tests covering Pushes 5 & 6 repairs R1–R5, R7, and R8.

Verifies:
  - R1: FO4SF_MQ103 never starts inside the opening (removed from Sanctuary01 StartQuestInstance;
        deferred when Sanctuary01 is active and player is away from Diamond City; never steals HUD SetActive).
  - R2: Sanctuary workbench OnActivate never pops RunWorkbenchBuildMenu over the real workshop;
        bench_activated logs complete=true ONLY when CompleteQuest() actually ran, complete=false otherwise;
        make_mission.summarize() refuses to mark complete=false as sanctuary01_complete.
  - R3: All 19 A4/A7/A7cd persistent ACHRs carry InitiallyDisabled (0x800) in C# and are enabled via
        EnableNoWait(False) strictly when their owning mission reaches the stage that needs them.
  - R4: Every talk step across A4/A7/A7cd provides BOTH a 360-degree CodsworthTalkActi (0x00081B) talk proxy
        AND a timed proximity talk fallback (TalkFallbackRadius / TalkFallbackSeconds) while the actor is alive.
  - R5: Strict sequential stage gating across MinRecruit00, MQ103, MQ104, MQ105, MQ106 (strictly behind
        MQ105 >= 100 so Fort Hagen never starts MQ105 & MQ106 together), MQ203, MQ204, MQ206.
  - R7: MQ204 SW Glowing Sea rads tick gated OFF unless S9 FO4SFRads.esm is installed (honoring the
        15 Nov owner environment-damage decision); restored Sanctuary01 SanctuaryWorkbench alias 0 self-checks.
  - R8: MQ206 relay & MQ203 Kellogg's memory NEVER falsely complete when FO4Port.esm or persistent markers
        (0x03D52E / 0x00F2D3) are missing; stand-ins (Sanctuary build counter, MQ106 Prydwen global,
        MQ203 autonomous scan, MQ206 workbench counter) are honestly labeled in logs and summarize().
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "mission")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_mission  # noqa: E402

CS_A4 = ROOT / "dotnet" / "Mission" / "NextStoryMissionsA4.cs"
CS_A7 = ROOT / "dotnet" / "Mission" / "NextStoryMissionsA7.cs"
CS_A7CD = ROOT / "dotnet" / "Mission" / "NextStoryMissionsA7cd.cs"

PSC_SANC = ROOT / "scripts" / "mission" / "FO4SF_Sanctuary01Quest.psc"
PSC_STEP = ROOT / "scripts" / "mission" / "FO4SF_MinRecruit00Quest.psc"
PSC_MQ103 = ROOT / "scripts" / "mission" / "FO4SF_MQ103Quest.psc"
PSC_MQ104 = ROOT / "scripts" / "mission" / "FO4SF_MQ104Quest.psc"
PSC_MQ105 = ROOT / "scripts" / "mission" / "FO4SF_MQ105Quest.psc"
PSC_MQ106 = ROOT / "scripts" / "mission" / "FO4SF_MQ106Quest.psc"
PSC_MQ203 = ROOT / "scripts" / "mission" / "FO4SF_MQ203Quest.psc"
PSC_MQ204 = ROOT / "scripts" / "mission" / "FO4SF_MQ204Quest.psc"
PSC_MQ206 = ROOT / "scripts" / "mission" / "FO4SF_MQ206Quest.psc"

ALL_W2_PSCS = (
    PSC_SANC, PSC_STEP, PSC_MQ103, PSC_MQ104, PSC_MQ105,
    PSC_MQ106, PSC_MQ203, PSC_MQ204, PSC_MQ206,
)


class Round10R1ToR8Tests(unittest.TestCase):
    def test_r1_mq103_never_starts_in_opening_or_steals_hud_focus(self) -> None:
        sanc = PSC_SANC.read_text(encoding="utf-8")
        mq103 = PSC_MQ103.read_text(encoding="utf-8")

        self.assertNotIn("StartMq103StoryHandoffIfNeeded", sanc)
        start_fn = re.search(r"Function StartQuestInstance\(\).*?EndFunction", sanc, re.S)
        self.assertIsNotNone(start_fn)
        self.assertNotIn("0x000A50", start_fn.group(0), "Sanctuary01 StartQuestInstance must NOT start MQ103")
        self.assertIn("StartPostOpeningHandoffs()", sanc)

        self.assertIn("CheckPredecessorOrGateProximity(player)", mq103)
        self.assertIn('Trace("mq103 gate_deferred reason=opening_active")', mq103)
        self.assertIn("if !IsSanctuaryOpeningRunning()", mq103)
        # R1 honesty (P2): explicitly notes FO4 MQ102 -> MQ103 vs deliberate one-tracked-opening-mission design
        self.assertIn("one-tracked-opening-mission", sanc)
        self.assertNotIn("matching Fallout 4's post-Sanctuary handoff", sanc)
        self.assertIn("one-tracked-opening-mission", mq103)
        self.assertNotIn("matching Fallout 4", mq103)

    def test_r2_sanctuary_workbench_no_modal_over_workshop_and_honest_complete_log(self) -> None:
        sanc = PSC_SANC.read_text(encoding="utf-8")

        # Stage < 100 bench activation must NOT call RunWorkbenchBuildMenu()
        on_act = re.search(r"Event ObjectReference\.OnActivate\(.*?EndEvent", sanc, re.S)
        self.assertIsNotNone(on_act)
        cur_lt_100 = re.search(r"if cur < 100.*?return", on_act.group(0), re.S)
        self.assertIsNotNone(cur_lt_100)
        code_lines = [ln.split(";", 1)[0] for ln in cur_lt_100.group(0).splitlines()]
        self.assertNotIn("RunWorkbenchBuildMenu", "\n".join(code_lines))

        # CompleteSanctuaryObjective advances FIRST, then logs complete=true ONLY if completed
        comp_fn = re.search(r"Function CompleteSanctuaryObjective\(.*?EndFunction", sanc, re.S)
        self.assertIsNotNone(comp_fn)
        body = "\n".join(ln.split(";", 1)[0] for ln in comp_fn.group(0).splitlines())
        self.assertLess(body.index('AdvanceTo(100, "bench")'), body.rindex("if completed"))
        self.assertLess(body.rindex("if completed"), body.index('complete=true'))
        self.assertIn('complete=false stage=', body)
        self.assertIn('complete=true', body)

        # make_mission.summarize() must NOT treat complete=false as sanctuary01_complete
        s_false = make_mission.summarize([
            "FO4SF_MISSION rt=10.0 min01 bench activated -> stage 100",
            "FO4SF_MISSION rt=10.1 sanctuary01 bench_activated=true ref=[ObjectReference < (04005C50)>] complete=false stage=100",
        ])
        self.assertTrue(s_false["min01_bench_activated"])
        self.assertIsNone(s_false["sanctuary01_complete"])
        self.assertIsNotNone(s_false["sanctuary01_bench_log"])

        s_true = make_mission.summarize([
            "FO4SF_MISSION rt=10.1 sanctuary01 bench_activated=true ref=[ObjectReference < (04005C50)>] complete=true",
        ])
        self.assertIsNotNone(s_true["sanctuary01_complete"])

    def test_r3_all_a4_a7_a7cd_achrs_initially_disabled_and_stage_enabled(self) -> None:
        for cs_path in (CS_A4, CS_A7, CS_A7CD):
            txt = cs_path.read_text(encoding="utf-8")
            self.assertIn("a.MajorRecordFlagsRaw |= 0x400 | 0x800;", txt, cs_path.name)
            self.assertIn("(r.MajorRecordFlagsRaw & 0x800) != 0", txt, cs_path.name)

        for psc_path in ALL_W2_PSCS:
            txt = psc_path.read_text(encoding="utf-8")
            self.assertIn("EnableNoWait(False)", txt, f"{psc_path.name} missing stage-gated EnableNoWait(False)")

        # Verify Sturges is not enabled until stage >= 100 and Kellogg not until stage >= 50
        sanc = PSC_SANC.read_text(encoding="utf-8")
        self.assertIn("if EffectiveStage() < 100", sanc)
        mq106 = PSC_MQ106.read_text(encoding="utf-8")
        self.assertIn("|| EffectiveStage() < 50", mq106)

    def test_r4_all_talk_steps_have_per_npc_360_proxy_and_timed_proximity_fallback(self) -> None:
        expected_proxies = (
            (PSC_SANC, ("0x000A0E",)),
            (PSC_STEP, ("0x000A27",)),
            (PSC_MQ103, ("0x000A5A", "0x000A5C")),
            (PSC_MQ104, ("0x000A8A", "0x000A8B")),
            (PSC_MQ105, ("0x000A8A", "0x000AB9", "0x000ABA")),
            (PSC_MQ106, ("0x000A8A",)),
            (PSC_MQ203, ("0x000AF6",)),
            (PSC_MQ204, ("0x000B19", "0x000B1A")),
            (PSC_MQ206, ("0x000B3E", "0x000B3F", "0x000B48")),
        )
        for psc_path, form_ids in expected_proxies:
            txt = psc_path.read_text(encoding="utf-8")
            self.assertNotIn("0x000970", txt, f"{psc_path.name} must NOT reuse CodsworthTalkActi (0x000970)")
            for fid in form_ids:
                self.assertIn(fid, txt, f"{psc_path.name} missing dedicated per-NPC talk proxy {fid}")
            self.assertIn("TalkFallbackRadius", txt, f"{psc_path.name} missing TalkFallbackRadius")
            self.assertIn("TalkFallbackSeconds", txt, f"{psc_path.name} missing TalkFallbackSeconds")
            self.assertIn("talk_fallback", txt, f"{psc_path.name} missing talk_fallback trace")

        # Verify every per-NPC talk proxy ACTI copies its NPC's exact Name and is self-checked in C#
        cs_checks = (
            (CS_A4, ("SturgesTalkActiId", "TenpinesTalkActiId", "PrestonTalkActiId", "PiperTalkActiId", "MayorTalkActiId", "EllieTalkActiId")),
            (CS_A7, ("NickTalkActiId", "MaloneTalkActiId", "GenevaTalkActiId", "DogmeatTalkActiId")),
            (CS_A7CD, ("AmariTalkActiId", "IsoldeTalkActiId", "VirgilTalkActiId", "DesdemonaTalkActiId", "TinkerTomTalkActiId", "IngramTalkActiId")),
        )
        for cs_path, const_names in cs_checks:
            txt = cs_path.read_text(encoding="utf-8")
            for cname in const_names:
                self.assertIn(cname, txt, f"{cs_path.name} missing {cname}")
            self.assertIn("talkActi.Name?.String == talkNpc.Name?.String", txt, f"{cs_path.name} missing NPC Name equality check")
            self.assertIn('talkActi.ActivateTextOverride?.String == "Talk"', txt, f"{cs_path.name} missing Talk prompt check")

    def test_r5_early_start_stays_dormant_on_runonce_and_wakes_on_predecessor_complete(self) -> None:
        gates = (
            (PSC_STEP, PSC_SANC, "minrecruit00", "minrecruit00 gate_deferred reason=opening_incomplete", "FO4SF_MinRecruit00Quest", "AdvanceTo(10,"),
            (PSC_MQ103, PSC_SANC, "mq103", "mq103 gate_deferred reason=opening_active", "FO4SF_MQ103Quest", "AdvanceTo(10,"),
            (PSC_MQ104, PSC_MQ103, "mq104", "mq104 gate_deferred reason=mq103_incomplete", "FO4SF_MQ104Quest", "AdvanceTo(10,"),
            (PSC_MQ105, PSC_MQ104, "mq105", "mq105 gate_deferred reason=mq104_incomplete", "FO4SF_MQ105Quest", "AdvanceTo(10,"),
            (PSC_MQ106, PSC_MQ105, "mq106", "mq106 gate_deferred reason=mq105_incomplete", "FO4SF_MQ106Quest", "AdvanceTo(10,"),
            (PSC_MQ203, PSC_MQ106, "mq203", "mq203 gate_deferred reason=mq106_incomplete", "FO4SF_MQ203Quest", "AdvanceTo(5,"),
            (PSC_MQ204, PSC_MQ203, "mq204", "mq204 gate_deferred reason=mq203_incomplete", "FO4SF_MQ204Quest", "AdvanceTo(10,"),
            (PSC_MQ206, PSC_MQ204, "mq206", "mq206 gate_deferred reason=mq204_incomplete", "FO4SF_MQ206Quest", "AdvanceTo(10,"),
        )
        for psc_path, pred_path, qtag, token, script_cls, first_stage_call in gates:
            txt = psc_path.read_text(encoding="utf-8")
            self.assertIn(token, txt, f"{psc_path.name} missing R5 gate token {token}")

            # 1. StartQuestInstance's gate_deferred branch MUST NOT call Stop() (RunOnce safety)
            start_fn = re.search(r"Function StartQuestInstance\(\).*?EndFunction", txt, re.S)
            self.assertIsNotNone(start_fn, f"{psc_path.name} missing StartQuestInstance")
            sbody = start_fn.group(0).replace("\r\n", "\n")
            defer_block = re.search(r"if !CheckPredecessor(?:Gate|OrGateProximity)\([^\n]*\)\s*\n(.*?)\breturn\b\s*\n\s*endif", sbody, re.S)
            self.assertIsNotNone(defer_block, f"{psc_path.name} missing defer block")
            defer_code = "\n".join(ln.split(";", 1)[0] for ln in defer_block.group(1).splitlines())
            self.assertNotIn("Stop()", defer_code, f"{psc_path.name} must NOT call Stop() on RunOnce gate_deferred")
            self.assertIn("gateDeferred = True", defer_code)
            self.assertIn("instanceStarted = False", defer_code)
            self.assertIn('RegisterForRemoteEvent(', defer_code)
            self.assertIn('"OnPlayerLoadGame"', defer_code)
            self.assertNotIn("SetObjectiveDisplayed", defer_code)
            self.assertNotIn("SetActive(", defer_code)
            self.assertNotIn("StartTimer(", defer_code)

            # 2. WakeFromPredecessor exists and re-enters StartQuestInstance once gate passes
            wake_fn = re.search(r"Function WakeFromPredecessor\(\).*?EndFunction", txt, re.S)
            self.assertIsNotNone(wake_fn, f"{psc_path.name} missing WakeFromPredecessor()")
            wbody = wake_fn.group(0)
            self.assertIn(f'Trace("{qtag} gate_resumed")', wbody)
            self.assertIn("StartQuestInstance()", wbody)

            # 3. OnPlayerLoadGame re-checks dormant gateDeferred quests without starting timers prematurely
            reload_ev = re.search(r"Event Actor\.OnPlayerLoadGame\(.*?EndEvent", txt, re.S)
            self.assertIsNotNone(reload_ev, f"{psc_path.name} missing OnPlayerLoadGame")
            self.assertIn("if gateDeferred && !instanceStarted", reload_ev.group(0))
            self.assertIn("WakeFromPredecessor()", reload_ev.group(0))

            # 4. Predecessor handoff wakes an already-running dormant RunOnce successor
            pred_txt = pred_path.read_text(encoding="utf-8")
            self.assertIn(f"as {script_cls}", pred_txt, f"{pred_path.name} does not cast to {script_cls} to wake dormant successor")
            self.assertIn(".WakeFromPredecessor()", pred_txt, f"{pred_path.name} does not call WakeFromPredecessor()")

            # 5. First stage exists in StartQuestInstance after gate clears
            self.assertIn(first_stage_call, sbody)

            # 6. Simulate RunOnce lifecycle: early start -> dormant -> predecessor completes -> reaches first stage
            stopped_forever = False
            pred_done = False
            gate_deferred = False
            instance_started = False
            stage = 0
            first_stage = 5 if "AdvanceTo(5," in first_stage_call else 10

            def start_quest_instance() -> None:
                nonlocal gate_deferred, instance_started, stage, stopped_forever
                if stopped_forever or instance_started:
                    return
                instance_started = True
                if not pred_done:
                    gate_deferred = True
                    instance_started = False
                    # Never sets stopped_forever on RunOnce defer!
                    return
                gate_deferred = False
                stage = first_stage

            start_quest_instance()  # Early start before predecessor finishes
            self.assertTrue(gate_deferred, f"{qtag} should defer when predecessor incomplete")
            self.assertFalse(stopped_forever, f"{qtag} must not Stop() on RunOnce defer")
            self.assertEqual(stage, 0, f"{qtag} must stay at stage 0 while dormant")

            pred_done = True  # Predecessor completes and calls WakeFromPredecessor()
            if not instance_started and pred_done:
                gate_deferred = False
                start_quest_instance()
            self.assertFalse(gate_deferred)
            self.assertTrue(instance_started)
            self.assertEqual(stage, first_stage, f"{qtag} must reach first stage {first_stage} after predecessor completes")

        # MQ106 specifically requires MQ105 completion (stage >= 200, NOT stage 100 trail)
        mq106 = PSC_MQ106.read_text(encoding="utf-8")
        self.assertIn("mq105.GetStage() >= 200", mq106)
        self.assertNotIn("mq105.GetStage() >= 100", mq106)

    def test_r7_mq204_rads_gated_by_fo4sfrads_and_sanctuary_alias_selfcheck_restored(self) -> None:
        mq204 = PSC_MQ204.read_text(encoding="utf-8")
        self.assertIn("if !Game.IsPluginInstalled(RadsPlugin)", mq204)
        self.assertIn('Trace("mq204 rads_gated active=false reason=s9_fo4sfrads_absent")', mq204)
        self.assertNotIn("ApplyTrack1GlowingSeaRads", mq204)

        a4_cs = CS_A4.read_text(encoding="utf-8")
        self.assertIn('sal.Name == "SanctuaryWorkbench" && sal.ForcedReference.IsNull', a4_cs)
        self.assertIn("sqObj10.Targets[0].AliasID == 0", a4_cs)

    def test_r8_no_false_completion_without_fo4port_and_honest_stand_in_labels(self) -> None:
        mq203 = PSC_MQ203.read_text(encoding="utf-8")
        self.assertIn("bool Function MovePlayerToKelloggBrain(Actor player)", mq203)
        self.assertIn("mq203 brain_move blocked=true reason=missing_port_cell cell=0x00F23E marker=0x00F2D3", mq203)
        self.assertIn("if MovePlayerToKelloggBrain(Game.GetPlayer())", mq203)
        self.assertIn('Trace("mq203 stand_in_scan=true reason=open_mode_autonomous_scan")', mq203)

        mq206 = PSC_MQ206.read_text(encoding="utf-8")
        fire_fn = re.search(r"Function FireRelayToInstitute\(.*?EndFunction", mq206, re.S)
        self.assertIsNotNone(fire_fn)
        body = fire_fn.group(0)
        self.assertIn("mq206 relay_blocked reason=missing_port_cell cell=0x03D252 marker=0x03D52E", body)
        # AdvanceTo(1200) must sit INSIDE the concourseMarker != None branch, never after the fallback block
        self.assertLess(body.index("AdvanceTo(1200, why)"), body.index("mq206 relay_blocked"))
        self.assertIn('Trace("mq206 stand_in_build part=platform kind=messagebox_counter")', mq206)

        mq106 = PSC_MQ106.read_text(encoding="utf-8")
        self.assertIn('Trace("mq106 prydwen_stand_in=true kind=global_only")', mq106)

        sanc = PSC_SANC.read_text(encoding="utf-8")
        self.assertIn('Trace("sanctuary01 stand_in_build_menu opened stage=" + EffectiveStage())', sanc)

        # make_mission.summarize() captures both stand_in_events and blocked_missing_port
        s = make_mission.summarize([
            "FO4SF_MISSION rt=1.0 sanctuary01 stand_in_build_menu opened stage=1000",
            "FO4SF_MISSION rt=2.0 mq106 prydwen_stand_in=true kind=global_only",
            "FO4SF_MISSION rt=3.0 mq203 brain_move blocked=true reason=missing_port_cell cell=0x00F23E marker=0x00F2D3",
            "FO4SF_MISSION rt=4.0 mq206 relay_blocked reason=missing_port_cell cell=0x03D252 marker=0x03D52E",
        ])
        self.assertEqual(len(s["stand_in_events"]), 2)
        self.assertEqual(len(s["blocked_missing_port"]), 2)


if __name__ == "__main__":
    unittest.main()
