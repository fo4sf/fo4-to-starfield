# 06: Fallout 4's own opening chain (MQ101, MQ102, the start of MQ103) and what our Vault 111 start must recreate

Written 2026-10-19 by Claude (research agent for the new-game phase). Web research plus a re-read of the project's
own offline evidence. No game, PC or GitHub was touched for this note, and nothing here was tested in game.

Labels, as in docs/ai/research-log.md:
- **verified** = a primary source says so, quoted or pinned with its URL, or the project's own read-only read of
  Fallout4.esm and the compiled `.pex` call lists (spike B4, `docs/spikes/B4-mission-anatomy.md`, 2026-10-17, which
  names its tools and files). "Verified" from a web page means only "the page says so": wiki pages are community
  sources built from the CK, not Bethesda documents. Quotes marked (fetch summary) were condensed by the fetch tool;
  re-read the page before quoting them elsewhere.
- **supported hypothesis** = inferred from sources, or player-level knowledge of FO4 that no page read today confirms.
- **unresolved** = not established; the last section says how each gets closed.

**Correction to the brief:** FO4's MQ103 is **"Jewel of the Commonwealth"** (form 000229E5), not "Jump in the
Water". **verified**: https://fallout.wiki/wiki/Jewel_of_the_Commonwealth infobox "Editor ID: MQ103", "Form ID:
000229E5", "Previous quest: Out of Time". A search for an FO4 quest named "Jump in the Water" found none.

## 0. Sources and what could not be read

Read today:
- The Fallout Wiki (fallout.wiki): https://fallout.wiki/wiki/War_Never_Changes , https://fallout.wiki/wiki/Out_of_Time ,
  https://fallout.wiki/wiki/Jewel_of_the_Commonwealth , https://fallout.wiki/wiki/Vault_111 ,
  https://fallout.wiki/wiki/Codsworth
- The Vault archive: https://fallout-archive.fandom.com/wiki/War_Never_Changes (infobox only; stage table empty)
- SKK, "SKK FastStart new game": https://www.nexusmods.com/fallout4/articles/1038
- Nexus article on giving items after the vault exit: https://www.nexusmods.com/fallout4/articles/1966
- Nexus forums: https://forums.nexusmods.com/topic/6445046-dear-mod-authors-that-put-stuff-into-the-player-inventory
  (2018) and https://forums.nexusmods.com/topic/9490328-how-to-script-activate-pipboy
- Fextralife Dogmeat: https://fallout4.wiki.fextralife.com/Dogmeat
- Project evidence: spike B4 (`docs/spikes/B4-mission-anatomy.md`), research log 2026-10-17,
  `docs/newgame/vault111-start.md`; sibling note `01-alternate-starts.md` in this folder (Start Me Up 18946, Redux
  70364, Skip 88418, SPECIAL Speed Start 99690, Fallout London reintegration 641, SKK FastStart 29227). Findings taken
  from note 01 say "(via note 01)"; its quotes and URLs are there.

Could not read (the WebFetch proxy answered HTTP 429, rate limited; none was retried):
- UESP https://en.uesp.net/wiki/Fallout_4:Out_of_Time (the fallout.wiki page was used in its place)
- https://fallout.fandom.com/wiki/Out_of_Time , https://fallout.fandom.com/wiki/War_Never_Changes ,
  https://fallout.wiki/wiki/Fallout_4_quests
- https://www.nexusmods.com/fallout4/mods/105204 , https://nexusmods.com/fallout4/articles/1827
- https://forums.nexusmods.com/topic/6963656-true-alternative-start-framework-need-scripting-helpadvice ,
  https://forums.nexusmods.com/topic/10308183-execute-script-when-mq102-stage-1-is-completed-player-exit-vault
- https://steamcommunity.com/app/377160/discussions/0/1637536330460549316
- https://eip.gg/fallout4/guides/fallout-4-out-of-time-quest-walkthrough/
- gamerguides Out of Time: refused by the session's permission check, not by the site.
- The FO4 Creation Kit wiki page read (ck.uesp.net quest-startup tutorial) had nothing on start-game quests.

