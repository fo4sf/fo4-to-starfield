# Animation, audio and physics: research findings and question framework

Author: Claude (cloud research agent, area "animation-audio-physics"), 2026-10-19. Builds on
`research/engine-mechanics/animations.md`, `radio-music-sound.md`, `physics-and-collision.md`,
`doors-activators-furniture.md`, and `research/next-phase/animations-ui-and-start.md` (section 2),
`physics-conversion.md`, `voice-lipsync-companions.md`. It does not repeat their record tables or file counts.
Door enter and exit animations have their own framework (`research/framework/door-animations.md`); this page only
links to it.

Labels: **verified** (read on the source page or in a file), **supported hypothesis** (evidence, not confirmed),
**unresolved**. "Verified" for a Nexus page means the page says so; it does not mean we ran the tool.

Research limits for this pass: the shared web search budget ran out, and WebFetch was rate-limited (HTTP 429) part
way through. Pages I could not read: the Animation IO GitHub README and docs folder
(github.com/deveris256/sf_animation_io), the wwiser docs (github.com/bnnm/wwiser), the Nexus article
starfield/articles/871, the Starfield wiki page "Adding Collision with 3ds Max 2021", and Nexus starfield/mods/8262.
They are listed under "Sources to read next". The Schaken-Mods tutorial on `.agx` and effect sequences was blocked
by robots.txt.

## What the community and tools offer today

### Animation
- **Animation IO** (Nexus Starfield 16184), a Blender add-on that imports and exports `.af` and `.rig`. Version
  1.0.0. By Deveris256 (Blender side) and Calaverah (the CALUMI library DLL), with Jojo. Recommended Blender 4.3.
  "No SFSE involved." Custom Nexus permissions (no re-upload, no conversion for other games without permission).
  It does not list `.agx`, `.afx` or `.hkx`. **Verified** (page). The project already uses the same CALUMI.Animation
  library to write door clips (`src/fo4sf/native_door.py`; engine-mechanics/animations.md).
- Animation IO comments (page 1 of 4, read 2026-10-19), all user reports, **supported hypothesis**:
  - a weapon idle was replaced and "It actually works" (melik173, 20 Mar 2026);
  - a modder generated new subgraph files "with a Creation Kit launch argument" and a custom weapon animation played,
    although the generated files looked empty (melik173); another user said "the current CK doesn't seem to actually
    generate" (jkruse05, 19 Mar 2026). The launch argument was not named on the page I could read;
  - a custom race (BB droids) works, but some animations stop when the player moves away (Bonepunk, 26 Mar 2026);
  - weapon animations broke after editing weapon nodes in the 1st or 3rd person rig (YellowZhao).
  Author: "Not dead. Development is going." (7 Jun 2026). No author answer on adding new vs replacing clips.
- **CALUMI Motion** (Nexus 16181, GitHub Calaverah/CALUMI.Motion), a node editor that imports and exports `.agx`
  behaviour graphs. Nexus version 0.1.1.1 (21 Mar 2026), "a very early release build"; GitHub says "functional MVP",
  LGPLv3, Qt6, "heavily advised to review and validate your agx output". `.af`/`.rig` raw editing and `.afx`
  creation are roadmap items. Main use so far: "to view and research the vanilla graphs". **Verified** (both pages).
- **Starfield-Behavior-Editor** (GitHub Monitor221hz), a WPF graph editor for `.agx`, GPL-3.0, marked WIP, .NET 7.
  Its README says Starfield uses "its own in-house behavior solution rather than Havok". **Verified** (page).
- **Starfield Rig Collection** (Nexus 16202, Flipdark95, v1.0, 21 Mar 2026): Blender 4.5 file with every vanilla
  armature: humans (3rd and 1st person), all creature body types, robots (Model A, Minibot, Model S, Model T, turrets,
  cameras). Modder's resource, no conversion to other games. **Verified** (page). Useful as a reference for retarget
  targets, but our pipeline must read rigs from the player's own Starfield files, not ship this file.
- **NAF SF / Native Animation Framework** (Nexus 7360, v1.2.3, 21 Dec 2024, **GPL-3**): SFSE plugin that plays glTF
  clips on actors, with blend graphs, IK and spring-bone nodes, face shape keys, a Papyrus API and an SFSE API. Limits
  on the page: it "can't replace vanilla animations" (it overrides them while playing), it does not save state across
  loads, and only the human skeleton by default (other races need JSON skeleton files). **Verified** (page).
- **SAF / Deputy NAF** (Nexus 16124, v6.0, updated 17 Oct 2026): successor to NAF for glTF/GLB, and FBX via `saf go`
  ("successfully tested with Mixamo assets"). Restrictive permissions, adult focus, 7 open bugs. **Verified** (page).
- **OSF Animation, Native Scene Framework** (Nexus 17457, ozooma10, v1.4.0, 30 Jul 2026): SFSE scene engine that
  plays synced multi-actor GLTF / GLB / `.af` clips "on one shared clock", JSON scene graphs, "engine-native Wwise
  audio with subtitles", a Papyrus API (`OSF.*`), and an optional library of "thousands of Starfield's own clips,
  humans plus 27 creature species". "Work in progress". Source on GitHub. **Verified** (page). Relevant as a
  precedent for paired and synced animation outside the behaviour graph, and as proof that a plugin can trigger
  Wwise audio of its own choosing (how it does that is **unresolved**).
- **Starfield Blender Extension** (Nexus 16979, MrTrilB, 1.6.0 beta, Blender 5.0+): NIF and `.mesh` import/export,
  "Collision authoring (colliders, collision layers, rigidbody and constraint controls)", Havok debug views, and
  "animation" among its workflows without detail. "Still a work in progress". **Verified** (page). The constraint
  controls are the first public sign that someone writes Starfield Havok constraints (not tested by us).
