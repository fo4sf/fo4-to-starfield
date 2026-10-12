"""The first converted Fallout 4 NPC (docs/actors/raider-conversion.md): raider_map.py's field mapping, calm probe and
npc_nav plans, the contract with dotnet/ActorRaider's writer, and the runner behaviour the N2 runs need (testqueue.py's
control_npc gate, plan keys, same-queue requires, the hostile-actor judging, exp_install.py's plugin-only install).
Synthetic data only: an export shaped like `ActorRaider export-fo4` writes, no game file, nothing executed."""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "actors"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import exp_install  # noqa: E402
import raider_map as rm  # noqa: E402
import test_npc_nav as nn  # noqa: E402  (its helpers: FakeControls, walk_obs, towards, run_args)
import testqueue as tq  # noqa: E402

WRITER = os.path.join(ROOT, "dotnet", "ActorRaider", "Writer.cs")
N0_PLAN = {"travel": "coc QASmoke", "a": [-8, -4, 0], "b": [5, 10, 0], "drop": 0.5, "settle_ms": 1500,
           "reads_s": [0, 3, 8, 15, 30], "radius": 2.5, "min_progress": 5.0}   # npc_nav_n0's plan.json values
RAIDER, PROBE, SPACER, CITIZEN = "02F04800", "02F04801", "00270255", "002B211C"


class Tmp(unittest.TestCase):
    def tmp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        return d


def link(edid, rtype, fid="00000001"):
    return {"id": fid, "edid": edid, "type": rtype}


def hop(frm, via, picked, cands=None):
    return {"from": frm, "via": link(via, "LeveledNpc"), "candidates": cands or [picked], "picked": picked}


def fo4_export(**over):
    """An export of a templated level-1 raider: traits from a face list, everything else from the tier-1 template."""
    cats = {c: {"templated": True, "source": "EncRaider01Template", "hops": [hop("LvlRaider", "LCharRaider", "EncRaider01Template")]}
            for c in ("Stats", "Factions", "SpellList", "AiData", "AiPackages", "BaseData", "Inventory", "AttackData", "Keywords")}
    cats["Traits"] = {"templated": True, "source": "encRaiderFaceM01",
                      "hops": [hop("LvlRaider", "LCharRaiderFaceAndGender", "encRaiderFaceM01", ["encRaiderFaceM01", "encRaiderFaceF01"])]}
    for c in ("ModelOrAnimation", "Script", "DefPackList"):
        cats[c] = {"templated": False, "source": "LvlRaider", "hops": []}
    fields = {
        "name": "Raider", "flags": ["Respawn", "AutoCalcStats"], "level": {"level": 1}, "xp_value_offset": 5,
        "disposition_base": 35, "class": link("raiderClass", "Class"), "properties": [{"av": "Health", "value": -10}],
        "factions": [dict(link("RaiderFaction", "Faction"), rank=0)], "perks": [link("crDamage075", "Perk")],
        "ai": {"aggression": "VeryAggressive", "confidence": "Foolhardy"}, "combat_style": link("csRaiderRanged", "CombatStyle"),
        "race": link("HumanRace", "Race"), "female": False, "voice": link("RaiderMale01", "VoiceType"), "height": [1, 1],
        "head_parts": 14,
        "items": [dict(link("LLI_Raider_Weapons", "LeveledItem"), count=1, entries=[
                      dict(link("LL_HandmadeGun", "LeveledItem"), level=1, count=1),
                      dict(link("LL_DoubleBarrelShotgun", "LeveledItem"), level=1, count=1),
                      dict(link("LL_CombatRifle", "LeveledItem"), level=14, count=1)]),
                  dict(link("LL_Stimpack_Raider_15", "LeveledItem"), count=1, entries=[])],
        "default_outfit": link("Outfit_Raider", "Outfit"), "death_item": link("LLD_Raider", "LeveledItem"),
        "default_package_list": link("DefaultMasterPackageList", "FormList"),
        "combat_override_package_list": link("DefaultCombatMasterPackageList", "FormList"),
        "keywords": [link("AnimArchetypeIrritated", "Keyword")],
    }
    fields.update(over.pop("fields", {}))
    doc = {"player_level": 1, "achr": {"id": "00000002", "edid": "SomeRaider"}, "categories": cats,
           "base": {"id": "00000003", "edid": "LvlRaider", "default_template": link("LCharRaider", "LeveledNpc")},
           "fields": fields}
    doc.update(over)
    return doc


