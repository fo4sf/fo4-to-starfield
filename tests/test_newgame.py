"""The Fallout 4 new game (docs/newgame/vault111-start.md): the contract between dotnet/NewGame (the plugin),
FO4SF_NewGameQuest.psc / FO4SF_NewGameLooks.psc / FO4SF_NewGameSpecial.psc / FO4SF_NewGameVersion.psc (the scripts) and
make_newgame.py (precheck, staging, verify, fold, the log reader). Synthetic only; the C# writer's own self-test runs
when a dotnet SDK is on PATH."""
import io
import unittest.mock
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "newgame"))
from fo4sf.core.core_values import CORE_VALUES_PLUGIN, core_form_id  # noqa: E402
import make_newgame as ng  # noqa: E402

PSC = os.path.join(ROOT, "scripts", "newgame", "FO4SF_NewGameQuest.psc")
LOOKS = os.path.join(ROOT, "scripts", "newgame", "FO4SF_NewGameLooks.psc")
SPECIAL = os.path.join(ROOT, "scripts", "newgame", "FO4SF_NewGameSpecial.psc")
VERSION = os.path.join(ROOT, "scripts", "newgame", "FO4SF_NewGameVersion.psc")
CS = os.path.join(ROOT, "dotnet", "NewGame", "Program.cs")
RECORDS = os.path.join(ROOT, "dotnet", "NewGame", "Records.cs")
DOC = os.path.join(ROOT, "docs", "newgame", "vault111-start.md")
# the stage options as argparse hands them to tool_options / the plan: every build switch, at its default
DEFAULTS = dict(hold=None, mq101debug=None, no_mq101debug=False, debug_after_hold=None, looks=True, race_menu_mode=None, special=True,
                version=True, build_version=None, keep_inventory=False, clear_inventory=False, vault_suit=None, require_persistent_anchor=False,
                allow_temporary_anchor=False, no_o2_fill=False, fade_hold=False, no_fade_hold=False, start_choice_backdrop=None, warfare_starts=None, start_places=None)


def namespace(**kw):
    return ng.main.__globals__["argparse"].Namespace(**{**DEFAULTS, **kw})


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def written_properties(cs):
    """(quest, looks, special, version): the property names Program.cs writes to each script. The quest's are the
    Properties() table plus its three object properties; the looks script's are LooksProperties() plus StartMessage;
    the SPECIAL script's are SpecialProperties() plus Special, TerminalMessage and SpecialMessage; the version
    script's (on the player alias) is BuildVersion alone."""
    def values(table):
        body = cs[cs.index(table):]
        return set(re.findall(r'\("(\w+)",', body[:body.index("};")]))

    def objects(entry, end):
        body = cs[cs.index(entry):]
        body = body[:body.index(end)]
        return set(re.findall(r'Obj\("(\w+)"', body)) | set(re.findall(r'ListProperty \{ Name = "(\w+)"', body))
    quest = values("public static List<(string Name, object Value)> Properties")
    looks = values("LooksProperties(Options o)")
    special = values("SpecialProperties(JsonElement pts, Places p)")
    looks |= objects("var looks = new SF.ScriptEntry", "quest.VirtualMachineAdapter.Scripts.Add(looks)")
    special |= objects("var special = new SF.ScriptEntry", "quest.VirtualMachineAdapter.Scripts.Add(special)")
    quest |= objects("var script = new SF.ScriptEntry", "quest.VirtualMachineAdapter = new SF.QuestAdapter")
    version = objects("var version = new SF.ScriptEntry", "var bound = new SF.QuestFragmentAlias")
    return quest, looks, special, version


