# People and story: quests, dialogue, voice, lip sync, faces, bodies, companions

Author: people-story (framework research agent), 2026-10-19. Labels: **verified** (read in the linked source),
**supported hypothesis**, **unresolved**. Builds on, and does not repeat, `next-phase/npcs-ai-factions-dialogue-quests.md`,
`next-phase/voice-lipsync-companions.md` and `engine-mechanics/{dialogue,companions,quests,actors-and-npcs}.md`.

**Research limits (said up front):** the shared web-search budget for this turn ran out partway through, and Nexus then
rate-limited fetches (HTTP 429). These pages could **not** be read: nexusmods.com/fallout4/mods/75137,
bethesda.net "Monthly Modder: Sirick", nexusmods.com/starfield/mods/14176, /6401 and /6439. Claims that depended on them
(Sim Settlements 2's player-voice handling in particular) are marked **unresolved** below. A follow-up pass can close them.

## Bottom line

The community has already proven the hardest-looking piece of this area: **the Starfield Creation Kit's FaceFX compiler
regenerates lip sync for a whole master's dialogue from WAV files.** A Japanese lip-sync mod ran it over `Starfield.esm`
and `ShatteredSpace.esm` themselves, which is the same shape of job as our ~123k Fallout 4 lines. What is not proven is
running it unattended, how long 100k+ lines take, and how it behaves on a plugin it did not author. The second big
finding is that **Starfield's dialogue menu is a replaceable Scaleform SWF** (Enhanced Dialogue Interface ships as
`Data\Interface` files, no SFSE named), so a Fallout-style four-direction wheel is a UI file job, not an engine job; an
SFSE HTML UI framework (Carbon UI) is a second route. Third: Starfield's engine **flashes unvoiced lines past too
quickly to read**, which an SFSE plugin exists to fix; any "text first, voice later" stage of our pipeline needs silent
placeholder voice files or that plugin. Fourth: **faces and clothing are the weakest area**. The community changes NPC
faces by copying CharGenMenu presets in game, editing pre-baked facegen meshes in NifSkope, or applying morphs at run
time through SFSE (Souls of Cities); nobody has published a morph translator from another game. Clothing needs
re-skinning onto Starfield's skeleton through Blender add-ons that are interactive, not batch tools. People and story is
therefore a **translation job for records, a solved-in-principle job for voice and lips, and an open research job for
faces and outfits.**

## Findings

### 1. Lip sync in practice (Starfield CK FaceFX)

- **verified**: Lip Sync Japanese (Momidi, v1.20250531) regenerated lip sync for vanilla Japanese voice. Steps:
  extract `Voices_ja` BA2, convert `.wem` to `.wav` with **vgmstream**, place in `Data\sound`, load `Starfield.esm` (or
  `ShatteredSpace.esm`) in the CK via File > Data, run **Audio > Run FaceFX Compiler**, click Compile; `.ffxanim` files
  appear next to the WAVs; then pack into a BA2 and delete the WAVs. The author notes the generator does not seem to
  support Japanese phonemes, so mouths are approximate but "better than closed mouths."
  https://www.nexusmods.com/starfield/mods/12842
  - Consequence (**supported hypothesis**): the compiler works on a master's full dialogue set, not only small mods, and
    the input is WAV plus the INFO text the CK reads from the loaded plugin. Our master would play the role of
    `Starfield.esm` in that recipe.
  - Consequence (**supported hypothesis**): English text with English FO4 audio is the generator's best case, unlike the
    Japanese mod's mismatch.
