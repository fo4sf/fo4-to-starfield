"""The first converted Fallout 4 NPC (docs/actors/raider-conversion.md): raider_map.py's field mapping and npc_nav plans,
the contract with dotnet/ActorRaider's writer, testqueue.py's control_npc gate and exp_install.py's plugin-only install.
Synthetic data only: an export shaped like `ActorRaider export-fo4` writes, no game file, nothing executed."""
import json
import os
import re
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "actors"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import exp_install  # noqa: E402
import raider_map as rm  # noqa: E402
import testqueue as tq  # noqa: E402

WRITER = os.path.join(ROOT, "dotnet", "ActorRaider", "Writer.cs")
N0_PLAN = {"travel": "coc QASmoke", "a": [-8, -4, 0], "b": [5, 10, 0], "drop": 0.5, "settle_ms": 1500,
           "reads_s": [0, 3, 8, 15, 30], "radius": 2.5, "min_progress": 5.0}   # npc_nav_n0's plan.json values


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
    def test_spec_has_every_key_the_writer_reads(self):
        with open(WRITER, encoding="utf-8-sig") as f:
            src = f.read()
        required = set(re.findall(r'n\.GetProperty\("([a-z_0-9]+)"\)', src))
        optional = set(re.findall(r'Opt\("([a-z_0-9]+)"\)', src))
        self.assertIn("default_template", required)
        spec, _ = rm.map_npc(fo4_export())
        self.assertFalse(required - set(spec), required - set(spec))
        self.assertFalse((set(spec) - required - optional) - {"form_id"}, set(spec) - required - optional)

    def test_template_slots_agree(self):
        with open(WRITER, encoding="utf-8-sig") as f:
            src = f.read()
        slots = dict((n, int(b)) for n, b in re.findall(r'\("([A-Za-z0-9]+)", (\d+)\)', src))
        self.assertEqual(slots, rm.CATEGORY_BITS)


class PlanTests(unittest.TestCase):
    def test_n2a_repeats_n0_with_the_raider_and_n2b_has_a_vanilla_control(self):
        n2a, n2b = rm.plans("02F04800")
        self.assertEqual({t["method"] for t in n2a}, {"none", "ptr_player", "cf_pathto_player", "follow_player"})
        for t in n2a + n2b:
            for k, v in N0_PLAN.items():
                self.assertEqual(t[k], v, (t["label"], k))
            self.assertTrue(t["expect"] and t["basis"])
            self.assertRegex(t["basis"], r"(verified|supported hypothesis|unresolved):")
            self.assertEqual(t["handle_tol"], 3.0)                        # hostile: may step away during the handle
        for t in n2a:
            self.assertEqual(t["npc"], "02F04800")
            self.assertFalse(t["control"])
            self.assertEqual(t.get("control_npc"), None if t["method"] == "none" else "002B211C")
        ctrl, raider = n2b
        self.assertEqual((ctrl["npc"], ctrl["method"], ctrl["control"]), ("00270255", "combat_player", True))
        self.assertEqual((raider["npc"], raider["method"], raider.get("control_npc")), ("02F04800", "combat_player", "00270255"))

    def test_plans_pass_plan_npc_validation_and_install_the_plugin_only_stage(self):
        n2a, n2b = rm.plans("02F04800")
        d = tempfile.mkdtemp()
        open(os.path.join(d, "FO4Port.esm"), "wb").close()
        for name, tests in (("n2a", n2a), ("n2b", n2b)):
            exp = os.path.join(d, name)
            os.makedirs(exp)
            with open(os.path.join(exp, "plan.json"), "w") as f:
                json.dump(tests, f)
            out = os.path.join(d, "q_" + name)
            tq.main(["plan-npc", "--staging", d, "--exp-dir", exp, "--out", out, "--install-exp",
                     os.path.join(d, "actor_raider1"), "--plugins", "FO4ActorRaider.esm", "--control-queue",
                     os.path.join(d, "npc_nav_n0"), "--fresh"])
            with open(os.path.join(out, "queue.json")) as f:
                q = json.load(f)
            self.assertTrue(all(t["fresh"] for t in q["tests"]))
            pre = q["pre_launch"]
            self.assertEqual(pre[pre.index("--plugins") + 1], "FO4ActorRaider.esm")
            if name == "n2a":
                self.assertEqual(q["tests"][0]["method"], "none")         # the baseline first
                self.assertEqual([t.get("control_npc") for t in q["tests"][1:]], ["002B211C"] * 3)
            else:
                self.assertTrue(q["tests"][0]["control"])                 # the vanilla control first

    def test_plans_command_writes_both_plan_files(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "spec.json"), "w") as f:
            json.dump({"plugin": "FO4ActorRaider.esm", "npc": {"form_id": "F04800"}}, f)
        rm.main(["plans", "--stage", d, "--n2a", os.path.join(d, "a"), "--n2b", os.path.join(d, "b")])
        with open(os.path.join(d, "a", "plan.json")) as f:
            self.assertEqual({t["npc"] for t in json.load(f)}, {"02F04800"})


