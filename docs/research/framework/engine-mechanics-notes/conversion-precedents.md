# Conversion precedents for game mechanics: research findings and question framework

Written 2026-10-19 by a wave-3 research agent (Claude-cloud), area **conversion-precedents-mechanics**. It builds on
[../findings/precedents.md](../findings/precedents.md) (history, schedules, legal, launcher lessons) and
[../engine-mechanics.md](../engine-mechanics.md) and does not repeat them. This page is about **mechanics**: how earlier
total conversions moved quests, dialogue, scripts, companions, menus and other systems from one engine to another, what
they automated, what they rebuilt by hand, and what broke.
Labels: **verified** (read on the source page or in the file), **supported hypothesis**, **unresolved**.
Method: web pages via WebSearch, WebFetch and TinyFish; two GPL-3 repositories (BACUP and py-creation-lib) and one MIT
README (tes4skyrim) read as code, shallow clones in the session scratchpad, no game data. Not reachable this run:
geckwiki.com directly (read through WebFetch only), the Morroblivion forum thread on Skywind quest conversion (HTTP 400),
two fallout.wiki pages (timeouts), mod.pub's TTW main page through one fetcher (bot block; a second URL worked).

**Bottom line for mechanics.** Two new precedents change the picture. (1) **BACUP already has a `fo4:starfield` pair
in code**: a world-only FO4 to Starfield translation map, a structured CELL/REFR writer, a FO4 LAND to Starfield `.btd`
terrain writer, struct relayouts and a spatial rescale (GPL-3, commit of 2026-10-17). Its README says only three pairs
are wired; the code says otherwise. It fences out quests, dialogue, NPCs, packages, perks and Story Manager for this
pair. This corrects wave 2 ("no pair targets Starfield"). (2) **tes4skyrim** (MIT, pre-alpha, 2026) converts Oblivion,
Morrowind, FO3 and FNV into Skyrim SE on the player's PC **including quests, dialogue, scripts and voice with lip
sync**, plus SKSE plugins for the engine behaviour Skyrim lacks. Both are mostly one-author, AI-assisted projects. Across
all precedents the mechanics lesson is the same: records and links convert automatically, **behaviour does not**. Every
project ended up with (a) a function map from source script calls to target calls with an explicit "unmapped" policy,
(b) hand-written fills for scripts that do not port, (c) small native plugins for engine behaviour the target lacks,
(d) rebuilt "joins" where a source system has no target record, and (e) a separate QA pass per quest. Saves break on
updates because Papyrus stores script properties in the save (Fallout London 1.03 needed a new game).

## What the community and tools offer today

### BACUP and py-creation-lib (Bryant-21, GPL-3)
- **Scope.** "converts records and assets from one Bethesda / Creation Engine game to another", with per-game schemas
  for FO3, FNV, FO4, FO76, Skyrim SE and Starfield, a Rust core running "a registry of phases", Python orchestration
  and an ImGui UI. README lists three pairs (fo76:fo4 most complete, fnvfo3:fo4 partial, skyrimse:fo4 early).
  Version file 0.9.1.0; last commit 2026-10-17 ("1.9.1.0"); 23 stars, 15 commits on the shallow history. **verified**
  ([README](https://github.com/Bryant-21/bacup); repo files `README.md`, `VERSION`, `LICENSE` = GPL-3)
- **A `fo4:starfield` pair exists in code, world only.** `source_pairs.py` defines `"fo4:starfield"` (source
  `Fallout4.esm`, output `Fallout4_SF.esm`) and states: "fo4:starfield and starfield:fo4 always convert world-only
  (exteriors and interiors; no quests, NPCs, or actors)". Its exclude fence lists ACHR, AMMO, ARMO, CSTY, DIAL, ENCH,
  FURN, INFO, LVLN, NPC_, OMOD, PACK, PERK, QUST, RACE, SCEN, SMBN, SMEN, SMQN, SPEL, TERM, WEAP and others. The
  translator registers `(Game::Fo4, Game::Starfield) => Fo4StarfieldHook`, and `scripts/regen.py --pair` accepts every
  defined pair. **verified** (files `bacup/py_bacup_lib/python/bacup_lib/source_pairs.py`,
  `native/conversion/src/translator/mod.rs` line 39, `scripts/regen.py` line 938)
- **What the FO4 to Starfield map does.** `embedded/translation_maps/fo4_to_starfield.yaml` (744 lines) covers WRLD,
  CELL, REFR, STAT, SCOL, MSTT, ACTI, LIGH, TXST, LTEX, MATT, WATR, KYWD, MUSC, MUST, REGN, LGTM, ASPC. Its header says
  the output starts as "a FULL CLONE of the source record's fields", so any subrecord whose layout differs "MUST be
  explicitly dropped", and the `drop:` lists are "built from a codec-by-codec comparison of the two generated schemas".
  It skips WTHR and CLMT (references are repointed at vanilla Starfield forms, e.g. `DefaultClimate (00015F)`) and
  SNDR/SNCT/SOPM ("no Starfield record type at all"). It states a spatial constant `FO4_TO_SF_SPATIAL = 1.0 / 69.99125`
  applied by hooks and phases, not by the map. **verified** (file read). Whether the output loads and plays in
  Starfield is **unresolved**: the referenced design docs (`bacup/docs/starfield_target/R1..R4`) are not in the public
  repo, and no in-game evidence was found.
- **Struct relayout hook.** `pair_hooks/fo4_starfield/mod.rs` rebuilds five FO4 subrecords in Starfield shape
  (`LIGH.DATA` to `DAT2`, `SCOL.ONAM`, `WATR.DNAM`, `LGTM.DATA`, `LGTM.DALC`) with unit tests asserting target widths
  (LIGH DAT2 76 bytes, WATR DNAM 152, LGTM DATA 108, DALC 24). **verified** (file read; widths are BACUP's claims,
  not checked against our xEdit dumps)
- **Starfield world phases.** `phase/starfield_cells.rs` (1,469 lines) writes the vanilla GRUP topology for exterior
  blocks and interior cells "measured against `Starfield.esm`"; `phase/terrain_btd.rs` (1,782 lines) writes "FO4 LAND
  -> Starfield `.btd`" and synthesizes the `SFBK` and `WRLD` linkage records; `starfield_navmesh.rs` (342 lines) exists.
  **verified** that the files exist and say this; behaviour **unresolved**.
- **Script conversion (FO76 to FO4).** Scripts are decompiled by BACUP's own Rust decompiler (`papyrus_core`, in
  py-creation-lib) and recompiled with the target game's `PapyrusCompiler.exe` in one `-all` batch process ("One CLR
  instead of W concurrent ones bounds RAM"). FO76 ships many client scripts "with their bodies stripped server-side",
  so BACUP keeps a folder of hand-written method fills spliced into the decompiled skeleton: 6,714 generated sources,
  2,514 patch files, 3,977 "unpatched candidates" listed as a review queue. Rule: "No game Papyrus. Files here MUST be
  original code." **verified** (`script_patches/README.md`, `workflows/unified.py` around line 5536,
  `native/conversion/src/script_conversion.rs`)
