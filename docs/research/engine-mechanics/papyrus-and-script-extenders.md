# Papyrus and script extenders (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

## In short
- Both games run the same Papyrus VM family: `.psc` source compiled to `.pex`, attached to forms through the `VMAD`
  subrecord. The VMAD layout (version, object format, scripts, properties with the same 15 type codes, Struct
  included, plus per-record fragment blocks) is the same in both xEdit definitions (**verified**, xEdit
  wbDefinitionsFO4.pas / wbDefinitionsSF1.pas). Verdict for attachment data: **carries as data** after FormID remap.
- The language grew a little in Starfield: guards (`Guard`, `LockGuard`, `TryLockGuard`, `RequiresGuard`,
  `ProtectsFunctionLogic`) and fuller structs (**verified** as compiler tokens, starfieldwiki). FO4 code that compiled
  for FO4 should be valid Starfield syntax (**supported hypothesis**; no FO4 keyword is known to be removed).
- The native API differs. FO4-only systems (Pip-Boy calls, power armor, companions' FO4 calls, vertibird events) have
  no Starfield native; Starfield adds planets, ships, credits, crew (**supported hypothesis**, from the Starfield wiki
  script pages, which are incomplete). Verdict: **take FO4 sources from the FO4 CK's script zips (on our PC since Oct 19; a player without the CK needs a
  decompiler), recompile against Starfield sources plus a shim library**.
- `.pex` cannot be loaded as-is: Starfield's compiler and `.pex` differ (new guard opcodes; Champollion had to be
  changed to read them) (**supported hypothesis**). Every FO4 script must be recompiled on the player's PC.
- SFSE 0.2.21 (game 1.16.244) has a plugin loader, a Scaleform menu interface and custom Papyrus native support
  (**verified**, SFSE whatsnew). Community plugins such as Cassiopeia Papyrus Extender register about 115 extra
  natives. Verdict: SFSE is allowed (settled), so missing natives that Papyrus cannot fake become a small SFSE plugin.

## How Fallout 4 does it
**Language** (FO4 added these over Skyrim; **verified**, falloutck "Differences from Skyrim to Fallout 4"):
structs, namespaces (`:` path separators, folder = namespace), `Var`, the `is` operator, `ScriptObject` as the root of
every script, `Const` and `Native` script flags, const properties and variables, `Group ... EndGroup`, custom events
(`RegisterForCustomEvent` / `SendCustomEvent`), remote event registration, timers (`StartTimer`, `OnTimer`, game-time
variants) instead of `OnUpdate`, `DebugOnly` / `BetaOnly` stripped by compile mode, `.ppj` project files.

**Attachment** (**verified**, xEdit wbDefinitionsFO4.pas lines 3860-4060):
- `VMAD` = Version (s16, default 6), Object Format (s16, default 2), Scripts[] (name, flags Local / Inherited /
  Removed, properties). Property types: None, Object, String, Int32, Float, Bool, Variable, Struct, and arrays 11-17.
- Fragment variants: `INFO` (OnBegin / OnEnd), `PACK` (OnBegin / OnEnd / OnChange), `PERK` (indexed fragments;
  `TERM` uses the same layout), `QUST` (fragments keyed by stage and stage index, then per-alias script lists),
  `SCEN` (OnBegin / OnEnd plus phase fragments OnStart / OnCompletion).
- Fragment scripts are generated: `QF_<QuestEDID>_<FormID>`, functions named after their editor association
  (falloutck's example: `Stage_0010`), flagged const and stored in type subfolders (**verified**, falloutck
  differences page). The B4 spike read them from `.pex` call lists, e.g. `QF_MQ102_0001CC2A` with 120 properties (**verified**,
  docs/spikes/B4-mission-anatomy.md section 1.4).

**Natives** (**verified** names on falloutck `Game_Script` and `Actor_Script`): `Game.ShowPipboyPlugin`,
`ShowPipboyBootSequence`, `EnablePipboyHDRMask`, `IsVATSPlaybackActive`, `FastTravel`, `RequestSave`,
`RequestAutoSave`, `ShowRaceMenu`, `SetInChargen`, `SetCharGenHUDMode`, `PrecacheCharGen`; Actor:
`SwitchToPowerArmor`, `IsInPowerArmor`, `SetCompanion`, `AllowCompanion`, `DisallowCompanion`, events
`OnCompanionDismiss`, `OnPlayerEnterVertibird`, `OnPlayerFireWeapon`, `OnCripple`, `OnSit`. The workshop is
mostly script-side (`WorkshopParentScript`, `WorkshopScript`) on top of a few natives (**supported hypothesis**).

