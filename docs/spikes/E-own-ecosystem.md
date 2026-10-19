# Spike E: Fallout 4 running as its own game inside Starfield (2026-10-19, Claude-cloud)

The owner, 2026-10-19 03:30Z: "I just want to get animations NPC's quest and the overall game in UI running within its
own ecosystem", then: "kind of away from Starfield as much as we can I don't want anything to be shipped like the gamma
launcher does with assets, but instead building that style of launcher with the assets you have", "Specifically with
the DLCS". Polish (heavy-physics movables, lighting tone, textures) waits until most of the game runs.

Status: plan only. Nothing here is built or tested. Labels as in docs/ai/research-log.md.

## 1. What "its own ecosystem" means here

- The player starts Fallout 4, not Starfield: a new game opens in Vault 111 (or the owner's chosen start) with no
  Starfield intro, ship, scanner, or Starfield quests running.
- Fallout 4's own NPCs, quests, dialogue, animations and interface run together, converted on the player's PC from
  their own Fallout 4 and all six DLC (Automatron, Wasteland Workshop, Far Harbor, Contraptions, Vault-Tec, Nuka-World).
- The launcher builds all of it locally and ships no assets (ROADMAP C1 constraint, the core-launcher plan section 2).
- Starfield.esm stays loaded because our plugins master it; "away from Starfield" means its content is kept out of play
  by our own override records and a start option, never deleted or patched (PLAN.md, #286).

## 2. Where we are (verified from the repo and project records)

| Area | Today | Gap to "own ecosystem" |
|---|---|---|
| NPCs | hand-built: one raider (FO4ActorRaider.esm), Preston and 5 raiders in FO4SFMission.esm, Codsworth on the mini bot skeleton | a bulk NPC_ converter: every FO4 actor base, its race, outfit, factions, AI packages, from Fallout4.esm + DLC |
| Bodies | Starfield Spacer looks for humans; Codsworth rebinds rigidly to a Starfield skeleton (`actor_rebind.py`) | FO4 human body and head on a Starfield human skeleton; creatures each need a skeleton route |
| Animations | none converted; `animation_curves.py` decodes NiTransformData only | FO4 animations (Havok .hkx) on Starfield's animation system; see section 3 |
| Quests | one hand-written cut-down quest (Min00) with a Papyrus poller instead of FO4's scenes and fragments | a bulk QUST/DIAL/INFO/SCEN converter plus FO4 script translation |
| Dialogue and voice | 20 Codsworth greetings converted to .wem | DIAL/INFO and every voice line routed by voice type |
| UI | none; no Pip-Boy | an FO4-style Pip-Boy, HUD and menus |
| Start | the player loads a Starfield save and uses coc | a new-game start in Vault 111 and Starfield's start quests held off |
| Launcher | plan only (L1 to L5, core-launcher plan); exp_install.py today | the GAMMA-style one-button build from the player's FO4 + DLC |

## 3. The hard parts, with what is known

1. **Animations (unresolved).** FO4 ships Havok 2014 packfiles (`hkpackfile.py` reads them). How Starfield stores and
   drives animation (its file format, behavior graphs and whether Havok behavior files can be added by plugins) has not
   been measured in this project. First task: inventory Starfield's animation files and one FO4 human walk cycle, and
   decide between retargeting FO4 clips onto Starfield's human skeleton and keeping Starfield's locomotion for humans
   at first (ACTOR-MILESTONE step 4 already allows native animation for the first proof).
2. **Papyrus (supported hypothesis).** Quests run on scripts. FO4 ships compiled .pex only; Starfield's compiler needs
   source. Route: decompile each FO4 .pex on the player's PC with an open-source decompiler (Champollion), map FO4 API
   calls that differ (Pip-Boy, workshop, perks, F4SE-free calls) to a shim script library we write, and recompile with
   the player's Creation Kit. Nothing decompiled is shipped. Needs a measured pass rate on a sample before committing.
3. **Records (verified tooling).** Mutagen reads every FO4 record type and writes Starfield QUST, DIAL, INFO, SCEN,
   PACK, NPC_ (raider-conversion.md section 4 lists what it cannot write for NPC_). The bulk converter generalises
   dotnet/Mission and dotnet/ActorRaider rather than starting over.
4. **UI (unresolved).** Whether Starfield's menus can be replaced or added from a plugin's interface files, and what
   format they use, is not yet measured. A Pip-Boy built as our own menu (original code and art, FO4's text and data)
   is the target; a Papyrus message-box Pip-Boy is the fallback for testing.
5. **Keeping Starfield out (supported hypothesis).** Override Starfield's start-game-enabled quests to off and add our
   own start quest that moves the player into Vault 111; hide Starfield HUD pieces only where the UI work shows how.
   Each override is listed so the vanilla profile restores Starfield untouched.
6. **DLC.** Each DLC esm is read as another source master with its own FormID range in our output (deterministic
   FormIDs, PLAN.md principle 6). DLC so far on the PC: DLCRobot, DLCworkshop01; the other four still need installing.

## 4. Order (bounded tasks; owner priorities first: Codsworth, the mission, the map)

| # | Task | Owner | Needs | Done when |
|---|---|---|---|---|
| E1 | Inventory: counts and samples of NPC_, RACE, QUST, DIAL, INFO, SCEN, PACK, IDLE, .hkx and .pex across Fallout4.esm and all DLC; Starfield's animation and interface file types | PC (read-only) | Fo4Export on the PC; the other 4 DLC installed | a table in this note with file, count and command |
| E2 | Papyrus round trip on 20 FO4 quest scripts (decompile, shim, compile) | PC + cloud | E1, Creation Kit | a pass rate and the failing call list |
| E3 | Animation route decision: one FO4 walk cycle on a Starfield human, or native locomotion first | cloud research, PC test | E1 | a go/no-go with a screenshot or log |
| E4 | Bulk NPC_ converter for humans (stand-in bodies allowed), then the FO4 human body | cloud | E1 | every Concord and Sanctuary actor placed; offline tests on synthetic masters |
| E5 | Bulk quest/dialogue converter, starting with Min00 and its DialogueConcordArea in full, replacing the hand poller | cloud | E2, E4 | Min00 plays with its own scenes and voice |
| E6 | Own start: new game in Vault 111, Starfield start quests held off | cloud | E5 | a new game reaches Vault 111 with no Starfield intro |
| E7 | Pip-Boy v0 (inventory, quests, map) | cloud research first | E1's UI rows | a go/no-go note |
| E8 | Launcher L1 to L3 grows a "build from FO4 + DLC" step that runs E4 to E6 | cloud | core-launcher plan | one command builds the set |

The mission, Codsworth and map threads keep their work; E5 replaces the hand-built mission only once it plays at least
as far, and the mission thread decides that swap.
