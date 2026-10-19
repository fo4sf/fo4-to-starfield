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

1. **Animations.** Verified (E1): FO4 ships Havok packfiles (14,128 .hkx in Fallout4 - Animations.ba2, 371 in
   DLCRobot, 49 in DLCworkshop01). Starfield - Animations.ba2 has no .hkx: 19,358 .af, 19,303 .afx, 390 .rig, 347 .agx
   graphs and 12 .xtbl tables (anim_events, anim_files, ...). So FO4 clips cannot be dropped in. Unresolved: the .af/.afx
   layout. Decision for now: humans and robots run Starfield's own locomotion on its rigs (ACTOR-MILESTONE step 4), and
   converting FO4 clips (hkx decode, then an .af writer) is its own spike that starts with one .af layout read.
2. **Papyrus (supported hypothesis).** Quests run on scripts. FO4 ships compiled .pex only; Starfield's compiler needs
   source. Route: decompile each FO4 .pex on the player's PC with an open-source decompiler (Champollion), map FO4 API
   calls that differ (Pip-Boy, workshop, perks, F4SE-free calls) to a shim script library we write, and recompile with
   the player's Creation Kit. Nothing decompiled is shipped. Needs a measured pass rate on a sample before committing.
3. **Records (verified tooling).** Mutagen reads every FO4 record type and writes Starfield QUST, DIAL, INFO, SCEN,
   PACK, NPC_ (raider-conversion.md section 4 lists what it cannot write for NPC_). The bulk converter generalises
   dotnet/Mission and dotnet/ActorRaider rather than starting over.
4. **UI.** Verified (E1): Starfield - Interface.ba2 holds 250 .swf and 29 .gfx (Scaleform, as FO4's interface is), e.g.
   interface\almanacmenu.swf, plus 3 .json data providers. Supported hypothesis: a menu of our own can be added as a
   loose .swf; unresolved: how a new menu is opened from Papyrus without SFSE. A Pip-Boy built as our own menu (original code and art, FO4's text and data)
   is the target; a Papyrus message-box Pip-Boy is the fallback for testing.
5. **Keeping Starfield out (supported hypothesis).** Override Starfield's start-game-enabled quests to off and add our
   own start quest that moves the player into Vault 111; hide Starfield HUD pieces only where the UI work shows how.
   Each override is listed so the vanilla profile restores Starfield untouched.
6. **DLC.** Each DLC esm is read as another source master with its own FormID range in our output (deterministic
   FormIDs, PLAN.md principle 6). DLC so far on the PC: DLCRobot, DLCworkshop01; the other four still need installing.

## E1 inventory (verified, PC job AR, 2026-10-19; read-only record-header walk, archives via fo4sf.ba2)

| esm | NPC_ | RACE | QUST | DIAL | INFO | SCEN | PACK | IDLE | VTYP |
|---|---|---|---|---|---|---|---|---|---|
| Fallout4.esm | 3015 | 45 | 1336 | 35443 | 78089 | 3568 | 3828 | 3025 | 531 |
| DLCRobot.esm | 235 | 8 | 112 | 1084 | 3649 | 184 | 99 | 224 | 16 |
| DLCworkshop01.esm | 38 | 23 | 15 | 1 | 3 | 0 | 5 | 7 | 0 |

Scripts (.pex): Fallout4 - Misc.ba2 7875, DLCRobot - Main.ba2 483, DLCworkshop01 - Main.ba2 43. DIAL and INFO match the
Codsworth picker's counts. Not installed: DLCCoast, DLCworkshop02, DLCworkshop03, DLCNukaWorld. Full output on the PC:
D:\Modding\scratch\e1_inventory\e1.md.

## AS file layouts (PC job AS, 2026-10-19; first 512 bytes of each, full dumps on the PC in D:\Modding\scratch\e1_inventory\as\dumps.txt)

- **.af** (verified: binary, no magic): `alert_idle.af` 1,513 bytes, `bipeda\animations\bleedout_walkforward.af` 27,740
  bytes. Supported hypothesis: a shared header (1.0f at 0x08, a float at 0x1c that may be the duration, 2.4186 for the
  walk, u16 5 at 0x28, then two counts), a u16 index list (bone or channel ids), then quantized keys or float curves.
  Writing .af needs this layout pinned down from several samples first.
- **.afx** (verified): plain XML beside each .af: state flag, tag, filename, prefix, and sound events by frame.
- **.rig** (supported hypothesis): `bipeda\characterassets\skeleton.rig`, 13,716 bytes, size at 0x04; per-bone records
  every 0x60 bytes with index, parent index (-1 for the root), a quaternion, a translation and an offset into a name
  table near 0x2e70. Readable enough to map FO4 bone names onto Starfield's for retargeting.
- **anim_files.xtbl** (verified): XML list of .af file names with a preload flag.
- **.swf** (verified): `interface\almanacmenu.swf` is a zlib SWF (CWS, version 12), Scaleform as in FO4.
- **.pex** (verified): FO4 scripts carry magic FA57C0DE, version 3.9, game id 2 and the original source path; Starfield's
  game id for comparison is unresolved.

Routes this sets: NPCs move with Starfield's own animations at first; FO4 clip conversion waits on an .af layout spike
(read the .rig names first, then several .af samples against their known durations); the Pip-Boy is a Scaleform menu of
our own; quest scripts go through decompile, shim and recompile (E2).

## 4. Order (bounded tasks; owner priorities first: Codsworth, the mission, the map)

| # | Task | Owner | Needs | Done when |
|---|---|---|---|---|
| E1 (done) | Inventory: counts and samples of NPC_, RACE, QUST, DIAL, INFO, SCEN, PACK, IDLE, .hkx and .pex across Fallout4.esm and all DLC; Starfield's animation and interface file types | PC (read-only) | Fo4Export on the PC; the other 4 DLC installed | a table in this note with file, count and command |
| E2 | Papyrus round trip on 20 FO4 quest scripts (decompile, shim, compile) | PC + cloud | E1, Creation Kit | a pass rate and the failing call list |
| E3 | Animation route decision: one FO4 walk cycle on a Starfield human, or native locomotion first | cloud research, PC test | E1 | a go/no-go with a screenshot or log |
| E4 | Bulk NPC_ converter for humans (stand-in bodies allowed), then the FO4 human body | cloud | E1 | every Concord and Sanctuary actor placed; offline tests on synthetic masters |
| E5 | Bulk quest/dialogue converter, starting with Min00 and its DialogueConcordArea in full, replacing the hand poller | cloud | E2, E4 | Min00 plays with its own scenes and voice |
| E6 | Own start: new game in Vault 111, Starfield start quests held off | cloud | E5 | a new game reaches Vault 111 with no Starfield intro |
| E7 | Pip-Boy v0 (inventory, quests, map) | cloud research first | E1's UI rows | a go/no-go note |
| E8 | Launcher L1 to L3 grows a "build from FO4 + DLC" step that runs E4 to E6 | cloud | core-launcher plan | one command builds the set |

The mission, Codsworth and map threads keep their work; E5 replaces the hand-built mission only once it plays at least
as far, and the mission thread decides that swap.
