"""Cross-plugin FormID resolution, cast-type, and EditorID uniqueness tests (`1c`)."""

from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core.cross_plugin_check import (  # noqa: E402
    ROUTE_LOOT_JSON_REL,
    VmadPropBinding,
    build_writer_catalog,
    parse_cs_vmad_bindings,
    parse_psc_declared_properties,
    parse_psc_form_refs,
    validate_native_core_value_refs,
    validate_psc_form_refs,
    validate_route_loot_refs,
    validate_staged_esms,
    validate_vault_pistol_sync,
    validate_vmad_bindings,
)
from fo4sf.planet.esm import PluginWriter, Record, zbytes  # noqa: E402

# Probe-only / spike scripts that target throwaway probe `.esm`s rather than bundle plugins
PROBE_SCRIPT_DIRS = frozenset({"bridge", "combined_probes", "planet", "questprobe"})
PROBE_SCRIPT_FILES = frozenset({
    "FO4SF_MarkerProbeQuest.psc",
    "FO4SF_AnimConsoleProbe.psc",
    "FO4SF_AnimDoorProbe.psc",
})


def _collect_repo_psc_props() -> tuple[list, dict[str, dict[str, str]]]:
    all_refs = []
    psc_props_by_script: dict[str, dict[str, str]] = {}
    scripts_root = os.path.join(ROOT, "scripts")
    for dp, dirs, files in os.walk(scripts_root):
        dirs[:] = [d for d in sorted(dirs) if d not in PROBE_SCRIPT_DIRS]
        for fn in sorted(files):
            if not fn.endswith(".psc") or fn in PROBE_SCRIPT_FILES:
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            with open(full, encoding="utf-8") as handle:
                psc_text = handle.read()
            all_refs.extend(parse_psc_form_refs(rel, psc_text))
            sname, sprops = parse_psc_declared_properties(psc_text)
            if sname:
                psc_props_by_script[sname.lower()] = sprops
    return all_refs, psc_props_by_script


def _pack_wstr(s: str) -> bytes:
    raw = s.encode("cp1252")
    return struct.pack("<H", len(raw)) + raw


def _pack_vmad_single_obj(script_name: str, prop_name: str, raw_form_id: int, prop_type: int = 1) -> bytes:
    out = bytearray(struct.pack("<HHH", 6, 2, 1))
    out += _pack_wstr(script_name) + b"\x00" + struct.pack("<H", 1)
    out += _pack_wstr(prop_name) + struct.pack("<BB", prop_type, 1)
    if prop_type == 1:
        out += struct.pack("<HhI", 0, -1, raw_form_id)
    elif prop_type == 3:
        out += struct.pack("<i", int(raw_form_id))
    return bytes(out)