class MappingTests(unittest.TestCase):
    def test_identity_is_own_and_behaviour_is_inherited_from_the_spacer_templates(self):
        spec, rows = rm.map_npc(fo4_export())
        self.assertEqual((spec["editor_id"], spec["name"], spec["form_id"]), ("FO4_LvlRaider", "Raider", "F04800"))
        self.assertEqual(spec["role"], "conversion")
        self.assertEqual(spec["race"], rm.HUMAN_RACE)
        self.assertEqual(spec["default_template"], rm.ENC_SPACER_01)
        self.assertEqual(spec["templates"]["Traits"]["edid"], "EncSpacerFaceM01")
        for c in rm.INHERIT:
            self.assertIn(c, spec["templates"])
            if c != "Traits":
                self.assertEqual(spec["templates"][c], rm.ENC_SPACER_01, c)
        # own: factions, base data (name, flags), inventory; never inherited, so the FO4 identity survives
        for c in rm.OWN:
            self.assertNotIn(c, spec["use_template"])
        self.assertEqual(rm.template_flags(spec["use_template"]), 0x7E3B)
        self.assertEqual([f["faction"]["edid"] for f in spec["factions"]], ["SpacerFaction", "GroupFactionSpacers"])
        self.assertEqual(spec["formation_faction"]["edid"], "GroupFactionSpacers")
        self.assertEqual(spec["items"], [{"item": rm.COACHMAN, "count": 1}])
        self.assertEqual((spec["death_item"]["edid"], spec["default_outfit"]["edid"], spec["space_outfit"]["edid"]),
                         ("LLD_Spacer", "Outfit_Clothes_Mechanic_Tanktop_Brown", "Outfit_Spacesuit_Spacer_AssaultOrNoRole"))
        self.assertEqual(spec["combat_style"]["edid"], "csSpacer_Assault")
        self.assertEqual(spec["flags"], ["Respawn"])                     # AutoCalcStats goes with the inherited Stats
        self.assertEqual(spec["level"], 8)                               # tier 1 -> tier 1 (EncSpacer01Template)
        self.assertEqual((spec["voice"]["edid"], spec["class"]["edid"]), ("SpacerMale01", "CrimsonFleetClass"))
        self.assertEqual(spec["object_bounds"], [[-0.31, -0.31, 0.0], [0.31, 0.31, 1.8]])
        hows = {r["fo4"]: r for r in rows}
        self.assertIn("inherited", hows["AIDT"]["sf_value"])
        self.assertIn("LL_Stimpack_Raider_15", hows["CNTO other"]["fo4_value"])
        self.assertNotIn("LLI_Raider_Weapons", hows["CNTO other"]["fo4_value"])

    def test_the_record_carries_what_every_vanilla_npc_carries(self):
        # raw scan of Starfield.esm: form version 581 and PRPS / STON / PRON / EDCT in all 7,131 NPC_; the writer copies
        # PRPS from the Stats template and STON / PRON from the Traits template, both inherited
        spec, rows = rm.map_npc(fo4_export())
        self.assertEqual(spec["form_version"], 581)
        self.assertEqual(spec["copied"], {"properties": "Stats", "skin_tone_index": "Traits", "pronoun": "Traits"})
        for cat in spec["copied"].values():
            self.assertIn(cat, spec["use_template"])                       # only an inherited category is copied
        spec["copied"]["pronoun"] = "Factions"
        self.assertEqual(rm.VANILLA_CONSTANTS["copied"]["pronoun"], "Traits")   # each spec has its own copy
        self.assertTrue(any("PRPS" in r["fo4"] and "7,131 of 7,131" in r["how"] for r in rows))
        self.assertTrue(any("STON" in r["sf"] and "EDCT 0" in r["sf_value"] for r in rows))

    def test_overridden_fields_and_the_ammo_inference_are_labelled(self):
        _, rows = rm.map_npc(fo4_export())
        hows = {r["fo4"]: r["how"] for r in rows}
        self.assertIn("probably overridden (supported hypothesis)", hows["INAM death item"])
        self.assertIn("goes with Traits", hows["INAM death item"])
        self.assertIn("supported hypothesis", hows["ZNAM combat style"])
        self.assertIn("same csSpacer_Assault (verified)", hows["ZNAM combat style"])
        self.assertIn("supported hypothesis", hows["CNTO weapons"])
        self.assertIn("74 of 84", hows["CNTO weapons"])

    def test_the_calm_probe_is_the_conversion_without_factions(self):
        spec, _ = rm.map_npc(fo4_export())
        probe = rm.calm_probe(spec)
        self.assertEqual((probe["role"], probe["editor_id"], probe["form_id"]), ("calm_probe", "FO4_LvlRaider_Calm", "F04801"))
        self.assertEqual(probe["factions"], [])
        self.assertNotIn("formation_faction", probe)
        same = {k for k in spec if k not in ("role", "editor_id", "form_id", "factions", "formation_faction")}
        self.assertEqual({k: probe[k] for k in same}, {k: spec[k] for k in same})
        self.assertEqual(len(spec["factions"]), 2)                        # the conversion is untouched

    def test_every_starfield_link_names_id_edid_and_type(self):
        spec, _ = rm.map_npc(fo4_export())

        def links(o):
            if isinstance(o, dict):
                if set(o) == {"id", "edid", "type"}:
                    yield o
                for v in o.values():
                    yield from links(v)
            elif isinstance(o, list):
                for v in o:
                    yield from links(v)
        found = list(links(spec))
        self.assertGreater(len(found), 15)
        for ln in found:
            self.assertRegex(ln["id"], r"^00[0-9A-F]{6}$")              # Starfield.esm (load index 00) only
            self.assertTrue(ln["edid"] and ln["type"])

    def test_weapon_is_the_first_mapped_entry_at_the_encounter_level(self):
        f = fo4_export()
        f["fields"]["items"][0]["entries"] = [dict(link("LL_CombatRifle", "LeveledItem"), level=14, count=1),
                                              dict(link("LL_DoubleBarrelShotgun", "LeveledItem"), level=20, count=1)]
        with self.assertRaises(rm.MappingError):                           # above level 1: not this encounter's
            rm.map_npc(f)
        f["player_level"] = 20
        self.assertEqual(rm.map_npc(f)[0]["items"][0]["item"]["edid"], "Coachman")

    def test_unmappable_sources_stop_the_mapping(self):
        for over in ({"fields": {"race": link("GhoulRace", "Race")}},
                     {"fields": {"factions": [dict(link("GunnerFaction", "Faction"), rank=0)]}}):
            with self.assertRaises(rm.MappingError, msg=str(over)):
                rm.map_npc(fo4_export(**over))
        f = fo4_export()
        f["categories"]["Stats"]["source"] = "EncRaider05"                # a tier without a Starfield counterpart yet
        with self.assertRaises(rm.MappingError):
            rm.map_npc(f)

    def test_a_dropped_faction_is_reported_but_the_mapped_one_kept(self):
        f = fo4_export(fields={"factions": [dict(link("RaiderFaction", "Faction"), rank=0),
                                            dict(link("DN092_Faction", "Faction"), rank=1)]})
        spec, rows = rm.map_npc(f)
        self.assertEqual(len(spec["factions"]), 2)
        self.assertTrue(any(r["fo4_value"] == "DN092_Faction" and r["how"].startswith("dropped") for r in rows))

    def test_faces_map_by_gender_and_number(self):
        self.assertEqual(rm.face_for("encRaiderFaceM01", False)["edid"], "EncSpacerFaceM01")
        self.assertEqual(rm.face_for("encRaiderFaceM05", False)["edid"], "EncSpacerFaceM01")    # 4 Starfield faces
        self.assertEqual(rm.face_for("encRaiderFaceF02", False)["edid"], "EncSpacerFaceF02")
        self.assertEqual(rm.face_for("SomeoneElse", True)["edid"], "EncSpacerFaceF01")

    def test_runtime_id_and_template_flags(self):
        self.assertEqual(rm.runtime_id("02", "F04800"), "02F04800")
        for bad in (("00", "F04800"), ("FE", "F04800"), ("02", "7FF"), ("02", "1000000")):
            with self.assertRaises(rm.MappingError):
                rm.runtime_id(*bad)
        self.assertEqual(rm.template_flags(["Traits", "Unknown2"]), 1 | 1 << 14)
        with self.assertRaises(rm.MappingError):
            rm.template_flags(["Voice"])

    def test_table_has_a_row_per_mapping(self):
        _, rows = rm.map_npc(fo4_export())
        md = rm.table_md(rows)
        self.assertEqual(md.count("\n"), len(rows) + 2)
        self.assertIn("| SNAM faction | RaiderFaction rank 0 | Factions | SpacerFaction + GroupFactionSpacers |", md)