class ContractTests(unittest.TestCase):
    def test_lift_and_s13_inventory_o2_switches_remain_independent(self):
        """Combining the S3/S13 branches must not let the lift flag change inventory or O2 policy."""
        for lift in (False, True):
            for keep in (False, True):
                for no_o2 in (False, True):
                    with self.subTest(lift=lift, keep=keep, no_o2=no_o2):
                        args = namespace(exit_lift="private-lift-stage" if lift else None,
                                         keep_inventory=keep, no_o2_fill=no_o2)
                        options = ng.tool_options(args)
                        self.assertEqual("--animated-exit-lift" in options, lift)
                        self.assertEqual("--keep-inventory" in options, keep)
                        self.assertEqual("--no-o2-fill" in options, no_o2)
                        self.assertEqual(ng.clear_inventory_option(args), not keep)
                        self.assertEqual(ng.o2_fill_option(args), not keep and not no_o2)

    def test_no_variable_shares_a_property_name(self):
        """Papyrus names are case-insensitive: a script variable or local named like a property fails to compile
        (newgame_v4 on the PC, 21 Oct: CenterTicks and centerTicks)."""
        decl = re.compile(r"^\s*(?!Event|Function|EndFunction|EndEvent|return|if|elseif|while|Scriptname)"
                          r"[A-Za-z_]\w*(?:\[\])?\s+([A-Za-z_]\w*)\s*(?:=|$)")
        for d in ("newgame", "questprobe"):
            folder = os.path.join(ROOT, "scripts", d)
            for name in sorted(n for n in os.listdir(folder) if n.endswith(".psc")):
                text = read(os.path.join(folder, name))
                props = {m.lower() for m in re.findall(r"\bProperty\s+(\w+)", text)}
                names = [m.group(1) for line in text.splitlines() if "Property" not in line
                         for m in [decl.match(line.split(";")[0])] if m]
                with self.subTest(script=name):
                    self.assertEqual([n for n in names if n.lower() in props], [])

    def test_plugin_names_match_the_resolver(self):
        """The writer refuses references not owned by the plugin the script resolves them in (Codex review on #393);
        those names must be the script's own defaults."""
        cs, psc = read(CS), read(PSC)
        for prop, const in (("VaultPlugin", "PortPlugin"), ("CorePlugin", "CorePluginFile")):
            want = re.search(rf'string Property {prop} = "([^"]+)"', psc).group(1)
            self.assertIn(f'{const} = "{want}"', cs)

    def test_the_record_reader_is_documented(self):
        """The records verb (Records.cs) answers newgame.md's K and N record questions in one PC run: the doc names
        the exact command, every section's NG id, and the reader's own defaults; the verb is dispatched and the main
        selftest runs the records one."""
        cs, rec, doc = read(CS), read(RECORDS), read(DOC)
        self.assertIn('"records" when args.Length >= 2', cs)
        self.assertIn('NewGameRecords.SelfTest(Path.Combine(dir, "records"))', cs)
        sf_data = re.search(r'DefaultSfData = @"([^"]+)"', rec).group(1)
        self.assertEqual(sf_data, r"D:\SteamLibrary\steamapps\common\Starfield\Data")
        self.assertIn(f"`{sf_data}`", doc)
        self.assertIn("-- records \"<Fallout 4>\\Data\" --out ", doc)
        for section in ("NG-K1", "NG-K2", "NG-K4", "NG-K9", "NG-N4"):
            self.assertIn(f'o.Section("{section} ', rec.replace("$\"", "\""))
            self.assertIn(f"| `{section}` | {section}", doc)
        self.assertIn('o.Section($"anchor: ', rec)
        self.assertIn("| `anchor` |", doc)
        self.assertIn("SustenanceId = 0x2EEA4D", rec)
        self.assertIn("002EEA4D", doc)
        self.assertIn("**unresolved** until that PC run", doc)

    def test_saving_and_hud_restored_with_the_fade_in(self):
        """MQ101's stage 0 turns saving off and hides the HUD; its stop (stage 9000) restores neither (PC read of
        QF_MQ101_00003448.psc, 19 Oct). Our own start (newgame_v11) never runs MQ101, but a run must not depend on that:
        the one fade in (FadeIn, the call Roleplayers' Alternate Start makes once its start cell has loaded) turns both
        back on. It runs once, from the start's wait for the player's 3D or from the timer, whichever sees the 3D first,
        and never before the 3D is in: the start's wait can return without it, and the start fades only if it is in, else
        the timer does once it sees it (29 Oct review on #588: a fade under the loading screen, then never again). The
        timer's comes before it confirms the vault."""
        psc = read(PSC)
        fade = psc[psc.index("Function FadeIn"):psc.index("Function NoteLooksStage20")]
        code = fade[fade.index("    if faded"):]                  # past the doc comment
        self.assertTrue(code.startswith("    if faded\n        return\n    endif\n    faded = true\n"))
        # the pod's heading again while the screen is still dark, for a player the start moved into the vault
        self.assertIn("    if vaultMoves > 0 && StandsInVault(player)\n        player.SetAngle(0.0, 0.0, PodHeading)\n    endif\n", code)
        self.assertLess(code.index("player.SetAngle(0.0, 0.0, PodHeading)"), code.index("Game.FadeOutGame("))
        self.assertLess(code.index("Game.FadeOutGame(False, True, 0.0, 0.1, False)"), code.index("Game.SetInChargen(false, false, false)"))
        self.assertLess(code.index("Game.SetInChargen(false, false, false)"), code.index("Game.SetCharGenHUDMode(0)"))
        self.assertIn('Trace("fade in by=" + by + " loaded=" + player.Is3DLoaded() + " cell=" + player.GetParentCell() + "; saving and HUD on")', code)
        prep_ui = psc[psc.index("Function PrepareStartRoomUi"):psc.index("int Function RunModeChoiceChain")]
        self.assertNotIn("Game.FadeOutGame(True, True, 0.0, 0.1, True)", prep_ui)
        self.assertIn("Game.FadeOutGame(False, True, 0.0, 0.1, False)", prep_ui)
        self.assertIn("Game.SetInChargen(false, false, false)", prep_ui)
        self.assertIn("Game.ShowFirstPersonGeometry(false)", prep_ui)
        self.assertIn("Game.SetCharGenHUDMode(2)", prep_ui)
        self.assertIn('Trace("mode fade lifted by=timeout s=" + (StartLoadTimeout as int))', prep_ui)
        begin = psc[psc.index("Function Begin"):psc.index("Function StandDown")]
        self.assertLess(begin.index("StartTimer(1.0, 1)"), begin.index("player.WaitFor3DLoad()"))
        self.assertLess(begin.index("player.WaitFor3DLoad()"), begin.index('FadeIn("start")'))
        self.assertIn('    player.WaitFor3DLoad()                                   ; latent: returns once the 3D is in, or will not load\n'
                      '    bool ready = player.Is3DLoaded()\n    Trace("3d wait over loaded=" + ready)\n'
                      '    if ready\n        if UsePreworldRoom()\n            PrepareStartRoomUi("start")\n            Game.ShowFirstPersonGeometry(false)\n        else\n            FadeIn("start")', begin)
        zero = psc[psc.index("    if stage == 0\n"):psc.index("    elseif stage == 10")]
        self.assertIn('        if !player.Is3DLoaded()\n', zero)
        self.assertIn('            StartTimer(1.0, 1)                               ; the game is still loading\n'
                      '            return\n        endif\n        if UsePreworldRoom()\n            PrepareStartRoomUi("timer")', zero)
        self.assertLess(zero.index('        if !player.Is3DLoaded()\n'), zero.index('FadeIn("timer")'))
        self.assertLess(zero.index('FadeIn("timer")'), zero.index("if !entered"))
        self.assertEqual(re.findall(r'\bFadeIn\("([^"]+)"\)', psc), ["start", "timer", "mode_story"])
        self.assertEqual(re.findall(r'\bForceFadeIn\("([^"]+)"\)', psc), ["story_landing", "warfare"])
        self.assertIn("FadeOutGame", ng.NATIVES[ng.SCRIPT]["Game"])
        self.assertIn("ShowFirstPersonGeometry", ng.NATIVES[ng.SCRIPT]["Game"])
        self.assertIn("WaitFor3DLoad", ng.NATIVES[ng.SCRIPT]["ObjectReference"])

    def test_the_timers_wait_for_the_3d_writes_a_line(self):
        """Stage 0's timer waits for the player's 3D before anything else (the fade, the vault confirmation, the
        temporary anchor's retries and their bound). A wait that never ends (a move, or a centering, that moved nobody)
        used to write nothing at all, so a log could not tell it from a timer that never ran (29 Oct review on #588):
        every 10th tick of the wait writes what the start did (vault_moves, centered) and where the player is, and the
        log reader keeps the last such line ("waiting_3d")."""
        psc = read(PSC)
        zero = psc[psc.index("    if stage == 0\n"):psc.index("    elseif stage == 10")]
        wait = zero[zero.index("        if !player.Is3DLoaded()\n"):zero.index('FadeIn("timer")')]
        self.assertTrue(wait.startswith("        if !player.Is3DLoaded()\n            if ticks % 10 == 0\n"))
        self.assertIn('                Trace("waiting for the 3d tick=" + ticks + " vault_moves=" + vaultMoves + " centered=" + centered'
                      ' + " cell=" + player.GetParentCell())\n            endif\n            StartTimer(1.0, 1)', wait)
        self.assertLess(wait.index("Trace("), wait.index("return"))
        timer = psc[psc.index("Event OnTimer"):psc.index("bool Function IsNewGame")]
        self.assertLess(timer.index("    ticks += 1\n"), timer.index("    if stage == 0\n"))   # counted before the wait
        # the temporary anchor's bound counts the timer's tries, which wait for the 3D: its docs say so
        center = " ".join(psc[psc.index("bool Function CenterOnVault"):psc.index("Function ResetInventory")].split())
        self.assertIn("Bounded once the player's 3D is in", center)
        self.assertIn('the timer\'s "waiting for the 3d" line every 10 ticks is then the only trace', center)
        self.assertIn("which come only once the player's 3D is in (CenterOnVault)", " ".join(psc.split()))
        line = "[x] FO4SF_NEWGAME rt=12.0 waiting for the 3d tick=10 vault_moves=0 centered=1 cell=None\n"
        self.assertEqual(ng.summarize([line])["waiting_3d"], "tick=10 vault_moves=0 centered=1 cell=None")

    def test_every_mandatory_property_is_written_and_every_written_one_declared(self):
        written, looks_written, special_written, version_written = written_properties(read(CS))
        for psc, written_here in ((PSC, written), (LOOKS, looks_written), (SPECIAL, special_written), (VERSION, version_written)):
            declared = ng.declared_properties(read(psc))
            mandatory = {n for n, m in declared.items() if m}
            self.assertEqual(mandatory - written_here, set(), f"mandatory properties the plugin never fills ({psc})")
            self.assertEqual(written_here - set(declared), set(), f"properties the plugin writes that {psc} lacks")
        self.assertIn("HoldOff", written)
        self.assertIn("TestModeGlobal", written)
        self.assertIn("LooksWait", written)                  # 0 in a --no-looks build, so the quest does not wait
        self.assertEqual(looks_written, {"StartMessage", "RaceMenuMode"})
        self.assertEqual(special_written, {"Special", "TerminalMessage", "SpecialMessage", "SpecialMessagePage2", "TerminalId", "TerminalX", "TerminalY", "TerminalZ"})
        self.assertEqual(version_written, {"BuildVersion"})   # SavedVersion is the script's own, written in game, never by the plugin
        self.assertFalse(ng.declared_properties(read(VERSION))["SavedVersion"])

    def test_the_save_version_check(self):
        """NG-15 / NG-L2: the build's version number is one constant in the writer and Python, written to our own
        constant GLOB (--build-version, --no-version drops the check); the quest's alias 0 is the player (PlayerRef
        00000014), its script records the GLOB when the alias fills and compares it on OnPlayerLoadGame, logging both
        and notifying on a mismatch; it never changes the save otherwise."""
        cs, version, psc = read(CS), read(VERSION), read(PSC)
        self.assertIn(f"DefaultBuildVersion = {ng.DEFAULT_BUILD_VERSION}f", cs)
        self.assertIn('ArgOrNull(a, "--build-version")', cs)
        self.assertIn('a.Contains("--no-version")', cs)
        self.assertIn('VersionGlobEdid = "FO4SF_NewGameVersion", VersionScript = "FO4SF_NewGameVersion"', cs)
        self.assertIn("PlayerRefId = 0x000014, PlayerAlias = 0", cs)
        self.assertIn("MajorFlags = SF.Global.MajorFlag.Constant", cs)
        self.assertIn("ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(new FormKey(SfEsm, PlayerRefId))", cs)
        self.assertIn("quest.VirtualMachineAdapter.Aliases.Add(bound)", cs)
        self.assertIn(f"Scriptname {ng.VERSION} extends ReferenceAlias", version)
        self.assertIn("GlobalVariable Property BuildVersion Auto Const Mandatory", version)
        self.assertIn("float Property SavedVersion = -1.0 Auto", version)
        self.assertIn("Event OnInit()", version)
        self.assertIn("Event OnPlayerLoadGame()", version)
        code = version[version.index("GlobalVariable Property BuildVersion"):]
        self.assertEqual(code.count("SavedVersion = BuildVersion.GetValue()"), 1)
        self.assertIn("if SavedVersion < 0.0", code)         # recorded once, when the alias fills
        self.assertIn('Trace("version saved=" + SavedVersion + " (new game)")', code)
        self.assertIn('Trace("version load saved=" + SavedVersion + " installed=" + installed)', code)
        self.assertIn("if SavedVersion != installed", code)
        self.assertIn('Trace("version mismatch")', code)
        self.assertIn("Debug.Notification(", code)
        self.assertEqual(code.count("Debug.Notification("), 1)   # on the mismatch alone
        self.assertEqual(code.count("Debug.OpenUserLog(LogName)"), 2)   # in OnInit (the quest script's open may not have run yet) and on load (a new game session)
        for forbidden in ("SetStage(", "SetValue(", "MoveTo(", "Stop(", "SetPosition(", "Clear(", "ForceRefTo("):
            self.assertNotIn(forbidden, code)              # the check changes nothing
        self.assertNotIn("Version", psc.split("}", 1)[1])   # the quest script knows nothing of it
        self.assertEqual(ng.OPTIONAL[ng.VERSION], "--no-version")
        self.assertEqual(ng.tool_options(namespace()), [])
        self.assertEqual(ng.build_version_option(namespace()), ng.DEFAULT_BUILD_VERSION)
        self.assertEqual(ng.tool_options(namespace(version=False)), ["--no-version"])
        self.assertIsNone(ng.build_version_option(namespace(version=False)))
        self.assertEqual(ng.tool_options(namespace(build_version=2)), ["--build-version", "2"])
        self.assertEqual(ng.build_version_option(namespace(build_version=2)), 2)

    def test_the_starting_inventory_reset(self):
        """NG-K8: the reset is one default (on, S13 row 2) in the writer and Python; it makes the quest script
        empty the inventory once the player is confirmed in the vault and before stage 10, logging the count (whether
        quest items stay is unverified: Starfield's third parameter is abRespectTargetCapacity, so neither the doc nor
        the line claims it); --vault-suit names the port's ARMO the writer resolves by EditorID (refused with
        --keep-inventory) and the script adds and equips after the reset, logging it. Every native of it is
        prechecked, and the plan records both."""
        cs, psc = read(CS), read(PSC)
        self.assertIn(f"DefaultClearInventory = {str(ng.DEFAULT_CLEAR_INVENTORY).lower()};", cs)
        self.assertTrue(ng.DEFAULT_CLEAR_INVENTORY)
        self.assertIn('a.Contains("--keep-inventory")', cs)
        self.assertIn('ArgOrNull(a, "--vault-suit")', cs)
        self.assertIn("--keep-inventory turns it off", cs)
        self.assertIn('("ClearInventory", o.ClearInventory), ("VaultSuitId", (int)p.VaultSuit)', cs)
        self.assertIn("port.Armors.Where(x => string.Equals(x.EditorID, vaultSuit", cs)
        self.assertIn('Owned(suits[0], port.ModKey, $"the vault suit {vaultSuit}")', cs)
        self.assertIn(f"bool Property ClearInventory = {str(ng.DEFAULT_CLEAR_INVENTORY).lower()} Auto Const", psc)
        self.assertIn("int Property VaultSuitId = 0 Auto Const", psc)
        body = psc[psc.index("Event OnTimer"):]
        enter = body.index("if !entered\n                StartTimer(1.0, 1)")
        self.assertLess(enter, body.index("if ClearInventory\n                ResetInventory(player)"))
        self.assertLess(body.index("ResetInventory(player)"), body.index("AdvanceTo(10)"))
        self.assertNotIn("ResetInventory(", psc[psc.index("Function Begin"):psc.index("Function StandDown")])   # never during the first load
        reset = psc[psc.index("Function ResetInventory"):psc.index("Function InVault")]
        self.assertEqual(reset.count("player.RemoveAllItems("), 1)   # once; the doc comment names the call too
        self.assertIn("player.RemoveAllItems(None, false, false)", reset)   # FO4's arguments
        self.assertIn("whether quest items stay is unverified", reset)
        for text in (psc, cs, read(ng.__file__), read(DOC)):
            self.assertNotIn("quest items kept", text)       # Starfield's third parameter is no quest-item flag
        self.assertIn("int before = player.GetItemCount(None)", reset)
        self.assertIn('Trace("inventory cleared removed=" + (before - after) + " left=" + after)\n', reset)
        self.assertIn("if VaultSuitId > 0", reset)
        self.assertIn("Game.GetFormFromFile(VaultSuitId, VaultPlugin) as Armor", reset)
        self.assertLess(reset.index("player.AddItem(suit, 1, true)"), reset.index("player.EquipItem(suit, false, true)"))
        self.assertIn('Trace("vault suit equipped " + suit + " worn=" + player.IsEquipped(suit))', reset)
        self.assertIn('Trace("vault suit " + VaultPlugin + ":" + VaultSuitId + " does not resolve")', reset)
        for native in ("RemoveAllItems", "GetItemCount", "AddItem"):
            self.assertIn(native, ng.NATIVES[ng.SCRIPT]["ObjectReference"])
        for native in ("EquipItem", "IsEquipped"):
            self.assertIn(native, ng.NATIVES[ng.SCRIPT]["Actor"])
        self.assertNotIn("RemoveAllItems", read(LOOKS) + read(SPECIAL) + read(VERSION))
        self.assertEqual(ng.tool_options(namespace(vault_suit="FO4Port_VaultSuit111")), ["--vault-suit", "FO4Port_VaultSuit111"])
        self.assertEqual(ng.tool_options(namespace(clear_inventory=True, vault_suit="FO4Port_VaultSuit111")),
                         ["--vault-suit", "FO4Port_VaultSuit111"])   # --clear-inventory: old command lines, the default
        self.assertEqual(ng.tool_options(namespace(keep_inventory=True)), ["--keep-inventory"])
        for bad in (dict(keep_inventory=True, vault_suit="FO4Port_VaultSuit111"), dict(keep_inventory=True, clear_inventory=True)):
            with self.assertRaises(SystemExit):
                ng.tool_options(namespace(**bad))
        self.assertIn("--keep-inventory", read(DOC))
        self.assertIn("--vault-suit", read(DOC))
        self.assertIn("## 4c. The starting inventory reset", read(DOC))

    def test_companions_held_off(self):
        """S13 row 5, the first group (owner, 15 Nov: "Companions first"): Starfield's companion and crew quests that the
        PC found running in our new game (result-pc-read-s13-5-partb) join the default hold list after the core five.
        Exactly the owner's group: the COM_* quests, SQ_Companions, SQ_Crew and CREW_*; not SQ_Followers (the follower
        system) nor SQ_COM_CREW_AngerCombatOverride. The selftest builds the list without them as a variant, cross-checks
        both ways and rejects a list that lost SQ_Companions; the PC run says whether they stay stopped."""
        cs = read(CS)
        self.assertEqual(ng.DEFAULT_HOLD[:len(ng.HOLD_CORE) + len(ng.HOLD_COMPANIONS)], ng.HOLD_CORE + ng.HOLD_COMPANIONS)
        self.assertEqual(len(ng.HOLD_COMPANIONS), 18)
        self.assertEqual(len(set(ng.DEFAULT_HOLD)), len(ng.DEFAULT_HOLD))
        for q in ng.HOLD_COMPANIONS:
            self.assertTrue(q.upper().startswith(("COM_", "CREW_")) or q in ("SQ_Companions", "SQ_Crew"), q)
            self.assertIn(f'EditorID = "{q}"', cs)                         # the selftest's master has it
        for q in ("SQ_Followers", "SQ_COM_CREW_AngerCombatOverride"):
            self.assertNotIn(q, ng.DEFAULT_HOLD)
        self.assertIn('("nocompanions", idsPath, plain with { Hold = HoldCore })', cs)
        self.assertIn('"a hold list without the companion group as the default one"', cs)
        self.assertIn('("the hold list lost SQ_Companions"', cs)

    def test_audio_logs_and_tutorials_held_off(self):
        """S13 row 5, the second group (owner, 15 Nov: "Keep going with shutting off quests until stuff starts to break",
        least risky first): the running AudioLogsQuest* quests and the two tutorials join the default hold list after
        the companions. Nothing of the follower, crew or group plumbing the owner keeps for Warfare squads. The selftest
        builds the list without them as a variant, cross-checks both ways and rejects a list that lost OutpostTutorial."""
        cs = read(CS)
        self.assertEqual(ng.DEFAULT_HOLD[:len(ng.HOLD_CORE) + len(ng.HOLD_COMPANIONS) + len(ng.HOLD_AUDIO_TUTORIALS)],
                         ng.HOLD_CORE + ng.HOLD_COMPANIONS + ng.HOLD_AUDIO_TUTORIALS)
        self.assertEqual(len(ng.HOLD_AUDIO_TUTORIALS), 14)
        self.assertEqual(len(set(ng.DEFAULT_HOLD)), len(ng.DEFAULT_HOLD))
        for q in ng.HOLD_AUDIO_TUTORIALS:
            self.assertTrue(q.startswith("AudioLogsQuest") or q in ("SQ_ENV_Tutorial", "OutpostTutorial"), q)
            self.assertIn(f'EditorID = "{q}"', cs)
        for q in ("SQ_Followers", "SQ_Crew", "SQ_Groups", "SQ_COM_CREW_AngerCombatOverride"):
            self.assertNotIn(q, ng.HOLD_AUDIO_TUTORIALS)
        self.assertIn('("noaudio", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).ToArray() })', cs)
        self.assertIn('"a hold list without the audio-log and tutorial group as the default one"', cs)
        self.assertIn('("the hold list lost OutpostTutorial"', cs)

    def test_city_and_faction_held_off(self):
        """S13 row 5, the third group (city and faction dialogue): the running quests that serve one Starfield city,
        settlement or faction join the default hold list after the audio logs. Generic dialogue, ship dialogue, the
        main-quest AlwaysOn quests and the follower, crew and group plumbing (the owner's Warfare boundary) stay out.
        The selftest builds the list without them, cross-checks both ways and rejects one that lost DialogueCydonia."""
        cs = read(CS)
        self.assertEqual(ng.DEFAULT_HOLD[:len(ng.HOLD_CORE + ng.HOLD_COMPANIONS + ng.HOLD_AUDIO_TUTORIALS + ng.HOLD_CITY_FACTION)],
                         ng.HOLD_CORE + ng.HOLD_COMPANIONS + ng.HOLD_AUDIO_TUTORIALS + ng.HOLD_CITY_FACTION)
        self.assertEqual(len(ng.HOLD_CITY_FACTION), 80)
        self.assertEqual(len(set(ng.DEFAULT_HOLD)), len(ng.DEFAULT_HOLD))
        for q in ng.HOLD_CITY_FACTION:
            self.assertTrue(q.startswith(("City", "CF", "UC0", "Dialog", "RI_Support", "Settlement_")), q)
            self.assertNotIn("Ships", q)                                      # the ship dialogue is the ships group
            self.assertFalse(q.startswith("DialogueGeneric") and q != "DialogueGenericHouseVaruun", q)
            self.assertIn(f'EditorID = "{q}"', cs)
        for q in ("SQ_Followers", "SQ_Groups", "SQ_COM_CREW_AngerCombatOverride", "DialogueGeneric", "DialogueCrowds",
                  "DialogueGenericPlayer", "SQ_PlayerShip", "DialogueShipServices", "MQ105_AlwaysOnDialogueNeon"):
            self.assertNotIn(q, ng.HOLD_CITY_FACTION)
        self.assertIn('("nocity", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).ToArray() })', cs)
        self.assertIn('"a hold list without the city and faction group as the default one"', cs)
        self.assertIn('("the hold list lost DialogueCydonia"', cs)

    def test_generic_dialogue_and_activities_held_off(self):
        """S13 row 5, the fourth group (FAL-1041): the rest of Gemini's city and faction dialogue batches (32), then the
        rest of its activities and misc batches (16), join the default hold list after the city and faction group. The
        five quests the Warfare boundary keeps running and the seven never to stop stay out, and so do the radiant, ship
        and system batches. The selftest builds the list without the group and without the activities, cross-checks
        each both ways and rejects a list that lost DialogueCrowds or SQ_Doctors."""
        cs = read(CS)
        prefix = (ng.HOLD_CORE + ng.HOLD_COMPANIONS + ng.HOLD_AUDIO_TUTORIALS + ng.HOLD_CITY_FACTION
                  + ng.HOLD_GENERIC_DIALOGUE + ng.HOLD_ACTIVITIES)
        self.assertEqual(ng.DEFAULT_HOLD[:len(prefix)], prefix)
        self.assertEqual((len(ng.HOLD_GENERIC_DIALOGUE), len(ng.HOLD_ACTIVITIES)), (32, 16))
        self.assertEqual(len(set(ng.DEFAULT_HOLD)), len(ng.DEFAULT_HOLD))
        for q in ng.HOLD_GENERIC_DIALOGUE + ng.HOLD_ACTIVITIES:
            self.assertNotIn("Ships", q)                                      # the ship dialogue is the ships group
            self.assertIn(f'EditorID = "{q}"', cs)
        for q in ng.HOLD_GENERIC_DIALOGUE:
            self.assertTrue("Dial" in q or q.startswith("LC082_"), q)        # DialgoueSSNNScenes: Starfield's spelling
        for q in ("SQ_Followers", "SQ_Groups", "SQ_COM_CREW_AngerCombatOverride", "SQ_Captive", "SQ_Airlock",  # Warfare
                  "SQ_PlayerShip", "SQ_Parent", "PlayerSkills", "DialogueGenericPlayer", "DialogueGeneric",
                  "SpeechChallenge", "Achievements_Quest",                                     # never to stop
                  "MB_Parent", "RE_Parent", "DialogueShipServices", "SQ_Traits"):              # later groups
            self.assertNotIn(q, ng.HOLD_GENERIC_DIALOGUE + ng.HOLD_ACTIVITIES)
        self.assertIn('("nodialogue", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).ToArray() })', cs)
        self.assertIn('"a hold list without the generic dialogue and activities group as the default one"', cs)
        self.assertIn('"a hold list without the activities as the default one"', cs)
        self.assertIn('("the hold list lost DialogueCrowds"', cs)
        self.assertIn('("the hold list lost SQ_Doctors"', cs)

    def test_radiant_ships_and_system_held_off(self):
        """S13 row 5, the fifth group (section 4i): the remaining 9 radiant quests, 21 holdable ship quests and 4
        Starfield-only system quests join the default hold list after the activities list (199 held total). The 5
        Warfare boundary quests and 7 core engine quests never to stop remain excluded."""
        cs, doc = read(CS), read(DOC)
        self.assertEqual(ng.DEFAULT_HOLD, ng.HOLD_CORE + ng.HOLD_COMPANIONS + ng.HOLD_AUDIO_TUTORIALS
                         + ng.HOLD_CITY_FACTION + ng.HOLD_GENERIC_DIALOGUE + ng.HOLD_ACTIVITIES
                         + ng.HOLD_RADIANT + ng.HOLD_SHIPS + ng.HOLD_SYSTEM)
        self.assertEqual((len(ng.HOLD_RADIANT), len(ng.HOLD_SHIPS), len(ng.HOLD_SYSTEM)), (9, 21, 4))
        self.assertEqual(len(ng.DEFAULT_HOLD), 199)
        self.assertEqual(len(set(ng.DEFAULT_HOLD)), len(ng.DEFAULT_HOLD))
        for q in ng.HOLD_RADIANT + ng.HOLD_SHIPS + ng.HOLD_SYSTEM:
            self.assertIn(f'EditorID = "{q}"', cs)
            self.assertIn(f"`{q}`", doc)
        for q in ("SQ_Followers", "SQ_Groups", "SQ_COM_CREW_AngerCombatOverride", "SQ_Captive", "SQ_Airlock",
                  "SQ_PlayerShip", "SQ_Parent", "PlayerSkills", "DialogueGenericPlayer", "DialogueGeneric",
                  "SpeechChallenge", "Achievements_Quest"):
            self.assertNotIn(q, ng.DEFAULT_HOLD)
        self.assertIn('("noradiant", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).Concat(HoldActivities).ToArray() })', cs)
        self.assertIn('("noships", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).Concat(HoldActivities).Concat(HoldRadiant).ToArray() })', cs)
        self.assertIn('("nosystem", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).Concat(HoldActivities).Concat(HoldRadiant).Concat(HoldShips).ToArray() })', cs)
        self.assertIn('"a hold list without the radiant, ship and system group as the default one"', cs)
        self.assertIn('"a hold list without the ships and system lists as the default one"', cs)
        self.assertIn('"a hold list without the system list as the default one"', cs)
        self.assertIn('("the hold list lost MB_Parent"', cs)
        self.assertIn('("the hold list lost DialogueShipServices"', cs)
        self.assertIn('("the hold list lost SQ_Traits"', cs)
        self.assertEqual(len(ng.OMIT_HOLD_GROUPS["radiant"]), 190)
        self.assertEqual(len(ng.OMIT_HOLD_GROUPS["ships"]), 178)
        self.assertEqual(len(ng.OMIT_HOLD_GROUPS["system"]), 195)
        for group_name, omitted in (("radiant", ng.HOLD_RADIANT), ("ships", ng.HOLD_SHIPS), ("system", ng.HOLD_SYSTEM)):
            ns_opt = namespace(omit_hold_group=group_name)
            expected = ",".join(q for q in ng.DEFAULT_HOLD if q not in set(omitted))
            self.assertEqual(ng.hold_option(ns_opt), expected)
            self.assertEqual(ng.tool_options(ns_opt), ["--hold", expected])
        with self.assertRaises(SystemExit):
            ng.hold_option(namespace(hold="MQ00", omit_hold_group="system"))

    def test_no_starfield_environment(self):
        """S13 row 2b (FAL-883, owner decision 15 Nov): with the empty start the player takes no Starfield environment
        damage and the body stays drawn. No game setting switches it off; SQ_ENV's player alias gives 17 ENV abilities
        (PC read 15 Nov; HumanRace's two hit-spell abilities and placed local hazards are not SQ_ENV's and are the PC
        run's to check), so SQ_ENV is on the default hold list, and the quest tops 0002E2 up to 100 right after the
        reset for the O2/CO2 dial. No stand-in piece and no record override: the plugin's only Starfield links are
        script properties. --no-o2-fill and a --hold without SQ_ENV are the ways back; the selftest covers both."""
        cs, psc = read(CS), read(PSC)
        self.assertEqual(ng.HOLD_CORE[-1], "SQ_ENV")
        self.assertTrue(ng.DEFAULT_O2_FILL)
        self.assertIn(f"DefaultO2Fill = {str(ng.DEFAULT_O2_FILL).lower()};", cs)
        self.assertIn("O2CapacityId = 0x0002E2;", cs)
        self.assertIn("O2CapacityAmount = 100f;", cs)
        self.assertIn("public bool O2 => ClearInventory && O2Fill;", cs)
        self.assertIn('!a.Contains("--no-o2-fill")', cs)
        self.assertIn('("O2CapacityAmount", o.O2 ? O2CapacityAmount : 0f)', cs)
        self.assertIn('Obj("O2Capacity", new FormKey(SfEsm, O2CapacityId))', cs)
        self.assertIn('EditorID = "SQ_ENV"', cs)                             # the selftest's master has it
        for mutation in ("the hold list lost SQ_ENV", "the O2 capacity amount changed", "the O2 capacity linked to Oxygen", "O2Capacity removed"):
            self.assertIn(f'("{mutation}"', cs)
        self.assertIn('"a hold list without SQ_ENV as the default one"', cs)
        for gone in ("StandIn", "ArmorTypeSpacesuit", "Skin_Naked"):          # the stand-in route ended (owner, 15 Nov)
            self.assertNotIn(gone, cs)
            self.assertNotIn(gone, psc)
        self.assertIn("ActorValue Property O2Capacity Auto Const", psc)
        self.assertIn("float Property O2CapacityAmount = 0.0 Auto Const", psc)
        timer = psc[psc.index("Event OnTimer"):]
        self.assertLess(timer.index("ResetInventory(player)"), timer.index("FillO2(player)"))
        self.assertLess(timer.index("FillO2(player)"), timer.index("AdvanceTo(10)"))
        fn = psc[psc.index("Function FillO2"):]
        fn = fn[:fn.index("EndFunction")]
        self.assertIn("float added = O2CapacityAmount - player.GetValue(O2Capacity)", fn)   # tops up, never adds twice
        self.assertIn("player.ModValue(O2Capacity, added)", fn)
        self.assertIn('Trace("o2 capacity added="', fn)
        for native in ("ModValue", "GetValue"):
            self.assertIn(native, ng.NATIVES[ng.SCRIPT]["Actor"])
        self.assertTrue(ng.o2_fill_option(namespace()))
        self.assertFalse(ng.o2_fill_option(namespace(no_o2_fill=True)))
        self.assertFalse(ng.o2_fill_option(namespace(keep_inventory=True)))
        self.assertNotIn("--no-o2-fill", ng.tool_options(namespace()))
        self.assertEqual(ng.tool_options(namespace(no_o2_fill=True)), ["--no-o2-fill"])
        doc = read(DOC)
        self.assertIn("## 4d. No Starfield environment damage (S13 row 2b)", doc)
        self.assertIn("--no-o2-fill", doc)

    def test_the_default_start_has_no_starfield_items(self):
        """System model S13 row 2 (strip down Starfield): the default build empties Starfield's starting inventory
        (outfit, gear, credits) at the pod in all three places that hold the default, as FO4's MQ101 does; until the
        port has a vault suit the player starts with nothing. --keep-inventory still builds the old start, the way
        back; the plan and README say which. The selftest refuses an off default and builds the keep variant."""
        cs, psc = read(CS), read(PSC)
        self.assertTrue(ng.DEFAULT_CLEAR_INVENTORY)
        self.assertIn("DefaultClearInventory = true;", cs)
        self.assertIn("bool Property ClearInventory = true Auto Const", psc)
        self.assertTrue(ng.clear_inventory_option(namespace()))
        self.assertTrue(ng.clear_inventory_option(namespace(clear_inventory=True)))
        self.assertFalse(ng.clear_inventory_option(namespace(keep_inventory=True)))
        self.assertNotIn("--keep-inventory", ng.tool_options(namespace()))   # no option: Program.cs's default applies
        self.assertIn('bool clear = !keep && DefaultClearInventory;', cs)
        self.assertIn('("keep", idsPath, keep)', cs)
        self.assertIn("!DefaultClearInventory || !plain.ClearInventory", cs)   # the selftest refuses an off default
        self.assertIn('("the inventory reset switched off"', cs)

    def test_the_vault_anchor_modes(self):
        """PC result 21 Oct: the installed port's FO4Port_Vault111Cryo has no persistent reference (0 of 1,166; the COC
        marker 001338 and every terminal temporary), so the persistent-only resolver refused the build. A temporary
        reference of an unloaded cell resolves to None (verified 16 Oct), so the writer now falls back to the temporary
        COC marker and tells the script (AnchorTemporary, VaultCell) to load the cell with Debug.CenterOnCell once before
        the same MoveTo; the retry is bounded once the player's 3D is in (CenterTicks, one more centering at most, then
        a failure line each 10 tries; the timer waits for the 3D before it retries, and while it waits it writes its
        own line every 10 ticks). The persistent mode stays preferred. Since newgame_v11 (our own start) the temporary
        mode is refused by default: its centering comes during the first load, and a centering that moves nobody hands
        nothing back, so that load would never end (29 Oct review on #588); --allow-temporary-anchor builds it, and
        --require-persistent-anchor is kept for old command lines. write and check print the mode after the anchor id;
        plan.json records it; the log summary reads the centering line."""
        cs, psc = read(CS), read(PSC)
        self.assertIn(f"DefaultRequirePersistentAnchor = {str(ng.DEFAULT_REQUIRE_PERSISTENT_ANCHOR).lower()};", cs)
        self.assertTrue(ng.DEFAULT_REQUIRE_PERSISTENT_ANCHOR)
        self.assertIn('!a.Contains("--allow-temporary-anchor")', cs)
        self.assertIn('throw new Refusal("--allow-temporary-anchor and --require-persistent-anchor contradict each other")', cs)
        self.assertIn("--allow-temporary-anchor builds on the temporary COC marker", cs)   # the refusal names the way in
        self.assertIn("bool requirePersistentAnchor = DefaultRequirePersistentAnchor", cs)
        self.assertIn("if (persistent is null && requirePersistentAnchor)", cs)
        self.assertIn("var anchor = persistent ?? cocs[0];", cs)
        self.assertIn("bool anchorTemporary = persistent is null;", cs)
        self.assertIn('("AnchorTemporary", p.AnchorTemporary), ("VaultCell", VaultCell)', cs)
        self.assertIn('AnchorTemporary ? "temporary" : "persistent"', cs)
        self.assertIn("vault anchor FO4Port.esm:{places.VaultAnchor:X6} {places.AnchorMode} at", cs)       # write's line
        self.assertIn("  vault anchor FO4Port.esm:{places.VaultAnchor:X6} {places.AnchorMode}, cog door", cs)   # check's line
        self.assertIn("string s => new SF.ScriptStringProperty", cs)
        self.assertIn("(string s, SF.IScriptStringPropertyGetter sp) => sp.Data == s", cs)
        # the script: the two properties the writer fills, the bound, and the centering only in the temporary mode
        self.assertIn("bool Property AnchorTemporary = false Auto Const", psc)
        self.assertIn('string Property VaultCell = "FO4Port_Vault111Cryo" Auto Const', psc)
        self.assertIn('VaultCell = "FO4Port_Vault111Cryo"', cs)
        self.assertIn("int Property CenterTicks = 30 Auto Const", psc)
        enter = psc[psc.index("bool Function EnterVault"):psc.index("bool Function CenterOnVault")]
        self.assertIn("if anchor == None\n        if AnchorTemporary\n            return CenterOnVault()\n        endif", enter)
        self.assertEqual(enter.count("player.MoveTo(anchor, PodX - AnchorX, PodY - AnchorY, PodZ + PodLift - AnchorZ, False, False)"), 1)   # one MoveTo, both modes
        center = psc[psc.index("bool Function CenterOnVault"):psc.index("Function ResetInventory")]
        self.assertEqual(center.count("Debug.CenterOnCell(VaultCell)"), 1)
        self.assertEqual(psc.count("Debug.CenterOnCell("), 1)      # nowhere else
        self.assertIn("if centered == 0 || (centered == 1 && centerTries > CenterTicks)", center)
        self.assertIn("elseif centerTries > CenterTicks && centerTries % 10 == 0", center)
        self.assertIn('Trace("centered on " + VaultCell + " attempt=" + centered + " tick=" + centerTries', center)
        self.assertIn('does not resolve after " + centerTries + " ticks and " + centered + " centerings', center)
        self.assertEqual(center.count("return false"), 1)          # the caller's retry does the move; no MoveTo here
        self.assertNotIn("MoveTo(", center)
        self.assertIsNone(re.search(r"^\s*while\b", center, re.M))   # no loop: the timer's retry is the only repeat
        # the guard still runs first, once (Begin): EnterVault, and so any centering, comes after it; a centering is a
        # move under way, so the start goes on (the hold-off, the write) as after a MoveTo and never hands back (the
        # reason the mode is built only on request)
        begin = psc[psc.index("Function Begin"):psc.index("Function StandDown")]
        self.assertLess(begin.index("if !IsNewGame(days, level)"), begin.index("entered = EnterVault(player)"))
        self.assertLess(begin.index("entered = EnterVault(player)"), begin.index("if startRoomMoves == 0 && vaultMoves == 0 && centered == 0"))
        self.assertLess(begin.index("if startRoomMoves == 0 && vaultMoves == 0 && centered == 0"), begin.index("HoldOffPass(1)"))
        self.assertIn("anchor_temporary=", begin)
        # the precheck reads the native; the stage option, the plan and the README carry the mode
        self.assertIn("CenterOnCell", ng.NATIVES[ng.SCRIPT]["Debug"])
        self.assertEqual(ng.tool_options(namespace(allow_temporary_anchor=True)), ["--allow-temporary-anchor"])
        self.assertEqual(ng.tool_options(namespace(require_persistent_anchor=True)), [])   # the default: nothing to pass
        self.assertEqual(ng.tool_options(namespace()), [])
        with self.assertRaises(SystemExit):
            ng.tool_options(namespace(allow_temporary_anchor=True, require_persistent_anchor=True))
        self.assertEqual(ng.anchor_mode("  vault anchor FO4Port.esm:001338 temporary, cog door none, exit anchor FO4TerrainCore.esm:0A775B\n"),
                         {"id": "001338", "mode": "temporary"})
        self.assertEqual(ng.anchor_mode("x\n  vault anchor FO4Port.esm:000805 persistent, cog door 000802 Door X, exit anchor FO4TerrainCore.esm:0A775B\n"),
                         {"id": "000805", "mode": "persistent"})
        self.assertIsNone(ng.anchor_mode("  vault anchor FO4Port.esm:000805, cog door none"))   # the line before the modes
        self.assertIsNone(ng.anchor_mode(""))
        src = read(os.path.join(ROOT, "scripts", "newgame", "make_newgame.py"))
        self.assertIn('"anchor": anchor,', src)
        self.assertIn('"allow_temporary_anchor": bool(a.allow_temporary_anchor)', src)
        doc = read(DOC)
        self.assertIn("--allow-temporary-anchor", doc)
        self.assertIn("## 3a. The vault anchor: persistent, or the temporary COC marker", doc)
        self.assertRegex(doc, r"0 persistent references of\s+1,166")
        self.assertIn("`CenterOnCell`", doc)

    def test_the_pod_start_is_lifted_and_checked(self):
        """Run 3 of 28 Oct (newgame_v9): the MoveTo put the player at about the pod's z (read back -1.045, the pod's
        -1.029), the bridge saw them 0.69 m lower once the vault had loaded, and 0.64 s later the game stood them on the COC marker 8 m away (no script
        moved them). On that marker (z -0.738) they stood at -0.852, so the start goes PodLift (0.3) higher, the marker's
        height, and the first loaded tick after the move logs where the player stands ("pod settle"). The check moves
        nothing: the game's own reset to the marker is the fallback."""
        psc = read(PSC)
        self.assertIn("float Property PodLift = 0.3 Auto Const", psc)
        self.assertIn("float Property PodRadius = 1.0 Auto Const", psc)
        self.assertIn("float Property PodDrop = 0.5 Auto Const", psc)
        self.assertAlmostEqual(-1.029 + 0.3, -0.738, delta=0.01)   # the lifted start is the marker's height
        enter = psc[psc.index("bool Function EnterVault"):psc.index("Function CheckPod")]
        self.assertIn('" target=" + PodX + " " + PodY + " " + (PodZ + PodLift) + " cell="', enter)   # the log's target is the start
        body = psc[psc.index("Event OnTimer"):psc.index("bool Function IsNewGame")]
        ten = body[body.index("elseif stage == 10"):body.index("elseif stage == 20 || stage == 30")]
        self.assertIn("if !podChecked && player.Is3DLoaded()\n            CheckPod(player)\n        endif", ten)
        self.assertLess(ten.index("CheckPod(player)"), ten.index("LooksWait"))   # a --no-looks build still checks first
        check = psc[psc.index("Function CheckPod"):psc.index("bool Function CenterOnVault")]
        self.assertIn("podChecked = true", check)
        self.assertIn("float targetZ = PodZ + PodLift", check)
        self.assertIn("float drop = targetZ - sampleZ", check)
        self.assertIn("bool ok = dx * dx + dy * dy <= PodRadius * PodRadius && drop <= PodDrop", check)
        self.assertIn('Trace("pod settle ok=" + ok + " pos="', check)
        for call in ("MoveTo(", "SetPosition(", "CenterOnCell("):
            self.assertNotIn(call, check)                    # evidence only
        self.assertEqual(psc.count("CheckPod(player)"), 2)   # stage 10 legacy wait + InVault for pre-world Story jump to stage 20

    def test_the_surface_arrival_waits_a_tick(self):
        """Run 3 of 28 Oct: the ride's SetPosition, called in the MoveTo's own tick, was ignored (the "surface
        setposition" line read the MoveTo's position, the anchor's local spot, 6.8 m under it) and the fall check's
        SetPosition 5.7 s later took. The ride is now two ticks, like the load door (MoveTo, wait, SetPosition): Surface
        only moves; FinishSurface sets the merged arrival on a later tick, once the player is outside and loaded, reads
        the position back, and goes on to stage 40 when it took or after SurfaceTries; a MoveTo that never left the vault
        is redone once, then the elevator asks again."""
        psc = read(PSC)
        self.assertIn("float Property SurfaceWait = 10.0 Auto Const", psc)
        self.assertIn("int Property SurfaceTries = 3 Auto Const", psc)
        surface = psc[psc.index("Function Surface(Actor player)"):psc.index("Function FinishSurface")]
        self.assertEqual(surface.count("player.MoveTo(anchor, 0.0, 0.0, 0.0, True, False)"), 1)
        self.assertNotIn("SetPosition(", surface)
        self.assertNotIn("AdvanceTo(", surface)
        self.assertLess(surface.index("player.MoveTo("), surface.index("surfaceMovedAt = Utility.GetCurrentRealTime()"))
        finish = psc[psc.index("Function FinishSurface"):psc.index("Function CheckLanding")]
        self.assertNotIn("MoveTo(", finish.replace("Surface(player)", ""))   # its only move is Surface's, once more
        # inside: wait, or count a missed move; outside but not loaded: wait; both return before the SetPosition
        inside = finish[finish.index("    if player.IsInInterior()\n"):finish.index("    if !player.Is3DLoaded()\n")]
        self.assertTrue(inside.endswith("        return\n    endif\n"), inside)
        self.assertIn("    if !player.Is3DLoaded()\n        return", finish)
        self.assertLess(finish.index("if !player.Is3DLoaded()"), finish.index("player.SetPosition(x, y, ArrivalZ)"))
        self.assertNotIn("Is3DLoaded", inside)               # an outside player still loading is never a missed move
        self.assertIn("bool ok = dx * dx + dy * dy <= 25.0", finish)
        self.assertIn('Trace("surface setposition ok=" + ok +', finish)
        self.assertNotIn("if ok || surfaceSets >= SurfaceTries", finish)
        self.assertIn('elseif surfaceSets >= SurfaceTries', finish)
        self.assertIn('FailExit("surface_cell_not_core")', finish)
        self.assertIn('FailExit("surface_position_not_confirmed")', finish)
        self.assertLess(finish.index("if ok\n"), finish.index("AdvanceTo(40)"))
        self.assertIn("if surfaceMoves < 2", finish)
        self.assertIn("asked = false", finish)               # a missed ride lets the platform ask again
        self.assertIn("ClearVaultSaveLock()", surface)
        self.assertIn("anchor.Enable(False)", surface)
        self.assertIn("TrySurfaceExteriorFallbacks(player, anchor)", surface)
        self.assertEqual(psc.count("Debug.CenterOnCell("), 1)
        self.assertEqual(psc.count("AdvanceTo(40)"), 1)
        self.assertEqual(psc.count("FinishSurface(player)"), 1)   # only a later tick's OnTimer finishes the ride
        invault = psc[psc.index("Function InVault"):psc.index("Function Surface(Actor player)")]
        self.assertIn("Surface(player)", invault)
        self.assertNotIn("SetPosition(", invault)
        body = psc[psc.index("Event OnTimer"):psc.index("bool Function IsNewGame")]
        branch = body[body.index("elseif stage == 20 || stage == 30"):body.index("elseif stage == 40")]
        self.assertIn("elseif surfaceMovedAt > 0.0\n            FinishSurface(player)", branch)
        self.assertLess(branch.index("FinishSurface(player)"), branch.index("InVault(player, stage)"))
        land = psc[psc.index("Function CheckLanding"):psc.index("bool Function Near")]
        self.assertIn("if Utility.GetCurrentRealTime() - arrivedAt < 3.0", land)   # three seconds after the arrival that took

    def test_special_at_the_vault_terminal(self):
        """NG-5 / NG-C4: the SPECIAL rule is one set of numbers in the writer, the script and Python; the allocation
        message's buttons are the stats in order, then Reset, Confirm, Leave; the script applies Confirm with
        Actor.SetValue on the seven AVIF and logs every ending as "special <how>"; the quest never waits on it (no
        SPECIAL wait in the quest script), and a --no-special build drops the script, its MESG and the AVIF."""
        cs, special, psc = read(CS), read(SPECIAL), read(PSC)
        self.assertIn("SpecialNames = { " + ", ".join(f'"{n}"' for n in ng.SPECIAL_STATS) + " }", cs)
        self.assertIn("SpecialExtraButtons = { " + ", ".join(f'"{n}"' for n in ng.SPECIAL_BUTTONS[len(ng.SPECIAL_STATS):]) + " }", cs)
        self.assertIn(f"SpecialBase = {ng.SPECIAL_BASE}, SpecialPoints = {ng.SPECIAL_POINTS}, SpecialMax = {ng.SPECIAL_MAX};", cs)
        self.assertIn(f"int Property SpecialBase = {ng.SPECIAL_BASE} Auto Const", special)
        self.assertIn(f"int Property SpecialPoints = {ng.SPECIAL_POINTS} Auto Const", special)
        self.assertIn(f"int Property SpecialMax = {ng.SPECIAL_MAX} Auto Const", special)
        self.assertIn(f"int Property MaxPresses = {ng.SPECIAL_MAX_PRESSES} Auto Const", special)
        self.assertIn("while presses < MaxPresses", special)   # the loop is bounded: no spin on a box that returns at once
        self.assertNotIn("while true", special)
        self.assertGreater(ng.SPECIAL_MAX_PRESSES, 10 * (ng.SPECIAL_POINTS + 1))   # ten full passes with a Reset each
        self.assertEqual(len(ng.SPECIAL_BUTTONS), 10)
        self.assertLessEqual(len(ng.SPECIAL_PAGE1_BUTTONS), 7)
        self.assertLessEqual(len(ng.SPECIAL_PAGE2_BUTTONS), 7)
        self.assertIn("Confirm", ng.SPECIAL_PAGE1_BUTTONS)    # B3: Confirm reachable from the first box
        self.assertIn("if button >= 0 && button < 3", special)
        self.assertIn("if button >= 0 && button < 4", special)
        self.assertIn("elseif button == 5", special)          # Confirm on both <=7-button pages
        self.assertIn("Message Property SpecialMessagePage2 Auto Const Mandatory", special)
        self.assertIn("int[] values = new int[7]", special)
        self.assertIn("player.SetValue(Special[i], values[i] as float)", special)
        self.assertIn('Trace("special set S="', special)
        self.assertIn('Trace("special skipped: left the vault with SPECIAL unset")', special)
        self.assertIn('Trace("special later")', special)
        self.assertIn('Trace("special left: ', special)
        self.assertIn("ActorValue[] Property Special Auto Const Mandatory", special)
        self.assertIn('string Property VaultPlugin = "FO4Port.esm" Auto Const', special)
        self.assertNotIn("as FO4SF_NewGameSpecial", psc)     # dynamic CastAs only; --no-special still compiles without it
        self.assertIn('CastAs("FO4SF_NewGameSpecial")', psc)
        self.assertIn("bool Function AllocateFromLift(Actor player)", special)
        self.assertIn('SpecialScript = "FO4SF_NewGameSpecial"', cs)
        self.assertIn('a.Contains("--no-special")', cs)
        self.assertNotIn("Types.SpecialAttribute", cs)
        self.assertIn("plug.ActorValueInformation.Count == 0", cs)
        self.assertIn(f'CoreValuesPlugin = "{CORE_VALUES_PLUGIN}"', cs)
        self.assertIn('Obj("TestModeGlobal", testModeKey)', cs)
        self.assertEqual(ng.SPECIAL_AVIF_IDS, tuple(0x810 + i for i in range(7)))
        self.assertEqual(ng.TEST_MODE_GLOBAL_ID, core_form_id("FO4SF_TestModeEnabled"))
        self.assertEqual(ng.TEST_MODE_GLOBAL_ID, 0x860)
        self.assertIn('"TerminalId", (int)p.Terminal', cs)
        self.assertEqual(ng.tool_options(namespace(special=False)), ["--no-special"])
        self.assertEqual(ng.OPTIONAL, {ng.LOOKS: "--no-looks", ng.SPECIAL: "--no-special", ng.VERSION: "--no-version"})

    def test_the_allocation_rule(self):
        """special_press is FO4SF_NewGameSpecial.Allocate's rule: base 1 each, 33 points (pool of 40 total),
        10 at most per stat, Reset starts over, Confirm only with every point spent, Leave (or a closed message)
        keeps the defaults."""
        base, pts = [ng.SPECIAL_BASE] * 7, ng.SPECIAL_POINTS
        self.assertEqual((ng.SPECIAL_BASE, ng.SPECIAL_POINTS, ng.SPECIAL_MAX), (1, 33, 10))
        values, left, end = ng.special_press(base, pts, 0)
        self.assertEqual((values, left, end), ([2, 1, 1, 1, 1, 1, 1], 32, None))
        for _ in range(12):                                   # Strength stops at 10 and costs nothing past it
            values, left, end = ng.special_press(values, left, 0)
        self.assertEqual((values[0], left, end), (ng.SPECIAL_MAX, 24, None))
        self.assertEqual(ng.special_press(values, left, 8), (values, 24, None))          # Confirm with points left
        for b in (1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6):   # spend remaining 24
            values, left, end = ng.special_press(values, left, b)
        self.assertEqual((values, left, end), ([10, 5, 5, 5, 5, 5, 5], 0, None))
        self.assertEqual(sum(values), 40)
        self.assertEqual(sum(values), 7 * ng.SPECIAL_BASE + ng.SPECIAL_POINTS)
        self.assertEqual(ng.special_press(values, 0, 3), (values, 0, None))              # no points left
        self.assertEqual(ng.special_press(values, 0, 8), (values, 0, "set"))
        self.assertEqual(ng.special_press(values, 0, 7), (base, pts, None))
        self.assertEqual(ng.special_press(values, 0, 9), (values, 0, "left"))
        self.assertEqual(ng.special_press(base, pts, -1), (base, pts, "left"))

    def test_the_race_menu_mode_and_the_opening_choice(self):
        """NG-6 / NG-C9 / NG-C1: the writer's --race-menu-mode (default 2) is the looks script's RaceMenuMode, passed
        to ShowRaceMenu as its uiMode; the opening MESG offers the creator or the quick start, and the quick start never
        calls ShowRaceMenu. The creator's close is awaited on "ChargenMenu", registered before the menu opens, with
        the quest's LooksWait as the fallback; every ending is logged as "looks done: <how>" (the log summary reads it)."""
        cs, looks, psc = read(CS), read(LOOKS), read(PSC)
        self.assertIn(f"DefaultRaceMenuMode = {ng.DEFAULT_RACE_MENU_MODE};", cs)
        self.assertIn('ArgOrNull(a, "--race-menu-mode")', cs)
        self.assertIn(f"int Property RaceMenuMode = {ng.DEFAULT_RACE_MENU_MODE} Auto Const", looks)
        code = looks[looks.index("Message Property StartMessage"):]   # past the header's signature note
        self.assertEqual(code.count("ShowRaceMenu("), 1)
        self.assertIn("Game.ShowRaceMenu(None, RaceMenuMode)", code)
        self.assertIn('StartMessageEdid = "FO4SF_NewGameStart"', cs)
        self.assertIn('Name = "Character Appearance"', cs)
        self.assertIn('Text = "Create character"', cs)
        self.assertIn('Text = "Quick start"', cs)
        self.assertLess(cs.index('Text = "Quick start"'), cs.index('Text = "Create character"'))
        self.assertIn("if button == 0", looks)
        self.assertIn("if cBtn == 0", psc)
        self.assertIn("ngQuest.IsPreworldLooksHandled()", looks)
        self.assertIn("Message Property StartMessage Auto Const Mandatory", looks)
        body = looks[looks.index("Event OnTimer"):]
        self.assertLess(body.index("StartMessage.Show()"), body.index("RegisterForMenuOpenCloseEvent(MenuName)"))
        self.assertLess(body.index("RegisterForMenuOpenCloseEvent(MenuName)"), body.index("Game.ShowRaceMenu("))
        self.assertIn('string Property MenuName = "ChargenMenu" Auto Const', looks)
        self.assertIn("Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)", looks)
        self.assertIn("if asMenuName == MenuName && !abOpening && waiting", looks)
        self.assertIn('Done("quick start")', looks)
        self.assertIn('Done("creator closed")', looks)
        self.assertIn('Trace("looks done: " + how)', looks)
        self.assertIn('Trace("looks done: LooksWait fallback after " + LooksWait + " s")', psc)
        self.assertEqual(ng.tool_options(namespace(race_menu_mode=1)), ["--race-menu-mode", "1"])

    def test_the_default_creator_has_no_starfield_backgrounds(self):
        """System model S13 (strip down Starfield) and the owner's NG-C3 (looks only): the default build does not open
        the full creator (mode 0, Starfield's Background and Traits pages) in any of the three places that hold the
        mode; --race-menu-mode 0 still builds it, the way back. The selftest's second build is that mode 0 one."""
        cs, looks = read(CS), read(LOOKS)
        self.assertEqual(ng.FULL_CREATOR_MODE, 0)
        self.assertNotEqual(ng.DEFAULT_RACE_MENU_MODE, ng.FULL_CREATOR_MODE)
        self.assertNotIn("DefaultRaceMenuMode = 0;", cs)
        self.assertNotIn("int Property RaceMenuMode = 0 Auto Const", looks)
        self.assertEqual(ng.tool_options(namespace(race_menu_mode=0)), ["--race-menu-mode", "0"])
        self.assertNotIn("--race-menu-mode", ng.tool_options(namespace()))   # no option: Program.cs's default applies
        self.assertIn('("mode0", idsPath, plain with { RaceMenuMode = 0 })', cs)
        self.assertIn("DefaultRaceMenuMode == 0", cs)                # the selftest refuses a full-creator default

    def test_stages_match(self):
        cs, psc = read(CS), read(PSC)
        self.assertIn("Stages = { " + ", ".join(str(s) for s in ng.STAGES) + " }", cs)
        for s in ng.STAGES:
            if s not in (20, 30):                            # 20 is set by the looks script or the wait, 30 by the cog door
                self.assertRegex(psc, rf"AdvanceTo\({s}\)")
        self.assertIn("SetStage(20)", read(LOOKS))
        self.assertIn("AdvanceTo(30)", psc)
        self.assertIn("SetObjectiveDisplayed(10)", psc)
        self.assertIn("Objective = 10", cs)

    def test_the_stage_contract_is_the_scripts(self):
        """NG-14: the stages are a published contract. The .psc header lists each stage with its meaning; the Python
        constants (the log summary, plan.json) and the doc's table must say the same."""
        header = read(PSC).split("}", 1)[0]
        listed = {int(m.group(1)): m.group(2).strip()
                  for m in re.finditer(r"^\s+(\d+) ([a-z].*)$", header[header.index("Stages are the published"):], re.M)}
        self.assertEqual(listed, ng.STAGE_CONTRACT)
        self.assertEqual(ng.STAGES, (1, 5, 10, 20, 30, 40, 200, 210))
        self.assertEqual(list(ng.STAGE_CONTRACT), [0] + list(ng.STAGES))
        doc = read(os.path.join(ROOT, "docs", "newgame", "vault111-start.md"))
        audit = read(os.path.join(ROOT, "docs", "newgame", "lift-rules-audit.md"))
        for n, what in ng.STAGE_CONTRACT.items():
            target_doc = audit if n in (5, 210) else doc
            self.assertIn(f"| {n} | {what} |", target_doc)

    def test_the_writer_defaults_match_the_python_ones(self):
        """NG-2: the default build writes NO GLOB MQ101Debug override (28 Oct run 2) and the quest writes 2 right after the
        hold-off (--debug-after-hold); --mq101debug <n> overrides the record for an experiment. NG-19 / NG-N1: the
        default hold list has the two quests MQ101's stage 9000 starts on stop."""
        cs = read(CS)
        self.assertIn("HoldCore = { " + ", ".join(f'"{q}"' for q in ng.HOLD_CORE) + " }", cs)
        self.assertIn("DefaultHold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction)\n"
                      "        .Concat(HoldGenericDialogue).Concat(HoldActivities)\n"
                      "        .Concat(HoldRadiant).Concat(HoldShips).Concat(HoldSystem).ToArray();", cs)
        for name, group in (("HoldCompanions", ng.HOLD_COMPANIONS), ("HoldAudioTutorials", ng.HOLD_AUDIO_TUTORIALS),
                            ("HoldCityFaction", ng.HOLD_CITY_FACTION), ("HoldGenericDialogue", ng.HOLD_GENERIC_DIALOGUE),
                            ("HoldActivities", ng.HOLD_ACTIVITIES), ("HoldRadiant", ng.HOLD_RADIANT),
                            ("HoldShips", ng.HOLD_SHIPS), ("HoldSystem", ng.HOLD_SYSTEM)):
            block = cs[cs.index(name + " = {"):]
            self.assertEqual(re.findall(r'"([^"]+)"', block[:block.index("};")]), list(group))
        self.assertNotIn("DefaultMQ101Debug", cs)
        self.assertIn(f"DefaultDebugAfterHold = {ng.DEBUG_AFTER_HOLD};", cs)
        self.assertIn('ArgOrNull(a, "--mq101debug") is { } d ? float.Parse(d, CultureInfo.InvariantCulture) : null', cs)
        self.assertEqual(ng.DEFAULT_HOLD[2:4], ("MQ101PostQuest", "MQ_TutorialQuest_Misc04"))   # [4]: SQ_ENV, row 2b
        p = namespace()
        self.assertEqual(ng.tool_options(p), [])
        self.assertIsNone(ng.mq101debug_option(p))
        self.assertEqual(ng.debug_after_hold_option(p), 2)
        p.no_mq101debug = True
        self.assertEqual(ng.tool_options(p), ["--no-mq101debug"])
        self.assertIsNone(ng.mq101debug_option(p))
        p.no_mq101debug, p.mq101debug, p.looks = False, 8.0, False
        self.assertEqual(ng.tool_options(p), ["--mq101debug", "8.0", "--no-looks"])
        self.assertEqual(ng.mq101debug_option(p), 8.0)
        p.mq101debug, p.debug_after_hold = None, 0
        self.assertEqual(ng.tool_options(p), ["--debug-after-hold", "0", "--no-looks"])
        self.assertEqual(ng.debug_after_hold_option(p), 0)

    def test_the_hold_off_runs_twice(self):
        """Our own start (newgame_v11) never starts MQ101 when it goes on (only a stand-down's hand back asks it to, and
        each stand-down returns before the hold-off: test_our_quest_is_the_startup_quest), but MQ00 is start-game
        enabled and may start after our start (unverified), and stopping MQ101, if something started it, runs its stage
        9000, which starts MQ101PostQuest and MQ_TutorialQuest_Misc04 (PC read 19 Oct, NG-N1). Pass 1 runs in the start
        right after the move into the vault (never before it: a hand back must find Starfield's start as the game left
        it); pass 2 once the vault has loaded, before stage 10, so once. Each stop is logged with its pass."""
        psc = read(PSC)
        begin = psc[psc.index("Function Begin"):psc.index("Function StandDown")]
        self.assertLess(begin.index("entered = EnterVault(player)"), begin.index("HoldOffPass(1)"))
        self.assertLess(begin.rindex("StandDown(loading, "), begin.index("HoldOffPass(1)"))
        zero = psc[psc.index("    if stage == 0\n"):psc.index("    elseif stage == 10")]
        self.assertLess(zero.index("if !entered\n                StartTimer(1.0, 1)"), zero.index("HoldOffPass(2)"))
        self.assertLess(zero.index("HoldOffPass(2)"), zero.index("AdvanceTo(10)"))
        self.assertEqual((psc.count("HoldOffPass(1)"), psc.count("HoldOffPass(2)"), len(re.findall(r"^\s+HoldOffPass\(", psc, re.M))), (1, 1, 2))
        self.assertIn('" pass=" + pass', psc)
        for q in ng.HOLD_CORE:
            self.assertIn(q, psc)                            # the HoldOff property's doc names the core list
        for name in ("HoldCompanions", "HoldAudioTutorials", "HoldCityFaction", "HoldGenericDialogue", "HoldActivities",
                     "HoldRadiant", "HoldShips", "HoldSystem"):
            self.assertIn(name, psc)                         # and the row 5 groups by their writer list

    def test_script_names_and_log_name(self):
        cs = read(CS)
        self.assertIn(f'ScriptName = "{ng.SCRIPT}"', cs)
        self.assertIn(f'LooksScript = "{ng.LOOKS}"', cs)
        self.assertIn(f'Plugin = "{ng.PLUGIN}"', cs)
        self.assertRegex(read(PSC), rf"Scriptname {ng.SCRIPT} extends Quest")
        self.assertRegex(read(LOOKS), rf"Scriptname {ng.LOOKS} extends Quest")
        self.assertIn(f'SpecialScript = "{ng.SPECIAL}"', cs)
        self.assertRegex(read(SPECIAL), rf"Scriptname {ng.SPECIAL} extends Quest")
        self.assertIn(f'VersionScript = "{ng.VERSION}"', cs)
        self.assertRegex(read(VERSION), rf"Scriptname {ng.VERSION} extends ReferenceAlias")
        self.assertIn('"FO4SF_NEWGAME rt="', read(PSC))
        self.assertIn('"FO4SF_NEWGAME rt="', read(SPECIAL))
        self.assertIn('"FO4SF_NEWGAME rt="', read(VERSION))

    def test_merge_offset_is_the_measured_one(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
        import vmad_patch
        x, y, _ = vmad_patch.MERGE_MEASURED
        self.assertIn(f"MergeX = {x:g}f, MergeY = {y:g}f", read(CS))
        self.assertIn(f"MergeOffsetX = {x}", read(PSC))
        self.assertIn(f"MergeOffsetY = {y}", read(PSC))

    def test_the_guard_rule_matches_the_script(self):
        """The day limit is one game day (28 Oct): Starfield's clock starts at 8:00, so GameDaysPassed reads about
        0.3335 a second into a new game (two in-game runs), and the first build's 0.25 stood every new game down."""
        psc = read(PSC)
        self.assertIn("return days < MaxNewGameDays && level <= MaxNewGameLevel", psc)
        self.assertIn(f"float Property MaxNewGameDays = {ng.MAX_NEW_GAME_DAYS} Auto Const", psc)
        self.assertEqual(ng.MAX_NEW_GAME_DAYS, 1.0)
        self.assertTrue(ng.is_new_game(0.0, 1))
        self.assertTrue(ng.is_new_game(ng.NEW_GAME_DAYS_MEASURED, 1))   # what a Starfield new game reads (28 Oct)
        self.assertTrue(ng.is_new_game(0.333537, 1))
        self.assertFalse(ng.is_new_game(0.333537, 1, max_days=0.25))   # the first build's limit: stood down
        self.assertFalse(ng.is_new_game(1.0, 1))             # a game day in: not a fresh start
        self.assertFalse(ng.is_new_game(0.0, 2))
        self.assertFalse(ng.is_new_game(12.5, 30))           # the owner's test saves

    def test_the_debug_global_is_written_after_the_hold_off(self):
        """28 Oct, two in-game runs. Run 1: the plugin's MQ101Debug = 10 was the developer start at the pirate fight
        (MQ101 stage 0 entry 10, Item_10: SetStage 210 and 250), so the opening ran and our guard stood down at
        opening_stage=250. Run 2: the override of 2 matched no stage-0 entry, and since each matching entry's fragment
        is what moves the player into the game (the intro's Item_02: moveto CharGenStartMarker, WaitFor3dLoad), the
        new game never left its loading screen and our quest never started. So the build overrides nothing at the
        start (Starfield's intro places the player, the hold-off stops it) and the quest writes 2 into the global right
        after hold-off pass 1, with SetValueInt as MQ102's own fragment does; the guard line still reads the global.
        Since our own start (newgame_v11) MQ101 never runs: the write stays, in the start, after the move and pass 1, and a
        stand-down returns before it, so a hand back to MQ101 finds the global as the game left it."""
        self.assertIsNone(ng.DEFAULT_MQ101DEBUG)
        self.assertEqual((ng.DEBUG_INTRO, ng.DEBUG_START_PIRATES, ng.DEBUG_UNMATCHED, ng.DEBUG_AFTER_HOLD), (0, 10, 2, 2))
        psc, cs = read(PSC), read(CS)
        self.assertIn("GlobalVariable Property DebugGlobal Auto Const Mandatory", psc)
        self.assertIn(f"int Property DebugAfterHold = {ng.DEBUG_AFTER_HOLD} Auto Const", psc)
        self.assertNotIn("DebugValue", psc)
        self.assertIn('Obj("DebugGlobal", debugGlob.FormKey)', cs)
        self.assertIn('("DebugAfterHold", o.DebugAfterHold)', cs)
        self.assertIn('DebugGlobEdid = "MQ101Debug"', cs)
        # the guard's readings line comes before the verdict, inside the once-only start (Begin), and names the global
        begin = psc[psc.index("Function Begin"):psc.index("Function StandDown")]
        guard = begin.index('Trace("guard days=')
        self.assertLess(begin.index("if begun\n"), guard)
        self.assertLess(guard, begin.index("if !IsNewGame(days, level)"))
        line = begin[guard:begin.index("\n", guard)]
        for literal in ("days=", " level=", " opening_stage=", " opening_running=", " mq101debug=", " write_after_hold="):
            self.assertIn(literal, line)
        self.assertNotIn(" fresh=", line)                    # MQ101 never runs: no fresh-start verdict to log
        self.assertIn("DebugGlobal.GetValue()", line)
        # the write comes after the move and hold-off pass 1, before the timer and the 3D wait, inside its own if (0
        # writes nothing); every stand-down returns before it, and Begin runs once (a retried move never writes again)
        write = begin.index("DebugGlobal.SetValueInt(DebugAfterHold)")
        self.assertLess(begin.index("entered = EnterVault(player)"), begin.index("HoldOffPass(1)"))
        self.assertLess(begin.index("HoldOffPass(1)"), begin.index("if DebugAfterHold != 0"))
        self.assertNotIn("endif", begin[begin.index("if DebugAfterHold != 0"):write])
        self.assertLess(write, begin.index("StartTimer(1.0, 1)"))
        self.assertLess(begin.rindex("StandDown(loading, "), write)
        self.assertEqual(psc.count("SetValueInt("), 1)
        self.assertIn('Trace("mq101debug written=" + DebugGlobal.GetValue() + " was=" + was)', psc)
        self.assertEqual(ng.NATIVES[ng.SCRIPT]["GlobalVariable"], ["GetValue", "SetValueInt", "SetValue"])
        # the two values of 28 Oct stay buildable on purpose (--mq101debug) for experiments, never as the default
        self.assertIn('("debug10", idsPath, plain with { MQ101Debug = 10 })', cs)
        self.assertIn('("debug0", idsPath, plain with { MQ101Debug = 0 })', cs)
        self.assertIn('("nowrite", idsPath, plain with { DebugAfterHold = 0 })', cs)
        self.assertIn("a MQ101Debug override added at the second build's 2", cs)

    def test_our_quest_is_the_startup_quest(self):
        """Our own start (the owner's pick F, 29 Oct): the plugin overrides the DefaultObject StartupQuest_DO
        (Starfield.esm 00562D, MQ101 in vanilla) to name our quest, which is run once and no longer start-game enabled,
        so only a New Game should start it (supported hypothesis, the doc's section 1 step 2): an early level-1 save
        under six hours (the 21 Oct review's case on #393) should never, and the opening-stage test that kept it out
        has nothing left to judge. Nothing of Starfield's moves the player then (28 Oct run 2: nobody moved, the first
        load never ended), so the start does it: once, from OnQuestStarted (the event Roleplayers' Alternate Start
        handles on its startup quest) or OnQuestInit, whichever comes first. A start that is not a new game, or that
        moves nobody, stands down; while the game still loads it first asks MQ101 to start (StartNoWait: nothing of
        ours waits on MQ101's start-up, and whether its stage 0 then moves the player is unverified), before its own
        stage and before anything was held off or written. The deployment gate's start check passes exactly this
        override from a plugin of ours."""
        cs, psc = read(CS), read(PSC)
        # the writer: the override (Starfield's id and EditorID kept), the flags, the refusals, the check
        self.assertIn('public const string StartupEdid = "StartupQuest_DO";', cs)
        self.assertIn("public const uint StartupId = 0x00562D;", cs)
        self.assertIn("Data = new SF.QuestData { Flags = SF.Quest.Flag.RunOnce | SF.Quest.Flag.DisplaysInHud, Priority = 70 }", cs)
        self.assertEqual(cs.count("Flags = SF.Quest.Flag.StartGameEnabled"), 0)
        self.assertIn("var startupOver = (SF.DefaultObject)startup.DeepCopy();\n        startupOver.Object.SetTo(quest.FormKey);\n"
                      "        mod.DefaultObjects.Add(startupOver);", cs)
        self.assertIn('throw new Refusal($"Starfield.esm has no DFOB {StartupEdid}")', cs)
        self.assertIn("not the start this plugin replaces", cs)
        self.assertIn("!q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) && q.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce)", cs)
        self.assertIn("the plugin's DFOB are not one override of Starfield's {StartupEdid} naming QUST 0x{QuestId:X} (our own start)", cs)
        for mutation in ("start game enabled again", "the startup override removed", "the startup override names Starfield's opening again",
                         "the startup override names MQ00", "the startup override renamed", "a second DFOB override",
                         "our own new DFOB named StartupQuest_DO instead of the override", "an MQ101 override added"):
            self.assertIn(f'("{mutation}", m =>', cs)        # the selftest's check rejects each
        # the record is Starfield's 00562D, the one the gate knows (write refuses another id), and our quest is the
        # plugin's only QUST (an MQ101 override would change the start it replaces)
        self.assertIn("if (dobj.FormKey != new FormKey(SfEsm, StartupId))", cs)
        self.assertIn('("a Starfield.esm whose StartupQuest_DO is not 00562D", sfMovedStartup)', cs)
        self.assertIn('Need(plug.Quests.Count == 1, $"the plugin carries {plug.Quests.Count} QUST, not {QuestEdid} alone");', cs)
        # the gate: the record is the start record check_start knows, and our plugin is one it passes
        sys.path.insert(0, os.path.join(ROOT, "src"))
        from fo4sf.core import loadset, preflight
        self.assertIn((b"DFOB", 0x00562D, "StartupQuest_DO"), loadset.START_RECORDS)
        self.assertEqual(preflight.OWN_START, "StartupQuest_DO")
        self.assertTrue(loadset.ours(ng.PLUGIN))
        # the script: two start events, one start
        self.assertIn('Event OnQuestStarted()\n    Begin("OnQuestStarted")\nEndEvent', psc)
        self.assertIn('Event OnQuestInit()\n    Begin("OnQuestInit")\nEndEvent', psc)
        self.assertEqual(psc.count("    Begin("), 2)
        begin = psc[psc.index("Function Begin"):psc.index("Function StandDown")]
        code = begin[begin.index("    if begun"):]
        self.assertTrue(code.startswith('    if begun\n        if routed\n'
                                        '            Trace("start event " + route + " came after the start: nothing to do")\n'))
        self.assertIn("        return\n    endif\n    begun = true\n", code)
        self.assertIn('Trace("start route=" + route + " player_loaded=" + loaded + " cell=" + startCell + " loading=" + loading)', code)
        # still loading if either reading says so (29 Oct review on #588: one reading alone could miss the load, and a
        # stand-down that then hands nothing back leaves the first load for ever)
        self.assertIn("    bool loaded = player.Is3DLoaded()\n    Cell startCell = player.GetParentCell()\n", code)
        self.assertIn("    bool loading = !loaded || startCell == None\n", code)
        self.assertLess(code.index("bool loading = "), code.index('Trace("start route='))
        # the two stand-downs come before the hold-off and the write; a stand-down hands back only while the game loads
        self.assertLess(code.index('StandDown(loading, "not a new game")'), code.index("entered = EnterVault(player)"))
        self.assertLess(code.index('StandDown(loading, "no move into the vault")'), code.index("HoldOffPass(1)"))
        self.assertLess(code.index("HoldOffPass(1)"), code.index("DebugGlobal.SetValueInt(DebugAfterHold)"))
        self.assertEqual(code.count("StandDown("), 2)
        for why in ("not a new game", "no move into the vault"):      # each returns: nothing held off or written after
            self.assertIn(f'StandDown(loading, "{why}")\n        return\n    endif\n', code)
        self.assertNotIn("StandDown(loaded", psc)
        stand = psc[psc.index("Function StandDown"):psc.index("Function HandBack")]
        self.assertIn("Function StandDown(bool loading, string why)", stand)
        # the request goes out before our own stage (SetStage is latent, and Begin may run from OnQuestInit while our
        # quest still starts up), and it waits for nothing (29 Oct review on #588: a latent Start could hold the start)
        self.assertIn("    if loading\n        HandBack(why)\n    endif\n    AdvanceTo(1)\n    Stop()\n", stand)
        hand = psc[psc.index("Function HandBack"):psc.index("Function FadeIn")]
        self.assertEqual(psc.count("Opening.StartNoWait()"), 1)   # in HandBack alone
        self.assertIn("    bool requested = Opening.StartNoWait()\n", hand)
        self.assertNotIn(".Start()", psc)                      # no latent start anywhere
        self.assertEqual(psc.count("HandBack(why)"), 1)        # from StandDown alone
        self.assertIn('Trace("handed back: requested=" + requested + " opening starting=" + Opening.IsStarting()'
                      ' + " running=" + Opening.IsRunning() + " stage=" + Opening.GetStage())', hand)
        self.assertLess(hand.index('Trace("handing back'), hand.index("Opening.StartNoWait()"))
        self.assertIn("unverified", hand[:hand.index("}")].lower())   # the effect is not stated as fact
        self.assertIn('Obj("Opening", opening.FormKey)', cs)
        # the guard is days and level alone; the fresh-start rule and its stage are gone from the script and the tool
        self.assertIn("if !IsNewGame(days, level)", code)
        for gone in ("IsFreshStart", "SaveableStage", "Opening.IsCompleted()"):
            self.assertNotIn(gone, psc)
        self.assertFalse(hasattr(ng, "is_fresh_start") or hasattr(ng, "SAVEABLE_STAGE"))
        # the looks and SPECIAL scripts start their timers on either start event, so they run whichever fires
        for path, timer in ((LOOKS, 2), (SPECIAL, 3)):
            text = read(path)
            for event in ("OnQuestStarted", "OnQuestInit"):
                self.assertRegex(text, rf"Event {event}\(\)\n    StartTimer\(1\.0, {timer}\)\s")

    def test_the_second_start_event_is_logged_after_the_route_line(self):
        """The two start events can both run Begin: the second arrives while the first is in a call (the log, the
        player), which releases the script's lock. Its line is written at once only when the start's route line is
        (routed); otherwise it is kept (lateRoute) and the start writes it right after that line, so a log always names
        the event that ran the start first (29 Oct review on #588). The flag is set right after the route line with no
        call before the start reads lateRoute, so the two threads cannot both miss it."""
        psc = read(PSC)
        self.assertIn('bool routed = false', psc)
        self.assertIn('string lateRoute = ""', psc)
        begin = psc[psc.index("Function Begin"):psc.index("Function StandDown")]
        code = begin[begin.index("    if begun"):]
        self.assertTrue(code.startswith(
            '    if begun\n        if routed\n            Trace("start event " + route + " came after the start: nothing to do")\n'
            '        else\n            lateRoute = route'))
        route_line = code.index('    Trace("start route=')
        flag = code.index("\n    routed = true\n")
        late = code.index('\n    if lateRoute != ""\n        Trace("start event " + lateRoute + " came after the start: nothing to do")\n    endif\n')
        self.assertLess(route_line, flag)
        self.assertEqual(flag + len("\n    routed = true"), late)   # nothing between the flag and its reading
        self.assertEqual((psc.count("routed = true"), psc.count("lateRoute = route")), (1, 1))

    def test_every_native_the_script_calls_is_prechecked(self):
        psc = read(PSC)
        calls = set(re.findall(r"\.(\w+)\(", psc)) | set(re.findall(r"^\s*(RegisterFor\w+|StartTimer|AddInventoryEventFilter)\(", psc, re.M))
        listed = {f for bases in ng.NATIVES[ng.SCRIPT].values() for f in bases}
        own = set(re.findall(r"^\s*\w*\s*Function\s+(\w+)", psc, re.M))
        # GetPositionY/Z share GetPositionX's script; cross-slice FO4SF quest calls go through CastAs + CallFunction
        calls |= set(re.findall(r"^Event (?:\w+\.)?(On\w+)\(", psc, re.M)) - {"OnTimer"}
        fo4sf_methods = {"GetPositionY", "GetPositionZ"}
        missing = calls - listed - own - fo4sf_methods
        self.assertEqual(missing, set())
        self.assertTrue({"OnQuestStarted", "OnQuestInit", "FadeOutGame", "WaitFor3DLoad", "StartNoWait", "IsStarting"} <= calls)
        self.assertNotIn("Start", ng.NATIVES[ng.SCRIPT]["Quest"])   # the hand back waits for nothing
        # Starfield's Utility.psc has no IsInMenuMode (precheck on the PC, 2026-10-19): neither script may call it
        self.assertNotIn("IsInMenuMode(", psc)
        self.assertNotIn("IsInMenuMode(", read(LOOKS))
        # the looks script: every dotted call, its bare self calls (RegisterForMenuOpenCloseEvent, StartTimer) and the
        # event it handles must be listed, or the precheck could pass a script that does not compile
        looks = read(LOOKS)
        looks_calls = set(re.findall(r"\.(\w+)\(", looks)) | set(re.findall(r"^\s*(RegisterFor\w+|StartTimer)\(", looks, re.M))
        looks_calls |= set(re.findall(r"^Event (On\w+)\(", looks, re.M)) - {"OnTimer"}
        looks_own = set(re.findall(r"^\s*\w*\s*Function\s+(\w+)", looks, re.M))
        looks_listed = {f for bases in ng.NATIVES[ng.LOOKS].values() for f in bases}
        self.assertEqual(looks_calls - looks_listed - looks_own - {"NoteLooksStage20", "IsPreworldLooksHandled"}, set())
        self.assertEqual(set(ng.NATIVES[ng.LOOKS]["ScriptObject"]), {"StartTimer", "RegisterForMenuOpenCloseEvent", "OnMenuOpenCloseEvent"})
        # the SPECIAL script the same way; its Actor.SetValue / GetValue are the unverified pair the precheck reads
        special = read(SPECIAL)
        special_calls = set(re.findall(r"\.(\w+)\(", special)) | set(re.findall(r"^\s*(RegisterFor\w+|StartTimer)\(", special, re.M))
        special_calls |= set(re.findall(r"^Event (On\w+)\(", special, re.M)) - {"OnTimer"}
        special_own = set(re.findall(r"^\s*[\w\[\]]*\s*Function\s+(\w+)", special, re.M))
        special_listed = {f for bases in ng.NATIVES[ng.SPECIAL].values() for f in bases}
        self.assertEqual(special_calls - special_listed - special_own - {"GetPositionY", "GetPositionZ"}, set())
        self.assertEqual(set(ng.NATIVES[ng.SPECIAL]["Actor"]), {"SetValue", "GetValue"})
        self.assertNotIn("IsInMenuMode(", special)
        self.assertNotIn("Function Reset(", special)          # Quest.psc has Reset(); Papyrus has no overloads
        # the version script the same way; its two events (OnInit, OnPlayerLoadGame) are declarations the precheck
        # looks up in ScriptObject.psc and ReferenceAlias.psc
        version = read(VERSION)
        version_calls = set(re.findall(r"\.(\w+)\(", version)) | set(re.findall(r"^Event (On\w+)\(", version, re.M))
        version_own = set(re.findall(r"^\s*[\w\[\]]*\s*Function\s+(\w+)", version, re.M))
        version_listed = {f for bases in ng.NATIVES[ng.VERSION].values() for f in bases}
        self.assertEqual(version_calls - version_listed - version_own, set())
        self.assertEqual(ng.NATIVES[ng.VERSION]["ReferenceAlias"], ["OnPlayerLoadGame"])
        self.assertEqual(ng.NATIVES[ng.VERSION]["ScriptObject"], ["OnInit"])
        self.assertNotIn("IsInMenuMode(", version)

    def test_declared_properties_parser(self):
        text = ("Quest[] Property A Auto Const Mandatory\nfloat Property B = 0.25 Auto Const\n"
                "string Property C = \"x.esm\" Auto Const\n  int Property D Auto Const Mandatory\n")
        self.assertEqual(ng.declared_properties(text), {"A": True, "B": False, "C": False, "D": True})


# Starfield's Game.psc declarations (PC read, 19 Oct): the fade in turns saving and the HUD on with both
CHARGEN = ("Function SetInChargen(bool abDisableSaving, bool abDisableWaiting, bool abShowControlsDisabledMessage) "
           "native global\nFunction SetCharGenHUDMode(int aiCGHUDMode) native global\n"
           "Function ShowFirstPersonGeometry(bool abShow = true) native global\n")
# Game.FadeOutGame, our own start's fade in: the five-argument call Roleplayers' Alternate Start makes (FO4's parameter
# names; Starfield's declaration is what the precheck reads)
FADE = ("Function FadeOutGame(bool abFadingOut, bool abBlackFade, float afSecsBeforeFade, float afFadeDuration, "
        "bool abStayFaded = false) native global\n")
FAST_READ = ("bool Function IsFastTravelEnabled() native global\n"
             "Function FastTravel(ObjectReference akDestination) native global\n")
AUTOSAVE = "Function RequestAutoSave() native global\n"
# Actor.psc's declarations the quest script itself needs: the guard's GetLevel, the inventory reset's EquipItem /
# IsEquipped and the O2 fill's ModValue / GetValue (FO4's signatures; Starfield's are what the precheck reads: its
# Actor.psc declares GetValue on a parent, 28 Oct). ObjectReference's RemoveAllItems, GetItemCount and AddItem are
# generated from NATIVES below
ACTOR_O2 = ("Function ModValue(ActorValue akAV, float afAmount) native\n"
            "float Function GetValue(ActorValue akAV) native\n")
ACTOR_CORE = ("int Function GetLevel() native\n"
              "Function EquipItem(Form akItem, bool abPreventRemoval = false, bool abSilent = false) native\n"
              "bool Function IsEquipped(Form akItem) native\n"
              "bool Function IsDead() native\n"
              "Function AddToFaction(Faction akFaction) native\n"
              "Event OnPlayerLoadGame()\nEndEvent\n"
              "Event OnDying(ObjectReference akKiller)\nEndEvent\n" + ACTOR_O2)


def fake_zip(path, game=None, utility=None, extra=None, scriptobject=None, actor=None, referencealias=None, debug=None,
             objectreference=None, quest=None, animation=True, remote=True, inventory_filter=True, dynamic_cast=True):
    base = {
        # Actor.psc: GetLevel (the guard), EquipItem / IsEquipped (the inventory reset's suit; FO4's signatures,
        # unverified in Starfield) and FO4's SetValue / GetValue (the SPECIAL script; unverified in Starfield)
        "Actor": actor if actor is not None else "Scriptname Actor extends ObjectReference\n" + ACTOR_CORE +
                                                 "Function SetValue(ActorValue akAV, float afValue) native\n"
                                                 "float Function GetValue(ActorValue akAV) native\n",
        # Debug.psc: CenterOnCell with FO4's signature (the temporary-anchor mode); Starfield's declaration is what the
        # precheck reads, unverified until then
        "Debug": debug if debug is not None else
                 "Function OpenUserLog(string a) native global\nbool Function TraceUser(string a, string b) native global\n"
                 "Function Notification(string a) native global\nFunction CenterOnCell(string asCellname) native global\n",
        "Game": game if game is not None else "Actor Function GetPlayer() native global\n"
                                              "Form Function GetFormFromFile(int a, string b) native global\n"
                                              "Function ShowRaceMenu(ObjectReference akMenuTarget = None, int uiMode = 0) native global\n"
                                              + CHARGEN + FADE + FAST_READ + AUTOSAVE,
        "GlobalVariable": "float Function GetValue() native\nFunction SetValueInt(int aiValue) native\nFunction SetValue(float afNewValue) native\n",
        "InputEnableLayer": "Scriptname InputEnableLayer extends ScriptObject\nInputEnableLayer Function Create() native global\nFunction EnableHandscanner(bool a = true) native\n",
        "Message": "int Function Show(" + ", ".join(f"float afArg{i} = 0.0" for i in range(1, 10)) + ") native\n",
        "ObjectReference": objectreference if objectreference is not None else
                           "\n".join(f"Function {f}() native" for f in ng.NATIVES[ng.SCRIPT]["ObjectReference"]),
        "Quest": quest if quest is not None else "\n".join(f"Function {f}() native" for f in ng.NATIVES[ng.SCRIPT]["Quest"]),
        # ScriptObject.psc (PC read 19 Oct): RegisterForMenuOpenCloseEvent is native; the event's signature is FO4's
        "ScriptObject": scriptobject if scriptobject is not None else
                        "Function StartTimer(float a, int b = 0) native\nFunction RegisterForMenuOpenCloseEvent(string asMenuName) native\n"
                        "Function UnregisterForMenuOpenCloseEvent(string asMenuName) native\n"
                        "Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)\nEndEvent\nEvent OnInit()\nEndEvent\n",
        # ReferenceAlias.psc (PC read 19 Oct, NG-L3): OnPlayerLoadGame, the version script's event
        "ReferenceAlias": referencealias if referencealias is not None else
                          "Scriptname ReferenceAlias extends Alias\nEvent OnPlayerLoadGame()\nEndEvent\n",
        "Utility": utility if utility is not None else "float Function GetCurrentRealTime() native global\n"
                                                       "bool Function IsInMenuMode() native global\nFunction Wait(float a) native global\n",
    }
    if animation:
        base["ScriptObject"] += ("\nFunction RegisterForAnimationEvent(ObjectReference source, string name) native\n"
                                 "Function UnregisterForAnimationEvent(ObjectReference source, string name) native\n"
                                 "Event OnAnimationEvent(ObjectReference source, string name)\nEndEvent\n")
    if remote:
        base["ScriptObject"] += ("\nbool Function RegisterForRemoteEvent(ScriptObject source, string name) native\n"
                                 "Function UnregisterForRemoteEvent(ScriptObject source, string name) native\n")
    if inventory_filter:
        base["ScriptObject"] += "\nFunction AddInventoryEventFilter(Form akFilter) native\n"
    if dynamic_cast:
        base["ScriptObject"] += ("\nScriptObject Function CastAs(string asScriptName) native\n"
                                 "Var Function CallFunction(string asFuncName, Var[] aParams) native\n")
    with zipfile.ZipFile(path, "w") as z:
        for name, text in base.items():
            z.writestr(f"Scripts/Source/{name}.psc", text)
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "")
        z.writestr("Scripts/Source/Fragments/Quests/QF_MQ101_00003448.psc",
                   extra if extra is not None else "if MQ101Debug.GetValue() == 8\n  ; start in the spaceport\nendif\n")


class PrecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_all_found(self):
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z)
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], [])
        self.assertTrue(all(r["natives"][ng.LOOKS].values()))
        self.assertTrue(all(r["natives"][ng.SPECIAL].values()))
        self.assertTrue(all(r["natives"][ng.VERSION].values()))
        self.assertEqual(r["drop"], [])
        self.assertEqual(len(r["mq101debug"]), 1)
        self.assertIn("QF_MQ101_00003448.psc:1:", r["mq101debug"][0])

    def test_an_inherited_declaration_counts(self):
        """28 Oct: Starfield's Actor.psc declares neither SetValue nor GetValue (Install's precheck), yet the Papyrus
        compiler built FO4SF_NewGameSpecial for newgame_v7, so the two are declared on a parent of Actor. The precheck
        follows "Scriptname X extends Y" the way the compiler resolves the call; a declaration nowhere in the chain still
        drops the script, and a chain that loops ends."""
        z = os.path.join(self.tmp, "cr.zip")
        objref = ("Scriptname ObjectReference extends Form\n"
                  + "\n".join(f"Function {f}() native" for f in ng.NATIVES[ng.SCRIPT]["ObjectReference"])
                  + "\nFunction SetValue(ActorValue akAV, float afValue) native\nfloat Function GetValue(ActorValue akAV) native\n")
        fake_zip(z, actor="Scriptname Actor extends ObjectReference\n" + ACTOR_CORE, objectreference=objref)
        r = ng.precheck_zip(z)
        self.assertTrue(r["natives"][ng.SPECIAL]["Actor.SetValue"])
        self.assertTrue(r["natives"][ng.SPECIAL]["Actor.GetValue"])
        self.assertEqual(r["drop"], [])
        fake_zip(z, actor="Scriptname Actor extends ObjectReference\n" + ACTOR_CORE)
        r = ng.precheck_zip(z)
        self.assertFalse(r["natives"][ng.SPECIAL]["Actor.SetValue"])
        self.assertEqual(r["drop"], ["--no-special"])
        self.assertEqual(r["missing_core"], [])              # the quest script's Actor natives are in Actor.psc itself
        # the O2 fill's GetValue / ModValue found on the parent count for the core script too
        bare = "Scriptname Actor extends ObjectReference\n" + ACTOR_CORE.replace(ACTOR_O2, "")
        fake_zip(z, actor=bare, objectreference=objref + ACTOR_O2)
        self.assertEqual(ng.precheck_zip(z)["missing_core"], [])
        loop = {"actor": "Scriptname Actor extends ObjectReference\n", "objectreference": "Scriptname ObjectReference extends Actor\n"}
        self.assertFalse(ng.declares(loop, "Actor", "SetValue"))
        self.assertEqual(ng.parent_of("Scriptname Actor extends ObjectReference\n"), "ObjectReference")
        self.assertIsNone(ng.parent_of("Scriptname ScriptObject\n"))

    def test_missing_show_race_menu_only_drops_the_looks(self):
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, game="Actor Function GetPlayer() native global\nForm Function GetFormFromFile(int a, string b) native global\n"
                    + CHARGEN + FADE + FAST_READ + AUTOSAVE)
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], ["Game.ShowRaceMenu"])
        self.assertFalse(r["natives"][ng.LOOKS]["Game.ShowRaceMenu"])
        out = os.path.join(self.tmp, "p.json")
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            rc = ng.main(["precheck", "--content-resources", z, "--out", out])
        self.assertEqual(rc, 1)
        self.assertIn("--no-looks", o.getvalue())
        self.assertNotIn("--no-special", o.getvalue())
        self.assertTrue(os.path.isfile(out))

    def test_missing_set_value_only_drops_the_special(self):
        """Actor.SetValue is what the SPECIAL script needs beyond the quest's natives (GetValue is the quest's own since
        the O2 fill reads its value): a source set without it fails only that script, and the precheck says
        --no-special."""
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, actor="Scriptname Actor extends ObjectReference\n" + ACTOR_CORE)
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], [])
        self.assertFalse(r["natives"][ng.SPECIAL]["Actor.SetValue"])
        self.assertTrue(r["natives"][ng.SPECIAL]["Actor.GetValue"])
        self.assertTrue(all(r["natives"][ng.LOOKS].values()))
        self.assertEqual(r["drop"], ["--no-special"])
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["precheck", "--content-resources", z]), 0)
        self.assertIn("FO4SF_NewGameSpecial cannot compile: stage with --no-special", o.getvalue())
        self.assertNotIn("--no-looks", o.getvalue())

    def test_missing_player_load_event_only_drops_the_version(self):
        """OnPlayerLoadGame on ReferenceAlias (PC read 19 Oct) is what the version script needs beyond the quest's
        natives: a source set without it fails only that script, and the precheck says --no-version."""
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, referencealias="Scriptname ReferenceAlias extends Alias\n")
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], [])
        self.assertFalse(r["natives"][ng.VERSION]["ReferenceAlias.OnPlayerLoadGame"])
        self.assertTrue(r["natives"][ng.VERSION]["ScriptObject.OnInit"])
        self.assertTrue(all(r["natives"][ng.LOOKS].values()))
        self.assertTrue(all(r["natives"][ng.SPECIAL].values()))
        self.assertEqual(r["drop"], ["--no-version"])
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["precheck", "--content-resources", z]), 0)
        self.assertIn("FO4SF_NewGameVersion cannot compile: stage with --no-version", o.getvalue())
        self.assertNotIn("--no-looks", o.getvalue())
        self.assertNotIn("--no-special", o.getvalue())

    def test_missing_core_native_fails(self):
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, utility="Function Wait(float a) native global\n")
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], ["Utility.GetCurrentRealTime"])
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(ng.main(["precheck", "--content-resources", z]), 1)

    def test_missing_inventory_natives_fail_the_core_script(self):
        """The inventory reset lives in the quest script (its ClearInventory property is on by default, and
        --keep-inventory builds still compile it): an Actor.psc without EquipItem / IsEquipped is a core miss, not an optional drop."""
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, actor="Scriptname Actor extends ObjectReference\nint Function GetLevel() native\n"
                          "bool Function IsDead() native\n"
                          "Function AddToFaction(Faction akFaction) native\nEvent OnPlayerLoadGame()\nEndEvent\n"
                          "Event OnDying(ObjectReference akKiller)\nEndEvent\n" + ACTOR_O2 +
                          "Function SetValue(ActorValue akAV, float afValue) native\nfloat Function GetValue(ActorValue akAV) native\n")
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], ["Actor.EquipItem", "Actor.IsEquipped"])
        self.assertEqual(r["drop"], [])
        self.assertTrue(r["natives"][ng.SCRIPT]["ObjectReference.RemoveAllItems"])
        self.assertTrue(r["natives"][ng.SCRIPT]["ObjectReference.GetItemCount"])
        self.assertTrue(r["natives"][ng.SCRIPT]["ObjectReference.AddItem"])
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["precheck", "--content-resources", z]), 1)
        self.assertIn("MISSING  FO4SF_NewGameQuest: Actor.EquipItem", o.getvalue())

    def test_missing_center_on_cell_fails_the_core_script(self):
        """Debug.CenterOnCell is the temporary-anchor mode's native in the quest script (the property is off in a
        persistent-anchor build, but the script must compile): a Debug.psc without it is a core miss, not an optional
        drop."""
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, debug="Function OpenUserLog(string a) native global\nbool Function TraceUser(string a, string b) native global\n"
                          "Function Notification(string a) native global\n")
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], ["Debug.CenterOnCell"])
        self.assertEqual(r["drop"], [])
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["precheck", "--content-resources", z]), 1)
        self.assertIn("MISSING  FO4SF_NewGameQuest: Debug.CenterOnCell", o.getvalue())

    def test_missing_start_natives_fail_the_core_script(self):
        """Our own start's natives: Game.FadeOutGame (the fade in once the 3D is in; what ends the first load is open,
        docs section 13) and the start event OnQuestStarted. A Game.psc without the first is a core miss; a Quest.psc
        without the second is too, and it drops the looks and SPECIAL scripts as well, which start their timers on it."""
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, game="Actor Function GetPlayer() native global\nForm Function GetFormFromFile(int a, string b) native global\n"
                         "Function ShowRaceMenu(ObjectReference akMenuTarget = None, int uiMode = 0) native global\n" + CHARGEN + FAST_READ + AUTOSAVE)
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], ["Game.FadeOutGame"])
        self.assertEqual(r["drop"], [])
        quest = "\n".join(f"Function {f}() native" for f in ng.NATIVES[ng.SCRIPT]["Quest"] if f != "OnQuestStarted")
        fake_zip(z, quest=quest)
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], ["Quest.OnQuestStarted"])
        self.assertEqual(r["drop"], ["--no-looks", "--no-special"])
        fake_zip(z, quest=quest + "\nEvent OnQuestStarted()\nEndEvent\n")
        self.assertEqual(ng.precheck_zip(z)["missing_core"], [])   # an Event declaration counts, as for OnMenuOpenCloseEvent
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            fake_zip(z, quest=quest)
            self.assertEqual(ng.main(["precheck", "--content-resources", z]), 1)
        self.assertIn("MISSING  FO4SF_NewGameQuest: Quest.OnQuestStarted", o.getvalue())

    def test_has_function_needs_the_declaration(self):
        self.assertTrue(ng.has_function("bool Function IsInMenuMode() native global", "IsInMenuMode"))
        self.assertFalse(ng.has_function("; IsInMenuMode() is not here\nFunction IsInMenuModeX()", "IsInMenuMode"))
        self.assertTrue(ng.has_function("Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)", "OnMenuOpenCloseEvent"))
        self.assertFalse(ng.has_function("Function RegisterForMenuOpenCloseEvent(string a) native", "OnMenuOpenCloseEvent"))

    def test_missing_menu_event_only_drops_the_looks(self):
        """The creator's close is awaited with RegisterForMenuOpenCloseEvent / OnMenuOpenCloseEvent (ScriptObject,
        PC read 19 Oct): both FO4SF_NewGameQuest (S5/X3) and FO4SF_NewGameLooks require them."""
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, scriptobject="Function StartTimer(float a, int b = 0) native\n")
        r = ng.precheck_zip(z)
        self.assertEqual(
            r["missing_core"],
            [
                "ScriptObject.RegisterForMenuOpenCloseEvent",
                "ScriptObject.UnregisterForMenuOpenCloseEvent",
                "ScriptObject.OnMenuOpenCloseEvent",
            ],
        )
        self.assertFalse(r["natives"][ng.LOOKS]["ScriptObject.RegisterForMenuOpenCloseEvent"])
        self.assertFalse(r["natives"][ng.LOOKS]["ScriptObject.OnMenuOpenCloseEvent"])
        self.assertTrue(r["natives"][ng.LOOKS]["ScriptObject.StartTimer"])
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["precheck", "--content-resources", z]), 1)
        self.assertIn("--no-looks", o.getvalue())

    def test_task0a_natives_ownership_in_precheck(self):
        self.assertIn("FastTravel", ng.NATIVES[ng.SCRIPT]["Game"])
        self.assertNotIn("EnableFastTravel", ng.NATIVES[ng.SCRIPT]["Game"])
        for obj_native in ("AddToMap", "EnableFastTravel", "Reset"):
            self.assertIn(obj_native, ng.NATIVES[ng.SCRIPT]["ObjectReference"])
        z = os.path.join(self.tmp, "cr.zip")
        obj_without_eft = "\n".join(
            f"Function {f}() native" for f in ng.NATIVES[ng.SCRIPT]["ObjectReference"] if f != "EnableFastTravel"
        )
        fake_zip(
            z,
            game="Actor Function GetPlayer() native global\nForm Function GetFormFromFile(int a, string b) native global\n"
                 "Function ShowRaceMenu(ObjectReference akMenuTarget = None, int uiMode = 0) native global\n"
                 "Function EnableFastTravel(bool abEnable = true) native global\n"
                 + CHARGEN + FADE + FAST_READ + AUTOSAVE,
            objectreference=obj_without_eft,
        )
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], ["ObjectReference.EnableFastTravel"])