class CrossPluginResolutionTests(unittest.TestCase):
    def test_zero_duplicate_edids_and_all_psc_form_references_resolve(self) -> None:
        catalog, dup_errors = build_writer_catalog(ROOT)
        self.assertEqual(dup_errors, [], "\n".join(dup_errors))
        self.assertIn("FO4SFMission.esm", catalog)
        self.assertIn("FO4SFRouteLoot.esm", catalog)
        self.assertEqual(catalog["FO4SFMission.esm"][0x816], ("QUST", "FO4SF_Codsworth01"))
        self.assertEqual(catalog["FO4SFMission.esm"][0x817], ("QUST", "FO4SF_Sanctuary01"))
        self.assertEqual(catalog["FO4SFMission.esm"][0x97A], ("WEAP", "FO4SF_ConcordRaiderSidearm"))
        self.assertEqual(catalog["FO4SFMission.esm"][0x990], ("SCEN", "FO4SF_PrestonPostScene"))
        self.assertEqual(catalog["FO4SFMission.esm"][0x9C0], ("SCEN", "FO4SF_CodsworthPostScene"))
        self.assertEqual(catalog["FO4SFWorkshop.esm"][0x84B], ("FURN", "FO4SF_Sanctuary_WoodChair"))
        self.assertEqual(catalog["FO4SFWorkshop.esm"][0x84C], ("FURN", "FO4SF_Sanctuary_SleepingCot"))
        self.assertEqual(catalog["FO4SFWorkshop.esm"][0x84D], ("CONT", "FO4SF_Sanctuary_StorageCrate"))
        self.assertEqual(catalog["FO4SFWorkshop.esm"][0x84E], ("COBJ", "FO4SF_COBJ_Sanctuary_WoodChair"))
        self.assertEqual(catalog["FO4SFWorkshop.esm"][0x84F], ("COBJ", "FO4SF_COBJ_Sanctuary_SleepingCot"))
        self.assertEqual(catalog["FO4SFWorkshop.esm"][0x850], ("COBJ", "FO4SF_COBJ_Sanctuary_StorageCrate"))
        self.assertEqual(catalog["FO4SFRouteLoot.esm"][0x800], ("CONT", "FO4SF_Vault111ArmoryCase"))

        all_refs, psc_props_by_script = _collect_repo_psc_props()
        self.assertGreaterEqual(len(all_refs), 20)
        ref_errors = validate_psc_form_refs(catalog, all_refs)
        self.assertEqual(ref_errors, [], "\n".join(ref_errors))

        rl_errors = validate_route_loot_refs(catalog, os.path.join(ROOT, ROUTE_LOOT_JSON_REL))
        self.assertEqual(rl_errors, [], "\n".join(rl_errors))

        all_bindings = []
        dotnet_dir = os.path.join(ROOT, "dotnet")
        for entry in sorted(os.listdir(dotnet_dir)):
            if entry.endswith("Probe"):
                continue
            prog = os.path.join(dotnet_dir, entry, "Program.cs")
            if not os.path.isfile(prog):
                continue
            rel_cs = os.path.relpath(prog, ROOT).replace("\\", "/")
            with open(prog, encoding="utf-8") as handle:
                all_bindings.extend(parse_cs_vmad_bindings(rel_cs, handle.read()))

        self.assertGreater(len(all_bindings), 0)
        mission_bindings = [b for b in all_bindings if "Mission" in b.cs_rel]
        self.assertGreaterEqual(len(mission_bindings), 5)
        vmad_errors = validate_vmad_bindings(catalog, psc_props_by_script, all_bindings)
        self.assertEqual(vmad_errors, [], "\n".join(vmad_errors))

        pistol_errors = validate_vault_pistol_sync(all_bindings, os.path.join(ROOT, ROUTE_LOOT_JSON_REL))
        self.assertEqual(pistol_errors, [], "\n".join(pistol_errors))

        # Negative B5 check: mismatched VaultPistolBase binding vs route_loot_ids.json must fail
        drifted_bindings = [
            VmadPropBinding(b.cs_rel, b.script_name, b.prop_name, "Starfield.esm", 0x2773C8)
            if (b.script_name == "FO4SF_NewGameQuest" and b.prop_name == "VaultPistolBase")
            else b
            for b in all_bindings
        ]
        drift_errs = validate_vault_pistol_sync(drifted_bindings, os.path.join(ROOT, ROUTE_LOOT_JSON_REL))
        self.assertTrue(drift_errs)
        self.assertIn("!= route_loot_ids.json vault111.pistol_id", "\n".join(drift_errs))

        native_errors = validate_native_core_value_refs(ROOT, catalog)
        self.assertEqual(native_errors, [], "\n".join(native_errors))

    def test_binary_stage_esm_validator_catches_edid_dup_bad_core_ref_and_vmad_mismatch(self) -> None:
        catalog, _ = build_writer_catalog(ROOT)
        _refs, psc_props_by_script = _collect_repo_psc_props()

        with tempfile.TemporaryDirectory() as td:
            # Valid synthetic FO4SFRouteLoot.esm + FO4SFMission.esm binary stage check
            rl_w = PluginWriter(["Starfield.esm", "FO4SFCoreValues.esm"])
            rl_w.add(
                Record(
                    b"CONT",
                    rl_w.own(0x800),
                    [
                        (b"EDID", zbytes("FO4SF_Vault111ArmoryCase")),
                        (b"CNTO", struct.pack("<Ii", 0x01000851, 2)),  # FO4SFCoreValues.esm:0x000851 (FO4SF_Stimpak)
                    ],
                )
            )
            rl_path = os.path.join(td, "FO4SFRouteLoot.esm")
            rl_w.write(rl_path)

            ms_w = PluginWriter(["Starfield.esm", "FO4TerrainCore.esm", "FO4ActorRaider.esm"])
            ms_w.add(
                Record(
                    b"QUST",
                    ms_w.own(0x817),
                    [
                        (b"EDID", zbytes("FO4SF_Sanctuary01")),
                        (b"VMAD", _pack_vmad_single_obj("FO4SF_Sanctuary01Quest", "XMarkerBase", 0x0000003B)),
                    ],
                )
            )
            ms_path = os.path.join(td, "FO4SFMission.esm")
            ms_w.write(ms_path)

            self.assertEqual(validate_staged_esms([rl_path, ms_path], catalog, psc_props_by_script), [])

            # Negative 1: duplicate EditorID colliding with FO4SFCoreValues.esm + unresolved CoreValues CNTO FormID
            bad_rl = PluginWriter(["Starfield.esm", "FO4SFCoreValues.esm"])
            bad_rl.add(
                Record(
                    b"CONT",
                    bad_rl.own(0x800),
                    [
                        (b"EDID", zbytes("FO4SF_GameMode")),  # owned by FO4SFCoreValues.esm!
                        (b"CNTO", struct.pack("<Ii", 0x010009FF, 1)),  # missing in FO4SFCoreValues.esm!
                    ],
                )
            )
            bad_rl_path = os.path.join(td, "FO4SFBadLoot.esm")
            bad_rl.write(bad_rl_path)

            # Negative 2: VMAD property name or type mismatch on FO4SF_HardcoreQuest
            bad_hc = PluginWriter(["Starfield.esm", "FO4SFCoreValues.esm"])
            bad_hc.add(
                Record(
                    b"QUST",
                    bad_hc.own(0x830),
                    [
                        (b"EDID", zbytes("FO4SF_HardcoreQuest")),
                        (b"VMAD", _pack_vmad_single_obj("FO4SF_HardcoreQuest", "SurvivalStartGlobal", 1, prop_type=3)),
                    ],
                )
            )
            bad_hc_path = os.path.join(td, "FO4SFHardcore.esm")
            bad_hc.write(bad_hc_path)

            errs = validate_staged_esms([bad_rl_path, bad_hc_path], catalog, psc_props_by_script)
            joined = "\n".join(errs)
            self.assertIn("Binary stage duplicate EditorID across plugins", joined)
            self.assertIn("FO4SF_GameMode", joined)
            self.assertIn("unresolved cross-plugin ref FO4SFCoreValues.esm:0x0009FF", joined)
            self.assertIn("FO4SF_HardcoreQuest.SurvivalStartGlobal VMAD type 3 != .psc GlobalVariable", joined)

    @unittest.skipUnless(os.environ.get("FO4SF_PHASE2_STAGES_DIR"), "FO4SF_PHASE2_STAGES_DIR not set")
    def test_phase2_staged_binary_esms_pass_cross_plugin_and_vmad_parity(self) -> None:
        stages_root = os.environ["FO4SF_PHASE2_STAGES_DIR"]
        stage_names = (
            "00-core-values-r2",
            "02b-mission",
            "03-newgame-r2",
            "04-mapmarkers-r2",
            "05-hardcore-r2",
            "08-progression-r2",
            "17-route-loot",
        )
        esm_paths: list[str] = []
        for sname in stage_names:
            sdir = os.path.join(stages_root, sname)
            self.assertTrue(os.path.isdir(sdir), f"missing stage folder: {sname}")
            for fn in sorted(os.listdir(sdir)):
                if fn.lower().endswith(".esm"):
                    esm_paths.append(os.path.join(sdir, fn))
        self.assertGreaterEqual(len(esm_paths), 7)
        catalog, dup_errors = build_writer_catalog(ROOT)
        self.assertEqual(dup_errors, [])
        _refs, psc_props_by_script = _collect_repo_psc_props()
        stage_errors = validate_staged_esms(esm_paths, catalog, psc_props_by_script)
        self.assertEqual(stage_errors, [], "\n".join(stage_errors))

    def test_r13_native_checker_rejects_missing_wrong_type_and_unregistered_core_lookups(self) -> None:
        catalog, _ = build_writer_catalog(ROOT)
        main_rel = "sfse/FO4SFPipboyMenu/src/main.cpp"
        with open(os.path.join(ROOT, *main_rel.split("/")), encoding="utf-8") as handle:
            main_txt = handle.read()

        # 1. Missing 0x000865 in FO4SFCoreValues.esm (the exact pre-A6 bug!) must fail
        cat_without_865 = {k: dict(v) for k, v in catalog.items()}
        cat_without_865["FO4SFCoreValues.esm"].pop(0x000865, None)
        errs_missing = validate_native_core_value_refs(ROOT, cat_without_865)
        self.assertTrue(errs_missing)
        self.assertIn("0x000865", "\n".join(errs_missing))

        # 2. Wrong RTTI type (reading GLOB 0x865 as ActorValueInfo@@) must fail
        wrong_rtti_cpp = main_txt.replace(
            'KitFileForm("FO4SFCoreValues.esm", kCorePipboyAcquiredId, "TESGlobal@@", detail)',
            'KitFileForm("FO4SFCoreValues.esm", kCorePipboyAcquiredId, "ActorValueInfo@@", detail)',
        )
        errs_rtti = validate_native_core_value_refs(ROOT, catalog, cpp_overrides={main_rel: wrong_rtti_cpp})
        self.assertTrue(errs_rtti)
        self.assertIn("incompatible with RTTI ActorValueInfo@@", "\n".join(errs_rtti))

        # 3. Unregistered FO4SFCoreValues.esm lookup in C++ must fail until added to NATIVE_CORE_VALUE_SPECS
        extra_cpp = main_txt + '\nvoid _TestUnregistered() { std::string d; KitFileForm("FO4SFCoreValues.esm", 0x860, "TESGlobal@@", d); }\n'
        errs_unreg = validate_native_core_value_refs(ROOT, catalog, cpp_overrides={main_rel: extra_cpp})
        self.assertTrue(errs_unreg)
        self.assertIn("missing from NATIVE_CORE_VALUE_SPECS", "\n".join(errs_unreg))

    def test_checker_catches_all_three_cd03411a_bugs_and_duplicate_edids(self) -> None:
        """Prove `1c` fails on `cd03411a`'s 3 silent wrong reads (`1b`) and duplicate EditorIDs (`1a`)."""
        # Reconstruct cd03411a writer catalog snapshot where NewGame, Progression, ListDialogue, and Reputation collided
        cd03411a_catalog = {
            "FO4SFNewGame.esm": {
                0x800: ("QUST", "FO4SF_NewGame"),
                0x810: ("AVIF", "FO4SF_Special_Strength"),
                0x811: ("AVIF", "FO4SF_Special_Perception"),
            },
            "FO4SFProgression.esm": {
                0x800: ("AVIF", "FO4SF_Special_Strength"),
                0x813: ("AVIF", "FO4SF_Skill_Guns"),
                0x818: ("AVIF", "FO4SF_Skill_Science"),
                0x81A: ("AVIF", "FO4SF_Skill_Speech"),
                0x820: ("PERK", "FO4SF_BG_VaultDweller"),
                0x836: ("PERK", "FO4SF_Trait_GoodNatured"),
            },
            "FO4SFListDialogue.esm": {
                0x800: ("AVIF", "FO4SF_Skill_Speech"),
                0x801: ("AVIF", "FO4SF_Skill_Science"),
                0x802: ("PERK", "FO4SF_BG_VaultDweller"),
                0x803: ("PERK", "FO4SF_Trait_GoodNatured"),
            },
            "FO4SFReputation.esm": {
                0x800: ("QUST", "FO4SF_ReputationQuest"),
                0x801: ("AVIF", "FO4SF_RepKarma"),
            },
        }

        # 1. Duplicate EditorID check must flag SPECIAL + Speech/Science/BG/Trait collisions
        seen: dict[str, list[str]] = {}
        for plg, recs in cd03411a_catalog.items():
            for _, (_, edid) in recs.items():
                seen.setdefault(edid.lower(), []).append(plg)
        dups = {ed: plgs for ed, plgs in seen.items() if len(set(plgs)) > 1}
        self.assertIn("fo4sf_special_strength", dups)
        self.assertIn("fo4sf_skill_speech", dups)
        self.assertIn("fo4sf_skill_science", dups)
        self.assertIn("fo4sf_bg_vaultdweller", dups)
        self.assertIn("fo4sf_trait_goodnatured", dups)

        # 2. Exact cd03411a Papyrus snippets for the 3 silent wrong reads in 1b:
        combat_cd03411a = """
Scriptname FO4SF_CombatQuest extends Quest
float Function ReadPlayerPerception()
    GlobalVariable g = Game.GetFormFromFile(0x000811, "FO4SFNewGame.esm") as GlobalVariable
    return 6.0
EndFunction
float Function ReadPlayerGunsSkill()
    ActorValue gunsAv = Game.GetFormFromFile(0x000800, "FO4SFProgression.esm") as ActorValue
    return 25.0
EndFunction
"""
        companions_cd03411a = """
Scriptname FO4SF_CompanionsQuest extends Quest
string RepPlugin = "FO4SFReputation.esm"
int RepGoodwillGlobId = 0x000801
bool Function HasFactionGoodwill(Actor candidate)
    GlobalVariable gw = Game.GetFormFromFile(RepGoodwillGlobId, RepPlugin) as GlobalVariable
    return gw != None
EndFunction
"""
        refs = (
            parse_psc_form_refs("scripts/combat/FO4SF_CombatQuest.psc", combat_cd03411a)
            + parse_psc_form_refs("scripts/companions/FO4SF_CompanionsQuest.psc", companions_cd03411a)
        )
        self.assertEqual(len(refs), 3)
        errors = validate_psc_form_refs(cd03411a_catalog, refs)
        self.assertEqual(len(errors), 3, "\n".join(errors))
        joined = "\n".join(errors)
        self.assertIn("FO4SFNewGame.esm:0x000811 (FO4SF_Special_Perception) is AVIF, cannot cast as GlobalVariable", joined)
        self.assertIn("expected 'guns' record, but FO4SFProgression.esm:0x000800 is 'FO4SF_Special_Strength'", joined)
        self.assertIn("FO4SFReputation.esm:0x000801 (FO4SF_RepKarma) is AVIF, cannot cast as GlobalVariable", joined)


if __name__ == "__main__":
    unittest.main()
