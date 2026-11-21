"""Unit tests for the Fallout 4 -> Starfield Papyrus bridge shims, AST rewriter, and compile_census --with-shims.

Uses synthetic invented Papyrus snippets only (zero game source text or assets).
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fo4sf.papyrus.shim_rewriter import rewrite_source, rewrite_tree  # noqa: E402

spec = importlib.util.spec_from_file_location("compile_census", ROOT / "scripts" / "papyrus" / "compile_census.py")
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)


EXPECTED_SHIM_FILES = {
    "FO4SF_NativeBridge.psc",
    "FO4SF_Shim_ActorAI.psc",
    "FO4SF_Shim_AudioWeather.psc",
    "FO4SF_Shim_ObjectRef.psc",
    "FO4SF_Shim_PlayerUI.psc",
    "FO4SF_Shim_PowerArmor.psc",
    "FO4SF_Shim_QuestScene.psc",
    "FO4SF_Shim_SurvivalRad.psc",
    "FO4SF_Shim_Workshop.psc",
    "Component.psc",
    "EncounterZone.psc",
    "Holotape.psc",
    "OutputModel.psc",
    "Sound.psc",
    "SoundCategory.psc",
    "SoundCategorySnapshot.psc",
}


class ShimInventoryTests(unittest.TestCase):
    def test_all_expected_shim_files_exist_and_only_native_bridge_is_native(self):
        shim_dir = ROOT / "scripts" / "papyrus" / "shims"
        found = {p.name for p in shim_dir.glob("*.psc")}
        self.assertEqual(found, EXPECTED_SHIM_FILES)
        for p in sorted(shim_dir.glob("*.psc")):
            if p.name == "FO4SF_NativeBridge.psc":
                self.assertTrue(cc.is_native(p), "FO4SF_NativeBridge.psc must declare Native")
                txt = p.read_text(encoding="utf-8")
                for fn in (
                    "Dismember",
                    "IsDismembered",
                    "GetLinkedRefChildren",
                    "ShowPipboyPlugin",
                    "ResetSpeechChallenges",
                ):
                    self.assertIn(f"Function {fn}(", txt)
            else:
                self.assertFalse(cc.is_native(p), f"{p.name} must be pure Papyrus (non-Native)")


class ShimRewriterTests(unittest.TestCase):
    def test_global_and_chained_member_rewrites(self):
        src = (
            "Scriptname SyntheticBridgeDemo extends Quest\n"
            "Function Run(Actor a, Location loc)\n"
            "    if Utility.IsInMenuMode()\n"
            "        Utility.WaitMenuMode(0.5)\n"
            "    endif\n"
            "    a.GetActorBase().SetInvulnerable(true)\n"
            "    loc.SetCleared(true)\n"
            "    a.Dismember(\"LeftArm1\", false, false, false)\n"
            "    Self.ResetSpeechChallenges()\n"
            "EndFunction\n"
        )
        out = rewrite_source(src)
        self.assertIn("FO4SF_Shim_PlayerUI.IsInMenuMode()", out)
        self.assertIn("FO4SF_Shim_PlayerUI.WaitMenuMode(0.5)", out)
        self.assertIn("FO4SF_Shim_ActorAI.SetInvulnerable(FO4SF_Shim_ActorAI.GetActorBase(a), true)", out)
        self.assertIn("FO4SF_Shim_QuestScene.SetCleared(loc, true)", out)
        self.assertIn("FO4SF_NativeBridge.Dismember(a, \"LeftArm1\", false, false, false)", out)
        self.assertIn("FO4SF_NativeBridge.ResetSpeechChallenges(Self)", out)

    def test_companion_actor_wrappers_vs_followers_script_methods(self):
        src = (
            "Scriptname SyntheticCompanionDemo extends Quest\n"
            "FollowersScript Property Followers Auto\n"
            "Function Test(Actor buddy)\n"
            "    buddy.DisallowCompanion(SuppressDismissMessage = true)\n"
            "    buddy.SetAvailableToBeCompanion()\n"
            "    Followers.DisallowCompanion(buddy, true)\n"
            "    FollowersScript.GetScript().SetCompanion(buddy, true, true)\n"
            "EndFunction\n"
        )
        out = rewrite_source(src)
        self.assertIn("FO4SF_Shim_ActorAI.DisallowCompanion(buddy, SuppressDismissMessage = true)", out)
        self.assertIn("FO4SF_Shim_ActorAI.SetAvailableToBeCompanion(buddy)", out)
        self.assertIn("Followers.DisallowCompanion(buddy, true)", out)
        self.assertIn("FollowersScript.GetScript().SetCompanion(buddy, true, true)", out)

    def test_self_only_external_relay_preserves_self_calls(self):
        src = (
            "Scriptname SyntheticSelfOnlyDemo extends Quest\n"
            "CustomEvent AffinityEvent\n"
            "Function Ping(Quest other)\n"
            "    Self.GotoState(\"Ready\")\n"
            "    StartTimer(1.0, 10)\n"
            "    other.GotoState(\"Busy\")\n"
            "    other.StartTimerGameTime(2.0, 20)\n"
            "    other.RegisterForCustomEvent(Self, \"PingEvent\")\n"
            "    other.SendCustomEvent(AffinityEvent)\n"
            "EndFunction\n"
        )
        out = rewrite_source(src)
        self.assertIn("CustomEvent FO4SF_AffinityEvent", out)
        self.assertIn("Self.GotoState(\"Ready\")", out)
        self.assertIn("StartTimer(1.0, 10)", out)
        self.assertIn("FO4SF_Shim_QuestScene.RelayGotoState(other, \"Busy\")", out)
        self.assertIn("FO4SF_Shim_QuestScene.RelayStartTimerGameTime(other, 2.0, 20)", out)
        self.assertIn("FO4SF_Shim_QuestScene.RelayRegisterForCustomEvent(other, Self, \"PingEvent\")", out)
        self.assertIn("FO4SF_Shim_QuestScene.RelaySendCustomEvent(other, \"FO4SF_AffinityEvent\")", out)

    def test_event_widening_remote_renames_and_note_identifier(self):
        src = (
            "Scriptname SyntheticEventDemo extends ActiveMagicEffect\n"
            "Event OnEffectStart(Actor akTarget, Actor akCaster)\n"
            "    int note = 1\n"
            "EndEvent\n"
            "Event OnDeath(Actor akKiller)\n"
            "    Actor who = akKiller\n"
            "EndEvent\n"
            "Event Location.OnLocationCleared(Location akSender)\n"
            "EndEvent\n"
            "Function Sub(Location loc, Actor a, Actor b)\n"
            "    Self.OnEffectStart(a, b)\n"
            "    RegisterForRemoteEvent(loc, \"OnLocationCleared\")\n"
            "    Self.RegisterForLooksMenuEvent()\n"
            "EndFunction\n"
        )
        out = rewrite_source(src)
        self.assertIn(
            "Event OnEffectStart(ObjectReference __fo4sf_target, Actor akCaster, MagicEffect __fo4sf_effect, float __fo4sf_mag, float __fo4sf_dur)",
            out,
        )
        self.assertNotIn("__fo4sf_effect = None", out)
        self.assertIn("Self.OnEffectStart(a, b, None, 0.0, 0.0)", out)
        self.assertIn("Actor akTarget = __fo4sf_target as Actor", out)
        self.assertIn("int fo4sf_note = 1", out)
        self.assertIn("Event OnDeath(ObjectReference __fo4sf_akKiller)", out)
        self.assertIn("Actor akKiller = __fo4sf_akKiller as Actor", out)
        self.assertIn("Event Location.OnLocationExplored(Location akSender)", out)
        self.assertIn("RegisterForRemoteEvent(loc, \"OnLocationExplored\")", out)
        self.assertIn("Self.RegisterForMenuOpenCloseEvent(\"ChargenMenu\")", out)


class CensusWithShimsTests(unittest.TestCase):
    def test_with_shims_and_non_identical_only_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            fo4, sf, out = t / "fo4", t / "sf", t / "out"
            fo4.mkdir()
            sf.mkdir()
            (sf / cc.DEFAULT_FLAGS).write_text("", encoding="utf-8")
            # Native FO4 Sound.psc that must NOT leak into shimmed_fo4 or unshimmed_fo4
            (fo4 / "Sound.psc").write_text("Scriptname Sound extends Form Native\n", encoding="utf-8")
            # Clean identical script (should be skipped by non_identical_only)
            (fo4 / "CleanQuest.psc").write_text(
                "Scriptname CleanQuest extends Quest\nFunction Ok()\nEndFunction\n", encoding="utf-8"
            )
            # Non-identical logic script (calls GetActorBase)
            (fo4 / "NeedsShimLogic.psc").write_text(
                "Scriptname NeedsShimLogic extends Quest\n"
                "Function Check(Actor a)\n    ActorBase b = a.GetActorBase()\nEndFunction\n",
                encoding="utf-8",
            )
            # Non-identical scene script (references deleted Sound type)
            (fo4 / "TIF__0001.psc").write_text(
                "Scriptname TIF__0001 extends TopicInfo\nSound Property Beep Auto\n",
                encoding="utf-8",
            )
            compiler = t / "fake_compiler.exe"
            compiler.write_text("", encoding="utf-8")

            def fake_runner(cmd, timeout, cwd=None):
                name = cmd[1]
                imp = cmd[3].removeprefix("-i=")
                # Unshimmed pass uses empty_shim: NeedsShimLogic & TIF__0001 fail; CleanQuest succeeds
                if "empty_shim" in imp:
                    if name in ("NeedsShimLogic", "TIF__0001"):
                        return 1, f"{name}.psc(2,5): unshimmed error is not a function or does not exist\n", ""
                    return 0, "Compilation succeeded.\n", ""
                # Shimmed pass: verify NeedsShimLogic was rewritten in shimmed_fo4
                if name == "NeedsShimLogic":
                    rewritten = (out / "shimmed_fo4" / "NeedsShimLogic.psc").read_text(encoding="utf-8")
                    if "FO4SF_Shim_ActorAI.GetActorBase" not in rewritten:
                        return 1, "NeedsShimLogic.psc(3,5): GetActorBase is not a function or does not exist\n", ""
                return 0, "Compilation succeeded.\n", ""

            census = cc.run_census(
                fo4, sf, None, compiler, "", 0, 1, out,
                runner=fake_runner, with_shims=True, non_identical_only=True, jobs=2,
            )
            self.assertFalse((out / "shimmed_fo4" / "Sound.psc").exists())
            self.assertEqual(census["bridge"]["shims_total"], len(EXPECTED_SHIM_FILES))
            self.assertEqual(census["bridge"]["shims_compiled"], len(EXPECTED_SHIM_FILES))
            self.assertEqual(census["bridge"]["non_identical_baseline_failed"], 2)
            self.assertEqual(census["total"], 2)
            self.assertEqual(census["compiled"], 2)
            self.assertEqual(census["groups"]["logic"]["compiled"], 1)
            self.assertEqual(census["groups"]["scene"]["compiled"], 1)
            table = cc.format_table(census)
            self.assertIn("Bridge shims: 16/16 compiled clean", table)
            self.assertIn("non-identical baseline failed: 2", table)

    def test_rewrite_tree_counts_modified_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            src, dst = t / "src", t / "dst"
            src.mkdir()
            (src / "Same.psc").write_text("Scriptname Same extends Quest\n", encoding="utf-8")
            (src / "Changed.psc").write_text(
                "Scriptname Changed extends Quest\nFunction F()\n    Game.ShowSPECIALMenu()\nEndFunction\n",
                encoding="utf-8",
            )
            modified = rewrite_tree(src, dst)
            self.assertEqual(modified, 1)
            self.assertIn("FO4SF_Shim_PlayerUI.ShowSPECIALMenu()", (dst / "Changed.psc").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