# the guard's stand-down line as the quest script writes it since our own start (days, level, and whether the game was
# still loading: a New Game+ here, which hands back); test_the_stand_down_line_is_the_scripts holds the fixture to the script
STOOD_DOWN = "not a new game: days=0.333530 level=12 loading=true: standing down"
# a New Game+ in our own start's log after its init line: the route, the guard, the stand-down while the game loads, the
# hand back's two lines, then our stage 1 (test_our_own_start_lines_are_the_scripts reads this log and holds the lines
# to the script's traces)
NG_PLUS = ("start route=OnQuestStarted player_loaded=false cell=None loading=true",
           "guard days=0.333530 level=12 opening_stage=0 opening_running=false mq101debug=0.000000 write_after_hold=2",
           STOOD_DOWN,
           "handing back to Starfield's start: not a new game; mq101debug=0.000000",
           "handed back: requested=true opening starting=true running=false stage=0",
           "stage 1 by=trigger")


class LogTests(unittest.TestCase):
    # a shortened run: the lines the reader takes, in the order and at the times the scripts write them, but only one
    # of the status lines the quest writes every 5 ticks; of the lines the reader ignores, some are kept and the rest
    # left out (the looks menu's, the terminal's position)
    LINES = [
        "[10/20/2026 - 09:00:00AM] FO4SF_NEWGAME rt=5.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915",
        "[10/20/2026 - 09:00:00AM] FO4SF_NEWGAME rt=5.0 version saved=1.000000 (new game)",
        "[10/20/2026 - 09:00:00AM] FO4SF_NEWGAME rt=5.0 start route=OnQuestStarted player_loaded=false cell=None loading=true",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.0 guard days=0.333530 level=1 opening_stage=0 opening_running=false mq101debug=0.000000 write_after_hold=2",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.0 enter vault ok=False pos=0 0 0 target=11 20 1 cell=None",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.0 held off [Quest < (00012345)>] running_after=False pass=1",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.0 not running [Quest < (00054321)>] pass=1",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.0 not running [Quest < (00013579)>] pass=1",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.0 not running [Quest < (00024680)>] pass=1",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.0 hold-off pass 1 stopped=1 of 4",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.0 mq101debug written=2.000000 was=0.000000",
        "[10/20/2026 - 09:00:01AM] FO4SF_NEWGAME rt=6.1 start event OnQuestInit came after the start: nothing to do",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 3d wait over loaded=true",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 fade in by=start loaded=true cell=[Cell <FO4Port_Vault111Cryo>]; saving and HUD on",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 enter vault confirmed after the load pos=11 20 1 cell=[Cell <FO4Port_Vault111Cryo>]",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 not running [Quest < (00012345)>] pass=2",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 not running [Quest < (00054321)>] pass=2",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 held off [Quest < (00013579)>] running_after=False pass=2",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 not running [Quest < (00024680)>] pass=2",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 hold-off pass 2 stopped=1 of 4",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 inventory cleared removed=14 left=2",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 vault suit equipped [Armor < (0A000820)>] worn=True",
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 stage 10 by=trigger",
        "[10/20/2026 - 09:00:03AM] FO4SF rt=7.5 pos=1 2 3 (another log's line)",
        "[10/20/2026 - 09:00:03AM] FO4SF_NEWGAME rt=8.0 pod settle ok=true pos=11 20 1 dx=0.0 dy=0.0 drop=0.0",
        "[10/20/2026 - 09:00:04AM] FO4SF_NEWGAME rt=9.0 start choice button=0",
        "[10/20/2026 - 09:00:40AM] FO4SF_NEWGAME rt=45.0 looks done: creator closed",
        "[10/20/2026 - 09:00:40AM] FO4SF_NEWGAME rt=45.0 stage 20 by=scene",      # the looks script's Done, in its order
        "[10/20/2026 - 09:00:50AM] FO4SF_NEWGAME rt=55.0 terminal prompt button=1",
        "[10/20/2026 - 09:00:50AM] FO4SF_NEWGAME rt=55.0 special later",
        "[10/20/2026 - 09:00:58AM] FO4SF_NEWGAME rt=58.0 terminal prompt button=0",
        "[10/20/2026 - 09:00:59AM] FO4SF_NEWGAME rt=59.0 special set S=10 P=2 E=2 C=2 I=2 A=2 L=8 readback=10.000000 8.000000",
        "[10/20/2026 - 09:01:00AM] FO4SF_NEWGAME rt=60.0 status stage=20 pos=50 10 0 cell=x world=None",
        "[10/20/2026 - 09:02:00AM] FO4SF_NEWGAME rt=120.0 elevator prompt button=0",
        "[10/20/2026 - 09:02:00AM] FO4SF_NEWGAME rt=120.1 surface moveto pos=-1250 1290 110 world=[WorldSpace <x>] moves=1",
        "[10/20/2026 - 09:02:01AM] FO4SF_NEWGAME rt=121.1 surface setposition ok=true set=1 pos=-2450 -1410 110 target=-2450 -1410 110",
        "[10/20/2026 - 09:02:01AM] FO4SF_NEWGAME rt=121.1 stage 40 by=trigger",
        "[10/20/2026 - 09:02:04AM] FO4SF_NEWGAME rt=124.2 landed z=110.0",          # CheckLanding: 3 s after the arrival
        "[10/20/2026 - 09:02:04AM] FO4SF_NEWGAME rt=124.2 stage 200 by=trigger",
    ]

    def test_summary(self):
        s = ng.summarize(self.LINES)
        self.assertEqual(s["stages"], [10, 20, 40, 200])
        self.assertEqual(s["stages_named"], [f"{n} {ng.STAGE_CONTRACT[n]}" for n in (10, 20, 40, 200)])
        self.assertEqual(s["looks_done"], "creator closed")
        self.assertEqual(s["special"], "set S=10 P=2 E=2 C=2 I=2 A=2 L=8 readback=10.000000 8.000000")
        self.assertEqual(s["held_off"], ["[Quest < (00012345)>]", "[Quest < (00013579)>]"])
        self.assertEqual(s["held_off_by_pass"], {"1": ["[Quest < (00012345)>]"], "2": ["[Quest < (00013579)>]"]})
        self.assertTrue(s["entered_vault"])                 # the move's own check said no; the timer confirmed it after the load
        self.assertTrue(s["surfaced"].startswith("surface setposition ok=true set=1 "))
        self.assertEqual(s["pod_settle"], "ok=true pos=11 20 1 dx=0.0 dy=0.0 drop=0.0")
        self.assertTrue(s["landed"])
        self.assertFalse(s["fell"])
        self.assertFalse(s["stood_down"])
        self.assertIsNone(s["stand_down"])
        self.assertIsNone(s["handed_back"])
        self.assertIsNone(s["handing_back"])
        self.assertIsNone(s["waiting_3d"])                   # the 3D came in time: no wait line
        self.assertEqual(s["start"], "OnQuestStarted player_loaded=false cell=None loading=true")
        self.assertEqual(s["start_events"], ["OnQuestStarted", "OnQuestInit"])
        self.assertEqual(s["start_wait"], "loaded=true")
        self.assertEqual(s["fade"], "by=start loaded=true cell=[Cell <FO4Port_Vault111Cryo>]; saving and HUD on")
        self.assertEqual(s["guard"], "days=0.333530 level=1 opening_stage=0 opening_running=false mq101debug=0.000000 write_after_hold=2")
        self.assertEqual(s["mq101debug_written"], "2.000000 was=0.000000")
        self.assertIn("stage=20", s["last_status"])
        self.assertEqual(s["version_saved"], "1.000000")
        self.assertIsNone(s["version_load"])                 # no save was loaded in this run
        self.assertFalse(s["version_mismatch"])
        self.assertEqual(s["inventory_cleared"], "removed=14 left=2")
        self.assertEqual(s["vault_suit"], "equipped [Armor < (0A000820)>] worn=True")
        self.assertIsNone(s["centered"])                     # a persistent-anchor run never centers

    def test_centered_line(self):
        """The temporary-anchor mode: the first centering line is the summary's "centered" (the bound's second centering
        and its failure lines change nothing); the lines are the ones the script writes."""
        psc = read(PSC)
        self.assertIn('Trace("centered on " + VaultCell + " attempt=" + centered + " tick=" + centerTries + ": temporary anchor " + VaultPlugin + ":" + VaultAnchorId + " does not resolve before the cell loads")', psc)
        head = "[x] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:4920 anchor_temporary=True core=FO4TerrainCore.esm:685915\n"
        first = "centered on FO4Port_Vault111Cryo attempt=1 tick=1: temporary anchor FO4Port.esm:4920 does not resolve before the cell loads"
        code, s = self.run_log(head + f"[x] FO4SF_NEWGAME rt=7.0 {first}\n"
                                      "[x] FO4SF_NEWGAME rt=8.0 enter vault ok=True pos=11 20 1 target=11 20 1 cell=[Cell <FO4Port_Vault111Cryo>]\n")
        self.assertEqual(s["centered"], first[len("centered on "):])
        self.assertTrue(s["entered_vault"])
        code, s = self.run_log(head + f"[x] FO4SF_NEWGAME rt=7.0 {first}\n"
                                      "[x] FO4SF_NEWGAME rt=38.0 centered on FO4Port_Vault111Cryo attempt=2 tick=31: temporary anchor FO4Port.esm:4920 does not resolve before the cell loads\n"
                                      "[x] FO4SF_NEWGAME rt=47.0 vault anchor FO4Port.esm:4920 does not resolve after 40 ticks and 2 centerings on FO4Port_Vault111Cryo: the temporary-anchor start failed\n")
        self.assertEqual(s["centered"], first[len("centered on "):])
        self.assertIsNone(s["entered_vault"])
        self.assertEqual(code, 1)

    def test_stage_20_is_traced_by_whichever_script_sets_it(self):
        """Codex review on #393 (P2): the quest's AdvanceTo is where "stage <n> by=..." is traced, and the looks script sets
        stage 20 itself (SetStage, not AdvanceTo), tracing "stage 20 by=<scene|trigger>" to the same log in the same format
        right after SetStage(20); the summary reads it, and a looks run without it would still miss the stage."""
        quest, looks = read(PSC), read(LOOKS)
        self.assertIn('Trace("stage " + n + " by=" + by)', quest[quest.index("Function ApplyStage"):quest.index("EndFunction", quest.index("Function ApplyStage"))])
        done = looks[looks.index("Function Done"):]
        done = done[:done.index("EndFunction")]
        self.assertLess(done.index('Trace("looks done: " + how)'), done.index("SetStage(20)"))
        self.assertLess(done.index("SetStage(20)"), done.index('Trace("stage 20 by=" + by)'))
        # the same log and the same line format as the quest's Trace
        self.assertIn('string LogName = "fo4sf_newgame"', quest)
        self.assertIn('Debug.TraceUser(LogName, "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " " + msg)', quest)
        self.assertIn('Debug.TraceUser("fo4sf_newgame", "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " " + msg)', looks)
        self.assertIn(20, ng.summarize(self.LINES)["stages"])
        self.assertEqual(ng.summarize(self.LINES)["stage_causes"][20], "scene")
        without = [ln for ln in self.LINES if " stage 20 " not in ln]
        self.assertEqual(ng.summarize(without)["stages"], [10, 40, 200])

    def test_inventory_lines(self):
        """The inventory reset (NG-K8): a --keep-inventory build logs neither line (both None); a default build logs
        the count; a --vault-suit build the suit, or that it did not resolve."""
        head = "[x] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n"
        s = self.run_log(head + "[x] FO4SF_NEWGAME rt=7.0 enter vault ok=True pos=11 20 1 target=11 20 1 cell=x\n")[1]
        self.assertEqual((s["inventory_cleared"], s["vault_suit"]), (None, None))
        s = self.run_log(head + "[x] FO4SF_NEWGAME rt=7.0 inventory cleared removed=0 left=0\n")[1]
        self.assertEqual((s["inventory_cleared"], s["vault_suit"], s["o2_capacity"]), ("removed=0 left=0", None, None))
        s = self.run_log(head + "[x] FO4SF_NEWGAME rt=7.0 inventory cleared removed=4 left=0\n"
                                "[x] FO4SF_NEWGAME rt=7.0 o2 capacity added=100.000000 value=100.000000\n")[1]
        self.assertEqual(s["o2_capacity"], "added=100.000000 value=100.000000")
        s = self.run_log(head + "[x] FO4SF_NEWGAME rt=7.0 inventory cleared removed=3 left=1\n"
                                "[x] FO4SF_NEWGAME rt=7.0 vault suit FO4Port.esm:2080 does not resolve\n")[1]
        self.assertEqual(s["vault_suit"], "FO4Port.esm:2080 does not resolve")

    def test_the_stand_down_line_is_the_scripts(self):
        """The fixtures' stand-down line must be one the script writes: the guard's trace gained the opening's stage and
        the fresh verdict (21 Oct), and a fixture still naming days and level alone was a line no script produced. Our
        own start (newgame_v11) has no fresh verdict; the line says whether the game was still loading instead (either
        reading of the start: a hand back follows then)."""
        trace = 'Trace("not a new game: days=" + days + " level=" + level + " loading=" + loading + ": standing down")'
        self.assertIn(trace, read(PSC))
        parts = re.findall(r'"([^"]*)"', trace[len('Trace('):])
        self.assertEqual(parts, ["not a new game: days=", " level=", " loading=", ": standing down"])
        rest = STOOD_DOWN
        for literal in parts:                                # the literals in order, with a value between each pair
            self.assertIn(literal, rest)
            rest = rest[rest.index(literal) + len(literal):]
        self.assertEqual(rest, "")
        self.assertTrue(self.run_log(f"[x] FO4SF_NEWGAME rt=3.0 {STOOD_DOWN}\n")[1]["stood_down"])

    def test_the_init_line_is_the_scripts(self):
        """The fixtures' init line must be one the script writes: OnQuestInit's trace gained the anchor's mode
        (anchor_temporary=, 21 Oct), and a fixture without it was a line no script produced. Every init line of this
        file's fixtures carries the literals of the script's trace in order, with a value between each pair."""
        trace = ('Trace("init holdoff=" + HoldOff.Length + " vault=" + VaultPlugin + ":" + VaultAnchorId'
                 ' + " anchor_temporary=" + AnchorTemporary + " core=" + CorePlugin + ":" + ExitAnchorId)')
        self.assertIn(trace, read(PSC))
        parts = re.findall(r'"([^"]*)"', trace[len('Trace('):])
        self.assertEqual(parts, ["init holdoff=", " vault=", ":", " anchor_temporary=", " core=", ":"])
        # every fixture posing as the script's init line (split_runs' "init x" placeholders test the prefix alone)
        inits = re.findall(r'FO4SF_NEWGAME rt=[-\d.]+ (init holdoff=[^"\\]*)', read(__file__))
        self.assertGreaterEqual(len(inits), 8)
        for line in inits:
            rest = line
            for literal in parts:
                self.assertIn(literal, rest, line)
                rest = rest[rest.index(literal) + len(literal):]
            self.assertRegex(rest, r"^\d+$", line)             # the exit anchor's id ends the line
            self.assertRegex(line, r" anchor_temporary=(True|False|true|false) ", line)   # Starfield prints bools lowercase (28 Oct log)

    def test_our_own_start_lines_are_the_scripts(self):
        """Our own start (newgame_v11): every line the reader takes from the start is one the script writes (the
        literals in order), and the reader's verdicts. A New Game+ stands down and hands back (exit 1, the hand back's
        two lines, then stage 1); a start whose anchor resolves to nothing stands down the same way; a hand back whose
        request never returned leaves its first line alone; a stand-down on a running game hands nothing back; the
        start's wait can end without the 3D, and the timer fades in then, or logs its wait every 10 ticks. Each
        fixture is a log the script can write: its lines in the script's order (29 Oct review on #588)."""
        psc = read(PSC)
        for trace, line in (
                ('Trace("start route=" + route + " player_loaded=" + loaded + " cell=" + startCell + " loading=" + loading)',
                 "start route=OnQuestInit player_loaded=false cell=None loading=true"),
                ('Trace("start event " + route + " came after the start: nothing to do")',
                 "start event OnQuestStarted came after the start: nothing to do"),
                ('Trace("start event " + lateRoute + " came after the start: nothing to do")',
                 "start event OnQuestStarted came after the start: nothing to do"),
                ('Trace("3d wait over loaded=" + ready)', "3d wait over loaded=false"),
                ('Trace("fade in by=" + by + " loaded=" + player.Is3DLoaded() + " cell=" + player.GetParentCell() + "; saving and HUD on")',
                 "fade in by=timer loaded=true cell=[Cell <FO4Port_Vault111Cryo (030011F3)>]; saving and HUD on"),
                ('Trace("no move into the vault: anchor " + VaultPlugin + ":" + VaultAnchorId + " does not resolve; standing down")',
                 "no move into the vault: anchor FO4Port.esm:4920 does not resolve; standing down"),
                ("Trace(\"handing back to Starfield's start: \" + why + \"; mq101debug=\" + DebugGlobal.GetValue())",
                 "handing back to Starfield's start: no move into the vault; mq101debug=0.000000"),
                ('Trace("handed back: requested=" + requested + " opening starting=" + Opening.IsStarting() + " running=" + Opening.IsRunning() + " stage=" + Opening.GetStage())',
                 "handed back: requested=true opening starting=true running=false stage=0"),
                ('Trace("waiting for the 3d tick=" + ticks + " vault_moves=" + vaultMoves + " centered=" + centered + " cell=" + player.GetParentCell())',
                 "waiting for the 3d tick=10 vault_moves=1 centered=0 cell=None"),
                ('Trace("guard days=" + days + " level=" + level + " opening_stage=" + Opening.GetStage() + " opening_running=" + Opening.IsRunning() + " mq101debug=" + DebugGlobal.GetValue() + " write_after_hold=" + DebugAfterHold)',
                 "guard days=0.333530 level=12 opening_stage=0 opening_running=false mq101debug=0.000000 write_after_hold=2"),
                ('Trace("enter vault confirmed after the load pos=" + player.GetPositionX() + " " + player.GetPositionY()'
                 ' + " " + player.GetPositionZ() + " cell=" + player.GetParentCell())',
                 "enter vault confirmed after the load pos=9.2 -3.1 -0.85 cell=[Cell <FO4Port_Vault111Cryo (030011F3)>]")):
            with self.subTest(line=line):
                self.assertIn(trace, psc)
                rest = line
                for literal in re.findall(r'"([^"]*)"', trace[len("Trace("):]):
                    self.assertIn(literal, rest)
                    rest = rest[rest.index(literal) + len(literal):]
        head = "[x] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:4920 anchor_temporary=false core=FO4TerrainCore.esm:685915\n"
        guard = "guard days=0.333530 level={} opening_stage=0 opening_running=false mq101debug=0.000000 write_after_hold=2"
        handing = "handing back to Starfield's start: {}; mq101debug=0.000000"
        handed = "handed back: requested=true opening starting=true running=false stage=0"
        # a New Game+: the guard stands down while the game loads; the request to MQ101 goes out, then our stage 1
        code, s = self.run_log(head + "[x] FO4SF_NEWGAME rt=2.0 start route=OnQuestStarted player_loaded=false cell=None loading=true\n"
                                      f"[x] FO4SF_NEWGAME rt=2.0 {guard.format(12)}\n"
                                      f"[x] FO4SF_NEWGAME rt=2.1 {STOOD_DOWN}\n"
                                      f"[x] FO4SF_NEWGAME rt=2.1 {handing.format('not a new game')}\n"
                                      f"[x] FO4SF_NEWGAME rt=2.1 {handed}\n"
                                      "[x] FO4SF_NEWGAME rt=2.2 stage 1\n")
        self.assertEqual(code, 1)
        self.assertTrue(s["stood_down"])
        self.assertEqual(s["stand_down"], STOOD_DOWN)
        self.assertEqual(s["handing_back"], "not a new game; mq101debug=0.000000")
        self.assertEqual(s["handed_back"], "requested=true opening starting=true running=false stage=0")
        self.assertEqual(s["stages"], [1])
        self.assertIsNone(s["mq101debug_written"])           # a hand back follows no write
        # the other tests' New Game+ (NG_PLUS) is this log
        self.assertEqual(NG_PLUS, ("start route=OnQuestStarted player_loaded=false cell=None loading=true",
                                   guard.format(12), STOOD_DOWN, handing.format("not a new game"), handed, "stage 1 by=trigger"))
        # no move into the vault: the same stand-down and hand back
        no_move = "no move into the vault: anchor FO4Port.esm:4920 does not resolve; standing down"
        no_move_log = (head + "[x] FO4SF_NEWGAME rt=2.0 start route=OnQuestStarted player_loaded=true cell=None loading=true\n"
                              f"[x] FO4SF_NEWGAME rt=2.0 {guard.format(1)}\n"
                              "[x] FO4SF_NEWGAME rt=2.0 vault anchor FO4Port.esm:4920 does not resolve\n"
                              f"[x] FO4SF_NEWGAME rt=2.1 {no_move}\n"
                              f"[x] FO4SF_NEWGAME rt=2.1 {handing.format('no move into the vault')}\n")
        code, s = self.run_log(no_move_log + f"[x] FO4SF_NEWGAME rt=2.1 {handed}\n" "[x] FO4SF_NEWGAME rt=2.2 stage 1\n")
        self.assertEqual((code, s["stood_down"], s["stand_down"], s["stages"]), (1, True, no_move, [1]))
        self.assertEqual((s["handing_back"], s["handed_back"]), ("no move into the vault; mq101debug=0.000000", handed[len("handed back: "):]))
        # the same log cut after the hand back's first line: the request never returned, and our stage never came
        code, s = self.run_log(no_move_log)
        self.assertEqual((code, s["handing_back"], s["handed_back"], s["stages"]), (1, "no move into the vault; mq101debug=0.000000", None, []))
        # a start from the console on a played save: both readings say the game runs, stood down, nothing handed back
        s = self.run_log(head + "[x] FO4SF_NEWGAME rt=2.0 start route=OnQuestStarted player_loaded=true cell=[Cell <x>] loading=false\n"
                                "[x] FO4SF_NEWGAME rt=2.0 guard days=41.200000 level=12 opening_stage=2000 opening_running=false mq101debug=0.000000 write_after_hold=2\n"
                                "[x] FO4SF_NEWGAME rt=2.1 not a new game: days=41.200000 level=12 loading=false: standing down\n"
                                "[x] FO4SF_NEWGAME rt=2.1 stage 1\n")[1]
        self.assertTrue(s["stood_down"])
        self.assertEqual((s["handing_back"], s["handed_back"], s["stages"]), (None, None, [1]))
        # OnQuestInit first; the start's wait ends before the 3D is in, so the start leaves the fade to the timer
        moved = (f"[x] FO4SF_NEWGAME rt=2.0 {guard.format(1)}\n"
                 "[x] FO4SF_NEWGAME rt=2.1 enter vault ok=false pos=0 0 0 target=9.142858 -3.114286 -0.728571 cell=None\n"
                 "[x] FO4SF_NEWGAME rt=2.1 not running [mq00questscript <MQ00 (00005790)>] pass=1\n"
                 "[x] FO4SF_NEWGAME rt=2.1 not running [defaulttutorialquestscript <MQ101 (00003448)>] pass=1\n"
                 "[x] FO4SF_NEWGAME rt=2.1 not running [Quest <MQ101PostQuest (0006A960)>] pass=1\n"
                 "[x] FO4SF_NEWGAME rt=2.1 not running [Quest <MQ_TutorialQuest_Misc04 (00021353)>] pass=1\n"
                 "[x] FO4SF_NEWGAME rt=2.1 hold-off pass 1 stopped=0 of 4\n"
                 "[x] FO4SF_NEWGAME rt=2.1 mq101debug written=2.000000 was=0.000000\n")
        s = self.run_log(head + "[x] FO4SF_NEWGAME rt=2.0 start route=OnQuestInit player_loaded=false cell=None loading=true\n"
                                "[x] FO4SF_NEWGAME rt=2.0 start event OnQuestStarted came after the start: nothing to do\n"
                                + moved +
                                "[x] FO4SF_NEWGAME rt=3.0 3d wait over loaded=false\n"
                                "[x] FO4SF_NEWGAME rt=4.0 fade in by=timer loaded=true cell=x; saving and HUD on\n")[1]
        self.assertEqual(s["start_events"], ["OnQuestInit", "OnQuestStarted"])
        self.assertEqual(s["fade"], "by=timer loaded=true cell=x; saving and HUD on")
        self.assertEqual(s["start_wait"], "loaded=false")
        self.assertIsNone(s["waiting_3d"])                   # the timer saw the 3D within 10 ticks
        # a wait for the 3D that does not end: the timer's line every 10 ticks, the last one kept; no fade
        s = self.run_log(head + "[x] FO4SF_NEWGAME rt=2.0 start route=OnQuestStarted player_loaded=false cell=None loading=true\n"
                                + moved +
                                "[x] FO4SF_NEWGAME rt=12.1 waiting for the 3d tick=10 vault_moves=1 centered=0 cell=None\n"
                                "[x] FO4SF_NEWGAME rt=22.1 waiting for the 3d tick=20 vault_moves=1 centered=0 cell=None\n")[1]
        self.assertEqual((s["waiting_3d"], s["start_wait"], s["fade"]), ("tick=20 vault_moves=1 centered=0 cell=None", None, None))
        # an older build's log has none of them
        old = self.run_log(head + "[x] FO4SF_NEWGAME rt=7.0 enter vault ok=true pos=1 2 3 target=1 2 3 cell=x\n")[1]
        self.assertEqual((old["start"], old["start_events"], old["start_wait"], old["fade"], old["handing_back"], old["handed_back"],
                          old["waiting_3d"]), (None, [], None, None, None, None, None))

    def test_the_owners_run_of_28_oct_reads_as_stood_down(self):
        """The first in-game run (fo4sf_newgame.0.log, PC 28 Oct 11:24, build 3fb78b14): the version script saw a new
        game, the quest initialised, and the guard stood down with the opening at 250 (the developer start the
        MQ101Debug 10 override picked) and 0.3335 days passed (Starfield's 8:00 clock). An older build's log has no
        guard line, so "guard" is None."""
        text = ("[11:24:50] FO4SF_NEWGAME rt=597.945007 version saved=1.000000 (new game)\n"
                "[11:24:57] FO4SF_NEWGAME rt=605.252014 init holdoff=4 vault=fo4port.esm:4920 anchor_temporary=true core=fo4terraincore.esm:685915\n"
                "[11:24:58] FO4SF_NEWGAME rt=606.619019 not a new game: days=0.333537 level=1 opening_stage=250 fresh=false: standing down\n"
                "[11:24:58] FO4SF_NEWGAME rt=606.672058 stage 1\n")
        code, s = self.run_log(text)
        self.assertEqual(code, 1)
        self.assertTrue(s["stood_down"])
        self.assertEqual(s["stages"], [1])
        # Starfield prints bools lowercase (anchor_temporary=true, fresh=false above): the reader takes both spellings
        lower = self.run_log("[x] FO4SF_NEWGAME rt=7.0 enter vault ok=true pos=11 20 1 target=11 20 1 cell=[Cell <FO4Port_Vault111Cryo>]\n")[1]
        self.assertTrue(lower["entered_vault"])
        self.assertFalse(self.run_log("[x] FO4SF_NEWGAME rt=7.0 enter vault ok=false pos=1 2 3 target=11 20 1 cell=None\n")[1]["entered_vault"])
        self.assertEqual(s["version_saved"], "1.000000")
        self.assertIsNone(s["guard"])
        # the 10:43 run of the same day stood down with the opening still at stage 0: the day limit alone did it
        self.assertFalse(ng.is_new_game(0.333530, 1, max_days=0.25))
        self.assertTrue(ng.is_new_game(0.333530, 1))

    def test_the_owners_run_3_of_28_oct(self):
        """The third in-game run (fo4sf_newgame.0.log, PC 28 Oct 18:07, newgame_v9, Install's copy
        D:\\Modding\\testqueue\\newgame_20261028_run3): the whole chain ran, from the guard (opening at 5, running) to stage
        200, with the quick start and SPECIAL left unset. The surface line shows the SetPosition that did not take (its
        position is the MoveTo's), and "fell" is the fall check's fallback that moved the player off that spot. A build
        before newgame_v10 has no "pod settle" line."""
        text = ("[18:07:37] FO4SF_NEWGAME rt=36.587002 version saved=1.000000 (new game)\n"
                "[18:07:42] FO4SF_NEWGAME rt=41.694000 init holdoff=4 vault=fo4port.esm:4920 anchor_temporary=false core=fo4terraincore.esm:685915\n"
                "[18:07:43] FO4SF_NEWGAME rt=42.987003 guard days=0.333526 level=1 opening_stage=5 opening_running=true fresh=true mq101debug=0.000000 write_after_hold=2\n"
                "[18:07:44] FO4SF_NEWGAME rt=43.064003 held off [mq00questscript <MQ00 (00005790)>] running_after=false pass=1\n"
                "[18:07:44] FO4SF_NEWGAME rt=43.140003 held off [defaulttutorialquestscript <MQ101 (00003448)>] running_after=false pass=1\n"
                "[18:07:44] FO4SF_NEWGAME rt=43.254002 mq101debug written=2.000000 was=0.000000\n"
                "[18:07:44] FO4SF_NEWGAME rt=43.593002 enter vault ok=true pos=9.204920 -3.086447 -1.044888 target=9.142858 -3.114286 -1.028571 cell=[Cell <FO4Port_Vault111Cryo (030011F3)>]\n"
                "[18:07:44] FO4SF_NEWGAME rt=43.611004 stage 10\n"
                "[18:07:47] FO4SF_NEWGAME rt=46.120003 held off [Quest <MQ101PostQuest (0006A960)>] running_after=false pass=2\n"
                "[18:07:47] FO4SF_NEWGAME rt=46.191002 held off [Quest <MQ_TutorialQuest_Misc04 (00021353)>] running_after=false pass=2\n"
                "[18:07:52] FO4SF_NEWGAME rt=51.499001 looks done: Quick start\n"
                "[18:07:52] FO4SF_NEWGAME rt=51.533001 stage 20\n"
                "[18:07:54] FO4SF_NEWGAME rt=53.664001 status stage=20 pos=1.531505 -7.385632 -0.851672 cell=[Cell <FO4Port_Vault111Cryo (030011F3)>] world=None\n"
                "[18:08:43] FO4SF_NEWGAME rt=90.139008 cog door open_state before=3 after=2\n"
                "[18:08:43] FO4SF_NEWGAME rt=90.174004 stage 30\n"
                "[18:10:07] FO4SF_NEWGAME rt=173.281006 elevator prompt button=0\n"
                "[18:10:09] FO4SF_NEWGAME rt=175.729004 surface moveto pos=-1275.313965 1305.275757 119.384842 world=[WorldSpace <MarsPlanetWorld137917136288 (FF00C482)>]\n"
                "[18:10:09] FO4SF_NEWGAME rt=175.743011 surface setposition pos=-1275.313965 1305.275757 119.384842 target=-2467.781494 -1406.924927 128.109528\n"
                "[18:10:09] FO4SF_NEWGAME rt=175.758011 stage 40\n"
                "[18:10:12] FO4SF_NEWGAME rt=178.517014 special skipped: left the vault with SPECIAL unset\n"
                "[18:10:15] FO4SF_NEWGAME rt=181.429016 fell z=119.384842: fallback pos=-2475.313965 -1394.724243 127.223747\n"
                "[18:10:15] FO4SF_NEWGAME rt=181.443008 stage 200\n")
        code, s = self.run_log(text)
        self.assertEqual(code, 0)
        self.assertEqual(s["stages"], [10, 20, 30, 40, 200])
        self.assertEqual(s["guard"], "days=0.333526 level=1 opening_stage=5 opening_running=true fresh=true mq101debug=0.000000 write_after_hold=2")
        self.assertEqual(s["mq101debug_written"], "2.000000 was=0.000000")
        self.assertTrue(s["entered_vault"])
        self.assertIsNone(s["pod_settle"])
        self.assertEqual(s["looks_done"], "Quick start")
        self.assertEqual(s["special"], "skipped: left the vault with SPECIAL unset")
        self.assertTrue(s["fell"])
        self.assertIsNone(s["landed"])
        self.assertIn("pos=-1275.313965 1305.275757 119.384842 target=-2467.781494", s["surfaced"])   # not taken
        self.assertIsNone(s["centered"])                     # the port's COC marker is persistent now
        # newgame_v10's lines: the settle check and a surface line that says whether the arrival took
        v10 = self.run_log("[x] FO4SF_NEWGAME rt=43.6 enter vault ok=true pos=9.2 -3.1 -0.73 target=9.14 -3.11 -0.73 cell=x\n"
                           "[x] FO4SF_NEWGAME rt=46.2 pod settle ok=true pos=9.2 -3.1 -0.85 dx=0.06 dy=0.01 drop=0.12\n"
                           "[x] FO4SF_NEWGAME rt=47.2 pod settle ok=false pos=1.5 -7.4 -0.85 dx=-7.6 dy=-4.3 drop=0.12\n"
                           "[x] FO4SF_NEWGAME rt=178.7 surface setposition ok=true set=1 pos=-2467.78 -1406.92 128.11 target=-2467.78 -1406.92 128.11\n")[1]
        self.assertEqual(v10["pod_settle"], "ok=true pos=9.2 -3.1 -0.85 dx=0.06 dy=0.01 drop=0.12")   # the first line counts
        self.assertTrue(v10["surfaced"].startswith("surface setposition ok=true set=1 "))
        psc = read(PSC)
        self.assertIn('Trace("pod settle ok=" + ok + " pos="', psc)
        self.assertIn('Trace("surface setposition ok=" + ok + " set="', psc)

    def test_the_owners_run_2_of_28_oct_never_started(self):
        """The second in-game run (fo4sf_newgame.0.log, PC 28 Oct 13:35, build 5167f6aa, MQ101Debug overridden to 2):
        the version script's alias filled ("version saved") and nothing else ever ran, no init, no guard, because
        Starfield's first load never completed (no stage-0 entry of MQ101 matched 2, so nothing moved the player; the
        intro's own fragment is what does, Item_02: moveto CharGenStartMarker). The reader shows an unstarted run, not a
        stand-down, and exit 1; the build overrides nothing at the start since."""
        code, s = self.run_log("[13:35:28] FO4SF_NEWGAME rt=64.002007 version saved=1.000000 (new game)\n")
        self.assertEqual(code, 1)
        self.assertFalse(s["stood_down"])
        self.assertEqual(s["stages"], [])
        self.assertIsNone(s["guard"])
        self.assertIsNone(s["mq101debug_written"])
        self.assertEqual(s["version_saved"], "1.000000")
        self.assertEqual(s["runs"], 1)
        self.assertIsNone(ng.DEFAULT_MQ101DEBUG)
        self.assertEqual(ng.DEBUG_UNMATCHED, 2)

    def test_stood_down_and_exit_code(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "fo4sf_newgame.0.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("[x] FO4SF_NEWGAME rt=3.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=false core=FO4TerrainCore.esm:685915\n"
                    + "".join(f"[x] FO4SF_NEWGAME rt=3.0 {ln}\n" for ln in NG_PLUS))
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["log", "--file", path]), 1)
        self.assertTrue(json.loads(o.getvalue())["stood_down"])
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.LINES))
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(ng.main(["log", "--file", path]), 0)


    def run_log(self, text):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "fo4sf_newgame.0.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            code = ng.main(["log", "--file", path])
        return code, json.loads(o.getvalue())

    def test_an_older_completion_never_passes_a_newer_run(self):
        """Codex review on #393: the log is appended across sessions, so only the latest run is judged."""
        done = "\n".join(self.LINES) + "\n"
        init = "[y] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n"
        cases = {
            "failed": init + "[y] FO4SF_NEWGAME rt=3.0 enter vault ok=False pos=0 0 0 target=11 20 1 cell=None\n",
            "stood down": init + "".join(f"[y] FO4SF_NEWGAME rt=3.0 {ln}\n" for ln in NG_PLUS),
            "init only": init,
        }
        for name, newer in cases.items():
            with self.subTest(name):
                code, s = self.run_log(done + newer)
                self.assertEqual(code, 1)
                self.assertEqual(s["runs"], 2)
                self.assertTrue(s["earlier_completed"])
                self.assertNotIn(200, s["stages"])
        self.assertFalse(self.run_log(done + cases["failed"])[1]["entered_vault"])
        self.assertTrue(self.run_log(done + cases["stood down"])[1]["stood_down"])

    def test_the_latest_run_completing_passes(self):
        failed = "[y] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n" \
                 "[y] FO4SF_NEWGAME rt=3.0 enter vault ok=False pos=0 0 0 target=11 20 1 cell=None\n"
        code, s = self.run_log(failed + "\n".join(self.LINES) + "\n")
        self.assertEqual(code, 0)
        self.assertEqual(s["runs"], 2)
        self.assertFalse(s["earlier_completed"])
        self.assertTrue(s["entered_vault"])

    def test_looks_done_endings(self):
        """What ended the looks wait: the creator's close event, the quick start, or the quest's LooksWait fallback;
        the first ending counts, and a run without one reads None."""
        head = "[x] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n"
        for ending, want in (("quick start", "quick start"), ("LooksWait fallback after 120.0 s", "LooksWait fallback after 120.0 s")):
            code, s = self.run_log(head + f"[x] FO4SF_NEWGAME rt=9.0 looks done: {ending}\n[x] FO4SF_NEWGAME rt=9.0 stage 20\n")
            self.assertEqual(s["looks_done"], want)
        code, s = self.run_log(head + "[x] FO4SF_NEWGAME rt=9.0 looks done: creator closed\n"
                                      "[x] FO4SF_NEWGAME rt=130.0 looks done: LooksWait fallback after 120.0 s\n")
        self.assertEqual(s["looks_done"], "creator closed")
        self.assertIsNone(self.run_log(head)[1]["looks_done"])

    def test_special_endings(self):
        """The SPECIAL ending: set at the terminal, or skipped when the player left the vault without it; "later" and
        "left" are not endings, and a run without one reads None."""
        head = "[x] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n"
        code, s = self.run_log(head + "[x] FO4SF_NEWGAME rt=9.0 special later\n[x] FO4SF_NEWGAME rt=12.0 special left: defaults kept, 33 points unspent\n"
                                      "[x] FO4SF_NEWGAME rt=90.0 stage 40\n[x] FO4SF_NEWGAME rt=91.0 special skipped: left the vault with SPECIAL unset\n")
        self.assertEqual(s["special"], "skipped: left the vault with SPECIAL unset")
        self.assertIsNone(self.run_log(head + "[x] FO4SF_NEWGAME rt=9.0 special later\n")[1]["special"])

    def test_version_lines(self):
        """The save version check (NG-15 / NG-L2): the version recorded at the new game, the last load's comparison
        (a load logs no "init", so its lines join the run before it) and whether any load found a mismatch."""
        head = "[x] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n" \
               "[x] FO4SF_NEWGAME rt=2.0 version saved=1.000000 (new game)\n"
        code, s = self.run_log(head + "[y] FO4SF_NEWGAME rt=1.5 version load saved=1.000000 installed=1.000000\n")
        self.assertEqual((s["version_saved"], s["version_load"], s["version_mismatch"]), ("1.000000", "saved=1.000000 installed=1.000000", False))
        code, s = self.run_log(head + "[y] FO4SF_NEWGAME rt=1.5 version load saved=1.000000 installed=1.000000\n"
                                      "[z] FO4SF_NEWGAME rt=1.7 version load saved=1.000000 installed=2.000000\n"
                                      "[z] FO4SF_NEWGAME rt=1.7 version mismatch\n")
        self.assertEqual((s["version_load"], s["version_mismatch"]), ("saved=1.000000 installed=2.000000", True))
        self.assertEqual(s["runs"], 1)
        s = self.run_log("[x] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n")[1]
        self.assertEqual((s["version_saved"], s["version_load"], s["version_mismatch"]), (None, None, False))

    def test_split_runs(self):
        lines = ["[a] FO4SF_NEWGAME rt=1 status stage=20", "[b] other log", "[c] FO4SF_NEWGAME rt=2 init x",
                 "[d] FO4SF_NEWGAME rt=3 stage 10", "[e] FO4SF_NEWGAME rt=4 init y"]
        self.assertEqual(ng.split_runs(lines, ng.LINE), [["status stage=20"], ["init x", "stage 10"], ["init y"]])
        self.assertEqual(ng.split_runs([], ng.LINE), [])

    def test_a_version_line_before_init_joins_the_new_run(self):
        """21 Oct review on #393: the alias script's OnInit may trace before the quest's; either order is one run."""
        old = ["[a] FO4SF_NEWGAME rt=1 init old", "[b] FO4SF_NEWGAME rt=2 status stage=200"]
        for first, second in ((["version saved=7 installed=7"], ["init new"]),
                              (["init new"], ["version saved=7 installed=7"])):
            with self.subTest(first=first[0]):
                lines = old + [f"[c] FO4SF_NEWGAME rt=3 {m}" for m in first + second] + \
                    ["[d] FO4SF_NEWGAME rt=4 status stage=10"]
                runs = ng.split_runs(lines, ng.LINE, carry=("version saved=",))
                self.assertEqual(len(runs), 2)
                self.assertEqual(sorted(runs[1][:2]), ["init new", "version saved=7 installed=7"])
                self.assertEqual(ng.summarize(lines)["version_saved"], "7")

class VerifyFoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        t = self.tmp
        self.stage = os.path.join(t, "stage")
        os.makedirs(os.path.join(self.stage, "Data", "Scripts"))
        files = {ng.PLUGIN: b"plugin", "Data/Scripts/FO4SF_NewGameQuest.pex": b"pex1"}
        for rel, data in files.items():
            with open(os.path.join(self.stage, *rel.split("/")), "wb") as f:
                f.write(data)
        with open(os.path.join(self.stage, "README.txt"), "w", encoding="utf-8") as f:
            f.write("Fallout 4 new game (Claude-cloud). Install: not now.\n")
        self.core_dir = os.path.join(t, "core_set")
        os.makedirs(os.path.join(self.core_dir, "Data", "Terrain"))
        for name, data in (("FO4TerrainCore.esm", b"core"), ("Mars.esm", b"mars"), ("Data/Terrain/core.btd", b"btd")):
            with open(os.path.join(self.core_dir, *name.split("/")), "wb") as f:
                f.write(data)
        # the core set's README as make_core64c.py readme() writes it: FO4TerrainCore first (it names the --pack archive)
        self.core_install = ("scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> "
                             "--plugins FO4TerrainCore.esm,Mars.esm --pack")
        self.core_readme = ("Terrain core64c (Claude, 2026-10-12).\n\nInstall (game closed). The runner does it:\n  "
                            + self.core_install + "\n  --pack builds \"FO4TerrainCore - Main.ba2\" from Data\\\n"
                            "Queue: testqueue.py plan-terrain --exp-dir <this folder> --plugins FO4TerrainCore.esm,Mars.esm --fresh\n")
        with open(os.path.join(self.core_dir, "README.txt"), "w", encoding="utf-8") as f:
            f.write(self.core_readme)
        self.port = os.path.join(t, "FO4Port.esm")
        with open(self.port, "wb") as f:
            f.write(b"port")
        plan = {"kind": "newgame", "plugin": ng.PLUGIN, "plugin_sha256": ng.sha256(os.path.join(self.stage, ng.PLUGIN)),
                "scripts": {"FO4SF_NewGameQuest": ng.sha256(os.path.join(self.stage, "Data", "Scripts", "FO4SF_NewGameQuest.pex"))},
                "checked_against_sha256": {"FO4Port.esm": ng.sha256(self.port), "formids.json": "x",
                                           "FO4TerrainCore.esm": ng.sha256(os.path.join(self.core_dir, "FO4TerrainCore.esm"))}}
        with open(os.path.join(self.stage, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan, f)

    def fold(self, out, **kw):
        args = ["fold", "--stage", self.stage, "--core-dir", self.core_dir, "--out", out]
        for k, v in kw.items():
            args += [f"--{k}", v]
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            return ng.main(args)

    def test_fold_then_verify(self):
        out = os.path.join(self.tmp, "folded")
        self.assertEqual(self.fold(out, port=self.port), 0)
        self.assertTrue(os.path.isfile(os.path.join(out, "Mars.esm")))
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(ng.main(["verify", "--exp-dir", out, "--plan", os.path.join(self.stage, "plan.json"),
                                      "--port", self.port]), 0)

    def install_namespace(self, command):
        """The folded README's command as exp_install.py's own parser reads it (install patched out: nothing is
        installed), with the placeholders filled: the real CLI, not a string this test believes in."""
        sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
        import exp_install
        argv = command.split()[1:]
        self.assertEqual(argv[:3], ["install", "--exp-dir", "<this"])
        argv = ["install", "--exp-dir", self.folded, "--starfield", os.path.join(self.tmp, "game")] + argv[6:]
        with unittest.mock.patch.object(exp_install, "install", side_effect=lambda a: a) as install:
            exp_install.main(argv)
        return exp_install, install.call_args[0][0]

    def test_folded_readme_installs_every_plugin(self):
        """Codex review on #393 (P1): exp_install.py activates only the plugins of --plugins (none listed: the first
        .esm alphabetically), so the core README's own install command, copied into the fold as it was, would install
        the core set and never FO4SFNewGame.esm. The folded README's every install line names every plugin and
        --pack, and carries the stage's README."""
        self.folded = os.path.join(self.tmp, "folded")
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["fold", "--stage", self.stage, "--core-dir", self.core_dir, "--out", self.folded,
                                      "--port", self.port]), 0)
        every = "FO4TerrainCore.esm,Mars.esm,FO4SFNewGame.esm"
        self.assertIn(f"--plugins {every} --pack", o.getvalue())
        readme = read(os.path.join(self.folded, "README.txt"))
        install_lines = [ln for ln in readme.splitlines() if "exp_install.py install" in ln]
        self.assertEqual(len(install_lines), 2)              # the core's own line, widened, and the fold's
        for ln in install_lines:
            self.assertIn(f"--plugins {every} --pack", ln)
        self.assertNotIn(self.core_install, readme)           # the core-only command is gone
        self.assertIn("Terrain core64c (Claude, 2026-10-12).", readme)
        self.assertIn("Fallout 4 new game (Claude-cloud). Install: not now.", readme)
        # the real installer's reading of that command: every plugin selected, the new game's plugin and script staged
        exp_install, a = self.install_namespace(install_lines[-1].strip())
        self.assertTrue(a.pack)
        plugins = a.plugins.split(",")
        self.assertEqual(plugins, every.split(","))
        staged = {rel for _, rel in exp_install.staged_files(self.folded, plugins)}
        self.assertIn(ng.PLUGIN, staged)
        self.assertIn(os.path.join("Scripts", "FO4SF_NewGameQuest.pex"), staged)
        self.assertIn(os.path.join("Terrain", "core.btd"), staged)
        # ...and what the review found: the core's list, or no list at all, never stages the new game's plugin
        core_only = {rel for _, rel in exp_install.staged_files(self.folded, ["FO4TerrainCore.esm", "Mars.esm"])}
        self.assertNotIn(ng.PLUGIN, core_only)
        first = sorted(f for f in os.listdir(self.folded) if f.lower().endswith(".esm"))[:1]
        self.assertEqual(len(first), 1)                       # --plugins omitted: one plugin of three

    def test_fold_without_a_core_readme_lists_the_esm_files(self):
        os.remove(os.path.join(self.core_dir, "README.txt"))
        out = os.path.join(self.tmp, "folded")
        self.assertEqual(self.fold(out, port=self.port), 0)
        readme = read(os.path.join(out, "README.txt"))
        self.assertIn("--plugins FO4TerrainCore.esm,Mars.esm,FO4SFNewGame.esm --pack", readme)
        self.assertEqual(readme.count("exp_install.py install"), 1)

    def test_fold_refuses_a_core_readme_that_installs_other_plugins(self):
        with open(os.path.join(self.core_dir, "README.txt"), "w", encoding="utf-8") as f:
            f.write(self.core_readme.replace("Mars.esm", "Venus.esm"))
        out = os.path.join(self.tmp, "folded")
        with self.assertRaises(SystemExit) as cm:
            self.fold(out, port=self.port)
        self.assertIn("Venus.esm", str(cm.exception))
        self.assertFalse(os.path.exists(out))

    def test_fold_refuses_another_port(self):
        other = os.path.join(self.tmp, "other_port.esm")
        with open(other, "wb") as f:
            f.write(b"rebuilt port")
        out = os.path.join(self.tmp, "folded")
        with self.assertRaises(SystemExit):
            self.fold(out, port=other)
        self.assertFalse(os.path.exists(out))                # nothing published; the attempt stays beside it

    def test_verify_catches_a_changed_core(self):
        out = os.path.join(self.tmp, "folded")
        self.assertEqual(self.fold(out, port=self.port), 0)
        with open(os.path.join(out, "FO4TerrainCore.esm"), "wb") as f:
            f.write(b"another core")
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["verify", "--exp-dir", out, "--plan", os.path.join(self.stage, "plan.json"),
                                      "--port", self.port]), 1)
        self.assertIn("FO4TerrainCore.esm", o.getvalue())

    def test_existing_out_refused(self):
        out = os.path.join(self.tmp, "folded")
        os.makedirs(out)
        with self.assertRaises(SystemExit):
            self.fold(out, port=self.port)

    def test_fold_accepts_same_sha256_core_assets_and_pex_and_refuses_differing_ones(self):
        plan_path = os.path.join(self.stage, "plan.json")
        stage_pex = os.path.join(self.stage, "Data", "Scripts", "FO4SF_NewGameQuest.pex")
        core_pex = os.path.join(self.core_dir, "Data", "Scripts", "FO4SF_NewGameQuest.pex")
        os.makedirs(os.path.dirname(core_pex), exist_ok=True)
        with open(core_pex, "wb") as f:
            f.write(b"pex1")
        stage_copies = []
        real_copy2 = shutil.copy2
        def spy_copy2(src, dst, *a, **kw):
            if os.path.abspath(src).startswith(os.path.abspath(self.stage) + os.sep):
                stage_copies.append(os.path.abspath(src))
            return real_copy2(src, dst, *a, **kw)
        out_same_pex = os.path.join(self.tmp, "folded_same_pex")
        with unittest.mock.patch.object(ng.shutil, "copy2", side_effect=spy_copy2):
            self.assertEqual(self.fold(out_same_pex, port=self.port), 0)
        self.assertNotIn(os.path.abspath(stage_pex), stage_copies)
        self.assertEqual(ng.verify_dir(out_same_pex, ng.load_plan(plan_path), self.port), [])
        with open(core_pex, "wb") as f:
            f.write(b"differing_pex")
        out_diff_pex = os.path.join(self.tmp, "folded_diff_pex")
        with self.assertRaisesRegex(SystemExit, r"Data/Scripts/FO4SF_NewGameQuest\.pex"):
            self.fold(out_diff_pex, port=self.port)
        self.assertFalse(os.path.exists(out_diff_pex))
        with open(core_pex, "rb") as f:
            self.assertEqual(f.read(), b"differing_pex")
        os.remove(core_pex)
        rel = "Data/materials/fo4port/_neutral.mat"
        stage_mat = os.path.join(self.stage, *rel.split("/"))
        core_mat = os.path.join(self.core_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(stage_mat), exist_ok=True)
        os.makedirs(os.path.dirname(core_mat), exist_ok=True)
        with open(stage_mat, "wb") as f:
            f.write(b"neutral_bytes")
        with open(core_mat, "wb") as f:
            f.write(b"neutral_bytes")
        plan = ng.load_plan(plan_path)
        plan["cog_door"] = {"plugins": [], "outputs": {rel: ng.sha256(stage_mat)}}
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan, f)
        stage_copies.clear()
        out_same_mat = os.path.join(self.tmp, "folded_same_mat")
        with unittest.mock.patch.object(ng.shutil, "copy2", side_effect=spy_copy2):
            self.assertEqual(self.fold(out_same_mat, port=self.port), 0)
        self.assertNotIn(os.path.abspath(stage_mat), stage_copies)
        self.assertEqual(ng.verify_dir(out_same_mat, ng.load_plan(plan_path), self.port), [])
        with open(core_mat, "wb") as f:
            f.write(b"differing_neutral")
        out_diff_mat = os.path.join(self.tmp, "folded_diff_mat")
        with self.assertRaisesRegex(SystemExit, r"Data/materials/fo4port/_neutral\.mat"):
            self.fold(out_diff_mat, port=self.port)
        self.assertFalse(os.path.exists(out_diff_mat))
        with open(core_mat, "rb") as f:
            self.assertEqual(f.read(), b"differing_neutral")


@unittest.skipUnless(shutil.which("dotnet"), "no dotnet SDK on PATH")
class WriterSelfTest(unittest.TestCase):
    def test_selftest(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", os.path.join(ROOT, "dotnet", "NewGame"), "--",
                            "selftest", tmp], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn("selftest pass", r.stdout)


class PodStepOptionTests(unittest.TestCase):
    """Default pod step is -2.5 m (stand 9.143, -6.614, -1.029 m; heading unchanged), and stage's --pod-step overrides."""

    def args(self, **kw):
        base = dict(pod_ref=None, terminal_ref=None, pod_step=None)
        base.update(kw)
        return type("A", (), base)()

    def test_default_constant_matches_writer(self):
        self.assertEqual(ng.DEFAULT_POD_STEP, -2.5)
        self.assertIn("DefaultPodStep = -2.5f;", read(CS))
        self.assertIn('NewGame.Opt(args, "--pod-step", NewGame.DefaultPodStep)', read(CS))

    def test_unset_adds_nothing_so_writer_uses_default_minus_two_point_five(self):
        self.assertEqual(ng.points_options(self.args()), [])
        self.assertEqual(ng.points_options(self.args(pod_ref="4A011", terminal_ref="23CCD")),
                         ["--pod-ref", "4A011", "--terminal-ref", "23CCD"])

    def test_explicit_step_is_passed_verbatim(self):
        self.assertEqual(ng.points_options(self.args(pod_step=-2.5)), ["--pod-step", "-2.5"])
        self.assertEqual(ng.points_options(self.args(pod_step=1.0)), ["--pod-step", "1.0"])
        self.assertEqual(ng.points_options(self.args(pod_step=0.0)), ["--pod-step", "0.0"])

    def test_the_stage_parser_takes_it(self):
        self.assertIn('"--pod-step", type=float, default=None', read(os.path.join(ROOT, "scripts", "newgame", "make_newgame.py")))

    def test_handscanner_disabled_on_newgame(self):
        psc = read(PSC)
        self.assertIn("InputEnableLayer scannerLayer = None", psc)
        self.assertIn("scannerLayer = InputEnableLayer.Create()", psc)
        self.assertIn("scannerLayer.EnableHandscanner(false)", psc)
        self.assertIn('Trace("blocked input=handscanner")', psc)
        self.assertIn("DisableHandScanner()", psc)