class WriterContractTests(unittest.TestCase):
    """raider_map.py writes what dotnet/ActorRaider/Writer.cs reads; checked on the C# source, nothing is run."""
    def src(self):
        with open(WRITER, encoding="utf-8-sig") as f:
            return f.read()

    def test_spec_has_every_key_the_writer_reads(self):
        src = self.src()
        required = set(re.findall(r'n\.GetProperty\("([a-z_0-9]+)"\)', src))
        optional = set(re.findall(r'Opt\("([a-z_0-9]+)"\)', src))
        copied = set(re.findall(r'Tpl\("([a-z_0-9]+)"\)', src))
        self.assertTrue({"default_template", "role", "copied", "form_version"} <= required, required)
        spec, _ = rm.map_npc(fo4_export())
        for npc in (spec, rm.calm_probe(spec)):
            self.assertFalse(required - set(npc), required - set(npc))
            self.assertFalse((set(npc) - required - optional) - {"form_id"}, set(npc) - required - optional)
            self.assertEqual(set(npc["copied"]), copied)

    def test_template_slots_agree(self):
        slots = dict((n, int(b)) for n, b in re.findall(r'\("([A-Za-z0-9]+)", (\d+)\)', self.src()))
        self.assertEqual(slots, rm.CATEGORY_BITS)

    def test_check_knows_what_every_vanilla_npc_carries(self):
        src = self.src()
        always = re.search(r"AlwaysPresent =\s*\{([^}]*)\}", src).group(1)
        for sub in ("PRPS", "STON", "EDCT", "PRON", "ACBS", "AIDT"):
            self.assertIn(f'"{sub}"', always)
        self.assertEqual(int(re.search(r"VanillaNpcFormVersion = (\d+);", src).group(1)),
                         rm.VANILLA_CONSTANTS["form_version"])
        self.assertIn("npc.Tints = new ExtendedList<NpcTint>()", src)        # EDCT 0, no tint blocks