- **Moving scripts to a carrier the target can hold.** FO76 player scripts were "attached to the player's `NPC_`
  record. FO4 cannot carry that record, so they become `ReferenceAlias` scripts on ... `PlayerRef` alias. Every member
  that used `Self` as the actor must be replaced". **verified** (same README)
- **What broke, in their own words.** A missing compiler made every script "fail", and the step that strips a record's
  script binding after a failed compile "silently gutted a shipped ESM of 13624 bindings"; they now assert toolchain
  health first. **verified** (`workflows/unified.py` around line 2218)
- **Legacy script translation (FNV to FO4).** A lexer, parser, semantic and emitter pipeline turns GECK script into
  Papyrus `.psc`, driven by `fnv_to_fo4_script_functions.yaml` (56 entries; shapes `papyrus`, `expansion`,
  `rewrite: drop_with_warning`, e.g. `RewardKarma`, `GetIsCurrentWeather`) and `fnv_to_fo4_actor_values.yaml`
  (Karma, RadiationRads, Hunger, Thirst, Sleep map to `null`). The default policy for an unmapped function is `"halt"`
  (alternative `"skip_record"`). Quests, scenes, dialogue and voice have their own synthesizers (about 19,700 lines).
  **verified** (`native/conversion/src/fnv_legacy_scripting/`, `python/bacup_lib/models.py` line 466)
- **Voice as a manifest, not a guess.** FNV voice (OGG) becomes FO4 FUZ through "the authoritative WAV -> LIP/XWM ->
  FUZ pipeline"; the converter "emits a manifest rather than writing a fake FUZ header", and each line gets a status
  (`written`, `source_unavailable`, `transcript_unavailable`, `fuz_failed`, ...). **verified** (`voice.rs`,
  `python/bacup_lib/fnv_voice.py`)
- **Rebuilt joins for systems without a target record.** FO76 C.A.M.P. collectors depend on a `RESO` record FO4 lacks
  (178 in source, 0 in output); a fixup rebuilds the join (resource AVIF, produced LVLI, interval GLOB) and binds an
  original `B21:WorkshopCollector` script that accrues output from elapsed game time; unmatched collectors are "counted
  in the fixup's diagnostics rather than bound to a half-filled script". **verified**
  (`script_additions/fo76_fo4/B21/WorkshopCollector.contract.md`)
- **Menu patches shipped as code only.** `resources/` holds ActionScript fragments injected into the target's own menus
  (for example `realtime_vats/VATSMenu.as`, `perk_cards/`, `workshop/`, `currency/HUDMenu.as`), built with an in-repo SWF
  editor. **verified** (files exist); that they patch the player's own SWFs at conversion time is a **supported
  hypothesis**.
- **py-creation-lib's Papyrus compiler has a Starfield profile.** `papyrus_core/src/profile.rs` defines Starfield as
  game id 4, version 3.2, structs, groups and **guards** allowed; `pex_writer.rs` writes Starfield guard tables. It is a
  full compiler (parser, type checker, codegen, PEX writer, 15,359 lines). **verified** (files read). Whether its
  Starfield `.pex` output loads in game is **unresolved**.
- **CK-free generators.** `native/ck/` is "Creation Kit-equivalent generators (CK-free AnimTextData)". **verified**