**Compiler**: `Papyrus Compiler\PapyrusCompiler.exe`, flags file `Institute_Papyrus_Flags.flg` passed with `-f`,
`-i` import folders, `-o` output, `-op` optimize, `-r` release (strips DebugOnly), `-final` (strips BetaOnly)
(**verified**, falloutck Papyrus_Compiler). Vanilla sources ship with the FO4 CK as `Data\Scripts\Base.zip`,
extracted to `Data\Scripts\Source\Base` (**verified**, falloutck Papyrus_FAQs, via the coordinator). The game itself
ships 8,369 `.pex` without sources (**verified**, docs/FORMAT-GAP.md).

**F4SE**: 0.6.23 is the last build for runtime 1.10.163 (**verified**, f4se.silverlock.org). It loads native plugins
and adds Papyrus natives through its own `.pex`/`.psc` set (**supported hypothesis**; the page only says a custom
script set "must be installed"). The port does not need F4SE: FO4 is only read, never run.

## How Starfield does it
- **Language**: same core. New: guard blocks (`Guard`, `LockGuard ... EndLockGuard`, `TryLockGuard ...
  ElseTryLockGuard ... EndTryLockGuard`), `RequiresGuard`, `ProtectsFunctionLogic` (**verified**, token table from
  PCompiler.dll 4.7.0.5 on starfieldwiki Papyrus_Syntax_Reference). "Papyrus - New Features" lists guards (critical
  path single-thread protection), "almost first-class" structs, and imports of namespaces and attributes
  (**verified** as stated there; the exact struct change against FO4 is **unresolved**).
- **Attachment**: same VMAD header and property types (**verified**, xEdit wbDefinitionsSF1.pas lines 3232-3600).
  Fragment variants exist for INFO, PACK, PERK, QUST, SCEN, and new `TMLM` (terminal menu); `TERM` keeps the PERK-style
  layout (**verified**, same file, record TERM line 18155, TMLM line 18257). `NAVM` can now carry a VMAD (**verified**).
- **Natives** (Starfield wiki script pages, community-made from the shipped sources; presence **verified** there,
  absence only **supported hypothesis** because the pages are incomplete, e.g. the Actor page omits `StartCombat`,
  which the project compiled and ran):
  - Game keeps `ShowRaceMenu`, `SetInChargen`, `SetCharGenHUDMode`, `PrecacheCharGen`, `FastTravel`,
    `IsFastTravelEnabled`, `RequestSave`, `RequestAutoSave`, `IsVATSPlaybackActive` (vestigial), `GetPlayerGrabbedRef`,
    `SetLocalTime` / `GetLocalTime`, `PassTime`, even `GetCaps` / `GivePlayerCaps`. New: `GetCredits`,
    `AddPlayerOwnedShip`, `ShowGalaxyStarMapMenu`, `CreateStarbornGame`, `StartTitleSequence`, `ShowTitleSequenceMenu`,
    `AddToAvailableCrew`. No `ShowPipboyPlugin` / Pip-Boy calls listed.
  - ObjectReference keeps `AddToMap`, `EnableFastTravel`, `MoveTo`, `SetPosition`, `OnCellAttach` / `OnCellDetach`,
    `OnLoad`, `HasLocRefType`, `GetLocRefTypes`, `OnWorkshopObjectPlaced`; new `GetCurrentPlanet`, `GetWorldSpace`.
  - Actor: power armor and FO4 companion calls are not listed; `AddPassiveAffinity` is (**supported hypothesis**).
- **Sources and compiler**: vanilla sources ship in `Tools\ContentResources.zip` (**verified**, project B4). 5,034
  `.pex` in the game (**verified**). The Starfield flags file name was not found in public docs (**unresolved**; read
  it from ContentResources.zip or the CK install). CK2 runs `PapyrusCompiler.exe` from its own folder
  (**supported hypothesis**).
