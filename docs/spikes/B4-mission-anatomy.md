# Spike B4: mission anatomy (When Freedom Calls, Preston), the Vault 111 exit, grab mass limits (2026-10-17, Claude)

**Status:** research only, offline, read-only on the game data; nothing was built or run in game. Input to Phase B of
docs/ROADMAP.md (B1 exit, B2 Preston, B4 mission) and to Codex's record-machinery design (QUST / DIAL / INFO / PACK).
Labels: **verified** (read from the files, command below), **supported hypothesis**, **unresolved**.

Sources: Fallout4.esm, `Fallout4 - Voices.ba2`, `Fallout4 - Misc.ba2` (compiled scripts; no FO4 script sources ship),
`Fallout4.exe`; Starfield.esm, `Starfield.exe`, `Tools\ContentResources.zip` (vanilla Papyrus sources). Tools: the repo's
`fo4sf.fo4land.Plugin` walker and `fo4sf.ba2.Ba2` reader driven by scratch scripts (not committed), and
`dotnet run --project dotnet/ActorRaider -- fo4-dump <Fallout4.esm> 001A001C,0001D806,00019FD9` (Mutagen cross-check).
Script behaviour comes from the call lists in the compiled `.pex` files (method names, properties, literals); no
decompiled code is in this page.

## Answer in short

1. **"When Freedom Calls" is four quests, not one** (verified). `Min00` 001A001C carries the name, the Pip-Boy stages
   and objectives, and points at the other quests' aliases; the logic runs in `MQ102` 0001CC2A ("Out of Time", which
   also runs the Vault 111 exit); the museum fight, raider waves and the deathclaw are `DN092` 0001D806; this
   mission's Preston lines and the reward are in `DialogueConcordArea` 000179F3. The cut-down mission needs one new QUST
   (6 stages, 3 objectives, 10 aliases), 8 placed actors, one trigger, two globals and one short dialogue; it drops
   the power armor, minigun, deathclaw, waves, settlers, Codsworth and the Sanctuary hand-off.
2. **Preston** is NPC_ 00019FD9, HumanRace, voice type `NPCMPrestonGarvey` 00019FDE, 2,421 voice files in the base game
   (2,264 INFOs in 99 quests; 102 in this mission). The raider path covers the identity-on-a-template record; the gaps
   are a friendly template, a placed persistent ACHR in a converted cell, packages, a faction, dialogue and voice.