### tes4skyrim / "TES Auto-Convert" (bryantmh, MIT, pre-alpha)
- Converts Morrowind, Oblivion, FO3 and FNV (and total conversions like Nehrim) into Skyrim SE on the player's PC:
  "records, meshes, textures, collision, animations, sounds, dialogue, and scripts". "No Bethesda assets are included".
  Warns: "Updates will likely break your saves from converted games". **verified**
  ([README](https://github.com/bryantmh/tes4skyrim/blob/master/README.md))
- **Dialogue and quests** are "converted into Skyrim's branch/voice-type architecture, including voice-file renaming,
  topic/quest restructuring so NPCs greet and respond correctly, and barter/training menu hookup". **Scripts** are
  "transpiled to Papyrus (`.psc`) source and compiled", using an MIT Papyrus compiler (russo-2025) and Ormin's
  Skyblivion ScriptConverter as reference. **Voice** is converted with ffmpeg and xWMAEncode, and lip tracks are
  generated "for every transcribed line using the Creation Kit's LipGenerator ... Expect the occasional silent line".
  **verified** (README)
- **Where the target engine lacks a system, it ships native code.** `TESRuntime.dll` "sends an arrested player to the
  nearest jail as the source games do"; `FalloutRuntime.dll` does "the Fallout 3 / New Vegas gun handling Skyrim has no
  equivalent for"; `CreatureRuntime.dll` registers creature animations "so several mods can each add creatures without
  fighting over Skyrim's animation cache". Morrowind's topic dialogue "none of which Skyrim can represent" runs as a port
  of OpenMW's dialogue engine inside `MorrowindRuntime.dll` with its own menu. **verified** (README)
- **New game.** A separate start plugin overrides `MQ101` and shows a menu to pick a world; "Choosing Skyrim runs the
  vanilla Helgen opening untouched"; "it conflicts with other alternate-start mods". **verified** (README)
- **Plugin type lesson.** "A non-master plugin has every reference treated as always-active, and the engine hangs on the
  main menu past about a million of them." **verified** that the README says so (Skyrim SE; not tested for Starfield)
- **Journal gap.** A "Quest Journal Stage Text" patch makes old journal text reachable, because Skyrim's journal keeps
  only current text. **verified** (README)
- **Community reaction.** r/skyrimmods: users report "Both games are almost 100% fully playable" and "It works fairly
  well and is getting updates pushed daily"; others refuse it because "The number one contributed is Claude"; one user
  asked about "a trojan detected in the download". **verified** (forum comments, not tests:
  [r/skyrimmods](https://www.reddit.com/r/skyrimmods/comments/1wl4zqc/tes4skyrim_apparently_a_way_to_fully_convert_mw/))
- Same author as BACUP: **supported hypothesis** (similar names Bryant-21 / bryantmh, overlapping design, "Claude"
  contributor); not confirmed.

### Other open tools seen
- **Ormin, skyblivion-ScriptConverter**: "Oblivion's OBScript Language Lexer and Parser", an "AST to TES5 Skyrim Papyrus
  transpiler" and a build tool around the Papyrus compiler; needs the user's own Skyrim scripts and `Oblivion.esm`.
  **verified** ([GitHub](https://github.com/Ormin/skyblivion-ScriptConverter))
- **russo-2025, papyrus-compiler** (MIT, V language): "Currently, the compiler only supports Skyrim"; uses header `.psc`
  files with `native` stubs for type information; documents that Bethesda's compiler can change string-literal casing.
  **verified** ([GitHub](https://github.com/russo-2025/papyrus-compiler)). Not usable for Starfield as is.

## Precedents and lessons (mechanics only)

### Tale of Two Wastelands (FO3 into FNV)
- **Record approach.** Since 2012 a three-master layout: FalloutNV.esm unchanged, Fallout3.esm "patched to have
  FalloutNV.esm as its master", then TaleOfTwoWastelands.esm "resolves conflicts". The patch "makes it inject all of its
  records into FalloutNV.esm ... As far as the game is concerned the masters ARE merged". The lead aimed at "not touching
  ANYTHING on the FNV side". **verified** ([TTW forum t=970](https://taleoftwowastelands.com/viewtopic.php@t=970))
- **Mechanics rebuilt by hand, not converted.** TTW "upgrades Fallout 3's mechanics to those of FNV": companion wheel,
  companion perks, weapon mods, crafting, recipes, harvestable plants and poisons were added to DC content; level cap
  50 to 60; FO3 bobbleheads changed to "mini perks (since it's already too easy to max SPECIAL and Skills in TTW)".
  "TTW isn't just FO3 in FNV ... its own balance". **verified** ([mod.pub](https://mod.pub/ttw/133-tale-of-two-wastelands))
- **Team.** The credits list two lead designers, five programmers, six GECK programmers, one installer and tool
  programmer (Zilav), ten scripters, one quest designer and five QA. **verified** (same page)
- **Their own conversion rules (for FO3 mods into TTW).** An xEdit script with a CSV FormID map does "the basics"; by
  hand: recompile each script ("Never ever use the recompile all button, ever!"), companions get their own quest and
  wheel topics ("among the most time-consuming parts"), scripted workbenches become recipes, prices and Hardcore effects
  rebalanced, navmesh refinalized ("Cells must be navmeshed, no exceptions"), never edit the Startup quest, the Generic
  Handler quest or the vanilla Followers quest. **verified** (geckwiki "TTW Mod Conversion Package and Guidelines",
  read via WebFetch summary, linked from [mod.pub docs](https://mod.pub/ttw/133/docs/17-mod-conversion-guidelines))
- **Lesson for us.** Even with the same engine generation, the systems layer was redesigned: FO3 content was moved onto
  FNV's systems and rebalanced. Our plan to move FO4 content onto Starfield's systems where they fit (affinity,
  legendaries, build mode) is the TTW pattern; balance is its own work item, not a side effect.

### Fallout: London (new content on FO4)
- **Systems changed from FO4.** Pre-FO4 dialogue with full option text and a silent player; the ATTA-Boy replaces the
  Pip-Boy; power armour removed; "Horses and bicycles were planned, but ultimately cut due to bugs"; combat, VATS and
  settlements "work similarly to Fallout 4". **verified** ([Wikipedia](https://en.wikipedia.org/wiki/Fallout:_London))
- **The silent-player menu broke at launch for some players.** With a stale `dialoguemenu.swf` or Full Dialogue
  Interface installed, players saw only "Positive / Neutral / Negative" and "the player just sits there in silence for a
  solid 3 to 5 seconds"; the fix was deleting `Data/interface/dialoguemenu.swf` or the other dialogue mod. **verified**
  (player reports: [r/fallout4london](https://www.reddit.com/r/fallout4london/comments/1edjm65/dialogue_question/)).
  The 3 to 5 seconds is a **supported hypothesis** that unvoiced player lines still wait on a line duration.
- **Patch 1.03 "Rabbit & Pork" (2025-09-30).** "Due to how the papyrus scripting language stores properties in your
  save file you will **require** a new save game start ... continuing an existing save after updating will certainly
  break quests". Over 380 quest fixes, 126 NPC fixes. Their own `Folon_WorkshopParent` quest was "Gutted ... to avoid
  conflicts with the vanilla equivalent"; a "Dialogue blocker placed on vanilla dialogue in WorkshopParent to help
  prevent Boston voices slipping through"; vanilla dialogue removed from generic traders; settlers "would become
  unassigned"; perks that could be qualified for with buff items. They also bundled X-Cell, Buffout 4 and the High FPS
  Physics Fix and regenerated precombines, LOD and AnimTextData. **verified**
  ([fallout.wiki V1.03](https://fallout.wiki/wiki/Mod:Fallout_London/V1.03))
- **Lesson for us.** Three direct transfers: (1) expect each content update to need a new game unless script
  properties stay stable; (2) Starfield's own generic dialogue, workshop and follower quests will leak into our world
  ("Starfield voices slipping through") unless we condition or block them; (3) a parallel copy of a vanilla framework
  quest conflicts with the original, so either own the system fully or extend the vanilla one, not both.

### Capital Wasteland and other "Fallout 3 in Fallout 4" work
- Since the 2018 halt (see precedents.md) the team ships **standalone slices** on Nexus: a full recreation of the Point
  Lookout DLC ("every quest, location, NPC, enemy"), creature packs with "Full new animations and skeleton", a voiced
  companion with a "Brand new companion perk", robot packs craftable at the Automatron workbench, and a "Brand New
  scratch made Pip-Boy model" with "Custom animations". **verified** ([capitalwasteland.com](https://capitalwasteland.com/available-content))
- A separate FO4 mod reimplements FO3/FNV karma ("Karma is back!"). **supported hypothesis** (search snippet only:
  [Nexus FO4 80425](https://www.nexusmods.com/fallout4/mods/80425))
- **Lesson for us.** The FO3-in-FO4 work that reached players reused FO4's systems (workbenches, companions, leveled
  lists) and shipped mechanics in small packs. Releasing a system (for example our Pip-Boy or power armor) as a testable
  standalone module before the whole conversion matches this.

### Skyblivion (Oblivion into Skyrim SE)
- **Records converted, behaviour placeholder.** 2014, Zilav: "The current converted magic effects are placeholders,
  however all spells, potions and ingredients have correct links"; constant effects "Oblivion used spells for constant
  effects, but in Skyrim they are implemented via perks"; "We don't have a dialog file yet, so the quests can't be
  worked on today"; "I got a translator from Obscript to Papyrus". He also reported that of "10-20 newcomers ... noone
  came back with anything". **verified** ([Morroblivion forum, 2014-05-25](https://morroblivion.com/comment/58279))
- Script conversion used Ormin's OBScript to Papyrus transpiler (see tools). **verified** that the tool exists and was
  built for Skyblivion; how much of Skyblivion's final quest code is transpiled is **unresolved**.
- The final blockers (navmesh, last quest lines, QA) are in precedents.md.
- **Lesson for us.** Our v6 builds are at the same stage Skyblivion was in 2014: records and links convert, mechanics
  are placeholders. The rebuild of magic effects and perks into the target's model (spells to perks there; FO4 effects
  to Starfield effects here) is the long tail. Budget it per system.

### Skywind (Morrowind into Skyrim SE) and Morroblivion
- **Started as an automated port.** Morroblivion grew from a converter by Galadrielle that turned Morrowind ESM/ESP into
  Oblivion files "largely functional for worldspace, objects, weather, clothing"; Bethesda's community manager asked
  Nexus "to cease hosting Morroblivion, as it violates the end-user license agreement". Skywind began two days after
  Skyrim's release by porting Morroblivion; in 2014 the team decided "simply replacing ported assets with fresh ones
  isn't enough" and aimed for "modern standards"; a public alpha was pulled because of "an ongoing deluge of duplicate
  bug reports, support requests". Script names keep the prefix from the Morrowind to Morroblivion conversion (`fbmw`).
  **verified** ([Skywind handbook history](https://handbook.tesrskywind.com/%68ome/history))
- **What the automated dialogue import left behind.** Dialogue was first sorted into quests or a catch-all
  `MorroDefaultQuest`; quest topics were "accidentally left" there; in February 2021 (0.9.9.21) it was split into many
  `MorroDefaultQuest<descriptor>` quests "in order to preserve the filenames for voice acted lines". "A lot of
  Morrowind's system was not ported well, so we have, e.g. directions to a quest destination appearing before a quest
  was assigned, or all parts of a conversation are available instantly". **verified**
  ([quest design principles](https://handbook.tesrskywind.com/dev/Principles),
  [quest testing guidelines](https://handbook.tesrskywind.com/dev/quest-testing-guidelines))
- **Engine rules learned.** "All aliases must fill properly for a quest to start"; debug by setting aliases optional and
  using `sqv`; "Unique actors can have only one instance ... If there are more, then aliases using that actor will fail
  to fill"; "Start Game Enabled quests require an 'SEQ' file"; NPCs scripted to attack a player in a shared faction need
  the faction's combat relation removed; keep logic in quest stage fragments, keep topic info fragments to stage sets.
  Skyrim's journal "does not retain old log entries", so entries were rewritten. **verified** (same pages)
- **Lesson for us.** An automated dialogue import produces a working but wrong-timed conversation layer; topic
  conditions on quest stages are the part to verify per quest. Plan the dialogue-to-quest grouping and file-naming rule
  once, before any voice or lip files exist (the wave-2 filename rule now has a concrete cost: Skywind restructured
  in 2021 to keep voice filenames stable).

### Beyond Skyrim
- Covered in precedents.md W2-1: rebuilt from scratch and re-voiced, umbrella of teams, one province slice in 8 years.
  No mechanics-conversion tooling was found. **unresolved** for mechanics.

### FNV to FO4 (terry-haire / bololo11)
- Covered in precedents.md: world, cells and placements only; "NPCs, creatures, quests and scripts are excluded".
  For mechanics this is the same fence BACUP draws for `fo4:starfield`. **verified** (precedents.md)

## Possibilities and hard limits in CE2 (from these precedents)

- **Possible: transpile scripts with a function map and an explicit unmapped policy.** BACUP (GECK to Papyrus) and
  tes4skyrim (OBScript and others to Papyrus) both do it; FO4 Papyrus to Starfield Papyrus is a closer pair (same
  language family, Starfield adds guards). **supported hypothesis** that our 77 missing functions fit a YAML map with
  `drop_with_warning` and a "halt" default.
- **Possible: compile without the CK GUI.** BACUP calls the game's `PapyrusCompiler.exe -all` in one batch, and
  py-creation-lib has its own compiler with a Starfield profile. **verified** for FO4 targets (code); **unresolved** for
  Starfield output.
- **Possible: rebuild a missing system as an original script bound by a fixup.** BACUP's C.A.M.P. collector is the
  pattern. **verified** for FO4.
- **Possible: native plugins for engine behaviour the target lacks** (jail on arrest, gun handling, animation
  registration, a whole foreign dialogue engine). **verified** for Skyrim SE (SKSE). For Starfield this runs into
  SFSE's update breakage and disabled co-save (engine-mechanics.md). **supported hypothesis**
- **Limit: save compatibility across our updates.** Papyrus stores properties in saves (Fallout London 1.03,
  tes4skyrim README). **verified** for FO4 and Skyrim; assumed for Starfield (**supported hypothesis**).
- **Limit: scripts attached to the player's base record.** BACUP moved them to a PlayerRef alias because FO4 could not
  carry the FO76 player record. Whether Starfield can carry scripts on the player `NPC_` record we write is
  **unresolved**.
- **Limit: non-master plugins with very many references.** Skyrim SE hangs "past about a million"; our v6 build has
  683,870 FormIDs. Starfield's threshold is **unresolved**.
- **No precedent converts a CE1 game's quests into CE2.** BACUP fences quests out of `fo4:starfield`; tes4skyrim targets
  Skyrim SE (CE1). **verified** (absence in both codebases)

## Question framework

Phases: **P1** new game, **P2** interiors, **P3** quests and people, **P4** Fallout systems, **P5** release.

### A. Relationship to BACUP and other open converters

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| A1 | Does BACUP's `fo4:starfield` output load and render in Starfield 1.16.244 (one interior, one exterior block)? **Partly answered (other threads, read in code, 2026-10-19):** nothing shows BACUP output ever loaded in game; it is record-only (no meshes, collision, havok or doors), skips FO4 navmesh and writes no locations or markers; the in-game load test is still open. | if yes, it is a second implementation of our world pipeline to compare against, or reuse | code exists, world only, no in-game evidence (this page) | build BACUP on the PC, run `regen.py --pair fo4:starfield` on Fallout4.esm, load one cell with `coc` | blocks A2, A3; needs the PC and Rust + MSVC | P2 | **key** |
| A2 | Where do BACUP's choices differ from ours (spatial factor 1/69.99125, LIGH DAT2 76 bytes, WATR DNAM 152, LGTM layouts, weather repointing, GRUP topology)? **Answered offline (Map, Interiors and Bugs threads):** it writes its own WRLD (no overlay), scales by 1/69.99125 (ours 1/70, 0.4 m across the core), drops XMRK, FNAM, TNAM, XLOC and XLCN, writes OBND as i16 where vanilla uses f32; to borrow: zero a door's transition cell when that cell is not built, optionally keep FO4 lighting templates; to check: its LIGH flag bits, XCLL +28 as gravity scale, NVNM variants; later: real per-quadrant land-texture layering from VTXT/ATXT. Details: map-markers.md on #399, interiors.md "BACUP compared", docs/spikes/bacup-comparison.md on #400. | each difference is a possible bug in one of the two pipelines | BACUP's values read in code; ours in `scripts/` and engine-mechanics pages | offline diff: their YAML drop lists and relayout widths against our xEdit dumps and converter constants | A1; feeds tools-and-scripting record layouts | P2 | **key** |
| A3 | Do we reuse BACUP code (GPL-3, same licence as our Mutagen code), only read it, or contact the author? **Narrowed:** the comparisons found no code worth taking, only ideas; reuse stays the owner's call (AP-60, WO-8 on the questions page). | reuse saves months on terrain `.btd`, navmesh, cells; outreach is the owner's call | GPL-3 compatible with our licence plan; README and code public | owner decision after A1/A2; licence check of each file we would take | A1, A2; owner outreach rule | P5 | **key** |
| A4 | Can py-creation-lib's Papyrus compiler produce Starfield `.pex` the game runs (guards included)? | a CK-free compiler removes the headless-CK question for scripts | Starfield profile in `profile.rs`, guard writer in `pex_writer.rs` | compile one of our probe scripts with it and with the CK compiler, compare in game | X2 in engine-mechanics.md; tools 6.1 | P3 | **key** |
| A5 | Does BACUP's Rust decompiler read Starfield `.pex` well enough to audit what Starfield scripts call? | lets us list Starfield natives used by its quests without Champollion's guard guesses | `pex.rs` parses Starfield guard definitions (test name) | decompile 20 Starfield `.pex` and compare with CK sources | none | P3 | |
| A6 | Should we adopt BACUP's script-patch convention (decompiled skeleton plus original method fills, keyed by script path)? | gives a legal, reviewable way to fix FO4 scripts that do not port without shipping Bethesda sources | BACUP rule "No game Papyrus" and splice rules (this page) | write 3 patches against our converted scripts in that shape; review with owner | X2 legal question (compile on player PC) | P3 | |
| A7 | Is tes4skyrim's start-menu design (override the vanilla opening, offer a world choice, vanilla path untouched) usable for our Vault 111 start? | settles whether the Starfield intro stays reachable and how we coexist with other start mods | README: overrides MQ101, conflicts with alternate starts | compare with our newgame.md findings (MQ101 stop leaves saving off) | newgame save trap | P1 | |

### B. Script conversion

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| B1 | Do we put the 77 missing FO4 functions in a data file (target expression, expansion, drop with warning) with a "halt on unmapped" default? | makes every unconverted call visible instead of silently compiled away | BACUP's 56-entry FNV map and halt policy; our probe list of 77 (engine-mechanics X1) | draft the YAML for the 77 with one target each; count how many need SFSE | X1; blocks the shim library | P3 | **key** |
| B2 | Do we check toolchain health before stripping script bindings from records whose script failed to compile? | BACUP lost 13,624 bindings in a shipped ESM when the compiler was missing | verified incident in BACUP code | add a unit test: compiler absent means abort, not strip | our converter's script stage | P3 | **key** |
| B3 | Which FO4 scripts are attached to the player record or to records Starfield cannot carry, and do they move to a PlayerRef alias? | BACUP had to rewrite every `Self` use when moving player scripts | FO76 to FO4 case verified; Starfield player record scripting unresolved | scan Fallout4.esm VMADs on the player NPC_ and on record types we drop; CK test one script on Starfield's player | quests, survival, SPECIAL | P3 | |
| B4 | Do we compile all converted scripts in one batch process and cache by source hash? | BACUP batches `-all` to bound memory; about 10,000 scripts per tools notes | BACUP pattern verified; our timing unknown | time `PapyrusCompiler.exe -all` on 500 converted scripts on the PC | tools 6.1, launcher time budget | P5 | |
| B5 | How do we name converted scripts so prefixes survive (Skywind kept `fbmw`, Skyblivion `TES4`, BACUP `B21`)? | Papyrus names are global; renaming later breaks saves and VMADs | X4 in engine-mechanics.md (CompanionActorScript clash) | decide prefix rule in decisions.md | X4; every script | P3 | |
| B6 | Does Bethesda's Starfield compiler change string-literal casing as russo-2025 documents for Skyrim's? | FO4 scripts that use strings as keys (scene names, animation events) could break silently | documented for Skyrim compiler only | compile a two-literal test script, read the `.pex` strings | B4 | P3 | |

### C. Quests and dialogue conversion

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| C1 | Which Starfield generic dialogue, workshop and follower lines would fire in our world, and how do we block them? | Fallout London had "Boston voices slipping through" and needed a dialogue blocker | FOLON 1.03 notes (this page); Starfield follower lines locked by MQ101 (companions notes) | in game, talk to a converted settler and a vendor; list every Starfield INFO that plays; check its conditions | C2; companions F2 | P3 | **key** |
| C2 | Do we extend Starfield's framework quests (workshop, followers, dialogue hubs) or replace them with our own, never both? | FOLON's parallel WorkshopParent conflicted with vanilla; TTW forbids editing the Followers quest | precedents agree: one owner per system | decide per system in decisions.md, starting with workshop and followers | workshop B1, companions F2 | P3, P4 | **key** |
| C3 | After conversion, do FO4 topics unlock at the right quest stage, or are conversations available too early (Skywind's failure)? | an automated import can keep text but lose timing | Skywind: "directions ... appearing before a quest was assigned" | pick 3 FO4 quests; compare INFO conditions on stage in FO4 vs our output; one in-game run each | quests Q1, D1 | P3 | **key** |
| C4 | Where does converted dialogue that belongs to no quest go, and is that grouping stable enough to key voice and lip filenames on? | Skywind had to split its catch-all quest in 2021 to keep voice filenames | Skywind rule: filenames from quest and topic ID prefixes | read Starfield's voice path scheme; decide grouping before any voice work | V2 voice path rule, X5 | P3 | |
| C5 | Do our aliases fill: unique actors placed once, persist locations set, fill order respected? | "All aliases must fill properly for a quest to start"; a failed fill stops a quest silently (quests notes) | Skywind rules; our quest notes on silent alias failure | offline check over our output: unique NPC_ placed more than once, missing persist locations; `sqv` in game | quests Q1 | P3 | |
| C6 | Which FO4 journal behaviour do we need on Starfield's Missions menu (old log entries, objectives tied to stages)? | Skyrim lost old entries and both Skywind and tes4skyrim had to work around it | UI 9.4 (Missions menu) open | in game, run one converted quest through three stages and read the Missions menu | UI 9.4 | P3 | |
| C7 | How do we test quests: happy path only, or Skywind's "try to break it" list (kill NPCs early, take items early, wrong order)? | precedents say quest QA is the long tail (FOLON 380 quest fixes in one patch) | Skywind testing guidelines | adopt a per-quest checklist in docs; run it on the first converted quest | QA capacity | P3 | |

### D. Voice and the silent player

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| D1 | How long does Starfield hold an unvoiced player line, and does our silent player cause FOLON's 3 to 5 second pause? | a pause after every choice makes the silent player feel broken | FOLON player reports; Starfield Silent Voice mod exists (quests notes) | in game, pick a player line with no voice file; time it; repeat with a silent file | quests D3, V5 | P1, P3 | **key** |
| D2 | Do we keep the dialogue menu vanilla (no menu file replacement) so stale or third-party menu files cannot break it? | FOLON's replaced dialogue menu failed when another `dialoguemenu.swf` was present | FOLON fix was deleting the loose file | decide in UI 1.3; if we replace, have the launcher check for conflicting loose files | UI 1.3 | P3, P5 | |
| D3 | If voice conversion is ever allowed, do we write a per-line manifest with statuses (written, source missing, transcript missing, lip failed) like BACUP? | lets the launcher report coverage and resume instead of failing silently | BACUP manifest and status enum verified; owner voice decision open | design only; no work until voice decision A1 in quests notes | owner voice decision | P3, P5 | |

### E. Systems rebuild

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| E1 | For each FO4 system without a Starfield record (workshop resources, settlement attacks, power armor frames, robot bench), what is the "join" we rebuild and which script binds it? | BACUP's collector shows the pattern; without it converted objects do nothing | collector contract verified; our workshop and character notes list missing natives | write one contract page per system in the shape of WorkshopCollector.contract.md | workshop B1, T1; character A1 | P4 | **key** |
| E2 | Which FO4 mechanics do we redesign on purpose (as TTW did with bobbleheads and level cap), and who signs off balance? | TTW: content on new systems needs rebalancing; else SPECIAL and skills max too fast | TTW feature list | owner list of deliberate changes; one balance pass per phase | character systems, economy | P4 | |
| E3 | Do we release systems as standalone testable modules (Pip-Boy, power armor, settlement layer) before the full conversion? | Capital Wasteland shipped packs; Beyond Skyrim kept interest with one slice | CW available content; precedents.md W2-1 | owner decision; pick the first module | release plan | P4, P5 | |
| E4 | Which engine behaviours need native code in the precedents' sense (jail on arrest, gun handling, animation registration), and is each worth an SFSE plugin? | tes4skyrim needed five DLLs; each SFSE plugin breaks on Starfield updates | tes4skyrim README; SFSE breakage history in tools notes | list FO4 behaviours with no Papyrus route (from B1); cost each | B1, R2 in companions notes | P4 | |
| E5 | Which converted records are linked but behave as placeholders (Skyblivion 2014: magic effects), and how do we track them? | a record that loads is not a mechanic that works | Skyblivion forum 2014 | add a "behaviour verified" flag per record family in our conversion report | QA dashboard | P3, P4 | |

### F. Saves and updates

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| F1 | Which of our changes force a new game (script property changes, alias changes, record removals), and do we promise save compatibility at all? | FOLON 1.03 and tes4skyrim both require new saves after updates | verified for FO4 and Skyrim | in game: save, change one script property, load; record the result | release notes, launcher update flow | P5 | **key** |
| F2 | Does the launcher warn when a rebuild would break the player's current save? | players lose progress silently otherwise | none | compare converter version and script property hashes stored at build time | F1 | P5 | |
| F3 | Is the output one master or several, and what reference count makes a non-master hang on Starfield's main menu? | Skyrim SE hangs past about a million references in a non-master; we have 683,870 FormIDs | tes4skyrim README; plugin-type question in tools notes | load our v6 build as non-master and as master; time the main menu | tools master type question | P1, P5 | |

### G. QA and community response

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| G1 | How do we present an AI-agent-built converter so the community judges it on results, given the "number one contributor is Claude" reaction? | tes4skyrim drew both praise and refusal for the same reason | r/skyrimmods thread | owner decides wording on the release page; show test evidence and a known-issues list | release page | P5 | |
| G2 | Do we sign or otherwise vouch for the launcher binary to avoid antivirus false positives? | a "trojan detected" report appeared for tes4skyrim | one forum comment | check how TTW, BACUP and FOLON ship their exes; ask on release | launcher packaging | P5 | |
| G3 | How do we avoid Skywind's duplicate-bug-report deluge when a public build appears? | Skywind pulled a public alpha for this reason | Skywind history | issue template plus a known-issues list before any public build | community report flow in AGENTS.md | P5 | |

## Corrections to project notes
1. **wave2-rechecks.md "Precedent: BACUP"** and **engine-mechanics.md** say BACUP has "a Starfield schema but no pair
   targeting Starfield". The README says three pairs, but the code defines and registers a world-only `fo4:starfield`
   pair with its own translation map, hook, cell writer and terrain writer (files and lines above). Labels: code
   **verified**, runtime **unresolved**.
2. **precedents.md** "Only one precedent actually converts game A's content into game B's engine on the player's PC
   and has shipped for years: TTW." Still true for "years", but since 2026 tes4skyrim converts quests, dialogue, scripts
   and voice cross-engine on the player's PC (pre-alpha, Skyrim SE target). It is the closest mechanics precedent we
   have. It also converts FO3 and FNV voice from the player's copy, the pattern Capital Wasteland was warned about; no
   Bethesda response to it was found (**unresolved**).

## Sources
- https://github.com/Bryant-21/bacup (README; files read in a shallow clone at commit cfa3d0dc, 2026-10-17:
  `bacup/py_bacup_lib/python/bacup_lib/source_pairs.py`, `.../workflows/unified.py`, `.../fnv_voice.py`,
  `.../models.py`, `.../script_patches/README.md`, `.../script_additions/fo76_fo4/B21/WorkshopCollector.contract.md`,
  `.../resources/realtime_vats/VATSMenu.as`, `bacup/py_bacup_lib/native/conversion/src/embedded/translation_maps/fo4_to_starfield.yaml`,
  `.../translator/mod.rs`, `.../translator/pair_hooks/fo4_starfield/mod.rs`, `.../phase/starfield_cells.rs`,
  `.../phase/terrain_btd.rs`, `.../phase/starfield_worldspace_gate.rs`, `.../script_conversion.rs`,
  `.../fnv_legacy_scripting/mod.rs`, `voice.rs`, `data/fnv_to_fo4_script_functions.yaml`,
  `data/fnv_to_fo4_actor_values.yaml`, `script_translator/semantic.rs`, `scripts/regen.py`)
- https://github.com/Bryant-21/py-creation-lib (README; `native/papyrus_core/src/profile.rs`, `pex.rs`,
  `pex_writer.rs`, `compiler.rs`; `native/ck/src`)
- https://github.com/bryantmh/tes4skyrim/blob/master/README.md
- https://www.reddit.com/r/skyrimmods/comments/1wl4zqc/tes4skyrim_apparently_a_way_to_fully_convert_mw/
- https://github.com/Ormin/skyblivion-ScriptConverter
- https://github.com/Ormin/skyblivion-NIFConverter (search result only)
- https://github.com/russo-2025/papyrus-compiler
- https://taleoftwowastelands.com/viewtopic.php@t=970
- https://mod.pub/ttw/133-tale-of-two-wastelands
- https://mod.pub/ttw/133/docs/17-mod-conversion-guidelines and
  https://geckwiki.com/index.php?title=TTW_Mod_Conversion_Package_and_Guidelines (WebFetch summary)
- https://thebestoftimes.moddinglinked.com/ttw.html
- https://en.wikipedia.org/wiki/Fallout:_London
- https://fallout.wiki/wiki/Mod:Fallout_London/V1.03
- https://www.reddit.com/r/fallout4london/comments/1edjm65/dialogue_question/
- https://capitalwasteland.com/available-content
- https://www.nexusmods.com/fallout4/mods/80425 (search snippet only)
- https://morroblivion.com/comment/58279
- https://en.m.uesp.net/wiki/Tes5Mod:Skyblivion
- https://www.dsogaming.com/videotrailer-news/skyblivion-oblivion-mod-for-skyrim-gets-a-new-teaser-trailer/
- https://handbook.tesrskywind.com/%68ome/history
- https://handbook.tesrskywind.com/dev/Principles
- https://handbook.tesrskywind.com/dev/quest-testing-guidelines
- Project files read: ../findings/precedents.md, ../engine-mechanics.md, wave2-rechecks.md, ../README.md
- Not readable this run: m.morroblivion.com/forums/skywind/skywind-development/2762 (HTTP 400), fallout.wiki
  Mod:Fallout_London and its Traits page (timeouts), mod.pub/ttw/133 (bot block)
