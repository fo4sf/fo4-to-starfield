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
sys.path.insert(0, os.path.join(ROOT, "scripts", "newgame"))
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
                version=True, build_version=None, clear_inventory=False, vault_suit=None, require_persistent_anchor=False,
                allow_temporary_anchor=False)


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
        fade = psc[psc.index("Function FadeIn"):psc.index("Function AdvanceTo")]
        code = fade[fade.index("    if faded"):]                  # past the doc comment
        self.assertTrue(code.startswith("    if faded\n        return\n    endif\n    faded = true\n"))
        # the pod's heading again while the screen is still dark, for a player the start moved into the vault
        self.assertIn("    if vaultMoves > 0 && StandsInVault(player)\n        player.SetAngle(0.0, 0.0, PodHeading)\n    endif\n", code)
        self.assertLess(code.index("player.SetAngle(0.0, 0.0, PodHeading)"), code.index("Game.FadeOutGame("))
        self.assertLess(code.index("Game.FadeOutGame(False, True, 0.0, 0.1, False)"), code.index("Game.SetInChargen(false, false, false)"))
        self.assertLess(code.index("Game.SetInChargen(false, false, false)"), code.index("Game.SetCharGenHUDMode(0)"))
        self.assertIn('Trace("fade in by=" + by + " loaded=" + player.Is3DLoaded() + " cell=" + player.GetParentCell() + "; saving and HUD on")', code)
        code_only = re.sub(r"\{[^}]*\}", "", psc)          # the doc comments name the fade call too
        for call in ("Game.FadeOutGame(", "Game.SetInChargen(", "Game.SetCharGenHUDMode("):
            self.assertEqual(code_only.count(call), 1, call)  # in FadeIn alone
        begin = psc[psc.index("Function Begin"):psc.index("Function StandDown")]
        self.assertLess(begin.index("StartTimer(1.0, 1)"), begin.index("player.WaitFor3DLoad()"))
        self.assertLess(begin.index("player.WaitFor3DLoad()"), begin.index('FadeIn("start")'))
        self.assertIn('    player.WaitFor3DLoad()                                   ; latent: returns once the 3D is in, or will not load\n'
                      '    bool ready = player.Is3DLoaded()\n    Trace("3d wait over loaded=" + ready)\n'
                      '    if ready\n        FadeIn("start")', begin)
        zero = psc[psc.index("    if stage == 0\n"):psc.index("    elseif stage == 10")]
        self.assertIn('        if !player.Is3DLoaded()\n', zero)
        self.assertIn('            StartTimer(1.0, 1)                               ; the game is still loading\n'
                      '            return\n        endif\n        FadeIn("timer")', zero)
        self.assertLess(zero.index('        if !player.Is3DLoaded()\n'), zero.index('FadeIn("timer")'))
        self.assertLess(zero.index('FadeIn("timer")'), zero.index("if !entered"))
        self.assertEqual(len(re.findall(r'\bFadeIn\("', psc)), 2)   # the two calls, each behind its 3D check
        self.assertIn("FadeOutGame", ng.NATIVES[ng.SCRIPT]["Game"])
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
        self.assertIn("LooksWait", written)                  # 0 in a --no-looks build, so the quest does not wait
        self.assertEqual(looks_written, {"StartMessage", "RaceMenuMode"})
        self.assertEqual(special_written, {"Special", "TerminalMessage", "SpecialMessage", "TerminalId", "TerminalX", "TerminalY", "TerminalZ"})
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
        """NG-K8: the reset is one default (off) in the writer and Python; --clear-inventory makes the quest script
        empty the inventory once the player is confirmed in the vault and before stage 10, logging the count (whether
        quest items stay is unverified: Starfield's third parameter is abRespectTargetCapacity, so neither the doc nor
        the line claims it); --vault-suit names the port's ARMO the writer resolves by EditorID (refused without
        --clear-inventory) and the script adds and equips after the reset, logging it. Every native of it is
        prechecked, and the plan records both."""
        cs, psc = read(CS), read(PSC)
        self.assertIn(f"DefaultClearInventory = {str(ng.DEFAULT_CLEAR_INVENTORY).lower()};", cs)
        self.assertFalse(ng.DEFAULT_CLEAR_INVENTORY)
        self.assertIn('a.Contains("--clear-inventory")', cs)
        self.assertIn('ArgOrNull(a, "--vault-suit")', cs)
        self.assertIn("it needs --clear-inventory", cs)
        self.assertIn('("ClearInventory", o.ClearInventory), ("VaultSuitId", (int)p.VaultSuit)', cs)
        self.assertIn("port.Armors.Where(x => string.Equals(x.EditorID, vaultSuit", cs)
        self.assertIn('Owned(suits[0], port.ModKey, $"the vault suit {vaultSuit}")', cs)
        self.assertIn("bool Property ClearInventory = false Auto Const", psc)
        self.assertIn("int Property VaultSuitId = 0 Auto Const", psc)
        body = psc[psc.index("Event OnTimer"):]
        enter = body.index("if !entered\n            StartTimer(1.0, 1)")
        self.assertLess(enter, body.index("if ClearInventory\n            ResetInventory(player)"))
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
        self.assertEqual(ng.tool_options(namespace(clear_inventory=True)), ["--clear-inventory"])
        self.assertEqual(ng.tool_options(namespace(clear_inventory=True, vault_suit="FO4Port_VaultSuit111")),
                         ["--clear-inventory", "--vault-suit", "FO4Port_VaultSuit111"])
        with self.assertRaises(SystemExit):
            ng.tool_options(namespace(vault_suit="FO4Port_VaultSuit111"))
        self.assertIn("--clear-inventory", read(DOC))
        self.assertIn("--vault-suit", read(DOC))
        self.assertIn("## 4c. The starting inventory reset", read(DOC))

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
        self.assertLess(begin.index("entered = EnterVault(player)"), begin.index("if vaultMoves == 0 && centered == 0"))
        self.assertLess(begin.index("if vaultMoves == 0 && centered == 0"), begin.index("HoldOffPass(1)"))
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
        self.assertIn("float drop = PodZ + PodLift - player.GetPositionZ()", check)
        self.assertIn("bool ok = dx * dx + dy * dy <= PodRadius * PodRadius && drop <= PodDrop", check)
        self.assertIn('Trace("pod settle ok=" + ok + " pos="', check)
        for call in ("MoveTo(", "SetPosition(", "CenterOnCell("):
            self.assertNotIn(call, check)                    # evidence only
        self.assertEqual(psc.count("CheckPod(player)"), 1)

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
        self.assertIn('Trace("surface setposition ok=" + ok + " set=" + surfaceSets', finish)
        self.assertIn("if ok || surfaceSets >= SurfaceTries", finish)
        self.assertLess(finish.index("if ok || surfaceSets >= SurfaceTries"), finish.index("AdvanceTo(40)"))
        self.assertIn("if surfaceMoves < 2", finish)
        self.assertIn("asked = false", finish)               # a missed ride lets the platform ask again
        self.assertEqual(psc.count("AdvanceTo(40)"), 1)
        self.assertEqual(psc.count("FinishSurface(player)"), 1)   # only a later tick's OnTimer finishes the ride
        invault = psc[psc.index("Function InVault"):psc.index("Function Surface(Actor player)")]
        self.assertIn("Surface(player)", invault)
        self.assertNotIn("SetPosition(", invault)
        body = psc[psc.index("Event OnTimer"):psc.index("bool Function IsNewGame")]
        branch = body[body.index("elseif stage == 20 || stage == 30"):body.index("elseif stage == 40")]
        self.assertIn("if surfaceMovedAt > 0.0\n            FinishSurface(player)", branch)
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
        self.assertEqual(len(ng.SPECIAL_BUTTONS), 10)         # FO4's MESG limit; the script's button indices
        self.assertIn("if button >= 0 && button < 7", special)
        self.assertIn("elseif button == 7", special)         # Reset
        self.assertIn("elseif button == 8", special)         # Confirm
        self.assertIn("int[] values = new int[7]", special)
        self.assertIn("player.SetValue(Special[i], values[i] as float)", special)
        self.assertIn('Trace("special set S="', special)
        self.assertIn('Trace("special skipped: left the vault with SPECIAL unset")', special)
        self.assertIn('Trace("special later")', special)
        self.assertIn('Trace("special left: ', special)
        self.assertIn("ActorValue[] Property Special Auto Const Mandatory", special)
        self.assertIn('string Property VaultPlugin = "FO4Port.esm" Auto Const', special)
        self.assertNotIn("Special", psc.split("}", 1)[1])     # the quest script knows nothing of it
        self.assertIn('SpecialScript = "FO4SF_NewGameSpecial"', cs)
        self.assertIn('a.Contains("--no-special")', cs)
        self.assertIn("Types.SpecialAttribute", cs)
        self.assertIn("Flag.DefaultToOne | SF.ActorValueInformation.Flag.MinimumOne | SF.ActorValueInformation.Flag.MaximumTen", cs)
        self.assertIn("Max = SpecialMax, Flags = SpecialAvifFlags", cs)
        self.assertIn('"TerminalId", (int)p.Terminal', cs)
        self.assertEqual(ng.tool_options(namespace(special=False)), ["--no-special"])
        self.assertEqual(ng.OPTIONAL, {ng.LOOKS: "--no-looks", ng.SPECIAL: "--no-special", ng.VERSION: "--no-version"})

    def test_the_allocation_rule(self):
        """special_press is FO4SF_NewGameSpecial.Allocate's rule: base 1 each, 21 points, 10 at most per stat, Reset
        starts over, Confirm only with every point spent, Leave (or a closed message) keeps the defaults."""
        base, pts = [ng.SPECIAL_BASE] * 7, ng.SPECIAL_POINTS
        values, left, end = ng.special_press(base, pts, 0)
        self.assertEqual((values, left, end), ([2, 1, 1, 1, 1, 1, 1], 20, None))
        for _ in range(12):                                   # Strength stops at 10 and costs nothing past it
            values, left, end = ng.special_press(values, left, 0)
        self.assertEqual((values[0], left, end), (ng.SPECIAL_MAX, 12, None))
        self.assertEqual(ng.special_press(values, left, 8), (values, 12, None))          # Confirm with points left
        for b in (1, 2, 3, 4, 5, 6, 6, 6, 6, 6, 6, 6):        # spend the rest
            values, left, end = ng.special_press(values, left, b)
        self.assertEqual((values, left, end), ([10, 2, 2, 2, 2, 2, 8], 0, None))
        self.assertEqual(sum(values), 7 * ng.SPECIAL_BASE + ng.SPECIAL_POINTS)
        self.assertEqual(ng.special_press(values, 0, 3), (values, 0, None))              # no points left
        self.assertEqual(ng.special_press(values, 0, 8), (values, 0, "set"))
        self.assertEqual(ng.special_press(values, 0, 7), (base, pts, None))
        self.assertEqual(ng.special_press(values, 0, 9), (values, 0, "left"))
        self.assertEqual(ng.special_press(base, pts, -1), (base, pts, "left"))

    def test_the_race_menu_mode_and_the_opening_choice(self):
        """NG-6 / NG-C9 / NG-C1: the writer's --race-menu-mode (default 0) is the looks script's RaceMenuMode, passed
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
        self.assertIn('Text = "Create character"', cs)
        self.assertIn('Text = "Quick start"', cs)
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
        self.assertEqual(ng.STAGES, (1, 10, 20, 30, 40, 200))
        self.assertEqual(list(ng.STAGE_CONTRACT), [0] + list(ng.STAGES))
        doc = read(os.path.join(ROOT, "docs", "newgame", "vault111-start.md"))
        for n, what in ng.STAGE_CONTRACT.items():
            self.assertIn(f"| {n} | {what} |", doc)

    def test_the_writer_defaults_match_the_python_ones(self):
        """NG-2: the default build writes NO GLOB MQ101Debug override (28 Oct run 2) and the quest writes 2 right after the
        hold-off (--debug-after-hold); --mq101debug <n> overrides the record for an experiment. NG-19 / NG-N1: the
        default hold list has the two quests MQ101's stage 9000 starts on stop."""
        cs = read(CS)
        self.assertIn("DefaultHold = { " + ", ".join(f'"{q}"' for q in ng.DEFAULT_HOLD) + " }", cs)
        self.assertNotIn("DefaultMQ101Debug", cs)
        self.assertIn(f"DefaultDebugAfterHold = {ng.DEBUG_AFTER_HOLD};", cs)
        self.assertIn('ArgOrNull(a, "--mq101debug") is { } d ? float.Parse(d, CultureInfo.InvariantCulture) : null', cs)
        self.assertEqual(ng.DEFAULT_HOLD[2:], ("MQ101PostQuest", "MQ_TutorialQuest_Misc04"))
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
        self.assertLess(zero.index("if !entered\n            StartTimer(1.0, 1)"), zero.index("HoldOffPass(2)"))
        self.assertLess(zero.index("HoldOffPass(2)"), zero.index("AdvanceTo(10)"))
        self.assertEqual((psc.count("HoldOffPass(1)"), psc.count("HoldOffPass(2)"), len(re.findall(r"^\s+HoldOffPass\(", psc, re.M))), (1, 1, 2))
        self.assertIn('" pass=" + pass', psc)
        for q in ng.DEFAULT_HOLD:
            self.assertIn(q, psc)                            # the HoldOff property's doc names the default list

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
        self.assertEqual(ng.NATIVES[ng.SCRIPT]["GlobalVariable"], ["GetValue", "SetValueInt"])
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
        calls = set(re.findall(r"\.(\w+)\(", psc))
        listed = {f for bases in ng.NATIVES[ng.SCRIPT].values() for f in bases}
        own = set(re.findall(r"^\s*\w*\s*Function\s+(\w+)", psc, re.M))
        # GetPositionY/Z share GetPositionX's script; GetDistance is not used; the rest must be listed or our own
        calls |= set(re.findall(r"^Event (On\w+)\(", psc, re.M)) - {"OnTimer"}   # the start events: OnQuestStarted, OnQuestInit
        missing = calls - listed - own - {"GetPositionY", "GetPositionZ"}
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
        self.assertEqual(looks_calls - looks_listed - looks_own, set())
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
           "native global\nFunction SetCharGenHUDMode(int aiCGHUDMode) native global\n")