class PlanTests(Tmp):
    def test_n2a_is_the_calm_probe_against_n0_and_n2b_the_hostile_pair(self):
        qa = os.path.join(self.tmp(), "npc_nav_n2a")
        n2a, n2b = rm.plans(RAIDER, PROBE, qa)
        for t in n2a + n2b:
            for k, v in N0_PLAN.items():
                self.assertEqual(t[k], v, (t["label"], k))
            self.assertTrue(t["expect"] and t["basis"])
            self.assertRegex(t["basis"], r"(verified|supported hypothesis|unresolved):")
            self.assertNotEqual(t["method"], "combat_player")              # no StartCombat on innately hostile actors
            self.assertFalse(t["control"])
        # N2a: the calm probe, N0's methods, gated by N0's citizen; all but the base wait for the base's spawn
        self.assertEqual({t["npc"] for t in n2a}, {PROBE})
        self.assertEqual({t["method"] for t in n2a}, {"none", "ptr_player", "cf_pathto_player", "follow_player"})
        base = [t for t in n2a if t["method"] == "none"][0]
        self.assertEqual((base["label"], base["expect"]), ("N2a_base", "PASS"))
        self.assertNotIn("requires", base)
        for t in n2a:
            self.assertNotIn("handle_tol", t)                               # calm: N0's 2 m
            if t is not base:
                self.assertEqual(t["control_npc"], CITIZEN)
                self.assertEqual(t["requires"], {"test": "N2a_base", "verdict": "DECIDED"})
                self.assertNotIn("hostile raider", t["basis"])
        # N2b: the conversion and the vanilla Spacer, both without a command; the raider waits for N2a's base
        self.assertEqual({(t["npc"], t["method"], t["expect"]) for t in n2b},
                         {(SPACER, "none", "FAIL WANDER"), (RAIDER, "none", "FAIL WANDER")})
        for t in n2b:
            self.assertEqual(t["handle_tol"], 3.0)                        # hostile: may step away during the handle
            self.assertNotIn("control_npc", t)
        raider = [t for t in n2b if t["npc"] == RAIDER][0]
        self.assertEqual(raider["requires"], {"test": "N2a_base", "verdict": "DECIDED", "queue": qa})

    def plan(self, d, name, tests, *extra):
        exp = os.path.join(d, name)
        os.makedirs(exp, exist_ok=True)
        with open(os.path.join(exp, "plan.json"), "w") as f:
            json.dump(tests, f)
        out = os.path.join(d, "q_" + name)
        tq.main(["plan-npc", "--staging", d, "--exp-dir", exp, "--out", out, "--install-exp",
                 os.path.join(d, "actor_raider2"), "--plugins", "FO4ActorRaider.esm", "--fresh", *extra])
        with open(os.path.join(out, "queue.json")) as f:
            return out, json.load(f)

    def test_plans_pass_plan_npc_validation_and_check_queue(self):
        d = self.tmp()
        open(os.path.join(d, "FO4Port.esm"), "wb").close()
        qa_dir = os.path.join(d, "q_n2a")
        n2a, n2b = rm.plans(RAIDER, PROBE, qa_dir)
        with self.assertRaises(SystemExit):                                # N2b before N2a: its base is not planned
            self.plan(d, "n2b", n2b)
        qa, a = self.plan(d, "n2a", n2a, "--control-queue", os.path.join(d, "npc_nav_n0"))
        qb, b = self.plan(d, "n2b", n2b)
        self.assertEqual(qa, qa_dir)
        for q in (a, b):
            self.assertTrue(all(t["fresh"] for t in q["tests"]))
            pre = q["pre_launch"]
            self.assertEqual(pre[pre.index("--plugins") + 1], "FO4ActorRaider.esm")
        self.assertEqual(a["tests"][0]["id"], "0000_npc_nav_N2a_base")      # the baseline first
        self.assertEqual([t.get("control_npc") for t in a["tests"][1:]], [CITIZEN] * 3)
        for t in a["tests"][1:]:                                           # same queue: dir and id filled in
            self.assertEqual(t["requires"], {"queue": qa, "test": "0000_npc_nav_N2a_base", "verdict": "DECIDED"})
        rb = [t for t in b["tests"] if t["npc"] == RAIDER][0]["requires"]
        self.assertEqual(rb, {"queue": qa, "test": "0000_npc_nav_N2a_base", "verdict": "DECIDED"})
        for name, q in (("n2a", qa), ("n2b", qb)):
            self.assertEqual(rm.check_queue(os.path.join(d, name, "plan.json"), q), [])
        # a queue planned by a runner that drops keys it does not know is caught
        with open(os.path.join(qa, "queue.json")) as f:
            q = json.load(f)
        q["tests"][1].pop("control_npc")
        q["tests"][2].pop("requires")
        with open(os.path.join(qa, "queue.json"), "w") as f:
            json.dump(q, f)
        problems = rm.check_queue(os.path.join(d, "n2a", "plan.json"), qa)
        self.assertEqual(len(problems), 2, problems)
        with self.assertRaises(SystemExit):
            rm.main(["check-queue", "--plan", os.path.join(d, "n2a", "plan.json"), "--queue", qa])

    def test_n2b_must_install_what_n2a_measured(self):
        d = self.tmp()
        open(os.path.join(d, "FO4Port.esm"), "wb").close()
        qa_dir = os.path.join(d, "q_n2a")
        n2a, n2b = rm.plans(RAIDER, PROBE, qa_dir)
        self.plan(d, "n2a", n2a)
        exp = os.path.join(d, "n2b")
        os.makedirs(exp)
        with open(os.path.join(exp, "plan.json"), "w") as f:
            json.dump(n2b, f)
        with self.assertRaises(SystemExit):                                # another staged plugin than N2a's
            tq.main(["plan-npc", "--staging", d, "--exp-dir", exp, "--out", os.path.join(d, "q_n2b"),
                     "--install-exp", os.path.join(d, "actor_raider1"), "--plugins", "FO4ActorRaider.esm"])

    def test_same_queue_requires_is_one_level_and_names_another_test(self):
        d = self.tmp()
        open(os.path.join(d, "FO4Port.esm"), "wb").close()
        base = dict(N0_PLAN, label="b0", npc=PROBE, method="none")
        one = dict(N0_PLAN, label="b1", npc=PROBE, requires={"test": "b0", "verdict": "DECIDED"})
        _, q = self.plan(d, "ok", [one, base])
        self.assertEqual(q["tests"][1]["requires"]["test"], q["tests"][0]["id"])   # the baseline was sorted first
        for name, tests in (("self", [base, dict(one, requires={"test": "b1"})]),          # itself
                            ("none", [base, dict(one, requires={"test": "b9"})]),          # no such label
                            ("chain", [base, one, dict(one, label="b2", requires={"test": "b1"})])):
            with self.assertRaises(SystemExit, msg=name):
                self.plan(d, name, tests)

    def test_plans_command_writes_both_plan_files(self):
        d = self.tmp()
        with open(os.path.join(d, "spec.json"), "w") as f:
            json.dump({"plugin": "FO4ActorRaider.esm", "npcs": [{"role": "conversion", "form_id": "F04800"},
                                                                {"role": "calm_probe", "form_id": "F04801"}]}, f)
        rm.main(["plans", "--stage", d, "--n2a", os.path.join(d, "a"), "--n2b", os.path.join(d, "b"),
                 "--n2a-queue", os.path.join(d, "qa")])
        with open(os.path.join(d, "a", "plan.json")) as f:
            self.assertEqual({t["npc"] for t in json.load(f)}, {PROBE})
        with open(os.path.join(d, "b", "plan.json")) as f:
            self.assertEqual({t["npc"] for t in json.load(f)}, {RAIDER, SPACER})