- **SFSE** (**verified**, github ianpatt/sfse `sfse_whatsnew.txt`): 0.2.21 for 1.16.244, Steam only; plugin manager
  (0.1.0), version-independent plugins (0.1.3), Scaleform menu plugin interface (0.1.3), task interface (0.1.6),
  "preliminary custom papyrus native function support" (0.1.1), serialization API disabled in 0.2.12 (stability),
  Address Library plugins must flag version 2 (0.2.17). Game patches have broken most plugins twice (1.14.70, a later
  compiler change). CommonLibSF and Cassiopeia Papyrus Extender (about 115 natives: inventory, input, menus,
  pathing) build on it (**verified** as described on its page). Custom Command Framework's page says scripts reach
  SFSE plugins through `Debug.ExecuteConsole()` "since SFSE lacks custom Papyrus function support"; that conflicts
  with Cassiopeia's page (**unresolved** which is current; Cassiopeia is the newer evidence).

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| VMAD on forms and refs | VMAD, same layout | data copy | remap Object property FormIDs; script names may gain our namespace |
| QUST / INFO / SCEN / PACK / PERK fragments | same variants | data copy + recompile | fragment `.pex` are rebuilt from the CK's fragment sources (decompiled only without the CK) |
| TERM fragments | TERM (PERK layout) or TMLM menu fragments | translate | FO4 terminals map to TMLM menus (see doors/activators note) |
| 8,369 `.pex` | must be Starfield `.pex` | rebuild on player PC | sources from the player's FO4 CK `Base.zip` when installed, else Champollion |
| Engine natives present in both | same name | recompile | most of what B4 used already compiled (SetStage, MoveTo, StartCombat, AddItem, RegisterForRemoteEvent) |
| Pip-Boy natives | none | script shim + SFSE menu | own Pip-Boy menu (animations-ui-and-start.md section 3) |
| Power armor natives and events | none known | rebuild | furniture + armor swap design; SFSE if frame entry needs engine help |
| VATS natives | `IsVATSPlaybackActive` remains, no VATS | rebuild or drop | Fallout systems phase |
| Companion natives (`SetCompanion`, affinity) | Starfield crew / affinity (AFFE) | translate or shim | companions.md (other writer) |
| Workshop scripts | Starfield outposts use other scripts | rebuild | fence Starfield outposts out of our world |
| Caps (`GetCaps`, `GivePlayerCaps`) | still in Game | shim | decide caps item vs credits |
| F4SE-dependent mod scripts | SFSE | out of scope | vanilla FO4 needs no F4SE |
| `Institute_Papyrus_Flags.flg` | Starfield's flags file | use Starfield's | FO4 user flags are rare in vanilla |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- **Shim library** (namespace `FO4SF:`, plain Papyrus): one script per FO4 base type method the API diff finds
  missing, with the same signature, so FO4 source compiles unchanged after a mechanical rename pass
  (`Game.ShowPipboyPlugin(...)` to `FO4SF:Game.ShowPipboyPlugin(...)`). Shims that only need data become Papyrus;
  shims that need engine state (menus, power armor camera, VATS time scale) call SFSE natives.
- **Compiler on the player's PC**: Starfield's own compiler ships with CK2, which players may be asked to install
  (settled). Caprica is the CK-free fallback, but its Starfield guard and struct support is to be checked.
- **Decompile only when needed**: if the player has the FO4 CK, read `Base.zip` sources directly (cleaner than
  decompiler output). Champollion supports Starfield since 1.3.1 and lists FO4 support in its README; its Starfield
  guard syntax was a guess marked `;***` (**verified**, Champollion releases page).
- **Save safety**: Papyrus state is saved (variables, properties, running stacks); renaming or removing scripts later
  drops data with log warnings (**verified** for FO4, falloutck Save File Notes (Papyrus)). Freeze script and property
  names before players keep saves.

## Port status and links
- B4 listed the scripts of the first mission and confirmed which natives compiled and ran
  ([B4-mission-anatomy.md](../../spikes/B4-mission-anatomy.md)); the route (decompile, recompile, shim `FO4SF_`) is in
  [../next-phase/npcs-ai-factions-dialogue-quests.md](../next-phase/npcs-ai-factions-dialogue-quests.md) section 7.
- The Pip-Boy and SFSE menu routes are in
  [../next-phase/animations-ui-and-start.md](../next-phase/animations-ui-and-start.md) section 3.
- Console bridges already used: `cf` (CallFunction) and `cgf` (CallGlobalFunction) found in Starfield.exe
  (**verified** strings, docs/ai/research-log.md 2026-10-14; whether `cgf` reaches every native is **unresolved**).
- PLAN.md pins SFSE 0.2.21 with Starfield 1.16.244.

## PC probe results (2026-10-19, verified)

`scripts/research/engine_probe.py` (commit f799f60) ran read-only on the owner's PC (PC job 7). It reads Starfield's
`Tools\ContentResources.zip` and looks for FO4 sources, and records names only. Output:
`D:\Modding\research\engine_probe\engine_probe.json` (704,457 bytes).