# Game.FadeOutGame, our own start's fade in: the five-argument call Roleplayers' Alternate Start makes (FO4's parameter
# names; Starfield's declaration is what the precheck reads)
FADE = ("Function FadeOutGame(bool abFadingOut, bool abBlackFade, float afSecsBeforeFade, float afFadeDuration, "
        "bool abStayFaded = false) native global\n")
# Actor.psc's declarations the quest script itself needs: the guard's GetLevel and the inventory reset's EquipItem /
# IsEquipped (FO4's signatures; Starfield's are what the precheck reads). ObjectReference's RemoveAllItems, GetItemCount
# and AddItem are generated from NATIVES below
ACTOR_CORE = ("int Function GetLevel() native\n"
              "Function EquipItem(Form akItem, bool abPreventRemoval = false, bool abSilent = false) native\n"
              "bool Function IsEquipped(Form akItem) native\n")


def fake_zip(path, game=None, utility=None, extra=None, scriptobject=None, actor=None, referencealias=None, debug=None,
             objectreference=None, quest=None):
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
                                              + CHARGEN + FADE,
        "GlobalVariable": "float Function GetValue() native\nFunction SetValueInt(int aiValue) native\n",
        "Message": "int Function Show(" + ", ".join(f"float afArg{i} = 0.0" for i in range(1, 10)) + ") native\n",
        "ObjectReference": objectreference if objectreference is not None else
                           "\n".join(f"Function {f}() native" for f in ng.NATIVES[ng.SCRIPT]["ObjectReference"]),
        "Quest": quest if quest is not None else "\n".join(f"Function {f}() native" for f in ng.NATIVES[ng.SCRIPT]["Quest"]),
        # ScriptObject.psc (PC read 19 Oct): RegisterForMenuOpenCloseEvent is native; the event's signature is FO4's
        "ScriptObject": scriptobject if scriptobject is not None else
                        "Function StartTimer(float a, int b = 0) native\nFunction RegisterForMenuOpenCloseEvent(string asMenuName) native\n"
                        "Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)\nEndEvent\nEvent OnInit()\nEndEvent\n",
        # ReferenceAlias.psc (PC read 19 Oct, NG-L3): OnPlayerLoadGame, the version script's event
        "ReferenceAlias": referencealias if referencealias is not None else
                          "Scriptname ReferenceAlias extends Alias\nEvent OnPlayerLoadGame()\nEndEvent\n",
        "Utility": utility if utility is not None else "float Function GetCurrentRealTime() native global\n"
                                                       "bool Function IsInMenuMode() native global\nFunction Wait(float a) native global\n",
    }
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
        loop = {"actor": "Scriptname Actor extends ObjectReference\n", "objectreference": "Scriptname ObjectReference extends Actor\n"}
        self.assertFalse(ng.declares(loop, "Actor", "SetValue"))
        self.assertEqual(ng.parent_of("Scriptname Actor extends ObjectReference\n"), "ObjectReference")
        self.assertIsNone(ng.parent_of("Scriptname ScriptObject\n"))

    def test_missing_show_race_menu_only_drops_the_looks(self):
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, game="Actor Function GetPlayer() native global\nForm Function GetFormFromFile(int a, string b) native global\n"
                    + CHARGEN + FADE)
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], [])
        self.assertFalse(r["natives"][ng.LOOKS]["Game.ShowRaceMenu"])
        out = os.path.join(self.tmp, "p.json")
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            rc = ng.main(["precheck", "--content-resources", z, "--out", out])
        self.assertEqual(rc, 0)
        self.assertIn("--no-looks", o.getvalue())
        self.assertNotIn("--no-special", o.getvalue())
        self.assertTrue(os.path.isfile(out))

    def test_missing_set_value_only_drops_the_special(self):
        """Actor.SetValue / GetValue are what the SPECIAL script needs beyond the quest's natives: a source set
        without them fails only that script, and the precheck says --no-special."""
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, actor="Scriptname Actor extends ObjectReference\n" + ACTOR_CORE)
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], [])
        self.assertFalse(r["natives"][ng.SPECIAL]["Actor.SetValue"])
        self.assertFalse(r["natives"][ng.SPECIAL]["Actor.GetValue"])
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
        """The inventory reset lives in the quest script (its ClearInventory property is off by default, but the
        natives must compile): an Actor.psc without EquipItem / IsEquipped is a core miss, not an optional drop."""
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, actor="Scriptname Actor extends ObjectReference\nint Function GetLevel() native\n"
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
                         "Function ShowRaceMenu(ObjectReference akMenuTarget = None, int uiMode = 0) native global\n" + CHARGEN)
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
        PC read 19 Oct): a source set without them fails only the looks script, and the precheck says --no-looks."""
        z = os.path.join(self.tmp, "cr.zip")
        fake_zip(z, scriptobject="Function StartTimer(float a, int b = 0) native\n")
        r = ng.precheck_zip(z)
        self.assertEqual(r["missing_core"], [])
        self.assertFalse(r["natives"][ng.LOOKS]["ScriptObject.RegisterForMenuOpenCloseEvent"])
        self.assertFalse(r["natives"][ng.LOOKS]["ScriptObject.OnMenuOpenCloseEvent"])
        self.assertTrue(r["natives"][ng.LOOKS]["ScriptObject.StartTimer"])
        with unittest.mock.patch("sys.stdout", io.StringIO()) as o:
            self.assertEqual(ng.main(["precheck", "--content-resources", z]), 0)
        self.assertIn("--no-looks", o.getvalue())


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
           "stage 1")


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
        "[10/20/2026 - 09:00:02AM] FO4SF_NEWGAME rt=7.0 stage 10",
        "[10/20/2026 - 09:00:03AM] FO4SF rt=7.5 pos=1 2 3 (another log's line)",
        "[10/20/2026 - 09:00:03AM] FO4SF_NEWGAME rt=8.0 pod settle ok=true pos=11 20 1 dx=0.0 dy=0.0 drop=0.0",
        "[10/20/2026 - 09:00:04AM] FO4SF_NEWGAME rt=9.0 start choice button=0",
        "[10/20/2026 - 09:00:40AM] FO4SF_NEWGAME rt=45.0 looks done: creator closed",
        "[10/20/2026 - 09:00:40AM] FO4SF_NEWGAME rt=45.0 stage 20",             # the looks script's Done, in its order
        "[10/20/2026 - 09:00:50AM] FO4SF_NEWGAME rt=55.0 terminal prompt button=1",
        "[10/20/2026 - 09:00:50AM] FO4SF_NEWGAME rt=55.0 special later",
        "[10/20/2026 - 09:00:58AM] FO4SF_NEWGAME rt=58.0 terminal prompt button=0",
        "[10/20/2026 - 09:00:59AM] FO4SF_NEWGAME rt=59.0 special set S=10 P=2 E=2 C=2 I=2 A=2 L=8 readback=10.000000 8.000000",
        "[10/20/2026 - 09:01:00AM] FO4SF_NEWGAME rt=60.0 status stage=20 pos=50 10 0 cell=x world=None",
        "[10/20/2026 - 09:02:00AM] FO4SF_NEWGAME rt=120.0 elevator prompt button=0",
        "[10/20/2026 - 09:02:00AM] FO4SF_NEWGAME rt=120.1 surface moveto pos=-1250 1290 110 world=[WorldSpace <x>] moves=1",
        "[10/20/2026 - 09:02:01AM] FO4SF_NEWGAME rt=121.1 surface setposition ok=true set=1 pos=-2450 -1410 110 target=-2450 -1410 110",
        "[10/20/2026 - 09:02:01AM] FO4SF_NEWGAME rt=121.1 stage 40",
        "[10/20/2026 - 09:02:04AM] FO4SF_NEWGAME rt=124.2 landed z=110.0",          # CheckLanding: 3 s after the arrival
        "[10/20/2026 - 09:02:04AM] FO4SF_NEWGAME rt=124.2 stage 200",
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
        """Codex review on #393 (P2): the quest's AdvanceTo is where "stage <n>" is traced, but the looks script sets
        stage 20 itself (SetStage, not AdvanceTo), so a looks run logged no "stage 20" and the summary's "stages"
        skipped it; the fixture above hid that with a line no script wrote. The looks script's Done now traces the same
        line, to the same log in the same format, right after SetStage(20); the summary reads it, and a looks run
        without it would still miss the stage."""
        quest, looks = read(PSC), read(LOOKS)
        self.assertIn('Trace("stage " + n)', quest[quest.index("Function AdvanceTo"):quest.index("EndFunction", quest.index("Function AdvanceTo"))])
        done = looks[looks.index("Function Done"):]
        done = done[:done.index("EndFunction")]
        self.assertLess(done.index('Trace("looks done: " + how)'), done.index("SetStage(20)"))
        self.assertLess(done.index("SetStage(20)"), done.index('Trace("stage 20")'))
        # the same log and the same line format as the quest's Trace
        self.assertIn('string LogName = "fo4sf_newgame"', quest)
        self.assertIn('Debug.TraceUser(LogName, "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " " + msg)', quest)
        self.assertIn('Debug.TraceUser("fo4sf_newgame", "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " " + msg)', looks)
        self.assertIn(20, ng.summarize(self.LINES)["stages"])
        without = [ln for ln in self.LINES if not ln.endswith(" stage 20")]
        self.assertEqual(ng.summarize(without)["stages"], [10, 40, 200])

    def test_inventory_lines(self):
        """The inventory reset (NG-K8): a default build logs neither line (both None); a --clear-inventory build logs
        the count; a --vault-suit build the suit, or that it did not resolve."""
        head = "[x] FO4SF_NEWGAME rt=2.0 init holdoff=4 vault=FO4Port.esm:2049 anchor_temporary=False core=FO4TerrainCore.esm:685915\n"
        s = self.run_log(head + "[x] FO4SF_NEWGAME rt=7.0 enter vault ok=True pos=11 20 1 target=11 20 1 cell=x\n")[1]
        self.assertEqual((s["inventory_cleared"], s["vault_suit"]), (None, None))
        s = self.run_log(head + "[x] FO4SF_NEWGAME rt=7.0 inventory cleared removed=0 left=0\n")[1]
        self.assertEqual((s["inventory_cleared"], s["vault_suit"]), ("removed=0 left=0", None))
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
                                   guard.format(12), STOOD_DOWN, handing.format("not a new game"), handed, "stage 1"))
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
        code, s = self.run_log(head + "[x] FO4SF_NEWGAME rt=9.0 special later\n[x] FO4SF_NEWGAME rt=12.0 special left: defaults kept, 21 points unspent\n"
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


@unittest.skipUnless(shutil.which("dotnet"), "no dotnet SDK on PATH")
class WriterSelfTest(unittest.TestCase):
    def test_selftest(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", os.path.join(ROOT, "dotnet", "NewGame"), "--",
                            "selftest", tmp], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn("selftest pass", r.stdout)


if __name__ == "__main__":
    unittest.main()