class ControlNpcGateTests(unittest.TestCase):
    """A converted actor in the vanilla control cell is judged against the vanilla actor's control there."""
    def setUp(self):
        self.base = tq.npc_test(0, dict(N0_PLAN, label="N0_base", npc="002B211C", method="none"))
        self.ctrl = tq.npc_test(1, dict(N0_PLAN, label="N0_ptr", npc="002B211C", method="ptr_player", control=True))
        self.raider = tq.npc_test(2, dict(N0_PLAN, label="N2a_ptr", npc="02F04800", method="ptr_player",
                                          control_npc="002B211C"))
        self.n0 = tempfile.mkdtemp()
        with open(os.path.join(self.n0, "queue.json"), "w") as f:
            json.dump({"tests": [self.base, self.ctrl]}, f)

    def n0_done(self, base, ctrl):
        with open(os.path.join(self.n0, "state.json"), "w") as f:
            json.dump({"done": {self.base["id"]: {"verdict": base, "class": "X"},
                                self.ctrl["id"]: {"verdict": ctrl, "class": "X"}}}, f)

    def gate(self, test=None):
        d = tempfile.mkdtemp()
        q = {"tests": [test or self.raider], "control_queue": self.n0}
        with open(os.path.join(d, "queue.json"), "w") as f:
            json.dump(q, f)
        return tq.control_gate(d, q, test or self.raider, "FAIL", "NONAV", "x")

    def test_the_vanilla_actors_control_and_baseline_gate_the_converted_one(self):
        self.n0_done("PASS", "PASS")
        v, c, d = self.gate()
        self.assertEqual((v, c), ("FAIL", "NONAV"))
        self.assertIn("control 0001_npc_nav_N0_ptr and baseline 0000_npc_nav_N0_base passed", d)
        self.n0_done("PASS", "FAIL")
        self.assertEqual(self.gate()[1], "CONTROL")
        self.n0_done("FAIL", "PASS")                                       # the citizen came on its own
        self.assertEqual(self.gate()[1], "CONTROL")

    def test_without_control_npc_the_converted_actor_has_no_control(self):
        self.n0_done("PASS", "PASS")
        own = dict(self.raider)
        own.pop("control_npc")
        self.assertEqual(self.gate(own)[1], "CONTROL")

    def test_control_npc_is_validated(self):
        for bad in ({"control_npc": "citizen"}, {"control_npc": "002B211C", "control": True},
                    {"control_npc": "002B211C", "method": "none"}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                tq.npc_test(0, {**N0_PLAN, "label": "x", "npc": "02F04800", "method": "ptr_player", **bad})
        self.assertEqual(tq.npc_test(0, dict(N0_PLAN, npc="02F04800", control_npc="002b211c"))["control_npc"], "002B211C")


class PluginOnlyInstallTests(unittest.TestCase):
    def test_pack_without_a_data_tree_installs_the_plugin_and_no_archive(self):
        root = tempfile.mkdtemp()
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
