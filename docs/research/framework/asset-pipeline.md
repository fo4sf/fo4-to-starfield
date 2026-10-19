# Asset pipeline: converting every Fallout 4 asset class on the player's PC

Part of the [next-phase framework](README.md). Waves 1 and 2, 2026-10-19. Sources: findings/asset-conversion.md, findings/starfield-toolchain.md (asset parts; wave 2 LOD, precombine, CDB, BA2), findings/people-story.md (faces, lip sync, clothing; wave 2 facegen), findings/versions-performance.md (disk, archive limits; wave 2 BA2), findings/legal-policy.md (wave 2 Wwise licence).

## In short

- Static assets are solved in our own code and verified in game: meshes (S1 writer), materials (S3 `.mat` cloner) and collision (compressed-mesh transplant). Outside tools are oracles, not dependencies.
- Voice and lip sync have a proven route: loose `.wem` for playback plus the Creation Kit's FaceFX compiler for `.ffxanim`. A community mod ran it over whole masters. Unattended running, time per 1,000 lines and resume are not proven.
- Sound effects, behaviour graphs (`.agx`), facegen and skinned clothing are the open research areas. Wave 2: named NPC faces need per-NPC baked FaceGeom NIFs plus face DDS (CK GUI bake or our own writer). ~~Object LOD has a CK command-line switch (`-MockWorldSpaceLOD`)~~ [Correction 2026-10-19: ~~whether `-MockWorldSpaceLOD` exists is **unresolved (sources conflict)**~~: web guides say it does, ~~a job 18 string dump of the installed CreationKit.exe does not show it~~ [Correction 2026-10-19: the job 18 dump printed only strings matching its default patterns (Generate, Compile, Lip, AnimInfo, -Convert, -Build), so it had filtered the switch out; job 20 (read-only, patterns Mock, WorldSpaceLOD and "Should be -") found it: **verified (Starfield CK, job 20)**, usage "-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [WorldSpaceName1] [...]"]; the dump does show `-GenerateMeshLOD*` switches (**verified**)]; Starfield has no precombine or previs records, ~~so there is nothing to bake there~~ [Correction 2026-10-19: but its CK has the GUI actions "Generate Precombined Visibility for Current Cell" and "... All Loaded Cells" (interiors.md T9), so a precombined-visibility bake may exist; what it writes and whether it matters for performance is **unresolved**].
- Scale is unmeasured: no whole-game build time, no peak disk figure, no FO4 texture count. Engine ceilings (256 BA2s, about 4 GiB per archive) are known; the BA2 format itself has 64-bit offsets. TTW's installer (about 40 minutes, mostly audio encoding) is the nearest precedent.
- Most uncertain: whether CK-only steps (FaceFX, face bakes, LOD) can run with no human, and whether `.wem` encoding needs Wwise on the player's PC. Wave 2: Wwise's free trial is non-commercial and limited to 200 media assets in SoundBanks; whether a player's batch conversion is allowed is a question for Audiokinetic.
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
- Lip sync is produced only by the CK's embedded FaceFX (Audio > Run FaceFX Compiler; log `ffxc_00.log`) (**verified**, same sources and [facefx.com/node/4600](https://facefx.com/node/4600)). [Correction 2026-10-19: besides the menu, the Starfield CK has a `-CompileFaceFXAnims` switch and ships `Tools\LipGenerator\LipGenerator.exe` (**verified**, job 18 string dump); it has no `-GenerateLips` (the FO4 CK has `-GenerateLips` and `-GenerateSingleLip`). Neither CK has a script-compile switch; `PapyrusCompiler.exe` does that, headless.] It has been run over all of `Starfield.esm` and `ShatteredSpace.esm` (**verified**, Lip Sync Japanese, [Nexus 12842](https://www.nexusmods.com/starfield/mods/12842)).
- Starfield's Wwise version is 2021.1.14.8108; the CK installs `Starfield.wproj`; "Convert All Audio Files" writes `.wem` to `.cache/<platform>` (**verified**, [Xbox porting guide](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox), [Nexus 12561](https://www.nexusmods.com/starfield/mods/12561)). Use Vorbis; PCM is about 10x bigger (**verified** article, comments **supported hypothesis**, [Nexus article 173](https://www.nexusmods.com/starfield/articles/173)).
- Named Starfield NPCs have pre-baked facegen meshes and textures (**verified**, Enhanced Hadrian, [Nexus 9326](https://www.nexusmods.com/starfield/mods/9326)).
- Unvoiced lines flash past too fast to read in Starfield (**verified**, Starfield Silent Voice, [Nexus 3153](https://www.nexusmods.com/starfield/mods/3153)).
- BA2: 4,095 MB per archive, split large sets; v2 GNRL/DX10 and v3 LZ4 textures; Archive2 ships with the CK (**verified**, [ejams1 guide](https://github.com/ejams1/starfield-modding-guide), repo S9). At most 256 active archives; an SFSE "BA2 Limit Fix" raises it (**verified**, [Nexus 17936](https://www.nexusmods.com/starfield/mods/17936)).
- Starfield patch 1.11.36 renamed about 323,099 vanilla mesh paths (**verified**, [Nexus 9234](https://www.nexusmods.com/starfield/mods/9234)). Lesson: resolve vanilla paths at build time, never hard-code them.
- Hardware floor: 16 GB RAM, GTX 1070 Ti class, 125 GB on an SSD (required) (**verified**, [system requirements](https://starfieldwiki.net/wiki/Starfield:System_Requirements)).

Wave 2 facts (2026-10-19):

- Facegen: Starfield ships per-NPC face geometry at `meshes\Actors\Character\FaceGenData\FaceGeom\Starfield.esm\<FormID>.nif` and per-NPC face textures under `textures\actors\character\facecustomization\starfield.esm\`. The CK makes them with two GUI bakes on the NPC's Face Customization tab: "Bake FCT" (Ctrl+F4; ao, color, normal, rough DDS) and "Bake Chargen Mesh Geometry"; facial-structure edits need the geometry bake. Export silently writes nothing for actors with the Chargen preset flag or a Use Traits template. Results are inconsistent (bald heads, seams; one crash report on CK 1.15.222, another user has both bakes working) (**verified**, people-story W2-2; [Nexus 5572](https://www.nexusmods.com/starfield/mods/5572), [forum 13521838](https://forums.nexusmods.com/topic/13521838-ck-bugquestion-%E2%80%9Cbake-chargen-mesh-geometry%E2%80%9D-always-crashes-%E2%80%94-is-this-broken-for-everyone/)). Bakes are keyed by plugin name, so for us they must be made on the player's PC or emitted as generated data (**supported hypothesis**).
- Object LOD: `CreationKit.exe -MockWorldSpaceLOD:<Plugin>.esp <Worldspace>,...` writes LOD `.nif` to `Data\Meshes\Terrain\<Worldspace>\` and settings to `Data\LODSettings\`; objects are picked by layers with the LOD box ticked; "one or more cells may fail to process", more likely in multi-cell worldspaces (~~**verified**~~ [Correction 2026-10-19: ~~**unresolved (sources conflict)**~~: web guides say the switch exists; ~~a keyword-filtered string dump of the installed CreationKit.exe (job 18, `D:\Modding\research\ck_switches_1.txt`) does not show it, though it shows other "WorldSpace" strings and~~ the job 18 dump shows the LOD-related `-GenerateMeshLODAssociations`, `-GenerateMeshLODFailureReport`, `-GenerateMeshLODStats` (**verified**)~~; it may be a wide string the filter missed, or absent in the current CK~~] [Correction 2026-10-19: **verified (Starfield CK, job 20)**: the job 18 dump printed only strings matching its default patterns (Generate, Compile, Lip, AnimInfo, -Convert, -Build), so it had filtered the switch out (the other "WorldSpace" strings appeared only because they also contain "Generate"); job 20 (read-only, patterns Mock, WorldSpaceLOD and "Should be -") shows it in the Starfield CK, not in the FO4 CK, usage "-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [WorldSpaceName1] [...]" (an ESM filename)], [modding.wiki](https://modding.wiki/en/starfield/developers/tutorials/creatingworldspacelod), [forum 13497519](https://forums.nexusmods.com/topic/13497519-how-to-create-lod/)). LAYR has `LODB` (Default / Aggregate / No LODs) and base objects carry "Has Distant LOD" / "Is Full LOD" flags, so LOD membership is plugin data we can write (**verified** schema, xEdit `wbDefinitionsSF1.pas`). xLODGen/DynDoLOD do not list Starfield (**verified**, [dyndolod.info](https://dyndolod.info/Help/xLODGen)).
- Terrain edits reach the game only through an exported `.btd`; our pipeline already writes BTD directly (**verified**, [Steam guide 3385012985](https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985)).
- Precombines: Starfield's CELL has no `PCMB`, `VISI`, `XPRI` or `XCRI` (FO4 has all four); Starfield has an `OVIS` "Object Visibility Manager" record of unknown purpose (**verified** schema, xEdit `wbDefinitionsSF1.pas` / `wbDefinitionsFO4.pas`). The renderer builds indirect draw arguments on the GPU (ExecuteIndirect) (**verified**, [vkd3d-proton PR 1694](https://github.com/HansKristian-Work/vkd3d-proton/pull/1694)). [Added 2026-10-19] CK strings (interiors.md T9, both CK string dumps, PC job 18): the FO4 CK has `-GeneratePreCombined` and `-GeneratePreVisData`; the Starfield CK has neither switch but has the GUI actions "Generate Precombined Visibility for Current Cell" and "... All Loaded Cells" (**verified** strings), and `-GenerateCellAndRefCounts` (possibly per-cell reference counts; **unresolved**). What the Starfield bake writes and whether it matters for performance is **unresolved**.
- Materials: no public tool writes or merges `materialsbeta.cdb`; the community uses loose `.mat` plus the CK's refresh (**supported hypothesis**). Starfield Material Exporter (SFME, open source) reads the CDB or Materials BA2 and exports loose `.mat` JSON (**verified**, [github.com/maximusmaxy/SFME](https://github.com/maximusmaxy/SFME)).
- Textures: Cathedral Assets Optimizer (MPL-2.0) does not list Starfield; every Starfield batch texture tool found wraps texconv (**verified** CAO page and repo, **supported hypothesis** for "no CAO equivalent"; asset-conversion W2-2). BA2 Upgrader rewrites texture BA2s to v3 (LZ4), and the CK's Archive2 writes v3 directly (**verified**, user comments, [Nexus 1192](https://www.nexusmods.com/starfield/mods/1192?tab=posts)).
- BA2: FO4 next-gen archives are header versions 7 and 8; xEdit and OpenMW parse them exactly like v1 (**verified**, [Nexus FO4 article 5844](https://www.nexusmods.com/fallout4/articles/5844), xEdit `wbBSArchive.pas`, [OpenMW MR 4055](https://gitlab.com/OpenMW/openmw/-/merge_requests/4055)); so v7/v8 changed only the version number (**supported hypothesis**, three readers agree). BA2 offsets are 64-bit in the format (**verified**, `wbBSArchive.pas`); FO4 users report 9.5 GB and 14.7 GB archives loading; Starfield above 4 GiB is **unresolved**.
- Medium masters hold ObjectIDs 0x0000 to 0xFFFF (at most 65,536) and there are 256 medium slots; Update-flagged files cannot hold new records (**verified**, xEdit `wbImplementation.pas`, `wbInterface.pas`).
- Wwise: the free trial is for non-commercial projects and limited to 200 media assets in SoundBanks; a free Non-Commercial licence can be requested per project; licences are tied to one project (**verified**, [Wwise pricing](https://www.audiokinetic.com/en/wwise/pricing/)). Nothing found on redistributing WwiseConsole or on whether `convert-external-source` counts toward the 200 limit; full EULA not read (**unresolved**).
- TTW precedent: its installer applies xdelta3 patches to the player's own files, transcodes audio (all voice to 24 kHz), and "patches and creates all non-unique assets dynamically from original game files"; about 40 minutes on a Ryzen 5 5600X, mostly audio encoding; a `-threads:1` switch; a 17 GB output folder is the community's install check; both games must be English (**verified**, [TTW FAQ](https://thebestoftimes.moddinglinked.com/faq.html), [install guide](https://thebestoftimes.moddinglinked.com/ttw.html)).

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
| Drive the CK face bakes (Bake FCT + Bake Chargen Mesh Geometry) per named NPC on the player's PC | baked FaceGeom NIF + four face DDS keyed by our plugin | GUI, per actor, inconsistent results, crash reports; no headless switch known | people-story W2-2 | **verified** bakes exist, **unresolved** unattended |
| Write FaceGeom `.nif` + ao/color/normal/rough DDS ourselves | no CK bake | internal FaceGeom layout unknown (likely `BSFaceGenNiNode`) | Geometry Bridge `.dat` code | **unresolved** |
| "Use Traits" template NPCs (no per-NPC bake) | no bake step | no unique face | vanilla generic crowds | **supported hypothesis** |

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
| Export vanilla `.mat` JSON with SFME (open source, reads CDB) and diff with ours | scriptable material oracle | reader only, no CDB writer exists | [SFME](https://github.com/maximusmaxy/SFME) | **verified** tool |
| Pack converted textures into v3 (LZ4) texture BA2s instead of loose | users report faster loads, smoother play | maybe a `sResourceIndexFileList` INI entry; Bethesda-like compression takes tens of minutes to hours | BA2 Upgrader ([Nexus 1192](https://www.nexusmods.com/starfield/mods/1192?tab=posts)), Archive2 | **supported hypothesis** (user reports) |

### Sound and music

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| Decode `.xwm` (ffmpeg) then Wwise 2021.1.14.8108 encodes Vorbis `.wem` on the player's PC | correct format | free trial is non-commercial, 200 media assets in SoundBanks; whether `convert-external-source` counts and whether a player's batch conversion is covered is **unresolved**; headless unknown; player installs under own account | Nexus 12561, article 173; modder licence paths at MSFS and REDkit ([Wwise pricing](https://www.audiokinetic.com/en/wwise/pricing/)) | **supported hypothesis** |
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
| CK object LOD: `CreationKit.exe -MockWorldSpaceLOD:<Plugin>.esp <Worldspace>` | official output, command line | some cells may fail in multi-cell worldspaces; stray meshes reported; `.esm` acceptance and 64-cell time unknown | [modding.wiki](https://modding.wiki/en/starfield/developers/tutorials/creatingworldspacelod), docs/terrain/object-lod.md | ~~**verified** command~~ [Correction 2026-10-19: ~~**unresolved (sources conflict)**, not in the job 18 CK string dump~~] [Correction 2026-10-19: **verified (Starfield CK, job 20)**; the job 18 dump's filter patterns had filtered it out; usage "-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [WorldSpaceName1] [...]"], **supported hypothesis** it runs unattended |
| Converter sets LAYR `LODB` and object LOD flags so the CK run picks the right objects | no manual layer work | which flags vanilla uses unknown | xEdit SF1 schema | **supported hypothesis** |
| Convert FO4 `.bto` as stand-in `_lod_N` NIFs | whole map at once | `lodruntimedb.bgsdb` listing unknown | none | **unresolved** |
| Third-party generator (xLODGen-style) | batch | xLODGen/DynDoLOD do not list Starfield | none | **verified** not available |
| Merge static geometry per cell ourselves | fewer draw calls | new writer work; CE2 has no precombine records and draws GPU-driven, so the need is unproven [Correction 2026-10-19: the Starfield CK has "Generate Precombined Visibility" GUI actions (interiors.md T9), so an engine-side bake may exist; unresolved] | FO4 precombines | **supported hypothesis** not needed |
| Place references one by one (current) | simple | draw-call cost unmeasured | Phase A walk, no crash | **verified** current state |

### Packaging, input versions and budgets

| option | what it gives | cost or risk | precedent | label |
|---|---|---|---|---|
| One ESM + 1 to 3 archives, medium masters for DLC areas | stays under 256 BA2s | archives over 4 GiB unresolved (format allows it); a medium master holds at most 65,536 ObjectIDs, so world plugins must be full masters | versions-performance Q17, toolchain W2-5 | **supported hypothesis** |
| Archive2 from the CK install | official packer | needs CK (allowed) | repo S9 | **verified** |
| Open packer (bsa-rs) | no CK for packing | maintenance | toolchain Q11 | **unresolved** |
| Detect FO4 data version by `.esm` hashes and BA2 headers | right converter per player | per-version fixtures; BA2 v7/v8 read with the v1 layout | TTW model (installer needs both games with all DLCs, in English, **verified**), xEdit and OpenMW for v7/v8 | **supported hypothesis** |

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
- Options: pre-baked (named vanilla NPCs have it); run-time (vanilla crowds and Souls of Cities suggest it works). Wave 2: a custom named face needs the CK's two bakes (Bake FCT, Bake Chargen Mesh Geometry) or our own FaceGeom NIF + four DDS writer; "Use Traits" template NPCs need no per-NPC bake.
- Answer by: a new NPC_ with custom morphs and no facegen files, in game, to see the exact fallback; PC probe.
- Blocks: People and story.
- Status: narrowed (wave 2): named NPCs render from pre-baked FaceGeom `.nif` + face DDS keyed by plugin and FormID; missing or stale bakes look visibly wrong (bald, mismatched) rather than being rebuilt from the record (**supported hypothesis**); templated Use Traits NPCs have no per-NPC bake. Open: the exact run-time fallback, and whether bakes can be made without the CK GUI (**unresolved**). [people-story W2-2; asset-conversion W2-3] (also: asset-conversion Q22; people-story Q6, Q17) [Update 2026-10-19: narrowed: the Starfield CK has "-ExportFaceGenData:(ESMFilename) (TESNPCExportFaceDataMode) [Platform]" and the FO4 CK "-ExportFaceGenData:(ESMFilename) (XB1|X64|PS4|W32)" (**verified**, job 20 string read, never run), so a headless facegen export may exist; whether it bakes or only exports is **unresolved**.]

**AP-10. Which named-cast face route, and does it lip sync?**
- Why it matters: Preston, Piper and Nick looking like strangers is the most visible flaw.
- Options: (a) template; (b) FO4 head as ARMO, likely no lips; (c) hand-made record values (Enhanced Hadrian method); (d) dial-fitting optimiser.
- Answer by: one ARMO head speaking a line; one hand-made Preston face; PC probe, then owner decision.
- Blocks: People and story.
- Status: narrowed (wave 2): routes (c) and (d) give a unique face only with a per-NPC bake (CK GUI, crash-prone, inconsistent) or our own FaceGeom writer (AP-11); a Use Traits template route avoids bakes but gives up a unique face. Bakes are keyed by our plugin name, so they are made on the player's PC or emitted as generated data, never shipped as Bethesda assets (**supported hypothesis**). [people-story W2-2] (also: people-story Q15) [Update 2026-10-19: the per-NPC bake may have a headless path: `-ExportFaceGenData` in the Starfield CK (**verified**, job 20; bake or export only is **unresolved**, AP-09).]

**AP-11. Can FO4 facegen `.nif` + `.tri` be converted to `BSFaceGenNiNode` + morph `.dat` at all?**
- Why it matters: the only fully automatic route to FO4 faces.
- Options: read Geometry Bridge's `.dat` code as reference (MIT); no other reader known. Wave 2: the target is the vanilla pair `FaceGeom\<Plugin>\<FormID>.nif` plus ao/color/normal/rough DDS under `facecustomization\<plugin>\`; or drive the CK bakes instead.
- Answer by: read-only dump of one vanilla FaceGeom NIF against what our NIF writer emits (offline), then one test face (PC probe).
- Blocks: People and story.
- Status: narrowed (wave 2): output files and paths are known (**verified**); the FaceGeom NIF's internal layout (likely `BSFaceGenNiNode` per FORMAT-GAP) is **unresolved**. [asset-conversion W2-3; people-story W2-2] [Update 2026-10-19: "drive the CK bakes" may be headless via `-ExportFaceGenData` (**verified** switch, job 20; bake or export only is **unresolved**, AP-09).]

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
- Options: count from archives offline; time a sample with texconv. Wave 2: no CAO-like batch optimiser exists for Starfield; every tool found wraps texconv, so our S3 step is the norm; choices left are BC format per role, downscaling 4K FO4 HD textures, and packing (AP-58).
- Answer by: archive listing count plus a timed 1,000-texture batch; offline then PC probe.
- Blocks: Launcher, World.
- Status: open (tooling narrowed, wave 2: texconv is the only engine, **supported hypothesis**; count and time still unmeasured). [asset-conversion W2-2]

**AP-25. What texture caps does the default build use per VRAM tier?**
- Why it matters: today's caps (1024 colour, 512 normal) were set for archive size, not VRAM.
- Options: three presets keyed to detected VRAM.
- Answer by: VRAM use at each cap on an 8 GB card; PC probe on lower-end hardware (community).
- Blocks: Launcher, Release.
- Status: open. (also: versions-performance Q20)

**AP-26. Can we use fo76utils NifSkope's compiled-material reader as an oracle for our loose `.mat`?**
- Why it matters: no offline check today against vanilla compiled materials.
- Options: fo76utils NifSkope (GUI); Starfield Material Exporter (SFME, open source, reads `materialsbeta.cdb` or the Materials BA2 and exports loose `.mat` JSON, so it can be scripted).
- Answer by: export a vanilla material with SFME (or the fixed Extract Resource Files spell) and diff with our clone; offline.
- Blocks: All interiors (quality checks).
- Status: narrowed (wave 2): SFME is a **verified** open-source CDB reader and the better oracle candidate; no public tool writes a CDB, which supports our loose-`.mat` route (**supported hypothesis**). [starfield-toolchain W2-3, its Q36]

**AP-58. Do we pack converted textures into Starfield v3 (LZ4) texture BA2s instead of loose files, and must each BA2 be listed in `sResourceIndexFileList`?**
- Why it matters: users report better load times and smoother play with v3 and fewer archives (**supported hypothesis**, user reports); one BA2 Upgrader user says packed former loose files need that INI entry.
- Options: Archive2 from the CK writes v3 directly; our own v3 writer; stay loose. Bethesda-like compression takes "tens of minutes to several hours" in BA2 Upgrader.
- Answer by: load time and stutter, loose vs v3 BA2, same route; with and without the INI entry; PC probe.
- Blocks: Launcher, World, All interiors.
- Status: open (new, wave 2). [asset-conversion W2-2] (also: AP-55)

### Sound and music

**AP-30. Is Wwise 2021.1.14.8108 authoring on the player's PC acceptable (licence, download, login), and can it convert headless?**
- Why it matters: it is the only verified `.wem` encoder; 122,857 voice files plus SFX depend on it.
- Options: Wwise on player PC, installed under the player's own Audiokinetic account (free trial or a requested Non-Commercial licence); an open encoder (none known, must be verified against the format); another playback path.
- Answer by: ask Audiokinetic in writing whether a player's free install may batch-convert their own game's audio for a free mod, and whether `convert-external-source` output counts toward the 200-asset limit (community contact); read the full EULA (offline); WwiseConsole on the CK's `Starfield.wproj` without GUI (PC probe).
- Blocks: People and story, Launcher, Fallout systems (radio).
- Status: narrowed (wave 2): free trial is non-commercial and limited to 200 media assets in SoundBanks; licences are per project; MSFS and REDkit send modders to a free non-commercial key (**verified**). Nothing on redistributing WwiseConsole or on conversion counting (**unresolved**). We cannot bundle Wwise; a per-player batch conversion is a use none of the published modder paths describe (**supported hypothesis**). Headless use still untested. [legal-policy W2-B] (also: asset-conversion Q12; starfield-toolchain Q19; legal-policy W2 Q5, Q6)

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
- Options: a CK command-line switch (~~unknown;~~ [Correction 2026-10-19: the Starfield CK has `-CompileFaceFXAnims` plus `Tools\LipGenerator\LipGenerator.exe`, **verified**, job 18; it has no `-GenerateLips`, which only the FO4 CK has, with `-GenerateSingleLip`; job 19 queued for LipGenerator's usage text;] navmesh switches exist in CreationKit.exe strings); GUI automation; direct `ffxc.exe` on the CK-written `.animset`; ship lips later.
- Answer by: strings scan of CreationKit.exe for FaceFX switches (PC read-only) [done 2026-10-19, job 18]; the Lip Sync Japanese recipe timed on 1,000 FO4 WAVs with `ffxc_00.log` captured (PC probe).
- Blocks: People and story, Launcher.
- Status: open. (also: asset-conversion Q11, Q20; starfield-toolchain Q18; people-story Q7) [Update 2026-10-19, job 21 (**verified**): Starfield's archives ship 0 `.facefx` files and 278,582 per-line `.ffxanim` lip files; LipGenerator.exe's required `actor.facefx` and `actoranalysis.facefx` inputs are not in the shipped data; where they come from is **unresolved** and must be settled before a timed run.]

**AP-41. Can the compile be split and resumed, and is its output deterministic?**
- Why it matters: a multi-hour step needs checkpoints; the launcher's determinism gate needs hashes.
- Options: batch per voice type or plugin; rerun skips existing `.ffxanim`. [Added 2026-10-19: split runs could go through `-CompileFaceFXAnims` or `Tools\LipGenerator\LipGenerator.exe` (both **verified** to exist, job 18; job 19 queued for LipGenerator's usage text).]
- Answer by: rerun on a half-done folder; compile 20 lines twice and compare hashes; PC probe.
- Blocks: Launcher.
- Status: open. (also: people-story Q8, Q34) [Update 2026-10-19: vanilla lips are per-line `.ffxanim` files (278,582 shipped, no `.facefx`; **verified**, job 21); LipGenerator.exe's `actor.facefx` and `actoranalysis.facefx` inputs are not shipped (source **unresolved**), see AP-40.]

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
- Options: CK `-MockWorldSpaceLOD:<Plugin>.esp <Worldspace>` on the player's PC (object LOD; objects chosen by LOD-ticked layers); FO4 `.bto` as `_lod_N` stand-ins; own writer. xLODGen/DynDoLOD do not support Starfield (**verified**). Terrain LOD stays our own `.btd` writer.
- Answer by: [Correction 2026-10-19: first settle whether `-MockWorldSpaceLOD` exists: ~~a wide-string search of CreationKit.exe or running it on a test worldspace~~ [Correction 2026-10-19: settled by job 20: **verified (Starfield CK, job 20)**, usage "-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [WorldSpaceName1] [...]"]; then] run `-MockWorldSpaceLOD` on a 4-cell test worldspace, time it, check `.esm` acceptance and the partial-cell failure on 64 cells (PC probe); read one `.bto` against a vanilla `_lod_0.nif` (offline).
- Blocks: World.
- Status: narrowed (wave 2): ~~the CK command and its output folders are **verified**~~ [Correction 2026-10-19: the CK command is ~~**unresolved (sources conflict)**~~: web guides describe it and its output folders, ~~the job 18 string dump of CreationKit.exe does not show it~~ [Correction 2026-10-19: the job 18 dump printed only strings matching its default patterns (Generate, Compile, Lip, AnimInfo, -Convert, -Build), so it had filtered the switch out; the command is **verified (Starfield CK, job 20)**, not in the FO4 CK, usage "-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [WorldSpaceName1] [...]" (an ESM filename); output folders still from web guides]; `-GenerateMeshLODAssociations`, `-GenerateMeshLODFailureReport` and `-GenerateMeshLODStats` are **verified** CK switches]; that it runs unattended is a **supported hypothesis**; run time, `.esm` acceptance and cell failures at 64 cells are **unresolved**. [starfield-toolchain W2-1, its Q15] (also: asset-conversion Q16, Q17; starfield-toolchain Q15)

**AP-48. Does Starfield have a precombine or previs step, and is per-reference placement fast enough without one?**
- Why it matters: FO4 relies on 95,856 precombined NIFs plus previs; we place about 650k references one by one.
- Options: find an engine feature; merge static geometry per cell ourselves; accept the cost; reduce clutter.
- Answer by: frame time, VRAM and RAM at 3 fixed spots (dense downtown, open wasteland, interior), vanilla vs core vs core-with-LOD (PC probe).
- Blocks: All interiors, World.
- Status: narrowed (wave 2), ~~first half answered~~: Starfield's CELL has no precombine or previs subrecords (**verified** schema), ~~so there is no bake to replicate~~ [Correction 2026-10-19: first half reopened: the "no bake step" hypothesis is weakened by interiors.md T9 (both CK string dumps, PC job 18): the FO4 CK has `-GeneratePreCombined` and `-GeneratePreVisData`; the Starfield CK has neither switch but has the GUI actions "Generate Precombined Visibility for Current Cell" and "... All Loaded Cells". Starfield may have a precombined-visibility bake run from the CK GUI; what it writes and whether it matters for performance is **unresolved**. The Starfield CK also has `-GenerateCellAndRefCounts` (possibly per-cell reference counts; **unresolved**)]; the GPU-driven renderer lowers per-object draw cost (**supported hypothesis**). Open: whether dense converted cells run well without it; remaining cost is likely reference loading, scripts, Havok and streaming (**supported hypothesis**, unmeasured). The `OVIS` record's purpose is **unresolved**. [starfield-toolchain W2-2; versions-performance W2-2] (also: asset-conversion Q7; starfield-toolchain Q7; versions-performance Q5, Q6, Q18)

**AP-59. Should the converter set LAYR `LODB` and object LOD flags itself so the CK LOD run picks the right objects without manual layer work?**
- Why it matters: `-MockWorldSpaceLOD` selects objects by LOD-ticked layers [Correction 2026-10-19: per web guides; whether the switch exists is ~~**unresolved (sources conflict)**~~, see AP-47] [Correction 2026-10-19: the switch is **verified (Starfield CK, job 20)**, see AP-47]; LAYR `LODB` (Default / Aggregate / No LODs), "Has Distant LOD" / "Is Full LOD" flags and `BGSLodOwner_Component` are plugin data (**verified** schema), so an unattended run needs them written by us.
- Options: the converter writes layers and flags; or an author ticks layers in the CK by hand (not unattended).
- Answer by: xEdit read of a vanilla overlay's layers (offline), then one CK LOD run on our flagged test worldspace (PC probe).
- Blocks: World.
- Status: open (new, wave 2). [starfield-toolchain W2-1, its Q35] (also: AP-47)

### Pipeline at scale: inputs, build time, disk, archives

**AP-49. What is the total first-install time and peak disk per asset class, on the owner's PC and on a minimum-spec PC?**
- Why it matters: Starfield 125 GB on SSD plus FO4 plus work folder plus output plus temporary archives; the owner's 7950X3D hides costs.
- Options: measure the whole 64-cell core, scale by cell count; rerun with a memory cap and fewer cores; a thread-count switch from day one and an output check (TTW uses folder size; our planned per-file hash ledger is stricter).
- Answer by: timed full conversion with peak disk and peak RSS; PC probe (or cloud VM with matching cores).
- Blocks: Launcher, Release.
- Status: open; precedent added (wave 2): TTW's installer takes about 40 minutes on a Ryzen 5 5600X, "several hours or even longer" on slower CPUs, mostly in audio encoding, and writes 17 GB (**verified**); so budget tens of minutes to hours, dominated by voice and textures (**supported hypothesis**). [asset-conversion W2-1] (also: asset-conversion Q13; versions-performance Q15, Q16)

**AP-52. Which FO4 data versions does the converter accept, and how does it detect them from data alone?**
- Why it matters: most players have 1.11.240; `ba2.py` accepts only header versions 1 to 3, so it cannot read a current unmodified install's next-gen archives.
- Options: hash `.esm` files per known version (TTW model); read BA2 header versions and accept `{1, 7, 8}` with the v1 layout in `src/fo4sf/ba2.py` (line 59); check for Anniversary CC files; support all versions with fixtures, or normalise inputs.
- Answer by: a synthetic v7/v8 fixture unittest (offline); first 8 bytes of each `Fallout4 - *.ba2` and `cc*.ba2` on a current install (minutes); a record and archive diff between 1.10.163 and 1.11.240; PC probe then owner decision.
- Blocks: Launcher, New game, Release.
- Status: narrowed (wave 2): next-gen archives are versions 7 and 8 (**verified**); xEdit and OpenMW parse them exactly like v1 (**verified**), so only the version number changed (**supported hypothesis**); the reader fix is one line, not a format project. [Update 2026-10-19: fix on PR #394, not merged: draft PR #394 at 1825141 reads FO4 BA2 v7 and v8 with the v1 layout, with a synthetic test; detect lists archive versions and duplicate archive names; 368da05 makes detect refuse sTestFile INIs and report loose files in My Games Data.] Open: which vanilla archives are 7 and which 8, and whether the Anniversary update changed anything beyond that. [versions-performance W2-1; starfield-toolchain W2-6] (also: asset-conversion Q15; versions-performance Q7, Q8, Q9, Q31)

**AP-54. Are the about 150 Anniversary Creation Club files, and GOG or Microsoft Store FO4 installs, valid asset sources?**
- Why it matters: they change what "the player's FO4" means and widen the asset surface.
- Options: ignore `cc*` files; opt in per file; Steam only.
- Answer by: owner decision; file listings and hashes from GOG and Game Pass installs (community contact).
- Blocks: Launcher, Release.
- Status: open. (also: versions-performance Q10, Q11)

**AP-55. How are outputs packed under engine limits: archive count, size per archive, auto-loaded archive names?**
- Why it matters: 256 active BA2s shared with the player's mods; 4,095 MB per archive; whether one archive can pass 4 GiB is unresolved; 64 cells need about 8.5 GiB.
- Options: one ESM with `- Main.ba2` and `- Textures.ba2`; numbered archives (`- Main01.ba2`, unresolved); BA2 Limit Fix (SFSE).
- Answer by: a synthetic 5 GiB archive and two numbered archives loaded in game; archive count with Starfield Engine Fixes' counter; PC probe.
- Blocks: All interiors, World, Launcher.
- Status: narrowed (wave 2): BA2 offsets are 64-bit, so the format does not stop at 4 GiB (**verified**); FO4 users report 9.5 GB and 14.7 GB archives loading (user reports, FO4 only). Whether Starfield's engine reads past 4 GiB is **unresolved**; keep splitting at 4,095 MB until the probe. Medium masters hold at most 65,536 ObjectIDs over 256 slots (**verified**), so world plugins must be full masters. [starfield-toolchain W2-5, W2-6; versions-performance W2-3] (also: starfield-toolchain Q14; versions-performance Q4, Q17)

**AP-56. Does the build cache key include the Starfield runtime and Starfield.esm hash?**
- Why it matters: a Starfield patch can change records we override or vanilla assets we reference.
- Options: full Starfield.esm hash; only overridden records and referenced paths.
- Answer by: offline design.
- Blocks: Launcher.
- Status: open. (also: versions-performance Q14)

### Tool dependencies and licences

**AP-50. Which steps may depend on Bethesda or third-party tools installed on the player's PC, and is each acceptable?**
- Why it matters: CK is settled; Wwise and 3ds Max are not; each adds install friction and per-patch risk.
- Options: CK for FaceFX, navmesh, object LOD (`-MockWorldSpaceLOD` [Correction 2026-10-19: existence ~~**unresolved (sources conflict)**~~] [Correction 2026-10-19: **verified (Starfield CK, job 20)**]), face bakes (GUI only so far [Update 2026-10-19: job 20 found "-ExportFaceGenData:(ESMFilename) (TESNPCExportFaceDataMode) [Platform]"; bake or export only is **unresolved**, AP-09]) and Archive2; Wwise for `.wem`; avoid 3ds Max.
- Answer by: owner decision after AP-30 and AP-40.
- Blocks: Launcher, Release, People and story.
- Status: open (wave 2: Wwise is a non-Bethesda licence gate with free non-commercial terms whose fit for per-player conversion is **unresolved**; CK LOD has a command-line switch). (also: asset-conversion Q35; starfield-toolchain Q11, Q25)

**AP-51. Which external binaries may the launcher bundle, and which must the player fetch?**
- Why it matters: GitHub then Nexus release must meet each licence.
- Options (licences as found): texconv (MIT, **supported hypothesis**), CALUMI (LGPL-3), HavokLib (GPL-3), Geometry Bridge (MIT), Mutagen and Spriggit (GPL-3), Cathedral Assets Optimizer (MPL-2.0, **verified**; reference only, no Starfield support), vgmstream and ffmpeg (not read), Wwise (not bundlable, player installs under own account, **supported hypothesis**; no Audiokinetic text on redistributing WwiseConsole found), CK (player installs). Nexus "no conversion to other games" clauses (Void SFG Bridge, Animation IO) versus their GitHub licences.
- Answer by: a licence table (offline research), then owner decision.
- Blocks: Release, Launcher.
- Status: narrowed (wave 2): CAO licence read (MPL-2.0); Wwise cannot be bundled and nothing found allows redistributing WwiseConsole (**unresolved** pending the full EULA). [asset-conversion W2-2; legal-policy W2-B] (also: asset-conversion Q14, Q31; starfield-toolchain Q26)

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

- **AP-50 player-installed tools:** recommend CK required, Wwise only if AP-30 shows free headless use is allowed, 3ds Max never. Why: CK is already allowed; Wwise is the only verified encoder. Wave 2: the free terms are non-commercial and capped at 200 SoundBank media assets, so ask Audiokinetic in writing before committing (legal-policy W2-B).
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
4. **Read Geometry Bridge `.dat` code and Starfield Blender Extension constraint code; dump one vanilla FaceGeom NIF read-only and compare with our NIF writer's output.** Feeds AP-04, AP-11.
5. **Read one FO4 `.bto` against a vanilla `_lod_0.nif`; xEdit read of a vanilla overlay's layers and LOD flags.** Feeds AP-47, AP-59. (The precombine scan is done: no such records, AP-48. [Correction 2026-10-19: but the Starfield CK has "Generate Precombined Visibility" GUI actions (interiors.md T9); what they write is **unresolved**, AP-48.])
5a. **Synthetic BA2 v7/v8 fixture unittest and the one-line `ba2.py` fix.** Feeds AP-52. [Update 2026-10-19: done on draft PR #394 (1825141), not merged.]
5b. **SFME export of a vanilla material, diffed with our clone.** Closes AP-26.
5c. **Written question to Audiokinetic** on per-player batch conversion and the 200-asset limit (owner sends; outreach is the owner's job). Feeds AP-30, AP-50.

PC read-only probes:

6. **Strings scan of CreationKit.exe** for FaceFX and face-bake switches (like the navmesh ~~and `-MockWorldSpaceLOD`~~ ones). Feeds AP-09, AP-40, AP-50. [Correction 2026-10-19: done as job 18: it shows `-CompileFaceFXAnims`, `-GenerateMeshLOD*` and `-GenerateSEQ`, no `-GenerateLips` ~~and no `-MockWorldSpaceLOD`; a wide-string search is still needed for the latter~~ [Correction 2026-10-19: the dump printed only strings matching its default patterns (Generate, Compile, Lip, AnimInfo, -Convert, -Build), so it had filtered `-MockWorldSpaceLOD` out; job 20 (read-only, patterns Mock, WorldSpaceLOD and "Should be -") found it, **verified (Starfield CK, job 20)**, and also "-ExportFaceGenData:(ESMFilename) (TESNPCExportFaceDataMode) [Platform]" (bake or export only is **unresolved**)]. Job 19 queued for LipGenerator's usage text.]
7. **First 8 bytes of every `Fallout4 - *.ba2`** on a current install, plus `.esm` hashes. Closes the BA2 part of AP-52; feeds AP-54.
8. **Read-only dump of both games' `skeleton.nif`.** Closes AP-06.

PC probes that write test data (owner time):

9. **1,000-line FaceFX run** from a space-free staging folder: time it, rerun to test resume, compile 20 lines twice for hashes, try WAV-only. Closes AP-40 (timing), AP-41, AP-42, AP-43; feeds AP-44.
10. **WwiseConsole on `Starfield.wproj` without the GUI.** Feeds AP-30, AP-50.
11. **Whole-core build with peak disk, RSS and time,** then with a memory cap. Closes AP-49.
12. **`-MockWorldSpaceLOD` on a 4-cell test worldspace:** [Correction 2026-10-19: first settle whether the switch exists: ~~a wide-string search of CreationKit.exe or running it on a test worldspace~~ [Correction 2026-10-19: settled, **verified (Starfield CK, job 20)**]; then] time, `.esm` acceptance, failed cells; then 64 cells. Feeds AP-47, AP-59.
13. **Synthetic 5 GiB BA2 loaded in game; loose vs v3 texture BA2 load time and stutter.** Closes the engine part of AP-55; closes AP-58.
14. **Frame time, VRAM and RAM at 3 fixed spots,** vanilla vs core vs core-with-LOD. Closes the second half of AP-48.

## Gaps (after wave 2)

- Read the full Wwise EULA: redistribution of WwiseConsole, and whether `convert-external-source` counts toward the 200-asset limit (AP-30, AP-51). Pricing page read in wave 2.
- Find any open-source Wwise Vorbis `.wem` encoder (AP-30).
- Search for a public `.agx` description or editor, and Starfield animation text data or subgraph practice (AP-20, AP-21).
- Purpose of Starfield's `OVIS` "Object Visibility Manager" record (AP-48).
- Starfield draw-call and VRAM profile with a dense modded load (only vanilla VRAM figures found) (AP-48, AP-25).
- Read Nexus article 535 on music replacers (AP-33) and any guide on new WWED events (AP-31).
- Licences of vgmstream, ffmpeg builds, texconv (re-read), Trainwreck and the Starfield Blender Extension (AP-51).
- Whether the CK face bakes can run without the GUI, and the exact run-time fallback for a named NPC with no bake (AP-09, AP-11).
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

Wave 2 (as cited by the findings files):

- https://thebestoftimes.moddinglinked.com/faq.html
- https://thebestoftimes.moddinglinked.com/ttw.html
- https://www.nexusmods.com/skyrimspecialedition/mods/23316
- https://github.com/Guekka/Cathedral-Assets-Optimizer/
- https://stepmodifications.org/wiki/Fallout4:Cathedral_Assets_Optimizer
- https://www.nexusmods.com/starfield/mods/1192?tab=posts
- https://www.nexusmods.com/starfield/mods/12471 , https://www.nexusmods.com/starfield/mods/14825 , https://www.nexusmods.com/starfield/mods/14659 (search listings)
- https://www.nexusmods.com/starfield/mods/5572
- https://www.nexusmods.com/starfield/mods/7834/?tab=posts (snippet)
- https://forums.nexusmods.com/topic/13521838-ck-bugquestion-%E2%80%9Cbake-chargen-mesh-geometry%E2%80%9D-always-crashes-%E2%80%94-is-this-broken-for-everyone/
- https://www.reddit.com/r/starfieldmods/comments/1dp6yv8/npc_edits_having_issues/
- https://steamcommunity.com/sharedfiles/filedetails/?id=3287508493
- https://www.reddit.com/r/CreationKit/comments/1lp64l5/creation_kit_not_generating_facegen_files/
- https://forums.nexusmods.com/topic/13526765-generating-facegen-data/
- https://modding.wiki/en/starfield/developers/tutorials/creatingworldspacelod
- https://forums.nexusmods.com/topic/13497519-how-to-create-lod/
- https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985
- https://dyndolod.info/Help/xLODGen
- https://github.com/maximusmaxy/SFME , https://www.nexusmods.com/starfield/mods/7830
- https://www.nexusmods.com/starfield/mods/17879
- https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/ (wbDefinitionsSF1.pas, wbDefinitionsFO4.pas, wbImplementation.pas, wbInterface.pas, wbBSArchive.pas)
- https://forums.nexusmods.com/topic/11091353-ba2-size-limits-and-splitting-textures-between-ba2s
- https://www.nexusmods.com/fallout4/articles/5844
- https://gitlab.com/OpenMW/openmw/-/merge_requests/4055
- https://github.com/HansKristian-Work/vkd3d-proton/pull/1694
- https://www.audiokinetic.com/en/wwise/pricing/
- https://docs.flightsimulator.com/html/Asset_Creation/Sounds/Wwise_Licence_Information.htm
- https://cdprojektred.atlassian.net/wiki/spaces/W3REDkit/pages/6327958/HOW-TO+Get+a+Wwise+license
