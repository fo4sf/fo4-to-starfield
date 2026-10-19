# Asset pipeline: converting every Fallout 4 asset class on the player's PC

Part of the [next-phase framework](README.md). Wave 1, 2026-10-19. Sources: findings/asset-conversion.md, findings/starfield-toolchain.md (asset parts), findings/people-story.md (faces, lip sync, clothing), findings/versions-performance.md (disk, archive limits).

## In short

- Static assets are solved in our own code and verified in game: meshes (S1 writer), materials (S3 `.mat` cloner) and collision (compressed-mesh transplant). Outside tools are oracles, not dependencies.
- Voice and lip sync have a proven route: loose `.wem` for playback plus the Creation Kit's FaceFX compiler for `.ffxanim`. A community mod ran it over whole masters. Unattended running, time per 1,000 lines and resume are not proven.
- Sound effects, behaviour graphs (`.agx`), facegen and skinned clothing are the open research areas. LOD and precombines have no known tool path.
- Scale is unmeasured: no whole-game build time, no peak disk figure, no FO4 texture count. Engine ceilings (256 BA2s, about 4 GiB per archive) are known.
- Most uncertain: whether CK-only steps (FaceFX, maybe LOD) can run with no human, and whether `.wem` encoding needs Wwise on the player's PC.
- The 3 decisions that unlock the most: (1) which external tools the player must install (CK settled; Wwise open), AP-50; (2) animation route: Starfield graphs with retargeted clips, or SFSE glTF players, AP-20; (3) the people route for breadth: Starfield stand-in faces and outfits first, AP-31 and AP-36.

## What is settled

Owner decisions (findings/BRIEF.md, also every findings file):

| decision | consequence for assets |
|---|---|
| No game assets ship; the player owns both games and conversion runs on their PC | every asset class needs a local, repeatable converter or a local Bethesda tool |
| The free Starfield Creation Kit MAY be required | CK FaceFX lip sync and CK navmesh switches are allowed dependencies |
| SFSE MAY be required | SFSE glTF animation players (NAF, SAF, OSF) and Silent Voice are allowed options |
| Starfield's own animations first, FO4 clips later | no animation conversion blocks the early phases |
| Silent player by default | no player voice lines to convert |
| Breadth before polish | stand-in faces, outfits and sounds are acceptable first steps |
| GitHub release first, then Nexus; GPL-3 notice for Mutagen | GPL-3 linking (HavokLib) is probably compatible; needs a licence table (AP-51) |

Verified facts that close or bound questions:

- Our mesh writer is the reference: byte-for-byte `.mesh` on 3,000 of 3,000 samples, meshlets 4,000 of 4,000, `BSGeometry` 20,224 of 20,224 (**verified**, repo S1; asset-conversion §1).
- `.mesh` triangles are u16 x3, so one `.mesh` addresses at most 65,536 vertices (**verified**, repo FORMAT-GAP/S1; Geometry Bridge advises the same limit, [Nexus 4360](https://nexusmods.com/starfield/mods/4360)).
- FO4 hk_2014 collision is decoded and transplanted into Starfield tagfiles; single dynamic bodies work; constraints do not (**verified**, repo `meshcollision.py`, `sfbodies.py`; asset-conversion §2).
- The project writes door `.rig` and `.af` with CALUMI (LGPL-3, alpha, compression "planned") (**verified**, repo decisions.md; [CALUMI](https://github.com/Calaverah/CALUMI.Animation)).
- Starfield voice is loose files at `Data\Sound\Voice\<Plugin>.esm\<VoiceType>\<id>`; each line needs `.wav` (for lip generation) and `.wem` (for playback); no spaces; voice type must match body type (**verified**, [Audio File Conversion](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion), [Nexus 12576](https://nexusmods.com/starfield/mods/12576)).
- Lip sync is produced only by the CK's embedded FaceFX (Audio > Run FaceFX Compiler; log `ffxc_00.log`) (**verified**, same sources and [facefx.com/node/4600](https://facefx.com/node/4600)). It has been run over all of `Starfield.esm` and `ShatteredSpace.esm` (**verified**, Lip Sync Japanese, [Nexus 12842](https://www.nexusmods.com/starfield/mods/12842)).
- Starfield's Wwise version is 2021.1.14.8108; the CK installs `Starfield.wproj`; "Convert All Audio Files" writes `.wem` to `.cache/<platform>` (**verified**, [Xbox porting guide](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox), [Nexus 12561](https://www.nexusmods.com/starfield/mods/12561)). Use Vorbis; PCM is about 10x bigger (**verified** article, comments **supported hypothesis**, [Nexus article 173](https://www.nexusmods.com/starfield/articles/173)).
- Named Starfield NPCs have pre-baked facegen meshes and textures (**verified**, Enhanced Hadrian, [Nexus 9326](https://www.nexusmods.com/starfield/mods/9326)).
- Unvoiced lines flash past too fast to read in Starfield (**verified**, Starfield Silent Voice, [Nexus 3153](https://www.nexusmods.com/starfield/mods/3153)).
- BA2: 4,095 MB per archive, split large sets; v2 GNRL/DX10 and v3 LZ4 textures; Archive2 ships with the CK (**verified**, [ejams1 guide](https://github.com/ejams1/starfield-modding-guide), repo S9). At most 256 active archives; an SFSE "BA2 Limit Fix" raises it (**verified**, [Nexus 17936](https://www.nexusmods.com/starfield/mods/17936)).
- Starfield patch 1.11.36 renamed about 323,099 vanilla mesh paths (**verified**, [Nexus 9234](https://www.nexusmods.com/starfield/mods/9234)). Lesson: resolve vanilla paths at build time, never hard-code them.
- Hardware floor: 16 GB RAM, GTX 1070 Ti class, 125 GB on an SSD (required) (**verified**, [system requirements](https://starfieldwiki.net/wiki/Starfield:System_Requirements)).

Scale numbers we have (all **verified** from repo files cited in the findings, unless marked):

| item | count or size | source |
|---|---|---|
| placed exterior objects / models, current builds | 648,358 / 4,346 | asset-conversion §1 (ROADMAP, JOURNAL) |
| 64-cell core | 649,596 references, 11,769 models, about 8.5 GiB at full resolution | versions-performance (decisions 2026-10-12) |
| build time, 15 cells / 4,014 models | 311 to 373 s | versions-performance (optimization.md) |
| FO4 skinned NIFs | 3,588 NIFs, 16,350 skinned shapes (15,325 `BSSubIndexTriShape`) | asset-conversion §1 (research-log 2026-10-10) |
| FO4 precombined NIFs | 95,856 | asset-conversion §8 |
| FO4 voice `.fuz` | 122,857 | asset-conversion §6 (FORMAT-GAP) |
| FO4 `.xwm` audio | 7,380 | asset-conversion §5 |
| FO4 SNDR records | 5,476 | asset-conversion §5 |
| Starfield `.ffxanim` / `.wem` (vanilla) | about 278k / about 26k | asset-conversion §3, §5 |
| FO4 textures (count, size) | not measured (**unresolved**) | asset-conversion §4 |
| FO4 install size with DLC | about 30+ GB (**unresolved**) | versions-performance risk 7 |

## Possibilities

### Meshes and LOD slots

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| Own writer (S1), outside tools as oracles | full control, no licence ties | we maintain format changes per patch | S1 spike | **verified** |
| Split shapes over 65,536 vertices across `BSGeometry` blocks | no failed meshes | unknown how many FO4 shapes need it | none found | **unresolved** |
| Fill `BSGeometry` LOD slots 1 to 3 with meshoptimizer output | distance and shadow LOD | build time; unknown benefit | NifSkope meshoptimizer spell ([releases](https://github.com/fo76utils/nifskope/releases)) | **supported hypothesis** |
| Leave LOD slots empty | zero cost | possible frame-time cost at 648k+ refs | current builds | **verified** (current state) |

### Collision

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| FO4 bodies transplanted (current) | real FO4 shapes | constraints not done | repo `meshcollision.py` | **verified** |
| Decode constraint blob with Starfield Blender Extension code as reference | multi-body systems | no licence named on page | [Nexus 16979](https://www.nexusmods.com/starfield/mods/16979) | **supported hypothesis** |
| Bethesda ArtTools in 3ds Max 2021 | official path | paid software, not a launcher dependency | [collision guide](https://starfieldwiki.net/wiki/Starfield_Mod:Adding_Collision_with_3ds_Max_2021) | **verified** path, **supported hypothesis** it is unsuitable |

### Skinned meshes, bodies and clothing

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| Starfield stand-in outfits per FO4 outfit class | breadth now | wrong look | none needed | **supported hypothesis** |
| Our own Starfield skin writer, bone-name map, checked against community tools | batch, consistent with S1 | skin writer not done (ACTOR-MILESTONE step 2); bone map unknown | Void SFG Bridge, Starfield Blender Extension | **unresolved** |
| Donor weight transfer ("Morph Genesis" style) | fits FO4 outfits to Starfield bodies | interactive, not batch; Void SFG Bridge forbids conversion to other games | [Nexus 17968](https://www.nexusmods.com/starfield/mods/17968) | **verified** tool, **unresolved** for batch |
| Morph Data NONE on converted outfits | skip body-shape morphs | clips on non-default bodies | Void SFG Bridge page | **verified** |

### Faces and facegen

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| (a) Starfield template faces | breadth now | named cast look wrong | ROADMAP B2 | **verified** plan |
| (b) FO4 head as an ARMO | FO4 look | likely no lip sync (FaceFX drives the race face rig) | none | **supported hypothesis** |
| (c) Hand-made faces per named NPC (CharGenMenu then xEdit), shipped as record values | lips work, no game assets shipped | hand work per NPC; legal check | Enhanced Hadrian ([Nexus 9326](https://www.nexusmods.com/starfield/mods/9326)) | **verified** method |
| (d) Optimiser fitting Starfield dials to FO4 head renders | automatic | research project | none | **unresolved** |
| Run-time face pool for generic NPCs (SFSE) | variety for crowds | SFSE dependency | Souls of Cities ([allmods](https://allmods.net/?p=225677)) | **verified** tool |
| Convert FO4 facegen `.nif`+`.tri` to `BSFaceGenNiNode` + morph `.dat` | FO4 faces as assets | only reader/writer reference is Geometry Bridge | [Nexus 4360](https://nexusmods.com/starfield/mods/4360) | **unresolved** |

### Animation and behaviour

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| Starfield animations only (settled first step) | no conversion | FO4 feel lost | owner decision | **verified** |
| Decode FO4 `.hkx` with HavokLib, write `.af` with CALUMI, use in vanilla Starfield graphs | native playback | `.agx` opaque; CALUMI has no compression; HavokLib GPL-3 | door clips (repo) | **supported hypothesis** |
| Play FO4 clips through SFSE glTF players (NAF GPL-3, SAF 6.0, OSF 1.4.0) | idles, furniture, scenes without `.agx` | SFSE dependency; AI-package fit unknown | [Nexus 7360](https://www.nexusmods.com/starfield/mods/7360), [16124](https://www.nexusmods.com/starfield/mods/16124), [17457](https://www.nexusmods.com/starfield/mods/17457) | **verified** capabilities |
| Port whole FO4 behaviour graphs | full fidelity | no `.agx` spec | none | not realistic (**unresolved** spec) |
| New creature `.rig` + `.af` + cloned Starfield creature graph | FO4 creatures | foreign rig acceptance unknown | Sebbo retargeting on FO4 ([Nexus 69177](https://nexusmods.com/fallout4/mods/69177)) | **unresolved** |

### Textures and materials

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| S3 path: BC1/BC5/BC4 re-encode with texconv, loose `.mat` | in game today | likely slowest bulk step; count unknown | S3 | **verified** |
| Texture caps per VRAM tier (today 1024 colour / 512 normal) | fits 8 GB cards | quality loss | decisions 2026-10-12 | **supported hypothesis** |
| Compare our `.mat` with compiled `materialsbeta.cdb` via fo76utils NifSkope | material oracle | GUI tool | [releases](https://github.com/fo76utils/nifskope/releases) | **supported hypothesis** |

### Sound and music

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| Decode `.xwm` (ffmpeg) then Wwise 2021.1.14.8108 encodes Vorbis `.wem` on the player's PC | correct format | Wwise licence, install, login unknown; headless unknown | Nexus 12561, article 173 | **supported hypothesis** |
| Open-source `.wem` encoder | no Wwise | none known | none | **unresolved** |
| Map FO4 SNDR to nearest vanilla Starfield WWED event | no new events | wrong sounds in places | none | **supported hypothesis** |
| Author new WWED events and banks | real FO4 sounds | no public guide; one failed attempt | article 641 comments | **unresolved** |
| Replace vanilla `.wem` by id | easy | changes Starfield's own sounds | [article 641](https://www.nexusmods.com/starfield/articles/641) | **verified**, unacceptable scope |
| Radio music as loose `.wem` like voice | no banks | untested | article 535 (not read) | **unresolved** |

### Voice and lip sync

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| `.fuz` to xWMA to `.wav`, Wwise `.wem`, CK FaceFX `.ffxanim` | full voiced lips | multi-hour CK step; automation unknown | Lip Sync Japanese | **verified** at master scale (community) |
| Audio first, lips later | audio sets line length | closed mouths | next-phase route (c) | **supported hypothesis** |
| Silent placeholder `.wem` per text-only line, or one shared id | readable text-only lines | disk, or untested record trick | FO4 and Skyrim practice | **supported hypothesis** |
| Starfield Silent Voice (SFSE) | readable unvoiced lines | SFSE dependency | [Nexus 3153](https://www.nexusmods.com/starfield/mods/3153) | **verified** |
| Convert FO4 `.lip` to `.ffxanim` | skip FaceFX | formats differ; no converter | none | **supported hypothesis** it is not possible |

### LOD and precombines

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| CK object LOD generation | official output | no documented batch; trial planned | docs/terrain/object-lod.md | **unresolved** |
| Convert FO4 `.bto` as stand-in `_lod_N` NIFs | whole map at once | `lodruntimedb.bgsdb` listing unknown | none | **unresolved** |
| Third-party generator (xLODGen-style) | batch | Starfield support unknown | none found | **unresolved** |
| Merge static geometry per cell ourselves | fewer draw calls | new writer work | FO4 precombines | **supported hypothesis** |
| Place references one by one (current) | simple | draw-call cost unmeasured | Phase A walk, no crash | **verified** current state |

### Packaging, input versions and budgets

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| One ESM + 1 to 3 archives, medium masters for DLC areas | stays under 256 BA2s | archives over 4 GiB unresolved | versions-performance Q17 | **supported hypothesis** |
| Archive2 from the CK install | official packer | needs CK (allowed) | repo S9 | **verified** |
| Open packer (bsa-rs) | no CK for packing | maintenance | toolchain Q11 | **unresolved** |
| Detect FO4 data version by `.esm` hashes and BA2 headers | right converter per player | per-version fixtures | TTW model (**supported hypothesis**) | **supported hypothesis** |

## Questions

### Meshes

**AP-01. Do any FO4 shapes exceed 65,536 vertices, and does the writer split or refuse them?**
- Why it matters: `.mesh` indices are u16; an oversize shape fails silently or loudly at full scale.
- Options: split across `BSGeometry` blocks; decimate; refuse and report (asset-conversion §1).
- Answer by: scan max vertex count per FO4 shape with `nif.py` over all archives; offline research.
- Blocks: All interiors, World.
- Status: open. (also: asset-conversion Q6)

**AP-02. Should the converter fill `BSGeometry` LOD slots 1 to 3?**
- Why it matters: Starfield may use them for distance and shadow LOD at 648k+ references.
- Options: meshoptimizer (as NifSkope's spell); leave empty.
- Answer by: share of vanilla meshes with slots filled (offline); frame-time A/B in game (PC probe).
- Blocks: World, All interiors.
- Status: open. (also: asset-conversion Q8)

**AP-03. How do we keep converted assets valid across Starfield patches that rename vanilla paths or change NIF versions?**
- Why it matters: 1.11.36 renamed about 323k mesh paths ([Nexus 9234](https://www.nexusmods.com/starfield/mods/9234)); NIF BS versions 173 to 175 seen; NifSkope needed a 1.15.214 update.
- Options: resolve vanilla paths at build time from the player's archives; a hash list of vanilla paths we reference, re-checked per patch.
- Answer by: a patch-day check script (offline tooling).
- Blocks: Release, Launcher.
- Status: open. (also: starfield-toolchain Q4, Q31; asset-conversion risk 8)

### Collision

**AP-04. Can the vanilla Starfield constraint blob be decoded so multi-body FO4 systems keep their joints?**
- Why it matters: multi-body systems are merged into one rigid body today.
- Options: read Starfield Blender Extension code (claims rigidbody and constraint controls, [Nexus 16979](https://www.nexusmods.com/starfield/mods/16979)); own reverse engineering.
- Answer by: offline reading of that code, then one round trip; offline research.
- Blocks: All interiors, Fallout systems.
- Status: open.

**AP-05. Run a full-archive "convert everything, count failures" job for each asset class before more feature work?**
- Why it matters: breadth before polish needs real failure classes, not guesses.
- Options: per class (meshes, collision, materials, textures, audio, clips) with a failure report, as CAO does (**supported hypothesis** precedent).
- Answer by: one build run with a report; offline (Claude build).
- Blocks: All interiors, World, Launcher.
- Status: open. (also: asset-conversion Q34; interiors-specific MSTT collision handed off)

### Skinned meshes, bodies and clothing

**AP-06. Is the FO4 skeleton's bone set mappable by name onto Starfield's human skeleton?**
- Why it matters: decides whether outfit weights transfer by name or need donor weight transfer.
- Options: name map; donor transfer (Void SFG Bridge "Morph Genesis").
- Answer by: read-only nif dump of both `skeleton.nif`; offline if files are reachable, else PC probe.
- Blocks: People and story, Fallout systems.
- Status: open. (also: people-story Q28; asset-conversion Q23)

**AP-07. Write Starfield skinned geometry ourselves, or use community Blender tools as oracles only?**
- Why it matters: 16,350 skinned FO4 shapes; the published tools are interactive, not batch.
- Options: own writer (skin blocks, bone indices in `.mesh`, segment replacement) checked against Starfield Blender Extension or Void SFG Bridge output. Void SFG Bridge forbids conversion to other games: viewer or oracle at most.
- Answer by: write one skinned outfit, compare with an oracle export, view in game; offline plus PC probe; owner on permissions.
- Blocks: People and story, Fallout systems.
- Status: open. (also: asset-conversion Q23)

**AP-08. Do FO4 body weight values map to Starfield's apparel morphs (Basis, Overweight, Thin, Strong)?**
- Why it matters: keeps NPC body variety and avoids clipping.
- Options: map FO4 weight values to the four morphs; Morph Data NONE (clips on non-default bodies).
- Answer by: offline research on both NPC_ layouts and `morph.dat` ([allmods mesh guide](https://allmods.net/starfield-mods/starfield-miscellaneous/organization-of-starfields-meshes-and-related-assets/)).
- Blocks: People and story.
- Status: open. (also: people-story Q29)

### Faces and facegen

**AP-09. Does a new Starfield NPC need pre-baked facegen, or will the engine build it at run time from NPC_ morph data?**
- Why it matters: pre-baked facegen would add a CK export step to the launcher.
- Options: pre-baked (named vanilla NPCs have it); run-time (vanilla crowds and Souls of Cities suggest it works).
- Answer by: a new NPC_ with custom morphs and no facegen files, in game; PC probe.
- Blocks: People and story.
- Status: open (partly answered: named vanilla NPCs ship pre-baked facegen, **verified**, [Nexus 9326](https://www.nexusmods.com/starfield/mods/9326); run-time faces for crowds are a **supported hypothesis**). (also: asset-conversion Q22; people-story Q6, Q17)

**AP-10. Which named-cast face route, and does it lip sync?**
- Why it matters: Preston, Piper and Nick looking like strangers is the most visible flaw.
- Options: (a) template; (b) FO4 head as ARMO, likely no lips; (c) hand-made record values (Enhanced Hadrian method); (d) dial-fitting optimiser.
- Answer by: one ARMO head speaking a line; one hand-made Preston face; PC probe, then owner decision.
- Blocks: People and story.
- Status: open. (also: people-story Q15)

**AP-11. Can FO4 facegen `.nif` + `.tri` be converted to `BSFaceGenNiNode` + morph `.dat` at all?**
- Why it matters: the only fully automatic route to FO4 faces.
- Options: read Geometry Bridge's `.dat` code as reference (MIT); no other reader known.
- Answer by: offline research, then one test face; offline plus PC probe.
- Blocks: People and story.
- Status: open.

### Animation and behaviour

**AP-20. For FO4 idles, furniture, scenes and creature motion: retarget into Starfield graphs as `.af`, or play glTF through an SFSE player?**
- Why it matters: `.agx` is opaque; the choice sets the whole animation track.
- Options: (a) HavokLib decode, CALUMI `.af`, vanilla graph via animation text data; (b) NAF, SAF or OSF with glTF.
- Answer by: decode one FO4 idle, play it both ways on a converted NPC; offline plus PC probe.
- Blocks: People and story, Fallout systems.
- Status: open. (also: asset-conversion Q24)

**AP-21. Can new clips be added to vanilla `.agx` graphs without editing the graph?**
- Why it matters: route (a) of AP-20 depends on it.
- Options: animation text data or subgraph equivalent; none.
- Answer by: community Discords, then one PC probe.
- Blocks: People and story, Door animations (later FO4 clips).
- Status: open. (also: asset-conversion Q25)

**AP-22. Do uncompressed CALUMI `.af` files bloat disk and memory at full-game scale, and when does CALUMI add compression?**
- Why it matters: CALUMI lists compression and full decoding as "planned" ([CALUMI](https://github.com/Calaverah/CALUMI.Animation)).
- Options: wait; contribute; ask the author (AP-53).
- Answer by: convert every FO4 door clip and compare sizes with vanilla `.af`; offline.
- Blocks: Door animations, People and story.
- Status: open. (also: asset-conversion Q4, risk 4)

**AP-23. Can FO4 creatures with no Starfield rig (deathclaw, mirelurk, super mutant, Mr. Handy) run on a new `.rig` + `.af` + cloned creature graph?**
- Why it matters: creature-heavy quests need them.
- Options: new rig on a cloned graph; nearest Starfield creature as stand-in.
- Answer by: CALUMI deathclaw `.rig` driven by one retargeted walk; PC probe.
- Blocks: Fallout systems, People and story.
- Status: open. (also: asset-conversion Q26)

### Textures and materials

**AP-24. How many FO4 textures are there, how large, and how long does re-encoding take?**
- Why it matters: likely the slowest bulk step on the player's PC.
- Options: count from archives offline; time a sample with texconv.
- Answer by: archive listing count plus a timed 1,000-texture batch; offline then PC probe.
- Blocks: Launcher, World.
- Status: open.

**AP-25. What texture caps does the default build use per VRAM tier?**
- Why it matters: today's caps (1024 colour, 512 normal) were set for archive size, not VRAM.
- Options: three presets keyed to detected VRAM.
- Answer by: VRAM use at each cap on an 8 GB card; PC probe on lower-end hardware (community).
- Blocks: Launcher, Release.
- Status: open. (also: versions-performance Q20)

**AP-26. Can we use fo76utils NifSkope's compiled-material reader as an oracle for our loose `.mat`?**
- Why it matters: no offline check today against vanilla compiled materials.
- Answer by: extract a vanilla material via the fixed Extract Resource Files spell and diff with our clone; offline.
- Blocks: All interiors (quality checks).
- Status: open.

### Sound and music

**AP-30. Is Wwise 2021.1.14.8108 authoring on the player's PC acceptable (licence, download, login), and can it convert headless?**
- Why it matters: it is the only verified `.wem` encoder; 122,857 voice files plus SFX depend on it.
- Options: Wwise on player PC; an open encoder (none known); another playback path.
- Answer by: Audiokinetic licence terms (offline research); WwiseConsole on the CK's `Starfield.wproj` without GUI (PC probe).
- Blocks: People and story, Launcher, Fallout systems (radio).
- Status: open. (also: asset-conversion Q12; starfield-toolchain Q19)

**AP-31. Can new non-voice sounds be added (new WWED events and banks), or must FO4 SFX map to existing Starfield events?**
- Why it matters: 5,476 FO4 SNDR records; replacing vanilla ids changes Starfield's own sounds.
- Options: author new events (undocumented); nearest-event map from `soundbanksinfo.json`; stand-in Starfield sounds for breadth.
- Answer by: one new event in a test bank (PC probe); a SNDR to WWED mapping table (offline).
- Blocks: Door animations, All interiors, World, Fallout systems.
- Status: open. (also: asset-conversion Q5, Q19)

**AP-32. Does `.xwm` decode cleanly with an open decoder (for example ffmpeg) for all 7,380 FO4 files?**
- Why it matters: every audio path starts here.
- Answer by: decode all, count failures, round-trip check with vgmstream on resulting `.wem`; offline.
- Blocks: People and story, World.
- Status: open.

**AP-33. Can FO4 radio music and DJ lines play as loose `.wem` like voice, or do they need banks and events?**
- Why it matters: radio is a core Fallout system.
- Answer by: Nexus article 535 (not read); one loose music `.wem` test; offline plus PC probe.
- Blocks: Fallout systems.
- Status: open. (also: asset-conversion Q29)

### Voice and lip sync

**AP-40. Can the CK FaceFX compile run unattended, and how long per 1,000 lines?**
- Why it matters: the biggest build-time unknown; 122,857 lines on each player's PC.
- Options: a CK command-line switch (unknown; navmesh switches exist in CreationKit.exe strings); GUI automation; direct `ffxc.exe` on the CK-written `.animset`; ship lips later.
- Answer by: strings scan of CreationKit.exe for FaceFX switches (PC read-only); the Lip Sync Japanese recipe timed on 1,000 FO4 WAVs with `ffxc_00.log` captured (PC probe).
- Blocks: People and story, Launcher.
- Status: open. (also: asset-conversion Q11, Q20; starfield-toolchain Q18; people-story Q7)

**AP-41. Can the compile be split and resumed, and is its output deterministic?**
- Why it matters: a multi-hour step needs checkpoints; the launcher's determinism gate needs hashes.
- Options: batch per voice type or plugin; rerun skips existing `.ffxanim`.
- Answer by: rerun on a half-done folder; compile 20 lines twice and compare hashes; PC probe.
- Blocks: Launcher.
- Status: open. (also: people-story Q8, Q34)

**AP-42. Does the compile need both WAV and WEM, or only WAV plus text?**
- Why it matters: WAVs for 123k lines are tens of GB of disk.
- Answer by: compile with WAVs only; PC probe.
- Blocks: Launcher (disk budget).
- Status: open. (also: people-story Q10)

**AP-43. Which path and name rules must the launcher enforce before a compile?**
- Why it matters: no spaces in paths, plugin-name case sensitivity, numeric file names; Steam often sits under "Program Files (x86)".
- Options: stage WAVs in a space-free work folder and copy results back; a junction.
- Answer by: one compile from a space-free staging folder; PC probe.
- Blocks: Launcher.
- Status: open. (also: people-story Q9)

**AP-44. Which voice type settings make lips work for FO4 voice types on Starfield bodies?**
- Why it matters: voice type must match body type, or lines are mute or lipless.
- Options: copy VTYP ANAM face archetype from a matching Starfield VTYP; leave empty.
- Answer by: one line with and without ANAM set; PC probe. Map FO4 voice-type paths offline.
- Blocks: People and story.
- Status: open. (also: asset-conversion Q21; starfield-toolchain Q20; people-story Q18)

**AP-45. For lines with no FO4 audio or a text-first stage: our own silent `.wem` placeholders, or Starfield Silent Voice (SFSE)?**
- Why it matters: unvoiced lines flash past unreadably.
- Options: one silent `.wem` per line; one shared id via the response's WEM field (untested); the SFSE plugin.
- Answer by: an INFO with a shared silent WEM id in game; PC probe, then owner on SFSE default.
- Blocks: People and story, New game.
- Status: open. (also: people-story Q11)

**AP-46. How do we check lip sync offline?**
- Why it matters: `.ffxanim` is not a public format.
- Options: presence and count checks (one `.ffxanim` per `.wem`); in-game screenshot sequence; low priority: read FO4 `.lip` curves as a cross-check.
- Answer by: QA design, one PC probe.
- Blocks: Launcher, Release.
- Status: open. (also: people-story Q33, Q35; asset-conversion Q33)

### LOD and precombines

**AP-47. Where does Commonwealth object and terrain LOD come from: the CK, a third-party generator, converted FO4 `.bto`, or our own writer?**
- Why it matters: nothing draws beyond loaded cells today; Starfield uses `.btd`/`.lod`, with no public `.btd` writer.
- Options: CK trial (object-lod.md); FO4 `.bto` as `_lod_N` stand-ins; xLODGen-style tool (unknown); own writer.
- Answer by: CK strings scan for LOD switches and the planned CK trial (PC probe); read one `.bto` against a vanilla `_lod_0.nif` (offline).
- Blocks: World.
- Status: open. (also: asset-conversion Q16, Q17; starfield-toolchain Q15)

**AP-48. Does Starfield have a precombine or previs step, and is per-reference placement fast enough without one?**
- Why it matters: FO4 relies on 95,856 precombined NIFs plus previs; we place about 650k references one by one.
- Options: find an engine feature; merge static geometry per cell ourselves; accept the cost; reduce clutter.
- Answer by: scan Starfield.esm for precombine-like data (offline); frame time and draw calls in the densest converted interior and on a core64 walking route (PC probe).
- Blocks: All interiors, World.
- Status: open. (also: asset-conversion Q7; starfield-toolchain Q7; versions-performance Q5, Q6, Q18)

### Pipeline at scale: inputs, build time, disk, archives

**AP-49. What is the total first-install time and peak disk per asset class, on the owner's PC and on a minimum-spec PC?**
- Why it matters: Starfield 125 GB on SSD plus FO4 plus work folder plus output plus temporary archives; the owner's 7950X3D hides costs.
- Options: measure the whole 64-cell core, scale by cell count; rerun with a memory cap and fewer cores.
- Answer by: timed full conversion with peak disk and peak RSS; PC probe (or cloud VM with matching cores).
- Blocks: Launcher, Release.
- Status: open. (also: asset-conversion Q13; versions-performance Q15, Q16)

**AP-52. Which FO4 data versions does the converter accept, and how does it detect them from data alone?**
- Why it matters: most players have 1.11.240; `ba2.py` accepts only header versions 1 to 3; v7/v8 for next-gen is **unresolved**.
- Options: hash `.esm` files per known version (TTW model); read BA2 header versions; check for Anniversary CC files; support all versions with fixtures, or normalise inputs.
- Answer by: first 8 bytes of each `Fallout4 - *.ba2` on a current install (minutes); a record and archive diff between 1.10.163 and 1.11.240; PC probe then owner decision.
- Blocks: Launcher, New game, Release.
- Status: open. (also: asset-conversion Q15; versions-performance Q7, Q8, Q9, Q31)

**AP-54. Are the about 150 Anniversary Creation Club files, and GOG or Microsoft Store FO4 installs, valid asset sources?**
- Why it matters: they change what "the player's FO4" means and widen the asset surface.
- Options: ignore `cc*` files; opt in per file; Steam only.
- Answer by: owner decision; file listings and hashes from GOG and Game Pass installs (community contact).
- Blocks: Launcher, Release.
- Status: open. (also: versions-performance Q10, Q11)

**AP-55. How are outputs packed under engine limits: archive count, size per archive, auto-loaded archive names?**
- Why it matters: 256 active BA2s shared with the player's mods; 4,095 MB per archive; whether one archive can pass 4 GiB is unresolved; 64 cells need about 8.5 GiB.
- Options: one ESM with `- Main.ba2` and `- Textures.ba2`; numbered archives (`- Main01.ba2`, unresolved); BA2 Limit Fix (SFSE).
- Answer by: a synthetic archive over 4 GiB and two numbered archives loaded in game; archive count with Starfield Engine Fixes' counter; PC probe.
- Blocks: All interiors, World, Launcher.
- Status: open. (also: starfield-toolchain Q14; versions-performance Q4, Q17)

**AP-56. Does the build cache key include the Starfield runtime and Starfield.esm hash?**
- Why it matters: a Starfield patch can change records we override or vanilla assets we reference.
- Options: full Starfield.esm hash; only overridden records and referenced paths.
- Answer by: offline design.
- Blocks: Launcher.
- Status: open. (also: versions-performance Q14)

### Tool dependencies and licences

**AP-50. Which steps may depend on Bethesda or third-party tools installed on the player's PC, and is each acceptable?**
- Why it matters: CK is settled; Wwise and 3ds Max are not; each adds install friction and per-patch risk.
- Options: CK for FaceFX, navmesh, maybe LOD and Archive2; Wwise for `.wem`; avoid 3ds Max.
- Answer by: owner decision after AP-30 and AP-40.
- Blocks: Launcher, Release, People and story.
- Status: open. (also: asset-conversion Q35; starfield-toolchain Q11, Q25)

**AP-51. Which external binaries may the launcher bundle, and which must the player fetch?**
- Why it matters: GitHub then Nexus release must meet each licence.
- Options (licences as found): texconv (MIT, **supported hypothesis**), CALUMI (LGPL-3), HavokLib (GPL-3), Geometry Bridge (MIT), Mutagen and Spriggit (GPL-3), vgmstream and ffmpeg (not read), Wwise (not bundlable, **supported hypothesis**), CK (player installs). Nexus "no conversion to other games" clauses (Void SFG Bridge, Animation IO) versus their GitHub licences.
- Answer by: a licence table (offline research), then owner decision.
- Blocks: Release, Launcher.
- Status: open. (also: asset-conversion Q14, Q31; starfield-toolchain Q26)

**AP-53. Which tool authors do we contact first?**
- Why it matters: their work overlaps our open items.
- Options: Calaverah (CALUMI compression), SesamePaste or MrTrilB (constraints, skin), Momidi and DJLegends (whole-master lip sync), the Souls of Cities author (run-time faces), the Void SFG Bridge author (batch re-skin).
- Answer by: owner decision (outreach is the owner's job under AGENTS.md).
- Blocks: People and story, Fallout systems.
- Status: open. (also: asset-conversion Q32; people-story Q31)

**AP-57. Which readers and writers are reusable when FO3 and New Vegas join?**
- Why it matters: FO3/NV NIFs (BS 34, `NiTriShape`, hk_550 collision) and audio (`.ogg`, `.lip`) differ from FO4.
- Options: a second reader feeding the same Starfield writers; only the decode step changes for audio.
- Answer by: list each reader and writer and its game coupling; offline.
- Blocks: Multi-game.
- Status: open. (also: asset-conversion Q36)

## Owner decisions in this area

Recommendations, not decisions:

- **AP-50 player-installed tools:** recommend CK required, Wwise only if AP-30 shows free headless use is allowed, 3ds Max never. Why: CK is already allowed; Wwise is the only verified encoder.
- **AP-51 bundling:** recommend bundling only permissive and LGPL/GPL tools with notices; the player installs CK and Wwise. Why: keeps the no-assets, GPL-noticed release clean.
- **AP-20 animation route:** recommend SFSE glTF players for idles and scenes first, `.af` retargeting later. Why: no `.agx` spec, and SFSE is allowed.
- **AP-10 named-cast faces:** recommend template faces for breadth, hand-made record faces for the main cast later. Why: only route (c) is known to lip sync without shipping assets.
- **AP-07 / clothing:** recommend Starfield stand-in outfits first. Why: re-skinning is not batch-proven.
- **AP-45 text-only lines:** recommend our own silent `.wem` placeholders, keeping SFSE optional. Why: data-only survives patches better.
- **AP-52 / AP-54 FO4 inputs:** recommend accepting 1.10.163 and 1.11.240 data with detection, ignoring `cc*` files by default. Why: most players are on 1.11.240; CC files widen scope.
- **AP-53 contacts:** recommend Calaverah and DJLegends first. Why: compression and lip-sync automation are the top blockers.

## Cheapest experiments

Offline first:

1. **Asset census over the owner's FO4 archives:** max vertices per shape, texture count and size, `.xwm` decode with failure count. Closes AP-01, AP-24 (count part), AP-32; feeds AP-49.
2. **Full-archive convert-and-count run per class** with a failure report. Closes AP-05; feeds AP-01, AP-22, AP-49.
3. **Licence table** for every tool named here. Closes AP-51; feeds AP-50.
4. **Read Geometry Bridge `.dat` code and Starfield Blender Extension constraint code.** Feeds AP-04, AP-11.
5. **Read one FO4 `.bto` against a vanilla `_lod_0.nif`; scan Starfield.esm for precombine-like data.** Feeds AP-47, AP-48.

PC read-only probes:

6. **Strings scan of CreationKit.exe** for FaceFX, LOD and precombine switches (like the navmesh one). Feeds AP-40, AP-47, AP-48, AP-50.
7. **First 8 bytes of every `Fallout4 - *.ba2`** on a current install, plus `.esm` hashes. Closes the BA2 part of AP-52; feeds AP-54.
8. **Read-only dump of both games' `skeleton.nif`.** Closes AP-06.

PC probes that write test data (owner time):

9. **1,000-line FaceFX run** from a space-free staging folder: time it, rerun to test resume, compile 20 lines twice for hashes, try WAV-only. Closes AP-40 (timing), AP-41, AP-42, AP-43; feeds AP-44.
10. **WwiseConsole on `Starfield.wproj` without the GUI.** Feeds AP-30, AP-50.
11. **Whole-core build with peak disk, RSS and time,** then with a memory cap. Closes AP-49.

## Gaps for wave 2

- Read the Audiokinetic Wwise licence terms: free use, automation, redistribution (AP-30, AP-51).
- Find any open-source Wwise Vorbis `.wem` encoder (AP-30).
- Search for a public `.agx` description or editor, and Starfield animation text data or subgraph practice (AP-20, AP-21).
- Search for xLODGen or other Starfield object LOD support, and CK LOD batch use (AP-47).
- Find whether CE2 has a precombine or previs equivalent; Starfield draw-call and VRAM profiles (AP-48, AP-25).
- Confirm next-gen FO4 BA2 header versions (v7/v8) and their layout from BSArch or xEdit source (AP-52).
- Read the TTW FAQ and the Cathedral Assets Optimizer README (rate-limited in wave 1) to verify the precedent lessons.
- Read Nexus article 535 on music replacers (AP-33) and any guide on new WWED events (AP-31).
- Licences of vgmstream, ffmpeg builds, texconv (re-read), Trainwreck and the Starfield Blender Extension (AP-51).
- Starfield NPC face pipeline: whether a new NPC_ renders a face without facegen files (AP-09) from community sources.
- FO4 install size with DLC and Anniversary content (AP-49).

## Handed to phase files

| question | target file |
|---|---|
| Which Vault 111 assets are not yet converted (spouse, Shaun, Vault-Tec rep, cryo pods, freeze effects); stand-in or posed actors? (asset-conversion Q1) | newgame.md |
| Do Vault 111 effect materials (frost, glow, cryo glass) need the emissive `.mat` path before phase 1? (asset-conversion Q2) | newgame.md |
| Silent opening, or the spouse's voiced intro with FaceFX in phase 1? (asset-conversion Q3) | newgame.md |
| Can CALUMI door clips cover every FO4 door family? (asset-conversion Q4; general part kept as AP-22) | door-animations.md |
| Which FO4 door sounds map to Starfield WWED events? (asset-conversion Q5; general part kept as AP-31) | door-animations.md |
| Census of FO4 effect, animated and swap materials per interior (asset-conversion Q9) | interiors.md |
| Can interior movable clutter use FO4 bodies for all 961 MSTT bases? (asset-conversion Q10) | interiors.md |
| Power armor: which pieces are asset conversion and which are systems? (asset-conversion Q27) | engine-mechanics.md |
| Pip-Boy first-person model, `.af` and animated screen material (asset-conversion Q28) | engine-mechanics.md |
| First-person weapon animations: Starfield weapon graphs or the effect-sequence trick (Nexus 17294)? (asset-conversion Q30) | engine-mechanics.md |
| Trees and foliage at distance (FO4 TREE has no Starfield record) (asset-conversion Q18) | world-planet framework file (cross-cutting, this wave) |
| FO4 region, ambient and weather sounds to Starfield biome and weather events (asset-conversion Q19; general part kept as AP-31) | world-planet framework file |
| Launcher pin strategy, disk check UI, version refusal (starfield-toolchain Q13; versions-performance Q12, Q13) | launcher.md |

## Sources

- Repo (read-only, as cited by the findings): docs/FORMAT-GAP.md, docs/ROADMAP.md, docs/RISKS.md, docs/ACTOR-MILESTONE.md, docs/spikes/S1-mesh-writer.md, S3-materials.md, S6-collision.md, S2-S4-S9-plugin-units-loading.md, WP-doors-research.md, docs/terrain/object-lod.md, docs/actors/npc-navigation.md, docs/ai/research-log.md, docs/ai/decisions.md, docs/ai/optimization.md, docs/JOURNAL.md, src/fo4sf/ba2.py and the converter modules named in findings/asset-conversion.md; /mnt/project-files/research/next-phase/physics-conversion.md; /mnt/project-files/research/engine-mechanics/materials-textures-lighting.md
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Main_Page
- https://www.nexusmods.com/starfield/mods/12561
- https://nexusmods.com/starfield/mods/12576
- https://www.nexusmods.com/starfield/mods/12842
- https://www.nexusmods.com/starfield/articles/641
- https://www.nexusmods.com/starfield/articles/173
- https://www.nexusmods.com/starfield/articles/535 (found, not read)
- https://facefx.com/node/4600
- https://starfieldwiki.net/wiki/Starfield_Mod:Adding_Collision_with_3ds_Max_2021
- https://starfieldwiki.net/wiki/Starfield_Mod:Setting_up_3ds_Max_2021_for_Starfield
- https://starfieldwiki.net/wiki/Starfield_Mod:Creation_Kit
- https://starfieldwiki.net/wiki/Starfield:System_Requirements
- https://nexusmods.com/starfield/mods/4360
- https://www.nexusmods.com/starfield/mods/16979
- https://www.nexusmods.com/starfield/mods/17968
- https://www.nexusmods.com/starfield/mods/9234
- https://www.nexusmods.com/starfield/mods/9326
- https://www.nexusmods.com/starfield/mods/3153
- https://allmods.net/?p=225677
- https://allmods.net/starfield-mods/starfield-miscellaneous/organization-of-starfields-meshes-and-related-assets/
- https://github.com/fo76utils/nifskope/releases
- https://github.com/BadDogSkyrim/PyNifly/
- https://forums.nexusmods.com/topic/13491770-nifskope-how-to-convert-nitrishape-into-bsgeometry-mesh-please-help
- https://www.nexusmods.com/starfield/mods/16184
- https://github.com/Calaverah/CALUMI.Animation
- https://github.com/deveris256/sf_animation_io
- https://github.com/PredatorCZ/HavokLib
- https://www.nexusmods.com/starfield/mods/7360
- https://www.nexusmods.com/starfield/mods/16124
- https://www.nexusmods.com/starfield/mods/17457
- https://www.nexusmods.com/starfield/mods/17294
- https://www.nexusmods.com/fallout4/mods/16694
- https://www.nexusmods.com/fallout4/mods/41209
- https://nexusmods.com/fallout4/mods/69177
- https://falloutck.uesp.net/wiki/Subgraphs (found, not read)
- https://github.com/ejams1/starfield-modding-guide
- https://www.nexusmods.com/starfield/mods/17936
- https://forums.nexusmods.com/topic/13518743-crash-issue-too-many-ba2-files-causing-ctds-%E2%80%93-looking-for-fix-or-insight/
- https://www.nexusmods.com/starfield/mods/10457?tab=files
- https://www.nexusmods.com/news/15400
- https://www.nexusmods.com/news/14993
- https://www.nuget.org/packages/Mutagen.Bethesda.Starfield
- https://github.com/Mutagen-Modding/Spriggit
- Not readable in wave 1 (HTTP 429): https://taleoftwowastelands.com/faq , https://github.com/Guekka/Cathedral_Assets_Optimizer