- **Starfield ships 5,029 `.psc` sources** in ContentResources.zip. No `*.flg` file sits in `Starfield\Tools` itself
  (the flags file is elsewhere, likely inside the zip or the CK's script folder: **unresolved**).
- **Starfield scripts present:** `CompanionActorScript`, `SQ_CompanionsScript`, `SQ_CrewScript`,
  `SQ_FollowersScript`, `MQ101Script`, `InputEnableLayer`. **Absent:** `FollowersScript`, `WorkshopParentScript`,
  `WorkshopScript`, `PipboyScript`, `UI`, `AffinityEventScript`.
- **Declared in Starfield's core scripts** (Actor, Game, ObjectReference, Quest, ReferenceAlias, Form, Utility,
  Debug, ScriptObject, ActiveMagicEffect, Weapon, Armor, Perk, Location, Cell, Math, CompanionActorScript):
  `SwitchToPowerArmor`, `SetRace`, `RewardPlayerXP`, `GetPlayerFollowers`, `SetPlayerTeammate`, `IsPlayerTeammate`,
  `SetCommandState`, `ShowRaceMenu`, `SetInChargen`, `FadeOutGame`, `FastTravel`, `PlayIdle`,
  `PlaySubGraphAnimation`, `ChangeAnimArchetype`, `SetSubGraphFloatVariable`, `Say`, `SayCustom`, `AddPerk`,
  `GetValue`/`SetValue`/`ModValue`, `EvaluatePackage`, `StartCombat`, `SetStage`, `SetObjectiveDisplayed`,
  `ForceRefTo`, `MoveTo`, `SetPosition`, `PlaceAtMe`, `GetCurrentGameTime`, `RequestAutoSave`.
- **Not declared there:** `IsInPowerArmor`, `IsPipboyOpen`, `ShowPipboyPlugin`, `OpenWorkshopSettlementMenu`,
  `StartVATS`, `IsInVATS`, `IsInMenuMode`, `IsMenuOpen`, `SendAffinityEvent`, `TryToModAffinity`. (Caveat:
  `SendStoryEvent` and `SetTimeScale` were also not found, but `SendStoryEvent` is a Keyword function and time scale
  is a global, and neither script was in the scanned set; they say nothing.)
- **FO4 sources (after the owner installed the FO4 Creation Kit, job 15)**: the CK put them in
  `D:\SteamLibrary\steamapps\common\Fallout 4\Data\Scripts\Source\(name)\(name).zip`: Base 7,854 `.psc`, DLC01
  483, DLC02 43, DLC03 830, DLC04 908, DLC05 40, DLC06 92, CreationClub 32. Decompiling vanilla FO4 scripts is no longer
  needed.

### The native gap, script by script (PC probe job 15, verified)

Function and event names each FO4 core script declares, compared with Starfield's script of the same name (FO4 CK
sources vs ContentResources.zip, commit 797dde5). "FO4-only" is what a shim must supply or a converter must rewrite.

| script | shared | FO4-only | SF-only | the FO4-only names |
|---|---:|---:|---:|---|
| Actor | 231 | 28 | 51 | AddSpell, DispelSpell, GetActorBase (likely renamed in SF), AllowCompanion, DisallowCompanion, SetCompanion, SetAvailableToBeCompanion, FollowerFollow, FollowerWait, FollowerSetDistanceNear/Medium/Far, Dismember, IsDismembered, IsInPowerArmor, SetAnimArchetype{Confident, Depressed, Elderly, Friendly, Irritated, Nervous, Neutral}, SetDogAnimArchetype{Agitated, Alert, Neutral, Playful}, SetEyeTexture, StartCannibal |
| ObjectReference | 256 | 19 | 124 | DeleteWhenAble, GetEncounterZone, GetLinkedRefChildren, getLinkedRefArray, IsActivateChild, MakeRadioReceiver, OnHolotapeChatter, OnHolotapePlay, OnWorkshopObjectDestroyed, OnWorkshopObjectRepaired, OpenWorkshopSettlementMenu(Ex), RaidTargetsAvailable, RecalculateResources, RemoveComponents, SellItem, StoreInWorkshop, TetherToHorse, WaitForWorkshopResourceRecalc |
| Game | 104 | 10 | 57 | EnablePipboyHDRMask, ForceDisableSSRGodraysDirLight, GetCommonProperties, InitializeMarkerDistances, SetInsideMemoryHUDMode, ShowPerkVaultBoyOnHUD, ShowPipboyBootSequence, ShowPipboyPlugin, ShowSPECIALMenu, ShowTrainingMenu |
| ActiveMagicEffect, ReferenceAlias | 84, 101 | 4 each | 67, 77 | OnHolotapeChatter, OnHolotapePlay, OnWorkshopObjectDestroyed, OnWorkshopObjectRepaired |
| Location | 16 | 4 | 22 | HasEverBeenCleared, IsCleared, OnLocationCleared, SetCleared (Starfield's concept is "explored", as in the condition functions) |
| ScriptObject | 76 | 3 | 30 | OnLooksMenuEvent, RegisterForLooksMenuEvent, UnregisterForLooksMenuEvent |
| Quest | 57 | 2 | 25 | OnStoryClearLocation, ResetSpeechChallenges |
| Utility | 28 | 2 | 11 | IsInMenuMode, WaitMenuMode |
| Debug | 34 | 1 | 5 | SetFootIK |
| Cell, Form, Math, Perk, Weapon | 12, 7, 15, 1, 2 | 0 | 3, 2, 10, 0, 0 | none |

Game scripts, not engine scripts: FO4's `FollowersScript` (98 functions: companion slots, Dogmeat, affinity events,
situation awareness, loitering, teleport, vertibird events) has **no** Starfield counterpart, and FO4's
`CompanionActorScript` shares only 2 of its 56 names with Starfield's script of the same name (FO4's 54 are the affinity
thresholds, romance and murder-session logic). Both are ported as our own scripts under our prefix.

