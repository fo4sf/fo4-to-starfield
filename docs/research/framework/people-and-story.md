# People and story

Part of the [next-phase framework](README.md). Waves 1 and 2, 2026-10-19. Sources: findings/people-story.md, findings/precedents.md (voice parts, incl. wave 2 Sim Settlements 2), findings/multi-game-scope.md (karma, reputation, affinity, factions and companions parts), findings/distribution-community.md (wave 2 languages part).

Covers quests, dialogue and its UI, the silent player, voice and lip sync (technical side only), NPC faces and bodies,
clothing, companions, factions, settlers and radiant quests. The **legal side of voice** (reusing FO4 voice, AI voice,
Capital Wasteland) lives in [release-community-legal.md](release-community-legal.md); this file only points there.
It builds on, and does not repeat, `next-phase/npcs-ai-factions-dialogue-quests.md` (records, scale, Story Manager,
Papyrus, fencing Starfield out) and `next-phase/voice-lipsync-companions.md` (the `.fuz` to `.wem` pipeline, AFFE,
companion order). Labels: **verified**, **supported hypothesis**, **unresolved**.

## In short

- Lip sync at master scale is proven by the community: the Starfield CK's FaceFX compiler regenerated lips for all of
  `Starfield.esm` and `ShatteredSpace.esm` from WAV (**verified**, SF mod 12842). Not proven: unattended runs, time per
  1,000 lines, and behaviour on a plugin it did not author.
- The dialogue menu is a loose-file Scaleform SWF (**verified** for Enhanced Dialogue Interface), so a Fallout-style
  wheel or full-line list is a UI file job, likely without SFSE (**supported hypothesis**).
- Unvoiced lines flash past unreadably in Starfield (**verified**, SF mod 3153): any text-before-audio stage needs silent
  placeholder files or the Silent Voice SFSE plugin.
- Faces and clothing are the weakest area: no morph translator and no batch re-skinning tool exist (**unresolved** /
  **verified** that published tools are interactive).
- Named Starfield NPCs render from per-NPC CK bakes (FaceGeom `.nif` plus face textures keyed by FormID and plugin);
  the bakes are GUI, per actor and crash-prone (**verified** community reports; runtime fallback **unresolved**).
- Always-on (Start Game Enabled) dialogue quests likely need `Data\SEQ\<plugin>.seq`, a bare FormID list we can write
  ourselves (**supported hypothesis**; the Starfield CK still makes SEQ files, **verified**).
- Voiced in both games: EN, FR, DE, ES, JA only (**verified**, Steam store API); the Starfield CK is English only.
- Most uncertain: whether bakes can be made without the CK GUI, and whether a converted voice type lips.
- Three decisions that unlock the most: **PS-01** (prompt, full line or both for player choices), **PS-08** (how the
  launcher runs the FaceFX compile, decided after one timed probe), **PS-15** (named-cast face route).

## What is settled