3. **Vault 111 exit:** the cog door is driven by `MQ03QuestScript` (the console's animation event "stage4" makes the
   quest call `PlayAnimation('Stage2')` on the door); the elevator ride ends in FO4 itself with an **automatic load
   door** (`AutoloadDoorNoText`, flags 0x42). **GO** for the project's scripted load door in place of the ride, and **GO**
   for the cog door as a door rig (`--door-anim-dll`, FO4's Stage2 keys as the open clip); **NO-GO for B1** on an
   activator rig with Stage clips.
4. **Grab limits:** neither ESM sets the grab weight limits; both executables default to `fGrabMaxWeightWalking` 100
   and `fGrabMaxWeightRunning` 50 (verified, read from the initializers). The converted items measured so far weigh
   10-50 kg, under 100, so mass alone should not stop a walking grab (supported hypothesis). The owner's
   `SetRigidBodyMass` experiment plus one `SetGS fGrabMaxWeightWalking` check decides it; no converter rule yet.

## 1. "When Freedom Calls"

### 1.1 The records (verified)

| QUST | form | role | stages | objectives | aliases | scripts | DIAL / INFO | scenes |
|---|---|---|---|---|---|---|---|---|
| `Min00` "When Freedom Calls" | 001A001C | the Pip-Boy quest (Minutemen); text, objectives, XP (global `XPFaction`) | 19 | 14 | 26 (20 external: 14 from MQ102, 6 from DN092) | fragments `QF_Min00_001A001C` | 0 / 0 | 0 |
| `MQ102` "Out of Time" | 0001CC2A | the driver: Vault 111 exit, Codsworth, Concord, museum, power armor | 54 | 19 | 73 | `MQ03QuestScript`, 2 counters, fragments; scripts on 43 aliases | 0 / 0 | 0 |
| `DN092` "The Museum of Freedom" | 0001D806 | the fight: raiders, waves, deathclaw, intercoms | 15 | 0 | 34 | `DN092QuestScript`, `defaultQuestRespawnScript`, fragments; scripts on 12 aliases | 22 / 28 | 10 |
| `DialogueConcordArea` | 000179F3 | Preston and the settlers' dialogue, the reward | 9 | 0 | 13 | `DIalogueConcordScript`, fragments | 255 / 397 | 15 |

The chain (fragments): MQ102 stage 55 (one of 4 exterior triggers `MQ102SetStage55Trigger01-04REF` in cells
(-16..-14, 16..18)) starts Min00 and sets DN092 stage 1; MQ102 stages 65 / 70 / 75 / 80 / 85 / 89 / 90 / 100 /
110 / 115 / 122 / 123 / 130 / 140 each set the matching Min00 stage (20 / 25 / 27 / 30 / 35 / 40 / 45 or 47 / 50 /
60 / 65 / 70 / 75 / 80 / 90). DialogueConcordArea stage 5 sets MQ102 89 (Preston's first line), stage 40 gives the
reward, stage 200 sets MQ102 200 and Min01 50 ("Sanctuary").

### 1.2 Min00 stages and objectives (verified; the log text is the game's own)

| stage | note | objective shown |
|---|---|---|
| 10 / 20 | hears of the Minutemen / Preston tells the player to enter | 10 Find the Last Minutemen, 60 Enter the Museum, 70 (Optional) Take the Laser Musket |
| 25 / 27 | entered the museum / took the musket | 80 Locate the Trapped Settlers |
| 30 / 35 | tried Preston's door / museum raiders dead | 85 Kill the Raiders (`MQ102FirstRaiderCount`/`MQ102FirstRaiderTotal` = 7) |
| 40 / 45 / 47 | met Preston / quest given (47: already in power armor) | 86 Talk to Preston Garvey, 87 Unlock the Security Gate, 90 Get a Fusion Core |
| 50-75 | gate, power armor, minigun, raiders and deathclaw of the second fight | 105, 110, 115, 120 Clear Concord of Hostiles |
| 80 / 90 / 100 | Concord safe / talked to Preston / to Sanctuary | 140 Report back to Preston, 150 Join Preston in Sanctuary |
| 200 / 1000 | complete / shutdown (achievement 2) | all completed |

### 1.3 Aliases that matter (verified)

| alias (quest id) | fill | notes |
|---|---|---|
| PrestonGarvey (MQ102 2, Min00 3, DN092 1, DialogueConcordArea 4) | unique actor 00019FD9 | MQ102 adds `RaiderEnemyFaction` and the window-sniping package |
| ConcordMuseum (loc) | `ConcordMuseumLocation` 0001D807 | the raiders fill from it by location ref type |
| RaiderA1, A2, B1, B2, C1, C2, RaiderMannequin (MQ102 21-27, 55) | `DN092_EncA_Raider01/02`, `DN092_RaiderRefType2` (x2), `_RefType3`, `_RefType3_doorkicker`, `DN092_Mannequin_Raider` | alias script `MQ03RaiderAliasScript`: OnDeath counts the 7; a failsafe kills and disables a raider that changes location |
| PrestonDoor / PrestonExitDoor | `PrestonDoorREF` 0001E2EA / 0001E2E9 | locked until the raiders are dead (`OpenPrestonDoor`: Unlock, SetOpen) |
| PowerArmorFurniture, Minigun, FusionCore, SecurityGate | 000370E3 (`PowerArmorFurnitureT45_NoCore_Partial_Dmg50`), `MQ102MinigunREF` 0001F583, `MQ102FusionCoreREF` 00237B27, `MQ03SecurityGateREF` 0005C66C | the second half; `MQ102PowerArmorScript` on the furniture |
| Deathclaw (DN092 9), RaiderBoss, WaveRaider01-03, RoofLookout | unique `DN092AmbushDeathclaw` 0002C969; created at spawn markers (`LvlRaiderBoltAction`, `LvlRaider_Handmade_MG`, `EncRaider01Boss` "We're Not Friends") | waves respawn (pool 8); the deathclaw spawns after 8 wave kills or 300 s |

The 7 counted raiders are placed ACHRs in ConcordMuseum01 (00017DF7): `DN092_EncA_R01` 0001D809 and `_R02` 0001D808
(`LvlRaider_Handmade_MG`), `DN092_EncB_R01` 0001CB6E (`LvlRaider_MaleVoice02`), `_EncB_R02` 0001E2E0 and `_EncC_R01`
0001E2E2 (`LvlRaiderMeleeMale02`), `_EncC_R02` 0001E2E1 (`LvlRaider_MaleVoice01`), `DN092_Mannequin_R01` 00018D6B
(`LvlRaider`). Four of them (EncB, EncC) are initially disabled (flag 0x800) and are enabled by DN092 stages 25 / 50
or MQ102 stage 78.

### 1.4 Scripts (verified from the .pex call lists)

| script | on | what it does |
|---|---|---|
| `QF_MQ102_0001CC2A` (120 properties) | MQ102 stages | moves Preston and the settlers (MoveTo markers), EvaluatePackage, AddToFaction, `SetGhost(False)` at 85, starts scenes 003 / 005 / 006 / 009, unlocks Preston's exit door (88), enables the 7 raiders at 78 if disabled, `MQ102PostquestEnableMarker` at 150 |
| `MQ03QuestScript` | MQ102 | `FirstWaveRaiderDead`: `Min00.ModObjectiveGlobal` on the count, stage 85 at 7; `OpenPrestonDoor`; the Vault 111 console and gear-door sequence (section 3) |
| `QF_Min00_001A001C` | Min00 stages | only `SetObjectiveDisplayed` / `Completed`, achievement at 1000 |
| `QF_DN092_0001D806`, `DN092QuestScript` | DN092 | enables the encounter raiders by stage, `StartCombat(player)` on the ambush and wave raiders, the deathclaw timer |
| `QF_DialogueConcordArea_000179F3` | stage 40 | the reward: `AddItem` caps x100 and fusion cells x50; Min00 adds quest XP (`XPFaction`) |
| `MQ102PrestonActorScript` | Preston | OnLoad: equips his musket while MQ102 runs |
| `defaultrefontriggerenter` | 9 triggers in the museum | `DefaultSetStageTrigger(PlayerOnly)` 0003251C / 0003251F: MQ102 70 (entered), 77, 78, 86, 87, 88, 135; DN092 10, 50 |

### 1.5 Dialogue and voice (verified; voice files counted in `Fallout4 - Voices.ba2`)

- DialogueConcordArea: 255 DIAL (243 scene topics), 397 INFO, 363 responses. Voice files: Preston 102, player 100 per
  sex, Mama Murphy 75, Sturges 63, Marcy 14, Jun 8. DN092: 22 DIAL / 28 INFO, raiders and museum loudspeakers only.
  MQ102 and Min00 own no dialogue.
- Preston's 102 lines here: 68 in scene topics, 34 in other topic types (HELO 11, IDAT 9, WFPI 6, GREE 6, HIT_ 1,
  CUST 1). By scene: 003 balcony call 7, 004 door 3, 005 beckon 8, **006 meeting and quest 21** (86 INFOs with 36 player and 23 settler lines), 006 Shaun
  variant 4, 009 lobby 1, **010 reward 20** (54 INFOs), 011 lobby 4.
- Voice types: `NPCMPrestonGarvey`, the two player voices, `NPCFMamaMurphy`, `NPCMSturges`, `NPCFMarcyLong`,
  `NPCMJunLong`, `RaiderMale01/02`, `MuseumVoice*`.

### 1.6 Packages (verified; template = the PKCU package template's editor id)

| who | package | template |
|---|---|---|
| Preston (own PKID) | `SanctuaryDefaultSandbox` 00115BD3, `ConcordPrestonTraveltoMarker1NoCombatWeaponDrawn` 00022AA4 | Sandbox, Travel |
| Preston (alias, DialogueConcordArea) | 8: ForceGreetLobby 0005DF28, TraveltoBalcony 0001D414 / 0005E5C7, TraveltoMarker4 0001F5B8, MuseumWindow 000A878D, CustomForcegreet 00022B3C, StayinMuseum 0003FE3C | ForceGreet, Travel (x5), custom |
| Preston (alias, MQ102) | `MQ102PrestonUseWeaponAtMuseumWindowPackage` 002394C2; override list `MQ102PrestonOverridePackageList` (3 HoldPosition) | custom |
| museum raiders (alias) | `DN092_RaiderFireAtPrestonPKG`, `_StayOnBridgeDuringCombatPKG`, `_SeekPlayerPostMQ102stage80`, `_AmbushRaiderExhibitPKG` | UseWeapon, HoldPosition, TravelSuspicious, PatrolAndGuard |
| wave raiders / deathclaw | `DN092_RaiderRunToWavePKG`; `DN092_DeathclawEmergePKG`, `_IntroPKG` | UseWeaponMultipleTargets; Sandbox, AmbushTemplate |

Starfield.esm has the same templates by editor id (verified): Travel 00002CB0, Sandbox 00002CB1, ForceGreet 00017BAB,
HoldPosition 0001D415, UseWeapon 0001D6B3, UseWeaponMultipleTargets 0005F432, PatrolAndGuard 00035953,
TravelSuspicious 00079773 (no AmbushTemplate).

### 1.7 Cells and state (verified)

- **ConcordMuseum01** 00017DF7: 3,402 REFR + 12 ACHR (Preston `PrestonGarveyRef` 0001A4D7 persistent, Sturges, Mama
  Murphy, Marcy, Jun, the 7 raiders). Load doors: front 00077D22 -> exterior 0001AC07 (cell -14, 17), balcony 0001B94A
  -> 0001D22F, roof 0002C1C6 -> 00029AD8 (-14, 16). Interior backlog rank 17, class L; converted offline in the
  near-slice batch, not deployed.
- **Concord exterior** (Commonwealth persistent cell 00018AA2, cells -16..-14 x 16..18): the 4 stage-55 triggers, the
  laser musket 0001F22E, power armor 000370E3, minigun 0001F583, `DN092concordRaider01` 00046458 (the converted
  raider's source) and DN092's spawn markers.
- Enable / move machinery is all script-side (fragments above); museum refs barely use enable parents (30 refs under
  6 parents: 5 XMarkers and a light). Actors in cell exports are `deferred_refs` and are not written today
  (docs/CELL-EXPORT.md).

### 1.8 The cut-down mission for Phase B (proposal)

Order kept from FO4: the player is called to the museum, clears it, then meets Preston (FO4 gives Preston's quest after
the fight). The roadmap's exit criterion says "walks to Preston, takes the objective, fights"; suggest the wording
"is called to the museum, fights through it, talks to Preston".

| step | FO4 source | cut-down | Starfield needs | the runner checks |
|---|---|---|---|---|
| 0 start | MQ102 55, 4 exterior triggers, Min00 objective 60 | quest starts enabled (or on one Concord trigger); objective 10 "Enter the Museum" | QUST, objective target = the **exterior door ACTI** (a quest target does not route through our scripted doors, which are not XTEL load doors: supported hypothesis) | bridge: `Quest.IsRunning`, `IsObjectiveDisplayed(10)` |
| 1 reach the museum | trigger `MQ102SetStage70TriggerREF` 0001D315 | the same trigger box (FO4 base 0003251C), stage 10; objective 20 "Kill the Raiders (x/7)" (objective 30 "Talk to Preston Garvey" at stage 20) | REFR of `DefaultSetStageTriggerPlayerOnly` 0003251F (same id and editor id in Starfield; script `DefaultRefOnTriggerEnter`, properties `QuestToSetOrCheck`, `StageToSet`, not FO4's `myQuest`) | door_trip into ConcordMuseum01, then `GetStageDone(10)` |
| 2 clear the raiders | 7 ACHR, `MQ03RaiderAliasScript`, 2 globals | 7 raider aliases (forced refs) with `DefaultCounterAliasIncOnceOnDeathA` + `DefaultCounterQuestA` (TargetValue 7) -> stage 20; or N = 3 (the never-disabled EncA x2 + Mannequin) if the 4 upper-floor ones fail | 7 ACHR on FO4_LvlRaider-style NPC_ (4 bases), SpacerFaction hostility, the converted navmesh, 2 GLOB for "(x/7)" | npc_nav combat reads per raider, `IsDead`, `GetStageDone(20)` |
| 3 talk to Preston | `OpenPrestonDoor`; scene 006 (21 Preston lines) | stage 20 unlocks `PrestonDoorREF`; one dialogue (8-12 of Preston's lines from scenes 006 / 010, subtitled silent until WP-15) whose INFO sets stage 30 (`DefaultTopicInfoSetStage`) | Preston NPC_ + ACHR, a friendly faction, Sandbox package (00002CB1), DIAL / INFO with `GetIsID` + `GetStage` conditions | Preston loaded, alive, `IsHostileToActor(player)` false, door unlocked; the talk itself is the owner's |
| 4 reward | DialogueConcordArea 40: caps 100, fusion cells 50; Min00 XP | stage 40: credits 100 (+ an ammo analog), then `CompleteQuest` / stage 100 | a fragment script (compiled Papyrus, Codex) | credits delta, `IsCompleted`, all reads again after save and reload |

**Kept records:** the 8 actors (Preston, 7 raiders), `PrestonDoorREF`, the stage-70 trigger, the museum's front door
pair, Min00's texts. **Dropped:** MQ102 except the museum part (vault, Codsworth, dogs, insects, power armor, minigun,
fusion core, security gate, terminal, deathclaw, Sanctuary hand-off), DN092 (waves, respawn, deathclaw, intercoms,
10 scenes), the settlers, Dogmeat and DialogueConcordArea's other scenes (15 in all; one exchange is kept), balcony
and roof doors, the 4 exterior Concord raiders (they stay the
existing npc test), Preston's 7 FO4 scripts.

**Open for the mission:** the converted raider never engaged unprompted (c1); FO4 itself forces combat in DN092
(`StartCombat(player)` at stages 13 and 76). Either the cut-down quest does the same at stage 10 (cheap, FO4's own
pattern) or the roadmap's "no forced start" stays and hostility is fixed first. A decision for the owner.

## 2. Preston Garvey as the first complex NPC

**The record (verified, NPC_ 00019FD9):** FULL "Preston Garvey"; `HumanRace`; voice `NPCMPrestonGarvey` 00019FDE; flags
Essential, AutoCalcStats, Unique, IsGhost (cleared by MQ102 85); level multiplier 1, min level 10; class
`ZeroSPECIALclass`; combat style `csPreston`; AI Aggressive, Foolhardy, NoCrime, HelpsAllies; 9 factions
(`MinutemenFaction` 00068043, `CompanionCrimeFaction_Preston`, Current/HasBeen/PotentialCompanionFaction,
`SettlementConcordArea`, `Voices_CompanionsFaction`, `WorkshopNoTrade`, `WorkshopNPCFaction`); outfit
`PrestonGarveyOutfit` 0001F158 = `ArmorPrestonGarveyOutfit` 0001F17B + `ArmorPrestonGarveyHat` 000316D4; inventory
`CompPrestonLaserMusket` 00062AA6, flare ammo, `ClothesMinutemanOutfit`; 6 perks; 6 keywords; packages: own PKID
Sandbox + Travel (above), **no default package list** (DPLT absent); face: 9 head parts, 14 tint layers, 11 morphs,
30 face-morph regions; 7 scripts (companion, workshop, power-armor keyword, teleport, crime hostility, MQ102 musket,
Minutemen). Placed once: `PrestonGarveyRef` 0001A4D7, persistent, ConcordMuseum01.

**Dialogue (verified):** 2,421 voice files, 2,264 INFOs, 99 quests: `COMPreston` 1,095, `AO_Comment_Dialogue` 178,
`Min01` 115, `DialogueConcordArea` 102, `MQ302Min` 88, `Min02` 74, the rest under 45 each.

**What the raider path already covers** (docs/actors/raider-conversion.md, decisions 11 Oct): an NPC_ with the FO4
identity (name, factions, inventory, weapon analog, outfit placeholder, death item) on a Starfield template for Traits
and behaviour; race mapping; the 16 mandatory subrecords and form version 581; template slots 13 / 14; a spawn
confirmed by `GetIsID`; combat once forced (c2 / c4 PASS ENGAGED).

**Gaps for Preston:**
1. a **friendly combat template** (the raider uses Spacer, hostile to the player): a vanilla ally human that fights
   SpacerFaction; which one is **unresolved**;
2. Unique / Essential / ghost-until-stage flags on Starfield's ACBS (mapping not checked);
3. a **placed persistent ACHR** in a converted interior with an id that survives rebuilds: the cell writer defers
   actors today (Codex: persistent identity);
4. **packages** (Sandbox / Travel / ForceGreet) and alias packages: the PACK writer (Codex);
5. a **faction**: a converted MinutemenFaction allied with the player and hostile to SpacerFaction, or a vanilla one;
6. **dialogue** (DIAL / INFO / SCEN) and a **voice type**; audio needs WP-15, silent subtitled lines meanwhile;
7. face (Grok's lane), the outfit and hat (skinned armour, actor milestone), the laser musket (a Starfield laser rifle
   analog, chosen like the raider's Coachman);
8. **save and reload persistence**: no save / reload test of a converted actor is recorded yet (docs/actors, journal).

## 3. The Vault 111 exit (B1)

**Cog door chain (verified, Vault111Cryo 000016D8):** `MQ102GearDoorConsoleREF` 00091A49 (ACTI `V111GearDoorConsole01`
00091A48, alias ControlPanel, `MQ03ControlPanelScript`): without a Pip-Boy, MQ102 stage 5 and a fail sound; with it,
stage 7 seats the player at `Vault111DoorConsoleFurnitureREF` 00054FED (`NPCVaultConsoleActivate`) and waits for the
plug-in animation events; the panel plays `Stage2` (glass flip); a second activation (`DepressButton`) starts the
klaxon and sets stage 9: the panel plays `Stage3`, the quest closes `Vault111ExitDoorREF01/02` and registers for
"stage4"; on it `MQ03QuestScript` plays `Stage2` on `Vault111GearDoorREF` 000330C3 (ACTI `VltGearDoor01` 000330C2,
no script of its own), enables the klaxon and strobe lights and `V111ExitLightingEnableMarker` 002075E4, adds the
music, and later sets stage 8. The gear-room gate `V111GearRoomGate01` (MSTT 0002FE23) is separate.

**Elevator chain (verified):** `vaultExitElevatorDown` 00020C3A (trigger, `vaultExitElevatorDownSCRIPT`) plays
`stage2` on `V111ElevatorREF` 000244EB (ACTI `VltElevator` 000244EF, no script) to bring the platform down. On it,
`RespecTriggerREF` 0008C94A (`vaultExitElevatorSCRIPT`) disables controls, shows the SPECIAL and looks menus, then
plays `stage3` (up 21.6 m) and fades out. The platform carries the player into `Vault111InteriorAutoLoadDoorREF`
0001F180 (enabled from the start, z 1563 at the shaft top): DOOR `AutoloadDoorNoText` 0007ECFC, FNAM 0x42 (automatic +
no "to" text), teleporting to 000998E3 on the surface. Later rides go through `Vault111AscendAgainTriggerREF` 0009A149
(`VaultElevatorAscendAgainScript`, initially disabled; it re-enables the same door). Outside, `Vault111OneShotExteriorElevatorTrigger` 00051877 (`vaultExitCommonWealthSCRIPT`) plays `stage4` on
the surface elevator and sets MQ102 stage 10 ("Emerged from the Vault"). The way back in uses
`Vault111DescendAgainTrigger` (clips `stage6` / `stage8`) and the same auto-load door pair; a companion failsafe door pair
00248AAD / 00248AAE (`InvisibleLoad01HiddenMinUse`) also links the two.

| piece | cheapest working port | verdict |
|---|---|---|
| exit elevator | the project's scripted load door (`FO4SF_LoadDoor` ACTI, MoveTo + the planned SetPosition) on the platform, destination a persistent marker at 000998E3; the reverse door on the surface platform. FO4 already ends the ride with a load door, so only the animation is lost | **GO** (needs the persistent exterior marker of the 16 Oct design; runner: door_trip both ways with save and reload) |
| exit elevator, animated ride | TranslateToRef platform (sliding-doors.md "Elevator") | NO-GO for B1, later polish |
| cog door | DOOR on the vanilla open / close graph with its own rig and FO4's `Stage2` keys (43.3 s) as the open clip (`--door-anim-dll`, the path of the 10 sliding doors); the console becomes a small activator script calling `SetOpen` on it, or the door itself is activated | **GO** (supported hypothesis: the rig path is proven offline only; 48 shapes, 5 skinned, 27 bodies; runner: activate, `GetOpenState`, a walk through) |
| cog door as activator rig | named Stage clips on an activator graph + `PlayAnimation` | NO-GO for B1: no vanilla activator graph surveyed |
| console seat, Pip-Boy plug, klaxons, char-gen menus | drop | out of B1 |

## 4. Carrying objects: grab mass limits (playtest row 26)

| setting | FO4 ESM | FO4 exe default | Starfield ESM | Starfield exe default |
|---|---|---|---|---|
| `fGrabMaxWeightWalking` / `Running` | - | 100 / 50 | - | 100 / 50 |
| `fGrabRagdollMaxWeightWalking` | - | (none) | - | 200 |
| `fZKeyHeavyWeight` | - | 75 | - | 75 |
| `fZKeyMaxContactMassRatio` | - | 4 | - | 4 |
| `fZKeyActorMassTheshold` (sic) | - | (none) | - | 6 |
| `fZKeyMaxForce` | 175 | 250 | 250 | 250 |
| `fZKeyMaxForceWeightHigh` / `Low` | 150 / - | 300 / 0 (?) | (none) | (none) |
| `fZKeyMaxContactDistance` | - | 10 (units) | 0.1429 (m) | 0.14 |
| `fZKeyObjectDamping`, `SpringDamping`, `SpringElasticity` | - | 0.75, 0.5, 0.2 | - | 0.75, 0.5, 0.2 |
| `fZKeyMaxTranslationSpeed` / `RotationSpeed` | (none) | (none) | - | 2 / 180 |
| `fAVDCarryWeightBase` (inventory) | 200 | 150 | 130 | 150 |

- **verified:** the names and ESM values (GMST group of each ESM; FO4 2,037 GMST, Starfield 2,312). Exe defaults:
  FO4 keeps each setting as a static object whose value sits 8 bytes before its name pointer; Starfield initializes it
  in code, loading the float (`vmovss`) right before the `lea` of the name. Pairing by adjacency is a **supported
  hypothesis** per value, checked where both are known (`fZKeyMaxForce` 250, `fZKeyMaxContactDistance` 10 / 0.14).
- **supported hypothesis:** the grab gate compares the body's Havok mass (kg) with `fGrabMaxWeight*`. The converted
  items measured on 13 Oct weigh 10-50 kg (BurntBook01 25, CigarettePack 10, BobbyPinBox 50, trash can 15; vanilla
  median 10). All are under 100, so mass alone should not block a walking grab; the 50 kg box sits at the running
  limit. A force cap (`fZKeyMaxForce` 250) lifting 25-50 kg against gravity is a second suspect, **unresolved**:
  FO4 carries the same masses with a lower cap (175).
- **The experiment** (owner, in game): on one converted item that will not carry, `prid` it, `SetRigidBodyMass 5`,
  try to carry; then on another `SetGS fGrabMaxWeightWalking 1000` (`SetGS` / `GetGS` are console names in
  Starfield.exe; untested). Carries after either: mass is the gate and a converter rule (scale FO4 masses towards
  Starfield's distribution) is justified. Carries after neither: look at grab eligibility (motion type, layer,
  record type). The runner can read the grab through `Game.GetPlayerGrabbedRef()` (a Starfield Papyrus native) in a
  bridge probe.

## Unresolved

- Which Starfield NPC_ template gives Preston friendly combat behaviour; Starfield's ACBS mapping for Essential /
  Unique / ghost.
- Whether a quest target in a converted interior shows through our scripted (non-XTEL) doors.
- Whether the cog door's 43.3 s Stage2 clip and its 27 bodies survive the door-rig path in game.
- The grab gate's exact comparison (mass vs `fGrabMaxWeight*`, the force cap) until the owner's experiment.
- Whether the cut-down quest may force combat (FO4's own pattern) under the Phase B exit criterion.