**What it means:** the engine-level gap is about **77 names** across the core scripts, and they cluster in the systems
the reference already marks as rebuilds: workshop (11), Pip-Boy and FO4 menus (8), companions and followers (8),
holotapes (2 events on 4 scripts), animation archetypes (11), dismemberment (2), power armor (1), cleared locations
(4), menu mode (2). Everything else a FO4 script calls on these classes exists in Starfield under the same name. Names
only: argument lists can still differ (**unresolved**; the next probe can compare signatures). `IsInVATS`, `StartVATS`,
`IsPipboyOpen`, `IsMenuOpen` and `SetTimeScale` exist in neither game's core scripts (FO4's menu checks live in F4SE's
`UI` script, outside vanilla).

## Open questions and cheap checks
- Native diff: done by name (table above). Next: compare signatures, and count call sites of the ~77 names in FO4's
  7,854 base sources.
- Starfield flags file: none in `Tools` (job 15); check inside ContentResources.zip and the CK2 install.
- Compile one FO4 quest fragment (`QF_MQ102_0001CC2A`) against Starfield sources; record each error.
- Does the Starfield compiler accept FO4 `Var`, `CustomEvent`, `is` unchanged? One synthetic `.psc` test.
- Does SFSE 0.2.21 register custom natives reliably? Load Cassiopeia and call one native from a test quest.
- Answered (job 15): Starfield's `Actor` declares `SwitchToPowerArmor` but not `IsInPowerArmor` or `SetCompanion`.
- Champollion on 20 FO4 `.pex` vs the CK `Base.zip` sources: diff to measure decompiler fidelity.

## Sources
- xEdit definitions dev-4.1.6: wbDefinitionsFO4.pas, wbDefinitionsSF1.pas ([TES5Edit](https://github.com/TES5Edit/TES5Edit)).
- [Differences from Skyrim to Fallout 4 (falloutck)](https://falloutck.uesp.net/wiki/Differences_from_Skyrim_to_Institute)
- [Papyrus Compiler (falloutck)](https://falloutck.uesp.net/wiki/Papyrus_Compiler); [Papyrus FAQs (falloutck)](https://falloutck.uesp.net/wiki/Papyrus_FAQs)
- [Game Script (falloutck)](https://falloutck.uesp.net/wiki/Game_Script); [Actor Script (falloutck)](https://falloutck.uesp.net/wiki/Actor_Script)
- [Save File Notes (Papyrus) (falloutck)](https://falloutck.uesp.net/wiki/Save_File_Notes_(Papyrus))
- [Starfield Mod: Papyrus Syntax Reference](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Papyrus_Syntax_Reference); [Papyrus - New Features](https://starfieldwiki.net/wiki/Starfield_Mod:Papyrus_-_New_Features)
- [Starfield Mod: Script-Game](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Game); [Script-Actor](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Actor); [Script-ObjectReference](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-ObjectReference)
- [SFSE repository](https://github.com/ianpatt/sfse), [sfse_whatsnew.txt](https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt); [SFSE on Nexus](https://www.nexusmods.com/starfield/mods/106)
- [F4SE](https://f4se.silverlock.org/)
- [Champollion releases](https://github.com/Orvid/Champollion/releases)
- [Cassiopeia Papyrus Extender (mirror page)](https://allmods.net/starfield-mods/starfield-miscellaneous/cassiopeia-papyrus-extender-v1-1/); [Custom Command Framework](https://www.nexusmods.com/starfield/mods/9779)
