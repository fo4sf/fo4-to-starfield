# FO4 systems internals: research findings and question framework

Wave 3, area fo4-systems-internals. Author: Claude (research agent), 2026-10-19. Labels: **verified** (read on the
source page or in a project file), **supported hypothesis** (evidence, not confirmed), **unresolved**.

Scope: how Fallout 4's five big scripted systems are built (workshop rules, followers, radio, power armor, Survival),
what each rebuild on Starfield must reproduce, which of the FO4-only Papyrus names from
`engine-mechanics/papyrus-and-script-extenders.md` ("The native gap, script by script", called **the gap table**
below) each system touches, what can stay Papyrus-only, and what needs SFSE. It builds on, and does not repeat:
`engine-mechanics/workshop-and-settlements.md`, `companions.md`, `radio-music-sound.md`, `power-armor.md`,
`health-damage-effects.md`, and the wave 1/2 notes `workshop-items-economy.md`, `companions-ai-factions-combat.md`,
`animation-audio-physics.md`, `character-systems.md`, `findings/fallout-systems-precedents.md` (which already cover the
Starfield-side mods: radio DLLs, survival mods, Command NPCs, Amazing Follower Tweaks, Sim Settlements status).

Method note: GitHub API access to `kinggath/WorkshopFramework` was not enabled in this session, so the Workshop
Framework detail comes from its wiki (read through the github-wiki-see.page mirror) and the SS2 wiki. FO4's vanilla
sources (`Base.zip` from the FO4 CK) are on the owner's PC only; nothing here is copied from them. Where a function
name is given for a vanilla script, the source is a public forum post or wiki page, cited inline.

## What the community and tools offer today

