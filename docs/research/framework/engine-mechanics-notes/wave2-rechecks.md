# Wave 2 rechecks: pages wave 1 could not read

Author: Claude (wave 2 research agent), 2026-10-19. Research only; the wave 1 files are unchanged.
Labels as in the brief: **verified** (read on the source page or in the file), **supported hypothesis**, **unresolved**.
Method: GitHub code search plus raw file reads from raw.githubusercontent.com (no rate limits hit), WebFetch for
Nexus and wiki pages, paced. No 429s this pass. "Answers or changes" names the question id and the wave 1 file.

## 1. Can an SFSE plugin register a new Scaleform movie as a real engine menu?

What I read:
- SFSE source, `sfse/PluginAPI.h`, `sfse/Hooks_Scaleform.cpp`, `sfse/Hooks_Scaleform.h`
  (https://github.com/ianpatt/sfse, master branch, raw files).
- libxse CommonLibSF `include/RE/U/UI.h`, `include/RE/I/IMenu.h`, `include/RE/IDs.h`, `EXCEPTIONS`
  (https://github.com/libxse/commonlibsf, main branch). The older Starfield-Reverse-Engineering/CommonLibSF repo is
  archived (GitHub repo metadata, archived: true).
- OSF UI `src/Input/FocusMenu.h` and `.cpp`, README, LICENSE (https://github.com/ozooma10/osf-ui).
- PULSAR co-op tool `include/Lobby/LobbyMenu.h`, `src/Lobby/LobbyMenu.cpp`, README
  (https://github.com/ramisotti13-eng/pulsar-tool).

What it says:
- SFSE's own `SFSEMenuInterface` (version 2) offers only two callbacks: `RegisterMenuMovieCreated` (called after any
  menu's `IMenu::LoadMovie`) and `RegisterScaleformManagerCreated`. It has **no** function to register a new menu.
  **verified** (PluginAPI.h lines 118 to 134; Hooks_Scaleform.cpp hooks `IMenu_LoadMovie` at RelocAddr 0x02551AB0).
- CommonLibSF wraps the engine's own `UI::RegisterMenu(const char* name, Create_t* create, bool flag)` through
  Address Library ID 130463, with `IsMenuRegistered`, `GetMenu`, `menuMap` at UI+0x470. `IMenu` flags are still
  unnamed (`Flag0`, `Flag1`, ... `Flag27`), so which bit means "pause game" is not documented there. **verified**
  (UI.h, IMenu.h, IDs.h).
- OSF UI registers a real engine menu, `OSFUI_FocusMenu`, by calling `RE::UI::RegisterMenu` with a creator
  function. It is **movie-less** on purpose: `LoadMovie` returns true with no SWF, `GetRootPath` returns "", it sets
  no menu flags, and pause and cursor are driven separately. Its comment: the menu exists to give the HTML overlay "a
  slot in the engine's active menu array (open/close bookkeeping, input contexts) and a gamepad capture gate".
  **verified** (FocusMenu.h). So registering a new engine menu by name works in a shipped mod targeting 1.16.244:
  **supported hypothesis** (the code is public; OSF UI requires SFSE and Address Library; I did not run it).
- PULSAR (GPL-3.0, author no longer developing, "Starfield 1.16.244" required) registers a native Scaleform
  `LobbyMenu` meant to load `Interface/pulsar_lobby.swf`. Its notes: CommonLibSF's `IMenu` vtable thunks and the
  Scaleform heap singleton ID are "stale {0}" and crashed; it instead copies the engine's real IMenu vtable
  (REL::ID 475515), runs the engine's base IMenu constructor (offset 0x25516B0), sets flags `0x40483` copied from
  LoadingMenu, and inserts its creator straight into `menuMap` ("CONFIRMED in-game"). Its `GetRootPath` returns ""
  because "file path here crashed the engine". **verified** (LobbyMenu.cpp comments). Whether its custom SWF actually
  draws is **unresolved**: the code shows registration and open/close, not a rendered custom movie.

Answers or changes:
- **ui-pipboy-vats.md 1.2** (key): moves from unresolved to **supported hypothesis, partly yes**. Registering a new
  named engine menu works (OSF UI, movie-less; PULSAR, Scaleform attempt). Loading our own SWF into it is still
  unproven and the one public attempt hit crashes and stale CommonLibSF data. Cheapest next check: read PULSAR's
  git history and design spec for whether the SWF rendered, then a one-menu SFSE test on the PC. New sub-questions:
  which `IMenu` flag bits pause the game and take input (PULSAR used LoadingMenu's 0x40483), and do we fix
  CommonLibSF's stale vtable IDs upstream or copy PULSAR's workaround.
- **ui-pipboy-vats.md 1.1**: a fifth pattern exists, "HTML overlay plus a movie-less engine menu for input and
  pause" (OSF UI), which gives an HTML Pip-Boy engine menu behaviour without a SWF.
- **tools-and-scripting.md 5.2**: libxse/commonlibsf is the live fork (updated 2026-10-17); the original repo is
  archived. Licence of libxse CommonLibSF: GPL-3.0-or-later with a Modding Exception and a GPL-3.0 Linking Exception
  **verified** (EXCEPTIONS file; Carbon UI's LICENSE states the same). Fits our GPL-3.

## 2. Mutagen's current Starfield support, and does it write FACT relations?

What I read:
- Mutagen README (https://github.com/Mutagen-Modding/Mutagen, dev branch, raw).
- NuGet flat-container and registration APIs for `Mutagen.Bethesda.Starfield` and `Mutagen.Bethesda`
  (https://api.nuget.org/v3-flatcontainer/mutagen.bethesda.starfield/index.json).
- `Mutagen.Bethesda.Starfield/Records/Major Records/Faction.xml`, `Records/Common Subrecords/Relation.xml`,
  `Records/StarfieldMod_Generated.cs` (dev branch, raw).

What it says:
- The README does not state Starfield status or a licence; it describes Mutagen generally. **verified**. The GitHub
  releases API returned 403 to this session, so release notes are **unresolved**.
- Newest listed `Mutagen.Bethesda.Starfield` on NuGet is **0.55.0-alpha.75, published 2026-10-19**; the project's
  pin 0.55.0-alpha.67 was published 2026-10-06; newest stable is 0.54.4. **verified** (NuGet API).
- The "2.8.x prereleases" the launcher note mentions: `Mutagen.Bethesda` lists `2.8.1-prerelease001/002`, `7.1.0` and
  `23.4.0`, all **unlisted** with a 1900-01-01 publish date (NuGet's marker for unlisted). They are not the live line.
  **verified** (NuGet registration). Who published them is **unresolved**; treat them as not ours to use.
- Starfield `Faction` (FACT) is fully typed: `Relations` (list of `Relation`: `Target` FormLink to IRelatable,
  `Modifier` Int32, `Reaction` CombatReaction enum, subrecord XNAM), `Keyword` (DNAM), `Flags`, `SharedCrimeFactionList`
  (CRGR), `CrimeValues` (CRVA: Arrest, AttackOnSight, Murder, Assault, Trespass, Pickpocket, StealMultiplier,
  Escape, Piracy, SmuggleMultiplier), `Prisons` (PRIS: door, ship landing, cargo and inventory contraband, companion
  wait markers), `Ranks`, vendor fields (VEND, VENC, VENV, PLVD), `Conditions`, `VoiceType` (VTCK), `Herd` (HERD:
  search radius, min/max members, idle chatter times) and `FormationRadius` (GRPH). **verified** (Faction.xml).
- Starfield `AffinityEvent` (AFFE) has a typed group. **verified** (StarfieldMod_Generated.cs). There is **no**
  `Relationship` (RELA) group among the 175 Starfield groups. **verified** for the dev branch (grep of
  StarfieldMod_Generated.cs). Conditions `GetRelationshipRank`, `GetFactionRelation` exist as typed condition data.

Answers or changes:
- **tools-and-scripting.md 3.5** (can Mutagen write faction ties): **answered yes, verified at the schema level**.
  Relations, crime values, prisons, vendor data, herd and formation radius are typed fields. A write-and-load test is
  still needed (offline round trip through xEdit, then in game).
- **tools-and-scripting.md 3.1**: the live upstream line is 0.55.0-alpha.x (alpha.75 today), not 2.8.x. Upgrading
  is eight alpha steps, cheap to try.
- **companions-ai-factions-combat.md H5** (RELA): new constraint. Mutagen cannot write RELA as a typed record on the
  dev branch, so converting FO4's 64 RELA needs raw record writing or a Mutagen contribution. Check first whether
  xEdit's SF1 definition and the game read RELA at all (H5's existing test).
- **companions-ai-factions-combat.md S1, S2, S3**: the HERD, GRPH and VTCK fields are writable from our converter,
  so those tests can use generated plugins.

## 3. Address Library for SFSE: does it support 1.16.244?

What I read: https://www.nexusmods.com/starfield/mods/3256 and its files tab (`?tab=files`).

What it says: main file "All in one - v22 (1.16.244.0) SFSE Address Library", version 22, uploaded 13 June 2026,
"Contains all versions up to game version 1.16.244.0 of Steam". Earlier: v21 for 1.16.242.0 (15 May 2026), v20
for 1.16.236.0 (8 Apr 2026), v19 for 1.15.222.0 (5 Aug 2025). The description text still names 1.7.23 and is stale.
Steam only for recent versions. **verified**.

Answers or changes:
- **tools-and-scripting.md** "Address Library ... 1.16.244 status unresolved": now **verified yes** (v22).
- **tools-and-scripting.md 5.3** (patch latency): data points for the table. Address Library came out on
  15 May 2026 for 1.16.242 and 13 June 2026 for 1.16.244. Game patch dates still need adding (SFSE whatsnew).
- **ui-pipboy-vats.md 1.1**: the statement "all four stacks exist for 1.16.244" holds for the Address Library side.

## 4. Starfield CK command-line switches (lips, Papyrus, subgraph data)

What I read:
- https://starfieldwiki.net/wiki/Starfield_Mod:Creation_Kit (no command-line switches mentioned). **verified**
- https://stepmodifications.org/wiki/Starfield:Creation%20Kit (stub, nothing on switches). **verified**
- https://falloutck.uesp.net/wiki/Subgraphs: Fallout 4's CK builds subgraph metadata with
  `CreationKit.exe -GenerateAnimInfo:<ESMFilename> <DataFilepath> <OutputFilepath> [--speed] [--stance] [--forceAll]`,
  for example `-GenerateAnimInfo:SubgraphExample.esm ..\Data ..\Data\Meshes\AnimTextData --speed`; MT roles use
  `--speed`, weapons `--speed --stance`, furniture no flags; the ESM name must have no spaces. **verified**
- Web searches for `"-GenerateLips" Starfield` and `"GenerateAnimInfo" Starfield` found no page that documents either
  switch for the Starfield CK. GitHub code search found `-GenerateAnimInfo` only in BACUP, which uses it with the
  **Fallout 4** CK. **verified** (search results, 2026-10-19).

Answers or changes:
- **tools-and-scripting.md 6.1** and **quests-dialogue-voice.md L1**: still **unresolved** on the web. **Update (after wave 2, verified on the PC, jobs 18 to 33):** 6.1 answered (the Starfield CK has switches but no -GenerateLips); L1 answered for generation (LipGenerator.exe plus ffxc.exe run headless; time per 1,000 lines not yet measured); see engine-mechanics.md, PC checks. The cheapest
  check stands: `strings CreationKit.exe` on the PC, grep `-Generate`, `-Compile`, `-Export`, and now also
  `GenerateAnimInfo`.
- **animation-audio-physics.md B1** (new clip with CK-generated subgraph data): the "CK launch argument" an Animation IO
  commenter used is very likely the FO4-style `-GenerateAnimInfo` (**supported hypothesis**: same engine family, same
  job; the Starfield name is not confirmed). Add it to the strings check.

## 5. Starfield Affinity page; SetCommandState and OnCommandModeGiveCommand

What I read:
- https://starfieldwiki.net/wiki/Starfield:Affinity
- https://falloutck.uesp.net/wiki/SetCommandState_-_Actor
- https://falloutck.uesp.net/wiki/OnCommandModeGiveCommand_-_Actor
- https://ck.uesp.net/wiki/Relationship (the Skyrim page wave 1 could not read)

What it says:
- Starfield affinity reactions: Loves +50, Likes +25, Indifferent 0, Dislikes -15, Hates -35, hidden "Wants to Talk"
  +1; message "Sarah Morgan Liked That". Story gates 1 to 8 at 100, 200, ... 800 affinity, with minimum real time
  30 minutes for gate 1 and 1 hour for gates 2 to 8. Fighting a civilian dismisses the companion; killing one
  dismisses and angers. The page does not give cooldowns, actor value or global names. **verified**
- FO4 `SetCommandState(bool abStartCommandMode)`: "Sets/Unsets the actor in command mode so that we can order them
  around." Requires `SetCanDoCommand()` first or an already commandable actor, "e.g. teammates". **verified**
- FO4 `OnCommandModeGiveCommand(int aeCommandType, ObjectReference akTarget)`: command types 0 None, 1 Call,
  2 Follow, 3 Move, 4 Attack, 5 Inspect, 6 Retrieve, 7 Stay, 8 Release, 9 Heal, 10 Workshop Assign,
  11 Ride Vertibird, 12 Enter Power Armor. **verified**
- Skyrim Relationship ranks: Ally and Friend "will only be attacked by Frenzied actors, and will be assisted by Helps
  Friends and Allies actors"; Enemy is attacked on sight by Aggressive and above. No numeric values and nothing on
  forgiving hits on that page. **verified**

Answers or changes:
- **companions-ai-factions-combat.md A3** (key, timers vs FO4 tiers): Starfield's gate table is now sourced: 8 gates
  every 100 points with real-time minimums. FO4's tiers (250/500/750/1000, no timers) do not line up with
  Starfield's 100-point gates, so either rescale or keep FO4's tiers in globals; the owner decision can now be made
  with both tables. Reaction sizes differ too (Starfield +50/+25/-15/-35).
- **companions-ai-factions-combat.md A8**: Starfield already dismisses on civilian assault and angers on murder,
  which overlaps FO4's crime-faction hostility. Test whether that logic fires for our companions (it may come with
  the Starfield companion layer we fence out).
- **companions-ai-factions-combat.md C1** (key): the CE2 test must call `SetCanDoCommand(true)` (or make the actor a
  teammate) before `SetCommandState(true)`, and should log `aeCommandType` values to see which of FO4's 13 survive.
  Types 10 to 12 (workshop, vertibird, power armour) feed **C5** and the workshop notes.
- **companions-ai-factions-combat.md H2, H5**: Skyrim's documented effect of Friend/Ally (only frenzied actors attack,
  helpers assist) is now sourced; the hit-allowance numbers in H2 are not on that page.

## 6. Carbon UI licence: Nexus page vs GitHub

What I read: https://www.nexusmods.com/starfield/mods/17899 ; https://github.com/CarbonNode/CarbonUI README and LICENSE
(raw, main branch).

What it says:
- Nexus: code "GPL-3.0-or-later" with an Ultralight linking exception, and Ultralight DLLs under Ultralight's own
  free-tier licence, not the GPL. The Nexus **permissions** section also says "You are not allowed to convert this
  file to work on other games under any circumstances" and "You must get permission from me before you are allowed to
  modify my files". v0.11.0, updated 3 Oct 2026, targets Starfield 1.16.244, needs SFSE, Address Library, D3D12, and
  four Ultralight DLLs in the game root. **verified**
- GitHub LICENSE: GPL-3.0-or-later, copyright 2026 "Rober (the Carbon UI author)", statically links CommonLibSF, with
  three section 7 permissions: an Ultralight linking exception, a modding exception for Starfield, and a
  modding-libraries (SFSE) linking exception with Corresponding Source. README: working name "Star Deck", a port of
  PrismaUI (Skyrim), in-game present hook confirmed 2026-08-10. **verified**
- The Nexus "ask before modifying" line conflicts with the GPL's freedom to modify. The GPL text in the repository
  governs the source code; the Nexus line most likely governs the Nexus upload. **supported hypothesis** (not legal
  advice).

Answers or changes:
- **ui-pipboy-vats.md 1.1**: Carbon UI is GPL-3+ with exceptions that fit our GPL-3 code (**verified**). Before we
  depend on or fork it, ask the author to confirm the Nexus permissions do not apply to GPL use of the source
  (owner-approved message). Our build would also inherit the Ultralight free-tier licence for the DLLs.
- **ui-pipboy-vats.md 1.1, animation-audio-physics.md M2** ("OSF licence not named / unknown"): OSF UI is **GPL-3.0**
  (LICENSE file) and OSF Animation is **GPL-3.0 with a modding/linking exception** (LICENSE file, copyright 2025-2026
  ozooma10). **verified**. OSF UI needs SFSE, Address Library, OSF Settings 1.0.0 and the Edge WebView2 runtime.

## 7. Animation IO GitHub: CK launch argument and licence

What I read: https://github.com/deveris256/sf_animation_io (repo page), `blender_manifest.toml`, `README.md` and the six
files in `docs/` (raw, master branch).

What it says:
- `blender_manifest.toml`: id `tool_starfield_animation_io`, version 1.0.0, maintainers "Deveris, Calaverah & Jojo",
  Blender 4.3.0 minimum, `license = ["SPDX:MIT"]`. No LICENSE file and no licence in the GitHub sidebar; no releases.
  The repo bundles `CALUMI.Animation.dll`. **verified**
- OSF Animation's README credits CALUMI.Animation (Calaverah) as **LGPL-3.0**. **verified** (osf-animation README)
- The docs describe registering a rig and exporting `.af`; they do not mention the Creation Kit, launch arguments,
  subgraph data, `.agx` or `.afx`. **verified**

Answers or changes:
- **animation-audio-physics.md A3** (key, can we call CALUMI.Animation headless and ship it): the library is LGPL-3.0
  per OSF's credit (wave 1 said Animation IO is "custom"). Calling an LGPL DLL from our GPL-3 launcher is compatible
  (**supported hypothesis**). The Blender add-on is MIT in its manifest but the Nexus page sets custom permissions:
  another source vs page conflict to settle with the authors (M3).
- **animation-audio-physics.md B1**: the CK argument is not in the Animation IO docs; see item 4.

## 8. Other gap items that flip a key question

### OSF Animation plays mod audio through the engine's Wwise
Read: https://github.com/ozooma10/osf-animation README and `docs/SCENE_SCHEMA.md` (raw, main).
- README: "Engine-native Wwise loose-file audio playback (rides the game mix; no private-device fallback)". **verified**
- Schema: a sound `spec` is "a Data-relative file or `"event:<name>"` Wwise spec"; examples play loose
  `Sound/OSF/MyPack/voice01.wem` and `Sound/OSF/Seduce/F/a.wav`; clips can carry subtitle text that shows "in the
  dialogue box, attributed to the actor"; each actor has one voice channel and a new line cuts the old one via the AK
  `ExecuteActionOnPlayingID` stop. Positioned audio (`"emitter":"role"`) falls back to the listener on 1.16.244
  because "the former guessed registration entry point was removed rather than invoking an unverified ABI". **verified**
- Answers: **animation-audio-physics.md H3** (key) is now **answered in outline**: OSF calls the engine's Wwise with
  loose `.wem` or `.wav` files and shows its own subtitles, through SFSE. It does not create Wwise events or banks, so
  **H2** stays open. It strengthens **H1** and **quests-dialogue-voice.md V3**: loose `.wav` playback through the
  game's audio engine is possible with SFSE (**verified** as documented), though not through a plugin's INFO voice path.
  New limit: no positional (3D) voice on 1.16.244 in OSF's backend, so world-positioned barks from this route are not
  available today.

### Precedent: BACUP, a GPL-3 cross-game Creation Engine converter
Read: https://github.com/Bryant-21/bacup README.
- "Beth Asset Converter Universal Platform converts records and assets from one Bethesda / Creation Engine game to
  another". Wired pairs: Fallout 76 to Fallout 4 ("most complete"), Fallout 3 / New Vegas to Fallout 4 (partial),
  Skyrim SE to Fallout 4 (early). Per-game schemas exist for Starfield but no pair targets it. Rust core, Python
  orchestration, ImGui UI, GPL-3.0. Uses the FO4 CK `-GenerateAnimInfo` when present, "else the CK-free native
  generator". **verified**
- Answers: a precedent for **tools-and-scripting.md** (schema-driven translation, FormID remapping, per-pair hooks,
  a CK-free AnimTextData generator) and for the release phase (a GPL-3 converter that ships no game data).
  Question to add: can we reuse BACUP's FO4 schema or asset converters (GPL-3 compatible), or talk to its author?

## Sources
- https://github.com/ianpatt/sfse (sfse/PluginAPI.h, sfse/Hooks_Scaleform.cpp)
- https://github.com/libxse/commonlibsf (include/RE/U/UI.h, include/RE/I/IMenu.h, include/RE/IDs.h, EXCEPTIONS)
- https://github.com/Starfield-Reverse-Engineering/CommonLibSF (archived)
- https://github.com/ozooma10/osf-ui (src/Input/FocusMenu.h, FocusMenu.cpp, README, LICENSE)
- https://github.com/ramisotti13-eng/pulsar-tool (include/Lobby/LobbyMenu.h, src/Lobby/LobbyMenu.cpp, README)
- https://github.com/Mutagen-Modding/Mutagen (README; Mutagen.Bethesda.Starfield Faction.xml, Relation.xml, StarfieldMod_Generated.cs)
- https://api.nuget.org/v3-flatcontainer/mutagen.bethesda.starfield/index.json and NuGet registration pages
- https://www.nexusmods.com/starfield/mods/3256 (and ?tab=files)
- https://starfieldwiki.net/wiki/Starfield_Mod:Creation_Kit
- https://stepmodifications.org/wiki/Starfield:Creation%20Kit
- https://falloutck.uesp.net/wiki/Subgraphs
- https://starfieldwiki.net/wiki/Starfield:Affinity
- https://falloutck.uesp.net/wiki/SetCommandState_-_Actor
- https://falloutck.uesp.net/wiki/OnCommandModeGiveCommand_-_Actor
- https://ck.uesp.net/wiki/Relationship
- https://www.nexusmods.com/starfield/mods/17899 ; https://github.com/CarbonNode/CarbonUI (README, LICENSE)
- https://github.com/deveris256/sf_animation_io (blender_manifest.toml, README.md, docs/)
- https://github.com/ozooma10/osf-animation (README, LICENSE, docs/SCENE_SCHEMA.md)
- https://github.com/Bryant-21/bacup (README)
