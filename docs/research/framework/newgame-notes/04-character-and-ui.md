# 04: Character creation, player identity and the Fallout UI (new game, Vault 111 start)

Claude (cloud research agent), 2026-10-19. Web research only; nothing here was run in game or read from the
owner's PC. Labels: **verified** (a primary or tool-generated source says so directly), **supported hypothesis**
(secondary sources or inference), **unresolved**. Context read first: `docs/newgame/vault111-start.md` and
`scripts/newgame/FO4SF_NewGameLooks.psc` (our plugin calls `Game.ShowRaceMenu()` with no arguments in the vault).

Pages I could not read (the fetch proxy rate-limited them with HTTP 429, so they were not retried): news.xbox.com
"Starfield Starters: Customizing Your Perfect Captain", the TrueAchievements Starfield walkthrough part 4, Nexus
Starfield mod 15088, and dev.starfieldwiki.net `Script-ScriptObject`. Fextralife and help.bethesda.net refuse robots.
The points that depended on them are marked unresolved below.

---

## 1. Game.ShowRaceMenu in Starfield

- **verified (signature):** Starfield's Game script declares
  `ShowRaceMenu(ObjectReference akMenuTarget=NONE, int uiMode=0, ObjectReference akMenuSpouseFemale=NONE,
  ObjectReference akMenuSpouseMale=NONE, ObjectReference akVendor=NONE) NativeGlobal`. The doc comment lists modes
  0 chargen, 1 remake (player only, sex locked), 2 haircut, 3 plastic surgery, 4 face paint.
  https://papyrus.bellcube.dev/starfield/script/game/function/showracemenu/ . The same text and parameters are FO4's
  (https://falloutck.uesp.net/wiki/ShowRaceMenu_-_Game), spouse parameters included, so the comment is probably
  inherited from FO4 and the mode list may not describe Starfield's menu (**supported hypothesis**).
- **verified:** the same Game script has `PrecacheCharGen()`, `PrecacheCharGenClear()`, `SetCharGenHUDMode(int)`
  and `SetInChargen(bool abDisableSaving, bool abDisableWaiting, bool abShowControlsDisabledMessage)`. It has no
  Papyrus function for the player name, pronouns, voice, traits or backgrounds.
  https://papyrus.bellcube.dev/starfield/script/game/
- **verified (community):** the console command `showlooksmenu player 1` (`slm player 1`) opens the full creator,
  traits and background included. `slm player 2` opens a partial creator without traits and background.
  https://www.gamesradar.com/starfield-console-commands-cheats/ ; also used this way by the Nexus preset save
  https://www.nexusmods.com/starfield/mods/2792
- **supported hypothesis:** `ShowRaceMenu()` with uiMode 0 behaves like `slm player 1`: the full chargen with the
  Background and Traits screens. Nothing public maps uiMode to the slm number. A modder in
  https://forums.nexusmods.com/topic/13492009-help-locating-ng-chargenmenu-trigger/ was told to try
  `Game.ShowRaceMenu(None, 1)`, `Game.ShowRaceMenu()`, `ShowMenu ChargenMenu` and `SLM 1`. The same thread found
  that NG+ calls `ShowRaceMenu` from `mq401questscript`. **What uiMode 1 shows in Starfield is unresolved.**
- **verified (thread above):** the vanilla early MQ scripts wrap chargen in `SetInChargen`, an `InputEnableLayer`
  and `DisablePlayerControls`. When a modder removed or redirected the NG+ chargen trigger, the player was left
  partly locked (could look and jump, no Esc). A `coc` to another cell cleared it. The root cause stayed unresolved.
  This is the main risk for us, because we stop MQ101 and then open the menu ourselves.
- **verified (side effect):** reopening the full creator mid-game to add traits **resets the appearance**, and the
  traits Hero Worshipped, Dream Home and Kid Stuff start quests that may not work when added later. Source: the Take
  More Traits author, https://nexusmods.com/starfield/mods/4162 .
- **verified:** the in-game Enhance! kiosk reopens the creator for 500 credits. It changes sex, body, face and name,
  but not background, traits or skills. https://www.ggrecon.com/guides/starfield-how-to-change-character-appearance/
  Pronouns are changed by talking to the Enhance! manager (500 credits).
  https://insider-gaming.com/how-to-change-your-pronouns-in-starfield/
- **verified:** the chargen UI is a Scaleform file, `chargenmenu.swf`. Expanded Backgrounds ships an edited copy
  (made with JPEXS) and warns about other mods that change it. https://www.nexusmods.com/starfield/mods/15724
  So the Background and Traits tabs can in principle be hidden, reskinned or relabelled in the SWF.
- **verified (our precheck, docs/newgame/vault111-start.md):** Starfield's Utility.psc has no `IsInMenuMode`.
  **Unresolved:** whether Starfield's ScriptObject keeps FO4's `RegisterForMenuOpenCloseEvent`,
  `OnMenuOpenCloseEvent` and `RegisterForLooksMenuEvent`
  (FO4: https://falloutck.uesp.net/wiki/RegisterForMenuOpenCloseEvent_-_ScriptObject ). If it does, we can wait
  for "ChargenMenu" to close instead of guessing.

## 2. Backgrounds, traits, name, pronouns, voice

- **verified:** backgrounds and traits are perks. They are added with `player.addperk`, for example Chef
  `0022EC7F`, Hero Worshipped `00227FD9` and Alien DNA `00227FDA`.
  https://www.gamerguides.com/starfield/guide/mods/console-commands/all-perks-console-item-ids-for-starfield
  The "[File not found]" background is removed with `player.removeperk 002DFD1A`.
  https://www.nexusmods.com/starfield/mods/2792 and https://www.nexusmods.com/starfield/mods/2765
- **verified:** a background is mandatory (one of about 20 or 21) and gives three starting skills plus some
  dialogue options. Traits are optional, up to 3 of 17, and some exclude each other.
  https://www.ggrecon.com/guides/starfield-backgrounds-traits/
- **verified:** the "[FILE NOT FOUND]" background is the closest thing to a neutral one. It gives Wellness,
  Ballistics and Piloting (two of those are space skills) and has rare unique dialogue.
  https://www.siliconera.com/what-is-the-file-not-found-background-in-starfield/
- **verified:** mods add backgrounds and traits (More Backgrounds https://www.nexusmods.com/starfield/mods/5880 ,
  made with xEdit; Expanded Backgrounds above; Shade's Bonus Backgrounds and Traits
  https://www.nexusmods.com/starfield/mods/7991 , which needs SFSE). So a set of Fallout "backgrounds" is feasible.
  **Unresolved:** how the menu collects backgrounds (a keyword, a form list or the perk record). Read it in the CK
  or xEdit.
- **verified:** pronouns are set in the creator (he/him, she/her, they/them). They default from the body type.
  https://insider-gaming.com/how-to-change-your-pronouns-in-starfield/
- **verified:** Starfield's player is silent. https://www.pcgamer.com/uk/bethesda-confirms-your-starfield-character-will-be-a-silent-protagonist
  That fits our default: nothing is needed for a silent player.
- **verified:** Vasco's "name list" is datamined. If the typed name is on it, Vasco sometimes says it instead of
  "Captain". https://www.windowscentral.com/gaming/xbox/starfield-full-list-of-names-your-in-game-companion-vasco-can-call-you
  FO4 does the same with Codsworth (a separate system). **Unresolved:** how Starfield picks the line (a condition on
  the name, or something else). That matters if converted companions should say the player's name.
- **Unresolved:** whether the name field is inside chargenmenu.swf (the Enhance kiosk renames there, which
  supports this) or a separate prompt, and the order of the screens. The pages describing the order could not be
  read.

## 3. Face and body: can FO4 looks carry over?

- **verified:** Starfield creator presets ("Biometric ID") exist, and community presets ship as **save files** or
  screenshots, not plugin data (https://www.nexusmods.com/starfield/mods/4305 ,
  https://www.nexusmods.com/starfield/mods/2076). That suggests no easy export or import format for player faces.
- **Unresolved:** any FO4 to Starfield face mapping. FO4 FaceGen morphs, tints and the head parts do not
  correspond to Starfield's head system as far as any public tool shows. I found no converter. Treat a FO4
  preset import as a research spike, not a feature.

## 4. A Pip-Boy replacement: Starfield UI tech

- **verified:** Starfield's menus are Scaleform SWF/GFX (ActionScript 3). Modders decompile them with JPEXS
  (https://forums.nexusmods.com/topic/13087164-it-looks-like-bethesda-will-keep-using-scaleform-for-starfield-ui).
  A loose file in `Data\Interface` replaces the vanilla file whole. The last one loaded wins, and loose files beat
  archives (rbtUI2, https://www.nexusmods.com/starfield/mods/17873 ; AstraHUD edits `shipreticle.swf`,
  https://www.nexusmods.com/starfield/mods/15507). Both need `bInvalidateOlderFiles=1` and an empty
  `sResourceDataDirsFinal=`. Neither needs SFSE.
- **verified:** reskins of vanilla menus need no SFSE, so a Fallout look (green phosphor, FO4 fonts) for the HUD
  and messages is feasible without SFSE. rbtUI2 reskins the HUD, messages, markers, star map and cursor.
- **verified:** new menus need SFSE frameworks:
  - SFSE Menu Framework (ImGui, a C++ SDK, game 1.16.244): https://www.nexusmods.com/starfield/mods/18201 ,
    https://github.com/QTR-Modding/SFSE-Menu-Framework
  - OSF UI (HTML/CSS/JS views, **has a Papyrus API**, needs WebView2): https://www.nexusmods.com/starfield/mods/17711
  - Carbon UI (Ultralight HTML, C API, needs DLLs in the game root, game 1.16.244):
    https://www.nexusmods.com/starfield/mods/17899
  An HTML Pip-Boy (status, SPECIAL, inventory list, map, radio) on OSF UI driven from Papyrus is the most direct
  route found (**supported hypothesis**: nobody has published one).
- **verified (by absence):** I found **no published Starfield Pip-Boy mod**. The only hit was a Nexus image
  ("Pip-Boy IN SPACE", https://www.nexusmods.com/starfield/images/4368). Fallout-style UI for Starfield does not
  exist yet and would be our own work.
- **verified (precedent for a stopgap):** the VaultTec S.P.E.C.I.A.L. System puts its menus on a "Regenesys
  Assistant" data slate in Misc and uses terminal menus "until scripts can pass information to the UI".
  https://www.nexusmods.com/starfield/mods/13025 . A wearable or Misc "Pip-Boy" item that opens a terminal menu
  needs no SFSE: a workable phase 1 Pip-Boy.
- SFSE frameworks are PC Steam only, are pinned to one game version (1.16.244 at the time of reading) and are not
  available to Creations or Xbox users (Shade's mod says this outright: https://www.nexusmods.com/starfield/mods/7991).

## 5. SPECIAL vs Starfield skills

- **verified:** Starfield has 82 skills in 5 trees (Physical, Social, Combat, Science, Tech), each with 4 tiers
  unlocked by points spent (4/8/12), and 4 ranks per skill gated by challenges. The background gives 3 starting
  skills. https://www.gamesradar.com/starfield-skills-all
- FO4: SPECIAL is set on the Vault-Tec Rep's form in pre-war Sanctuary, the same scene where the name is chosen
  (MQ101 "War Never Changes", https://fallout-archive.fandom.com/wiki/War_Never_Changes). It is not set in the
  mirror creator.
- **verified:** a SPECIAL mod exists: VaultTec S.P.E.C.I.A.L. System (Project Regenesys, needs HTG System Module
  and the Regenesys Core). Points are set through data slate terminal menus, attributes show in the status menu,
  perks give the bonuses, and you get an extra point every 10 levels.
  https://www.nexusmods.com/starfield/mods/13025 . An add-on moves its perks to the master row:
  https://www.nexusmods.com/starfield/mods/15073 . Its licence forbids re-uploading, so we can study it but not
  ship it.
- Perk points per level can be changed with an SFSE/ASI plugin (PerkPointsPerLevel,
  https://www.nexusmods.com/starfield/mods/1779), which suggests the value is not a plain game setting (**supported
  hypothesis**).

## 6. FO4's opening and what alternate starts keep

- **verified:** FO4 order (https://fallout-archive.fandom.com/wiki/War_Never_Changes): mirror creator (spouse beside
  you), Vault-Tec Rep (SPECIAL and name), the baby and Codsworth, the TV broadcast, the run to Vault 111, the bombs,
  the overseer, the cryo pods, the brief thaw (spouse shot, Shaun taken), the release. Our repo's B4 spike verified
  that the Pip-Boy is picked up in the overseer's office and the cog door console needs it (MQ102).
- **verified:** Start Me Up (https://www.nexusmods.com/fallout4/mods/18946) shows its menu **after the bathroom
  mirror**. It offers a quick start (wake in the pod), a vault start released by mistake (SPECIAL and up to 20
  traits at the cryo terminal), 38 outside starts (SPECIAL, traits, occupation, location, gear and level through
  the bathroom door menu) and the vanilla start. It rewrites over 800 player lines because the protagonist is no
  longer a parent. Alternate Start for FO4 skips the whole intro (https://pcgamer.com/begin-a-new-life-in-fallout-4-with-an-alternate-start-mod).
  The pattern players are used to: **the looks first, then SPECIAL and identity, then the vault**, and a skip for
  replays.
- Starfield precedent: Alternate Start Starfield ships per-background **save files** and tells players to use
  `slm player 1` for looks and traits (https://www.nexusmods.com/starfield/mods/2076). That is the crudest route,
  not one for us.

---

## Questions the new-game design must answer

1. **What does `Game.ShowRaceMenu()` (uiMode 0) show when called by our quest, with MQ101 stopped?** It decides
   whether Background and Traits appear. *In-game test* (one new game, screenshots of every tab).
2. **What do uiMode 1 to 4 show in Starfield?** Mode 1 might be "looks only", which would remove the Starfield
   background and traits for free. *In-game test*, one mode per run.
3. **Does Starfield's ScriptObject have `RegisterForMenuOpenCloseEvent` / `OnMenuOpenCloseEvent` (and the menu
   name "ChargenMenu")?** Without it we cannot wait for the menu to close. *Read-only PC check* of ScriptObject.psc
   in ContentResources.zip.
4. **Which `SetInChargen` / `SetCharGenHUDMode` / `PrecacheCharGen` calls does MQ101 make around its own chargen,
   and do we need them?** Skipping them may leave saving and HUD in the wrong state, and copying them may leave
   controls locked (the NG+ thread). *Read-only PC check* of MQ101's scripts, then an *in-game test*.
5. **After stopping MQ101, are any of its input layers or chargen flags left active?** *In-game test*: after the
   menu, check Esc, saving, waiting, weapons and `GetPlayerControlsDisabled`.
6. **Should the player get a Starfield background at all?** Options: keep the screen; force "[FILE NOT FOUND]";
   strip all backgrounds; or ship Fallout backgrounds (Vault dweller, Soldier, Lawyer). *Owner decision*, then a
   check of how the menu lists backgrounds (question 7).
7. **How does chargenmenu.swf get its background and trait lists (a form list, a keyword or the perk records)?**
   This decides whether we can hide or replace them by data alone. *Read-only PC check* in the CK or xEdit, plus
   the SWF in JPEXS.
8. **Do we edit chargenmenu.swf (hide tabs, Vault-Tec reskin)?** It conflicts with other UI mods and breaks with
   game updates. *Owner decision* after question 1.
9. **Which Starfield traits are harmful in our world** (Hero Worshipped, Dream Home, Kid Stuff, faction
   religions, UC/Freestar citizen, Spaced/Terra Firma)? Their quests and effects assume Starfield's settled
   systems. *Read-only PC check* of each trait's perk and quest, then an *owner decision* on a block list.
10. **Where are SPECIAL and the name set?** FO4 does it at the Vault-Tec Rep before the war, and we start in the
    vault. Options: a cryo terminal (as Start Me Up), a vault clipboard or a G.O.A.T.-style form, or none in
    phase 1. *Owner decision*.
11. **Is SPECIAL in scope, and how does it map onto Starfield's 82 skills?** It changes how the player levels, the
    dialogue checks and our converted FO4 perks. *Owner decision*. Use VaultTec S.P.E.C.I.A.L. as a study (its
    licence forbids re-uploading).
12. **SFSE or not?** Frameworks (OSF UI with Papyrus, SFSE Menu Framework, Carbon UI) give a real Pip-Boy screen but
    lock us to Steam PC and one game version. Without SFSE we get terminal menus and SWF reskins only. *Owner
    decision*. It sets the whole UI plan.
13. **What is the phase 1 Pip-Boy?** A Misc or wearable item opening a terminal menu (no SFSE), an OSF UI HTML
    view (SFSE), or nothing. *Owner decision*. Then an *in-game test* of an item that opens a terminal menu
    from inventory.
14. **Does the cog door keep its "needs the Pip-Boy" rule, with a Pip-Boy item picked up in the overseer's
    office?** That keeps a known FO4 beat. *Owner decision*. The quest change is small (an item check).
15. **Which Starfield UI must be reskinned or hidden for a Fallout feel** (HUD compass, XP messages, scanner,
    skills menu art, the ship HUD)? *Owner decision* on the list, then an *offline check* of which SWFs hold each
    piece (JPEXS over the Interface archive, read-only).
16. **Pronouns and name: do our converted NPC lines need either?** FO4 lines are gendered by the player's sex. A
    "they" player in a gendered FO4 conversation needs a rule. *Offline check* of FO4 dialogue conditions
    (GetIsSex on player), then an *owner decision*.
17. **Do converted companions say the player's name (Codsworth's list) through Starfield's Vasco mechanism?**
    *Read-only PC check* of how Vasco's name lines are conditioned, then an offline check of FO4's Codsworth
    name topics.
18. **Can FO4 face presets or FaceGen be mapped to Starfield's head system?** If not, NPC faces need their own
    approach (a later phase). *Offline spike*: compare FO4 NPC face data (morphs, tints) with Starfield's NPC face
    records.
19. **Should a reopened creator (Enhance-style) exist in our world** (a Vault-Tec barber or surgeon, as FO4's
    uiMode 2/3)? *Owner decision*, then an *in-game test* of uiMode 2 and 3 with akVendor.
20. **Does the creator's preview need a lit room, a mirror or a camera position in Vault 111?** Starfield's
    chargen normally runs in a specific room. *In-game test* of where the camera ends up when called in our cell.
21. **Is a replay "quick start" wanted** (skip the creator and SPECIAL, as Start Me Up's quick start)? *Owner
    decision*. It is cheap once question 3 is solved.
22. **Starting skills and level:** with no background, does the player start with zero skills and a working skills
    menu, and does the level-up flow work outside MQ101? *In-game test* (`player.removeperk` the background, level
    up once).

## The five most important findings

1. `ShowRaceMenu` in Starfield keeps FO4's signature and mode list (0 to 4). `slm player 1` is the full creator
   with background and traits, and `slm player 2` leaves both out, so there is probably a way to show **looks only**.
   Which uiMode does that is the first thing to test.
2. Backgrounds and traits are **perks**, and the creator is **chargenmenu.swf** (already modded with JPEXS). So we
   can hide them, force a neutral one, or replace them with Fallout backgrounds by data and SWF alone.
3. Vanilla chargen sits inside `SetInChargen` and input layers. A modder who redirected NG+ chargen got stuck with
   partly locked controls. Stopping MQ101 and calling the menu ourselves carries the same risk, so we test for it.
4. **No Starfield Pip-Boy mod exists.** Reskins need no SFSE, but new screens need SFSE frameworks (OSF UI has
   Papyrus and HTML). A data slate or terminal menu item is a no-SFSE stopgap with precedent.
5. SPECIAL is set at the Vault-Tec Rep in FO4, not at the mirror, and a Starfield SPECIAL mod exists (data slate
   terminals plus perks). Our vault-only start must choose a new place for SPECIAL and the name, or drop them for
   phase 1.
