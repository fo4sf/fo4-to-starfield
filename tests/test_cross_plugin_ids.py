"""Cross-plugin FormID resolution, cast-type, and EditorID uniqueness tests (`1c`)."""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core.cross_plugin_check import (  # noqa: E402
    build_writer_catalog,
    parse_cs_vmad_bindings,
    parse_psc_declared_properties,
    parse_psc_form_refs,
    validate_psc_form_refs,
    validate_vmad_bindings,
)

# Probe-only / spike scripts that target throwaway probe `.esm`s rather than bundle plugins
PROBE_SCRIPT_DIRS = frozenset({"bridge", "combined_probes", "planet", "questprobe"})
PROBE_SCRIPT_FILES = frozenset({
    "FO4SF_MarkerProbeQuest.psc",
    "FO4SF_AnimConsoleProbe.psc",
    "FO4SF_AnimDoorProbe.psc",
})


class CrossPluginResolutionTests(unittest.TestCase):
    def test_zero_duplicate_edids_and_all_psc_form_references_resolve(self) -> None:
        catalog, dup_errors = build_writer_catalog(ROOT)
        self.assertEqual(dup_errors, [], "\n".join(dup_errors))

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

        self.assertGreaterEqual(len(all_refs), 20)
        ref_errors = validate_psc_form_refs(catalog, all_refs)
        self.assertEqual(ref_errors, [], "\n".join(ref_errors))

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
        vmad_errors = validate_vmad_bindings(catalog, psc_props_by_script, all_bindings)
        self.assertEqual(vmad_errors, [], "\n".join(vmad_errors))

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
