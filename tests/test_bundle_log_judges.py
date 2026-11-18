"""Unit tests for `bundle_log.py` system judges using synthetic hand-written state lines."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fo4sf.core import bundle_log  # noqa: E402


class BundleLogJudgesTests(unittest.TestCase):
    def test_workshop_requires_reload_audit_when_reload_with_positive_persisted_count(self) -> None:
        base_scrap_place = [
            "FO4SFWSCORE rt=10.0 bench_placed stage=10 mode=Console ref=1001 base=2001 moved=true loaded=true haskw=true cell=3001 dist=2.5 count=1 end=true",
            "FO4SFWSCORE rt=12.0 camp_deployed stage=15 mode=Console ref=1002 base=2002 moved=true loaded=true haskw=true cell=3001 dist=4.0 active_camps=1 end=true",
            "FO4SFWSCORE rt=14.0 scrap_run stage=20 mode=Console junk_removed=8 components_added=16 steel_iron=8 aluminum=4 adhesive=4 pass=true end=true",
        ]

        # Negative 1: arrival + stage50 reload_audit without an actual reload (reload_count=0) MUST fail
        no_reload_lines = [
            *base_scrap_place,
            "FO4SFWSCORE rt=2.0 reload_audit when=arrival reload_count=0 benches_ok=0/0 beacons_ok=0/0 stations_ok=0/0 pass=false end=true",
            "FO4SFWSCORE rt=16.0 reload_audit when=stage50 reload_count=0 benches_ok=1/1 beacons_ok=0/0 stations_ok=0/0 pass=true end=true",
        ]
        self.assertFalse(bundle_log.eval_workshop(no_reload_lines)["ok"])

        # Negative 2: when=init or tracked_beacons=0 or pass=false MUST fail
        self.assertFalse(
            bundle_log.eval_workshop([*base_scrap_place, "reload_audit when=init tracked_beacons=1"])["ok"]
        )
        self.assertFalse(
            bundle_log.eval_workshop([*base_scrap_place, "reload_audit when=reload tracked_beacons=0"])["ok"]
        )
        self.assertFalse(
            bundle_log.eval_workshop(
                [*base_scrap_place, "reload_audit when=reload reload_count=1 benches_ok=0/0 beacons_ok=0/0 stations_ok=0/0 pass=false"]
            )["ok"]
        )

        # Positive 1: post-reload audit line with positive persisted bench/beacon count passes
        post_reload = [
            *base_scrap_place,
            "FO4SFWSCORE rt=25.0 reload_audit when=reload reload_count=1 benches_ok=1/1 beacons_ok=1/1 stations_ok=0/0 pass=true end=true",
        ]
        self.assertTrue(bundle_log.eval_workshop(post_reload)["ok"])

        # Positive 2: tracked_beacons=[1-9] schema
        self.assertTrue(
            bundle_log.eval_workshop(
                ["cmpo_scrap items=16", "camp_deployed ok=true", "reload_audit when=reload tracked_beacons=1"]
            )["ok"]
        )

    def test_dialogue_requires_explicit_choice_line_and_fails_on_baseline_sheet_or_stage10(self) -> None:
        # Negative: speaker init + baseline_low eval without opening DialogueMenu choice MUST fail
        baseline_only = [
            "FO4SFLIST rt=5.0 Init speaker_present=true arrival_present=true end=true",
            "FO4SFLIST rt=10.0 eval phase=baseline_low speech=25.0 speech50=fail science=25.0 science40=fail strength=1.0 strength7=fail bg_vaultdweller=Locked trait_goodnatured=Locked end=true",
        ]
        self.assertFalse(bundle_log.eval_dialogue(baseline_only)["ok"])

        # Bare stage=10, bare stage=20 without choice, qualified_high sheet, or Plain_Goodbye stage=60 MUST fail
        self.assertFalse(bundle_log.eval_dialogue(["stage=10"])["ok"])
        self.assertFalse(bundle_log.eval_dialogue(["poll stage=20"])["ok"])
        self.assertFalse(
            bundle_log.eval_dialogue(
                ["FO4SFLIST rt=12.0 eval phase=qualified_high speech=55.0 speech50=pass science=45.0 science40=pass end=true"]
            )["ok"]
        )
        self.assertFalse(
            bundle_log.eval_dialogue(["FO4SFLIST rt=15.0 choice_stage stage=60 tag=Plain_Goodbye outcome=exit end=true"])["ok"]
        )

        # Positive: explicit choice / choice_stage on stages 20..50 passes
        self.assertTrue(
            bundle_log.eval_dialogue(
                ["FO4SFLIST rt=20.0 choice_stage stage=20 tag=Speech_50 outcome=pass end=true"]
            )["ok"]
        )
        self.assertTrue(bundle_log.eval_dialogue(["choice stage=30 strength_pass=true"])["ok"])

    def test_progression_requires_progression_creation_applied_and_rejects_harness_chargen_or_stage10(self) -> None:
        # Negative 1: walk-harness FO4SFCoreCandidate chargen_applied alone MUST fail
        cand_harness = [
            "FO4SFCANDIDATE rt=10.0 chargen_applied run=1 trigger=kiosk_activate bg=VaultDweller trait1=GoodNatured trait2=SmallFrame traits_count=2 special_sum=40 speech=52 science=52 str=7 end=true"
        ]
        res_harness = bundle_log.eval_progression(cand_harness, ["FO4SFPROG rt=5.0 Init pool28=0 cadence=2 respec_used=0 end=true"])
        self.assertFalse(res_harness["ok"])
        self.assertIn("walk_harness_only", res_harness["detail"])

        # Negative 2: loose stage id=10, console test-stage creation line, or wrong special_sum MUST fail
        self.assertFalse(bundle_log.eval_progression([], ["stage id=10"])["ok"])
        self.assertFalse(
            bundle_log.eval_progression(
                [],
                ["FO4SFPROG rt=15.0 creation ok=true bg=Vault_Dweller traits=2 special_sum=40 skills_count=13 end=true"],
            )["ok"]
        )
        self.assertFalse(
            bundle_log.eval_progression(
                [],
                ["FO4SFPROG rt=18.0 creation_applied source=lift_prompt bg=0 traits=2 special_sum=35 skills_count=13 end=true"],
            )["ok"]
        )

        # Positive: FO4SFProgression creation_applied state line with 40-pt SPECIAL and 13 skills passes
        prog_applied = [
            "FO4SFPROG rt=20.0 creation_applied source=lift_prompt bg=0 traits=2 special_sum=40 skills_count=13 tags=10,3,4 carry_mod=45.0 end=true"
        ]
        self.assertTrue(bundle_log.eval_progression(cand_harness, prog_applied)["ok"])

    def test_companions_requires_real_chokepoint_teleport_and_reload_audit(self) -> None:
        fireteam_and_reload = [
            "FO4SFCOMP rt=10.0 stage_result stage=20 cap=4 active=4 wait_all=4 follow_all=4 pass=true end=true",
            "FO4SFCOMP rt=30.0 reload_audit when=reload reload_count=1 squad_ok=4/4 following=4 waiting=0 stance=0 united_perk=true pass=true end=true",
        ]

        # Negative 1: loose word 'teleport' in init/config/refusal or moved=0 MUST fail
        self.assertFalse(
            bundle_log.eval_companions([*fireteam_and_reload, "FO4SFCOMP rt=1.0 init register_player_teleport=true end=true"])["ok"]
        )
        self.assertFalse(
            bundle_log.eval_companions([*fireteam_and_reload, "FO4SFCOMP rt=20.0 teleport reason=load_door_cell_change moved=0 active=0 end=true"])["ok"]
        )
        self.assertFalse(
            bundle_log.eval_companions([*fireteam_and_reload, "FO4SFCOMP rt=25.0 teleport_refused reason=in_combat end=true"])["ok"]
        )

        # Negative 2: stage50 audit without reload (when=stage50 reload_count=0) MUST fail
        no_reload = [
            "FO4SFCOMP rt=10.0 stage_result stage=20 cap=4 active=4 wait_all=4 follow_all=4 pass=true end=true",
            "FO4SFCOMP rt=15.0 teleport reason=load_door_cell_change moved=3 skipped_waiting=1 active=4 cell=4001 interior=true end=true",
            "FO4SFCOMP rt=20.0 reload_audit when=stage50 reload_count=0 squad_ok=4/4 following=4 waiting=0 stance=0 united_perk=true pass=true end=true",
        ]
        self.assertFalse(bundle_log.eval_companions(no_reload)["ok"])

        # Positive: FO4SFCompanions teleport chokepoint line + post-reload audit passes
        self.assertTrue(
            bundle_log.eval_companions(
                [
                    *fireteam_and_reload,
                    "FO4SFCOMP rt=15.0 teleport reason=load_door_cell_change moved=3 skipped_waiting=1 active=4 cell=4001 interior=true end=true",
                ]
            )["ok"]
        )

    def test_pipboy_requires_discovered_markers_and_fails_on_watchdog_or_gfx_failure(self) -> None:
        good_populate = [
            "step=map_key n=1 vk=0x4d was_open=0 page=3 sent=show",
            "step=data_obj_fill when=PopulatePipboyInfoObj page=0 tab=0 hp=200/200 ap=100/100 lvl=1 stim=2 radaway=1 rads=0 date=10.23.2287",
            "step=map_texture loaded=1 children=1",
            "step=map_markers n=310 discovered=1 undiscovered=308 player_idx=309 corners_set=3/3 read_back=match",
            "step=toggle n=1 was_open=1 sent=hide",
            "step=starmap_blocked n=1 route=create",
        ]
        self.assertTrue(bundle_log.eval_pipboy(good_populate)["ok"])

        # Legacy step=code_obj_special ... pushed=7 also accepted when PopulatePipboyInfoObj line is absent
        good_special = [
            "step=code_obj_special n=1 when=late mode=fill found=1 type=9 cleared_by=splice pushed=7 length=#7",
            "step=map_key n=1 vk=0x4D was_open=0 page=3 sent=show",
            "step=map_markers n=309 discovered=2 undiscovered=307 player_idx=309 corners_set=3/3 read_back=match",
            "step=map_key n=2 vk=0x4D was_open=1 on_map=1 sent=hide",
            "step=starmap_blocked n=1 route=create",
        ]
        self.assertTrue(bundle_log.eval_pipboy(good_special)["ok"])

        # Negative: step=map_markers n=310 discovered=0 MUST fail even if map_texture loaded=1 is present
        zero_discovered = [
            ln.replace("discovered=1", "discovered=0") for ln in good_populate
        ]
        res_zero = bundle_log.eval_pipboy(zero_discovered)
        self.assertFalse(res_zero["ok"])
        self.assertIn("markers_discovered=False", res_zero["detail"])

        # Watchdog busy or gfx_exit ok=0 MUST fail
        self.assertFalse(
            bundle_log.eval_pipboy([*good_populate, "step=watchdog_busy seq=4 call=Menu_mc.InvalidateData busy_ms=2100"])["ok"]
        )
        self.assertFalse(
            bundle_log.eval_pipboy([*good_populate, "step=gfx_exit seq=5 call=Menu_mc.InvalidateData ok=0 took_ms=12"])["ok"]
        )

    def test_rads_fails_when_rule_switch_or_verdict_reports_false(self) -> None:
        # Negative: exposure + RadAway happened, but Rule B mode_switch ok=false and verdict pass=false
        failed_switch = [
            "FO4SFRADSCORE rt=10.0 gain source=hazard_zone raw=180.0 resist=0.0 added=180.0 rads=200.0 end=true",
            "FO4SFRADSCORE rt=20.0 mode_switch stage=40 from_rule=0 to_rule=1 rads=600.0 hp=200.0 end=1.0 agi=1.0 str=1.0 drift_hp=0.0 drift_end=3.0 drift_agi=2.0 drift_str=1.0 ok=false end=true",
            "FO4SFRADSCORE rt=30.0 radaway before=100.0 delta=-100.0 rads=0.0 rule=0 mut_on=0 starched=false cured_perk=None end=true",
            "FO4SFRADSCORE rt=35.0 verdict pass=false stages=10,20,30,40,50,60 drift=0.0 end=true",
        ]
        self.assertFalse(bundle_log.eval_rads(failed_switch)["ok"])
        self.assertTrue(
            bundle_log.eval_rads(
                [
                    "FO4SFRADSCORE rt=10.0 gain source=hazard_zone rads=150.0 end=true",
                    "FO4SFRADSCORE rt=20.0 radaway delta=-300 rads=0.0 end=true",
                ]
            )["ok"]
        )


if __name__ == "__main__":
    unittest.main()