**What is missing:** the wiki stage tables list only the stages that have a log entry or objective. MQ102 has 54
stages (B4), so most of them (Codsworth's scenes, the insects, Dogmeat, the radios) have no number here. The full
table with fragments is cheapest to get offline on the PC (question 1).

---

## 1. The chain in records

| quest | editor id | form id | role | evidence |
|---|---|---|---|---|
| War Never Changes | `MQ101` | 0001ED86 | pre-war house, the mirror, Codsworth (pre-war), the Vault-Tec Rep and SPECIAL, the run to the vault, the pod | **verified**: fallout.wiki War_Never_Changes infobox "Editor ID: MQ101", "Form ID: 0001ED86", reward "Vault 111 Jumpsuit"; the fragment `QF_MQ101_0001ED86` (via note 01, Fallout London) |
| Out of Time | `MQ102` | 0001CC2A | **the driver** from the pod to Concord: the Vault 111 exit, Codsworth, the Sanctuary search, Concord, the museum, the power armor | **verified**: fallout.wiki Out_of_Time ("Editor ID: MQ102", "Form ID: 0001CC2A", rewards incl. "Pip-Boy 3000 Mark IV", Codsworth and Dogmeat as companions); B4: 54 stages, 19 objectives, 73 aliases, no dialogue of its own |
| When Freedom Calls | `Min00` | 001A001C | the Pip-Boy face of Concord; logic in MQ102 | **verified** (B4) |
| (museum fight) | `DN092` | 0001D806 | raiders, waves, deathclaw | **verified** (B4) |
| (dialogue) | `DialogueConcordArea` | 000179F3 | Preston and the settlers; stage 200 sets MQ102 200 and Min01 50 ("Sanctuary") | **verified** (B4) |
| Jewel of the Commonwealth | `MQ103` | 000229E5 | go to Diamond City; "Given by: Mama Murphy or Irma" | **verified** (fallout.wiki) |

Naming note (**verified**, B4): MQ102's quest script is `MQ03QuestScript` and its console script
`MQ03ControlPanelScript`; the pre-war Codsworth is `MQ101PrewarCodsworth` (**verified**, fallout.wiki Codsworth).
**supported hypothesis**: the scripts keep an older numbering (MQ01 to MQ03) from before the MQ1xx renumbering, so
search FO4 sources under both spellings.

### 1.1 MQ101 "War Never Changes": stages

**verified**, fallout.wiki War_Never_Changes, the page's table (stage: description):
10 Create character; 20 Player allowed to walk around house; 30 Walked into den and trigger Codsworth; 80 Codsworth
goes to Shaun; 90 Vault-Tec Rep rings doorbell; 100 Talk to Vault-Tec Rep; 200 Choose S.P.E.C.I.A.L. stats and choose
name; 220 Go to Shaun; 240 Activate mobile; 260 Investigate television; 400 Get to the vault; 450 Talk to the gate
guard; 470 Get on the platform; 620 Take a suit; 680 Follow the scientist; 700 Comfort Shaun; 710 Get in the pod;
**1000 Quest completed**; **5000 (failed) Player leaves area - world ends**. The page also notes "The quest does not
appear in the Pip-Boy."

Stages that are not in that table but are pinned elsewhere:

| stage | what | evidence |
|---|---|---|
| 0 | `PlayerREF.RemoveAllItems()` while the game goes from the main menu through the intro video to the mirror | **verified** (fetch summary), article 1038 |
| 20 | SKK FastStart "intercepts MQ101 at Stage(20) to take control and bypass the Stage(900) inventory clear down" | **verified**, article 1038 |
| 770 | Skip's trigger sets 770 "so the cryo corpses spawn properly" (v001 used 900) | **verified** via note 01 |
| 900 | the move from the pre-war to the post-war vault; `RemoveAllItems()` again. Forum: "don't mess with the inventory before or on mq101 stage 900"; SKKmods: "The base game clears the player inventory between pre-war sanctuary and vault 111", a `RemoveAllItems` in MQ101's fragment | **verified**, article 1038 and forum 6445046 |
| 1000 | completion (table above); London's reintegration lets MQ101 reach 900 and 1000 | **verified** |
| the cryo cut scene, the Kellogg scene | between 710 and 900 | **unresolved**: numbers not read |

FO4 has an `MQ101Debug` global like Starfield's: **verified** via note 01 (Skip advances "by changing the
MQ101Debug global"). What its values do in FO4: **unresolved**.

### 1.2 MQ102 "Out of Time": stages

The wiki's table (**verified**, fallout.wiki Out_of_Time; stage: description): **1 Exit Vault 111**; **10 Go home**;
20 Talk to Codsworth; 30 Search the Neighborhood with Codsworth; 32 and 34 Kill the Insects; 55 Investigate Concord;
65 "Quest complete" (marked with the finished icon).

Combined with the ESM read and the mod authors:

| stage | what sets it / what it does | evidence |
|---|---|---|
| 0 | start; SKK SyntheticPlayer sets 0, 10 and 15 done | **verified**, article 1038 |
| 1 | objective "Exit Vault 111" | **verified**, fallout.wiki |
| 5 | the cog door console used **without** a Pip-Boy: stage 5 and a fail sound | **verified** (B4) |
| 6 | Fallout London's reintegration teleports into Vault 111 and starts MQ102 at 6 | **verified** via note 01; its meaning **unresolved** |
| 7 | console **with** Pip-Boy: the player is seated at `Vault111DoorConsoleFurnitureREF` 00054FED for the plug-in | **verified** (B4) |
| 9 | the button: klaxon, `Vault111ExitDoorREF01/02` closed, then the gear door opens | **verified** (B4) |
| 8 | set later in the gear-door sequence | **verified** (B4); meaning **unresolved** |
| 10 | **"Go home"**; set by `Vault111OneShotExteriorElevatorTrigger` 00051877 (`vaultExitCommonWealthSCRIPT`) on the surface. Forum: "the stage set the moment the elevator reaches the top on Vault Exit"; article 1966 checks `MQ102.GetCurrentStageID() >= 10` as "exit the vault" | **verified** (B4; forum 6445046; article 1966) |
| 15 | **"Radios on"**; Redux: 10 triggers 15 (radio, Brotherhood signal) | **verified**, article 1038; via note 01 |
| 20 / 30 / 32 / 34 | Codsworth, the neighbourhood search, the insects | **verified** (wiki) |
| 55 | one of 4 exterior Concord triggers `MQ102SetStage55Trigger01-04REF`: starts Min00, sets DN092 1; "Investigate Concord" | **verified** (B4, wiki) |
| 65 to 140 | museum steps, each mirrored into a Min00 stage | **verified** (B4) |
| 150 | enables `MQ102PostquestEnableMarker` | **verified** (B4) |
| 200 | set by DialogueConcordArea 200 with Min01 50 | **verified** (B4) |

Conflict, **unresolved**: the wiki marks 65 as "Quest complete", but B4 found MQ102 fragments running to 200 and
setting Min00's stages. **supported hypothesis**: MQ102's displayed part ends at 65 and Min00 carries the display,
while MQ102 itself keeps running as the logic quest; which stage calls `CompleteQuest` / `Stop` is read offline.

### 1.3 MQ103 "Jewel of the Commonwealth" (the start only)

**verified** (fallout.wiki): 10 Go to Diamond City; 20 Find information about Shaun; 25 Found information about
Shaun; 30 Go to Valentine's Detective Agency; 100 complete, "Trigger Unlikely Valentine". Starts "at the conclusion
of When Freedom Calls", from Mama Murphy, or on first reaching Diamond City (fetch summary). Out of Time's "Next
quests" are Jewel of the Commonwealth and When Freedom Calls (**verified**, fallout.wiki Out_of_Time).

---

## 2. What each part gives or sets

| item | what FO4 does | label |
|---|---|---|
| Inventory wipe | MQ101 0 and 900 call `RemoveAllItems()` | **verified** (article 1038, forum 6445046) |
| Vault 111 Jumpsuit | MQ101's reward; "The player is given a Vault 111 Jumpsuit" (stage 620 "Take a suit"); more jumpsuits lie in the post-war vault | **verified** (fallout.wiki War_Never_Changes, Vault_111) |
| SPECIAL and name | chosen at the door with the Vault-Tec Rep (MQ101 200); the exit elevator offers them again: `vaultExitElevatorSCRIPT` disables controls and "shows the SPECIAL and looks menus" | **verified** (wiki; B4) |
| Looks | the bathroom mirror (MQ101 10) | **verified** (wiki) |
| "You're SPECIAL!" book | sits by Shaun's crib in the pre-war house | **verified** (wiki, fetch summary). That reading it gives one SPECIAL point once: **supported hypothesis** |
| Pip-Boy 3000 Mark IV | on a scientist's skeleton beside the vault door: "The player can remove the Pip-Boy 3000 Mark IV from their remains and equip it." Listed as an Out of Time reward | **verified** (fallout.wiki Out_of_Time, Vault_111). **Correction candidate:** `docs/newgame/vault111-start.md` §4 says "no Pip-Boy until the overseer's office"; the wiki places the skeleton beside the vault door (the cog door). Which is right is read from the cell offline (question 4) |
| Weapons and loot | two 10mm pistols, two security batons, the Cryolator (Master-locked case in the overseer's office), four Stimpaks, jumpsuit boxes at security; the pistols and batons "always auto-equip when picked up" | **verified** (fallout.wiki Vault_111). That these are placed loot, not quest `AddItem`s: **supported hypothesis**; the auto-equip suggests a script on the items (**unresolved**) |
| Input layers | "The new game start scripts do disable player menu controls with an InputEnableLayer"; "There is also an InputEnableLayer used to disable the PipBoy on the MQ102 quest" (SKKmods) | **verified**, forum 9490328 |
| Time scale | a fast start "fixed a time-scale problem that stopped the Concord Preston scene" | **verified** via note 01; which globals MQ101/102 touch is **unresolved** |
| Map markers | Vault 111 has a vault-icon marker | **verified** that it exists (wiki); what MQ102 reveals (Sanctuary, Red Rocket, Concord) is **unresolved** |
| Radio | on at MQ102 15 | **verified** (article 1038) |
| Codsworth | companion; "permanent Companion", Robot Sympathy perk, recruitable "upon reaching a trigger point in Concord during Out of Time" (fetch summary); speaks the player's name if it is on his list | **verified** (fallout.wiki Codsworth) |
| "Hi Honey!" holotape | Codsworth may hand it over in Sanctuary | **verified** (fallout.wiki Out_of_Time, fetch summary) |

---

## 3. What in the Commonwealth listens to the chain

| system | gate | label |
|---|---|---|
| Mods and Creation Club | "Many mods start their processing at MQ102 Stage(10), the vault exit elevator, or Stage(15), 'Radios on.' Creation Club content also triggers its quests there" | **verified**, article 1038 |
| Items from mods | wait for MQ102 10 or `MQ101.IsCompleted()`; SKKmods: "some mods are active in V111 so the player needs tapes on cryo wakeup" | **verified**, forum 6445046, article 1966 |
| Radio | MQ102 15 | **verified** |
| Workshops | `WorkshopParentScript` needs "TWO MINUTES" after the looks menu for its registrations | **verified**, article 1038. Sanctuary's workbench tied to Min01 "Sanctuary": **supported hypothesis** (B4 shows Min01 50 set from Concord) |
| Minutemen | MQ102 55 starts Min00; DialogueConcordArea 200 sets Min01 50 | **verified** (B4) |
| Codsworth | MQ102 20/30/32/34. Notes: clearing Sanctuary first sends the player straight to Concord; removing the bloatflies by console "can break his dialogue and block progress"; reaching Concord first makes him a companion at once; reaching Diamond City first, talking to him recruits him and skips the insects; finishing the main quest first gives unique Shaun lines. Bug: he may stop searching | **verified** (fallout.wiki Out_of_Time, fetch summary); SKK: sprinting to Sanctuary before MQ102 catches up can "glitch Codsworth dialogue" (article 1038) |
| Preston at the museum | MQ102 aliases, `SetGhost(False)` at 85, door unlocked at 88 | **verified** (B4) |
| Dogmeat | "found outside Red Rocket Truck Stop, south of Sanctuary"; Nick Valentine introduces him later if skipped | **verified** (fextralife). Whether an MQ102 stage enables him: **unresolved** (B4 lists "dogs" in MQ102's content) |
| Random encounters | no source read | **unresolved** |
| `OnLocationChange` fallbacks | "the Vault111 location spans both the internal vault and the external vault elevator areas, so it will not trigger until the player is moving down the hill" | **verified**, article 1038 |

---

## 4. Vault 111 specifics

**verified** (B4, Fallout4.esm, cell Vault111Cryo 000016D8) unless marked:
- **Pods.** The player's `MQPlayerCryopodREF` 0004A011, the spouse's `MQPlayerSpousePodREF` 0004A012
  (vault111-start.md §4). Corpses in the other pods depend on the MQ101 stage reached (Skip, via note 01). Later, the
  spouse's pod can be opened; "Opening any other pod, or closing the Sole Survivor's pod, triggers 'Malfunction in
  cryo pod manual release override'"; the Wedding Ring is on the spouse's body (**verified**, fallout.wiki Vault_111,
  fetch summary). Bug: not taking the ring during Out of Time still triggers "I'll find Shaun" on a later return.
- **Cog door.** `MQ102GearDoorConsoleREF` 00091A49 (`MQ03ControlPanelScript`). Without a Pip-Boy: stage 5 and a fail
  sound. With it: stage 7 seats the player, the panel plays `Stage2`; the second activation (`DepressButton`) sets 9,
  klaxon, panel `Stage3`, closes `Vault111ExitDoorREF01/02`, registers for "stage4", then plays `Stage2` on
  `Vault111GearDoorREF` 000330C3 (ACTI `VltGearDoor01`), enables klaxon, strobes, `V111ExitLightingEnableMarker`
  002075E4 and music, and later sets 8. The gear-room gate `V111GearRoomGate01` is separate.
- **Elevator.** `vaultExitElevatorDown` 00020C3A brings `V111ElevatorREF` 000244EB down; `RespecTriggerREF` 0008C94A
  (`vaultExitElevatorSCRIPT`) disables controls, shows the SPECIAL and looks menus, rides up 21.6 m and fades; the
  automatic load door `Vault111InteriorAutoLoadDoorREF` 0001F180 (`AutoloadDoorNoText`) takes the player to 000998E3;
  `Vault111OneShotExteriorElevatorTrigger` 00051877 sets MQ102 10.
- **Overseer's office.** Overseer's and security terminals with logs that end abruptly; the Cryolator case; pod
  listings with known inconsistencies (B1-B6 vs C9-C14; C3) (**verified**, fallout.wiki Vault_111, fetch summary).
  Whether any terminal entry is needed for the exit: **supported hypothesis** none (the exit needs only the Pip-Boy).
- **Returning.** Re-entry by "a red button in the command station next to the entrance" and standing on the platform
  (wiki); in records `Vault111DescendAgainTrigger` (clips `stage6`/`stage8`), `Vault111AscendAgainTriggerREF` 0009A149
  (`VaultElevatorAscendAgainScript`, initially disabled), the same auto-load door pair, and a companion failsafe pair
  00248AAD / 00248AAE (B4). "Items left in the Vault stay there indefinitely" (wiki). SKK FastStart keeps the vault
  animations (elevator, gear door, spouse) primed so the player can return (via note 01). Later story ties: Kellogg's
  orders and the vault are in *Dangerous Minds* (wiki): **unresolved** for our design.
- **Known bug at the pod.** "the player may be unable to move or save after first leaving the cryo chamber"
  (**verified**, fallout.wiki War_Never_Changes, fetch summary); with SKK's note on InputEnableLayers this points to a
  start-up input layer not released (**supported hypothesis**).

---

## 5. Scripts, and what is said to be hardcoded

| script / record | role | label |
|---|---|---|
| `QF_MQ101_0001ED86` | MQ101 fragments, incl. `RemoveAllItems` at 0 and 900 | **verified** name (via note 01) and calls (article 1038; forum 6445046 cites "line 1722" of the fragment) |
| `QF_MQ102_0001CC2A` | MQ102 fragments (120 properties) | **verified** (B4) |
| `MQ03QuestScript`, `MQ03ControlPanelScript` | MQ102's quest script; the cog door console | **verified** (B4) |
| `vaultExitElevatorDownSCRIPT`, `vaultExitElevatorSCRIPT`, `VaultElevatorAscendAgainScript`, `vaultExitCommonWealthSCRIPT` | the elevator chain | **verified** (B4) |
| `MQ102PowerArmorScript`, `MQ102PrestonActorScript`, `MQ03RaiderAliasScript`, `DN092QuestScript`, `DIalogueConcordScript`, `QF_Min00_001A001C` | Concord | **verified** (B4) |
| `WorkshopParentScript` | workshop registration, about two minutes after the looks menu | **verified** (article 1038) |
| `MQ101Debug` GLOB | debug start lever | **verified** exists; values **unresolved** |

Sources: B4 found only compiled scripts in `Fallout4 - Misc.ba2` (**verified**); that FO4's Creation Kit ships the
vanilla Papyrus sources as a zip is a **supported hypothesis** for the PC check.

Engine-hardcoded claims:
- "MQ101 is hardcoded in Fallout4.exe": **unresolved**; no page read today says so. Against a full hardcode: SKK,
  Skip, Start Me Up and London all bypass MQ101 with stages, records and scripts. **supported hypothesis**: the engine
  owns the new-game sequence (main menu, intro video, then the start-game-enabled quests), the looks and SPECIAL
  menus (called from script), and per Skip "an engine image space modifier" white flash (via note 01).
- No Papyrus call opens the Pip-Boy: "As far as I know, there is no papyrus solution for opening the Pipboy, at all"
  (**verified** as a forum claim, forum 9490328).
- INI keys `sStartingQuest` / `SCharGenQuest`: **unresolved**; a search found no source for either in FO4 or
  Starfield. **supported hypothesis**: the start is record-driven (start-game-enabled quests; Starfield's
  `StartupQuest_DO`, via note 01). A string search of both executables settles it (question 21).

---

## 6. How FO4 alternate starts reproduce the exit, and what broke

**verified** from the pages named (article 1038 directly; the rest via note 01):
- **SKK FastStart:** takes over MQ101 at 20, skips the 900 wipe, completes MQ101, sets MQ102 10 and 15. Rebuilt "from
  a sweet and simple linear single script to split multi thread at vault exit"; MQ102 can take "several minutes to
  return stages", causing "missed scenes and out-of-sequence triggers".
- **SKK SyntheticPlayer:** takes over MQ101 at 0, completes it, sets MQ102 0, 10 and 15.
- **SKK's listener template:** checks "in the Commonwealth", MQ102 >= 10, MQ102 >= 0 or MQ101 complete, else
  registers for OnStageSet (MQ101, MQ102) and OnLocationChange, with a one-shot guard. Its stated blind spot: an
  alternate start that skips MQ102 and begins in an interior or another worldspace. **Our start is that case.**
- **SKKmods on input:** re-enables controls on the MQ101 layer, re-enables the Z key and deletes the layer
  (forum 9490328, paraphrase of the thread).
- **Start Me Up / Redux:** sets "all of the MQ101 and MQ102 stages"; Redux waits 20 s in the Commonwealth before MQ102
  10; added an MQ101 stop stage to clean aliases; disables vault activators that must not work. Known: missing radio,
  Codsworth skipping his search, Preston's museum door, frozen Nate/Nora outside the pod.
- **Skip:** MQ101 900, then 770 for the corpses; a variant gets the SPECIAL menu on exit; skipping chargen leaves the
  default male body.
- **SPECIAL Speed Start:** a time scale left wrong stopped the Concord scene.
- **Fallout London reintegration:** a one-shot teleport into Vault 111 starts MQ102 at 6.

Lessons for us (**supported hypothesis**): (a) Starfield has no FO4 MQ102, so the listener problem is reversed:
whatever we port later that listened to MQ102 1/10/15 needs our own "out of the pod", "left the vault" and "radios
on" signals; (b) stagger work after the exit; (c) disable what must not work in the vault (pods, the spouse scene);
(d) release any input layer and reset any time scale or global our start touches; (e) do not wipe inventory in a way
that eats items other content gave in the vault.

---

## 7. Recreate or leave out (draft for the owner)

| FO4 piece | our plan today (vault111-start.md) | suggestion |
|---|---|---|
| Pod exit cut scene, Kellogg | none | leave out in phase 1 |
| Pip-Boy from the skeleton, console plug-in | none; the console opens the door without it | keep; record it as a deliberate difference |
| Inventory wipe (MQ101 0/900) | none | owner decision on Starfield's starting inventory (question 7) |
| Jumpsuit, 10mm, baton, Stimpaks | none | converted placed loot would cover it once the items convert |
| SPECIAL and looks on the elevator | looks in the vault via `Game.ShowRaceMenu()` | owner decision on a second offer at the elevator |
| MQ102 1 / 10 / 15 | the quest completes on the exit | publish our own stages at the same moments |
| Returning into the vault | not handled | needed before the vault is a place to go back to |
| Codsworth, Dogmeat, Concord | later phases (B2/B4) | gate them on our exit stage, not on MQ102 |

---

## Questions for our design

| # | question | why it matters | how it gets answered |
|---|---|---|---|
| 1 | What are all 54 MQ102 stages, with their fragments, and which stage calls `CompleteQuest`/`Stop` (the wiki says 65, B4 sees 200)? | the wiki lists only 10 log stages; we need the full list to choose which moments our start mirrors | offline read of Fallout4.esm (the B4 walker) plus the fragment call lists, or the CK source zip on the PC |
| 2 | Which MQ101 stages fall between 710 and 1000 (the cryo scene, Kellogg, 770, 900), and what does each fragment do? | Skip shows corpses depend on 770; 900 wipes the inventory; we must know what state the vault expects | offline read of `QF_MQ101_0001ED86` |
| 3 | What does MQ102 stage 6 mean, and is it the right model for "player stands outside the pod"? | London starts MQ102 at 6 after a teleport, the closest precedent to our start | offline read of the stage-6 fragment and its conditions |
| 4 | Where exactly is the Pip-Boy skeleton: beside the cog door (wiki) or in the overseer's office (our doc)? | `docs/newgame/vault111-start.md` §4 may need a public correction | offline read of Vault111Cryo's placed refs (the Pip-Boy item and the skeleton) |
| 5 | Do we ever give a Pip-Boy-like item in the vault, or is the console open without one for good? | decides whether the cog door needs a "fail without it" branch like FO4's stage 5 | owner decision |
| 6 | Do we show SPECIAL (or a Starfield equivalent) at all, and where: in the vault, or on the elevator like `vaultExitElevatorSCRIPT`? | FO4 offers SPECIAL and looks twice (the door, the elevator) | owner decision, then an in-game test of the menu we call |
| 7 | Do we clear Starfield's starting inventory, and when, so that it does not eat items other content gives in the vault? | FO4's two `RemoveAllItems` broke many mods | owner decision; in-game test of what Starfield's new game hands the player |
| 8 | What do we name and number our own "out of the pod", "left the vault" and "radios on" stages, and do we document them as a public contract? | FO4 content and mods hang on MQ102 1/10/15; our later ports need the same hooks | owner decision, recorded in docs/ai/decisions.md |
| 9 | When the player is put in the pod, does any Starfield input layer (from MQ101 or MQ00) stay active? | FO4's start scripts disable controls with layers; a leftover layer gives the "cannot move or save" bug | in-game test: Starfield's console layer dump (if it has one) and a move/save check after our start |
| 10 | Does our start change or depend on the time scale or other globals Starfield's opening sets? | a wrong time scale stopped the Concord scene in an FO4 fast start | offline read of MQ101's Starfield fragments for `SetValue` on globals; in-game `GetGlobalValue TimeScale` |
| 11 | Which map markers must be known when the player reaches the surface (Vault 111, Sanctuary, Red Rocket, Concord)? | FO4 reveals some on exit; our Commonwealth map must not start blank or full | offline read of MQ102's fragments for `AddToMap`; owner decision |
| 12 | What should happen if the player goes back down the elevator? | FO4 supports returning (descend trigger, ascend-again trigger, failsafe doors); ours does not yet | owner decision; then an in-game round trip with save and reload |
| 13 | Do the other cryo pods hold corpses in our converted vault, and which FO4 stage state did the converter capture? | Skip needed 770 for the corpses; a static conversion may carry an odd state | offline read of the port's Vault111Cryo refs vs FO4's enable parents; in-game look |
| 14 | What do we do with the spouse's pod and the Wedding Ring? | FO4 lets it open while other pods give a "Malfunction" message; the ring gates a later line | owner decision (story scope of phase 1) |
| 15 | Is the cog door's "player seated at the console" sequence wanted, or only the door opening? | B4 put the seat, plug-in and klaxons out of B1 | owner decision |
| 16 | How long do our exit and the Commonwealth's start-up scripts take, and do we need to stagger them like SKK and Redux (20 s, 2 min)? | FO4's exit is the busiest script moment; backlogs caused missed scenes | in-game test with log timestamps from `fo4sf_newgame.0.log` |
| 17 | Which converted Commonwealth content (workshops, radio, encounters) will check "has the player left the vault", and against what? | without MQ102, ported conditions on it will be false forever | offline survey of ported records' conditions referencing MQ101/MQ102 (CTDA on GetStage / GetStageDone) |
| 18 | When Codsworth arrives (later phase), which MQ102 states must we fake so his lines and the search do not break? | the wiki lists four ordering cases and two bugs | offline read of Codsworth's INFO conditions on MQ102; owner decision on scope |
| 19 | Is Dogmeat enabled by an MQ102 stage or placed from the start at Red Rocket? | if a stage enables him, he will not exist in our world | offline read of Dogmeat's REFR enable parent and MQ102 aliases |
| 20 | Does anything in FO4's opening depend on the player's name or sex (Codsworth's name list, the spouse)? | Starfield's player is silent and its chargen differs | offline read of the conditions; owner decision |
| 21 | Do `sStartingQuest`, `SCharGenQuest` or similar strings exist in Fallout4.exe or Starfield.exe? | would offer a cleaner start lever than stopping MQ00/MQ101 | offline strings search of both executables on the PC |
| 22 | What do FO4's `MQ101Debug` values do, and does Starfield's lever have a matching design? | both games have the global; values may skip the intro cleanly | offline read of the MQ101 scripts that read it (FO4 sources, Starfield ContentResources.zip) |
| 23 | Which MQ103 start route do we keep (Mama Murphy, the end of When Freedom Calls, reaching Diamond City)? | the main story's next step depends on Concord, which is a later phase | owner decision |