- **verified**: The Nexus guide "Lip Sync for custom voice files" (Tbonex28b, Nov 2024): needs the CK; needs both WAV
  (for generation) and WEM (for playback); **file and folder paths must contain no spaces**; files under
  `Data\Sound\Voice\[ModName].esm\[VoiceType]\` named like `00849905.wav`; the **Voice Type must match the body type**
  (a male body can use a feminine-sounding voice if the voice type is male); the compiler "may appear to stop at a certain
  percentage" (watch `ffxc_00.log`); output is `.animset` then `.ffxanim`, placed automatically; common errors are
  "Could not find audio file", voice type/body mismatch and muted lines, usually from missing masters, misplaced WEMs or
  naming. https://nexusmods.com/starfield/mods/12576
- **verified**: FaceFX's own forum: FaceFX is embedded in the Starfield CK; a modder (DJLegends, Nov 2024) had `.animset`
  generation fail and traced it to **FaceFX being case sensitive for plugin names with spaces**; FaceFX staff say they do
  not know Bethesda's implementation and point users to Bethesda support. https://facefx.com/node/4600
- **verified**: Adoring Fangirl for Starfield (Reigor): voice made with ElevenLabs TTS; tools xTranslator, foobar2000,
  Wwise, MediaHuman Audio Converter, SF1Edit, WinHex. The original description says the CK "couldn't create lip files"
  so lips did not move; the changelog adds lip sync in 1.0.5 and "missing voice and lip sync files" in 1.1.0.
  https://www.nexusmods.com/starfield/mods/9957
  - Lesson (**supported hypothesis**): early CK lip generation was unreliable for some modders and later worked; the
    failures seen in the community trace to paths, names and voice-type/body matching rather than to a hard limit.
- **verified**: Liga of Followers (Iggdrasil7) added "facial animation of the voiced responses of companions to commands"
  in 1.01, for reused vanilla companion voice. https://www.nexusmods.com/starfield/mods/12598?tab=docs

### 2. Unvoiced lines in Starfield

- **verified**: Starfield Silent Voice (SFSE plugin) exists because the engine makes unvoiced mod dialogue "zoom by" too
  fast to read. It forces a shared set of silent voice files for any unvoiced line, shows subtitles for them, and (1.4)
  ships "working silent voice/lip sync assets" and an option to skip empty responses. Requires SFSE and Address Library.
  https://www.nexusmods.com/starfield/mods/3153
  - Consequence: the project's route (c) "text and audio first, lips later" is fine (audio sets line length), but any
    stage that ships **text before audio**, and any FO4 INFO with no voice file, needs either our own silent `.wem`
    placeholders (one per line, or one shared file via a per-response WEM id) or this SFSE plugin. **supported
    hypothesis** that per-line silent files work the way they do in FO4/Skyrim modding; not tested.

### 3. Dialogue UI: wheel vs list

- **verified**: Enhanced Dialogue Interface (Starfield, Seb263, v2.0.1) widens/centres the dialogue text area, removes
  delays when lines appear, adds number-key selection; installed by copying `Data\Interface` (SWF files, including an
  `Enhanced Fonts.swf`) plus the usual `bInvalidateOlderFiles=1` / `sResourceDataDirsFinal=` INI lines; an INI file in
  `Data\Interface` holds user settings; 1.0.1 fixed persuasion minigame glitches. SFSE is not mentioned.
  https://www.nexusmods.com/starfield/mods/871 , https://stepmodifications.org/wiki/Starfield:Enhanced_Dialogue_Interface
  - Consequence (**supported hypothesis**): the dialogue menu is a loose-file-replaceable Scaleform movie, so a
    Fallout-style four-direction layout, tone tags or full-line display can be built as an Interface file, without SFSE.
    This corrects the engine note's guess that a faithful wheel "possibly" needs SFSE (see Corrections).
- **verified**: Carbon UI (Squeetsquib, v0.11.0): SFSE plugin that renders HTML/CSS/JS menus (Ultralight) as a
  transparent overlay with input capture and a C API; needs Starfield 1.16.244, matching SFSE, Address Library and four
  Ultralight DLLs copied next to `Starfield.exe`. The page does not claim it can replace vanilla menus.
  https://www.nexusmods.com/starfield/mods/17899 (an example consumer: https://www.nexusmods.com/starfield/mods/17900)
- **verified**: Disable Dialogue Camera (Antonix35, Starfield mod 7157) was hidden by its author on 16 Dec 2025 as
  unsupported. https://www.nexusmods.com/starfield/mods/7157 ; it existed and worked with Enhanced Dialogue Interface per
  https://mezha.ua/en/2023/11/27/new-mod-allows-you-to-turn-off-the-dialog-camera-in-starfield/
- **FO4 precedents (verified)**:
  - Full Dialogue Interface (FO4 mod 1235): replaces `DialogueMenu.swf` and `MultiActivateMenu.swf` **and the Strings
    files** to show full lines in a list, with tone tags ([Lie], [Flirt], [Barter]); no F4SE; a "Lite" keeps the wheel
    with full text. https://www.nexusmods.com/fallout4/mods/1235
  - Extended Dialogue Interface, XDI (FO4 mod 27216): replaces `DialogueMenu.swf` plus an **F4SE** C++ plugin; removes
    the four-option limit, pulls full text dynamically, adds cue icons (question: does not advance; door: ends). For
    **unvoiced player dialogue, NPC dialogue starts right after the choice**, and the camera stays on the NPC.
    https://nexusmods.com/fallout4/mods/27216
  - Say Shh... (Mute Player) (FO4 mod 83415) silences the player by overwriting the player's voice files in
    `Data\Sound` (not by deleting them), and recommends XDI and a cinematic camera mod. https://www.nexusmods.com/fallout4/mods/83415
  - Lesson (**supported hypothesis**): FO4's data already carries both the short prompt (RNAM) and the full player line
    (response text). The silent-player choice in Starfield is native (no player audio path), so the only design choice
    is **which text the list shows**: FO4's paraphrase, the full line, or both (FDI's approach).

### 4. Faces

- **verified**: Enhanced Hadrian (Aurelianis): edited Hadrian's **facegen meshes** in NifSkope (a Starfield-capable fork),
  facegen textures in Photoshop, and **morphs pulled with CharGenMenu then written in xEdit**.
  https://www.nexusmods.com/starfield/mods/9326 . So named Starfield NPCs have pre-baked facegen assets (answers the
  actors-and-npcs open question; see Corrections).
- **verified**: Nexus article 1037 (Zaldan660) says "linking custom morphs to NPC character records isn't currently
  possible", and gives an in-game route: `player.capp <npc>`, edit with CharGenMenu (`slm 14 2`), then `capp 14` on the
  NPC. https://www.nexusmods.com/starfield/articles/1037 . The article's date was not visible; Enhanced Hadrian shows
  morph edits via xEdit do work, so the claim is at least outdated or narrower than stated (**supported hypothesis**).
- **verified**: CharGenMenu presets are `.json` under `SFSE\Plugins\Chargen\Presets\` and need SFSE (Naomi Nagata preset,
  https://www.nexusmods.com/starfield/mods/8015 ; Calliope Shaw, https://www.nexusmods.com/starfield/mods/17067).
- **verified**: Souls of Cities (SFSE) replaces crowd NPCs at run time, choosing face, expression, name, voice and outfit
  from text databases of editor ids, applies "FaceGen morphs" properly, and since 5.0 has a **custom FaceGen processor**;
  a native component fixes neck seams. https://allmods.net/?p=225677
  - Consequence (**supported hypothesis**): Starfield can build generic faces at run time from morph data (the vanilla
    crowd does), while named NPCs use pre-baked facegen; both routes exist for us.
- **verified**: Facial Animation Switcher (LarannKiar) changes NPC expressions with a single `.pex` of global functions,
  and notes many vanilla lines carry "override anims" that replace the set expression.
  https://www.nexusmods.com/starfield/mods/6428 . Relevant because FO4 INFOs carry emotion keyword plus value, and
  Starfield INFOs carry an animation block (engine notes).
- **unresolved**: no published tool maps FO4 face morphs/tints to Starfield face dials, morph groups or tint strings.
  No precedent found.

### 5. Bodies, skeleton, clothing

- **verified**: Starfield geometry lives in separate `.mesh` files under `Data/geometries/<folder>/`, referenced from the
  `.nif` BSGeometry node by a hashed "Mesh Path"; bone lists sit in the nif's `SkinAttach`; weights are in the `.mesh`
  (bone names are lost on Blender import and must be restored from the nif); a mesh must stay under 65,535 vertices.
  Body shapes for apparel live in `Data/meshes/morphs/.../morph.dat` (offsets, vertex colours, delta normals/tangents),
  referenced from the `.esm`. https://allmods.net/starfield-mods/starfield-miscellaneous/organization-of-starfields-meshes-and-related-assets/
- **verified**: Void SFG Bridge (Blender 5.1.1+, fork of SesamePaste233's Starfield Geometry Bridge) imports apparel
  `morph.dat` as **Basis, Overweight, Thin, Strong** shapes; "Morph Genesis" transfers skin weights from a known-good
  Starfield **donor** to a fitted target ("reference-driven, not one-click auto-rigging"); if geometry changes without
  matching morph data, set the ArmorAddon **Morph Data** to NONE; no claim of automatic CK record generation; Windows only.
  https://www.nexusmods.com/starfield/mods/17968 . Starfield Blender Extension (Blender 5.0+) adds skeleton matching
  help, morph tooling and Havok workflows. https://www.nexusmods.com/starfield/mods/16979
- **verified**: The 1.11.36 update renamed vanilla mesh paths and broke custom models; a migration tool exists.
  https://www.nexusmods.com/starfield/mods/9234 . (Lesson: our converter must not hard-code vanilla mesh paths.)
- **supported hypothesis**: FO4 armour on Starfield NPCs needs (1) geometry split into `.mesh` + nif, (2) re-skinning
  onto Starfield's human skeleton by bone-name mapping or donor weight transfer, (3) four body-shape morphs or Morph Data
  NONE (which then clips on non-default bodies). None of this is batch-proven; the published tools are interactive.
- **unresolved**: FO4 and Starfield human bone name lists side by side. No source read; a read-only nif dump of each
  game's `skeleton.nif` answers it.

### 6. Companions and followers

- **verified**: Liga of Followers (Starfield): recruit non-hostile people and animals; commands follow, stay, sneak,
  guard, relax; group commands; voiced for four companions. https://www.nexusmods.com/starfield/mods/12598?tab=docs .
  Precedent that a FO4-style command layer can be built on Starfield; how (script/SFSE) is not documented on the page.
- **verified**: "Aflin and DJLegend's Starfield NPC Template" (July 2026), a design document for **voiced followers**:
  biography, event-driven and conversation dialogue, useful conditions, **affinity events**; says the next step is
  exporting dialogue and recording lines "in the usual manner", and that there is no public CK wiki yet.
  https://www.nexusmods.com/starfield/mods/17694 . DJLegends is the same modder who debugged CK lip generation on the
  FaceFX forum: a likely **community contact** for voiced-follower practice.
- **verified**: Companion Dialogue Fix (Paulbrock) changes a quest script so companions say location-specific lines only
  in the right places; it is bundled in a Creation Club mod. https://www.nexusmods.com/starfield/mods/9285 (shows vanilla
  companion commentary is location-condition driven and buggy; our own commentary should not inherit Starfield's).

### 7. Big FO4 quest mods and voice

- **verified**: Sim Settlements 2 cast through Casting Call Club: 22 roles listed, 10 filled at the time, roles "3 lines
  to 200+ lines", unpaid volunteer team with IMDb credit and commissioned art, the production's **audio engineers clean
  and cut** recordings (actors do not), auditions include shouting lines for reverb; most roles North American / Boston.
  No player-voice role listed. https://www.castingcall.club/projects/fallout-sim-settlements
- **unresolved** (pages blocked, see top): how SS2 handled the voiced Sole Survivor's lines (silent, text only, or a
  reused vanilla subset). This matters as a precedent for what players accept.
- Relevance: we do not need new voice (we convert the player's own FO4 audio), but SS2 shows a volunteer pipeline for
  **new** lines if the port ever needs bridging lines (e.g. replacements for lines that reference the voiced player).

### 8. CK quest modding in practice

- **verified**: Starfield's community wiki main page lists no quest, dialogue, scene, follower, NPC or face tutorials;
  only form reference, Papyrus references, a VS Code debugging guide, the Starfield Voice Tool and the audio conversion
  pages. https://dev.starfieldwiki.net/wiki/Starfield_Mod:Main_Page . The NPC template above says no public CK wiki exists.
  So Starfield quest modding knowledge lives in Skyrim/FO4 CK wikis plus mod pages and Discords (**supported hypothesis**).
- **unresolved**: whether Starfield needs **SEQ files** for Start Game Enabled quests with dialogue as FO4 and Skyrim do
  (Skyrim guide: https://wiki.beyondskyrim.org/wiki/Arcane_University:Seq_Guide ; FO4 thread
  https://forums.nexusmods.com/topic/7720963-do-i-still-need-to-make-a-seq-file ). This could explain dialogue that never
  appears on our always-on dialogue quests, and it must be in the launcher's build if needed. Not read (search budget).

## Precedents and what they teach us

| precedent | what it teaches |
|---|---|
| Lip Sync Japanese (SF 12842) | CK FaceFX compiles a whole master's lines from WAV; input layout `Data\sound\voice\<master>\<vtype>\*.wav`; output beside it. Strongest evidence for our route (a). |
| Lip-sync guide (SF 12576) and FaceFX forum | No spaces in paths, plugin-name case, voice type must match body: rules our launcher must enforce before it starts a multi-hour run. |
| Starfield Silent Voice (SF 3153) | Unvoiced lines are unreadable in Starfield; we need placeholders for any text-only stage. |
| Enhanced Dialogue Interface (SF 871) | Dialogue menu is a loose SWF: a wheel or full-text UI is a file, not an engine hack. |
| FO4 Full Dialogue Interface / XDI / Say Shh | FO4 players already chose silent-player and full-text options; XDI's "NPC answers at once" is exactly Starfield's default behaviour. |
| Enhanced Hadrian, Souls of Cities | Faces: pre-baked facegen for named NPCs, run-time morphs for crowds; morphs editable via xEdit. |
| Void SFG Bridge | Clothing needs donor weight transfer and morph data; no batch tool. |
| Liga of Followers, NPC Template | Command systems and voiced followers are being built now; contacts exist. |
| Sim Settlements 2 casting | Volunteer voice pipeline for any new lines; audio cleaned centrally. |

## Risks

1. **Lip generation time and stability at 123k+ lines (high impact, medium likelihood).** The compiler "may appear to
   stop"; a CK GUI step lasting hours on the player's PC is fragile. Only a timed run of 1,000 lines answers it.
2. **Face mismatch for the named cast (high visibility, high likelihood).** No translator exists. Template faces will
   make Preston, Piper and Nick look like strangers; the FO4-head-as-ARMO route has untested seams, eyes and lip rig
   (FaceFX drives Starfield's face rig, not a static FO4 head mesh: an ARMO head would **not lip sync**; supported
   hypothesis, see Questions).
3. **Voice type must match body type for lips (medium).** Our own FO4-named voice types need whatever body/face
   archetype link Starfield's VTYP carries (VTYP ANAM "Animation Face Archetype", engine notes); wrong values give mute
   or lipless lines.
4. **Clothing on NPCs (high effort).** Without batch re-skinning, FO4 outfits on Starfield bodies stall people
   conversion visually even when quests work. Using Starfield outfits as stand-ins is the breadth-first escape.
5. **Unvoiced line flashing (low effort, high annoyance).** Easy to miss in offline tests; shows only in game.
6. **Community knowledge is thin for Starfield quests (medium).** No CK wiki; every engine question becomes a PC probe.
7. **UI mod conflicts (low to medium).** If we ship a dialogue SWF, users of Enhanced Dialogue Interface or StarUI-style
   mods will conflict; a GAMMA-style launcher must detect and order them.

## Questions for the framework

### New game (Vault 111 start)

1. **What does the dialogue list show for FO4 player choices: the prompt, the full line, or both?** Why: the first
   scenes (Nate/Nora, Codsworth, the Vault-Tec rep) are choice-heavy and silent-player turns paraphrases into guesswork.
   Options: RNAM prompt only (vanilla FO4 look); full response text (FO4 Full Dialogue Interface approach,
   nexusmods fallout4/1235); prompt plus full line in a custom SWF. Evidence: one converted scene in game with each
   choice. Who: owner decision after a PC probe.
2. **Which spouse lines and player-addressed lines break with a silent player?** Why: NPCs answer lines the player never
   audibly said; FO4's intro has the voiced player speaking to the mirror and spouse. Options: keep text, cut, or play the
   FO4 player audio as a sound on the player (next-phase note). Evidence: list INFOs in MQ101/MQ102 spoken by the player
   with no choice (monologue lines). Who: offline record scan, owner decision.
3. **Can the character-creation mirror reuse Starfield's chargen while FO4's face presets are unavailable?** Why: FO4
   chargen sliders do not map; CharGenMenu shows presets are JSON. Options: Starfield chargen as-is; a curated set of
   presets approximating FO4 looks. Evidence: whether Starfield's look menu can be opened in our cell
   (`showlooksmenu player 1` per https://www.nexusmods.com/starfield/mods/8015). Who: PC probe.

### Door animations

4. **Do scenes that end at load doors (FO4 escort scenes into Vault 111, Sanctuary) keep dialogue alive across the
   door?** Why: Starfield's package/door behaviour differs; dropped scenes stall quests. Evidence: one escort scene
   through a converted door. Who: PC probe (door track).

### All interiors

5. **Which interior scenes rely on FO4 camera paths, speaker/listener idles and furniture idles that Starfield INFO
   dropped?** Why: talking NPCs may stand rigid; dropped fields are listed in dialogue.md. Options: Starfield scene
   Animation/Camera actions; ignore for breadth. Evidence: count INFOs with SRAF/SNAM/LNAM per quest. Who: offline scan.
6. **Do generic interior NPCs (settlers, Diamond City vendors) get run-time faces or pre-baked ones?** Why: thousands of
   templated NPCs. Options: Starfield templates (cheap); a Souls of Cities-style run-time face pool from FO4-like
   presets (https://allmods.net/?p=225677). Evidence: does a templated converted NPC with no facegen render a face?
   Who: PC probe (the raider already does, so likely yes; check named ones).

### Launcher

7. **Can the launcher drive the CK FaceFX compile unattended, and how long does it take per 1,000 lines?** Why: the
   biggest build-time unknown. Options: CK command-line switch (unknown); UI automation of Audio > Run FaceFX Compiler;
   direct `ffxc.exe` (Tools folder) with the `.animset` the CK writes; ship lips later. Evidence: the Lip Sync Japanese
   recipe (https://www.nexusmods.com/starfield/mods/12842) timed on 1,000 FO4 WAVs; capture `ffxc_00.log`. Who: PC probe.
8. **Can the compile be split and resumed?** Why: a multi-hour step needs checkpoints. Options: one plugin per voice
   type batch; compile all and skip existing `.ffxanim`. Evidence: does a rerun skip lines that already have an
   `.ffxanim`? Who: PC probe.
9. **Which name and path rules does the launcher enforce before compiling?** Why: no spaces in paths, plugin-name case,
   numeric file names (https://nexusmods.com/starfield/mods/12576 ; https://facefx.com/node/4600). Users install Steam
   under "Program Files (x86)" with spaces. Options: stage WAVs in a space-free work folder and copy results back; junction.
   Evidence: one compile from a space-free staging dir. Who: PC probe.
10. **Does the compile need the WAVs and the WEMs, or only WAVs plus text?** Why: disk use (WAVs for 123k lines are tens
    of GB). Options per guide: both present. Evidence: compile with WAVs only. Who: PC probe.
11. **Does the launcher ship placeholder silent voice files for text-only lines, or require Starfield Silent Voice
    (SFSE)?** Why: unvoiced lines flash (https://www.nexusmods.com/starfield/mods/3153). Options: one silent `.wem` per
    line id (disk), one shared id via the response's WEM file field (record trick, untested), the SFSE plugin. Evidence:
    an INFO with a shared silent WEM id in game. Who: PC probe, owner decision on SFSE.
12. **Do we ship our own dialogue SWF, and how do we detect conflicting UI mods?** Why: Enhanced Dialogue Interface and
    similar replace the same files (https://www.nexusmods.com/starfield/mods/871). Options: no custom UI at first;
    optional wheel module; compatibility patches. Who: owner decision.

### World and planet

13. **Which FO4 radiant quests depend on locations Starfield's Story Manager cannot fire (Kill Actor, Trespass, etc.)
    and do any of them key on planet-only events?** Why: Minutemen settlement radiants are the backbone of mid-game
    story. Evidence: SMQN/SMEN scan (quests.md lists the dropped events). Who: offline scan.
14. **Do Starfield companions' location-driven commentary systems fire in our world?** Why: Companion Dialogue Fix shows
    vanilla commentary is location-keyed (https://www.nexusmods.com/starfield/mods/9285); if a Starfield companion
    follows the player into the Commonwealth, odd lines play. Options: fence Starfield companions out of our world. Who:
    owner decision, PC check.

### People and story

15. **Named-cast faces: which route, and does the chosen route lip sync?** Why: a static FO4 head as an ARMO will not be
    driven by FaceFX (supported hypothesis: Starfield lips drive the face rig of the race's head). Options: (a) template
    faces; (b) FO4 head as ARMO (no lips, likely); (c) hand-authored Starfield faces per named NPC via CharGenMenu then
    xEdit, the Enhanced Hadrian method (https://www.nexusmods.com/starfield/mods/9326), shipped as **records only**
    (morph values are our own data, not game assets); (d) an optimiser that fits Starfield face dials to FO4 head
    renders. Evidence: one ARMO head speaking a line; one hand-made Preston face. Who: PC probe, owner decision.
16. **Is a hand-made face record (option c) legal to ship in a no-assets GPL release?** Why: face dial values are
    numbers we author, not Bethesda assets, but they reference Starfield morph assets. Who: owner decision (and
    release-community question).
17. **Does Starfield need pre-baked facegen for a named NPC, or will it build one at run time from the NPC_ morph data?**
    Why: if pre-baked facegen is required, the CK must export it (another CK step for the launcher). Evidence: a new
    NPC_ with custom morphs and no facegen files, in game. Who: PC probe.
18. **Which voice type settings make lips work on our FO4 voice types?** Why: "Voice Type must match body type"
    (https://nexusmods.com/starfield/mods/12576). Options: copy VTYP ANAM face archetype from a matching Starfield VTYP;
    leave empty. Evidence: one line with and without ANAM set. Who: PC probe.
19. **Do FO4 emotion keywords and values on responses map to Starfield's facial expressions, and do they get overridden
    by line "override anims"?** Why: Facial Animation Switcher notes override anims on vanilla lines
    (https://www.nexusmods.com/starfield/mods/6428). Evidence: one converted angry line. Who: PC probe.
20. **How do we present persuasion: FO4 Charisma odds on the INFO, or Starfield's SPCH minigame?** Why: settled in
    dialogue.md to keep INCC, but the odds formula needs our SPECIAL. Options: script condition on our Charisma AV;
    perk entry point; colour tags in a custom SWF. Who: owner decision plus offline design.
21. **What does the four-slot wheel lose in a list?** Why: FO4 slot position carries meaning (Positive/Negative,
    sarcastic always in one slot). Options: order the list in FO4 slot order; add tone tags like FO4 Full Dialogue
    Interface ([Sarcastic], [Lie]); build a wheel SWF. Evidence: player test of one converted scene. Who: owner decision.
22. **How many FO4 player choice lines have no RNAM prompt (the wheel used the topic text)?** Why: an empty prompt shows
    as the full line or blank in Starfield. Evidence: offline scan of player topics. Who: offline research.
23. **Companions: command mode via dialogue only, or a Liga-style command layer?** Why: FO4 command mode (hold activate)
    is unresolved on CE2; Liga of Followers shows follow/stay/sneak/guard/relax commands are buildable
    (https://www.nexusmods.com/starfield/mods/12598?tab=docs). Who: owner decision; ask the Liga author how it is built.
24. **Do we reuse the community's voiced-follower template (Aflin and DJLegends) as a checklist for converted
    companions?** Why: it lists the dialogue categories a follower needs in Starfield
    (https://www.nexusmods.com/starfield/mods/17694). Who: offline reading; community contact.
25. **Which FO4 lines reference the voiced player so directly that they need rewriting or cutting?** Why: e.g. NPCs
    quoting the player. Options: keep; subtitles note. Who: owner decision; offline sampling.
26. **Is any new voice needed at all, and if so, AI or volunteers?** Why: bridging lines (e.g. explaining missing
    systems). Precedents: ElevenLabs in Adoring Fangirl (https://www.nexusmods.com/starfield/mods/9957), volunteer casting
    in SS2 (https://www.castingcall.club/projects/fallout-sim-settlements). Licensing and Nexus AI-content rules matter.
    Who: owner decision.
27. **NPC outfits: Starfield stand-in outfits first, or FO4 outfits converted?** Why: re-skinning is manual today
    (https://www.nexusmods.com/starfield/mods/17968). Options: Starfield outfits per FO4 outfit class; converted FO4
    outfits with Morph Data NONE (clips on non-default bodies); full re-skin later. Who: owner decision; PC probe of one
    converted outfit.
28. **Is the FO4 skeleton's bone set a subset of Starfield's human skeleton (name map possible), or different?** Why:
    decides whether clothing weights transfer by name. Evidence: read-only nif dump of both `skeleton.nif`. Who: PC
    probe / offline if the files are reachable.
29. **Do FO4's body weight morphs (thin/muscular/large) have a Starfield counterpart for NPCs?** Why: Starfield apparel
    carries Basis/Overweight/Thin/Strong morphs; NPC bodies use them. Mapping FO4 NPC weight values (MWGT/morph regions)
    to those keeps body variety. Who: offline research on both NPC_ layouts.

### Fallout systems

30. **Do companion idolize perks and affinity reactions need SFSE events (e.g. on-item-crafted, on-lockpick) that
    Starfield's Papyrus lacks?** Why: FO4 reactions fire from many player actions. Evidence: the native diff in
    papyrus-and-script-extenders.md, filtered to companion reaction triggers. Who: offline research.

### Release and community

31. **Which community authors do we contact first?** Candidates: DJLegends (CK lip sync, voiced followers), Momidi (whole
    master lip regeneration), the Void SFG Bridge author (batch re-skin), the Souls of Cities author (run-time faces).
    Who: owner (outreach is the owner's job under AGENTS.md).
32. **How do we explain to players that the Sole Survivor is silent and faces are approximations?** Why: expectations;
    FO4 players already accept silent-player mods (Say Shh, XDI). Who: owner, release notes.

### Tooling and testing

33. **How do we test lip sync offline?** Why: `.ffxanim` is not a public format. Options: only presence and count checks
    offline (one `.ffxanim` per `.wem`, as vanilla 4,462 = 4,462); in-game screenshot sequence for one line. Who: QA,
    PC probe.
34. **Is the CK FaceFX compiler deterministic, so a launcher build can be verified by hash?** Why: reproducible builds
    and resume. Evidence: compile the same 20 lines twice and compare. Who: PC probe.
35. **Can we read FO4 `.lip` curves to cross-check generated lips (route b) even if we never convert them?** Why: a
    cheap quality signal. Who: offline research, low priority.

### Cross-cutting

36. **Do we accept SFSE for UI and silent-voice fixes in breadth phases, or keep the base pipeline SFSE-free?** Why:
    several solutions found here (Silent Voice, Carbon UI, CharGenMenu, Souls of Cities) need SFSE; Enhanced Dialogue
    Interface does not. Who: owner decision (SFSE is allowed; this is about what is default).
37. **Do Start Game Enabled dialogue quests need SEQ files in Starfield?** Why: silent failure of always-on dialogue.
    Evidence: a dialogue quest with and without a generated SEQ. Who: offline research then PC probe.

## Corrections

- `engine-mechanics/dialogue.md` marks the CK FaceFX route as **supported hypothesis (not run here)**. Community practice
  now goes further: it has been run over whole masters (`Starfield.esm`, `ShatteredSpace.esm`) by Lip Sync Japanese
  (https://www.nexusmods.com/starfield/mods/12842). Still not run by us, but "works at master scale" is verified as a
  community result.
- `engine-mechanics/dialogue.md` says a faithful four-direction wheel "possibly" needs SFSE (Scaleform menu swap). The
  Starfield dialogue menu is replaced as loose `Data\Interface` SWF files by Enhanced Dialogue Interface, with no SFSE
  mentioned (https://www.nexusmods.com/starfield/mods/871). Layout changes likely need no SFSE; an XDI-style change to
  the engine's option handling might.
- `engine-mechanics/actors-and-npcs.md` asks "Does Starfield ship per-NPC facegen?". Enhanced Hadrian edits Hadrian's
  "facegen meshes" and "facegen textures" (https://www.nexusmods.com/starfield/mods/9326): named NPCs at least have them.
- The next-phase plan's route (c) "ship text and audio first with no lips" is fine, but a text-before-audio stage is not:
  unvoiced lines flash past in Starfield (https://www.nexusmods.com/starfield/mods/3153).

## Sources

- https://www.nexusmods.com/starfield/mods/12842 (Lip Sync Japanese)
- https://nexusmods.com/starfield/mods/12576 (lip-sync guide for custom voice)
- https://facefx.com/node/4600 (FaceFX forum, Starfield CK animset failure)
- https://www.nexusmods.com/starfield/mods/9957 (Adoring Fangirl)
- https://www.nexusmods.com/starfield/mods/12598?tab=docs (Liga of Followers)
- https://www.nexusmods.com/starfield/mods/17694 (Aflin and DJLegend's NPC Template)
- https://www.nexusmods.com/starfield/mods/9285 (Companion Dialogue Fix)
- https://www.nexusmods.com/starfield/mods/3153 (Starfield Silent Voice)
- https://www.nexusmods.com/starfield/mods/871 , https://stepmodifications.org/wiki/Starfield:Enhanced_Dialogue_Interface ,
  https://stepmodifications.org/wiki/Concept:Starfield_ModGroup_16-Interface (Enhanced Dialogue Interface)
- https://www.nexusmods.com/starfield/mods/17899 , https://www.nexusmods.com/starfield/mods/17900 (Carbon UI and a consumer)
- https://www.nexusmods.com/starfield/mods/7157 , https://mezha.ua/en/2023/11/27/new-mod-allows-you-to-turn-off-the-dialog-camera-in-starfield/
- https://www.nexusmods.com/fallout4/mods/1235 (Full Dialogue Interface)
- https://nexusmods.com/fallout4/mods/27216 (XDI)
- https://www.nexusmods.com/fallout4/mods/83415 (Say Shh... Mute Player)
- https://www.nexusmods.com/starfield/mods/9326 (Enhanced Hadrian)
- https://www.nexusmods.com/starfield/articles/1037 (changing NPC appearance)
- https://www.nexusmods.com/starfield/mods/8015 , https://www.nexusmods.com/starfield/mods/17067 (CharGenMenu presets)
- https://allmods.net/?p=225677 (Souls of Cities)
- https://www.nexusmods.com/starfield/mods/6428 (Facial Animation Switcher)
- https://allmods.net/starfield-mods/starfield-miscellaneous/organization-of-starfields-meshes-and-related-assets/
- https://www.nexusmods.com/starfield/mods/17968 (Void SFG Bridge) , https://www.nexusmods.com/starfield/mods/16979 (Starfield Blender Extension)
- https://www.nexusmods.com/starfield/mods/9234 (mesh path migration after 1.11.36)
- https://www.castingcall.club/projects/fallout-sim-settlements (SS2 casting)
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Main_Page
- https://wiki.beyondskyrim.org/wiki/Arcane_University:Seq_Guide , https://forums.nexusmods.com/topic/7720963-do-i-still-need-to-make-a-seq-file (SEQ, not read)
- Not readable this session (rate limit): https://www.nexusmods.com/fallout4/mods/75137 , https://bethesda.net/en-EU/news/monthly-modder-sirick ,
  https://www.nexusmods.com/starfield/mods/14176 , https://www.nexusmods.com/starfield/mods/6401 , https://www.nexusmods.com/starfield/mods/6439