class Phase2BeginningRealTests(unittest.TestCase):
    """Tasks 3 & 4 contracts: S3-S5 mode choice & Warfare branch, X1-X4 console/Pip-Boy/lift/map-setup, R4 output guard."""

    def test_2b_landing_handoff_starts_mission_quests_with_start_no_wait(self):
        psc = read(PSC)
        adv = psc[psc.index("Function ApplyStage"):psc.index("Event OnTimer")]
        self.assertIn("elseif n == 200\n        CompleteQuest()\n        StartLandingQuests()", adv)
        self.assertIn("elseif n == 210\n        CompleteQuest()\n        StartLandingQuests()", adv)
        handoff = psc[psc.index("Function StartLandingQuests"):psc.index("Function EnsureLoadHookRegistered")]
        self.assertIn('Trace("mission gate mode=" + gm + " started=" + storyAllowed)', handoff)
        self.assertIn('Game.GetFormFromFile(0x000800, "FO4SFMission.esm") as Quest', handoff)
        self.assertIn('Game.GetFormFromFile(0x000814, "FO4SFMission.esm") as Quest', handoff)
        self.assertIn("StartOptionalMissionQuest(0x000816)", handoff)
        self.assertIn('Trace("landing quests started min00=" + min00Ok + " keeper=" + keeperOk + " codsworth01=" + codsworth01Ok)', handoff)
        self.assertNotIn(".Start()", psc)
        s = ng.summarize(["[x] FO4SF_NEWGAME rt=10.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n",
                          "[x] FO4SF_NEWGAME rt=50.0 landing quests started min00=True keeper=True codsworth01=False\n"])
        self.assertEqual(s["landing_quests"], "min00=True keeper=True codsworth01=False")

    def test_s3_warfare_starts_table_and_refusal_of_unknown_marker(self):
        from fo4sf.core import warfare_starts as ws
        from fo4sf.core import start_worlds as sw
        entries = ws.load_warfare_starts()
        self.assertGreaterEqual(len(entries), 1)
        first = entries[0]
        self.assertEqual(first.key, "minutemen_sanctuary")
        self.assertEqual(first.faction_slot, 0)
        self.assertEqual(first.marker_edid, "FO4Core_CommonwealthMapMarkerSanctuary")
        self.assertEqual((first.min_difficulty, first.max_difficulty), (0, 3))
        self.assertEqual(first.squad_cap, 4)
        self.assertGreaterEqual(len(first.gear), 1)
        ws.load_warfare_starts(known_marker_edids={"FO4Core_CommonwealthMapMarkerSanctuary"})
        with self.assertRaisesRegex(ValueError, "unknown marker_edid"):
            ws.load_warfare_starts(known_marker_edids={"FO4Core_CommonwealthMapMarkerVault111"})
        # Legacy nonexistent-cell faction rows in start_worlds are marked inactive while world rows remain intact
        self.assertFalse(sw.get_start_world("minuteman_volunteer").active)
        self.assertTrue(sw.get_start_world("vault111").active)
        self.assertTrue(sw.get_start_world("goodsprings").active)

    def test_s4_mode_choice_chain_fade_hold_and_load_default(self):
        cs, psc = read(CS), read(PSC)
        self.assertIn('ModeButtons = { "Story", "Warfare" }', cs)
        self.assertIn('SurvivalButtons = { "Survival: No", "Survival: Yes" }', cs)
        self.assertIn('WarfareDiffButtons = { "Easy", "Normal", "Hard", "Very Hard" }', cs)
        self.assertIn("bool Property FadeHold = false Auto Const", psc)
        self.assertIn("int Property StartChoiceBackdrop = 1 Auto Const", psc)
        self.assertIn("float Property StartLoadTimeout = 15.0 Auto Const", psc)
        self.assertEqual(ng.tool_options(namespace()), [])
        self.assertEqual(ng.tool_options(namespace(fade_hold=True)), ["--fade-hold"])
        self.assertEqual(ng.tool_options(namespace(no_fade_hold=True)), ["--no-fade-hold"])
        self.assertEqual(
            ng.tool_options(namespace(start_choice_backdrop="title_card")),
            ["--start-choice-backdrop", "title_card"],
        )
        self.assertIn('Trace("start room ready by=" + by', psc)
        self.assertIn('Trace("mode fade lifted by=timeout s=" + (StartLoadTimeout as int))', psc)
        self.assertIn('Trace("mode choice mode=" + modeTag + " survival=" + survVal)', psc)
        self.assertIn('Trace("start record mode=" + modeTag + " story=" + storyId', psc)
        self.assertIn('Trace("mode load default=story stage=" + GetStage())', psc)
        self.assertIn('CastAs("FO4SF_HardcoreQuest")', psc)
        self.assertIn('CallFunction("EvaluateHardcore"', psc)
        s = ng.summarize([
            "[x] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n",
            "[x] FO4SF_NEWGAME rt=2.2 enter start room ok=True pos=0.0 0.0 0.0 cell=[Cell <FO4SF_StartRoomCell>]\n",
            "[x] FO4SF_NEWGAME rt=3.0 mode fade lifted by=timeout s=15\n",
            "[x] FO4SF_NEWGAME rt=5.0 mode choice mode=story survival=1\n",
            "[x] FO4SF_NEWGAME rt=5.05 start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=1 difficulty=1 backdrop=empty_cell\n",
            "[x] FO4SF_NEWGAME rt=5.1 stage 5 by=Trigger\n",
            "[x] FO4SF_NEWGAME rt=5.2 stage 10 by=Trigger\n",
            "[x] FO4SF_NEWGAME rt=20.0 mode load default=story stage=10\n",
        ])
        self.assertTrue(s["entered_start_room"])
        self.assertEqual(s["mode_fade_lifted"], "by=timeout s=15")
        self.assertEqual(s["mode_choice"], "mode=story survival=1")
        self.assertEqual(
            s["start_record"],
            "mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=1 difficulty=1 backdrop=empty_cell",
        )
        self.assertEqual(s["mode_load_default"], "story stage=10")
        self.assertEqual(s["stages"], [5, 10])

    def test_s5_warfare_branch_shared_map_setup_and_stage_210(self):
        psc = read(PSC)
        self.assertEqual(psc.count("int Function RunSharedMapSetup()"), 1)
        ascent = psc[psc.index("Function StartAscent"):psc.index("Event OnAnimationEvent")]
        wf = psc[psc.index("Function RunWarfareBranch"):psc.index("Event OnMenuOpenCloseEvent")]
        self.assertIn("RunSharedMapSetup()", ascent)
        self.assertIn("RunSharedMapSetup()", wf)
        self.assertIn('CastAs("FO4SF_ProgressionQuest")', wf)
        self.assertIn('CallFunction("OpenAttributeAllocation"', wf)
        self.assertIn('CallFunction("ApplyWarfareBackground"', wf)
        self.assertIn('Trace("warfare gear n=" + gearAdded)', wf)
        self.assertIn('Trace("warfare move ok=" + moveOk + " marker=" + wMarker + " dist=" + dist + " z=" + player.GetPositionZ())', wf)
        self.assertIn('CallFunction("DiscoverSingleMarker"', wf)
        self.assertIn('CallFunction("SetFactionScoresAbsolute"', wf)
        self.assertIn('CallFunction("SetKarmaAbsolute"', wf)
        self.assertIn("player.AddToFaction(fac)", wf)
        self.assertIn('Trace("warfare standing slot=" + slot', wf)
        self.assertIn('ForceFadeIn("warfare")', wf)
        self.assertIn("AdvanceTo(210)", wf)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        log_path = os.path.join(tmp, "fo4sf_newgame.0.log")
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write(
                "[x] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n"
                "[x] FO4SF_NEWGAME rt=3.0 mode fade held\n"
                "[x] FO4SF_NEWGAME rt=4.0 mode choice mode=warfare survival=0\n"
                "[x] FO4SF_NEWGAME rt=4.1 warfare pick faction=0 start=minutemen_sanctuary difficulty=1\n"
                "[x] FO4SF_NEWGAME rt=4.2 stage 5\n"
                "[x] FO4SF_NEWGAME rt=8.0 special set S=6 P=6 E=6 C=6 I=6 A=5 L=5 sum=40 source=warfare\n"
                "[x] FO4SF_NEWGAME rt=9.0 warfare gear n=4\n"
                "[x] FO4SF_NEWGAME rt=10.0 warfare move ok=True marker=[ObjectReference < (030A775A)>] dist=0.0 z=96.0\n"
                "[x] FO4SF_NEWGAME rt=10.2 map setup done markers=4 elapsed=0.05\n"
                "[x] FO4SF_NEWGAME rt=10.3 warfare standing slot=0 fame=45.0 infamy=0.0 karma=150.0 squad_cap=4\n"
                "[x] FO4SF_NEWGAME rt=10.4 stage 210\n"
            )
        with unittest.mock.patch("sys.stdout", io.StringIO()) as out:
            rc = ng.main(["log", "--file", log_path])
        self.assertEqual(rc, 0)
        summary = json.loads(out.getvalue())
        self.assertEqual(summary["stages"], [5, 210])
        self.assertEqual(summary["warfare_pick"], "faction=0 start=minutemen_sanctuary difficulty=1")
        self.assertEqual(summary["warfare_gear"], "4")
        self.assertEqual(summary["map_setup"], "markers=4 elapsed=0.05")

    def test_x1_console_only_gear_door_blocks_direct_activation_and_gates_shortcuts_on_test_mode(self):
        cs, psc = read(CS), read(PSC)
        self.assertIn('("ConsoleRefId", (int)p.Console)', cs)
        self.assertIn('GearDoorConsoleActiEdid = "FO4SF_GearDoorConsole"', cs)
        self.assertIn('GearDoorConsoleRefEdid = "FO4SF_GearDoorConsoleRef"', cs)
        self.assertIn("GearDoorConsoleActiId = 0x818", cs)
        self.assertIn("GearDoorConsoleRefId = 0x819", cs)
        self.assertIn('if (console == 0)\n            throw new Refusal(', cs)
        invault = psc[psc.index("Function InVault"):psc.index("Function StartAscent")]
        self.assertIn("if stage == 20 && CogDoorId > 0 && TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0", invault)
        self.assertIn("cogDoorWatchedRef.BlockActivation(True, False)", psc)
        self.assertIn('RegisterForRemoteEvent(cogDoorWatchedRef, "OnActivate")', psc)
        self.assertIn("consoleWatchedRef = GearDoorConsoleRef", psc)
        self.assertIn('RegisterForRemoteEvent(consoleWatchedRef, "OnActivate")', psc)
        self.assertIn('Trace("console activator registered ref=" + consoleWatchedRef', psc)
        self.assertIn('Trace("cog door activate blocked by=player open_state=" + curState)', psc)
        self.assertIn("Utility.Wait(2.0)", psc)
        self.assertIn('Trace("cog door console activated ref=" + consoleWatchedRef + " before=" + before + " after=" + after)', psc)
        self.assertIn('Trace("cog door open failed state=" + after)', psc)

    def test_x2_pipboy_pickup_console_gate_and_pistol_picked(self):
        cs, psc = read(CS), read(PSC)
        # A6 & A16: FO4SF_PipboyAcquired lives solely in FO4SFCoreValues.esm:000865; 0x80C and 0x810..0x816 stay reserved
        self.assertNotIn("PipboyAcquiredGlobId =", cs)
        self.assertIn('var pipboyAcquiredKey = new FormKey(coreKey, RequireCoreId(coreIds, PipboyAcquiredGlobEdid));', cs)
        self.assertIn("ReservedFormIds = { 0x80C, 0x810, 0x811, 0x812, 0x813, 0x814, 0x815, 0x816 }", cs)
        self.assertIn("PipboyWristArmorId = 0x80D", cs)
        self.assertIn("PipboyCorpseActiId = 0x80E", cs)
        self.assertIn("PipboyCorpseRefId = 0x80F", cs)
        self.assertIn("NoPipboyMsgId = 0x817", cs)
        self.assertIn("MaxMessageButtons = 7", cs)
        self.assertIn("Fo4PipboyPickup = 0x075039", cs)
        self.assertIn("Fo4PipboySkeleton = 0x0AB6AF", cs)
        self.assertIn('["pipboy_corpse"]', cs)
        self.assertIn("AddInventoryEventFilter(VaultPistolBase)", psc)
        self.assertLess(
            psc.index("AddInventoryEventFilter(VaultPistolBase)"),
            psc.index('RegisterForRemoteEvent(player as ObjectReference, "OnItemAdded")'),
        )
        self.assertIn('Trace("pistol filter added base=" + VaultPistolBase + " id=" + VaultPistolId)', psc)
        self.assertIn("if akBaseItem == VaultPistolBase", psc)
        self.assertIn('Trace("console refused: no pipboy")', psc)
        self.assertIn('Trace("pipboy pickup equipped flag=1 worn=" + worn)', psc)
        self.assertEqual(psc.count('Trace("pistol picked '), 1)
        z = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        z.close()
        try:
            fake_zip(z.name, remote=False, inventory_filter=False)
            r = ng.precheck_zip(z.name)
            self.assertIn("ScriptObject.RegisterForRemoteEvent", r["missing_core"])
            self.assertIn("ScriptObject.UnregisterForRemoteEvent", r["missing_core"])
            self.assertIn("ScriptObject.AddInventoryEventFilter", r["missing_core"])
        finally:
            os.unlink(z.name)

    def test_x3_three_button_lift_prompt_requires_40pt_special_before_continue_and_disables_special_skipped(self):
        cs, psc, special = read(CS), read(PSC), read(SPECIAL)
        self.assertIn('ExitButtons = { "Continue", "S.P.E.C.I.A.L.", "Stay" }', cs)
        self.assertIn('ExitNeedSpecialMsgEdid = "FO4SF_NewGameExitNeedSpecialMsg"', cs)
        self.assertIn("ExitNeedSpecialMsgId = 0x81F", cs)
        self.assertIn('ReturnMsgEdid = "FO4SF_NewGameReturn"', cs)
        self.assertIn("ReturnMsgId = 0x80B", cs)
        self.assertIn('"Ride down to Vault 111", "Stay"', cs)
        self.assertIn('Trace("elevator continue refused: special unconfirmed")', psc)
        self.assertIn("ExitNeedAttrMsg.Show()", psc)
        self.assertIn("OpenLiftAttributeAllocation()", psc)
        self.assertNotIn("OpenLiftCharacterRespec()", psc)
        self.assertIn('Game.GetFormFromFile(0x000880, "FO4SFProgression.esm")', psc)
        self.assertIn('CastAs("FO4SF_ProgressionQuest")', psc)
        self.assertIn('CastAs("FO4SF_NewGameSpecial")', psc)
        self.assertNotIn("as FO4SF_ProgressionQuest", psc)
        self.assertIn("PrepareArrivalMarkerDuringRide()", psc)
        self.assertIn("PreAttachArrivalMarker(player)", psc)
        self.assertIn("CheckReturnLift(player)", psc)
        self.assertIn("bool Property LegacyTerminalEnabled = false Auto Const", special)
        self.assertIn("if aiTimerID != 3 || !LegacyTerminalEnabled\n        return", special)
        audit = read(os.path.join(ROOT, "docs", "newgame", "lift-rules-audit.md"))
        for rule_num in range(1, 8):
            self.assertIn(f"### {rule_num}.", audit)
        self.assertIn("NOT BUILT", audit)

    def test_r4_stage_tools_refuse_worktree_and_game_output_folders(self):
        with self.assertRaisesRegex(SystemExit, "inside Git worktree"):
            ng.refuse_forbidden_out_dir(os.path.join(ROOT, "forbidden_stage_out"))
        with self.assertRaisesRegex(SystemExit, "Starfield"):
            ng.refuse_forbidden_out_dir(os.path.join(ng.STARFIELD, "Data", "forbidden_stage_out"))
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        ng.refuse_forbidden_out_dir(os.path.join(tmp, "allowed_stage_out"))

    def test_b6_and_b8_black_hold_after_loading_neutral_spot_waiting_timer_and_stage_causes(self):
        from types import SimpleNamespace
        from tests.test_exit_arrival import translated_functions

        psc = read(PSC)
        ev_menu = re.search(r"Event OnMenuOpenCloseEvent\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        ev_stage = re.search(r"Event OnStageSet\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        wrapped = (
            psc
            + f"\nFunction MenuEvent({ev_menu[1]})\n{ev_menu[2]}EndFunction\n"
            + f"\nFunction StageEvent({ev_stage[1]})\n{ev_stage[2]}EndFunction\n"
            + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
        )

        logs, fades, waits, timers, moves = [], [], [], [], []
        cur_stage = [0]
        neutral_val = [1.0]
        start_room_marker = SimpleNamespace(GetParentCell=lambda: "StartRoomCell")
        vault_anchor = SimpleNamespace(GetParentCell=lambda: "VaultCell")
        player = SimpleNamespace(
            pos=(9.1, -6.6, -0.9),
            cell="InitCell",
            GetPositionX=lambda: player.pos[0],
            GetPositionY=lambda: player.pos[1],
            GetPositionZ=lambda: player.pos[2],
            SetPosition=lambda x, y, z: setattr(player, "pos", (x, y, z)),
            SetAngle=lambda *a: None,
            MoveTo=lambda ref, dx, dy, dz, *rest: (
                moves.append((ref, dx, dy, dz)),
                setattr(player, "cell", ref.GetParentCell()),
                setattr(
                    player,
                    "pos",
                    (0.0 + dx, 0.0 + dy, 0.0 + dz)
                    if ref is start_room_marker
                    else (60.0 + dx, 25.0 + dy, 1.0 + dz),
                ),
            ),
            GetParentCell=lambda: player.cell,
            Is3DLoaded=lambda: True,
        )

        def show_mode_box():
            # At ModePickMsg.Show(): player must be in StartRoomCell (never VaultCell) with fade lifted!
            self.assertEqual(player.cell, "StartRoomCell")
            self.assertEqual(fades[-1], (False, True, 0.0, 0.1, False))
            ns["TimerEvent"](2)
            ns["TimerEvent"](2)
            return 0

        ns = dict(
            FadeHold=True, StartChoiceBackdrop=1, StartLoadTimeout=15.0, LooksWait=0.0, RaceMenuMode=2,
            ClearInventory=False, AnchorTemporary=False,
            faded=False, warfareFadeTicks=0, entered=False, startRoomMoves=0, startRoomEntered=False, startRoomUiPrepared=False,
            loadingMenuOpen=False, loadingMenuClosedSeen=False, loadingHookRegistered=False, startUiReady=False, h00SkipLoading=False,
            modeChoiceRan=False, modeBoxWaiting=False, modeBoxWaitSeconds=0,
            preworldLooksDone=False, preworldLooksHow="", preworldLooksBy="Trigger",
            setupWaitingCreator=False, warfareWaitingCreator=False,
            applied=0, pendingStage=-1, pendingStageBy="other", looksSetStage20=False,
            exitUsedFallback=False, vaultMoves=0, centered=0, centerTries=0, ticks=0, startedAt=0.0,
            VaultAnchorId=0x805, VaultPlugin="FO4Port.esm", VaultCell="FO4Port_Vault111Cryo", CenterTicks=30,
            AnchorX=60.0, AnchorY=25.0, AnchorZ=1.0,
            PodX=10.0, PodY=20.0, PodZ=1.0, PodLift=0.5, PodHeading=90.0,
            StartRoomMarkerRef=start_room_marker,
            StartCardOpenGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
            StartChoiceDoneGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
            StartNeutralSpotGlobal=SimpleNamespace(GetValue=lambda: neutral_val[0]),
            GameModeGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
            StoryLineGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
            StartPlaceRowGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
            SurvivalStartGlobal=SimpleNamespace(SetValue=lambda v: None),
            SurvivalLockedGlobal=SimpleNamespace(SetValue=lambda v: None),
            StartDifficultyGlobal=SimpleNamespace(SetValue=lambda v: None),
            WarfareFactionGlobal=SimpleNamespace(SetValue=lambda v: None),
            WarfareStartIndexGlobal=SimpleNamespace(SetValue=lambda v: None),
            H00SkipLoadingHookGlobal=SimpleNamespace(GetValue=lambda: 0.0),
            TestModeGlobal=SimpleNamespace(GetValue=lambda: 0.0),
            ModePickMsg=SimpleNamespace(Show=show_mode_box),
            StoryLineMsg=SimpleNamespace(Show=lambda: 0),
            SurvivalPickMsg=SimpleNamespace(Show=lambda: 0),
            StartPickMsg=None,
            StoryChoiceIds=["fo4_commonwealth"],
            StartPlaceIds=["fo4_vault111"],
            StartPlaceModes=[1],
            StartPlaceStories=["fo4_commonwealth"],
            StartPlacePlugins=["FO4Port.esm"],
            StartPlaceMarkerIds=[0x805],
            StartPlaceWarfareRows=[-1],
            Game=SimpleNamespace(
                GetPlayer=lambda: player,
                ShowFirstPersonGeometry=lambda *a: None,
                FadeOutGame=lambda *a: fades.append(a),
                SetInChargen=lambda *a: None,
                SetCharGenHUDMode=lambda *a: None,
                GetFormFromFile=lambda fid, plg: vault_anchor if (fid, plg) == (0x805, "FO4Port.esm") else None,
            ),
            Utility=SimpleNamespace(Wait=lambda s: waits.append(s), GetCurrentRealTime=lambda: 12.0),
            Debug=SimpleNamespace(Notification=lambda *a: None),
            InputEnableLayer=SimpleNamespace(Create=lambda: None),
            scannerLayer=None,
            RegisterForMenuOpenCloseEvent=lambda m: None,
            UnregisterForMenuOpenCloseEvent=lambda m: None,
            StartTimer=lambda s, tid: timers.append((s, tid)),
            SetStage=lambda n: cur_stage.__setitem__(0, n),
            GetStage=lambda: cur_stage[0],
            SetObjectiveDisplayed=lambda *a: None,
            SetObjectiveCompleted=lambda *a: None,
            SetActive=lambda *a: None,
            CompleteQuest=lambda: None,
            StartLandingQuests=lambda: None,
            EnsureLoadHookRegistered=lambda p: None,
            TriggerVaultPodRecoveryAutosave=lambda *a: None,
            CancelTimer=lambda *a: None,
            vaultSavingRelocked=False,
            Trace=lambda m: logs.append(m),
        )
        funcs = (
            "BackdropName", "UsePreworldRoom", "StandsInStartRoom", "EnterStartRoom", "PrepareStartRoomUi",
            "SetStartCardBackdrop", "WaitForStartUiReady", "HoldNeutralSpotForModeChoice",
            "RegisterStartLoadingHook", "UnregisterStartLoadingHook", "ReadH00Glob",
            "FindStoryStartPlaceRow", "FindWarfareStartPlaceRow", "RunPreworldLooksChoice", "SpawnAtStoryStartPlace",
            "EnterVault", "StandsInVault", "FadeIn", "DisableHandScanner",
            "NoteLooksStage20", "ClearVaultSaveLock", "ApplyStage", "AdvanceTo", "RunModeChoiceChain",
            "MenuEvent", "StageEvent", "TimerEvent",
        )
        vars_csv = (
            "faded, warfareFadeTicks, entered, startRoomMoves, startRoomEntered, startRoomUiPrepared, "
            "loadingMenuOpen, loadingMenuClosedSeen, loadingHookRegistered, startUiReady, h00SkipLoading, "
            "modeChoiceRan, modeBoxWaiting, modeBoxWaitSeconds, preworldLooksDone, preworldLooksHow, preworldLooksBy, "
            "setupWaitingCreator, warfareWaitingCreator, applied, pendingStage, pendingStageBy, "
            "looksSetStage20, exitUsedFallback, vaultMoves, centered, centerTries, ticks, startedAt, scannerLayer, vaultSavingRelocked"
        )
        exec(compile(translated_functions(wrapped, funcs, vars_csv), PSC, "exec"), ns)

        ns["EnterStartRoom"](player)
        ns["PrepareStartRoomUi"]("start")
        ns["RegisterStartLoadingHook"]()
        ns["MenuEvent"]("LoadingMenu", True)
        self.assertTrue(ns["loadingMenuOpen"])
        ns["MenuEvent"]("LoadingMenu", False)
        self.assertFalse(ns["loadingMenuOpen"])
        self.assertTrue(ns["loadingMenuClosedSeen"])

        chosen = ns["RunModeChoiceChain"](player)
        self.assertEqual(chosen, 1)
        self.assertIn("start room ready by=start loaded=True cell=StartRoomCell backdrop=empty_cell", logs)
        self.assertIn("mode loading menu closed", logs)
        self.assertTrue(any(l.startswith("mode neutral spot active ") for l in logs), logs)
        self.assertEqual([l for l in logs if l.startswith("mode box waiting ")], ["mode box waiting s=60", "mode box waiting s=120"])
        ns["TimerEvent"](2)
        self.assertEqual([l for l in logs if l.startswith("mode box waiting ")], ["mode box waiting s=60", "mode box waiting s=120"])
        self.assertIn(
            "start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=empty_cell",
            logs,
        )
        self.assertIn("stage 5 by=Trigger", logs)
        self.assertIn("stage 10 by=Trigger", logs)
        # Only AFTER start record does Story move the player into Vault 111 at the pod
        self.assertEqual(player.cell, "VaultCell")
        self.assertAlmostEqual(player.pos[0], 10.0, places=3)
        self.assertAlmostEqual(player.pos[1], 20.0, places=3)

        # B6 external console setstage (without AdvanceTo) logs by=other
        ns["StageEvent"](30, 0)
        self.assertIn("stage 30 by=other", logs)

    def test_h0_loading_menu_close_never_arrives_lifts_fade_and_shows_box(self):
        from types import SimpleNamespace
        from tests.test_exit_arrival import translated_functions

        psc = read(PSC)
        wrapped = psc
        funcs = (
            "BackdropName", "UsePreworldRoom", "StandsInStartRoom", "EnterStartRoom", "PrepareStartRoomUi",
            "SetStartCardBackdrop", "WaitForStartUiReady", "HoldNeutralSpotForModeChoice",
            "RegisterStartLoadingHook", "UnregisterStartLoadingHook", "ReadH00Glob",
            "FindStoryStartPlaceRow", "FindWarfareStartPlaceRow", "RunPreworldLooksChoice", "SpawnAtStoryStartPlace",
            "EnterVault", "StandsInVault", "FadeIn", "DisableHandScanner",
            "NoteLooksStage20", "ClearVaultSaveLock", "ApplyStage", "AdvanceTo", "RunModeChoiceChain",
        )
        vars_csv = (
            "faded, warfareFadeTicks, entered, startRoomMoves, startRoomEntered, startRoomUiPrepared, "
            "loadingMenuOpen, loadingMenuClosedSeen, loadingHookRegistered, startUiReady, h00SkipLoading, "
            "modeChoiceRan, modeBoxWaiting, modeBoxWaitSeconds, preworldLooksDone, preworldLooksHow, preworldLooksBy, "
            "setupWaitingCreator, warfareWaitingCreator, applied, pendingStage, pendingStageBy, "
            "looksSetStage20, exitUsedFallback, vaultMoves, centered, centerTries, ticks, startedAt, scannerLayer, vaultSavingRelocked"
        )
        compiled = compile(translated_functions(wrapped, funcs, vars_csv), PSC, "exec")

        # Test BOTH default path (neutral=0.0) and B8 neutral-spot path (neutral=1.0) when LoadingMenu close NEVER arrives
        for neutral_setting in (0.0, 1.0):
            with self.subTest(neutral=neutral_setting):
                logs, fades, waits, unregs, shown = [], [], [], [], []
                cur_stage = [0]
                start_room_marker = SimpleNamespace(GetParentCell=lambda: "StartRoomCell")
                vault_anchor = SimpleNamespace(GetParentCell=lambda: "VaultCell")
                player = SimpleNamespace(
                    pos=(0.0, 0.0, 0.0),
                    cell="StartRoomCell",
                    GetPositionX=lambda: player.pos[0],
                    GetPositionY=lambda: player.pos[1],
                    GetPositionZ=lambda: player.pos[2],
                    SetPosition=lambda x, y, z: setattr(player, "pos", (x, y, z)),
                    SetAngle=lambda *a: None,
                    MoveTo=lambda ref, dx, dy, dz, *rest: (
                        setattr(player, "cell", ref.GetParentCell()),
                        setattr(
                            player,
                            "pos",
                            (0.0 + dx, 0.0 + dy, 0.0 + dz)
                            if ref is start_room_marker
                            else (60.0 + dx, 25.0 + dy, 1.0 + dz),
                        ),
                    ),
                    GetParentCell=lambda: player.cell,
                    Is3DLoaded=lambda: True,
                )

                def on_mode_box_show():
                    # H0 acceptance: fade MUST be lifted and timeout logged BEFORE ModePickMsg.Show() blocks for input!
                    self.assertFalse(ns["loadingMenuOpen"])
                    self.assertFalse(ns["loadingHookRegistered"])
                    self.assertIn("LoadingMenu", unregs)
                    self.assertEqual(fades[-1], (False, True, 0.0, 0.1, False))
                    self.assertFalse(any(f[0] is True for f in fades), fades)
                    self.assertIn("mode fade lifted by=timeout s=15", logs)
                    shown.append("ModePickMsg")
                    return 0

                ns = dict(
                    FadeHold=True, StartChoiceBackdrop=1, StartLoadTimeout=15.0, LooksWait=0.0, RaceMenuMode=2,
                    ClearInventory=False, AnchorTemporary=False,
                    faded=False, warfareFadeTicks=0, entered=False, startRoomMoves=1, startRoomEntered=True, startRoomUiPrepared=True,
                    loadingMenuOpen=True, loadingMenuClosedSeen=False, loadingHookRegistered=True, startUiReady=False, h00SkipLoading=False,
                    modeChoiceRan=False, modeBoxWaiting=False, modeBoxWaitSeconds=0,
                    preworldLooksDone=False, preworldLooksHow="", preworldLooksBy="Trigger",
                    setupWaitingCreator=False, warfareWaitingCreator=False,
                    applied=0, pendingStage=-1, pendingStageBy="other", looksSetStage20=False,
                    exitUsedFallback=False, vaultMoves=0, centered=0, centerTries=0, ticks=0, startedAt=0.0,
                    VaultAnchorId=0x805, VaultPlugin="FO4Port.esm", VaultCell="FO4Port_Vault111Cryo", CenterTicks=30,
                    AnchorX=60.0, AnchorY=25.0, AnchorZ=1.0,
                    PodX=10.0, PodY=20.0, PodZ=1.0, PodLift=0.5, PodHeading=90.0,
                    StartRoomMarkerRef=start_room_marker,
                    StartCardOpenGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    StartChoiceDoneGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    StartNeutralSpotGlobal=SimpleNamespace(GetValue=lambda: neutral_setting),
                    GameModeGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    StoryLineGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    StartPlaceRowGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    SurvivalStartGlobal=SimpleNamespace(SetValue=lambda v: None),
                    SurvivalLockedGlobal=SimpleNamespace(SetValue=lambda v: None),
                    StartDifficultyGlobal=SimpleNamespace(SetValue=lambda v: None),
                    WarfareFactionGlobal=SimpleNamespace(SetValue=lambda v: None),
                    WarfareStartIndexGlobal=SimpleNamespace(SetValue=lambda v: None),
                    H00SkipLoadingHookGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                    TestModeGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                    ModePickMsg=SimpleNamespace(Show=on_mode_box_show),
                    StoryLineMsg=SimpleNamespace(Show=lambda: (shown.append("StoryLineMsg"), 0)[1]),
                    SurvivalPickMsg=SimpleNamespace(Show=lambda: (shown.append("SurvivalPickMsg"), 0)[1]),
                    StartPickMsg=None,
                    StoryChoiceIds=["fo4_commonwealth"],
                    StartPlaceIds=["fo4_vault111"],
                    StartPlaceModes=[1],
                    StartPlaceStories=["fo4_commonwealth"],
                    StartPlacePlugins=["FO4Port.esm"],
                    StartPlaceMarkerIds=[0x805],
                    StartPlaceWarfareRows=[-1],
                    Game=SimpleNamespace(
                        GetPlayer=lambda: player,
                        ShowFirstPersonGeometry=lambda *a: None,
                        FadeOutGame=lambda *a: fades.append(a),
                        SetInChargen=lambda *a: None,
                        SetCharGenHUDMode=lambda *a: None,
                        GetFormFromFile=lambda fid, plg: vault_anchor if (fid, plg) == (0x805, "FO4Port.esm") else None,
                    ),
                    # LoadingMenu close event NEVER fires during Wait!
                    Utility=SimpleNamespace(Wait=lambda s: waits.append(s), GetCurrentRealTime=lambda: 20.0),
                    Debug=SimpleNamespace(Notification=lambda *a: None),
                    InputEnableLayer=SimpleNamespace(Create=lambda: None),
                    scannerLayer=None,
                    RegisterForMenuOpenCloseEvent=lambda m: None,
                    UnregisterForMenuOpenCloseEvent=lambda m: unregs.append(m),
                    StartTimer=lambda *a: None,
                    SetStage=lambda n: cur_stage.__setitem__(0, n),
                    GetStage=lambda: cur_stage[0],
                    SetObjectiveDisplayed=lambda *a: None,
                    SetObjectiveCompleted=lambda *a: None,
                    SetActive=lambda *a: None,
                    CompleteQuest=lambda: None,
                    StartLandingQuests=lambda: None,
                    EnsureLoadHookRegistered=lambda p: None,
                    TriggerVaultPodRecoveryAutosave=lambda *a: None,
                    CancelTimer=lambda *a: None,
                    vaultSavingRelocked=False,
                    Trace=lambda m: logs.append(m),
                )
                exec(compiled, ns)

                chosen = ns["RunModeChoiceChain"](player)
                self.assertEqual(chosen, 1)
                self.assertAlmostEqual(sum(waits), 15.75, places=2)
                self.assertEqual(shown, ["ModePickMsg", "StoryLineMsg", "SurvivalPickMsg"])
                self.assertIn("mode fade lifted by=timeout s=15", logs)
                self.assertTrue(any(l.startswith("start ui ready released_by=timeout_delay waited_s=") for l in logs), logs)
                if neutral_setting >= 0.5:
                    self.assertTrue(any(l.startswith("mode neutral spot active ") for l in logs), logs)
                self.assertEqual(player.cell, "VaultCell")
                self.assertEqual(cur_stage[0], 20)

    def test_n2_and_card4_start_places_table_and_warfare_pre_creator_special(self):
        from types import SimpleNamespace
        from fo4sf.core import start_places as sp
        from tests.test_exit_arrival import translated_functions

        # 1. Start-places table validation: available vs unbuilt rows, and refusal of unresolvable available rows
        all_rows = sp.load_start_places()
        avail_rows = sp.load_start_places(
            available_only=True,
            known_plugins={"FO4Port.esm", "FO4TerrainCore.esm"},
            known_marker_edids={"FO4Core_CommonwealthMapMarkerSanctuary"},
        )
        self.assertEqual([r.id for r in avail_rows], ["fo4_vault111", "minutemen_sanctuary"])
        unavail_ids = {r.id for r in all_rows if not r.available}
        self.assertIn("fnv_goodsprings", unavail_ids)
        self.assertIn("fo3_vault101", unavail_ids)
        self.assertEqual(sp.available_story_choices(all_rows), [("fo4_commonwealth", "Fallout 4: Commonwealth")])

        with self.assertRaisesRegex(ValueError, "not loaded"):
            sp.load_start_places(known_plugins={"FO4Port.esm"})
        with self.assertRaisesRegex(ValueError, "marker_edid"):
            sp.load_start_places(
                known_plugins={"FO4Port.esm", "FO4TerrainCore.esm"},
                known_marker_edids=set(),
            )

        # 2. N2 + Card 4 translated execution: Warfare with title_card backdrop + S.P.E.C.I.A.L. BEFORE ShowRaceMenu + R10 fallback
        psc = read(PSC)
        ev_menu = re.search(r"Event OnMenuOpenCloseEvent\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        wrapped = psc + f"\nFunction MenuEvent({ev_menu[1]})\n{ev_menu[2]}EndFunction\n"
        funcs = (
            "BackdropName", "UsePreworldRoom", "StandsInStartRoom", "EnterStartRoom", "PrepareStartRoomUi",
            "SetStartCardBackdrop", "WaitForStartUiReady", "HoldNeutralSpotForModeChoice",
            "RegisterStartLoadingHook", "UnregisterStartLoadingHook", "ReadH00Glob",
            "FindStoryStartPlaceRow", "FindWarfareStartPlaceRow", "RunPreworldLooksChoice",
            "RunWarfareBranch", "RunSharedMapSetup", "FillO2", "FadeIn", "ForceFadeIn", "DisableHandScanner",
            "NoteLooksStage20", "ClearVaultSaveLock", "ApplyStage", "AdvanceTo", "RunModeChoiceChain", "MenuEvent",
        )
        vars_csv = (
            "faded, warfareFadeTicks, entered, startRoomMoves, startRoomEntered, startRoomUiPrepared, "
            "loadingMenuOpen, loadingMenuClosedSeen, loadingHookRegistered, startUiReady, h00SkipLoading, h00SkipMap, "
            "modeChoiceRan, modeBoxWaiting, modeBoxWaitSeconds, preworldLooksDone, preworldLooksHow, preworldLooksBy, "
            "setupWaitingCreator, warfareWaitingCreator, mapSetupDone, applied, pendingStage, pendingStageBy, "
            "looksSetStage20, exitUsedFallback, vaultMoves, centered, centerTries, ticks, startedAt, scannerLayer, vaultSavingRelocked"
        )
        compiled = compile(translated_functions(wrapped, funcs, vars_csv), PSC, "exec")

        for cancel_all_tries in (False, True):
            with self.subTest(cancel_all_tries=cancel_all_tries):
                logs, events, card_vals, chargen_state = [], [], [], [False]
                cur_stage = [0]
                start_room_marker = SimpleNamespace(GetParentCell=lambda: "StartRoomCell")
                sanctuary_cell = SimpleNamespace(GetFormID=lambda: 0x03001000)
                sanctuary_marker = SimpleNamespace(
                    GetFormID=lambda: 0x030A775A,
                    GetParentCell=lambda: sanctuary_cell,
                    GetWorldSpace=lambda: "CommonwealthWorld",
                    Enable=lambda *a: None,
                    MoveTo=lambda *a: None,
                    SetPosition=lambda *a: None,
                )
                player = SimpleNamespace(
                    pos=(0.0, 0.0, 0.0),
                    cell="StartRoomCell",
                    interior=True,
                    GetPositionX=lambda: player.pos[0],
                    GetPositionY=lambda: player.pos[1],
                    GetPositionZ=lambda: player.pos[2],
                    SetPosition=lambda x, y, z: setattr(player, "pos", (x, y, z)),
                    SetAngle=lambda *a: None,
                    MoveTo=lambda ref, dx, dy, dz, *rest: (
                        events.append("MoveToWarfareStart" if ref is sanctuary_marker else "MoveToStartRoom"),
                        setattr(player, "cell", ref.GetParentCell()),
                        setattr(player, "interior", ref is start_room_marker),
                    ),
                    GetParentCell=lambda: player.cell,
                    GetWorldSpace=lambda: None if player.interior else "CommonwealthWorld",
                    IsInInterior=lambda: player.interior,
                    Is3DLoaded=lambda: True,
                    RemoveAllItems=lambda *a: None,
                    AddItem=lambda *a: None,
                    EquipItem=lambda *a: None,
                    GetValue=lambda av: 100.0,
                    ModValue=lambda av, d: None,
                    AddToFaction=lambda f: None,
                )

                def open_alloc(src):
                    # Card 4: S.P.E.C.I.A.L. runs BEFORE ShowRaceMenu while SetInChargen is False and still in StartRoomCell!
                    self.assertEqual(src, "warfare")
                    self.assertFalse(chargen_state[0])
                    self.assertEqual(player.cell, "StartRoomCell")
                    self.assertNotIn("ShowRaceMenu", events)
                    events.append("OpenAttributeAllocation")
                    return False if cancel_all_tries else True

                def offer_spread(src, allow_back):
                    self.assertEqual((src, allow_back), ("warfare", False))
                    events.append("OfferStandardSpread")
                    return True

                prog = SimpleNamespace(
                    OpenAttributeAllocation=open_alloc,
                    OfferStandardSpread=offer_spread,
                    ApplyWarfareBackground=lambda idx: events.append(f"Bg:{idx}"),
                )

                def show_race_menu(*a):
                    events.append("ShowRaceMenu")
                    chargen_state[0] = True
                    ns["MenuEvent"]("ChargenMenu", False)

                ns = dict(
                    FadeHold=True, StartChoiceBackdrop=2, StartLoadTimeout=15.0, LooksWait=10.0, RaceMenuMode=2,
                    ClearInventory=True, AnchorTemporary=False, O2Capacity=None, O2CapacityAmount=0.0,
                    SurfaceWait=1.0, SurfaceTries=3, FallDrop=3.0, MergeOffsetX=-1200.0, MergeOffsetY=-2700.0,
                    ArrivalX=0.0, ArrivalY=0.0, ArrivalZ=0.0,
                    ExitAnchorId=0x0A7759, CorePlugin="FO4TerrainCore.esm",
                    VaultAnchorId=0x805, VaultPlugin="FO4Port.esm",
                    faded=False, warfareFadeTicks=0, entered=False, startRoomMoves=1, startRoomEntered=True, startRoomUiPrepared=True,
                    loadingMenuOpen=False, loadingMenuClosedSeen=True, loadingHookRegistered=False, startUiReady=False,
                    h00SkipLoading=False, h00SkipMap=False,
                    modeChoiceRan=False, modeBoxWaiting=False, modeBoxWaitSeconds=0,
                    preworldLooksDone=False, preworldLooksHow="", preworldLooksBy="Trigger",
                    setupWaitingCreator=False, warfareWaitingCreator=False, mapSetupDone=False,
                    applied=0, pendingStage=-1, pendingStageBy="other", looksSetStage20=False,
                    exitUsedFallback=False, vaultMoves=0, centered=0, centerTries=0, ticks=0, startedAt=0.0,
                    StartRoomMarkerRef=start_room_marker,
                    PipboyWristArmor=SimpleNamespace(),
                    PipboyAcquiredGlobal=SimpleNamespace(SetValue=lambda v: None),
                    StartCardOpenGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: card_vals.append(v)),
                    StartChoiceDoneGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    StartNeutralSpotGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                    GameModeGlobal=SimpleNamespace(GetValue=lambda: 2.0, SetValue=lambda v: None),
                    StoryLineGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    StartPlaceRowGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    SurvivalStartGlobal=SimpleNamespace(SetValue=lambda v: None),
                    SurvivalLockedGlobal=SimpleNamespace(SetValue=lambda v: None),
                    StartDifficultyGlobal=SimpleNamespace(SetValue=lambda v: None),
                    WarfareFactionGlobal=SimpleNamespace(SetValue=lambda v: None),
                    WarfareStartIndexGlobal=SimpleNamespace(SetValue=lambda v: None),
                    H00SkipLoadingHookGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                    TestModeGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                    ModePickMsg=SimpleNamespace(Show=lambda: 1),
                    StoryLineMsg=SimpleNamespace(Show=lambda: 0),
                    SurvivalPickMsg=SimpleNamespace(Show=lambda: 0),
                    WarfareDiffMsg=SimpleNamespace(Show=lambda: 0),
                    WarfareGroupMsg=SimpleNamespace(Show=lambda: 0),
                    WarfareSpotMsg=SimpleNamespace(Show=lambda: 0),
                    StartPickMsg=SimpleNamespace(Show=lambda: 1),
                    StoryChoiceIds=["fo4_commonwealth"],
                    StartPlaceIds=["fo4_vault111", "minutemen_sanctuary"],
                    StartPlaceModes=[1, 2],
                    StartPlaceStories=["fo4_commonwealth", "none"],
                    StartPlacePlugins=["FO4Port.esm", "FO4TerrainCore.esm"],
                    StartPlaceMarkerIds=[0x805, 0x0A775A],
                    StartPlaceWarfareRows=[-1, 0],
                    WarfareKeys=["minutemen_sanctuary"],
                    WarfareFactionSlots=[0],
                    WarfareDistinctFactionSlots=[0],
                    WarfareMarkerIds=[0x0A775A],
                    WarfareMarkerX=[100.0],
                    WarfareMarkerY=[200.0],
                    WarfareMarkerZ=[95.0],
                    WarfareHeadings=[180.0],
                    WarfareMinDiffs=[0],
                    WarfareMaxDiffs=[3],
                    WarfareBgIndices=[0],
                    WarfareFames=[45.0],
                    WarfareInfamies=[0.0],
                    WarfareKarmas=[150.0],
                    WarfareSquadCaps=[4],
                    WarfareGearRowIndices=[0],
                    WarfareGearPlugins=["Starfield.esm"],
                    WarfareGearIds=[0x100],
                    WarfareGearCounts=[1],
                    WarfareGearEquips=[True],
                    CoreMarkerIds=[0x0A775A],
                    MapMarkerQuestIds=[],
                    Game=SimpleNamespace(
                        GetPlayer=lambda: player,
                        ShowFirstPersonGeometry=lambda *a: None,
                        FadeOutGame=lambda *a: None,
                        SetInChargen=lambda a, b, c: chargen_state.__setitem__(0, bool(a or b or c)),
                        SetCharGenHUDMode=lambda *a: None,
                        ShowRaceMenu=show_race_menu,
                        GetFormFromFile=lambda fid, plg: (
                            prog if (fid, plg) == (0x000880, "FO4SFProgression.esm")
                            else sanctuary_marker if (fid, plg) == (0x0A775A, "FO4TerrainCore.esm")
                            else SimpleNamespace() if plg == "Starfield.esm"
                            else None
                        ),
                    ),
                    Utility=SimpleNamespace(
                        Wait=lambda s: events.append(f"Wait({s})") if s == 2.0 else None,
                        GetCurrentRealTime=lambda: 30.0,
                    ),
                    Debug=SimpleNamespace(Notification=lambda *a: None),
                    InputEnableLayer=SimpleNamespace(Create=lambda: None),
                    scannerLayer=None,
                    RegisterForMenuOpenCloseEvent=lambda m: None,
                    UnregisterForMenuOpenCloseEvent=lambda m: None,
                    StartTimer=lambda *a: None,
                    SetStage=lambda n: (cur_stage.__setitem__(0, n), events.append(f"Stage{n}")),
                    GetStage=lambda: cur_stage[0],
                    SetObjectiveDisplayed=lambda *a: None,
                    SetObjectiveCompleted=lambda *a: None,
                    SetActive=lambda *a: None,
                    CompleteQuest=lambda: None,
                    StartLandingQuests=lambda: None,
                    TriggerVaultPodRecoveryAutosave=lambda *a: None,
                    CancelTimer=lambda *a: None,
                    vaultSavingRelocked=False,
                    Trace=lambda m: logs.append(m),
                )
                exec(compiled, ns)

                chosen = ns["RunModeChoiceChain"](player)
                self.assertEqual(chosen, 2)
                self.assertEqual(ns["vaultMoves"], 0)
                self.assertEqual(card_vals[0], 1.0)
                self.assertEqual(card_vals[-1], 0.0)
                self.assertIn(
                    "start record mode=warfare story=none faction=0 place=minutemen_sanctuary survival=0 difficulty=0 backdrop=title_card",
                    logs,
                )
                self.assertLess(events.index("OpenAttributeAllocation"), events.index("ShowRaceMenu"))
                self.assertLess(events.index("ShowRaceMenu"), events.index("Wait(2.0)"))
                self.assertLess(events.index("Wait(2.0)"), events.index("MoveToWarfareStart"))
                if cancel_all_tries:
                    self.assertEqual(events.count("OpenAttributeAllocation"), 3)
                    self.assertIn("OfferStandardSpread", events)
                else:
                    self.assertEqual(events.count("OpenAttributeAllocation"), 1)
                    self.assertNotIn("OfferStandardSpread", events)
                self.assertFalse(chargen_state[0])
                self.assertEqual(cur_stage[0], 210)

    def test_s1_s2_s3_s4_setup_menu_swap_parity_fallback_and_study_docs(self):
        from types import SimpleNamespace
        from fo4sf.core import start_places as sp
        from tests.test_exit_arrival import translated_functions

        psc = read(PSC)
        funcs = (
            "BackdropName", "UsePreworldRoom", "StandsInStartRoom", "EnterStartRoom", "PrepareStartRoomUi",
            "SetStartCardBackdrop", "WaitForStartUiReady", "HoldNeutralSpotForModeChoice",
            "RegisterStartLoadingHook", "UnregisterStartLoadingHook", "ReadH00Glob",
            "FindStoryStartPlaceRow", "FindWarfareStartPlaceRow", "RunPreworldLooksChoice",
            "SpawnAtStoryStartPlace", "EnterVault", "StandsInVault", "ResetInventory",
            "RunWarfareBranch", "RunSharedMapSetup", "FillO2", "FadeIn", "ForceFadeIn", "DisableHandScanner",
            "NoteLooksStage20", "ClearVaultSaveLock", "ApplyStage", "AdvanceTo", "RunModeChoiceChain",
        )
        vars_csv = (
            "faded, warfareFadeTicks, entered, startRoomMoves, startRoomEntered, startRoomUiPrepared, "
            "loadingMenuOpen, loadingMenuClosedSeen, loadingHookRegistered, startUiReady, h00SkipLoading, h00SkipMap, "
            "modeChoiceRan, modeBoxWaiting, modeBoxWaitSeconds, preworldLooksDone, preworldLooksHow, preworldLooksBy, "
            "setupWaitingCreator, warfareWaitingCreator, mapSetupDone, applied, pendingStage, pendingStageBy, "
            "looksSetStage20, exitUsedFallback, vaultMoves, centered, centerTries, ticks, startedAt, scannerLayer, vaultSavingRelocked"
        )
        compiled = compile(translated_functions(psc, funcs, vars_csv), PSC, "exec")
        rows = sp.load_start_places()

        def run_flow(backdrop_val: int, mode_is_warfare: bool, survival_on: bool, diff_val: int, native_setup_ack: bool = True):
            store = {
                "StartCardOpen": 0.0,
                "GameMode": 0.0,
                "StoryLine": 0.0,
                "SurvivalStart": 0.0,
                "SurvivalLocked": 0.0,
                "StartDifficulty": 0.0,
                "WarfareFaction": -1.0,
                "WarfareStartIndex": -1.0,
                "StartChoiceDone": 0.0,
                "StartPlaceRow": 0.0,
            }

            def make_glob(key):
                def _set(v):
                    store[key] = float(v)
                    if key == "StartCardOpen" and float(v) >= 1.5 and native_setup_ack:
                        # Native FO4SF_SetupMenu opens (ack 3.0) and commits exact SetupScreenModel payload!
                        model = sp.SetupScreenModel(rows)
                        if mode_is_warfare:
                            model.adjust_row(0, 1)
                        if survival_on:
                            model.adjust_row(3, 1)
                        while model.difficulty != diff_val:
                            model.adjust_row(4, 1)
                        payload = model.confirm()
                        assert payload is not None
                        store["GameMode"] = float(payload.mode_val)
                        store["StoryLine"] = float(payload.story_choice_idx)
                        store["SurvivalStart"] = float(payload.survival)
                        store["SurvivalLocked"] = float(payload.survival)
                        store["StartDifficulty"] = float(payload.difficulty)
                        store["WarfareFaction"] = float(payload.warfare_faction_slot)
                        store["WarfareStartIndex"] = float(payload.warfare_start_idx)
                        store["StartPlaceRow"] = float(payload.start_place_row)
                        store["StartCardOpen"] = 3.0
                        store["StartChoiceDone"] = 1.0

                return SimpleNamespace(GetValue=lambda: store[key], SetValue=_set)

            logs, cur_stage, msg_calls = [], [0], []
            start_room_marker = SimpleNamespace(GetParentCell=lambda: "StartRoomCell")
            vault_anchor = SimpleNamespace(GetParentCell=lambda: "VaultCell")
            sanctuary_cell = SimpleNamespace(GetFormID=lambda: 0x03001000)
            sanctuary_marker = SimpleNamespace(
                GetFormID=lambda: 0x030A775A,
                GetParentCell=lambda: sanctuary_cell,
                GetWorldSpace=lambda: "CommonwealthWorld",
                Enable=lambda *a: None,
                MoveTo=lambda *a: None,
                SetPosition=lambda *a: None,
            )
            player = SimpleNamespace(
                pos=(0.0, 0.0, 0.0),
                cell="StartRoomCell",
                interior=True,
                GetPositionX=lambda: player.pos[0],
                GetPositionY=lambda: player.pos[1],
                GetPositionZ=lambda: player.pos[2],
                SetPosition=lambda x, y, z: setattr(player, "pos", (x, y, z)),
                SetAngle=lambda *a: None,
                MoveTo=lambda ref, *rest: (
                    setattr(player, "cell", ref.GetParentCell()),
                    setattr(player, "interior", ref is not sanctuary_marker),
                ),
                GetParentCell=lambda: player.cell,
                GetWorldSpace=lambda: None if player.interior else "CommonwealthWorld",
                IsInInterior=lambda: player.interior,
                Is3DLoaded=lambda: True,
                GetItemCount=lambda *a: 0,
                RemoveAllItems=lambda *a: None,
                AddItem=lambda *a: None,
                EquipItem=lambda *a: None,
                IsEquipped=lambda *a: True,
                GetValue=lambda av: 100.0,
                ModValue=lambda av, d: None,
                AddToFaction=lambda f: None,
            )
            ns = dict(
                FadeHold=True, StartChoiceBackdrop=backdrop_val, StartLoadTimeout=15.0, LooksWait=0.0, RaceMenuMode=2,
                ClearInventory=True, VaultSuitId=0, AnchorTemporary=False, O2Capacity=None, O2CapacityAmount=0.0,
                SurfaceWait=1.0, SurfaceTries=3, FallDrop=3.0, MergeOffsetX=-1200.0, MergeOffsetY=-2700.0,
                ArrivalX=0.0, ArrivalY=0.0, ArrivalZ=0.0,
                AnchorX=0.0, AnchorY=0.0, AnchorZ=0.0, PodX=0.0, PodY=0.0, PodZ=0.0, PodLift=0.3, PodHeading=0.0,
                ExitAnchorId=0x0A7759, CorePlugin="FO4TerrainCore.esm",
                VaultAnchorId=0x805, VaultPlugin="FO4Port.esm", VaultCell="FO4Port_Vault111Cryo", CenterTicks=30,
                faded=False, warfareFadeTicks=0, entered=False, startRoomMoves=1, startRoomEntered=True, startRoomUiPrepared=True,
                loadingMenuOpen=False, loadingMenuClosedSeen=True, loadingHookRegistered=False, startUiReady=False,
                h00SkipLoading=False, h00SkipMap=False,
                modeChoiceRan=False, modeBoxWaiting=False, modeBoxWaitSeconds=0,
                preworldLooksDone=False, preworldLooksHow="", preworldLooksBy="Trigger",
                setupWaitingCreator=False, warfareWaitingCreator=False, mapSetupDone=False,
                applied=0, pendingStage=-1, pendingStageBy="other", looksSetStage20=False,
                exitUsedFallback=False, vaultMoves=0, centered=0, centerTries=0, ticks=0, startedAt=0.0,
                StartRoomMarkerRef=start_room_marker,
                PipboyWristArmor=SimpleNamespace(),
                PipboyAcquiredGlobal=SimpleNamespace(SetValue=lambda v: None),
                StartCardOpenGlobal=make_glob("StartCardOpen"),
                StartChoiceDoneGlobal=make_glob("StartChoiceDone"),
                StartNeutralSpotGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                GameModeGlobal=make_glob("GameMode"),
                StoryLineGlobal=make_glob("StoryLine"),
                StartPlaceRowGlobal=make_glob("StartPlaceRow"),
                SurvivalStartGlobal=make_glob("SurvivalStart"),
                SurvivalLockedGlobal=make_glob("SurvivalLocked"),
                StartDifficultyGlobal=make_glob("StartDifficulty"),
                WarfareFactionGlobal=make_glob("WarfareFaction"),
                WarfareStartIndexGlobal=make_glob("WarfareStartIndex"),
                H00SkipLoadingHookGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                TestModeGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                ModePickMsg=SimpleNamespace(Show=lambda: (msg_calls.append("ModePickMsg"), 1 if mode_is_warfare else 0)[1]),
                StoryLineMsg=SimpleNamespace(Show=lambda: (msg_calls.append("StoryLineMsg"), 0)[1]),
                SurvivalPickMsg=SimpleNamespace(Show=lambda: (msg_calls.append("SurvivalPickMsg"), 1 if survival_on else 0)[1]),
                WarfareDiffMsg=SimpleNamespace(Show=lambda: (msg_calls.append("WarfareDiffMsg"), diff_val)[1]),
                WarfareGroupMsg=SimpleNamespace(Show=lambda: (msg_calls.append("WarfareGroupMsg"), 0)[1]),
                WarfareSpotMsg=SimpleNamespace(Show=lambda: 0),
                StartPickMsg=None,
                StoryChoiceIds=["fo4_commonwealth"],
                StartPlaceIds=["fo4_vault111", "minutemen_sanctuary"],
                StartPlaceModes=[1, 2],
                StartPlaceStories=["fo4_commonwealth", "none"],
                StartPlacePlugins=["FO4Port.esm", "FO4TerrainCore.esm"],
                StartPlaceMarkerIds=[0x805, 0x0A775A],
                StartPlaceWarfareRows=[-1, 0],
                WarfareKeys=["minutemen_sanctuary"],
                WarfareFactionSlots=[0],
                WarfareDistinctFactionSlots=[0],
                WarfareMarkerIds=[0x0A775A],
                WarfareMarkerX=[100.0],
                WarfareMarkerY=[200.0],
                WarfareMarkerZ=[95.0],
                WarfareHeadings=[180.0],
                WarfareMinDiffs=[0],
                WarfareMaxDiffs=[3],
                WarfareBgIndices=[0],
                WarfareFames=[45.0],
                WarfareInfamies=[0.0],
                WarfareKarmas=[150.0],
                WarfareSquadCaps=[4],
                WarfareGearRowIndices=[0],
                WarfareGearPlugins=["Starfield.esm"],
                WarfareGearIds=[0x100],
                WarfareGearCounts=[1],
                WarfareGearEquips=[True],
                CoreMarkerIds=[0x0A775A],
                MapMarkerQuestIds=[],
                Game=SimpleNamespace(
                    GetPlayer=lambda: player,
                    ShowFirstPersonGeometry=lambda *a: None,
                    FadeOutGame=lambda *a: None,
                    SetInChargen=lambda *a: None,
                    SetCharGenHUDMode=lambda *a: None,
                    GetFormFromFile=lambda fid, plg: (
                        vault_anchor if (fid, plg) == (0x805, "FO4Port.esm")
                        else sanctuary_marker if (fid, plg) == (0x0A775A, "FO4TerrainCore.esm")
                        else SimpleNamespace() if plg == "Starfield.esm"
                        else None
                    ),
                ),
                Utility=SimpleNamespace(Wait=lambda s: None, GetCurrentRealTime=lambda: 10.0),
                Debug=SimpleNamespace(Notification=lambda *a: None),
                InputEnableLayer=SimpleNamespace(Create=lambda: None),
                scannerLayer=None,
                RegisterForMenuOpenCloseEvent=lambda m: None,
                UnregisterForMenuOpenCloseEvent=lambda m: None,
                StartTimer=lambda *a: None,
                SetStage=lambda n: cur_stage.__setitem__(0, n),
                GetStage=lambda: cur_stage[0],
                SetObjectiveDisplayed=lambda *a: None,
                SetObjectiveCompleted=lambda *a: None,
                SetActive=lambda *a: None,
                CompleteQuest=lambda: None,
                StartLandingQuests=lambda: None,
                TriggerVaultPodRecoveryAutosave=lambda *a: None,
                CancelTimer=lambda *a: None,
                vaultSavingRelocked=False,
                Trace=lambda m: logs.append(m),
            )
            exec(compiled, ns)
            chosen = ns["RunModeChoiceChain"](player)
            cell_tag = player.cell if isinstance(player.cell, str) else f"0x{player.cell.GetFormID():08X}"
            return chosen, store, logs, cur_stage[0], msg_calls, cell_tag

        # 1. Exact Variant (a) vs Variant (b) store + start-record + stage parity across Story & Warfare
        for wf_flag, surv_flag, diff_v, want_stage, want_cell in (
            (False, True, 1, 20, "VaultCell"),
            (True, True, 2, 210, sanctuary_cell := None),
        ):
            c_a, st_a, logs_a, stg_a, msgs_a, cell_a = run_flow(1, wf_flag, surv_flag, diff_v)
            c_b, st_b, logs_b, stg_b, msgs_b, cell_b = run_flow(3, wf_flag, surv_flag, diff_v)
            self.assertEqual(c_a, c_b)
            self.assertEqual(stg_a, want_stage)
            self.assertEqual(stg_b, want_stage)
            self.assertEqual(cell_a, cell_b)
            self.assertTrue(msgs_a)
            self.assertEqual(msgs_b, [])  # Variant (b) showed ZERO sequential MessageBox prompts!
            for k in ("GameMode", "StoryLine", "SurvivalStart", "SurvivalLocked", "StartDifficulty", "WarfareFaction", "WarfareStartIndex", "StartChoiceDone", "StartPlaceRow"):
                self.assertEqual(st_a[k], st_b[k], k)
            rec_a = next(l for l in logs_a if l.startswith("start record "))
            rec_b = next(l for l in logs_b if l.startswith("start record "))
            self.assertEqual(rec_a.replace("backdrop=empty_cell", "backdrop=setup_menu"), rec_b)

        # 2. R10 fallback: when FO4SF_SetupMenu does not open (no native ack), falls back cleanly to Variant (a) boxes
        c_fb, st_fb, logs_fb, stg_fb, msgs_fb, _ = run_flow(3, False, False, 1, native_setup_ack=False)
        self.assertEqual((c_fb, stg_fb), (1, 20))
        self.assertIn("setup menu unavailable: falling back to empty_cell boxes", logs_fb)
        self.assertEqual(msgs_fb, ["ModePickMsg", "StoryLineMsg", "SurvivalPickMsg"])
        self.assertIn(
            "start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=empty_cell",
            logs_fb,
        )

        # 3. S2 & S4 study documents exist, hold zero local paths, and carry required truth/scope markers
        s2_doc = read(os.path.join(ROOT, "docs", "newgame", "setup-options-proposal.md"))
        s4_doc = read(os.path.join(ROOT, "docs", "newgame", "character-looks-study.md"))
        for doc_txt in (s2_doc, s4_doc):
            self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", doc_txt))
        self.assertIn("BUILD NONE OF THE NEW OPTIONS THIS ROUND", s2_doc)
        for effort_tag in ("**`exists`**", "**`small`**", "**`large`**"):
            self.assertIn(effort_tag, s2_doc)
        self.assertIn("STUDY ONLY", s4_doc)
        self.assertIn("NOT OURS", s4_doc)

    def test_r6_t4_t3_story_timer1_alive_single_looks_box_and_loading_menu_wait(self):
        """R6 T4 + T3 translated execution:
        1) Story preworld start keeps Timer 1 alive after RunModeChoiceChain returns 1 with GetStage() >= 10,
           advances straight to stage 20 inside SpawnAtStoryStartPlace, and blocks FO4SF_NewGameLooks from
           showing 0x802 a second time in Vault 111.
        2) T3 LoadingMenu close arriving while WaitForStartUiReady waits (after modeChoiceRan=true) is NOT
           dropped, runs 0.75s settle, and logs start ui ready released_by=... for close/already_loaded/timeout.
        """
        from types import SimpleNamespace
        from tests.test_exit_arrival import translated_functions

        psc = read(PSC)
        looks_psc = read(LOOKS)
        cs = read(CS)
        self.assertIn("VaultPistolRefId = 0x820", cs)
        self.assertIn("VaultAmmoRefId = 0x821", cs)
        self.assertIn("VaultAmmoCount = 48", cs)

        ev_menu = re.search(r"Event OnMenuOpenCloseEvent\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        wrapped = (
            psc
            + f"\nFunction MenuEvent({ev_menu[1]})\n{ev_menu[2]}EndFunction\n"
            + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
        )
        funcs = (
            "BackdropName", "UsePreworldRoom", "StandsInStartRoom", "EnterStartRoom", "PrepareStartRoomUi",
            "SetStartCardBackdrop", "WaitForStartUiReady", "HoldNeutralSpotForModeChoice",
            "RegisterStartLoadingHook", "UnregisterStartLoadingHook", "ReadH00Glob",
            "FindStoryStartPlaceRow", "FindWarfareStartPlaceRow", "RunPreworldLooksChoice",
            "SpawnAtStoryStartPlace", "EnterVault", "StandsInVault", "CheckPod", "InVault", "ResetInventory", "FillO2",
            "FadeIn", "DisableHandScanner", "NoteLooksStage20", "IsPreworldLooksHandled",
            "ClearVaultSaveLock", "ApplyStage", "AdvanceTo", "RunModeChoiceChain", "MenuEvent", "TimerEvent",
        )
        vars_csv = (
            "faded, warfareFadeTicks, entered, startRoomMoves, startRoomEntered, startRoomUiPrepared, "
            "loadingMenuOpen, loadingMenuClosedSeen, loadingHookRegistered, startUiReady, h00SkipLoading, "
            "modeChoiceRan, modeBoxWaiting, modeBoxWaitSeconds, preworldLooksDone, preworldLooksHow, preworldLooksBy, "
            "setupWaitingCreator, warfareWaitingCreator, applied, pendingStage, pendingStageBy, "
            "looksSetStage20, exitUsedFallback, vaultMoves, centered, centerTries, ticks, startedAt, scannerLayer, "
            "podChecked, rideActive, surfaceMovedAt, returnSurfacePending, asked, vaultSavingRelocked"
        )
        compiled = compile(translated_functions(wrapped, funcs, vars_csv), PSC, "exec")

        for scenario in ("loading_menu_close_delay", "already_loaded_delay", "timeout_delay"):
            with self.subTest(scenario=scenario):
                logs, timers, waits, start_msg_calls = [], [], [], []
                cur_stage = [0]
                start_room_marker = SimpleNamespace(GetParentCell=lambda: "StartRoomCell")
                vault_anchor = SimpleNamespace(GetParentCell=lambda: "VaultCell")
                player = SimpleNamespace(
                    pos=(0.0, 0.0, 0.0),
                    cell="StartRoomCell",
                    GetPositionX=lambda: player.pos[0],
                    GetPositionY=lambda: player.pos[1],
                    GetPositionZ=lambda: player.pos[2],
                    SetPosition=lambda x, y, z: setattr(player, "pos", (x, y, z)),
                    SetAngle=lambda *a: None,
                    MoveTo=lambda ref, dx, dy, dz, *rest: (
                        setattr(player, "cell", ref.GetParentCell()),
                        setattr(player, "pos", (60.0 + dx, 25.0 + dy, 1.0 + dz) if ref is vault_anchor else (0.0 + dx, 0.0 + dy, 0.0 + dz)),
                    ),
                    GetParentCell=lambda: player.cell,
                    GetWorldSpace=lambda: None,
                    GetAngleZ=lambda: 90.0,
                    IsInInterior=lambda: True,
                    Is3DLoaded=lambda: True,
                    GetItemCount=lambda *a: 0,
                    RemoveAllItems=lambda *a: None,
                    AddItem=lambda *a: None,
                    EquipItem=lambda *a: None,
                    IsEquipped=lambda *a: True,
                    GetValue=lambda *a: 100.0,
                    ModValue=lambda *a: None,
                )

                def on_wait(secs):
                    waits.append(secs)
                    if scenario == "loading_menu_close_delay" and len(waits) == 1:
                        # LoadingMenu closes AFTER modeChoiceRan is already true!
                        self.assertTrue(ns["modeChoiceRan"])
                        self.assertFalse(ns["startUiReady"])
                        ns["MenuEvent"]("LoadingMenu", False)

                ns = dict(
                    FadeHold=True, StartChoiceBackdrop=1, StartLoadTimeout=15.0, LooksWait=120.0, RaceMenuMode=2,
                    ClearInventory=False, VaultSuitId=0, AnchorTemporary=False, O2Capacity=None, O2CapacityAmount=0.0,
                    faded=False, warfareFadeTicks=0, entered=False, startRoomMoves=1, startRoomEntered=True, startRoomUiPrepared=True,
                    loadingMenuOpen=(scenario != "already_loaded_delay"),
                    loadingMenuClosedSeen=False,
                    loadingHookRegistered=(scenario != "already_loaded_delay"),
                    startUiReady=False, h00SkipLoading=False,
                    modeChoiceRan=False, modeBoxWaiting=False, modeBoxWaitSeconds=0,
                    preworldLooksDone=False, preworldLooksHow="", preworldLooksBy="Trigger",
                    setupWaitingCreator=False, warfareWaitingCreator=False,
                    applied=0, pendingStage=-1, pendingStageBy="other", looksSetStage20=False,
                    exitUsedFallback=False, vaultMoves=0, centered=0, centerTries=0, ticks=0, startedAt=0.0,
                    podChecked=False, rideActive=False, surfaceMovedAt=0.0, returnSurfacePending=False,
                    VaultAnchorId=0x805, VaultPlugin="FO4Port.esm", VaultCell="FO4Port_Vault111Cryo", CenterTicks=30,
                    AnchorX=60.0, AnchorY=25.0, AnchorZ=1.0,
                    PodX=10.0, PodY=20.0, PodZ=1.0, PodLift=0.3, PodHeading=90.0, PodRadius=1.0, PodDrop=0.5,
                    CogDoorId=0, PlatformX=0.0, PlatformY=0.0, PlatformZ=0.0, PlatformRadius=2.0,
                    asked=False,
                    StartRoomMarkerRef=start_room_marker,
                    StartCardOpenGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    StartChoiceDoneGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    StartNeutralSpotGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                    GameModeGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    StoryLineGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    StartPlaceRowGlobal=SimpleNamespace(GetValue=lambda: 0.0, SetValue=lambda v: None),
                    SurvivalStartGlobal=SimpleNamespace(SetValue=lambda v: None),
                    SurvivalLockedGlobal=SimpleNamespace(SetValue=lambda v: None),
                    StartDifficultyGlobal=SimpleNamespace(SetValue=lambda v: None),
                    WarfareFactionGlobal=SimpleNamespace(SetValue=lambda v: None),
                    WarfareStartIndexGlobal=SimpleNamespace(SetValue=lambda v: None),
                    H00SkipLoadingHookGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                    TestModeGlobal=SimpleNamespace(GetValue=lambda: 0.0),
                    ModePickMsg=SimpleNamespace(Show=lambda: 0),
                    StoryLineMsg=SimpleNamespace(Show=lambda: 0),
                    SurvivalPickMsg=SimpleNamespace(Show=lambda: 0),
                    # Button 0 is now Quick start!
                    StartPickMsg=SimpleNamespace(Show=lambda: (start_msg_calls.append("preworld"), 0)[1]),
                    StoryChoiceIds=["fo4_commonwealth"],
                    StartPlaceIds=["fo4_vault111"],
                    StartPlaceModes=[1],
                    StartPlaceStories=["fo4_commonwealth"],
                    StartPlacePlugins=["FO4Port.esm"],
                    StartPlaceMarkerIds=[0x805],
                    StartPlaceWarfareRows=[-1],
                    Game=SimpleNamespace(
                        GetPlayer=lambda: player,
                        ShowFirstPersonGeometry=lambda *a: None,
                        FadeOutGame=lambda *a: None,
                        SetInChargen=lambda *a: None,
                        SetCharGenHUDMode=lambda *a: None,
                        GetFormFromFile=lambda fid, plg: vault_anchor if (fid, plg) == (0x805, "FO4Port.esm") else None,
                    ),
                    Utility=SimpleNamespace(Wait=on_wait, GetCurrentRealTime=lambda: 10.0),
                    Debug=SimpleNamespace(Notification=lambda *a: None),
                    InputEnableLayer=SimpleNamespace(Create=lambda: None),
                    scannerLayer=None,
                    RegisterForMenuOpenCloseEvent=lambda m: None,
                    UnregisterForMenuOpenCloseEvent=lambda m: None,
                    StartTimer=lambda s, tid: timers.append((s, tid)),
                    SetStage=lambda n: cur_stage.__setitem__(0, n),
                    GetStage=lambda: cur_stage[0],
                    SetObjectiveDisplayed=lambda *a: None,
                    SetObjectiveCompleted=lambda *a: None,
                    SetActive=lambda *a: None,
                    CompleteQuest=lambda: None,
                    StartLandingQuests=lambda: None,
                    EnsureLoadHookRegistered=lambda p: None,
                    TriggerVaultPodRecoveryAutosave=lambda *a: None,
                    CancelTimer=lambda *a: None,
                    vaultSavingRelocked=False,
                    EnsureVaultInteractivesRegistered=lambda: None,
                    Near=lambda *a: False,
                    HoldOffPass=lambda p: None,
                    Trace=lambda m: logs.append(m),
                )
                exec(compiled, ns)

                # Drive stage 0 via OnTimer(1) just like in-game!
                ns["TimerEvent"](1)
                self.assertEqual(cur_stage[0], 20)
                self.assertEqual(start_msg_calls, ["preworld"])
                self.assertTrue(ns["IsPreworldLooksHandled"]())
                # T4 critical proof: Timer 1 MUST be re-armed (1.0, 1) after Story mode completes stage 0 -> 20!
                self.assertIn((1.0, 1), timers)
                self.assertIn("looks done: quick start", logs)
                self.assertIn("stage 20 by=Trigger", logs)
                # Second Timer 1 tick at stage 20 must run CheckPod(player) inside InVault so pod settle ok= is logged!
                self.assertFalse(ns["podChecked"])
                ns["TimerEvent"](1)
                self.assertTrue(ns["podChecked"])
                self.assertTrue(any(l.startswith("pod settle ok=True ") for l in logs), logs)
                self.assertTrue(
                    any(l.startswith(f"start ui ready released_by={scenario} waited_s=") for l in logs),
                    logs,
                )
                if scenario == "loading_menu_close_delay":
                    self.assertIn("mode loading menu closed", logs)
                    self.assertEqual(waits[-1], 0.75)
                elif scenario == "already_loaded_delay":
                    self.assertEqual(waits, [0.75])
                else:
                    self.assertIn("mode fade lifted by=timeout s=15", logs)
                    self.assertEqual(waits[-1], 0.75)

        # Verify FO4SF_NewGameLooks suppresses StartMessage.Show() when IsPreworldLooksHandled() is True
        looks_ev = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", looks_psc, re.S)
        looks_wrap = looks_psc + f"\nFunction LooksTimer({looks_ev[1]})\n{looks_ev[2]}EndFunction\n"
        looks_compiled = compile(translated_functions(looks_wrap, ("LooksTimer",), "shown, waiting"), LOOKS, "exec")
        shown_in_vault = []
        fake_quest = SimpleNamespace(IsPreworldLooksHandled=lambda: True)
        lns = dict(
            self=fake_quest,
            shown=False, waiting=False, MenuDelay=2.0, MenuName="ChargenMenu", RaceMenuMode=2,
            GetStage=lambda: 10,
            StartMessage=SimpleNamespace(Show=lambda: (shown_in_vault.append(1), 0)[1]),
            Utility=SimpleNamespace(Wait=lambda s: None),
            StartTimer=lambda *a: None,
            Trace=lambda m: None,
        )
        exec(looks_compiled, lns)
        lns["LooksTimer"](2)
        self.assertEqual(shown_in_vault, [])

    def test_r6_t5_t8_and_grok_warfare_fade_hud_gmst_and_setup_row_resolution(self):
        """R6 T5 + T8 + Grok #5984954658:
        1) T5: RunWarfareBranch waits for Is3DLoaded + 0.5s settle, calls ForceFadeIn('warfare') even when
           faded was already True, and arms Timer 4 (1.5s then 2.5s = 2 ticks) re-asserting fade/chargen/HUD.
        2) T8: PrepareStartRoomUi uses SetCharGenHUDMode(2), Begin() re-asserts ShowFirstPersonGeometry(false),
           and Program.cs overrides iXPRewardDiscoverSecretArea to 0.
        3) Grok #5984954658: usedSetupMenu + modeVal==2 resolves rowIdx from StartPlaceWarfareRows[placeRow]
           and writes it back to WarfareStartIndexGlobal; make_newgame.py writes int(bool(o_show_unavailable)).
        """
        from types import SimpleNamespace
        from tests.test_exit_arrival import translated_functions

        psc = read(PSC)
        cs = read(CS)
        mk = read(os.path.join(os.path.dirname(PSC), "make_newgame.py")) if os.path.isfile(os.path.join(os.path.dirname(PSC), "make_newgame.py")) else read(ng.__file__)
        self.assertIn('DiscoverSecretAreaXpGmstEdid = "iXPRewardDiscoverSecretArea"', cs)
        self.assertIn('"show_unavailable_starts": int(bool(o_show_unavailable))', mk)

        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        wrapped = psc + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
        funcs = (
            "BackdropName", "UsePreworldRoom", "StandsInStartRoom", "EnterStartRoom", "PrepareStartRoomUi",
            "SetStartCardBackdrop", "WaitForStartUiReady", "HoldNeutralSpotForModeChoice",
            "RegisterStartLoadingHook", "UnregisterStartLoadingHook", "ReadH00Glob",
            "FindStoryStartPlaceRow", "FindWarfareStartPlaceRow", "RunPreworldLooksChoice",
            "ForceFadeIn", "RunWarfareBranch", "RunSharedMapSetup", "FillO2", "FadeIn", "DisableHandScanner",
            "ClearVaultSaveLock", "ApplyStage", "AdvanceTo", "RunModeChoiceChain", "TimerEvent",
        )
        vars_csv = (
            "faded, warfareFadeTicks, entered, startRoomMoves, startRoomEntered, startRoomUiPrepared, "
            "loadingMenuOpen, loadingMenuClosedSeen, loadingHookRegistered, startUiReady, h00SkipLoading, h00SkipMap, "
            "modeChoiceRan, modeBoxWaiting, modeBoxWaitSeconds, preworldLooksDone, preworldLooksHow, preworldLooksBy, "
            "setupWaitingCreator, warfareWaitingCreator, mapSetupDone, applied, pendingStage, pendingStageBy, "
            "looksSetStage20, exitUsedFallback, vaultMoves, centered, centerTries, ticks, startedAt, scannerLayer, "
            "podChecked, rideActive, surfaceMovedAt, returnSurfacePending, asked, vaultSavingRelocked"
        )
        compiled = compile(translated_functions(wrapped, funcs, vars_csv), PSC, "exec")

        logs, fades, chargens, huds, timers, waits = [], [], [], [], [], []
        cur_stage = [0]
        # Start with faded=True to prove ForceFadeIn STILL forces fade-in!
        # Also simulate WarfareStartIndexGlobal stale (-1.0) while StartPlaceRowGlobal selects placeRow=2 -> wfRow=1!
        store = {
            "StartCardOpen": 0.0,
            "GameMode": 2.0,
            "StoryLine": -1.0,
            "SurvivalStart": 0.0,
            "SurvivalLocked": 0.0,
            "StartDifficulty": 1.0,
            "WarfareFaction": 1.0,
            "WarfareStartIndex": -1.0,
            "StartChoiceDone": 0.0,
            "StartPlaceRow": 2.0,
        }

        def make_glob(key):
            def _set(v):
                store[key] = float(v)
                if key == "StartCardOpen" and float(v) >= 1.5:
                    store["StartCardOpen"] = 3.0
                    store["StartChoiceDone"] = 1.0
            return SimpleNamespace(GetValue=lambda: store[key], SetValue=_set)

        start_room_marker = SimpleNamespace(GetParentCell=lambda: "StartRoomCell")
        bunker_cell = SimpleNamespace(GetFormID=lambda: 0x03002000)
        bunker_marker = SimpleNamespace(
            GetFormID=lambda: 0x030A775C,
            GetParentCell=lambda: bunker_cell,
            GetWorldSpace=lambda: "CommonwealthWorld",
            Enable=lambda *a: None,
            MoveTo=lambda *a: None,
            SetPosition=lambda *a: None,
        )
        load_checks = [0]
        def is_3d_loaded():
            load_checks[0] += 1
            # Return False on first post-SetPosition check to exercise the StartLoadTimeout wait loop
            return load_checks[0] != 2

        player = SimpleNamespace(
            pos=(0.0, 0.0, 0.0),
            cell="StartRoomCell",
            interior=True,
            GetPositionX=lambda: player.pos[0],
            GetPositionY=lambda: player.pos[1],
            GetPositionZ=lambda: player.pos[2],
            SetPosition=lambda x, y, z: setattr(player, "pos", (x, y, z)),
            SetAngle=lambda *a: None,
            MoveTo=lambda ref, *rest: (
                setattr(player, "cell", ref.GetParentCell()),
                setattr(player, "interior", ref is start_room_marker),
            ),
            GetParentCell=lambda: player.cell,
            GetWorldSpace=lambda: None if player.interior else "CommonwealthWorld",
            IsInInterior=lambda: player.interior,
            Is3DLoaded=is_3d_loaded,
            RemoveAllItems=lambda *a: None,
            AddItem=lambda *a: None,
            EquipItem=lambda *a: None,
            GetValue=lambda av: 100.0,
            ModValue=lambda av, d: None,
            AddToFaction=lambda f: None,
        )
        ns = dict(
            FadeHold=True, StartChoiceBackdrop=3, StartLoadTimeout=15.0, LooksWait=0.0, RaceMenuMode=2,
            ClearInventory=True, AnchorTemporary=False, O2Capacity=None, O2CapacityAmount=0.0,
            SurfaceWait=1.0, SurfaceTries=3, FallDrop=3.0, MergeOffsetX=-1200.0, MergeOffsetY=-2700.0,
            ArrivalX=0.0, ArrivalY=0.0, ArrivalZ=0.0,
            ExitAnchorId=0x0A7759, CorePlugin="FO4TerrainCore.esm",
            VaultAnchorId=0x805, VaultPlugin="FO4Port.esm",
            faded=True, warfareFadeTicks=0, entered=False, startRoomMoves=1, startRoomEntered=True, startRoomUiPrepared=True,
            loadingMenuOpen=False, loadingMenuClosedSeen=True, loadingHookRegistered=False, startUiReady=False,
            h00SkipLoading=False, h00SkipMap=False,
            modeChoiceRan=False, modeBoxWaiting=False, modeBoxWaitSeconds=0,
            preworldLooksDone=False, preworldLooksHow="", preworldLooksBy="Trigger",
            setupWaitingCreator=False, warfareWaitingCreator=False, mapSetupDone=False,
            applied=0, pendingStage=-1, pendingStageBy="other", looksSetStage20=False,
            exitUsedFallback=False, vaultMoves=0, centered=0, centerTries=0, ticks=0, startedAt=0.0,
            podChecked=False, rideActive=False, surfaceMovedAt=0.0, returnSurfacePending=False,
            StartRoomMarkerRef=start_room_marker,
            PipboyWristArmor=SimpleNamespace(),
            PipboyAcquiredGlobal=SimpleNamespace(SetValue=lambda v: None),
            StartCardOpenGlobal=make_glob("StartCardOpen"),
            StartChoiceDoneGlobal=make_glob("StartChoiceDone"),
            StartNeutralSpotGlobal=SimpleNamespace(GetValue=lambda: 0.0),
            GameModeGlobal=make_glob("GameMode"),
            StoryLineGlobal=make_glob("StoryLine"),
            StartPlaceRowGlobal=make_glob("StartPlaceRow"),
            SurvivalStartGlobal=make_glob("SurvivalStart"),
            SurvivalLockedGlobal=make_glob("SurvivalLocked"),
            StartDifficultyGlobal=make_glob("StartDifficulty"),
            WarfareFactionGlobal=make_glob("WarfareFaction"),
            WarfareStartIndexGlobal=make_glob("WarfareStartIndex"),
            H00SkipLoadingHookGlobal=SimpleNamespace(GetValue=lambda: 0.0),
            TestModeGlobal=SimpleNamespace(GetValue=lambda: 0.0),
            ModePickMsg=None, StoryLineMsg=None, SurvivalPickMsg=None, StartPickMsg=None,
            StoryChoiceIds=["fo4_commonwealth"],
            StartPlaceIds=["fo4_vault111", "minutemen_sanctuary", "bos_cambridge"],
            StartPlaceModes=[1, 2, 2],
            StartPlaceStories=["fo4_commonwealth", "none", "none"],
            StartPlacePlugins=["FO4Port.esm", "FO4TerrainCore.esm", "FO4TerrainCore.esm"],
            StartPlaceMarkerIds=[0x805, 0x0A775A, 0x0A775C],
            StartPlaceWarfareRows=[-1, 0, 1],
            WarfareKeys=["minutemen_sanctuary", "bos_cambridge"],
            WarfareFactionSlots=[0, 1],
            WarfareDistinctFactionSlots=[0, 1],
            WarfareMarkerIds=[0x0A775A, 0x0A775C],
            WarfareMarkerX=[100.0, 300.0],
            WarfareMarkerY=[200.0, 400.0],
            WarfareMarkerZ=[95.0, 105.0],
            WarfareHeadings=[180.0, 90.0],
            WarfareMinDiffs=[0, 0],
            WarfareMaxDiffs=[3, 3],
            WarfareBgIndices=[0, 1],
            WarfareFames=[45.0, 55.0],
            WarfareInfamies=[0.0, 0.0],
            WarfareKarmas=[150.0, 100.0],
            WarfareSquadCaps=[4, 4],
            WarfareGearRowIndices=[0, 1],
            WarfareGearPlugins=["Starfield.esm", "Starfield.esm"],
            WarfareGearIds=[0x100, 0x101],
            WarfareGearCounts=[1, 1],
            WarfareGearEquips=[True, True],
            CoreMarkerIds=[0x0A775A, 0x0A775C],
            MapMarkerQuestIds=[],
            Game=SimpleNamespace(
                GetPlayer=lambda: player,
                ShowFirstPersonGeometry=lambda *a: None,
                FadeOutGame=lambda *a: fades.append(a),
                SetInChargen=lambda *a: chargens.append(a),
                SetCharGenHUDMode=lambda m: huds.append(m),
                GetFormFromFile=lambda fid, plg: (
                    bunker_marker if (fid, plg) == (0x0A775C, "FO4TerrainCore.esm")
                    else SimpleNamespace() if plg == "Starfield.esm"
                    else None
                ),
            ),
            Utility=SimpleNamespace(Wait=lambda s: waits.append(s), GetCurrentRealTime=lambda: 40.0),
            Debug=SimpleNamespace(Notification=lambda *a: None),
            InputEnableLayer=SimpleNamespace(Create=lambda: None),
            scannerLayer=None,
            RegisterForMenuOpenCloseEvent=lambda m: None,
            UnregisterForMenuOpenCloseEvent=lambda m: None,
            StartTimer=lambda s, tid: timers.append((s, tid)),
            SetStage=lambda n: cur_stage.__setitem__(0, n),
            GetStage=lambda: cur_stage[0],
            SetObjectiveDisplayed=lambda *a: None,
            SetObjectiveCompleted=lambda *a: None,
            SetActive=lambda *a: None,
            CompleteQuest=lambda: None,
            StartLandingQuests=lambda: None,
            EnsureLoadHookRegistered=lambda p: None,
            TriggerVaultPodRecoveryAutosave=lambda *a: None,
            CancelTimer=lambda *a: None,
            vaultSavingRelocked=False,
            Trace=lambda m: logs.append(m),
        )
        exec(compiled, ns)

        chosen = ns["RunModeChoiceChain"](player)
        self.assertEqual(chosen, 2)
        self.assertEqual(cur_stage[0], 210)
        # Grok #5984954658: resolved rowIdx=1 via StartPlaceWarfareRows[2] and wrote back to WarfareStartIndexGlobal!
        self.assertEqual(store["WarfareStartIndex"], 1.0)
        self.assertIn("warfare pick faction=1 start=bos_cambridge difficulty=1", logs)
        # T5: waited 0.5s post-SetPosition, ran ForceFadeIn even with faded=True, and armed Timer 4 at 1.5s
        self.assertIn(0.5, waits)
        self.assertTrue(any(l.startswith("fade in by=warfare ") for l in logs), logs)
        self.assertEqual(timers, [(1.5, 4)])
        # Fire Timer 4 tick 1 (+1.5s) -> re-arms at +2.5s; fire tick 2 (+2.5s) -> stops!
        fades_before = len(fades)
        ns["TimerEvent"](4)
        self.assertEqual(timers, [(1.5, 4), (2.5, 4)])
        self.assertEqual(fades[-1], (False, True, 0.0, 0.1, False))
        self.assertEqual(chargens[-1], (False, False, False))
        self.assertEqual(huds[-1], 0)
        ns["TimerEvent"](4)
        self.assertEqual(timers, [(1.5, 4), (2.5, 4)])  # No 3rd timer!
        self.assertEqual(len(fades), fades_before + 2)
        self.assertIn("warfare fade reassert tick=1", logs)
        self.assertIn("warfare fade reassert tick=2", logs)

    def test_r8_v1_story_landing_releases_fade_after_streaming_and_reasserts_bounded(self):
        """R8 V1 translated execution + negative regression:
        1) Negative regression: without ReleaseStoryLandingFade() on stage 200 (after Vault 111 FadeIn('start')
           already set faded=True), Story exterior landing never logs fade in by=story_landing or arms Timer 5.
        2) With V1: Story landing waits until exterior + Is3DLoaded() + 0.5s settle, forces fade-in even with
           faded=True (logging 'fade in by=story_landing ...; saving and HUD on'), arms Timer 5 for bounded
           ticks 1..3 (1.5s, 2.5s, 2.5s) re-asserting geometry/fade/chargen/HUD, refuses to fire indoors,
           leaves Warfare Timer 4 intact, and populates make_newgame.summarize() keys cleanly.
        """
        from types import SimpleNamespace
        from tests.test_exit_arrival import translated_functions

        psc = read(PSC)
        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        wrapped = psc + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
        funcs = (
            "FadeIn", "ForceFadeIn", "ReleaseStoryLandingFade", "DisableHandScanner",
            "StandsInVault", "FinishSurface", "CheckLanding", "RequestArrivalDiscovery",
            "ClearVaultSaveLock", "ApplyStage", "AdvanceTo", "TimerEvent",
        )
        vars_csv = (
            "faded, warfareFadeTicks, storyFadeTicks, loadingHookRegistered, vaultMoves, "
            "applied, pendingStage, pendingStageBy, exitUsedFallback, scannerLayer, "
            "arrivalWorld, surfaceSets, surfaceMovedAt, surfaceMoves, arrivedAt, fallbackPending, "
            "discoveryMarkerMoved, discoveryAttachPending, landingChecks, asked, "
            "h00SkipDiscovery, h00SkipSetPos, vaultSavingRelocked"
        )

        def run_story_landing(source_text, *, stay_interior=False, delay_3d_once=False):
            compiled = compile(translated_functions(source_text, funcs, vars_csv), PSC, "exec")
            logs, fades, chargens, huds, geom, timers, waits = [], [], [], [], [], [], []
            cur_stage = [30]
            now = [100.0]
            world = SimpleNamespace(__repr__=lambda self: "[WorldSpace <Commonwealth>]")
            vault_cell = SimpleNamespace(GetFormID=lambda: 0x02000100, __repr__=lambda self: "[Cell <FO4Port_Vault111Cryo>]")
            core_cell = SimpleNamespace(GetFormID=lambda: 0x03000CF0, __repr__=lambda self: "[Cell <FO4Core_Vault111Ext>]")
            vault_anchor = SimpleNamespace(GetParentCell=lambda: vault_cell)
            exit_anchor = SimpleNamespace(
                GetFormID=lambda: 0x030A775B,
                GetWorldSpace=lambda: world,
                GetPositionX=lambda: -1210.0,
                GetPositionY=lambda: -2720.0,
                GetPositionZ=lambda: 127.0,
                Enable=lambda *a: None,
                MoveTo=lambda *a: None,
                SetPosition=lambda *a: None,
                SetMarkerDiscovered=lambda: None,
            )
            loaded_state = [True]
            delayed_done = [False]

            def is_3d_loaded():
                if delay_3d_once and cur_stage[0] == 200 and not delayed_done[0]:
                    delayed_done[0] = True
                    return False
                return loaded_state[0]

            player = SimpleNamespace(
                pos=(-1200.0, -2700.0, 127.45),
                cell=vault_cell if stay_interior else core_cell,
                interior=stay_interior,
                GetPositionX=lambda: player.pos[0],
                GetPositionY=lambda: player.pos[1],
                GetPositionZ=lambda: player.pos[2],
                SetPosition=lambda x, y, z: setattr(player, "pos", (x, y, z)),
                SetAngle=lambda *a: None,
                GetParentCell=lambda: player.cell,
                GetWorldSpace=lambda: None if player.interior else world,
                IsInInterior=lambda: player.interior,
                Is3DLoaded=is_3d_loaded,
            )

            ns = dict(
                faded=False, warfareFadeTicks=0, storyFadeTicks=0, loadingHookRegistered=False,
                vaultMoves=1, applied=30, pendingStage=-1, pendingStageBy="other",
                exitUsedFallback=False, scannerLayer=None,
                arrivalWorld=None, surfaceSets=0, surfaceMovedAt=99.0, surfaceMoves=1,
                arrivedAt=0.0, fallbackPending=False, discoveryMarkerMoved=False,
                discoveryAttachPending=False, landingChecks=0, asked=False,
                h00SkipDiscovery=False, h00SkipSetPos=False,
                VaultAnchorId=0x805, VaultPlugin="FO4Port.esm", PodHeading=0.0,
                CorePlugin="FO4TerrainCore.esm", ExitAnchorId=0x0A775B, ArrivalDiscoveryId=0x0A775B,
                ArrivalX=0.0, ArrivalY=0.0, ArrivalZ=127.45, ArrivalHeading=180.0,
                FallbackX=-10.0, FallbackY=-20.0, FallbackZ=127.0,
                MergeOffsetX=-1200.0, MergeOffsetY=-2700.0,
                FallDrop=3.0, SurfaceWait=10.0, SurfaceTries=3, StartLoadTimeout=15.0, LiftId=0,
                Game=SimpleNamespace(
                    GetPlayer=lambda: player,
                    ShowFirstPersonGeometry=lambda v: geom.append(v),
                    FadeOutGame=lambda *a: fades.append(a),
                    SetInChargen=lambda *a: chargens.append(a),
                    SetCharGenHUDMode=lambda m: huds.append(m),
                    IsFastTravelEnabled=lambda: True,
                    GetFormFromFile=lambda fid, plg: (
                        vault_anchor if (fid, plg) == (0x805, "FO4Port.esm")
                        else exit_anchor if (fid, plg) == (0x0A775B, "FO4TerrainCore.esm")
                        else None
                    ),
                ),
                Utility=SimpleNamespace(Wait=lambda s: waits.append(s), GetCurrentRealTime=lambda: now[0]),
                InputEnableLayer=SimpleNamespace(Create=lambda: None),
                UnregisterStartLoadingHook=lambda: None,
                StartTimer=lambda s, tid: timers.append((s, tid)),
                SetStage=lambda n: cur_stage.__setitem__(0, n),
                GetStage=lambda: cur_stage[0],
                SetObjectiveDisplayed=lambda *a: None,
                SetObjectiveCompleted=lambda *a: None,
                SetActive=lambda *a: None,
                CompleteQuest=lambda: None,
                StartLandingQuests=lambda: logs.append("landing quests started min00=True keeper=True codsworth01=True"),
                TriggerVaultPodRecoveryAutosave=lambda *a: None,
                CancelTimer=lambda *a: None,
                vaultSavingRelocked=False,
                FailExit=lambda r: logs.append(f"fail {r}"),
                Trace=lambda m: logs.append(m),
            )
            exec(compiled, ns)

            # Vault 111 start already called FadeIn("start"), setting faded=True!
            ns["FadeIn"]("start")
            self.assertTrue(ns["faded"])
            fades_after_start = len(fades)

            if stay_interior:
                ns["AdvanceTo"](200)
            else:
                ns["FinishSurface"](player)
                self.assertEqual(cur_stage[0], 40)
                now[0] += 3.5
                ns["CheckLanding"](player)
                self.assertEqual(cur_stage[0], 200)

            return ns, player, logs, fades[fades_after_start:], chargens, huds, geom, timers, waits

        # 1) Negative regression: removing ReleaseStoryLandingFade() leaves Story landing with NO post-surface fade-in!
        without_v1 = wrapped.replace("        ReleaseStoryLandingFade()\n", "")
        self.assertNotEqual(without_v1, wrapped)
        _, _, logs_old, fades_old, _, _, _, timers_old, _ = run_story_landing(without_v1)
        self.assertFalse(any(l.startswith("fade in by=story_landing ") for l in logs_old), logs_old)
        self.assertEqual(fades_old, [])
        self.assertEqual(timers_old, [])

        # 2) Positive V1: waits for Is3DLoaded() + 0.5s settle, forces fade-in even with faded=True, arms Timer 5 ticks 1..3
        ns, player, logs, post_fades, chargens, huds, geom, timers, waits = run_story_landing(
            wrapped, delay_3d_once=True
        )
        self.assertEqual(waits, [0.25, 0.5])
        self.assertTrue(
            any(l.startswith("fade in by=story_landing loaded=True ") and l.endswith("; saving and HUD on") for l in logs),
            logs,
        )
        self.assertEqual(post_fades, [(False, True, 0.0, 0.1, False)])
        self.assertEqual(timers, [(1.5, 5)])

        # Drive Timer 5 ticks 1, 2, 3 -> stops after tick 3 (no 4th timer!)
        ns["TimerEvent"](5)
        self.assertEqual(timers, [(1.5, 5), (2.5, 5)])
        ns["TimerEvent"](5)
        self.assertEqual(timers, [(1.5, 5), (2.5, 5), (2.5, 5)])
        ns["TimerEvent"](5)
        self.assertEqual(timers, [(1.5, 5), (2.5, 5), (2.5, 5)])  # Strictly bounded at 3 ticks!
        self.assertIn("story fade reassert tick=1", logs)
        self.assertIn("story fade reassert tick=2", logs)
        self.assertIn("story fade reassert tick=3", logs)
        self.assertEqual(geom[-3:], [True, True, True])
        self.assertEqual(chargens[-3:], [(False, False, False)] * 3)
        self.assertEqual(huds[-3:], [0, 0, 0])

        # Warfare Timer 4 stays completely intact and independent (ticks 1..2 only)
        ns["warfareFadeTicks"] = 0
        ns["TimerEvent"](4)
        ns["TimerEvent"](4)
        self.assertIn("warfare fade reassert tick=1", logs)
        self.assertIn("warfare fade reassert tick=2", logs)
        self.assertEqual(timers[-1], (2.5, 4))

        # 3) Interior guard: stage 200 while still indoors never forces an exterior story_landing fade
        _, _, logs_in, fades_in, _, _, _, timers_in, _ = run_story_landing(wrapped, stay_interior=True)
        self.assertFalse(any(l.startswith("fade in by=story_landing ") for l in logs_in), logs_in)
        self.assertEqual(fades_in, [])
        self.assertEqual(timers_in, [])

        # 4) Interior abort mid-reassert: if player enters an interior before tick 2, Timer 5 stops immediately
        ns2, player2, logs2, _, _, _, _, timers2, _ = run_story_landing(wrapped)
        self.assertEqual(timers2, [(1.5, 5)])
        ns2["TimerEvent"](5)
        self.assertEqual(timers2, [(1.5, 5), (2.5, 5)])
        player2.interior = True
        ns2["TimerEvent"](5)
        self.assertEqual(timers2, [(1.5, 5), (2.5, 5)])  # Did NOT re-arm once indoors!
        self.assertNotIn("story fade reassert tick=2", logs2)

        # 5) make_newgame.summarize() preserves initial fade and captures story_landing_fade + reassert ticks
        sample_log = [
            "[x] FO4SF_NEWGAME rt=1.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n",
            "[x] FO4SF_NEWGAME rt=2.0 fade in by=start loaded=true cell=[Cell <FO4Port_Vault111Cryo>]; saving and HUD on\n",
            "[x] FO4SF_NEWGAME rt=50.0 stage 200 by=Trigger\n",
            "[x] FO4SF_NEWGAME rt=50.5 fade in by=story_landing loaded=true cell=[Cell <FO4Core_Vault111Ext>]; saving and HUD on\n",
            "[x] FO4SF_NEWGAME rt=52.0 story fade reassert tick=1\n",
            "[x] FO4SF_NEWGAME rt=54.5 story fade reassert tick=2\n",
            "[x] FO4SF_NEWGAME rt=57.0 story fade reassert tick=3\n",
        ]
        summary = ng.summarize(sample_log)
        self.assertEqual(summary["fade"], "by=start loaded=true cell=[Cell <FO4Port_Vault111Cryo>]; saving and HUD on")
        self.assertEqual(
            summary["story_landing_fade"],
            "by=story_landing loaded=true cell=[Cell <FO4Core_Vault111Ext>]; saving and HUD on",
        )
        self.assertEqual(summary["story_fade_reassert_ticks"], [1, 2, 3])
        self.assertEqual(summary["warfare_fade_reassert_ticks"], [])


class Round12Task1bAnd1iTests(unittest.TestCase):
    """Task 1b (Vault 111 death recovery before stage 200) and Task 1i (host world from persistent core refs)."""

    def test_task1b_pod_autosave_locks_vault_saving_and_ondying_reload_fallback(self):
        from types import SimpleNamespace
        from tests.test_exit_arrival import translated_functions

        psc = read(PSC)
        looks_psc = read(LOOKS)
        ev_timer = re.search(r"Event OnTimer\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        ev_dying = re.search(r"Event Actor\.OnDying\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        ev_stage = re.search(r"Event OnStageSet\((.*?)\)\n(.*?)EndEvent", psc, re.S)
        self.assertIsNotNone(ev_timer)
        self.assertIsNotNone(ev_dying)
        self.assertIsNotNone(ev_stage)
        wrapped = (
            psc
            + f"\nFunction TimerEvent({ev_timer[1]})\n{ev_timer[2]}EndFunction\n"
            + f"\nFunction DyingEvent({ev_dying[1]})\n{ev_dying[2]}EndFunction\n"
            + f"\nFunction StageSetEvent({ev_stage[1]})\n{ev_stage[2]}EndFunction\n"
        )
        funcs = (
            "TriggerVaultPodRecoveryAutosave", "EnsureLoadHookRegistered",
            "ClearVaultSaveLock", "RelockVaultSaving",
            "NoteLooksStage20", "ApplyStage", "Actor.OnPlayerLoadGame",
            "TimerEvent", "DyingEvent", "StageSetEvent", "ResolveHostWorld",
        )
        vars_csv = (
            "applied, pendingStage, pendingStageBy, looksSetStage20, exitUsedFallback, "
            "vaultPodAutosaved, vaultSavingRelocked, vaultRecoveryTriggered, vaultPodAutosaveSkips, "
            "loadHookRegistered, dyingHookRegistered, "
            "h00SuspectsRead, rideActive, rideDone, rideTransferred, ridingLift, ridingCell, "
            "surfaceMovedAt, surfaceMoves, surfaceSets, asked, "
            "returnSurfacePending, returnVaultAsked, returnSurfaceWaitTicks, returnSurfaceTries"
        )
        compiled = compile(translated_functions(wrapped, funcs, vars_csv), PSC, "exec")
        looks_compiled = compile(translated_functions(looks_psc, ("Done",), ""), LOOKS, "exec")

        def run_case(*, initial_stage=10, mode=1.0, in_vault=True, pre_autosaved=False, loaded=True, dead=False, fire_stage_set=True):
            logs, chargens, autosaves, timers, cancels, reg_events = [], [], [], [], [], []
            moves, sets, angles, restores = [], [], [], []
            cur_stage = [initial_stage]
            allow_anchor = [True]
            health_av = object()
            bench_ws = object()
            anchor_ws = object()
            bench_ref = SimpleNamespace(GetWorldSpace=lambda: bench_ws)
            exit_ref = SimpleNamespace(GetWorldSpace=lambda: anchor_ws)
            vault_anchor = SimpleNamespace(GetParentCell=lambda: "VaultCell")
            player = SimpleNamespace(
                pos=(1.0, 2.0, 3.0),
                interior=in_vault,
                loaded=loaded,
                dead=dead,
                Is3DLoaded=lambda: player.loaded,
                IsDead=lambda: player.dead,
                IsInInterior=lambda: player.interior,
                SetPosition=lambda x, y, z: (sets.append((x, y, z)), setattr(player, "pos", (x, y, z))),
                MoveTo=lambda ref, dx, dy, dz, *rest: moves.append((ref, dx, dy, dz)),
                SetAngle=lambda rx, ry, rz: angles.append((rx, ry, rz)),
                RestoreValue=lambda av, amt: restores.append((av, amt)),
            )

            def get_form(fid, plg):
                if (fid, plg) == (0x0002D4, "Starfield.esm"):
                    return health_av
                if (fid, plg) == (0x805, "FO4Port.esm"):
                    return vault_anchor
                if (fid, plg) == (0x005C50, "FO4TerrainCore.esm"):
                    return bench_ref
                if (fid, plg) == (0x0A775B, "FO4TerrainCore.esm") and allow_anchor[0]:
                    return exit_ref
                return None

            ns = dict(
                _PStr=lambda v: "None" if v is None else str(v),
                GameModeGlobal=SimpleNamespace(GetValue=lambda: mode),
                CorePlugin="FO4TerrainCore.esm",
                ExitAnchorId=0x0A775B,
                VaultPlugin="FO4Port.esm",
                VaultAnchorId=0x805,
                AnchorX=-60.0, AnchorY=0.0, AnchorZ=-1.0,
                PodX=-62.5, PodY=1.5, PodZ=-1.0, PodLift=0.3, PodHeading=90.0,
                applied=0, pendingStage=-1, pendingStageBy="other", exitUsedFallback=False,
                vaultPodAutosaved=pre_autosaved, vaultSavingRelocked=False, vaultRecoveryTriggered=False,
                vaultPodAutosaveSkips=0, loadHookRegistered=False, dyingHookRegistered=False,
                warfareFadeTicks=0, storyFadeTicks=0, modeBoxWaiting=False, modeBoxWaitSeconds=0,
                ticks=0, looksSetStage20=False,
                LogName="fo4sf_newgame",
                h00SuspectsRead=False, rideActive=False, rideDone=False, rideTransferred=False,
                ridingLift=None, ridingCell=None, surfaceMovedAt=0.0, surfaceMoves=0, surfaceSets=0,
                asked=False, returnSurfacePending=False, returnVaultAsked=False,
                returnSurfaceWaitTicks=0, returnSurfaceTries=0, exitFailures=0,
                Debug=SimpleNamespace(OpenUserLog=lambda *_: None),
                ReturnPlayerToVaultPlatform=lambda *_: None,
                UnregisterForAnimationEvent=lambda *_: None,
                Game=SimpleNamespace(
                    GetPlayer=lambda: player,
                    GetFormFromFile=get_form,
                    SetInChargen=lambda a, b, c: chargens.append((a, b, c)),
                    RequestAutoSave=lambda: autosaves.append(cur_stage[0]),
                    ShowFirstPersonGeometry=lambda *a: None,
                    FadeOutGame=lambda *a: None,
                    SetCharGenHUDMode=lambda *a: None,
                ),
                RegisterForRemoteEvent=lambda obj, ev: reg_events.append((obj, ev)),
                StandsInVault=lambda p: p.interior,
                StartTimer=lambda s, tid: timers.append((s, tid)),
                CancelTimer=lambda tid: cancels.append(tid),
                GetStage=lambda: cur_stage[0],
                SetStage=lambda st: (cur_stage.__setitem__(0, st), ns["StageSetEvent"](st, 0) if fire_stage_set else None),
                SetObjectiveDisplayed=lambda *a: None,
                SetObjectiveCompleted=lambda *a: None,
                SetActive=lambda *a: None,
                CompleteQuest=lambda: None,
                StartLandingQuests=lambda: None,
                ReleaseStoryLandingFade=lambda: None,
                Trace=lambda m: logs.append(m),
            )
            exec(compiled, ns)
            return SimpleNamespace(
                ns=ns, player=player, cur_stage=cur_stage, logs=logs, chargens=chargens,
                autosaves=autosaves, timers=timers, cancels=cancels, reg_events=reg_events,
                moves=moves, sets=sets, angles=angles, restores=restores,
                health_av=health_av, bench_ws=bench_ws, anchor_ws=anchor_ws, allow_anchor=allow_anchor,
            )

        # 1. Stage 20 cryo pod opens -> autosave once (momentary save unlock), then Timer 6 re-locks inside Vault (< 200)
        c1 = run_case(initial_stage=10, mode=1.0, in_vault=True)
        c1.cur_stage[0] = 20
        c1.ns["ApplyStage"](20, "Trigger")
        self.assertTrue(c1.ns["vaultPodAutosaved"])
        self.assertEqual(c1.autosaves, [20])
        self.assertEqual(c1.chargens, [(False, False, False)])
        self.assertIn((1.5, 6), c1.timers)
        self.assertIn("vault_death_recovery=autosave stage=20 skips=0", c1.logs)
        self.assertIn((c1.player, "OnDying"), c1.reg_events)
        c1.ns["TimerEvent"](6)
        self.assertTrue(c1.ns["vaultSavingRelocked"])
        self.assertEqual(c1.chargens[-1], (True, False, False))
        self.assertIn("vault_death_recovery=save_locked stage=20", c1.logs)

        # Dying after pod autosave logs autosave mode and lets the engine reload that autosave
        c1.ns["DyingEvent"](c1.player, None)
        self.assertIn("vault_death_recovery=autosave stage=20", c1.logs)
        self.assertEqual(c1.restores, [])

        # Stage 40 exit cancels Timers 6 & 7 and clears the Vault save lock
        c1.cur_stage[0] = 40
        c1.ns["ApplyStage"](40, "Trigger")
        self.assertIn(6, c1.cancels)
        self.assertIn(7, c1.cancels)
        self.assertFalse(c1.ns["vaultSavingRelocked"])
        self.assertEqual(c1.chargens[-1], (False, False, False))

        # 1b (#853 M1): If player is unloaded / outside vault at stage 20, autosave is skipped and retried via Timer 7
        c_skip = run_case(initial_stage=10, mode=1.0, in_vault=True, loaded=False)
        c_skip.cur_stage[0] = 20
        c_skip.ns["ApplyStage"](20, "Trigger")
        self.assertFalse(c_skip.ns["vaultPodAutosaved"])
        self.assertEqual(c_skip.ns["vaultPodAutosaveSkips"], 1)
        self.assertEqual(c_skip.autosaves, [])
        self.assertIn("vault_death_recovery=autosave_skip skips=1 stage=20", c_skip.logs)
        self.assertIn((1.0, 7), c_skip.timers)
        c_skip.player.loaded = True
        c_skip.ns["TimerEvent"](7)
        self.assertTrue(c_skip.ns["vaultPodAutosaved"])
        self.assertEqual(c_skip.autosaves, [20])
        self.assertIn("vault_death_recovery=autosave stage=20 skips=1", c_skip.logs)

        # 1c (#852 candidate-2g-fix4): Quick Start path (FO4SF_NewGameLooks.Done("quick start") -> NoteLooksStage20 -> SetStage(20))
        # MUST arm/fire vault_death_recovery=autosave stage=20 even though OnStageSet(20) short-circuits ApplyStage;
        # a subsequent death reloads via the engine with zero RequestAutoSave during OnDying.
        c_qs = run_case(initial_stage=10, mode=1.0, in_vault=True)

        def qs_set_stage(st):
            c_qs.cur_stage[0] = st
            c_qs.ns["StageSetEvent"](st, 0)

        looks_ns = dict(
            GetStage=lambda: c_qs.cur_stage[0],
            SetStage=qs_set_stage,
            TracePosition=lambda *_: None,
            Trace=lambda m: c_qs.logs.append(m),
        )
        looks_ns["self"] = SimpleNamespace(NoteLooksStage20=c_qs.ns["NoteLooksStage20"])
        exec(looks_compiled, looks_ns)
        looks_ns["Done"]("quick start")
        self.assertTrue(c_qs.ns["looksSetStage20"])
        self.assertTrue(c_qs.ns["vaultPodAutosaved"])
        self.assertEqual(c_qs.cur_stage[0], 20)
        self.assertEqual(c_qs.autosaves, [20])
        self.assertEqual(c_qs.chargens, [(False, False, False)])
        self.assertIn("vault_death_recovery=autosave stage=20 skips=0", c_qs.logs)
        self.assertIn((1.5, 6), c_qs.timers)
        c_qs.ns["TimerEvent"](6)
        self.assertTrue(c_qs.ns["vaultSavingRelocked"])
        self.assertEqual(c_qs.chargens[-1], (True, False, False))
        c_qs.player.dead = True
        c_qs.ns["DyingEvent"](c_qs.player, None)
        self.assertEqual(c_qs.autosaves, [20])
        self.assertEqual(c_qs.restores, [])
        self.assertIn("vault_death_recovery=autosave stage=20", c_qs.logs)

        # 1d (Task 0a): Even when SetStage(20) does NOT fire OnStageSet synchronously, NoteLooksStage20() MUST commit
        # stage 20 BEFORE TriggerVaultPodRecoveryAutosave(20) calls Game.RequestAutoSave(), so pod autosave is ALWAYS stage 20.
        c_qs_nosync = run_case(initial_stage=10, mode=1.0, in_vault=True, fire_stage_set=False)
        looks_nosync_ns = dict(
            GetStage=lambda: c_qs_nosync.cur_stage[0],
            SetStage=lambda st: c_qs_nosync.cur_stage.__setitem__(0, st),
            TracePosition=lambda *_: None,
            Trace=lambda m: c_qs_nosync.logs.append(m),
            self=SimpleNamespace(NoteLooksStage20=c_qs_nosync.ns["NoteLooksStage20"]),
        )
        exec(looks_compiled, looks_nosync_ns)
        looks_nosync_ns["Done"]("quick start")
        self.assertEqual(c_qs_nosync.cur_stage[0], 20)
        self.assertEqual(c_qs_nosync.autosaves, [20])
        self.assertEqual(c_qs_nosync.logs.count("stage 20 by=other"), 0)

        # Direct OnStageSet(20, 0) (even when applied >= 20 and looksSetStage20=True) also fires stage=20 autosave once
        c_set20 = run_case(initial_stage=20, mode=1.0, in_vault=True)
        c_set20.ns["applied"] = 20
        c_set20.ns["looksSetStage20"] = True
        c_set20.ns["StageSetEvent"](20, 0)
        self.assertTrue(c_set20.ns["vaultPodAutosaved"])
        self.assertEqual(c_set20.autosaves, [20])
        self.assertIn("vault_death_recovery=autosave stage=20 skips=0", c_set20.logs)

        # Even if StageSetEvent(20, 0) is reached directly with applied >= 20, autosave fires and dead player cancels Timer 7
        c_dead = run_case(initial_stage=20, mode=1.0, in_vault=True, pre_autosaved=False, dead=True)
        c_dead.ns["applied"] = 20
        c_dead.ns["StageSetEvent"](20, 0)
        self.assertFalse(c_dead.ns["vaultPodAutosaved"])
        self.assertEqual(c_dead.autosaves, [])
        self.assertEqual(c_dead.chargens, [])
        self.assertEqual(c_dead.timers, [])
        self.assertIn(7, c_dead.cancels)

        # 2. Dying BEFORE stage 200 without an autosave restores health + moves to pod coords + logs pod_reset + arms Timer 7 (NO save in OnDying!)
        c2 = run_case(initial_stage=10, mode=1.0, in_vault=True, pre_autosaved=False)
        c2.ns["DyingEvent"](c2.player, None)
        self.assertEqual(c2.restores, [(c2.health_av, 9999.0)])
        self.assertAlmostEqual(c2.sets[-1][0], -62.5, places=3)
        self.assertAlmostEqual(c2.sets[-1][1], 1.5, places=3)
        self.assertAlmostEqual(c2.sets[-1][2], -0.7, places=3)
        self.assertEqual(c2.angles[-1], (0.0, 0.0, 90.0))
        self.assertEqual(c2.autosaves, [])
        self.assertEqual(c2.chargens, [])
        self.assertIn((1.0, 7), c2.timers)
        self.assertNotIn((1.5, 6), c2.timers)
        self.assertFalse(c2.ns["vaultPodAutosaved"])
        self.assertIn("vault_death_recovery=pod_reset stage=10", c2.logs)
        # Timer 7 then performs the deferred pod autosave & resets vaultRecoveryTriggered so subsequent Vault deaths reload autosave
        c2.ns["TimerEvent"](7)
        self.assertTrue(c2.ns["vaultPodAutosaved"])
        self.assertFalse(c2.ns["vaultRecoveryTriggered"])
        self.assertEqual(c2.autosaves, [10])
        self.assertIn("vault_death_recovery=autosave stage=10 skips=0", c2.logs)

        # 2b. Death-reload onto the stage-20 pod autosave (saved before Timer 6) re-locks Vault saving on load,
        # and ApplyStage(210) clears vaultSavingRelocked / SetInChargen symmetrically with ApplyStage(40)/(200).
        c_reload = run_case(initial_stage=20, mode=1.0, in_vault=True, pre_autosaved=True)
        c_reload.ns["OnPlayerLoadGame"](c_reload.player)
        self.assertTrue(c_reload.ns["vaultSavingRelocked"])
        self.assertEqual(c_reload.chargens[-1], (True, False, False))
        self.assertIn("vault_death_recovery=save_locked stage=20", c_reload.logs)
        c_reload.cur_stage[0] = 210
        c_reload.ns["ApplyStage"](210, "Trigger")
        self.assertIn(6, c_reload.cancels)
        self.assertIn(7, c_reload.cancels)
        self.assertFalse(c_reload.ns["vaultSavingRelocked"])
        self.assertEqual(c_reload.chargens[-1], (False, False, False))

        # 3. After stage 200 or in Warfare mode, Vault death recovery does not trigger
        c3 = run_case(initial_stage=200, mode=1.0, in_vault=True, pre_autosaved=False)
        c3.ns["DyingEvent"](c3.player, None)
        self.assertFalse(c3.ns["vaultRecoveryTriggered"])
        c4 = run_case(initial_stage=10, mode=2.0, in_vault=True, pre_autosaved=False)
        c4.ns["DyingEvent"](c4.player, None)
        self.assertFalse(c4.ns["vaultRecoveryTriggered"])

        # 4. Task 1i (#858 F7): ResolveHostWorld checks persistent ExitAnchorId 0x0A775B FIRST, falling back to 0x005C50
        self.assertIs(c1.ns["ResolveHostWorld"](), c1.anchor_ws)
        c1.allow_anchor[0] = False
        self.assertIs(c1.ns["ResolveHostWorld"](), c1.bench_ws)
        self.assertNotIn("MarsPlanetWorld", psc)

        # 5. make_newgame.summarize() records vault_death_recovery lines
        s = ng.summarize([
            "[x] FO4SF_NEWGAME rt=10.0 vault_death_recovery=autosave stage=20 skips=0\n",
            "[x] FO4SF_NEWGAME rt=12.0 vault_death_recovery=save_locked stage=20\n",
        ])
        self.assertEqual(s["vault_death_recovery"], ["autosave stage=20 skips=0", "save_locked stage=20"])


if __name__ == "__main__":
    unittest.main()