### Workshop rules layer (FO4)
- **Four vanilla scripts carry the rules**: `WorkshopParentScript` (the `WorkshopParent` quest, the master script),
  `WorkshopScript` (on each workbench ref), `WorkshopObjectScript` (on each resource object), `WorkshopNPCScript` (on
  settlers). SKKmods calls `WorkshopParentScript` "complex, fragile and easily broken". **verified**
  (https://nexusmods.com/fallout4/articles/2298). This upgrades the "supported hypothesis" on the script names in
  workshop-and-settlements.md.
- **Settlement registration is data plus one script**: a run-once, start-game-enabled quest with a ref collection alias
  `WorkshopsCollection` (forced to the workbench ref, or filled by Location Alias Reference with ref type
  `WorkshopRefType`), alias inventory `WorkshopInitialResources_Settlement`, and the script `WorkshopAddLocationsScript`
  (properties `WorkshopParent`, `WorkshopsCollection`) plus `DefaultQuestShutdownScript`. The location needs keywords
  `LocTypeWorkshop`, `LocTypeWorkshopSettlement` ("VITAL for ResetWorkshop()"), `LocTypeSettlement`,
  `LocTypeClearable`, ref types `LocationCenterMarker`, `LocationEdgeMarker`, `MapMarkerRefType`, `WorkshopRefType`,
  an encounter zone with the Workshop flag and "Never resets". The workbench links: `WorkshopLinkCenter`,
  `WorkshopLinkContainer`, `WorkshopLinkSandbox`, `WorkshopLinkSpawn`; build area trigger linked by
  `WorkshopLinkedPrimitive`; optional border `WorkshopLinkedBuildAreaEdge`; attack markers (`LocationEdgeMarker` refs)
  linked by `WorkshopLinkAttackMarker`, "used by Workshop*Attack and WorkshopRadioBeaconRecruit spawns"; every
  resource object links to the workbench with `WorkshopItemKeyword`. Ownership via a `WorkshopSetOwnedTrigger` or
  `WorkshopScript.EnableAutomaticPlayerOwnership`; setting `OwnedByPlayer` directly "will cause ongoing registration and
  resource issues". Adding `LocTypeWorkshopSettlement` at runtime triggers `ResetWorkshop()`, so settlements cannot
  practically be created or moved at runtime. **verified** (same article). This is the converter's checklist for every
  FO4 settlement.
- **Attack chance constants** on `WorkshopScript`: `attackChanceBase = 0.05`, `attackChanceResourceMult = 0.05`,
  `attackChanceSafetyMult = 0.01`, `attackChancePopulationMult = 0.02`, `minDaysSinceLastAttack = 1.0` (all `const`);
  the daily check is `CheckForAttacks()` on `WorkshopScript`, gated by `AllowAttacks` on `WorkshopParent`; a
  `pWorkshopAttackScript.attackDelayGameTime` property exists; `WorkshopParentScript.TriggerAttack` can be called from
  the console. **verified** as quoted from posted source and console examples
  (https://forums.nexusmods.com/topic/6395706-need-help-getting-more-settlement-attacks,
  https://forums.nexusmods.com/topic/4929630-how-can-i-test-whether-ive-successfully-disabled-settlement-attacks,
  https://www.nexusmods.com/fallout4/mods/38738). The exact formula (how the terms combine, clamping) is
  **unresolved**: the forum poster's arithmetic is not confirmed.
- **Settler API surface** seen in public mod code: `WorkshopParentScript.AddActorToWorkshopPlayerChoice`,
  `AddPermanentActorToWorkshopPlayerChoice`, `UnassignActor(..., bRemoveFromWorkshop, bSendUnassignEvent)`,
  `GetWorkshopActors`, property `CaravanActorAliases` (provisioners live in aliases, not in `bIsWorker`);
  `WorkshopNPCScript.SetWorkshop`, `GetWorkshopID()` (mirrors the `workshopIDActorValue` actor value), `bIsWorker`,
  `bWorkshopStatusOn`, `bWork24Hours`; actor value `WorkshopRatingPopulation`; faction `WorkshopNPCFaction`; package
  `WorkshopMasterPackage`; keyword `WorkshopActorType`. **verified** as names used in posts
  (https://forums.nexusmods.com/topic/13510492-assigning-npc-to-workshop-through-dialogue,
  https://forums.nexusmods.com/topic/6892821-is-an-npc-assigned-to-a-workshop,
  https://forums.nexusmods.com/topic/10180778-shock-collars-change-bwork24hours-to-true,
  https://forums.nexusmods.com/topic/12810282-getting-thisworkshop-settlers-into-an-array).
- **Vanilla custom events on `WorkshopParentScript`** (names from Workshop Framework's list of events it extended):
  `WorkshopActorUnassigned`, `WorkshopActorAssignedToWork`, `WorkshopEnterMenu`; Workshop Framework adds
  `WorkshopRemoveActor`, `WorkshopFramework:MainQuest.PlayerEnteredSettlement` / `PlayerExitedSettlement`,
  `WorkshopFramework:WorkshopProductionManager.NotEnoughResources`. **verified**
  (https://github-wiki-see.page/m/kinggath/WorkshopFramework/wiki/New-or-Improved-Events). So FO4 already exposes its
  rules layer through Papyrus `CustomEvent`s, a pattern our rebuild can copy.
- **Native workshop hooks used by the rules** (falloutck ObjectReference page): `CanProduceForWorkshop()` native
  (false if unpowered, destroyed, or a required worker is missing, wounded or dead; keywords `WorkshopCanBePowered`,
  `WorkshopWorkObject`; valid only while the workshop is loaded), `GetWorkshopResourceDamage`, `RemoveComponents`,
  `RaidTargetsAvailable`, events `OnWorkshopMode`, `OnWorkshopNPCTransfer(Location, Keyword)`, `OnPowerOn`,
  `OnPowerOff`, `OnWorkshopObjectPlaced/Moved/Grabbed/Destroyed/Repaired`. **verified**
  (https://falloutck.uesp.net/wiki/ObjectReference_Script,
  https://falloutck.uesp.net/wiki/CanProduceForWorkshop_-_ObjectReference).
- **The caravan (supply line) and vassal menus are native**: `OpenWorkshopSettlementMenu(Keyword akActionKW, Message
  astrConfirm, Location aLocToHighlight)` native opens the "Workshop Caravan" submenu for a workshop NPC and returns the
  chosen Location (example passes `WorkshopAssignCaravan_DO`); `OpenWorkshopSettlementMenuEx` and
  `RaidTargetsAvailable` (native) add include/exclude keyword lists, `abOnlyOwnedWorkshops`,
  `abOnlyPotentialVassalSettlements` (Nuka-World raider outposts). **verified**
  (https://falloutck.uesp.net/wiki/OpenWorkshopSettlementMenu_-_ObjectReference,
  https://falloutck.uesp.net/wiki/RaidTargetsAvailable_-_ObjectReference). Provisioner travel itself is AI packages
  plus `CaravanActorAliases` (**supported hypothesis**: package detail not documented publicly; SKK lists "AI travel
  packages for Provisioners, Patrols, and Attacks", https://www.nexusmods.com/fallout4/mods/38738).
- **Starfield's ObjectReference keeps most workshop natives**: `GetWorkshop`, `GetWorkshopOwnedObjects`,
  `GetWorkshopResourceObjects`, `GetWorkshopResourceDamage`, `CanProduceForWorkshop`, `SetWorkshopState`,
  `StartWorkshop`, `ShowWorkshopBuilderMenu`, `ShowWorkshopTargetMenu`, events `OnWorkshopMode`,
  `OnWorkshopObjectPlaced/Moved/Grabbed`, `OnWorkshopObjectRemoved` (replaces Destroyed), `OnWorkshopNPCTransfer`,
  `OnWorkshopOutputLink`, `OnWorkshopCargoLinkChanged`, `OnWorkshopFlyCam`, power `IsPowered`, `HasSharedPowerGrid`,
  `OnPowerOn/Off`, `OnOutpostItemPowerOn/Off`, components `GetComponentCount`, `RemoveItemByComponent`. **verified** as
  listed on the community page (https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-ObjectReference). This
  answers most of next-phase check P4: only `OnWorkshopObjectRepaired` has no visible counterpart.
- **Workshop Framework (WF)** is "a redesign of the FO4 Workshop Scripts" (GitHub description, 184 commits, folder
  `Scripts/Source/User`; licence not shown on the page). Design rules from its wiki: keep vanilla property names and
  function signatures so existing mods keep working; prefer events and variable changes over script hooks; favour
  speed over memory; "Override Events" plus globals let a mod switch off a vanilla behaviour and supply its own; simple
  global API functions in `WSFW_API.psc` that need no editor properties; stable signatures, with new functions added
  and old ones redirected to protect saves. **verified** (https://github.com/kinggath/WorkshopFramework,
  https://github-wiki-see.page/m/kinggath/WorkshopFramework/wiki/Development-Design-Notes,
  https://github-wiki-see.page/m/kinggath/WorkshopFramework/wiki/API). Formula overrides work at three levels: a
  global (all settlements), a workshop resource object (built bonus), or per settlement
  (`workshopRef.maxStoredWaterBase = 10` plus `workshopRef.bUseGlobalmaxStoredWaterBase = false`). **verified**
  (https://github-wiki-see.page/m/kinggath/WorkshopFramework/wiki/Editing-Workshop-Formulas). A Papyrus threading
  engine (`WorkshopFramework:PlaceObjectManager`, `ObjectRefs:Thread_ScrapObject`, `ObjectRefs:Thread_CreateObject`)
  handles bulk object work; its docs are a placeholder. **verified**
  (https://github-wiki-see.page/m/kinggath/WorkshopFramework/wiki/Using-the-Threading-Engine). Several wiki pages
  (Assault Manager, Control Manager) are "TODO". **verified**. F4SE is optional: the wrapper only detects F4SE (quest
  `WSFW_F4SE`), and only the power grid scan, repair and destroy tools require it. **verified**
  (https://github-wiki-see.page/m/kinggath/WorkshopFramework/wiki/F4SE-Wrapper-(WIP),
  https://wiki.simsettlements2.com/gameplay/basics/workshop-framework).
- **Sim Settlements 2 add-on registration is pure data**: a constant Global `yourPrefix_Version`, a MiscItem copied
  from `SS2_Template_AddonConfig` (properties `MyVersionNumber`, `sAddonFilename`, `MyItems` = FormLists whose first
  entry is a keyword telling SS2 where content goes), and a controller quest copied from `SS2_AddonTemplate` with
  script `SimSettlementsV2:quests:AddonPack` (property `MyAddonConfig`). Bumping the Global makes SS2 rescan; unchanged
  saves skip registration. **verified** (https://wiki.simsettlements2.com/CreateAddons/Addon-Registration). SS2's
  content tools include a building-plan import tool and a City Plan web tool that needs no CK or xEdit. **verified**
  (https://wiki.simsettlements2.com/CreateAddons). SS2's permissions forbid conversion (already recorded in
  workshop-items-economy.md); only its architecture is a model, never its files.

### Followers (FO4)
- `Actor.SetCompanion(bool SetCompanion = true, FillCompanionAlias = true)`, `AllowCompanion(bool
  MakeCompanionIfNoneCurrently = true, bool ForceCompanion = false)`, `FollowerFollow()` (works only "if this actor is
  running a package based on FollowPlayer template") are documented without the `native` keyword, while pages for true
  natives (for example `OpenWorkshopSettlementMenu`, `MakeRadioReceiver`, `CanProduceForWorkshop`) show it.
  **verified** for the page text (https://falloutck.uesp.net/wiki/SetCompanion_-_Actor,
  https://falloutck.uesp.net/wiki/AllowCompanion_-_Actor, https://falloutck.uesp.net/wiki/FollowerFollow_-_Actor).
  **Supported hypothesis**: several of the gap table's 8 companion names are Papyrus wrappers in FO4's `Actor.psc`
  that call `FollowersScript`, so they are not engine natives at all and can be re-provided as plain Papyrus. A grep of
  `Actor.psc` in Base.zip for `native` on those lines settles it (question G1).
- Affinity mechanics: `CA_Affinity` hidden actor value; size scalars `CA_Size_Small` 0.5 / `CA_Size_Normal` 1 /
  `CA_Size_Large` 1.5; the multiplier logic is in `TryToModAffinity` in `CompanionActorScript.psc`; passive gain
  `40 - 0.033 x affinity` every 10 minutes of following when at least 1 XP was earned; +3% bump on recruit; tier stalls
  (MacCready, Curie at 499; Cait, Danse at 999) until personal quests; perks permanent at 1000; hatred at -1000 is a
  permanent departure; Preston drops to hated in "Home Sweet Home". **supported hypothesis** (Fallout wiki,
  https://fallout.fandom.com/wiki/Affinity). The passive-gain properties `WithPlayerBaseAffinityGainPerTick` (40.0),
  `WithPlayerCurrentAffinityMult` (0.033), function `GetWithPlayerAffinityGain()`, faction `CurrentCompanion`, and a
  `Followers.CA_Affinity` property are visible in a UFO4P-based mod's description. **verified** as quoted
  (https://www.nexusmods.com/fallout4/mods/77021).
- Reaction routing: `CompanionActorScript` on each companion holds `AffinitySettings` / `EventData_Array` (struct:
  event keyword, `Disposition_Global` such as `CA_Event_Likes`, `Message_to_Display` such as `CA_Cait_Likes`); topic
  infos carry `CA_DialogueBump_TopicInfoScript` and other `CA_...Script` fragments; custom keywords like
  `CA_CustomEvent_CaitLikes` and `CA__CustomEvent_MinSettlementHelp`. **verified** as names in the thread
  (https://forums.nexusmods.com/topic/12870213-creation-kit-how-to-make-a-companion-use-a-different-affinity-keyword).
  The sender side (which script broadcasts a `CA_Event_*` keyword to the active companions) is **unresolved**
  publicly; companions.md and the probe place it in `FollowersScript` (98 functions).
- Community frameworks (AFT, Everyone's Best Friend, Unlimited Companion Framework) all work by replacing
  `FollowersScript.pex` and are mutually incompatible. **verified** in companions-ai-factions-combat.md (wave 1). Same
  lesson as workshop: overwriting one vanilla god-script is the conflict source.

### Radio (FO4)
- `ObjectReference.MakeRadioReceiver(float afFrequency, float afVolume = 1.0, OutputModel aOverrideModel = None, bool
  abActive = true, bool abNoStatic = false) native`; default model from default object `WorldRadioOutputModel_DO`;
  activating an Activator receiver toggles it. **verified** (https://falloutck.uesp.net/wiki/MakeRadioReceiver_-_ObjectReference).
  It is in the gap table (missing in Starfield).
- Starfield still has radio receiver and player radio functions: ObjectReference `SetRadioOn`, `SetRadioFrequency`,
  `SetRadioVolume`, `GetRadioFrequency`, `GetRadioVolume`, `IsRadioOn`, event `OnPipboyRadioDetection`; Game
  `GetPlayerRadioFrequency`, `IsPlayerInRadioRange`, `IsPlayerRadioOn`, `SetPlayerRadioFrequency`,
  `TurnPlayerRadioOn`, `IsPlayerListening`. **verified** as listed
  (https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-ObjectReference,
  https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Game). **Supported hypothesis**: the engine radio
  (transmitter range, receiver, player radio) survives in CE2 code, and only `MakeRadioReceiver` (turning a non-radio
  ref into a receiver at runtime) is gone; placed ACTI with RADR data would not need it. Whether Starfield's player
  radio has any UI is **unresolved** (the Pip-Boy radio tab is our UI rebuild anyway).
- Station loop structure and the "radio silence" restart: a scene with a timer phase, an empty "SongSelect" phase,
  one phase per song gated by `GetVMQuestVariable CurrentSong == N`, `LastSongPlayed01..03 !=` anti-repeat
  conditions, host lines by `CurrentLine` / `LastLinePlayed[]`, a final phase that restarts the scene, and a
  `RestartScene` timer (credited to Glitchfinder) that restarts a stopped scene; vanilla's value is 900 s. **verified**
  (https://www.nexusmods.com/fallout4/mods/101520). Which vanilla quest and script own the 900 s value and the cause of
  the silence is **unresolved**; an older thread reports pauses and guesses empty topics, with no confirmed fix
  (https://forums.nexusmods.com/topic/4758600-question-custom-radio-station-silences-or-pauses).

### Power armor (FO4)
- Fusion core drain is tuned by game settings: `fPowerArmorPowerDrainPerActionPoint`,
  `fPowerArmorPowerDrainPerSecondRunning`, `fPowerArmorPowerDrainPerJump`, `fPowerArmorPowerDrainPerMeleeAttack`,
  `fPowerArmorPowerDrainPerImpactLand`, applied by a mod on leaving the start menu. **verified** as names on the page
  (https://www.nexusmods.com/fallout4/mods/85638). **Supported hypothesis**: the drain is engine code reading GMSTs, not
  Papyrus, so on Starfield it is a full script rebuild unless those GMSTs and the code behind them survive (check
  Starfield.esm GMST editor ids; question P2).
- `IsInPowerArmor` is documented as `bool Function IsInPowerArmor()` with no `native` keyword. **verified** page text
  (https://falloutck.uesp.net/wiki/IsInPowerArmor_-_Actor). Whether it is a wrapper (for example over a keyword or
  furniture check) is **unresolved**; on Starfield it can be shimmed as a keyword or faction check on our own PA state.
- Custom PA needs ARMA, ARMO, MISC, OMOD per piece plus MSWP, and the armor must show on both the furniture and the "PA
  race". **verified** (https://forums.nexusmods.com/topic/6308206-implementing-custom-power-armour). The PA race
  editor id is still **unresolved** (power-armor.md lists the xEdit check).

### Survival (FO4)
- The manager is the quest `HC_Manager` with `HC_ManagerScript.pex`; sleep-duration caps for mattresses and sleeping
  bags are "a couple conditional checks" and constants in it. **verified**
  (https://www.nexusmods.com/fallout4/mods/19162). This upgrades the "likely an `HC_`-prefixed manager quest" in
  health-damage-effects.md.
- Survival rules are loaded by the Hardcore Manager Script from a "Hardcore Rules Formlist"; removing the "No Fast
  Travel" rule from that list stops the script applying it, and an existing survival save keeps its running script.
  **verified** (https://www.nexusmods.com/fallout4/mods/11933). So the fast travel block is script data, not a hard
  engine rule (**supported hypothesis** on how the rule is applied: likely a GMST or `Game.EnableFastTravel` call).
- Other vanilla pieces named publicly: perk `HC_FillWaterBottlePerk`; game setting `bEnableConsoleMenuDuringSurvival`
  (engine-level survival console block). **verified** (https://www.nexusmods.com/fallout4/mods/46306). The
  bed-only-save rule's implementation is **unresolved** (no public page explains it).
- Starfield Game script has `RequestSave`, `RequestAutoSave`, `RequestSaveByName`, `FastTravel`,
  `IsFastTravelEnabled`, `IsFastTravelControlsEnabled`, `GetDifficulty` (its docs mention survival/hardcore),
  `GetGameSetting*`. **verified** (https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Game). Whether a save
  block exists (rather than just requesting saves) is **unresolved**.

## Precedents and lessons
- **One god-script per system is FO4's design, and the community's biggest pain.** `WorkshopParentScript` and
  `FollowersScript` are the files every big mod replaces; WF and SS2 exist to stop that, and companion frameworks still
  clash. **verified** (SKK article 2298; WF design notes; wave 1 notes). Lesson: our rebuild ships its own scripts
  under our prefix with a public API from day one; nothing named like vanilla.
- **WF's extension model is the template**: globals for defaults, per-settlement override flags
  (`bUseGlobal<name>`), resource objects for bonuses, `CustomEvent`s that report every state change, "override events"
  that let an add-on switch off a built-in rule, stable signatures. **verified** (WF wiki). Cheap to copy in Papyrus.
- **SS2's registration model is the template for content packs**: a controller quest, one config Misc, FormLists,
  and a version Global so saves rescan only when an add-on changes. **verified** (SS2 wiki). Useful for DLC
  (Far Harbor, Nuka-World, workshop DLC) as add-ons to our own framework.
- **Registration is static in FO4**: settlements cannot be created or moved at runtime because `ResetWorkshop()` fires
  on keyword change. **verified** (SKK 2298). Lesson: our converter must emit settlement registration as data in the
  plugin, not at runtime.
- **Script load is the scaling limit**: WF exposes a Max Threads setting (10 to 50) because script-heavy load
  orders become unstable; SS2 flags lag near dense settlements. **verified** (SS2 wiki, workshop-items-economy.md).
  Lesson: budget Papyrus threads per daily tick; FO4's daily update iterates every settlement.
- **Power grid corruption needed F4SE to fix in FO4** (WF's scan/repair tools require F4SE). **verified** (SS2 wiki
  WF page). Lesson: if we map FO4 wiring to Starfield's outpost power (`HasSharedPowerGrid`), test grid persistence
  early.
- **Radio stations need a watchdog** (the 900 s restart) even in vanilla. **verified** (Nexus FO4 101520). Lesson:
  whatever plays radio on Starfield (scene or SFSE DLL) needs a restart watchdog and a save/load re-arm.
- **Survival as rules in a form list is mod-friendly**: removing one rule entry disables it. **verified** (Nexus FO4
  11933). Lesson: keep the same "rule list" shape so players toggle rules (pairs with GPOF options in
  character-systems.md V3).

## Possibilities and hard limits in CE2
- **Workshop: Papyrus-only is realistic.** The rules layer is Papyrus in FO4 already; Starfield keeps the workshop
  ref model, placement events (Removed in place of Destroyed), resource object queries, power events and the workshop
  condition functions. **supported hypothesis** (Starfield wiki function list plus xEdit condition table in
  workshop-and-settlements.md). Gaps: `OnWorkshopObjectRepaired` (shim: our own repair activation),
  `RecalculateResources` / `WaitForWorkshopResourceRecalc` (shim: our own Papyrus rating sum over
  `GetWorkshopResourceObjects`), `RemoveComponents` (shim: `RemoveItemByComponent`), `StoreInWorkshop` (shim: move to
  the workshop container and disable), `OpenWorkshopSettlementMenu(Ex)` / `RaidTargetsAvailable` (no native menu:
  rebuild as a MESG or list menu, or SFSE UI). **supported hypothesis** for each shim, untested.
- **Settler actor values**: FO4 uses actor values for ratings (`WorkshopRatingPopulation` and siblings, read with
  `GetValue` on the workshop ref). Starfield has AVIF and workshop resource AVs (IRES `NAM1`). **supported
  hypothesis** that our own AVIFs on the workbench ref work the same; check by script test.
- **Followers: Papyrus-only for the framework, with one open engine question.** Starfield keeps teammate state,
  `SetPlayerTeammate`, `SetCommandState`, `GetPlayerFollowers`, `IsCommandedActor`, `AddPassiveAffinity`,
  `ChangeAnimArchetype(Keyword)` (verified names: PC probe and https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Actor).
  `SetAnimArchetype*` (11 FO4 names) map to `ChangeAnimArchetype` with a keyword (**supported hypothesis**; needs the
  FO4 archetype keywords as data). Command mode UI is the only piece that might need SFSE (companions-ai-factions-combat.md C1).
- **Radio: no native gap except `MakeRadioReceiver`.** Starfield keeps receivers and player radio natives (verified
  names). Hard limit: audio must be Wwise or an SFSE DLL (radio-music-sound.md). Possibility: DJ scenes with Radio
  actions stay data if the TACT or an NPC speaker plays in CE2 (unresolved, radio note).
- **Power armor: mostly not a native gap but an engine-feature gap.** Only `IsInPowerArmor` is missing by name;
  `SwitchToPowerArmor` is declared in Starfield, but the furniture flag, the PA race swap and the GMST-driven drain are
  engine features with no evidence of surviving. Papyrus can do: furniture activation, equip pieces, AV-based core
  charge with a timer, speed and damage effects. SFSE needed for: a PA HUD, a true behaviour graph swap if
  `SwitchToPowerArmor` or `SetRace` do not work, per-action drain hooks (AP spend, jump, melee) if Papyrus events do
  not cover them. **supported hypothesis**.
- **Survival: Papyrus-only except saving.** Needs, diseases and rules are script plus spells; Starfield has
  afflictions and GPOF. Hard limit candidates: blocking manual saves (Starfield Game script shows requesting saves,
  not blocking them; **unresolved**) and `Utility.IsInMenuMode` / `WaitMenuMode` (in the gap table; shim with
  `UI`-free timers or game-time timers). `Actor.AddSpell` / `DispelSpell` are FO4-only names on `Actor` in the gap table
  (**unresolved** whether Starfield moved them to another script; every disease and need effect depends on it).

## The five systems: what each rebuild must reproduce

Gap-table matching below is by name: a system "calls" a missing name when the name belongs to its feature area. That
is a **supported hypothesis** until the Base.zip grep (question G1) lists real call sites per script.

### 1. Workshop rules layer
| part | FO4 scripts and records | missing names it needs (gap table) | Starfield, Papyrus-only | needs SFSE |
|---|---|---|---|---|
| registration | `WorkshopAddLocationsScript` quest, `WorkshopsCollection`, LocTypeWorkshop* keywords, link keywords, ECZN Workshop flag | `Location.IsCleared`, `HasEverBeenCleared`, `SetCleared`, `OnLocationCleared`, `Quest.OnStoryClearLocation` (clear-to-own) | own registration quest per settlement emitted by the converter; "cleared" via our own flag or Starfield's "explored" concept | no |
| ratings and daily update | `WorkshopParentScript`, `WorkshopScript` (daily update, ratings AVs, happiness, vendor income, recruitment roll) | `RecalculateResources`, `WaitForWorkshopResourceRecalc` | own rating sum over `GetWorkshopResourceObjects` + `CanProduceForWorkshop`; FO4 numbers read from the user's files | no |
| objects | `WorkshopObjectScript` (resource ratings, worker assignment, power) | `OnWorkshopObjectDestroyed`, `OnWorkshopObjectRepaired` (on 4 scripts), `StoreInWorkshop`, `RemoveComponents`, `DeleteWhenAble` | `OnWorkshopObjectRemoved`, `RemoveItemByComponent`, own repair activator, `Delete()` | no |
| settlers | `WorkshopNPCScript` (assignment, `bWork24Hours`, `workshopIDActorValue`), `WorkshopNPCFaction`, `WorkshopMasterPackage` | `GetLinkedRefChildren`, `getLinkedRefArray` (generic, heavy use suspected) | own settler script; linked-ref children via ref collection aliases or keyword lookups | no, unless linked-ref children cannot be emulated fast enough |
| recruitment | radio beacon, `WorkshopRadioBeaconRecruit` quest, attack markers as spawn points | `MakeRadioReceiver` (if the beacon is made a receiver at runtime; unresolved) | placed receiver data plus our quest | no |
| attacks | `CheckForAttacks()`, attack constants, `Workshop*Attack` quests, `WorkshopLinkAttackMarker`, `TriggerAttack` | none by name | own radiant attack quests via Story Manager events; FO4 constants as globals | no |
| supply lines and caravan menu | `CaravanActorAliases`, provisioner packages, `OpenWorkshopSettlementMenu(Ex)`, `WorkshopAssignCaravan_DO` | `OpenWorkshopSettlementMenu`, `OpenWorkshopSettlementMenuEx`, `RaidTargetsAvailable` | provisioner travel packages; a list menu (MESG pages or terminal) for choosing a settlement | optional (a real map-style picker) |
| build menu, power grid | FLST menu tree; wiring | none by name | category keywords (workshop note); Starfield power events | only if grid persistence fails |
| Nuka-World vassals | `RaidTargetsAvailable(... abOnlyPotentialVassalSettlements)` | yes | list menu | optional |

### 2. Followers
| part | FO4 scripts and records | missing names | Papyrus-only | SFSE |
|---|---|---|---|---|
| framework | `Followers` quest, `FollowersScript` (98 functions: slots, Dogmeat, affinity events, loitering, teleport, vertibird), `CurrentCompanion` faction | `SetCompanion`, `AllowCompanion`, `DisallowCompanion`, `SetAvailableToBeCompanion`, `FollowerFollow`, `FollowerWait`, `FollowerSetDistanceNear/Medium/Far` | own framework quest and alias; wrappers re-provided in our own script (likely wrappers already, G1) | no |
| affinity | `CompanionActorScript` (56 names; `TryToModAffinity`, passive gain), `CA_Affinity`, `CA_Event_*`, `CA_CustomEvent_*`, `CA_Size_*`, `CA_DialogueBump_TopicInfoScript` | none by name | AFFE records or own script with FO4 numbers (companions.md) | no |
| moods | animation archetypes during scenes | `SetAnimArchetype*` (7), `SetDogAnimArchetype*` (4) | `ChangeAnimArchetype(Keyword)` with our keywords | no |
| talks and romance | `CA_WantsToTalk`, force-greet packages, affinity scene handler | none | quest dialogue and packages | no |
| command mode | engine command state, DIAL Command subtypes | none by name (engine UI) | `SetCommandState` test first | maybe (C1) |
| Dogmeat, dismemberment kills | Dogmeat alias; `Dismember`, `IsDismembered` in reactions (unresolved use) | `Dismember`, `IsDismembered` | drop or fake | likely, for dismemberment |

### 3. Radio
| part | FO4 scripts and records | missing names | Papyrus-only | SFSE |
|---|---|---|---|---|
| transmitter | REFR XRDO, quest alias forced to `RadioTransmitter`, MESG station name | none by name; XRDO has no Starfield field | `IsPlayerInRadioRange`-style engine range if a transmitter type survives; else our own range check | only for off-Wwise audio |
| receivers | ACTI RADR (`RadioDiamondCityReceiver`), workshop radios | `MakeRadioReceiver` | placed ACTI with RADR; `SetRadioOn`, `SetRadioFrequency` | no |
| station loop | scene phases, `GetVMQuestVariable` shuffle, 900 s restart timer | none | same scene pattern plus our watchdog | no |
| DJ and news | TACT (absent in Starfield.esm) and DN-style news scenes tied to quest progress | none | NPC speaker or TACT test | maybe (if songs leave Wwise) |
| holotape-adjacent | `OnHolotapePlay`, `OnHolotapeChatter` (4 scripts) | yes | terminal-based shim | for flash games |

### 4. Power armor
| part | FO4 | missing names | Papyrus-only | SFSE |
|---|---|---|---|---|
| suit furniture and entry | FURN flag 25, `OnSit` x3, `SwitchToPowerArmor`, `LinkPowerArmorKeyword` | `IsInPowerArmor` | FURN + activator script, own `IsInPowerArmor` | no |
| body | PA race / subgraph | none by name | test `SwitchToPowerArmor`, `SetRace` | yes if both fail |
| fusion core | GMST-driven drain (`fPowerArmorPowerDrainPer*`) | none by name | AV + timer, `OnActorAction`-style events if they exist (unresolved) | for per-action drain |
| HUD | PA HUD, IMPP image space | `Game.EnablePipboyHDRMask` (Pip-Boy side) | image space modifier only | yes for the HUD |

### 5. Survival
| part | FO4 | missing names | Papyrus-only | SFSE |
|---|---|---|---|---|
| manager | `HC_Manager` quest, `HC_ManagerScript`, Hardcore Rules Formlist | `Utility.IsInMenuMode`, `WaitMenuMode` (suspected) | own manager quest with game-time timers | no |
| needs and diseases | spells, effects, `HC_FillWaterBottlePerk` | `Actor.AddSpell`, `DispelSpell` | Starfield's equivalent (unresolved) or afflictions | no if an equivalent exists |
| no fast travel, console | rule in the form list; `bEnableConsoleMenuDuringSurvival` | none | Starfield fast travel enable functions (check) | maybe |
| bed-only saves | unresolved mechanism | none | none known | likely |

## Question framework

Phases: **NG** new game, **INT** interiors, **QP** quests/people, **FS** Fallout systems, **REL** release.

### G. Cross-system: the native gap per system
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| G1 | Of the gap table's FO4-only names, which are `native` in FO4's `.psc` and which are Papyrus wrappers (for example `SetCompanion`, `FollowerFollow`, `IsInPowerArmor`, `StoreInWorkshop`)? **Answered (verified, PC job 34):** 36 of 229 FO4-only names are natives; the rest are Papyrus wrappers or events; table in papyrus-and-script-extenders.md. | Wrappers are re-provided as plain Papyrus; only true natives can need SFSE | falloutck shows `native` on `OpenWorkshopSettlementMenu`, `RaidTargetsAvailable`, `MakeRadioReceiver`, `CanProduceForWorkshop` and not on `SetCompanion`, `AllowCompanion`, `FollowerFollow`, `IsInPowerArmor` (verified page text) | PC probe: grep `Actor.psc`, `ObjectReference.psc`, `Game.psc` in Base.zip for each name with `native` (names only) | blocks every shim plan | FS | **key** |
| G2 | Which FO4 game scripts call which gap names (call-site census per script: Workshop*, Followers*, CompanionActorScript, HC_*, radio, PA)? **Answered (verified, PC job 34):** FO4 calls 25 of the natives at 336 sites (dismemberment 126, spells 75, menus 39, cleared locations 32, workshop 30, menu mode 20, other 14); counts match by name; table in papyrus-and-script-extenders.md. | Turns the "by name" matching above into a real per-system shim list | names per class known (gap table); call sites unknown | PC probe: grep all Base.zip `.psc` for the 77 names, output script x name counts | G1; feeds the shim library | FS | **key** |
| G3 | Do argument lists of shared names differ between FO4 and Starfield for the workshop, follower and radio calls our rebuilds use? | A name match can still fail to compile | flagged unresolved in the gap table | next probe: compare signatures for the names used in G2 | G2 | FS | |
| G4 | One shared shim library (`FO4SF:Shim*`) for all systems, or a shim per system? | Avoids five copies of `GetLinkedRefChildren` emulation | decision pending (papyrus page) | design decision in docs/ai/decisions.md | G2 | FS | |
| G5 | Do `Actor.AddSpell` / `DispelSpell` exist anywhere in Starfield's scripts (moved to ObjectReference, renamed), or must every spell application be rewritten? **Answered (verified, PC job 34):** Starfield declares AddSpell and DispelSpell on ObjectReference; calls on actors should compile through inheritance (supported hypothesis until one compile test). | Survival, chems, companions and PA all add spells | FO4-only on `Actor` per the gap table | grep ContentResources.zip for `AddSpell` and `DispelSpell` across all `.psc` | blocks survival, PA effects | FS | **key** |

### W. Workshop rules layer
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| W1 | Rebuild the rules as a fresh design with WF's extension model (globals, per-settlement overrides, CustomEvents, override events), or a closer port of WorkshopParentScript's structure? | Fixes the architecture before any code; WF shows vanilla's structure is fragile | WF design notes and events (verified); SKK calls vanilla fragile (verified) | design decision after G2, written in decisions.md | G2; blocks W2 to W8 | FS | **key** |
| W2 | Can the converter emit FO4 settlement registration (location keywords, ref types, link keywords, `WorkshopsCollection`-style quest, ECZN flag) as data onto Starfield's WorkshopKeyword ACTI, and does Starfield's `GetWorkshop` / `GetWorkshopResourceObjects` then find our objects? | Everything else reads this registration | SKK checklist (verified); 29 workshops already promoted to ACTI (workshop note) | CK test: one converted settlement, one placed resource object with our link keyword, a script that logs `GetWorkshopResourceObjects` | blocks W3, W4 | FS | **key** |
| W3 | Do our own rating AVs on the workbench ref sum and persist when the settlement is unloaded (FO4's daily update runs on unloaded settlements; `CanProduceForWorkshop` is valid only while loaded)? | Ratings, happiness and attacks are computed off-screen | falloutck note on loaded-only validity (verified) | CK test: set AVs, leave the area, wait a game day, read them back | W2 | FS | **key** |
| W4 | What is FO4's daily update order and cost (all settlements per day), and what Papyrus budget does it need on Starfield? | Script lag was FO4's worst workshop problem | WF Max Threads 10 to 50 (verified) | PC probe: read `WorkshopParentScript` daily-update function names and loop structure (names only); measure our tick in game | W1 | FS | |
| W5 | Attack formula exact form, and how `Workshop*Attack` quests are started (Story Manager event, script start, which faction picks)? | Reproducing the feel of attacks; faction choice ties to the owner's faction-relationship interest | constants and `CheckForAttacks` (verified); quest family name only | PC probe: names of attack quests in Fallout4.esm and the Story Manager node that starts them; read the formula in Base.zip | W3; faction model | FS | |
| W6 | Supply lines: what data links settlements (`CaravanActorAliases`, a keyword or a location link), and is shared storage computed by script? | Linked consumption and shared crafting storage | caravan menu native (verified); WF "linked settlement consumption" (verified); Starfield Shared Outpost Container (workshop-items-economy.md) | PC probe: grep `WorkshopParentScript` for caravan function names; CK test of Starfield's shared container outside outposts | W2 | FS | |
| W7 | How does the player pick a settlement for a provisioner or settler move without `OpenWorkshopSettlementMenu`? | A core interaction with no native menu | native in FO4, absent in Starfield (gap table) | prototype: MESG paged list, then terminal list; SFSE map picker only if both are too clumsy | W2 | FS | |
| W8 | Do we publish our own add-on API (WSFW_API-like functions, CustomEvents, SS2-like registration quest plus config Misc plus FormLists plus version Global)? | Future settlement mods build on us instead of overwriting us | WF and SS2 models (verified) | decision, then a one-page API spec | W1 | REL | |
| W9 | Does Starfield's outpost power grid (`HasSharedPowerGrid`, `OnPowerOn/Off`) hold for FO4 wiring placed by the converter, across save and load? | FO4 grids corrupted and needed F4SE to fix | WF power tools need F4SE (verified) | in-game test: generator plus light placed by plugin, save, reload | W2 | FS | |
| W10 | Location "cleared" (FO4 `IsCleared`, `OnLocationCleared`) vs Starfield "explored": is there an engine "cleared" state we can use for clear-to-own settlements and radiant quests? | Many Minutemen radiants and ownership depend on it | four names missing (gap table) | grep Starfield `Location.psc` and condition functions for cleared or explored; CK test | G2 | QP | |

### F. Followers
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| F1 | Are FO4's companion `Actor` functions wrappers over `FollowersScript` (then our framework supplies them as Papyrus)? | Decides if any follower part needs SFSE | no `native` on falloutck pages (verified page text) | part of G1 | G1 | QP | **key** |
| F2 | Which `FollowersScript` functions are the minimum for the new game (slot, follow, wait, dismiss, teleport on fast travel, affinity broadcast)? | Breadth first: 98 functions is too many for phase one | 98 functions (verified count) | PC probe: list function names with one-line purpose; pick a minimum set | F1 | QP | **key** |
| F3 | Who broadcasts `CA_Event_*` keywords to companions, and with what range and cooldown logic, so each FO4 event has a sender on Starfield? | Without senders affinity never moves | `EventData_Array` and `TryToModAffinity` (verified names); sender unknown publicly | grep Base.zip for `CA_Event_` senders | F2; A5 in the companions note | QP | **key** |
| F4 | Do we keep FO4's passive gain formula (40 - 0.033 x affinity per 10 min with XP) or Starfield's `AddPassiveAffinity`? | Pacing of every companion story | FO4 formula (supported); `AddPassiveAffinity` exists in SF (verified name) | decide; test one with a timer | F2 | QP | |
| F5 | Do FO4's 11 animation archetypes map to Starfield archetype keywords for `ChangeAnimArchetype`? | Companion moods in scenes | 11 FO4-only names (verified); SF function exists (verified name) | list Starfield KYWD with "AnimArchetype" in Starfield.esm | animations area | QP | |
| F6 | Does FO4's "hatred leaves forever" and Preston's forced drop work with AFFE or need script? | Story consequences | wiki rules (supported) | design note after F3 | F3 | QP | |

### R. Radio
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| R1 | Does a placed ACTI with RADR data plus a transmitter ref make Starfield's `IsPlayerInRadioRange` / `OnPipboyRadioDetection` work? | If yes, FO4 range logic is engine-side and data only | SF natives exist (verified names); XRDO not in SF REFR (radio note) | CK test: one receiver and one transmitter candidate in a test cell; log the event | blocks R3 | FS | **key** |
| R2 | Which vanilla quest, scene and script hold Diamond City Radio, its 900 s restart, and the news (DN-style) scenes tied to quest progress? | The station is a quest system, not just audio | pattern documented (verified); vanilla ids unknown | Fo4Export read-only scan: SCEN with Radio actions, their quests and conditions | R1 | FS | **key** |
| R3 | Scene-driven station (data) or SFSE player DLL, given the watchdog need either way? | Decides the radio architecture | both patterns exist (verified, radio note and precedents) | after R1 and the Wwise loose-file test | R1; Wwise test | FS | **key** |
| R4 | Does the recruitment beacon use `MakeRadioReceiver` or a placed receiver? | One of few radio gap names | unresolved | part of G2 | G2 | FS | |

### P. Power armor
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| P1 | What does Starfield's declared `SwitchToPowerArmor` do when called with a FURN that has no PA flag? | Decides script-only vs SFSE body swap | declared in SF (PC probe); behaviour untested | one console or script test | blocks P3 | FS | **key** |
| P2 | Do the `fPowerArmorPowerDrainPer*` GMSTs exist in Starfield.esm? | If yes, engine drain code may survive | names verified on FO4 side | offline scan of Starfield GMST editor ids | P1 | FS | **key** |
| P3 | Can Papyrus catch the drain triggers (AP spend, sprint, jump, melee, landing) on Starfield? | Faithful core drain without SFSE | unresolved | grep SF `Actor.psc` / `ScriptObject.psc` for action events | P2 | FS | |
| P4 | Is `IsInPowerArmor` a wrapper in FO4 (G1), and which FO4 scripts and conditions call it (companion reactions, MQ102)? | Size of the shim | missing in SF (gap table) | G1, G2 | G1 | FS | |

### V. Survival
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| V4 | What rules does the Hardcore Rules Formlist hold, and how does `HC_ManagerScript` apply each (GMST, spell, perk, fast travel call)? | Each rule's CE2 path differs | `HC_Manager`, `HC_ManagerScript`, rules formlist (verified) | Fo4Export scan of the formlist plus Base.zip grep for its apply function names | G2, G5 | FS | **key** |
| V5 | Can bed-only saving be enforced on Starfield without SFSE? | The defining survival rule | mechanism unknown in FO4; SF Game has save requests only (verified names) | grep SF scripts and GMSTs for save disabling; in-game test | V4 | FS | **key** |
| V6 | Do `IsInMenuMode` / `WaitMenuMode` matter to survival timers, or can game-time timers replace them? | Two gap names | names missing (gap table) | G2 | G2 | FS | |
(V1 to V3 are in character-systems.md.)

## Sources
- https://nexusmods.com/fallout4/articles/2298 (SKK, registered settlements)
- https://forums.nexusmods.com/topic/6395706-need-help-getting-more-settlement-attacks
- https://forums.nexusmods.com/topic/4929630-how-can-i-test-whether-ive-successfully-disabled-settlement-attacks
- https://forums.nexusmods.com/topic/13510492-assigning-npc-to-workshop-through-dialogue
- https://forums.nexusmods.com/topic/6892821-is-an-npc-assigned-to-a-workshop
- https://forums.nexusmods.com/topic/10180778-shock-collars-change-bwork24hours-to-true
- https://forums.nexusmods.com/topic/12810282-getting-thisworkshop-settlers-into-an-array
- https://www.nexusmods.com/fallout4/mods/38738 (Move Workshop Markers by SKK)
- https://www.nexusmods.com/fallout4/articles/1597 (SKK Settlement Attack System)
- https://falloutck.uesp.net/wiki/Workshop
- https://falloutck.uesp.net/wiki/ObjectReference_Script
- https://falloutck.uesp.net/wiki/CanProduceForWorkshop_-_ObjectReference
- https://falloutck.uesp.net/wiki/OpenWorkshopSettlementMenu_-_ObjectReference
- https://falloutck.uesp.net/wiki/RaidTargetsAvailable_-_ObjectReference
- https://falloutck.uesp.net/wiki/MakeRadioReceiver_-_ObjectReference
- https://falloutck.uesp.net/wiki/SetCompanion_-_Actor , https://falloutck.uesp.net/wiki/AllowCompanion_-_Actor ,
  https://falloutck.uesp.net/wiki/FollowerFollow_-_Actor , https://falloutck.uesp.net/wiki/IsInPowerArmor_-_Actor
- https://github.com/kinggath/WorkshopFramework
- https://github-wiki-see.page/m/kinggath/WorkshopFramework/wiki_index and pages Development-Design-Notes, API,
  New-or-Improved-Events, Editing-Workshop-Formulas, Using-the-Threading-Engine, F4SE-Wrapper-(WIP), Assault-Manager,
  Control-Manager
- https://wiki.simsettlements2.com/gameplay/basics/workshop-framework
- https://wiki.simsettlements2.com/CreateAddons , https://wiki.simsettlements2.com/CreateAddons/Addon-Registration
- https://forums.nexusmods.com/topic/12870213-creation-kit-how-to-make-a-companion-use-a-different-affinity-keyword
- https://www.nexusmods.com/fallout4/mods/77021 (Toggle passive affinity gain)
- https://fallout.fandom.com/wiki/Affinity
- https://www.nexusmods.com/fallout4/mods/101520 (radio tutorial, restart script)
- https://forums.nexusmods.com/topic/4758600-question-custom-radio-station-silences-or-pauses
- https://www.nexusmods.com/fallout4/mods/85638 (fusion core drain settings)
- https://forums.nexusmods.com/topic/6308206-implementing-custom-power-armour
- https://www.nexusmods.com/fallout4/mods/19162 (HC_ManagerScript), https://www.nexusmods.com/fallout4/mods/11933
  (Hardcore Rules Formlist), https://www.nexusmods.com/fallout4/mods/46306 (SKK Survival Utilities)
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-ObjectReference ,
  https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Actor , https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Game
- Project: /mnt/project-files/research/engine-mechanics/papyrus-and-script-extenders.md (gap table),
  workshop-and-settlements.md, companions.md, radio-music-sound.md, power-armor.md, health-damage-effects.md;
  /mnt/project-files/research/framework/engine-mechanics-notes/ (wave 1 and 2 notes)