class ControlNpcGateTests(Tmp):
    """A converted actor in the vanilla control cell is judged against the vanilla actor's control there."""
    def setUp(self):
        self.base = tq.npc_test(0, dict(N0_PLAN, label="N0_base", npc=CITIZEN, method="none"))
        self.ctrl = tq.npc_test(1, dict(N0_PLAN, label="N0_ptr", npc=CITIZEN, method="ptr_player", control=True))
        self.raider = tq.npc_test(2, dict(N0_PLAN, label="N2a_ptr", npc=PROBE, method="ptr_player",
                                          control_npc=CITIZEN))
        self.n0 = self.tmp()
        with open(os.path.join(self.n0, "queue.json"), "w") as f:
            json.dump({"tests": [self.base, self.ctrl]}, f)

    def n0_done(self, base, ctrl, base_class="X"):
        with open(os.path.join(self.n0, "state.json"), "w") as f:
            json.dump({"done": {self.base["id"]: {"verdict": base, "class": base_class},
                                self.ctrl["id"]: {"verdict": ctrl, "class": "X"}}}, f)

    def gate(self, test=None, verdict="FAIL", cls="NONAV", own=None):
        d = self.tmp()
        tests = [test or self.raider] + ([own[0]] if own else [])
        q = {"tests": tests, "control_queue": self.n0}
        with open(os.path.join(d, "queue.json"), "w") as f:
            json.dump(q, f)
        if own:
            with open(os.path.join(d, "state.json"), "w") as f:
                json.dump({"done": {own[0]["id"]: own[1]}}, f)
        return tq.control_gate(d, q, test or self.raider, verdict, cls, "x")

    def test_the_vanilla_actors_control_and_baseline_gate_the_converted_one(self):
        self.n0_done("PASS", "PASS")
        v, c, d = self.gate()
        self.assertEqual((v, c), ("FAIL", "NONAV"))
        self.assertIn("control 0001_npc_nav_N0_ptr and baseline 0000_npc_nav_N0_base passed", d)
        self.n0_done("PASS", "FAIL")
        self.assertEqual(self.gate()[1], "CONTROL")
        self.n0_done("FAIL", "PASS", "WANDER")                             # the citizen came on its own (N0, 2026-10-12)
        self.assertEqual(self.gate()[1], "CONTROL")

    def test_without_control_npc_the_converted_actor_has_no_control(self):
        self.n0_done("PASS", "PASS")
        own = dict(self.raider)
        own.pop("control_npc")
        self.assertEqual(self.gate(own)[1], "CONTROL")

    def test_control_npc_is_validated(self):
        for bad in ({"control_npc": "citizen"}, {"control_npc": CITIZEN, "control": True},
                    {"control_npc": CITIZEN, "method": "none"}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                tq.npc_test(0, {**N0_PLAN, "label": "x", "npc": PROBE, "method": "ptr_player", **bad})
        self.assertEqual(tq.npc_test(0, dict(N0_PLAN, npc=PROBE, control_npc="002b211c"))["control_npc"], CITIZEN)

    def test_a_pass_says_whether_its_own_baseline_credits_the_command(self):
        self.n0_done("PASS", "PASS")
        own = tq.npc_test(3, dict(N0_PLAN, label="N2a_base", npc=PROBE, method="none"))
        v, c, d = self.gate(verdict="PASS", cls="PASS", own=(own, {"verdict": "PASS", "class": "PASS"}))
        self.assertEqual((v, c), ("PASS", "PASS"))
        self.assertIn("stayed away without a command: the command moved it", d)
        v, c, d = self.gate(verdict="PASS", cls="PASS", own=(own, {"verdict": "FAIL", "class": "WANDER"}))
        self.assertEqual((v, c), ("PASS", "PASS"))                        # still a PASS: the walk was observed
        self.assertIn("not credited to the command", d)
        self.assertEqual(self.gate(verdict="PASS", cls="PASS")[2], "x")     # no baseline of this actor: no note


class PlanKeyTests(unittest.TestCase):
    """plan.json keys: an unknown key stops the planning; requires may name a test of this queue and DECIDED."""
    def test_unknown_keys_stop_the_planning(self):
        for bad in ({"contol_npc": CITIZEN}, {"handle_tolerance": 3}, {"requires_runner": 2}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                tq.npc_test(0, dict(N0_PLAN, label="x", npc=PROBE, **bad))
        every = dict(N0_PLAN, label="x", npc=PROBE, method="ptr_player", pre=["gnm"], nomove=0.5, spawn_tol=3,
                     target_tol=3, fell_m=3, pre_wait_ms=5000, max_speed=8, spawn_wait_ms=2000, handle_tol=2,
                     path_line=False, control=False, control_npc=CITIZEN, fresh=True,
                     anchor={"ref": "02000800", "local": [0, 0, 0]}, spawn_local=[0, 0, 0],
                     requires={"test": "N2a_base"}, expect="PASS", basis="b")
        # the light and console fields (claude/runner-daylight) are read by with_extras after npc_test
        extras = set(tq.sky_light.LIGHT_KEYS) | set(tq.console_plan.CONSOLE_KEYS)
        self.assertEqual(set(every) | extras, set(tq.NPC_PLAN_KEYS))
        tq.npc_test(0, every)
        tq.npc_test(0, dict(every, time_of_day=12, console_pre=['GetINI "bBorderRegionsEnabled:General"']))

    def test_requires_forms(self):
        t = tq.npc_test(0, dict(N0_PLAN, label="x", npc=PROBE, requires={"test": "N2a_base", "verdict": "DECIDED"}))
        self.assertEqual(t["requires"], {"queue": "", "test": "N2a_base", "verdict": "DECIDED"})
        for bad in ({"test": "N2a_base", "verdict": "MAYBE"}, {"test": "N2a base"}, {"queue": "", "test": "x"},
                    {"test": "x", "when": "later"}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                tq.npc_test(0, dict(N0_PLAN, label="x", npc=PROBE, requires=bad))


class RequiresRunTests(Tmp):
    """A test that requires a test of its own queue waits for that test's final result in the same run."""
    def queue(self, base_verdict="DECIDED"):
        d = self.tmp()
        base = tq.npc_test(0, dict(N0_PLAN, label="N2a_base", npc=PROBE, method="none", expect="PASS"))
        dep = [tq.npc_test(n, dict(N0_PLAN, label=f"N2a_{m}", npc=PROBE, method=m))
               for n, m in ((1, "ptr_player"), (2, "follow_player"))]
        for t in dep:
            t["requires"] = {"queue": d, "test": base["id"], "verdict": base_verdict}
        q = {"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "s",
             "plugin_index": "02", "hours": [[0, 24]], "tests": [base] + dep}
        with open(os.path.join(d, "queue.json"), "w") as f:
            json.dump(q, f)
        return d, base, dep

    def run_queue(self, d, outcome, **args):
        """outcome: test id -> 'walk' | 'still' | 'nospawn' (or a list, one per attempt); returns the step order."""
        order = []

        def step(t, out):
            order.append(t["id"])
            o = outcome[t["id"]]
            o = o[min(order.count(t["id"]), len(o)) - 1] if isinstance(o, list) else o
            obs = nn.walk_obs(out, t, nn.towards(t, [0.2, 0.4, 0.7, 0.9] if o == "walk" else [0, 0, 0, 0]))
            if o == "nospawn":                                              # GetIsID 0: the spawn is not confirmed
                obs["spawn"] = dict(obs["spawn"], isid=0, confirmed=False, why="GetIsID 02F04801 read 0")
            with open(os.path.join(out, "obs.json"), "w") as f:
                json.dump(obs, f)
            return 0
        r = tq.Runner(d, nn.run_args(**args), ctl=nn.FakeControls(), step=step)
        r.session, r._ps = True, (lambda *a, **k: (0, ""))
        r.run()
        return order

    def done(self, d):
        with open(os.path.join(d, "state.json")) as f:
            return json.load(f)["done"]

    def results(self, d):
        with open(os.path.join(d, "results.jsonl"), encoding="utf-8") as f:
            return f.read()

    def test_dependents_wait_for_a_retried_base(self):
        d, base, dep = self.queue()
        order = self.run_queue(d, {base["id"]: ["nospawn", "still"], dep[0]["id"]: "walk", dep[1]["id"]: "walk"})
        self.assertEqual(order, [base["id"], base["id"], dep[0]["id"], dep[1]["id"]])
        done = self.done(d)
        self.assertEqual(done[base["id"]]["verdict"], "PASS")
        self.assertEqual([done[t["id"]]["verdict"] for t in dep], ["PASS", "PASS"])
        self.assertIn("the command moved it", self.results(d))

    def test_no_launch_is_spent_when_the_spawn_is_never_confirmed(self):
        d, base, dep = self.queue()
        order = self.run_queue(d, {base["id"]: "nospawn", dep[0]["id"]: "walk", dep[1]["id"]: "walk"})
        self.assertEqual(order, [base["id"], base["id"]])                  # max_attempts 2, then the others skip
        done = self.done(d)
        self.assertEqual((done[base["id"]]["verdict"], done[base["id"]]["class"]), ("INCONCLUSIVE", "SPAWN"))
        for t in dep:
            self.assertEqual((done[t["id"]]["class"], done[t["id"]]["attempts"]), ("PRECONDITION", 0))

    def test_decided_accepts_a_fail_of_the_base(self):
        d, base, dep = self.queue()
        order = self.run_queue(d, {base["id"]: "walk", dep[0]["id"]: "walk", dep[1]["id"]: "still"})
        self.assertEqual(len(order), 3)
        done = self.done(d)
        self.assertEqual(done[base["id"]]["class"], "WANDER")              # came on its own, the spawn was confirmed
        self.assertIn("not credited to the command", self.results(d))
        d, base, dep = self.queue(base_verdict="PASS")
        self.assertEqual(self.run_queue(d, {base["id"]: "walk", dep[0]["id"]: "walk", dep[1]["id"]: "walk"}),
                         [base["id"]])

    def test_a_dry_run_records_no_precondition(self):
        d, base, dep = self.queue()
        self.run_queue(d, {}, dry_run=True)
        self.assertEqual(self.done(d), {})


class HostileJudgeTests(Tmp):
    """The approach is measured from the spawn read as well as from t0: t0 is read after the player went to B, so an
    actor that came for the player on its own may have closed the gap before it."""
    def obs(self, t, at_t0, samples):
        d = self.tmp()
        o = nn.walk_obs(d, t, nn.towards(t, samples))
        o["t0"] = dict(o["t0"], read=nn.towards(t, [at_t0])[0])
        return d, o

    def test_a_baseline_that_closed_in_before_t0_came_to_b(self):
        base = tq.npc_test(0, dict(N0_PLAN, label="N2b_base", npc=RAIDER, method="none", expect="FAIL WANDER"))
        d, o = self.obs(base, 0.7, [0.7, 0.7, 0.7, 0.7])                  # closed 13 m, then held its distance
        v, cls, detail = tq.judge(base, o, d)
        self.assertEqual((v, cls), ("FAIL", "WANDER"), detail)            # was PASS (stayed away) when judged from t0
        self.assertIn("before the first read", detail)
        d, o = self.obs(base, 0.0, [0, 0.05, 0, 0.05])
        self.assertEqual(tq.judge(base, o, d)[:2], ("PASS", "PASS"))       # a calm actor is judged as before

    def test_a_command_after_an_approach_is_not_judged(self):
        t = tq.npc_test(0, dict(N0_PLAN, label="N2a_ptr", npc=PROBE, method="ptr_player"))
        for samples in ([0.7, 0.7, 0.7, 0.7], [0.75, 0.85, 0.95, 0.99]):   # held (was FAIL NONAV) or went on (PASS)
            d, o = self.obs(t, 0.7, samples)
            v, cls, detail = tq.judge(t, o, d)
            self.assertEqual((v, cls), ("INCONCLUSIVE", "PRECOMMAND"), detail)
        d, o = self.obs(t, 0.0, [0, 0, 0, 0])
        self.assertEqual(tq.judge(t, o, d)[:2], ("FAIL", "NONAV"))
        d, o = self.obs(t, 0.1, [0.2, 0.4, 0.7, 0.9])                      # 1.9 m before the command: a walk
        self.assertEqual(tq.judge(t, o, d)[:2], ("PASS", "PASS"))


class PluginOnlyInstallTests(Tmp):
    def test_pack_without_a_data_tree_installs_the_plugin_and_no_archive(self):
        root = self.tmp()
        game, exp, local = (os.path.join(root, x) for x in ("game", "exp", "local"))
        os.makedirs(os.path.join(game, "Data"))
        os.makedirs(exp)
        os.makedirs(os.path.join(local, "Starfield"))
        with open(os.path.join(exp, "FO4ActorRaider.esm"), "wb") as f:
            f.write(b"TES4")
        with open(os.path.join(exp, "README.txt"), "w") as f:
            f.write("not installed")
        plugins = os.path.join(local, "Starfield", "Plugins.txt")
        with open(plugins, "wb") as f:
            f.write(b"*FO4Port.esm\r\n")
        calls = []
        old = (exp_install.subprocess.run, os.environ.get("LOCALAPPDATA"))
        exp_install.subprocess.run = lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=1, stdout="", stderr="")
        os.environ["LOCALAPPDATA"] = local
        try:
            exp_install.main(["install", "--exp-dir", exp, "--starfield", game, "--plugins", "FO4ActorRaider.esm", "--pack"])
            self.assertEqual(calls, [])                                    # Archive2 never called
            self.assertEqual(sorted(os.listdir(os.path.join(game, "Data"))), ["FO4ActorRaider.esm", exp_install.RECORD])
            with open(plugins, "rb") as f:
                self.assertEqual(f.read(), b"*FO4Port.esm\r\n*FO4ActorRaider.esm\r\n")
            exp_install.main(["uninstall", "--starfield", game])
            self.assertEqual(os.listdir(os.path.join(game, "Data")), [])
            with open(plugins, "rb") as f:
                self.assertEqual(f.read(), b"*FO4Port.esm\r\n")
        finally:
            exp_install.subprocess.run = old[0]
            if old[1] is None:
                os.environ.pop("LOCALAPPDATA")
            else:
                os.environ["LOCALAPPDATA"] = old[1]


if __name__ == "__main__":
    unittest.main()