- **zsw Weapon Animation via Effect Sequence** (Nexus 17294, May 2026): proof of concept that animates a weapon part
  through the NIF effect sequence keyed to `WeaponAmmoCounterIndex`; first person only, overwrites vanilla files.
  **Verified** (page). Shows NIF-side keyframes still drive some motion in CE2.
- **True Ragdoll, No Death Animations** (Nexus 3625, updated 30 Aug 2026): the author edited about 200 death `.afx`
  files in `meshes/actors/human/...` so the start and stop frames for death animation and ragdoll are 0, and actors go
  straight to ragdoll; later extended to "All Aliens and Animals". **Verified** (page, author's own account).
  Consequence for us: `.afx` events control the hand-off from death clip to ragdoll (**supported hypothesis**).
- Early format thread (Nexus forums 13200546, Sep to Oct 2023): replacing walk and jog `.af` at the vanilla path
  works; `.afx` holds the footstep and audio events that FO4 kept inside `.hkx`. **Verified** (thread), the clip swap
  matching what engine-mechanics/animations.md already records.
- **CP's Menagerie** (Nexus 7783, Dec 2023): new creature meshes that reuse the ashta skeleton and animations; the
  author notes a limp and tail attacks that miss because "modders don't have the ability to add new animations"
  (true in Dec 2023, before Animation IO), and that adding creatures to planets needs reflection-data records modders
  could not edit. **Verified** (page); the "cannot add animations" part is out of date (**supported hypothesis**,
  given the 2026 tools above).

### Audio
- Workflow most Starfield sound mods use (Nexus articles 173 and 641, both read): unpack the `Starfield - Wwise
  Sounds XX.ba2` archives, search the generated `soundbanksinfo.json` for a name, note the numeric ID, audition with
  foobar2000 + vgmstream, make a replacement `.wem` in Wwise, and drop it in `Data/Sound/SoundBanks` with the same ID.
  "some sounds have multiple IDs or instances, so make sure you replace ALL of them." **Verified** (pages).
- Encoding: article 173 says use Vorbis "since the game won't recognize some encoding methods"; the music replacer
  article (535) says "some of the files (Akila bar, Londinion, Red Mile, Main menu song) need pcm encoding rather than
  vorbis", and that music is picked by numbered slots. **Verified** (pages). So PCM `.wem` does play in at least some
  slots, which supports the voice note's no-Wwise test (**supported hypothesis** for our own PCM writer).
- Wwise version: the Starfield wiki Xbox audio guide (and its Nexus copy, mod 12561) installs **Wwise
  2021.1.14.8108** with Authoring, opens `Tools/wwise/Starfield/Starfield.wproj`, imports WAVs, converts, and
  strips Wwise's numeric suffix from file names with a `.bat`. It packs `.wem` with the CK's Create Archive.
  **Verified** (both pages). This pins the version the voice note had as "2021.1.x".
- **Adding a brand-new sound event is not solved publicly.** Nexus forum thread 13493671 ("How to add a NEW sound into
  the game?", Jul 2024 to Sep 2025): soundbanks build in Wwise but the CK does not recognise them; the CK cannot
  preview sounds; "something to do with making sound banks and events"; a proposed workaround (a scene Radio or
  dialogue action pointing at a `.wem`, called from a script) was never confirmed. A commenter on article 173 also
  reports that regenerating soundbanks in the CK did not work. **Verified** (pages): no public recipe found.
- Every sound mod I sampled is a replacer (Nexus 7084 Beowulf firing sounds, 17375 headshot sounds: loose files under
  `Data/sound/soundbanks/`, INI `bInvalidateOlderFiles=1`). **Verified** (pages).
- Bank tools from other games: **rewwise** (GitHub vswarte, Apache-2.0/MIT) unpacks and repacks `.bnk` for Elden Ring,
  Armored Core 6 and Nightreign; creating a `.wem` "as of now requires Wwise studio itself". **Verified** (page).
  Whether it handles Starfield's Wwise 2021.1 bank version is **unresolved**. wwiser (bnnm) parses banks; not read.
- Radio mods in Starfield all sidestep the engine radio and Wwise: **Starfield Galactic Radio** (Nexus 3775, SFSE,
  v1.0.3, Oct 2023, source at GitHub ChairGraveyard/StarfieldRadio) "plays independently of the game audio"
  (MP3 and streams); **The Other Starfield Radio** (10286) is content for it; **Starfield Radio - Carbon UI** (17900,
  SFSE, streams, "touches zero game state"); **Star Radio Player** (16135, SFSE `RadioSFSE.dll`, local mp3/ogg/flac/wav
  and streams; its own sound effects "are included in star_radio - Main.ba2 and work without SFSE").
  **Verified** (pages). None uses ACTI RADR or the scene Radio action as far as the pages say.
- FO4 radio, for comparison (Nexus FO4 101520, 2026 tutorial, read in full): SNDR per song (category
  AudioCategoryRadio, output SOMStereo, about -8 to -12 dB static attenuation), a MESG for the station name, an NPC
  host with its own voice type (can be "Starts Dead"), a placed `RadioTransmitter` with RadioData frequency and
  "Ignores Distance Checks", a priority-30 quest whose alias is forced to the transmitter, scenes with one Radio action
  per song, `GetVMQuestVariable` conditions for shuffle, and a timer script that restarts the scene to avoid the
  "radio silence" bug (vanilla uses 900 s). Workshop radios duplicate `RadioDiamondCityReceiver`. **Verified** (page),
  and it matches the older tutorial already cited in radio-music-sound.md.
- Fallout London's custom-station bundle (Nexus fallout4london 552) fills 40 placeholder `.wav`/`.xwm` per station
  on frequencies 94.001 to 94.051 and has no shuffle "because too many tracks". **Verified** (page). Lesson: shuffle
  logic per station is the costly part, and fractional frequencies avoid clashes with other mods.

### Physics
- **Havok cloth export add-on** (Nexus 14491, OpheliaComplex, v0.3, Aug 2025): exports `BSClothExtraData` "using
  blender and the official art tools", needs a MeshConverter.dll and an FBXImporter fork; "does NOT MEAN IT'S EASY".
  **Verified** (page). Confirms the physics-conversion note: official Havok authoring for Starfield is cloth only.
- Starfield Blender Extension collision and constraint controls (above). **Verified** that the page claims them;
  output quality **unresolved**.
- Death to ragdoll hand-off via `.afx` (True Ragdoll, above).

## Precedents and lessons
- **Skyblivion / Skywind** (Nexus interview, Feb 2017): the lead creature developer came from Skywind and built a
  creature workflow reused across both; he used "more than 10 tools in about 5 different coding languages" and hit
  bugs in community and commercial tools; Oblivion creatures had "about 6-8 animations per creature walking cycle"
  against Skyrim's "10-12". Music: they kept the original soundtrack and added new pieces. The installer checks for a
  legitimate Oblivion copy. **Verified** (page). Lessons for us: (1) creature animation is its own specialist lane and
  the slowest one; (2) a converted creature looks wrong when its clip set is thinner than the target engine's graph
  expects, so plan which Starfield graph states each FO4 creature must fill; (3) tool sprawl needs a single pipeline.
- **FO4 animation history** (Nexus forum 13200546): FO4's animation scene grew because modders had HCT 2014 and the
  CK generated metadata; Starfield's tools are Bethesda in-house, so nothing comparable exists from Bethesda for
  clips. **Verified** (thread opinion, 2023). The 2026 community tools (Animation IO, CALUMI) fill part of that gap.
- **CP's Menagerie** (above): reusing the nearest vanilla creature skeleton works and ships, but gait and attacks give
  it away. A fallback for FO4 creatures in the "breadth before polish" phase. **Verified** (page).
- **Fallout London** radio bundle and FO4 radio tutorials: the engine radio needs one scene action per track and a
  restart timer; the radio-silence bug is a known FO4 failure. **Verified** (pages).
- **Starfield radio mods** chose SFSE players over the engine radio, presumably because adding new Wwise events is
  unsolved. **Supported hypothesis** (no author says why).
- No FO4-to-Starfield or Skyrim-to-Starfield animation or audio conversion project was found in this pass; the only
  hit was this project's own issue #40 (help wanted on `.af`). **Unresolved** (search budget ran out before a wider
  search of Capital Wasteland, Tale of Two Wastelands audio, and Beyond Skyrim creature workflows).

## Possibilities and hard limits in CE2
- **Possible today:** replacing `.af` clips at vanilla paths (players do it; **verified** by several pages);
  writing `.af`/`.rig` (Animation IO, our door work; **verified**); editing `.afx` events to change behaviour such as
  death-to-ragdoll timing (**verified** by True Ragdoll's account); playing arbitrary clips on actors through SFSE
  plugins (NAF, SAF, OSF; **verified** pages); reading and writing `.agx` graphs (CALUMI Motion, Behavior Editor;
  **verified** pages, output trust **unresolved**).
- **Probably possible, unproven:** new subgraph data generated by the CK for new clips (one user report;
  **supported hypothesis**); new races with own rigs (one user report of a custom race with animation issues;
  **supported hypothesis**); a plugin-shipped new `.agx` graph loaded by a base form's animation graph component
  (**unresolved**; door work uses vanilla graphs only).
- **Audio possible today:** replacing any vanilla sound by `.wem` ID (**verified**); PCM `.wem` plays in some slots
  (**verified** by the music article); new voice lines for new dialogue as `.wem` under `sound\voice\<plugin>\...`
  (**verified** in the Xbox guide and the voice note's workflow, playback of ours **unresolved**).
- **Audio hard limit (for now):** adding new Wwise events and banks that the engine and CK recognise has no public
  recipe (**verified** absence in the threads read). Workarounds: reuse vanilla events with replaced `.wem` (breaks
  vanilla sounds, unacceptable for a mod that keeps Starfield intact unless the event is unused), route sounds through
  dialogue or radio scene actions (voice path), or an SFSE audio player outside Wwise (radio mods do this).
- **Physics possible today:** static, keyframed and single dynamic bodies (project, **verified** in game). Cloth via
  official art tools (**verified** page). Constraints: one community tool claims authoring (**supported hypothesis**).
- **Licensing limits:** Wwise cannot be redistributed (voice note); several community tools forbid conversion or
  redistribution (Animation IO, CALUMI Motion Nexus page, Rig Collection), while CALUMI.Motion source is LGPLv3,
  Starfield-Behavior-Editor GPL-3.0 and NAF GPL-3. Our launcher can only bundle what the licence allows.

## Question framework

Columns: # | question | why it matters (decision it drives) | known so far (source) | cheapest way to answer |
depends on / blocks | phase | key. Phases: NG = new game, INT = interiors, QP = quests/people, FS = Fallout systems,
REL = release.

### A. Clip conversion (FO4 `.hkx` to Starfield `.af` + `.afx`)
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| A1 | What share of FO4 clips are spline-compressed vs interleaved, and are any other Havok animation classes used? | Sizes the decoder: one codec or two | Spline assumed (PyNifly wiki); share unresolved (animations.md) | Class-name count over all FO4 `.hkx` with `hkpackfile.py` (PC, read-only) | Blocks A2; needs nothing | NG | **key** |
| A2 | Does our clean-room spline decoder reproduce FO4's bind pose on frame 0 within tolerance? | Go/no-go for converting any FO4 clip | Plan step A2 exists (next-phase note) | Synthetic fixture test + one PC readback against `skeleton.nif` | Needs A1; blocks A3-A5, all creature work | NG | **key** |
| A3 | Can Animation IO's library (CALUMI.Animation) be called headless from the launcher, and does its licence allow us to ship or call it? | The writer is the last pipeline step; a Blender-only path cannot run on players' PCs | We already call CALUMI.Animation from `native_door.py`; Nexus permissions are restrictive; GitHub licence not read | Read the CALUMI.Animation repo licence; ask Calaverah in writing; time a 100-clip batch | Blocks launcher animation step; alternative is our own `.af` writer | REL | **key** |
| A4 | What are the unknown `.af` header field 4 and the compression scheme, well enough to write `.af` without CALUMI? | Removes a third-party dependency if A3 fails | Field 2 = bone count verified; field 4 unresolved (research-log 2026-10-09) | Diff 10 vanilla `.af` headers against frame counts and `.afx` lengths | Fallback for A3 | REL | |
| A5 | Which FO4 annotation events (foot, sound, weapon) have a Starfield `anim_events.xtbl` equivalent, and which need new events? | Missing events mean silent footsteps or broken weapon timing | `.afx` is XML of events by frame (verified); mapping not done | Dump all FO4 annotation strings and all `anim_events.xtbl` names; join by meaning | Needs A2; feeds audio C-section footsteps | NG | |
| A6 | How does the retarget handle FO4's 3 spine bones to Starfield's 4, fingers, and the root motion scale? | Visual quality of every human clip | Plan proposes interpolation for C_Spine1 (next-phase note) | One idle and one walk retargeted, screenshot side by side with FO4 | Needs A2; blocks first-person (F) | QP | |
| A7 | What do FO4's 14,396 `.txt` files in Animations.ba2 hold, and do they matter for conversion? | Could carry per-clip data we would otherwise lose | Unresolved (animations.md) | List 20 names, read 3 (PC) | None | NG | |

### B. Behaviour graphs, tables and wiring (`.agx`, `.xtbl`, subgraphs, IDLE)
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| B1 | Can a plugin add a new clip that the game plays without replacing a vanilla file (new IDLE pointing at a new `.af`, with CK-generated subgraph data)? **Decided by owner, 2026-10-19 (page PE-2, talk-through 22:04Z): play FO4's own clips through SFSE community glTF players first; move them into Starfield's .af format later.** Owner's note: "I want stuff to be as like fallout as I can so that is the focus" | Decides whether FO4 idles can coexist with Starfield's, or must replace them | One user reports CK subgraph generation via a launch argument worked, another says it does not (Animation IO comments, Mar 2026) | Find the launch argument (CK2 docs, Animation IO GitHub docs, ask melik173); one test IDLE in a test plugin, `playidle` in game | Blocks every FO4-specific idle, furniture and creature clip; needs A3 | NG | **key** |
| B2 | Can a plugin ship a new `.agx` graph that a base form's animation graph component or a RACE loads? **Decided by owner, 2026-10-19 (page PE-2, talk-through 22:04Z): play FO4's own clips through SFSE community glTF players first; move them into Starfield's .af format later.** Owner's note: "I want stuff to be as like fallout as I can so that is the focus" | New creatures and FO4-only furniture need graphs Starfield lacks | Doors use vanilla graphs only (door work); CALUMI Motion and Behavior Editor write `.agx` (pages) | Copy a vanilla door graph under a new name, point one test DOOR at it, test in game | Blocks creature graphs (C), animated activators (E) | INT | **key** |
| B3 | Is CALUMI Motion's `.agx` output byte-identical on a round trip of every vanilla graph? | Trust in any graph edit | "review and validate your agx output" (GitHub) | Round-trip all 347 vanilla `.agx` offline, diff | Needs B2 to matter | INT | |
| B4 | Where did FO4 IDLE DATA (loop min/max, replay delay, flags) go in Starfield: graph, `.afx`, or nowhere? | Idle timing for every converted IDLE | DATA gone, FNAM flags only (animations.md) | Dump 10 Starfield IDLE + their `.afx`, compare to an FO4 counterpart | Feeds IDLE translation | QP | |
| B5 | Which FO4 RACE subgraph roles and keyword sets (SAKD, STKD, SRAF) map to Starfield's roles, and what replaces FO4's "Idle" role? | Weapon, furniture and idle clip-set selection | Role enums differ (animations.md) | Table of both enums from xEdit; test one keyworded weapon subgraph | Needs B1 | FS | |
| B6 | Do `PlayIdle`, `PlayIdleAction`, `PlayAnimation`, `PlayGamebryoAnimation` exist in Starfield Papyrus with the same behaviour? | Many FO4 quest scripts call them | Unresolved (animations.md) | Grep Starfield `.psc` in ContentResources.zip | Blocks quest script shims | QP | |
| B7 | Do we use an SFSE animation framework (NAF GPL-3, OSF, SAF) for scripted FO4 scenes instead of the graph? | A fallback for paired and scene animation if B1/B2 fail; adds an SFSE dependency (allowed) | NAF is GPL-3 and cannot replace vanilla clips or survive a reload; OSF plays `.af` and Wwise audio (pages) | Read OSF's GitHub licence and API; one scripted two-actor scene in a test cell | Optional; depends on B1 outcome | QP | |

### C. Creatures and robots
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| C1 | For each FO4 creature (deathclaw, mirelurk, radroach, super mutant, Mr. Handy, protectron, assaultron, sentry bot), which Starfield race and rig is the nearest stand-in, and what breaks? | Breadth-first plan: populate the world with stand-ins before own rigs | CP's Menagerie reused ashta rigs (limp, tail attacks) (page); Starfield has 27 creature species in OSF's library, robots Model A/S/T, Minibot (Rig Collection) | Table of FO4 creature skeleton bone counts vs Starfield rigs; one mesh bound to a stand-in rig in game | Blocks creature encounters; needs actor rebinding (next-phase A1) | QP | **key** |
| C2 | Can a new RACE with its own `.rig` and its own clip set work end to end (move, attack, die, ragdoll)? | Real FO4 creatures need own rigs | One custom race report with clips stopping at distance (Animation IO comments) | One test race from a Starfield creature copy with a renamed rig and copied clips | Needs B1, B2; blocks C3 | FS | **key** |
| C3 | How many graph states does a Starfield creature graph expect, and how many FO4 clips does each creature have to fill them? | Skyblivion lesson: thin clip sets look wrong | Skyblivion: 6-8 vs 10-12 clips per walk cycle (interview) | Count states per creature `.agx` (CALUMI Motion) vs FO4 clip folders | Needs B3 | FS | |
| C4 | Does Codsworth (Mr. Handy) fit the Minibot rig, or does he need his own? | Codsworth is in the first hour of the new game | Plan A4 assigns his clips to the Minibot rig (next-phase note) | Bone and hierarchy comparison; one thruster idle in game | Needs A2; blocks NG companion | NG | **key** |
| C5 | How does Starfield stop animations on actors far from the player (the "stops at distance" report), and does it affect converted creatures? | Creatures freezing in the distance is a visible bug | One user report (Animation IO comments) | Test the custom race at 30, 60, 100 m | Needs C2 | FS | |

### D. Furniture, idle markers and held props
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| D1 | Which FO4 FURN marker types have a Starfield furniture animation set with matching enter/idle/exit clips (`enterfromstand`, `idle`, `exittostand`)? | Sitting, sleeping, leaning and work stations in every interior | Starfield furniture clip layout verified (animations.md) | List FO4 furniture behaviours by FNPR type vs Starfield folders under `animations/furniture/` | Blocks INT furniture; needs nothing | INT | **key** |
| D2 | How does a Starfield NIF mark furniture entry points, and does our converted FO4 furniture NIF carry them? | NPCs and the player must sit at the right spot | Unresolved (doors-activators-furniture.md) | Dump one vanilla chair NIF + its FURN `NNAM` | Blocks D1 test | INT | |
| D3 | Do FO4 IDLM archetype and flavor keywords (PNAM/QNAM) have Starfield equivalents, or do we fall back to Starfield idle markers by kind? | Sandboxing NPCs need idle markers | IDLM layout close (animations.md) | Keyword list join; one placed IDLM in a test cell | QP sandbox packages | QP | |
| D4 | Do held props (ANIO: clipboard, cigarette, mug) still attach and unload without FO4's BNAM unload event? | Many FO4 idles hold props | BNAM gone in Starfield (animations.md) | One Starfield idle that uses an ANIO; inspect its `.afx` for an unload event | Needs B1 for FO4 idles | QP | |
| D5 | Are FO4 workbench and terminal "use" animations replaceable by Starfield's equivalents without visible mismatch? | Workshop, terminals and crafting in FS phase | Benches placed as vanilla kinds (stations.md) | One converted bench used in game | Tied to workshop framework | FS | |

### E. Doors and animated activators
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| E1 | Can FO4's multi-stage animated activators (Vault 111 elevator stage1..stage8, gear door Stage0..3) be played from a graph that exposes named events, or must they become `TranslateToRef` platforms? | Vault 111 is the new-game opening | Not done (doors-activators-furniture.md) | One graph copy with named events driven by Papyrus `PlayAnimation` on a test ACTI | Needs B2; owned jointly with door framework | NG | **key** |
| E2 | Do door and activator `.afx` sound events play converted door sounds, or only the DOOR's Wwise sound refs? | Doors need sound for the full feel | Vanilla door sounds mapped from Starfield (door framework A7) | One door clip with an `.afx` sound event, listen in game | Needs audio G1 | INT | |
| E3 | Door enter and exit, load doors: see `research/framework/door-animations.md` | Avoids duplicate work | Owned by the Door animations thread | n/a | n/a | INT | |

### F. First person, weapons, Pip-Boy and power armor animation
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| F1 | Do FO4 weapons use Starfield's first- and third-person weapon clip sets by weapon class, or do we need FO4 reloads? | Combat feel and every weapon in FS phase | Starfield first-person rigs exist (animations.md); editing weapon nodes broke animations for one user (Animation IO comments) | Map FO4 weapon animation types to Starfield weapon subgraphs; one converted pistol in game | Needs B5 | FS | **key** |
| F2 | Can NIF effect sequences animate FO4 weapon parts (cylinders, belts, counters) as the zsw proof does? | Cheap moving parts without graph edits | Proof of concept on ArcWelder, first person only (Nexus 17294) | Repeat on one FO4 revolver cylinder | None | FS | |
| F3 | Is the Starfield subgraph role "Pipboy" usable for an arm-mounted menu animation (raise, lower, scroll)? | The Pip-Boy is FO4's main UI | Role exists, use unresolved (animations.md) | Search Starfield `.agx` and `anim_actions.xtbl` for Pipboy strings | Tied to UI framework | FS | |
| F4 | Power armor entry/exit and power armor locomotion: what Starfield furniture or race mechanism could host them? | Power armor is FS phase core | See power-armor.md | Read power-armor.md, then a clip-count of FO4 PA folders | Needs B1, B2 | FS | |

### G. Facial animation and death
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| G1 | Does the FaceFX path (`ffxc.exe`, LipGenerator) run headless on the player's PC for every converted line? | Lip sync for all FO4 dialogue | Tools listed, command-line use unresolved (voice note) | Owned by the voice note; listed here only to keep the dependency visible | Blocks QP dialogue quality | QP | |
| G2 | Do FO4 death `.afx` timings need editing so converted actors ragdoll like FO4 (no long death clips)? | FO4 players expect ragdoll deaths | True Ragdoll edits death `.afx` start/stop frames to 0 (page) | One edited human death `.afx` in a test plugin; compare to vanilla | Optional polish; needs nothing | FS | |
| G3 | How does Starfield do paired animations (kill moves, synced idles), and can FO4 kill moves map onto them or onto OSF-style synced playback? | FO4 melee and VATS kill cams | Unresolved (animations.md); OSF plays synced multi-actor clips (page) | Search `anim_events.xtbl` for paired, killmove, sync; read OSF docs | Ties to VATS framework | FS | |

### H. Sound effects and Wwise events
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| H1 | Does a self-written PCM (and Wwise ADPCM) `.wem` play when placed at a vanilla ID? | Decides if the launcher needs Wwise at all | Music article: some slots need PCM (Nexus article 535) | Write one PCM `.wem` for an unused vanilla sound ID, play in game (same as voice note test 2) | Blocks H2 option choice and launcher design | NG | **key** |
| H2 | Can we create **new** Wwise events and banks that Starfield loads (via a copy of `Starfield.wproj` in Wwise 2021.1.14.8108, the CK, or a bank writer)? | 5,476 FO4 SNDR need playable events without touching vanilla sounds | No public recipe; CK does not recognise new banks (Nexus forum 13493671, article 173 comments) | (1) Build one bank with one event in `Starfield.wproj`, add a WWED with its GUID, load in game; (2) inspect a bank's `.json` sidecar and the `soundbanksinfo.json` to see how the engine finds banks; (3) ask the Starfield Geometry Bridge or OSF authors | Blocks every non-voice sound in the mod | NG | **key** |
| H3 | How does OSF play "engine-native Wwise audio with subtitles" for its own scenes? | A working pattern for mod-authored audio inside Wwise | Claimed on the page (Nexus 17457) | Read OSF source on GitHub | Informs H2 | QP | **key** |
| H4 | If H2 fails, can FO4 sounds route through the voice path (dialogue or scene Radio/Dialogue actions, `.wem` under `sound\voice\<plugin>\`), and how far does that reach (ambient loops, weapons, footsteps)? | Fallback that keeps vanilla sounds intact | Proposed, unconfirmed (forum 13493671); voice path is the one documented route (Xbox guide) | One SFX played from a scene Radio action and one from a Papyrus-started scene | Needs H1 | QP | |
| H5 | If all else fails, which FO4 sounds can reuse a vanilla Starfield event as-is (no replacement), by category (doors, impacts, footsteps, UI)? | Breadth first: sound everywhere, even if not FO4's | Door sounds already mapped this way (door framework A7) | Category table of FO4 SNDR (by SNCT) vs Starfield WWED names | Cheapest fallback; needs nothing | INT | |
| H6 | How many FO4 SNDR are Compound or AutoWeapon (CNAM), and how many are multi-file random sets? | Sizes Wwise container work | Counts per type unresolved (radio-music-sound.md) | xEdit or Fo4Export count, read-only | Feeds H2 effort estimate | NG | |
| H7 | Can Wwise (free for non-commercial use) be a required install for players, and is its licence compatible with a GPL-3 launcher calling it? | Launcher design and player friction | Voice note licensing paragraph | Read Audiokinetic's current non-commercial licence; ask once | Needs H1/H2 result | REL | |
| H8 | Does rewwise or wwiser read and write Starfield's Wwise 2021.1 bank version? | Bank writing without Wwise | rewwise targets FromSoftware banks (page) | Run wwiser read-only on one Starfield `.bnk` (PC) | Optional path for H2 | REL | |

### I. Music
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| I1 | Can a new MUST point at a new Wwise event (MTSH) for an FO4 track, or must FO4 music replace Starfield music slots? | FO4 exploration and combat music | Music replacers use numbered slots (article 535); MUST uses MTSH refs (radio-music-sound.md) | Same test as H2 with one music event | Needs H2 | INT | **key** |
| I2 | Does Starfield's MUSC priority and ducking reproduce FO4's combat and discovery music switching on our planet? | Music state feel | MUSC flags carry (radio-music-sound.md) | One location with an FO4 MUSC copy, combat test | Needs I1 | FS | |
| I3 | How does Starfield pick music per planet, location and ASPC, and where does our one Earth-like planet hook in (WRLD, location, ASPC AMUS)? | Commonwealth music zones | ASPC has AMUS (radio-music-sound.md) | Read music fields on one vanilla planet worldspace and its locations | Ties to world framework | NG | |

### J. Radio stations
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| J1 | Does Starfield's engine radio still work: ACTI RADR receiver + scene Radio action + `GetPlayerRadioFrequency`, with no XRDO transmitter and no TACT? | Decides engine radio vs SFSE player for Diamond City Radio and others | Fields exist in xEdit; no Starfield mod uses them (pages read) | One test plugin: RADR activator, a quest scene with one Radio action, listen in game | Blocks J2-J4 | FS | **key** |
| J2 | If J1 fails, do we use an SFSE audio player outside Wwise (as Galactic Radio does) for radio, and what does that cost in subtitles, volume sliders and pause behaviour? | Radio is core FO4 identity | Galactic Radio plays "independently of the game audio" (page) | Read the StarfieldRadio GitHub source for the audio library and licence | Needs J1; SFSE allowed by settled decisions | FS | **key** |
| J3 | How does the player tune in without a Pip-Boy radio tab (UI)? | Player access to radio | Pip-Boy radio is a UI rebuild (radio-music-sound.md) | Owned by UI framework; note dependency | Needs UI decision | FS | |
| J4 | How many FO4 radio scenes, songs and DJ lines exist, including DLC (Far Harbor, Nuka-World stations)? | Sizes the radio port | FO4 tutorial shows the scene structure (Nexus FO4 101520) | Fo4Export scan for SCEN Radio actions per quest | Feeds J1/J2 plan | FS | |
| J5 | Do the FO4 DJ lines (Travis, Three Dog style hosts) carry their story-state conditions (quest progress news) through translation? | Radio reacts to quests in FO4 | Radio topics are dialogue with conditions (tutorial) | Read 5 FO4 Diamond City Radio news topics' conditions | Needs QP dialogue translation | QP | |
| J6 | Licensed music: FO4's licensed songs are the player's own files converted locally; do any vanilla tracks carry rights restrictions that make even local conversion inadvisable? | Release safety | No game assets shipped (settled) | Check Bethesda's Creations and mod policy text on music | REL policy | REL | |

### K. Ambience, acoustics, footsteps and impacts
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| K1 | Can FO4 ASPC region sounds become Starfield AMBS ambience sets that use vanilla Starfield events, until H2 is solved? | Interiors and exteriors feel dead without ambience | AMBS is new in Starfield (radio-music-sound.md) | One converted interior with an AMBS built from vanilla events | Needs H5 table | INT | **key** |
| K2 | Do FO4 footstep sets (FSTP/FSTS) and impact data (IPDS/IPCT by MATT) map to Starfield's by material name? | Every step and bullet hit | MATT map by name planned (physics-and-collision.md) | Join MATT names; one surface walk test | Needs A5 for foot events | INT | |
| K3 | Which Starfield REVB aux bus best matches each FO4 reverb class (vault, cave, office)? | Acoustic feel per interior | REVB numbers replaced by aux bus GUID (radio-music-sound.md) | Table of FO4 REVB ANAM class vs Starfield REVB names | None | INT | |
| K4 | Weather sounds for our planet: which Starfield WTHR sound refs fit FO4's rain, wind, thunder and radstorms? | Real days and weather is settled | WTHR typed sounds (radio-music-sound.md) | Tie to weather-time-climate framework | Needs H5 | NG | |

### L. Physics: constraints, ragdolls, destruction, props
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| L1 | What does a decoded vanilla Starfield constraint blob look like (hinge, ragdoll), and does our tagfile writer emit one the game accepts? | Ragdoll props, hanging lamps, chains | No decoded blob yet (physics-conversion note); one community tool claims constraint authoring (Nexus 16979) | Dump one vanilla NIF with a joint via `hktagfile.py`; then export one hinge from the Blender extension and diff | Blocks L2, L3 | INT | **key** |
| L2 | Do FO4 creature ragdolls follow automatically once a creature has its own Starfield rig with physics, or does each rig need its own ragdoll data? | Every killed FO4 creature | Actor ragdolls follow the race skeleton (physics notes) | Inspect a vanilla creature skeleton NIF for its ragdoll bodies | Needs C2 | FS | **key** |
| L3 | How many FO4 DEST stages swap models or play sequences, and can each `DSTA` sequence become a graph event? | Destructible cars, barrels, terminals | DSTA is an anim event in Starfield (physics-and-collision.md) | Fo4Export count of DEST with DMDL/DSTA | Needs B2 for events | FS | |
| L4 | Do FO4 cars and fusion cores explode with chain reactions using Starfield EXPL and DEST? | A signature FO4 feel | Unresolved | One converted car with DEST stages and EXPL in game | Needs L3 | FS | |
| L5 | Should mass follow FO4 kg or a per-class Starfield range? | Push feel for 80k movable refs | Owner liked a 5 kg override; per-class table proposed (physics-conversion note) | Judge the QASmoke control queue once | None | INT | |
| L6 | Can FO4 cloth-like items (flags, curtains) use Starfield cloth via the official art tools, or do they stay static? | Visual polish | Cloth export add-on exists, hard to use (Nexus 14491) | Defer; one flag test after breadth phase | Optional | REL | |
| L7 | Do grabbed and thrown objects (Starfield's grab) behave with converted bodies, and are there FO4-only grab expectations? | Player interaction | Moving items pass by hand (physics-conversion note) | One grab-and-throw test of five converted items | None | INT | |

### M. Cross-cutting: tools, licences and the launcher
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| M1 | Which animation and audio steps run on the player's PC, which need Starfield's own Tools (CK, FaceFX, Wwise project), and which need third-party installs? | Launcher scope and install friction | CK Tools contain `Starfield.wproj`, LipGenerator, FaceFX (voice note) | One table per pipeline step; time each on 100 items | Needs A3, H1, G1 | REL | **key** |
| M2 | Which community tools can we depend on given their licences (CALUMI.Motion LGPLv3, Behavior Editor GPL-3.0, NAF GPL-3, Animation IO custom, OSF unknown)? | GPL-3 project, no forbidden redistribution | Licences from pages above | Read each repo licence; written permission where needed | Blocks bundling decisions | REL | **key** |
| M3 | Do we coordinate with the Animation IO and CALUMI authors (format docs, headless API) rather than reverse-engineer in parallel? | Saves weeks; avoids duplicate formats | Author active (Jun 2026 comment) | One public, owner-approved message (owner decides outreach) | Owner approval | REL | |
| M4 | How does conversion time scale: 15,741 FO4 clips, ~9.4k SFX/music files, 122,857 voice lines? | Launcher build-time budget | Counts from engine-mechanics pages | Time 100 of each on the PC, extrapolate | Needs A3, H1 | REL | |
| M5 | Do faction-specific sounds and animations (Brotherhood power armor clanks, Institute teleport, Railroad idles) need faction-aware conditions on IDLE, MUSC or radio? | Ties to the owner's interest in reusing Starfield faction mechanics | Faction systems covered in factions-crime-relationships.md | Note for the factions framework: list FO4 IDLE/MUSC/SCEN conditions that test faction membership | Cross-area | QP | |

## Sources
Read in this pass (Nexus, wiki and GitHub pages, 2026-10-19):
- Animation IO, Nexus Starfield 16184 and its posts tab: https://www.nexusmods.com/starfield/mods/16184 ,
  https://www.nexusmods.com/starfield/mods/16184?tab=posts
- Starfield Blender Extension, Nexus 16979: https://www.nexusmods.com/starfield/mods/16979
- OSF Animation, Nexus 17457: https://www.nexusmods.com/starfield/mods/17457
- NAF SF, Nexus 7360: https://www.nexusmods.com/starfield/mods/7360
- SAF Deputy NAF, Nexus 16124: https://www.nexusmods.com/starfield/mods/16124
- Starfield Rig Collection, Nexus 16202: https://www.nexusmods.com/starfield/mods/16202
- zsw Weapon Animation via Effect Sequence, Nexus 17294: https://www.nexusmods.com/starfield/mods/17294
- Cuter Female Idle, Nexus 17707: https://www.nexusmods.com/starfield/mods/17707
- CALUMI Motion, Nexus 16181 and GitHub: https://www.nexusmods.com/starfield/mods/16181 ,
  https://github.com/Calaverah/CALUMI.Motion
- Starfield-Behavior-Editor: https://github.com/Monitor221hz/Starfield-Behavior-Editor
- sf_animation_io fork (landing page only): https://github.com/kindaginga/sf_animation_io
- Nexus forum, "Animation in af, afx?": https://forums.nexusmods.com/topic/13200546-animation-in-af-afx/
- True Ragdoll, Nexus 3625: https://www.nexusmods.com/starfield/mods/3625
- CP's Menagerie, Nexus 7783: https://www.nexusmods.com/starfield/mods/7783
- Havok cloth export add-on, Nexus 14491: https://www.nexusmods.com/starfield/mods/14491
- Making Your Own Sound Mods, Nexus article 173: https://www.nexusmods.com/starfield/articles/173
- Sound files step-by-step, Nexus article 641: https://www.nexusmods.com/starfield/articles/641
- Music replacer guide, Nexus article 535: https://www.nexusmods.com/starfield/articles/535
- Porting Custom Audio Files to Xbox: https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox ,
  Nexus 12561: https://www.nexusmods.com/starfield/mods/12561
- Nexus forum, "How to add a NEW sound into the game?":
  https://forums.nexusmods.com/topic/13493671-how-to-add-a-new-sound-into-the-game/
- Sound replacers: https://www.nexusmods.com/starfield/mods/7084 , https://www.nexusmods.com/starfield/mods/17375
- rewwise: https://github.com/vswarte/rewwise
- Starfield radio mods: https://www.nexusmods.com/starfield/mods/3775?tab=docs ,
  https://www.nexusmods.com/starfield/mods/10286 , https://www.nexusmods.com/starfield/mods/17900 ,
  https://www.nexusmods.com/starfield/mods/16135
- FO4 radio tutorial 2026, Nexus FO4 101520: https://www.nexusmods.com/fallout4/mods/101520
- Fallout London custom stations, Nexus fallout4london 552: https://www.nexusmods.com/fallout4london/mods/552
- Skyblivion team interview (Nexus, 2017): https://www.nexusmods.com/hellishquart/news/13125
- Project issue #40 (search hit only): https://github.com/fo4sf/fo4-to-starfield/issues/40

Project files built on: `research/engine-mechanics/animations.md`, `radio-music-sound.md`,
`physics-and-collision.md`, `doors-activators-furniture.md`; `research/next-phase/animations-ui-and-start.md`,
`physics-conversion.md`, `voice-lipsync-companions.md`; `research/framework/door-animations.md`.

Sources to read next (blocked in this pass by the search budget or rate limits):
- Animation IO README and docs (the CK launch argument for subgraph generation, licence):
  https://github.com/deveris256/sf_animation_io
- wwiser docs (bank version support): https://github.com/bnnm/wwiser/blob/master/doc/WWISER.md
- Nexus article 871 (Starfield, collision or Havok topic, unread): https://www.nexusmods.com/starfield/articles/871
- Starfield wiki, Adding Collision with 3ds Max 2021:
  https://starfieldwiki.net/wiki/Starfield_Mod:Adding_Collision_with_3ds_Max_2021
- Nexus Starfield 8262 (physics-related, unread): https://www.nexusmods.com/starfield/mods/8262
- OSF Animation GitHub source (audio routing, licence), StarfieldRadio GitHub source (audio library, licence).
- Wider precedent search: Capital Wasteland and Tale of Two Wastelands audio and radio, Beyond Skyrim creature
  animation workflows, any Skyrim-to-Starfield animation ports.