| item | source | label |
|---|---|---|
| Silent player by default | owner (findings/BRIEF.md) | owner decision |
| SFSE and the free Starfield CK MAY be required | owner (findings/BRIEF.md) | owner decision |
| Starfield's own animations first, FO4 clips later; breadth before polish | owner (findings/BRIEF.md) | owner decision |
| No game assets shipped; the conversion runs on the player's PC | owner (findings/BRIEF.md) | owner decision |
| Our own voice types, factions, quest types and Story Manager branch, fenced from Starfield | next-phase/npcs-ai-factions-dialogue-quests.md sections 5, 6, 8 | design default (not repeated here) |
| The CK's Audio > Run FaceFX Compiler builds `.ffxanim` for a whole master from WAV in `Data\sound\voice\<master>\<vtype>\` | https://www.nexusmods.com/starfield/mods/12842 | verified |
| Compiler traps: no spaces in paths, plugin-name case, numeric file names, voice type must match body type, `ffxc_00.log` shows stalls | https://nexusmods.com/starfield/mods/12576 , https://facefx.com/node/4600 | verified |
| The guide wants both WAV (to generate) and WEM (to play) | https://nexusmods.com/starfield/mods/12576 | verified |
| Unvoiced mod lines "zoom by"; Starfield Silent Voice (SFSE + Address Library) forces shared silent files and subtitles | https://www.nexusmods.com/starfield/mods/3153 | verified |
| Enhanced Dialogue Interface replaces the dialogue menu as `Data\Interface` SWF files; no SFSE named | https://www.nexusmods.com/starfield/mods/871 | verified |
| Carbon UI is an SFSE HTML/CSS/JS overlay menu framework (Starfield 1.16.244); it does not claim to replace vanilla menus | https://www.nexusmods.com/starfield/mods/17899 | verified |
| Named Starfield NPCs have pre-baked facegen meshes and textures; morphs can be edited via CharGenMenu then xEdit | https://www.nexusmods.com/starfield/mods/9326 | verified |
| CharGenMenu presets are `.json` under `SFSE\Plugins\Chargen\Presets\` and need SFSE | https://www.nexusmods.com/starfield/mods/8015 | verified |
| Souls of Cities builds crowd faces at run time from FaceGen morphs with its own FaceGen processor (SFSE) | https://allmods.net/?p=225677 | verified |
| Starfield geometry: `.mesh` under `Data/geometries/`, bones in nif `SkinAttach`, weights in `.mesh`, under 65,535 vertices; apparel body shapes in `morph.dat` | https://allmods.net/starfield-mods/starfield-miscellaneous/organization-of-starfields-meshes-and-related-assets/ | verified |
| Void SFG Bridge re-skins by donor weight transfer ("not one-click auto-rigging"); Morph Data NONE when shapes are missing | https://www.nexusmods.com/starfield/mods/17968 | verified |
| Update 1.11.36 renamed vanilla mesh paths; do not hard-code them | https://www.nexusmods.com/starfield/mods/9234 | verified |
| FO3 karma: -1000 to +1000 in five bands; gates companions and hit squads; AV 23 | https://fallout.fandom.com/wiki/Karma_(Fallout_3) ; xEdit FO3/FNV definitions | verified |
| NV reputation is a per-faction REPU record with GetReputation conditions (indices 573 to 575) | xEdit wbDefinitionsFNV.pas | verified |
| Every long-lived remake re-voiced; Capital Wasteland stopped over converting audio from the player's copy | findings/precedents.md section 5; see [release-community-legal.md](release-community-legal.md) | verified (press reports) |
| Starfield ships per-NPC face geometry at `meshes\Actors\Character\FaceGenData\FaceGeom\Starfield.esm\<FormID>.nif` and face textures under `facecustomization\starfield.esm\` | https://www.nexusmods.com/starfield/mods/5572 ; people-story W2-2 | verified |
| The CK has two bakes: Bake FCT (textures) and Bake Chargen Mesh Geometry; structure edits need the geometry bake; results inconsistent (bald heads, seams) | https://forums.nexusmods.com/topic/13521838-ck-bugquestion-%E2%80%9Cbake-chargen-mesh-geometry%E2%80%9D-always-crashes-%E2%80%94-is-this-broken-for-everyone/ ; https://www.reddit.com/r/starfieldmods/comments/1dp6yv8/npc_edits_having_issues/ | verified |
| CK facegen export writes nothing for actors with the Chargen preset flag or a Use Traits template | https://www.reddit.com/r/CreationKit/comments/1lp64l5/creation_kit_not_generating_facegen_files/ | verified |
| SEQ files are needed only for Start Game Enabled quests (FO4/Skyrim); format is a flat array of 32-bit FormIDs in `Data\Seq\<plugin>.seq` | https://forums.nexusmods.com/topic/7720963-do-i-still-need-to-make-a-seq-file/ ; xEdit `xeMainForm.pas` (dev-4.1.6) | verified |
| The Starfield CK still generates SEQ files (Drag and Drop Quest SEQ Tool) | https://www.nexusmods.com/starfield/mods/13119 | verified |
| Full audio: FO4 EN/FR/IT/DE/ES/JA, Starfield EN/FR/DE/ES/JA; Starfield CK English only | Steam store API appids 377160, 1716740, 2722710 | verified |
| SS2 ships its own player-voice audio (male and female, robovoice placeholders in development) | https://wiki.simsettlements2.com/getting-started/patch-notes | verified |

Corrections carried from the findings (people-story.md "Corrections"): the CK FaceFX route works at master scale in
community practice; a faithful wheel likely needs no SFSE; named Starfield NPCs do ship facegen; text-before-audio is
not safe without silent files. Wave 2 (people-story W2-2): named faces need a per-NPC CK bake, so "run-time build from
morphs" is no longer the leading hypothesis for named NPCs.

## Possibilities

### Dialogue UI and the silent player

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| Vanilla Starfield list, FO4 RNAM prompt as text | zero UI work | paraphrase guesswork; loses FO4 slot meaning | FO4 vanilla wheel text | supported hypothesis |
| List with full player line | clear choices | long lines; spoils the wheel's brevity | FO4 Full Dialogue Interface (fallout4/1235) | verified (FO4) |
| Custom SWF: prompt plus full line, tone tags | FO4 feel, clear | UI file to maintain; conflicts with other dialogue SWFs | FDI, XDI (fallout4/27216), EDI (starfield/871) | verified precedents; Starfield fit supported hypothesis |
| Four-direction wheel SWF | most faithful | most UI work; conflicts | XDI keeps a wheel with an F4SE plugin | supported hypothesis |
| HTML menu via Carbon UI | modern UI stack | SFSE, version-locked, not a vanilla-menu replacement | starfield/17899 | verified (tool), unresolved (fit) |
| Play FO4 player audio as a sound on the player | keeps voiced lines | menu must wait; legal side in release file | next-phase note "later option"; SS2 ships player lines in FO4 itself (wiki patch notes) | unresolved |

### Unvoiced and text-first lines

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| One silent `.wem` per line id | no SFSE | disk and file count | FO4/Skyrim modding practice | supported hypothesis, untested |
| One shared silent WEM id via the response's WEM file field | tiny | record trick, untested | none | unresolved |
| Require Starfield Silent Voice (SFSE) | proven fix, subtitles shown | SFSE dependency | starfield/3153 | verified |

### Lip sync (technical)

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| (a) Launcher drives CK Audio > Run FaceFX Compiler | proven output | GUI step, hours, may "appear to stop" | starfield/12842, 12576 | verified (manual) |
| (a2) CK command-line switch | headless | unknown in Starfield; engine-mechanics.md suggests trying the Skyrim/FO4 `-GenerateLips:<plugin>` form | engine-mechanics.md | unresolved |
| (a3) Call `ffxc.exe` directly with the CK's `.animset` | headless, resumable | undocumented | next-phase voice note | unresolved |
| (b) Convert FO4 `.lip` to `.ffxanim` | no CK step | format not public | none | unresolved |
| (c) Ship text and audio, lips later | fast breadth | closed mouths | Adoring Fangirl shipped without lips first (starfield/9957) | verified |

### Faces

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| Starfield template faces | free, works today | named cast look like strangers | converted raider renders (people-story Q6) | supported hypothesis |
| FO4 head as an ARMO | FO4 look | seams, eyes; likely no lip sync (FaceFX drives the race face rig) | none | supported hypothesis |
| Hand-made Starfield face per named NPC (CharGenMenu, then xEdit), shipped as record values | good likeness, no assets shipped | manual per NPC; legal check on values; also needs a CK bake (FCT plus geometry) per NPC on the player's PC, crash-prone | Enhanced Hadrian (starfield/9326); people-story W2-2 | verified (method); bake step verified |
| Our own writer for the FaceGeom `.nif` plus face DDS | no CK GUI step | format work; unknown effort | none | unresolved |
| Named NPC on a Use Traits template | no bake needed | no unique face | vanilla generic NPCs | supported hypothesis |
| Optimiser fitting Starfield dials to FO4 head renders | scalable | research project | none | unresolved |
| Run-time face pool for settlers and crowds | variety for thousands of templated NPCs | SFSE | Souls of Cities | verified (tool) |

### Bodies and clothing

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| Starfield stand-in outfits per FO4 outfit class | breadth now | not Fallout-looking | none needed | supported hypothesis |
| Converted FO4 outfits, Morph Data NONE | FO4 look | clips on non-default bodies; needs re-skin | Void SFG Bridge notes | verified (setting) |
| Full re-skin with donor weights and four morphs | correct fit | interactive tools only; no batch | starfield/17968, 16979 | verified (tools interactive) |

### Companions, affinity and alignment

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| Commands through dialogue only | cheap | loses FO4 command mode | vanilla Starfield | supported hypothesis |
| Liga-style command layer (follow, stay, sneak, guard, relax) | FO4 feel | build method undocumented | starfield/12598 | verified (exists) |
| Use the voiced-follower template as a checklist | complete dialogue categories, affinity events | reading time only | starfield/17694 | verified |
| One alignment system: FO4 affinity only | simplest | FO3/NV content later loses karma/reputation gates | FO4 | supported hypothesis |
| Superset: karma AV, REPU-style factions, affinity side by side | multi-game ready | rebalancing work | TTW keeps karma challenges | verified (TTW challenges); reconciliation unresolved |

### Quests, radiant quests and settlers

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| Own Story Manager branch for radiants | fenced from Starfield events | some FO4 SM events may not exist on CE2 | next-phase note section 6 | supported hypothesis |
| Rewrite radiants whose events are missing as scripted triggers | keeps Minutemen loop | script work | none | unresolved |
| Generic settlers on Starfield templates; run-time face pool later | thousands of NPCs cheaply | sameness | Souls of Cities | supported hypothesis |
| Our launcher writes `Data\SEQ\<plugin>.seq` for SGE quests | no CK step | Starfield FormID encoding for small/medium masters unknown | xEdit SEQ writer (Skyrim only); starfield/13119 (CK route) | supported hypothesis |

## Questions

### Dialogue UI and the silent player

**PS-01. What does the choice list show for FO4 player lines: the RNAM prompt, the full line, or both?**
- Why it matters: silent player turns paraphrases into guesswork; the Vault 111 opening is choice-heavy.
- Options: prompt only; full line (Full Dialogue Interface, https://www.nexusmods.com/fallout4/mods/1235); both in a custom SWF. (also: people-story Q1; engine-mechanics.md D3)
- Answer by: one converted scene in game with each variant. Who: PC probe, then owner decision.
- Blocks: New game, People and story.
- Status: open. PC job 21 (**verified**): Starfield ships 278,582 per-line `.ffxanim` files and no `.facefx` files; LipGenerator.exe needs `actor.facefx` and `actoranalysis.facefx`, which are not in the shipped data (source unresolved). The Starfield CK lip path is `-CompileFaceFXAnims` plus LipGenerator.exe (job 18). **Answered in part (2026-10-19, PC job 24, verified; research/engine-mechanics/dialogue.md):** LipGenerator.exe with the CK's Tools\FaceFX actors made `.ffxanim` files from a synthetic WAV in seconds, headless; job 25 compares the header with vanilla files. Open: time per 1,000 real lines, resume, and acceptance in game.

**PS-02. Do we ship our own dialogue SWF, and how does the launcher detect conflicting UI mods?**
- Why it matters: Enhanced Dialogue Interface and similar replace the same files (https://www.nexusmods.com/starfield/mods/871).
- Options: no custom UI at first; optional wheel module; compatibility patches. (also: people-story Q12)
- Answer by: owner decision; list of known dialogue SWF mods. Who: owner, offline research.
- Blocks: Launcher, Release.
- Status: open.

**PS-03. What does the four-slot wheel lose in a list, and how do we keep it?**
- Why it matters: FO4 slot position carries meaning (positive, negative, sarcastic always in one slot).
- Options: order the list in FO4 slot order; tone tags like FDI ([Sarcastic], [Lie]); a wheel SWF. (also: people-story Q21; engine-mechanics.md D2)
- Answer by: player test of one converted scene. Who: owner decision after a PC probe.
- Blocks: People and story.
- Status: open.

**PS-04. How many FO4 player choice lines have no RNAM prompt?**
- Why it matters: an empty prompt shows as the full line or blank in Starfield.
- Options: fill from topic text; fall back to the full line.
- Answer by: offline scan of player topics in Fallout4.esm. Who: offline research.
- Blocks: People and story, New game.
- Status: open.

**PS-05. Which FO4 lines address or quote the voiced player so directly that they need a rewrite or a cut?**
- Why it matters: NPCs answer lines the player never audibly said. (also: people-story Q2 for the intro, Q25)
- Options: keep; subtitle note; cut; play FO4 player audio on the player (legal side: [release-community-legal.md](release-community-legal.md)). SS2 wrote its new dialogue around available base-game player lines, some spliced (**supported hypothesis**, Reddit comments, https://www.reddit.com/r/SimSettlements/comments/1cdhpbx/player_va_question/); that is same-game practice, not evidence for moving lines into Starfield. See PS-37.
- Answer by: offline sampling plus a list of player monologue INFOs (no choice). Who: offline research, owner decision.
- Blocks: New game, People and story.
- Status: open.

**PS-06. How is persuasion shown: FO4 Charisma odds on the INFO, or Starfield's minigame?**
- Why it matters: kept INCC needs our own SPECIAL for the odds formula.
- Options: script condition on our Charisma AV; perk entry point; colour tags in a custom SWF. (also: people-story Q20)
- Answer by: offline design, then owner decision. Who: owner.
- Blocks: People and story, Fallout systems.
- Status: open.

### Voice and lip sync (technical)

**PS-07. Do text-only lines use our own silent `.wem` placeholders, one shared silent id, or Starfield Silent Voice (SFSE)?**
- Why it matters: unvoiced lines flash past (https://www.nexusmods.com/starfield/mods/3153).
- Options: as in Possibilities. (also: people-story Q11; engine-mechanics.md V5, D6)
- Answer by: an INFO with a shared silent WEM id in game. Who: PC probe, owner decision on SFSE.
- Blocks: People and story, Launcher.
- Status: open.

**PS-08. Can the launcher run the FaceFX compile unattended, and how long per 1,000 lines?**
- Why it matters: the biggest build-time unknown for about 123k lines.
- Options: UI automation of the CK menu; a CK command-line switch (engine-mechanics.md); direct `ffxc.exe`; lips later. (also: people-story Q7; engine-mechanics.md L1, L2)
- Answer by: the Lip Sync Japanese recipe (https://www.nexusmods.com/starfield/mods/12842) timed on 1,000 FO4 WAVs, capturing `ffxc_00.log`; `ffxc.exe -h`. Who: PC probe.
- Blocks: Launcher, People and story.
- Status: open.

**PS-09. Can the compile be split and resumed, and is it deterministic?**
- Why it matters: a multi-hour step needs checkpoints and hash checks.
- Options: one batch per voice type; rerun skips existing `.ffxanim`. (also: people-story Q8, Q34)
- Answer by: rerun after a partial compile; compile the same 20 lines twice and compare hashes. Who: PC probe.
- Blocks: Launcher.
- Status: open. **Answered in part (2026-10-19, PC job 24, verified; research/engine-mechanics/dialogue.md):** LipGenerator.exe with the CK's Tools\FaceFX actors made `.ffxanim` files from a synthetic WAV in seconds, headless; job 25 compares the header with vanilla files. Open: time per 1,000 real lines, resume, and acceptance in game.

**PS-10. Which path and name rules does the launcher enforce before compiling?**
- Why it matters: no spaces in paths, plugin-name case (https://facefx.com/node/4600), numeric names; Steam often sits under "Program Files (x86)".
- Options: stage in a space-free work folder and copy results back; a junction. (also: people-story Q9)
- Answer by: one compile from a space-free staging folder. Who: PC probe.
- Blocks: Launcher.
- Status: open.

**PS-11. Does the compile need WAVs and WEMs both, or WAVs plus INFO text only?**
- Why it matters: WAVs for 123k lines are tens of GB.
- Options: the guide says both present (https://nexusmods.com/starfield/mods/12576). (also: people-story Q10)
- Answer by: compile with WAVs only. Who: PC probe.
- Blocks: Launcher.
- Status: open.

**PS-12. Which voice type settings make lips work on our FO4-named voice types?**
- Why it matters: "Voice Type must match body type"; wrong values give mute or lipless lines.
- Options: copy VTYP ANAM face archetype from a matching Starfield VTYP; leave empty. (also: people-story Q18)
- Answer by: one line with and without ANAM. Who: PC probe.
- Blocks: People and story.
- Status: open.

**PS-13. Do FO4 emotion keywords and values map to Starfield expressions, or do line "override anims" win?**
- Why it matters: Facial Animation Switcher notes override anims on vanilla lines (https://www.nexusmods.com/starfield/mods/6428).
- Options: map emotion to the INFO animation block; ignore for breadth. (also: people-story Q19)
- Answer by: one converted angry line in game. Who: PC probe.
- Blocks: People and story.
- Status: open.

**PS-14. How do we test lip sync offline, and is reading FO4 `.lip` curves worth it as a quality check?**
- Why it matters: `.ffxanim` is not a public format.
- Options: presence and count checks (one `.ffxanim` per `.wem`); one in-game screenshot sequence; `.lip` cross-check (low priority). (also: people-story Q33, Q35)
- Answer by: QA design. Who: offline research, PC probe.
- Blocks: People and story, Release.
- Status: open.

### Faces

**PS-15. Named-cast faces: which route, and does it lip sync?**
- Why it matters: Preston, Piper and Nick on template faces look like strangers; an ARMO head likely does not lip sync.
- Options: template; FO4 head as ARMO; hand-made faces via CharGenMenu then xEdit (https://www.nexusmods.com/starfield/mods/9326) shipped as record values, then a CK bake per NPC on the player's PC; our own FaceGeom `.nif` plus DDS writer; a Use Traits template (no bake, no unique face); an optimiser. (also: people-story Q15)
- Answer by: one ARMO head speaking a line; one hand-made Preston face baked with both CK bakes. Who: PC probe, owner decision.
- Blocks: People and story, Launcher.
- Status: narrowed (wave 2): every unique named face needs a per-NPC bake (CK GUI, crash-prone, inconsistent results) or our own writer; bakes are keyed by our plugin name, so they are made on the player's PC or shipped as generated data, never Bethesda assets [people-story W2-2].

**PS-16. Does a new named NPC_ need pre-baked facegen, or is it built at run time from its morph data?**
- Why it matters: if pre-baked, the CK must export facegen, another launcher CK step.
- Options: CK Bake FCT plus Bake Chargen Mesh Geometry (`[Debug]` `bAlwaysGenerateCpuGeometryExtraFields=1`, `bEnableEditorSaveGeometry=1` community fix); our own writer; run-time build. (also: people-story Q17)
- Evidence: per-NPC FaceGeom `.nif` and face textures keyed by FormID (**verified**, https://www.nexusmods.com/starfield/mods/5572); missing or stale bakes show bald heads or seams (**verified**, community reports); pre-baked is the rule for named NPCs (**supported hypothesis**). Exact runtime fallback and a non-GUI bake: **unresolved**.
- Answer by: a new NPC_ with custom morphs and no facegen files, in game; then a CK bake with no GUI (command line or automation). Who: PC probe.
- Blocks: People and story, Launcher.
- Status: narrowed (wave 2): pre-baked, per NPC, through two CK bakes; open part is a headless bake and the fallback [people-story W2-2].

**PS-17. Do generic NPCs (settlers, vendors) get run-time faces or pre-baked ones?**
- Why it matters: thousands of templated NPCs.
- Options: Starfield templates (Use Traits, no per-NPC bake); a Souls of Cities-style run-time pool (https://allmods.net/?p=225677). (also: people-story Q6)
- Answer by: a templated converted NPC with no facegen in game (the raider already renders, so likely yes). Who: PC probe.
- Blocks: All interiors, World, People and story.
- Status: narrowed (wave 2): Use Traits templated NPCs are the case without per-NPC bakes, consistent with run-time generic faces (**supported hypothesis**) [people-story W2-2].

**PS-18. Is a hand-made face record legal to ship in a no-assets GPL release?**
- Why it matters: dial values are numbers we author but they reference Starfield morph assets; baked `.nif` and DDS output is derived from Starfield assets.
- Options: ship values; generate them on the player's PC; bake on the player's PC only. (also: people-story Q16)
- Answer by: owner decision; see [release-community-legal.md](release-community-legal.md). Who: owner.
- Blocks: Release.
- Status: open (wave 2 adds: bakes must be made on the player's PC or as generated data, never shipped as Bethesda assets).

### Bodies and clothing

**PS-19. NPC outfits: Starfield stand-ins first, or converted FO4 outfits?**
- Why it matters: re-skinning is manual today (https://www.nexusmods.com/starfield/mods/17968).
- Options: stand-ins per outfit class; FO4 outfits with Morph Data NONE; full re-skin later. (also: people-story Q27)
- Answer by: owner decision after a PC probe of one converted outfit. Who: owner, PC probe.
- Blocks: People and story.
- Status: open.

**PS-20. Is the FO4 human skeleton a name-mappable subset of Starfield's?**
- Why it matters: decides whether clothing weights transfer by bone name.
- Options: name map; donor weight transfer. (also: people-story Q28)
- Answer by: read-only nif dump of both games' `skeleton.nif`. Who: offline if the files are reachable, else PC probe.
- Blocks: People and story, Fallout systems (power armor).
- Status: open.

**PS-21. Do FO4 NPC body weight values map to Starfield's Basis, Overweight, Thin, Strong shapes?**
- Why it matters: keeps body variety.
- Options: map FO4 weight values to the four shapes; one default body. (also: people-story Q29)
- Answer by: offline comparison of both NPC_ layouts. Who: offline research.
- Blocks: People and story.
- Status: open.

### Companions and affinity

**PS-22. Companion commands: dialogue only, or a Liga-style command layer?**
- Why it matters: FO4 command mode is unresolved on CE2; follow, stay, sneak, guard, relax are buildable (https://www.nexusmods.com/starfield/mods/12598?tab=docs).
- Options: dialogue only; own command layer. (also: people-story Q23)
- Answer by: owner decision; ask the Liga author how it is built. Who: owner, community contact.
- Blocks: People and story, Fallout systems.
- Status: open.

**PS-23. Do we use the Aflin and DJLegends voiced-follower template as the checklist for converted companions?**
- Why it matters: it lists dialogue categories and affinity events a Starfield follower needs (https://www.nexusmods.com/starfield/mods/17694).
- Options: adopt as checklist; derive our own from FO4 COM quests. (also: people-story Q24)
- Answer by: offline reading. Who: offline research, community contact.
- Blocks: People and story.
- Status: open.

**PS-24. Do FO4 affinity reactions and idolize perks need events Starfield's Papyrus lacks?**
- Why it matters: FO4 reactions fire from many player actions (crafting, lockpicking).
- Options: native events; SFSE events; polling scripts. (also: people-story Q30)
- Answer by: the native diff in papyrus-and-script-extenders.md, filtered to reaction triggers. Who: offline research.
- Blocks: People and story, Fallout systems.
- Status: open.

**PS-25. Do Starfield companions' location-keyed commentary systems fire in our world, and do we fence them out?**
- Why it matters: vanilla commentary is location-condition driven and buggy (https://www.nexusmods.com/starfield/mods/9285).
- Options: fence Starfield companions out of our world; allow with a patch. (also: people-story Q14)
- Answer by: PC check with one Starfield companion in our world. Who: owner decision, PC probe.
- Blocks: World, People and story.
- Status: open.

### Factions, karma and reputation

**PS-26. Karma (FO3), reputation (NV) and FO4 affinity: one alignment system or three?**
- Why it matters: karma gates FO3 companions and spawns hit squads (https://fallout.fandom.com/wiki/Karma_(Fallout_3)); reputation is per-faction REPU; FO4 uses affinity.
- Options: keep karma as a world-local AV, REPU as factions, plus affinity; or derive karma from affinity events. How TTW reconciles karma and reputation is unresolved. (also: multi-game-scope Q23)
- Answer by: owner decision. Who: owner.
- Blocks: Multi-game, Fallout systems.
- Status: open.

**PS-27. Do we name the core's factions, actor values and keywords game-neutrally now (for example `FO_Karma`)?**
- Why it matters: later games plug in without a migration; cheap now.
- Options: neutral names; FO4 names and migrate later. (also: multi-game-scope Q38)
- Answer by: owner decision. Who: owner.
- Blocks: People and story, Multi-game.
- Status: open.

**PS-28. How do faction relations and companions cross worlds (Brotherhood in DC and Boston; Dogmeat in both)?**
- Why it matters: TTW did not carry faction relations in 2014 (Steam thread 522728813700378577); cross-world followers are unresolved.
- Options: a shared faction with a lore state; separate factions per game. (also: multi-game-scope Q18, Q19)
- Answer by: owner decision, then a probe. Who: owner.
- Blocks: Multi-game.
- Status: open.

**PS-29. Does story state from one game affect another?**
- Why it matters: lore links (the Brotherhood) invite it; deep links multiply work.
- Options: none (sandboxed); light flags for dialogue variants; deep quest changes. (also: multi-game-scope Q20)
- Answer by: owner decision. Who: owner.
- Blocks: Multi-game.
- Status: open.

### Quests, radiant quests and settlers

**PS-30. Which FO4 radiant quests depend on Story Manager events Starfield cannot fire?**
- Why it matters: Minutemen settlement radiants are the mid-game backbone.
- Options: own SM branch; rewrite missing events as scripted triggers. (also: people-story Q13)
- Answer by: SMQN/SMEN scan against the dropped-event list in engine-mechanics notes (quests). Who: offline research.
- Blocks: People and story, Fallout systems (workshop).
- Status: open.

**PS-31. Do Start Game Enabled dialogue quests need SEQ files in Starfield?**
- Why it matters: could explain always-on dialogue that never appears; the launcher must build them if needed.
- Options: our own writer emits `Data\SEQ\<plugin>.seq` (flat array of 32-bit FormIDs of SGE quests, xEdit format); drive the CK (https://www.nexusmods.com/starfield/mods/13119); use Story Manager starts instead of SGE where dialogue is not always-on; none needed. (also: people-story Q37)
- Evidence: FO4/Skyrim need SEQ only for SGE quests (**verified**); the Starfield CK still makes them (**verified**); Starfield requires them (**supported hypothesis**); Starfield FormID encoding for small/medium masters in the file (**unresolved**).
- Answer by: one SGE dialogue quest with a greeting, from a save made before the plugin was added, with and without the `.seq`; our file compared byte for byte with the CK's. Who: PC probe plus one offline writer task.
- Blocks: People and story, Launcher, New game.
- Status: narrowed (wave 2): only SGE quests matter, format known, writer is cheap; open part is whether Starfield requires it [people-story W2-1]. The Starfield CK has a `-GenerateSEQ` switch (**verified**, PC job 18 string dump), so the CK can also make it.

### New voice and community

**PS-32. Is any new voice needed (bridging lines), and if so volunteers or synthetic?**
- Why it matters: lines that explain missing systems or replace player references.
- Options: none; volunteers (SS2 casting, https://www.castingcall.club/projects/fallout-sim-settlements; Skywind about 300 actors); synthetic (ElevenLabs in https://www.nexusmods.com/starfield/mods/9957; the SS2 team rejects AI voices, **supported hypothesis**, Reddit comments). Rights and platform rules: [release-community-legal.md](release-community-legal.md). (also: people-story Q26; precedents Q16)
- Wave 2: any new voice multiplies by language; only EN/FR/DE/ES/JA are voiced in both games (see PS-36).
- Answer by: owner decision. Who: owner.
- Blocks: People and story, Release.
- Status: open.

**PS-33. Which community authors do we contact first?**
- Why it matters: they hold practice we cannot read on a wiki (no public Starfield CK wiki, https://dev.starfieldwiki.net/wiki/Starfield_Mod:Main_Page; wave 2 re-check of the live https://starfieldwiki.net/wiki/Starfield_Mod:Main_Page: still no quest, dialogue, scene, follower, NPC or face pages, **verified**).
- Options: DJLegends (lips, voiced followers), Momidi (master-scale lips), Void SFG Bridge author (re-skin), Souls of Cities author (run-time faces), Liga author (commands). (also: people-story Q31)
- Answer by: owner outreach (outreach is the owner's job under AGENTS.md). Who: owner.
- Blocks: People and story.
- Status: open.

**PS-34. How do we tell players the Sole Survivor is silent and faces are approximations?**
- Why it matters: expectations; FO4 players already accept silent-player mods (https://www.nexusmods.com/fallout4/mods/83415, XDI).
- Options: release notes; an in-launcher note. (also: people-story Q32)
- Answer by: owner. Who: owner.
- Blocks: Release.
- Status: open.

### Cross-cutting

**PS-35. Is SFSE on by default for UI and silent-voice fixes in breadth phases, or is the base pipeline SFSE-free?**
- Why it matters: Silent Voice, Carbon UI, CharGenMenu and Souls of Cities need SFSE; Enhanced Dialogue Interface does not.
- Options: SFSE-free base with optional SFSE modules; SFSE required. (also: people-story Q36)
- Answer by: owner decision (SFSE is allowed; this is the default). Who: owner.
- Blocks: Launcher, People and story.
- Status: open.

**PS-36. Which languages does converted dialogue support, and what happens to voice and lips in each?**
- Why it matters: FO4 full audio is EN/FR/IT/DE/ES/JA; Starfield full audio is EN/FR/DE/ES/JA; the Starfield CK is English only (**verified**, Steam store API appids 377160, 1716740, 2722710). Italian FO4 voice has no Starfield voice set; Russian and Traditional Chinese FO4 players have no matching Starfield UI language.
- Options: English-only v1 (TTW precedent, installer needs both games in English, https://thebestoftimes.moddinglinked.com/faq.html); English-first with string tables passed through for EN/FR/DE/ES/JA (plus PL and PT-BR text-only in both); all FO4 languages. (also: people-story W2-4; distribution-community Q18, Q19)
- Evidence: the FaceFX compile reads `.wav` per voice folder, so non-English FO4 voice should lip the same way (Lip Sync Japanese precedent, https://www.nexusmods.com/starfield/mods/12842) (**supported hypothesis**, untested).
- Answer by: one test with a non-English FO4 STRINGS set and one non-English voice folder through the FaceFX compile; then owner decision. Who: PC probe, owner.
- Blocks: People and story, Launcher, Release.
- Status: narrowed (wave 2): language data verified; overlap EN/FR/DE/ES/JA is the end-to-end candidate set [people-story W2-4; distribution-community W2-4].

**PS-37. If a voiced-player option is ever offered, may it use only FO4's own player lines unchanged, or also spliced lines?**
- Why it matters: SS2 ships its own player-voice audio in FO4, reportedly built from base-game lines, some spliced (https://wiki.simsettlements2.com/getting-started/patch-notes, **verified**; splicing **supported hypothesis**). That is same-game practice; Capital Wasteland is the cross-game precedent. A spliced line is closer to a new derivative recording.
- Options: no voiced player (settled default); FO4 player lines unchanged, converted on the player's PC; spliced lines allowed. (also: precedents W2-4 new question 4)
- Answer by: owner decision plus a Bethesda question; legal side in [release-community-legal.md](release-community-legal.md). Who: owner.
- Blocks: People and story, Release.
- Status: open (new in wave 2) [precedents W2-4].

## Owner decisions in this area

Each line is a **recommendation**, not a decision.
- PS-01: show prompt plus full line (FDI style) if a custom SWF is accepted, else the full line; clarity beats brevity for a silent player.
- PS-02: no custom SWF in the first breadth release; add an optional module later, so we do not fight EDI users early.
- PS-03: keep FO4 slot order in the list and add tone tags; cheapest way to keep slot meaning.
- PS-05: keep lines and cut only those that break sense; rewriting is new content.
- PS-06: script condition on our Charisma AV with an odds tag in text; no SWF needed.
- PS-07: our own silent placeholders by default, Silent Voice as optional; keeps the base SFSE-free.
- PS-15: template faces for breadth, then hand-made faces for the named cast; the only route with a proven method that lips.
- PS-18: decide with the release-legal thread before any face values ship.
- PS-19: Starfield stand-ins first; batch re-skin is not available.
- PS-22: dialogue commands first, command layer later; lowest cost.
- PS-25: fence Starfield companions out of our world; matches the "own ecosystem" plan.
- PS-26, PS-27: neutral names now, alignment design deferred to the multi-game spike; naming is cheap, design is not.
- PS-28, PS-29: separate factions and sandboxed story until multi-game starts.
- PS-32: no new voice in the first releases; legal question first.
- PS-33: DJLegends and Momidi first; they cover the largest unknown (PS-08).
- PS-34: say it plainly in release notes and the launcher.
- PS-35: SFSE-free base, optional SFSE modules; widest audience, matches EDI precedent.
- PS-36: English-first v1, string tables passed through for EN/FR/DE/ES/JA after one non-English test; cheapest plan
  that does not exclude most players.
- PS-37: keep the silent player; if a voiced option comes, unchanged FO4 lines only, never spliced, pending the legal
  thread.

## Cheapest experiments

Nothing here runs now; it is a list.

1. **Offline record scan of Fallout4.esm** (repo Mutagen tooling): empty RNAM counts, player monologue INFOs in
   MQ101/MQ102, emotion keyword use, SMQN/SMEN events used by radiants, lines naming the player, COM quests and reaction
   triggers. Closes or narrows PS-04, PS-05, PS-13 (scope), PS-24, PS-30.
2. **Timed FaceFX run on 1,000 FO4 WAVs** from a space-free staging folder (PC, read-only on game files): time, then
   interrupt and rerun, then 20 lines twice for hashes, then a WAVs-only run, and `ffxc.exe -h` for usage text.
   Closes PS-08, PS-09, PS-10, PS-11, informs PS-14.
3. **One converted choice scene in game** with three list variants, one shared-silent-WEM text line, one angry line,
   one line with and without VTYP ANAM, and an SGE greeting quest loaded from an older save with and without our
   generated `.seq` (compared byte for byte with the CK's). Closes PS-01, PS-03, PS-07, PS-12, PS-13, PS-31.
4. **Face probe:** a new NPC_ with custom morphs and no facegen; the same NPC after both CK bakes (with the `[Debug]`
   INI fix); a templated Use Traits NPC; one FO4 head as ARMO speaking a line. Closes PS-15 (lip part), PS-16, PS-17.
5. **Read-only nif dump of both `skeleton.nif`** files, offline if reachable. Closes PS-20, informs PS-19 and PS-21.
6. **Offline reading** of the NPC template (starfield/17694) and Liga docs, plus the papyrus native diff. Closes PS-23,
   informs PS-22, PS-24.
7. **Non-English pass:** one FO4 STRINGS set and one non-English voice folder through the converter and FaceFX
   compile. Closes most of PS-36.

## Gaps (after wave 2)

- SS2's own account of how its player lines were made (only patch notes and Reddit comments read; team pages
  nexusmods fallout4/75137 and bethesda.net Monthly Modder Sirick still unread).
- Nexus pages not read (HTTP 429): starfield/14176, /6401, /6439.
- Whether the Starfield engine requires SEQ files, and its FormID encoding for small/medium masters in them.
- Whether face bakes can run without the CK GUI, and the engine's fallback when bakes are missing.
- FO4 and Starfield human bone name lists.
- Any published FO4-to-Starfield face morph or tint translator (none found).
- A Starfield CK command-line lip generation switch.
- How Liga of Followers implements commands (script or SFSE).
- TTW's reconciliation of karma and reputation; current TTW faction relations across worlds (2014 report only).
- NV reputation fame/infamy thresholds (no primary source read).

## Handed to phase files

| question | target |
|---|---|
| Which spouse and Vault-Tec rep lines break with a silent player in MQ101/MQ102 (people-story Q2; PS-05 covers the general case) | [newgame.md](newgame.md) |
| Can the mirror reuse Starfield chargen and CharGenMenu presets (`showlooksmenu player 1`, starfield/8015) (people-story Q3) | [newgame.md](newgame.md) |
| Does the Vault 111 start use any FO4 voice lines (precedents Q1; legal side in release-community-legal.md) | [newgame.md](newgame.md) |
| Do escort scenes keep dialogue alive across load doors (people-story Q4) | [door-animations.md](door-animations.md) |
| Which interior scenes rely on dropped camera paths and speaker/listener idles (SRAF/SNAM/LNAM counts) (people-story Q5) | [interiors.md](interiors.md) |
| Launcher staging, checkpoint and UI-mod detection parts of PS-02, PS-08 to PS-11 | [launcher.md](launcher.md) |
| Companion command mode and affinity plumbing as engine mechanics (PS-22, PS-24) | [engine-mechanics.md](engine-mechanics.md) |
| Voice policy, Codsworth voice script gating, `.lip` legal status, AI voice (precedents Q16 to Q18) | [release-community-legal.md](release-community-legal.md) (not a phase file; pointer only) |

## Sources

- https://www.nexusmods.com/starfield/mods/12842
- https://nexusmods.com/starfield/mods/12576
- https://facefx.com/node/4600
- https://www.nexusmods.com/starfield/mods/9957
- https://www.nexusmods.com/starfield/mods/12598?tab=docs
- https://www.nexusmods.com/starfield/mods/17694
- https://www.nexusmods.com/starfield/mods/9285
- https://www.nexusmods.com/starfield/mods/3153
- https://www.nexusmods.com/starfield/mods/871
- https://stepmodifications.org/wiki/Starfield:Enhanced_Dialogue_Interface
- https://stepmodifications.org/wiki/Concept:Starfield_ModGroup_16-Interface
- https://www.nexusmods.com/starfield/mods/17899
- https://www.nexusmods.com/starfield/mods/17900
- https://www.nexusmods.com/starfield/mods/7157
- https://mezha.ua/en/2023/11/27/new-mod-allows-you-to-turn-off-the-dialog-camera-in-starfield/
- https://www.nexusmods.com/fallout4/mods/1235
- https://nexusmods.com/fallout4/mods/27216
- https://www.nexusmods.com/fallout4/mods/83415
- https://www.nexusmods.com/starfield/mods/9326
- https://www.nexusmods.com/starfield/articles/1037
- https://www.nexusmods.com/starfield/mods/8015
- https://www.nexusmods.com/starfield/mods/17067
- https://allmods.net/?p=225677
- https://www.nexusmods.com/starfield/mods/6428
- https://allmods.net/starfield-mods/starfield-miscellaneous/organization-of-starfields-meshes-and-related-assets/
- https://www.nexusmods.com/starfield/mods/17968
- https://www.nexusmods.com/starfield/mods/16979
- https://www.nexusmods.com/starfield/mods/9234
- https://www.castingcall.club/projects/fallout-sim-settlements
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Main_Page
- https://wiki.beyondskyrim.org/wiki/Arcane_University:Seq_Guide (not read)
- https://forums.nexusmods.com/topic/7720963-do-i-still-need-to-make-a-seq-file/ (read in wave 2)
- https://kotaku.com/fallout-3-in-fallout-4-mod-canceled-after-team-talks-to-1823738281
- https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod
- https://www.pcgamer.com/au/capital-wasteland-the-fallout-3-remake-in-fallout-4-has-resumed-development
- https://www.gamerevolution.com/news/478241-fallout-4-capital-wasteland-mod-returns
- https://www.gamerevolution.com/news/433019-fan-project-fallout-4-new-vegas-shows-progress
- https://wccftech.com/skywind-2026-milestone-quests-written-no-release-date/amp/
- https://en.wikipedia.org/wiki/Skyblivion
- https://fallout.fandom.com/wiki/Karma_(Fallout_3)
- https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbDefinitionsFNV.pas
- https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbDefinitionsFO3.pas
- https://thebestoftimes.moddinglinked.com/faq.html
- https://fallout.wiki/wiki/Mod:Tale_of_Two_Wastelands
- https://steamcommunity.com/app/22380/discussions/0/522728813700378577
- Wave 2: https://www.reddit.com/r/CreationKit/comments/1mg6kj1/created_npc_doesnt_spawn_when_loading_prior_saves/
- Wave 2: https://www.nexusmods.com/starfield/mods/13119
- Wave 2: https://github.com/TES5Edit/TES5Edit (branch dev-4.1.6: xEdit/xeMainForm.pas, xEdit/xeInit.pas, Core/wbInterface.pas)
- Wave 2: https://www.nexusmods.com/starfield/mods/5572 , https://www.nexusmods.com/starfield/mods/7834/?tab=posts (snippet)
- Wave 2: https://creations.bethesda.net/it/starfield/details/41e41fc3-438d-4608-8ed1-a7cacb74c843/Female_Dani_Garcia (snippet only)
- Wave 2: https://forums.nexusmods.com/topic/13521838-ck-bugquestion-%E2%80%9Cbake-chargen-mesh-geometry%E2%80%9D-always-crashes-%E2%80%94-is-this-broken-for-everyone/
- Wave 2: https://www.reddit.com/r/starfieldmods/comments/1dp6yv8/npc_edits_having_issues/
- Wave 2: https://steamcommunity.com/sharedfiles/filedetails/?id=3287508493
- Wave 2: https://www.reddit.com/r/CreationKit/comments/1lp64l5/creation_kit_not_generating_facegen_files/
- Wave 2: https://forums.nexusmods.com/topic/13526765-generating-facegen-data/
- Wave 2: https://starfieldwiki.net/wiki/Starfield_Mod:Main_Page , https://starfieldwiki.net/wiki/Starfield_Mod:Starfield_Creation_Kit
- Wave 2: https://store.steampowered.com/api/appdetails?appids=377160 , https://store.steampowered.com/api/appdetails?appids=1716740 ,
  https://store.steampowered.com/api/appdetails?appids=2722710
- Wave 2: https://wiki.simsettlements2.com/getting-started/patch-notes
- Wave 2: https://www.reddit.com/r/SimSettlements/comments/1cdhpbx/player_va_question/
- Wave 2: https://simsettlements.com/site/index.php?threads/changing-the-players-character-voice.26659/
- Not readable in wave 1: https://www.nexusmods.com/fallout4/mods/75137 , https://bethesda.net/en-EU/news/monthly-modder-sirick ,
  https://www.nexusmods.com/starfield/mods/14176 , https://www.nexusmods.com/starfield/mods/6401 , https://www.nexusmods.com/starfield/mods/6439
- Project files: scripts/actors/codsworth_voice.py; next-phase/npcs-ai-factions-dialogue-quests.md;
  next-phase/voice-lipsync-companions.md; framework/engine-mechanics.md
