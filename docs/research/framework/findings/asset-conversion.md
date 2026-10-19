# Asset conversion at full-game scale (FO4 to Starfield)

Author: asset-conversion research agent (Claude), 2026-10-19. Labels: **verified** (read in a linked source or a repo
file), **supported hypothesis**, **unresolved**. Research limits this session: the shared web-search budget ran out
partway through and WebFetch was then rate-limited (HTTP 429), so the TTW FAQ (taleoftwowastelands.com/faq) and the
Cathedral Assets Optimizer README (github.com/Guekka/Cathedral_Assets_Optimizer) could **not** be read. The precedent
section is therefore marked as hypothesis from prior knowledge. Questions on facegen, precombines and LOD tooling
that need web sources are marked for follow-up.

## Bottom line

The project has already solved the hardest *static* asset problems itself, and those solutions are in-game
verified: its own NIF/.mesh writer (S1), a `.mat` cloner with texture remapping (S3), and transplanting FO4's
compressed-mesh collision into Starfield Havok tagfiles (`meshcollision.py`). The remaining full-game gaps fall into
three kinds. (1) **Scale and robustness work on paths that exist**: LOD slots, the u16 index limit, emissive and swap
materials, precombines, object LOD. (2) **Paths that need Bethesda's own tooling on the player's PC**: lip sync (the
Creation Kit's embedded FaceFX compiler is the only documented `.ffxanim` route), sound (Wwise authoring
2021.1.14.8108 with the `Starfield.wproj` the CK installs), and possibly object LOD and precombines (CK generation). The
launcher must therefore drive the CK (and maybe Wwise) unattended, or find an open replacement for each.
(3) **Animation and behaviour**, where FO4 `.hkx` can be decoded with open code (HavokLib, GPL-3) and Starfield `.af`
can be written with CALUMI (LGPL-3, alpha, compression "planned"), but Starfield's `.agx` graph format has no public
specification. Whole FO4 behaviour graphs cannot be ported. The practical route is Starfield graphs with FO4 clips
retargeted into them, or SFSE glTF players (NAF, SAF, OSF) for scenes and idles. The biggest strategic question is
how much of the pipeline may depend on tools the player has to install (CK: settled yes; Wwise, 3ds Max: open), and
whether each such step can run headless.

## Findings

### 1. Meshes

- **The project's writer is the reference implementation now** (**verified**, repo). S1 reproduces vanilla `.mesh`
  byte-for-byte on 3,000 of 3,000 samples, the meshlet rule on 4,000 of 4,000, and `BSGeometry` on 20,224 of 20,224.
  At scale, 648,358 placed objects and 4,346 models in the current builds (docs/ROADMAP.md, JOURNAL integ_1017).
  Outside tools are references or oracles, not dependencies.
- **Outside Starfield mesh tools as of Oct 2026** (all **verified** on their pages):
  - *Starfield Geometry Bridge* (SesamePaste): Blender plugin for import/export of `.nif`, `.mesh` and morph `.dat`
    (as shape keys), cloth physics export and basic `.mat` export via texconv. MIT licensed, source on GitHub. It
    advises fewer than 65,536 vertices per model.
    [Nexus 4360](https://nexusmods.com/starfield/mods/4360)
  - *Starfield Blender Extension* (MrTrilB, 1.6.0 beta, Blender 5.0+): a rework of Geometry Bridge covering mesh,
    NIF, material, **collision (collider creation, collision layers, rigidbody and constraint controls)**, animation
    export configuration, morphs and Havok. Source on GitHub (MrTrilB/StarfieldBlenderExtension); no license named
    on the page. Credits "Bethesda Game Studios and Zenimax/BGS tooling contributors".
    [Nexus 16979](https://www.nexusmods.com/starfield/mods/16979)
  - *Void SFG Bridge* (VoidLightCreations, 1.8.10, 20 Sep 2026): a Blender 5.1.1+ fork of Geometry Bridge with
    skeleton, vertex-weight and skin workflows and "Morph Genesis" (transfers donor skinning to fitted targets).
    Explicitly no `.af` export. Its permissions **forbid converting it to work on other games**.
    [Nexus 17968](https://www.nexusmods.com/starfield/mods/17968)
  - *fo76utils NifSkope* 2.0.dev11 (30 Dec 2025): Starfield 1.15.214 updates; a Create Convex Shape spell with
    meshoptimizer simplification or CoACD decomposition; glb import and export; a meshoptimizer simplification spell
    for BSTriShape. No release note mentions an FO4-to-BSGeometry conversion spell.
    [releases](https://github.com/fo76utils/nifskope/releases)
  - Community practice for old-format shapes is to export through Blender with Geometry Bridge, not to convert
    inside NifSkope. [forum thread](https://forums.nexusmods.com/topic/13491770-nifskope-how-to-convert-nitrishape-into-bsgeometry-mesh-please-help)
- **No public FO4-to-Starfield bulk mesh converter was found** (**supported hypothesis**: none of the tool pages
  read mentions FO4 input, and the search ended early).
- **Index width limit.** `.mesh` triangles are u16 x3 (**verified**, FORMAT-GAP/S1), so one `.mesh` addresses at most
  65,536 vertices. FO4 shapes larger than that must be split across `BSGeometry` blocks. Whether any vanilla FO4
  shape exceeds this, and whether the writer splits or refuses, is **unresolved** (not found in S1).
- **LOD slots 1 to 3** of `BSGeometry.Meshes[4]` are unused by the converter (S1 "Not covered"). The meshoptimizer
  spell in NifSkope shows the simplification algorithm the vanilla workflow probably uses. Whether Starfield needs
  mesh LODs for performance at 648k+ references is **unresolved**.
- **Skinned actor meshes.** FO4 has 3,588 NIFs with 16,350 skinned shapes, 15,325 of them `BSSubIndexTriShape`
  (**verified**, research-log 2026-10-10). The repo reads FO4 skin (`fo4skin.py`) and bakes posed props, but
  writing **Starfield skinned** geometry (skin blocks, bone indices in `.mesh`, segment/partition replacement) is not
  done (ACTOR-MILESTONE step 2). The Void SFG Bridge and Starfield Blender Extension pages show that a skinned
  Starfield writer exists in community code (**verified** that they claim it, **unresolved** how complete it is).

### 2. Collision

- **Already done** (**verified**, repo): FO4 hk_2014 packfiles are decoded (`hkpackfile.py`, `fo4collision.py`,
  `fo4_compounds.py`). Compressed-mesh shapes are transplanted into a template Starfield tagfile (`meshcollision.py`),
  with convex, box, sphere and compound read-back (`sfbodies.py`). Single dynamic bodies work, and multi-body systems
  are merged into one rigid body (physics-conversion.md). Constraints are not done.
- **Bethesda's official collision path is 3ds Max 2021** with Bethesda ArtTools
  (`Starfield\Tools\ArtTools\BGS_Starfield_ArtTools_a.b.c.d.exe`, shipped with the CK), "Havok Content Tools >
  Physics > Create Rigid Body with Proxy(s)", the BGS CollisionGroup utility and "Open Bethesda FBX export"
  (**verified**: [collision guide](https://starfieldwiki.net/wiki/Starfield_Mod:Adding_Collision_with_3ds_Max_2021),
  [3ds Max setup](https://starfieldwiki.net/wiki/Starfield_Mod:Setting_up_3ds_Max_2021_for_Starfield)). Neither page
  says where Havok Content Tools come from or how FBX becomes NIF. 3ds Max is paid software and unsuitable as a
  launcher dependency (**supported hypothesis**).
- **New reference for constraints:** the Starfield Blender Extension claims "rigidbody and constraint controls"
  (**verified** claim, source on GitHub). Its code is a candidate for decoding the vanilla Starfield constraint blob
  that physics-conversion.md §3.4 names as the next step (**supported hypothesis**).

### 3. Animation and behaviour graphs

- **FO4 side.** `.hkx` animations are Havok 2014 (hk_2014.1.0-r1), 64-bit packfiles (**verified**, repo
  `hkpackfile.py` header and FO4 Animation Kit). The community's tooling assumes Havok Content Tools 2014 and 3ds Max:
  64-bit HKX is converted to 32-bit before hkx2fbx
  ([F4AK](https://www.nexusmods.com/fallout4/mods/16694),
  [furniture tutorial](https://www.nexusmods.com/fallout4/mods/41209)). An open alternative exists:
  **PredatorCZ HavokLib** reads packfiles from Havok 5.0 to 2017 on x64, including `hkaSplineCompressedAnimation` and
  `hkaSkeleton`. It is GPL-3.0. It does **not** load tagfiles (so it does not help on the Starfield side), and its
  binary export is experimental (**verified**, [HavokLib](https://github.com/PredatorCZ/HavokLib)). Sebbo's 3ds Max
  import script already retargets Ghoul, Super Mutant and FO76 human clips onto the FO4 player rig through HavokMax
  ([Nexus 69177](https://nexusmods.com/fallout4/mods/69177)), a precedent for cross-rig retargeting.
- **Starfield side.** `.af` (clips), `.afx` (XML tag-to-file descriptors), `.rig` (bone table), `.agx` (graphs in
  `AnimTextData\Tables\Graphs`) (**verified**, repo FORMAT-GAP and WP-doors-research). The project already writes
  `.rig` and `.af` for doors through **CALUMI.Animation** (**verified**, decisions.md, JOURNAL). CALUMI is LGPL-3,
  self-described alpha ("not in a state that is considered fool proof"), with **compression** and **full .af/.rig
  decoding** listed as planned (**verified**, [CALUMI](https://github.com/Calaverah/CALUMI.Animation)). The Blender
  front-end *Animation IO* (Deveris256, Calaverah, Jojo; sf_animation_io) imports and exports `.af` and `.rig`
  ([Nexus 16184](https://www.nexusmods.com/starfield/mods/16184)). Its Nexus permissions say it may not be converted
  to work on other games. That restriction is on the Nexus file, and the GitHub library carries its own LGPL license.
  Which governs our use is an owner question.
- **Behaviour graphs (`.agx`).** No public specification, editor or converter was found (**unresolved**; the search
  ended early). The repo shows vanilla doors share a few graphs (`SimpleOpenClose01.agx`, 215 doors), with motion
  carried by each object's own rig and clips (**verified**, WP-doors-research). FO4 behaviour graphs are Havok
  Behavior `.hkx` (**supported hypothesis**; the FO4 CK wiki's Subgraphs page covers subgraph data, not read here).
  **Port FO4 graphs** is not realistic. **Retarget FO4 clips into Starfield graphs** depends on whether graphs can
  reference new clips by subgraph or animation text data (**unresolved**).
- **Runtime-player route (SFSE).** Three SFSE frameworks play external clips on actors:
  - NAF SF (glTF/GLB, GPL-3; [Nexus 7360](https://www.nexusmods.com/starfield/mods/7360));
  - SAF 6.0 (glb/gltf/fbx/.saf, bone aliases, Papyrus API, blend variables and phase events;
    [Nexus 16124](https://www.nexusmods.com/starfield/mods/16124));
  - OSF Animation 1.4.0 (synced multi-actor scenes from JSON plus GLB/.af clips, camera, world anchoring; built on
    CALUMI and ozz-animation; [Nexus 17457](https://www.nexusmods.com/starfield/mods/17457)).

  So FO4 idles, furniture, scenes and sync kills could play without writing `.agx` at all, at the cost of an SFSE
  dependency (which the settled decisions allow) (**verified** capabilities, **supported hypothesis** that they suit
  AI-driven idles).
- **Face animation.** Starfield ships about 278k `.ffxanim` files (FORMAT-GAP). See §6.

### 4. Textures and materials

- Already established and not repeated here: S3 (BC1/BC5/BC4 mapping, in game) and
  research/engine-mechanics/materials-textures-lighting.md (emissive, MSWP to LMSW, PDCL/MTPT, TXST).
- **New:** Geometry Bridge's basic `.mat` export needs texconv, and NifSkope's 2025 notes say its new extraction
  buttons "do not support extracting Starfield materials" (compiled CDB) but the Extract Resource Files spell was
  fixed for them (**verified**, releases page). The fo76utils fork therefore reads `materialsbeta.cdb`, a candidate
  oracle for comparing our loose `.mat` against compiled vanilla materials (**supported hypothesis**).
- **Throughput.** Texture re-encoding is likely the slowest bulk step on the player's PC. FO4 texture count and total
  size are not in the repo measurements read here (**unresolved**; a cheap recon count). texconv is the
  DirectXTex sample, MIT licensed (**supported hypothesis**, not re-read). The repo takes it from xEdit's Edit
  Scripts folder (S3).

### 5. Sound and music

- Starfield sounds sit in `Starfield - WwiseSounds01..05.ba2` as about 26k `.wem` plus a `soundbanksinfo.json` that
  lists every `.wem` with hints about its use (**verified**,
  [Nexus article 641](https://www.nexusmods.com/starfield/articles/641)). Replacing a sound means a `.wem` with the
  same numeric id under `Data/Sound/SoundBanks`. Some sounds use several ids, and Wwise conversion should use
  **Vorbis** (some encodings are not recognised and PCM is about 10x too big)
  (**verified** article, comments **supported hypothesis**;
  [Nexus article 173](https://www.nexusmods.com/starfield/articles/173)).
- **Wwise version is 2021.1.14.8108.** The CK install puts a Wwise project at
  `Starfield/Content/Tools/wwise/Starfield/Starfield.wproj`. Wwise "Convert All Audio Files" writes `.wem` to a
  `.cache/<platform>` folder (**verified**,
  [Xbox porting guide](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox),
  [Nexus 12561](https://www.nexusmods.com/starfield/mods/12561)).
- **Adding new non-voice sounds** (new `WWED` events and new banks rather than replacing ids): no public guide was
  found, and one commenter could not get new sounds to load (**unresolved**). This is the key gap for porting FO4's
  5,476 SNDR records (FORMAT-GAP).
- FO4 sources: 7,380 `.xwm` and loose `.wav` (FORMAT-GAP). The xWMA decoder route (for example ffmpeg) is a
  **supported hypothesis**, not tested. vgmstream decodes `.wem` (**verified**, articles 641 and 173), which gives a
  round-trip oracle.
- **Licensing.** Whether a player may install Wwise authoring for free to run conversion on their own PC, and whether
  a launcher may automate it, is **unresolved** (Audiokinetic terms not read). No open-source Wwise Vorbis `.wem`
  *encoder* is known (**unresolved**).

### 6. Voice and lip sync

- **Voice lines are loose files, not banks.** The path is
  `Data\Sound\Voice\<Plugin>.esm\<VoiceType>\<numbered files>`, and each line needs **both** `.wav` (for lip sync
  generation) and `.wem` (for playback). No spaces are allowed in names, and the body type must match the voice
  type (**verified**,
  [Audio File Conversion](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion),
  [lip sync guide, Nexus 12576](https://nexusmods.com/starfield/mods/12576)). This parallels FO4's layout, so voice
  needs no bank generation (**supported hypothesis**).
- **Lip sync is produced only by the CK's embedded FaceFX.** Audio menu > Run FaceFX Compiler > pick master >
  Compile. It scans all dialogue topics, writes `.animset`, then `.ffxanim` into the voice folder, and logs progress
  to `ffxc_00.log` (it can look stalled) (**verified**, same sources). FaceFX staff say the tool is "embedded in the
  Starfield Creation Kit" and refer support to Bethesda. One user reports case and space sensitivity in plugin names
  (**verified**, [facefx.com/node/4600](https://facefx.com/node/4600)).
- FO4 `.fuz` = xWMA audio + FO4 `.lip` (RISKS.md). FO4 `.lip` cannot be converted into `.ffxanim`, so our pipeline
  discards `.lip` and regenerates from `.wav` (**supported hypothesis**: no converter found, formats differ). Scale:
  122,857 FO4 `.fuz` (FORMAT-GAP) through one CK compile run. Whether it runs headless or from the command line, and
  how long it takes, is **unresolved**.
- The dialogue (DIAL/INFO) must exist in the plugin loaded in the CK for the compiler to find lines (**verified**:
  "scans all dialogue topics"), so voice conversion follows WP-17's record work.

### 7. Facegen

- FO4: per-NPC facegen `.nif` + `.tri`. Starfield: `BSFaceGenNiNode` + morph `.dat` (`MRPH`) (**verified**,
  FORMAT-GAP). Geometry Bridge imports and exports morph `.dat` as Blender shape keys (**verified**, Nexus 4360),
  which is the only public reader/writer reference found. Whether a Starfield NPC needs precomputed face assets or
  generates the face at runtime from NPC record morph values is **unresolved** (web search exhausted; follow-up).
  Today's plan uses Starfield face stand-ins (ROADMAP B2).

### 8. LOD and precombines

- Object LOD: the repo's Grok note already establishes Starfield's `lodsettings/*.lod` (20 bytes), generated
  `meshes/lod/generated/*_lod_{0-3}.nif`, `distantlod/lodruntimedb.bgsdb` and the plan to trial CK generation
  (docs/terrain/object-lod.md). Not repeated. Whether xLODGen or another third-party generator supports Starfield
  object LOD is **unresolved** (follow-up search).
- Precombines: FO4 has 95,856 precombined NIFs plus previs (**verified**, research-log). The port places individual
  references (648,358 exterior objects) and uses FO4 precombined *physics* only as evidence for transforms
  (decisions.md). Whether Starfield uses precombines or previs for exteriors, and whether CK2 can generate them for a
  plugin's cells, is **unresolved** here. It matters for draw calls at full-map scale.

## Precedents and what they teach us

All from prior knowledge; their pages could not be read this session, so all are **supported hypothesis**.

- **Tale of Two Wastelands** (FO3 into New Vegas): an installer reads the player's own FO3 and NV, transcodes
  audio, repacks BSAs and applies binary patches to Bethesda files, so nothing copyrighted ships. It is the closest
  model for our launcher's legal shape, and it is highly automated because both games share an engine.
  *Lesson:* checksum-verified inputs, deterministic patches and long one-time install runs are acceptable to players.
- **Cathedral Assets Optimizer** (Skyrim LE to SE): bulk automatic mesh, texture and BSA conversion between two
  versions of one engine. *Lesson:* automation is near-total when formats are close, and per-asset exceptions get
  a report rather than a crash.
- **Skyblivion / Skywind** (Oblivion and Morrowind into Skyrim): record conversion was partly automated (Skyblivion
  had an ESM/script converter), but assets were largely **remade by hand** over more than a decade, partly for
  quality and partly because redistribution of converted assets is not allowed. *Lesson:* the hand-made route does not
  scale to "full game, breadth first", and our local-conversion model is what lets us avoid it.
- **Fallout London** (FO4): original assets, so it is not a conversion precedent; its installer is the owner's UI
  model (ROADMAP C1).
- **Capital Wasteland / Fallout 3 in FO4 efforts**: manual remakes with long timelines (**unresolved** status).
- The common lesson is that **cross-generation automated conversion with local build has no complete precedent**.
  The nearest (TTW, CAO) are same-engine. Our verified wins on meshes, materials and collision are already beyond
  what those projects needed, and voice, sound and animation are where no precedent helps.

## Risks

1. **CK-only steps cannot be automated** (lip sync, possibly LOD and precombines). Likelihood medium-high: the
   FaceFX compiler is a menu action with a log and no documented command line. If it needs GUI driving, the
   launcher needs input automation, which is fragile. Mitigation: probe for CK command-line switches on the PC.
2. **Wwise dependency for sound.** High likelihood it is needed for new `.wem`. Licence and installer friction for
   players are unknown. New-event authoring is undocumented, so FO4 SFX may be limited to replacing Starfield ids
   (wrong scope: it changes Starfield's own sounds) unless WWED and bank generation is solved.
3. **Behaviour graphs opaque.** High likelihood we cannot author `.agx` before a spec appears. Mitigation: Starfield
   graphs plus retargeted clips, or SFSE glTF players.
4. **Alpha libraries.** CALUMI has no compression yet, so FO4 animations as uncompressed `.af` may bloat. Its API
   may change. Medium.
5. **License and permission mismatches.** Nexus "no conversion to other games" clauses (Void SFG Bridge, Animation
   IO) versus GitHub licences, and HavokLib's GPL-3 for anything linked into our tool. Our tool is GPL-noticed for
   Mutagen, so GPL-3 is probably fine. Medium: needs an owner call before any linking.
6. **Throughput on the player's PC.** Textures, 122k voice lines, a CK FaceFX pass and 200k NIFs could make
   first-install time hours long. Unknown until measured. Medium.
7. **Draw calls without precombines** at full-map scale. Unknown. Medium; the Phase A walk had no crash, but
   performance was not measured.
8. **Game updates** shift NIF BS versions (173 to 175 seen) and CDB layout. NifSkope tracked a 1.15.214 change.
   Medium-low per patch, certain over time.

## Questions for the framework

### New game (Vault 111 start)
1. **Which assets does the Vault 111 start actually need that are not yet converted?** The prologue's skinned
   NPCs (Nate/Nora's spouse, Shaun, Vault-Tec rep), cryo pods with animated doors and the cryo "freeze" effect
   materials. *Why:* the first phase must not wait on actor skinning. *Options:* stand-in Starfield actors; static
   posed actors (`placed_pose.py` already poses skinned props). *Evidence:* a census of Vault 111 refs by asset class
   (skinned, effect material, animated). *Who:* offline research (repo exports).
2. **Do Vault 111's effect materials (frost, glow, cryo glass) need the emissive `.mat` path before Phase 1 ships?**
   *Why:* emissive and animated materials are not done (materials note). *Evidence:* list vanilla emissive `.mat`
   templates in ContentResources.zip; one in-game test. *Who:* PC probe.
3. **Is a silent, no-lip-sync opening acceptable, or does the spouse's voiced intro need the FaceFX pipeline in
   Phase 1?** *Why:* lip sync needs the CK compile (§6). *Options:* subtitled silent lines (ROADMAP B2 stand-in),
   audio only without lips, full pipeline. *Who:* owner decision.

### Door animations
4. **Can CALUMI-written door clips cover every FO4 door family, or do some need compression or features CALUMI
   lacks?** *Why:* CALUMI lists compression and full decoding as planned. *Evidence:* convert every FO4 DOOR model's
   Open/Close and report clip sizes against vanilla `.af` sizes. *Who:* offline.
5. **Which FO4 door sounds map to Starfield WWED events?** *Why:* doors without open/close audio feel broken, and new
   events are undocumented. *Options:* nearest vanilla Starfield door event per FO4 SNDR category; replace-by-id
   (unacceptable, it changes vanilla). *Evidence:* match soundbanksinfo.json door entries to FO4 door SNDR. *Who:*
   offline.

### All interiors
6. **Does the writer split shapes beyond 65,536 vertices, and do any FO4 interior meshes hit the limit?** *Why:* u16
   indices in `.mesh`. *Evidence:* a scan of max vertex count per FO4 shape (cheap with `nif.py`). *Who:* offline.
7. **Do interiors need FO4 precombines rebuilt, or is per-reference placement fast enough?** *Why:* FO4 relies on
   95,856 precombined NIFs plus previs to stay playable. *Evidence:* frame-time and draw-call capture in the densest
   converted interior (Diamond City market, the Institute) versus a vanilla Starfield city interior. *Who:* PC probe.
8. **Should the converter fill `BSGeometry` LOD slots 1 to 3 with simplified meshes?** *Why:* Starfield likely uses
   them for distance and shadow LOD. *Options:* meshoptimizer (as NifSkope does), none. *Evidence:* the share of
   vanilla meshes with LOD slots filled; an in-game frame-time A/B. *Who:* offline plus PC probe.
9. **Which FO4 effect, animated and swap materials appear in interiors, by count?** *Why:* the materials note lists
   them as not done. A count sets priority. *Evidence:* census of `.bgem` with glow or animation and MSWP/XMSP use per
   interior. *Who:* offline.
10. **Can interior movable-clutter collision use FO4's own bodies for all 961 MSTT bases, and what fails?** This
    extends physics-conversion.md §4.1 for interiors. *Who:* offline build report.

### Launcher
11. **Can the CK's FaceFX compiler (and any other CK step: LOD, precombines, `.mat` to CDB) run unattended from the
    command line?** *Why:* the launcher must not need a human in the CK. *Options:* documented CK switches (unknown),
    GUI automation (fragile), skip lip sync. *Evidence:* list the CK executable's command-line switches; try one
    compile with a tiny plugin. *Who:* PC probe.
12. **Is Wwise 2021.1.14.8108 authoring on the player's PC acceptable (licence, download size, login), and can
    WwiseConsole convert headless?** *Why:* the only verified `.wem` encoder. *Evidence:* Audiokinetic licence terms;
    whether the CK's `Starfield.wproj` converts without the GUI. *Who:* offline research plus PC probe.
13. **What is the total first-install conversion time and disk footprint on a typical PC, broken down by asset
    class?** *Why:* TTW-style installs are tolerated, but only within limits. *Evidence:* timed full conversion
    (meshes, textures, collision, audio, CK passes) with peak disk. *Who:* PC probe.
14. **Which external binaries does the launcher need the player to have, and which may it bundle?** texconv (MIT,
    bundlable?), CALUMI (LGPL-3 DLL, bundlable with notice), HavokLib (GPL-3), vgmstream, ffmpeg, Wwise (not
    bundlable), CK (player installs). *Who:* owner decision after a licence table (offline).
15. **How does the launcher verify input files (FO4 and DLC versions, Starfield version) before converting?** *Why:*
    BS 173 vs 175 and CDB changes per patch. *Options:* hash tables per known version (TTW model), version-tolerant
    readers. *Who:* offline design.

### World and planet
16. **Does Starfield object LOD for the Commonwealth come from the CK, a third-party generator, or our own writer?**
    *Why:* nothing is visible beyond loaded cells (ROADMAP). *Evidence:* the CK object-LOD trial planned in
    object-lod.md; a search for xLODGen Starfield support. *Who:* PC probe plus offline research.
17. **Can FO4's `.bto` object-LOD meshes be converted directly as stand-ins for generated Starfield `_lod_N` NIFs?**
    *Why:* they already exist for the whole map and could skip a generator. *Evidence:* read one `.bto` and compare
    with a vanilla `_lod_0.nif`; test whether `lodruntimedb.bgsdb` must list them. *Who:* offline.
18. **What draws at distance for trees and foliage (FO4 TREE has no Starfield record)?** *Why:* the outdoor look at
    scale. *Who:* offline research (flora.md first).
19. **Which FO4 ambient and region sounds (wind, ambience by region, weather sounds) can map to Starfield biome and
    weather audio events?** *Why:* the planet needs FO4's soundscape, not alien biome audio. *Evidence:* a table of
    FO4 region and weather SNDR versus Starfield WWED event names in soundbanksinfo.json. *Who:* offline.

### People and story
20. **What is the voice pipeline at scale: `.fuz` → xWMA → `.wav` → Wwise `.wem` plus CK FaceFX `.ffxanim`, for about
    122k lines?** *Evidence:* convert ten lines end to end and play one in game with lips (WP-15 acceptance); time it.
    *Who:* PC probe.
21. **How do FO4 voice types and file names map to Starfield's `Sound\Voice\<plugin>\<VoiceType>\<id>` layout, and
    must the body type match the voice type for FO4 NPCs placed on Starfield races?** *Why:* the guide says the body
    type must match. *Who:* offline (FO4 path rule from xEdit) plus PC probe.
22. **Does a Starfield NPC need precomputed facegen assets, or is the face generated at runtime from record
    morphs?** *Why:* it decides whether FO4 facegen `.nif` + `.tri` must become `BSFaceGenNiNode` + `.dat`, or only
    record values. *Evidence:* inspect a vanilla unique NPC's face files versus its NPC_ morph fields; read Geometry
    Bridge's `.dat` code. *Who:* offline research.
23. **Skinned outfits and bodies: write Starfield skin ourselves, or use the community Blender tools as reference
    oracles?** *Options:* our writer (consistent with S1) checked against Void SFG Bridge or Starfield Blender
    Extension output; the Morph Genesis approach for fitting FO4 outfits to Starfield bodies. *Note:* Void SFG Bridge
    forbids conversion to other games, so use it only as a viewer or oracle, if at all. *Who:* offline plus owner on
    permissions.
24. **For FO4 idle, furniture and scene animations, which route: (a) retarget FO4 clips to `.af` in Starfield's
    graphs, or (b) play FO4 clips through an SFSE glTF framework (NAF, SAF, OSF)?** *Why:* `.agx` is opaque. (b)
    needs no graph authoring but adds an SFSE dependency and may not integrate with AI packages. *Evidence:* decode
    one FO4 idle with HavokLib, write glTF, play with SAF on a converted NPC; separately write `.af` with CALUMI and
    try it via a vanilla idle's animation text data. *Who:* offline plus PC probe.
25. **Can new clips be added to vanilla Starfield `.agx` graphs without editing the graph (an animation text data or
    subgraph equivalent)?** *Why:* it decides route (a). *Who:* offline research (community Discords) plus a PC probe.

### Fallout systems
26. **Creature skeletons (deathclaw, mirelurk, super mutant, Mr. Handy) with no Starfield rig: is a new `.rig`
    plus `.af` plus a cloned Starfield creature graph feasible?** *Why:* every creature-heavy quest needs them.
    *Evidence:* write a deathclaw `.rig` with CALUMI and drive it with one retargeted walk; check whether a Starfield
    creature graph accepts a foreign rig. *Who:* PC probe.
27. **Power armor: skinned armor over a Starfield body, a furniture enter/exit animation and HUD.** Which pieces are
    asset conversion (meshes, skin, clips) and which are systems? *Who:* offline scoping.
28. **Pip-Boy screen: FO4's Pip-Boy is a skinned, animated first-person model with a render-to-texture screen.**
    Are first-person `.af` and an animated screen material possible? *Who:* offline research.
29. **Radio and music: FO4 radio stations are `.xwm` music plus DJ voice lines. Can they play as loose `.wem` like
    voice, or do they need music banks and events?** *Evidence:* article 535 (music replacers; not read here) and a
    loose-`.wem` music test. *Who:* offline plus PC probe.
30. **Weapons: first-person weapon animations are FO4 `.hkx` on the FO4 first-person rig.** Map to Starfield weapon
    graphs, or use the effect-sequence trick (Nexus 17294 rotates weapon parts through effect sequences)? *Who:*
    offline.

### Release and community
31. **How do we credit and licence-check every third-party library the converter links or calls (CALUMI LGPL-3,
    HavokLib GPL-3, Geometry Bridge MIT, texconv) against the GitHub, then Nexus, release?** *Who:* owner plus offline
    licence table.
32. **Should we contact CALUMI's author (Calaverah) about compression support, and SesamePaste or MrTrilB about
    constraint and skin layouts?** *Why:* their work overlaps our open items. *Who:* owner (community contact).

### Tooling and testing
33. **What are the offline oracles per asset class?** Meshes: our round trip plus NifSkope. Materials: NifSkope's CDB
    reader. Audio: vgmstream decode of our `.wem`. Clips: CALUMI read-back. Collision: `sfbodies.py`. Which are still
    missing (facegen `.dat`, `.ffxanim`, `.agx`)? *Who:* offline.
34. **Run a full-archive "convert everything, count failures" job per asset class (as physics-conversion.md §4.1
    proposes for movables) before any further feature work?** *Why:* breadth before polish; it gives real failure
    classes. *Who:* Claude build plus offline report.

### Cross-cutting
35. **Which steps depend on Bethesda tools on the player's PC (CK: FaceFX, possibly LOD and precombines; ArtTools
    3ds Max: collision authoring, avoided), and is each acceptable?** *Who:* owner decision after Q11 and Q12.
36. **When the owner adds FO3 and New Vegas, which converters are reusable?** FO3/NV NIFs (BS 34, `NiTriShape`,
    hk_550 bhk collision) differ from FO4, so a second reader feeds the same writers. FO3/NV audio (`.ogg` music,
    `.ogg` and `.lip` voice) changes only the decode step. *Evidence:* list each reader and writer and its game
    coupling. *Who:* offline.

## Corrections

- **docs/RISKS.md** (S1 row and line about mesh writers) calls the Starfield Blender extension closed-source and
  says "a mesh writer was not found". As of Oct 2026: Starfield Geometry Bridge is MIT with source on GitHub and
  exports `.nif` and `.mesh` ([Nexus 4360](https://nexusmods.com/starfield/mods/4360)). The Starfield Blender
  Extension's source is on GitHub ([Nexus 16979](https://www.nexusmods.com/starfield/mods/16979)). This does not
  change S1's result (our own writer is verified), only the risk table's fallback text.
- **research/next-phase/physics-conversion.md** (Sources) says community tooling has "no dynamic-body or ragdoll
  authoring" (about the Havok Physics Editor). The Starfield Blender Extension now claims rigidbody and constraint
  controls ([Nexus 16979](https://www.nexusmods.com/starfield/mods/16979)). This is not a contradiction of that
  tool, but there is a newer reference for the constraint blob decode.

## Sources

- Repo (read-only, main 447ec09): docs/FORMAT-GAP.md, docs/ROADMAP.md, docs/RISKS.md, docs/WORK-PACKAGES.md,
  docs/ACTOR-MILESTONE.md, docs/spikes/S1-mesh-writer.md, S3-materials.md, S6-collision.md, WP-doors-research.md,
  docs/terrain/object-lod.md, docs/ai/research-log.md, docs/ai/decisions.md, src/fo4sf/{hkpackfile, hktagfile,
  fo4collision, fo4skin, fo4_compounds, meshcollision, sfbodies, textures, animation_curves, door_clips}.py.
- /mnt/project-files/research/engine-mechanics/materials-textures-lighting.md;
  /mnt/project-files/research/next-phase/physics-conversion.md.
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Main_Page
- https://www.nexusmods.com/starfield/mods/12561
- https://nexusmods.com/starfield/mods/12576
- https://www.nexusmods.com/starfield/articles/641
- https://www.nexusmods.com/starfield/articles/173
- https://www.nexusmods.com/starfield/articles/535 (found, not read)
- https://facefx.com/node/4600
- https://starfieldwiki.net/wiki/Starfield_Mod:Adding_Collision_with_3ds_Max_2021
- https://starfieldwiki.net/wiki/Starfield_Mod:Setting_up_3ds_Max_2021_for_Starfield
- https://nexusmods.com/starfield/mods/4360
- https://www.nexusmods.com/starfield/mods/16979
- https://www.nexusmods.com/starfield/mods/17968
- https://github.com/fo76utils/nifskope/releases
- https://forums.nexusmods.com/topic/13491770-nifskope-how-to-convert-nitrishape-into-bsgeometry-mesh-please-help
- https://forums.nexusmods.com/topic/13050996-scols-of-static-objects-have-physics-in-the-ck (FO4 only; no Starfield precombine content)
- https://www.nexusmods.com/starfield/mods/16184
- https://github.com/Calaverah/CALUMI.Animation
- https://github.com/deveris256/sf_animation_io
- https://www.nexusmods.com/starfield/mods/17457
- https://www.nexusmods.com/starfield/mods/7360
- https://www.nexusmods.com/starfield/articles/619
- https://www.nexusmods.com/starfield/mods/16124
- https://www.nexusmods.com/starfield/mods/17294
- https://www.nexusmods.com/fallout4/mods/16694
- https://www.nexusmods.com/fallout4/mods/60005
- https://www.nexusmods.com/fallout4/mods/41209
- https://nexusmods.com/fallout4/mods/69177
- https://github.com/PredatorCZ/HavokLib
- https://falloutck.uesp.net/wiki/Subgraphs (found, not read)
- Not readable this session (HTTP 429): https://taleoftwowastelands.com/faq,
  https://github.com/Guekka/Cathedral_Assets_Optimizer

## Wave 2 additions (2026-10-19)

Added by a wave-2 research agent (Claude). Wave-1 text above is unchanged. It fills the pages wave 1 could not read (TTW
FAQ, Cathedral Assets Optimizer) and the facegen follow-up. Labels as above.

### W2-1. TTW installer behaviour (turns the wave-1 precedent row from hypothesis into verified; feeds Q11, Q14, Q35)

- **verified**: the TTW FAQ's "What does the TTW Installer do?" lists: updates Vorbis libraries to 1.3.7; creates or
  edits the Custom INI in My Games\FalloutNV (archive list plus performance settings); **decompresses the BSAs in the
  mod folder (not the originals)**; transcodes sound effects OGG to WAV; transcodes **all voice files to 24 kHz** to
  match New Vegas; fixes some FO3 radio tracks (mono MP3 to WAV to stereo WAV to MP3); moves all MP3s out of BSAs as
  loose files; and "**patches and creates all non-unique assets dynamically from original game files**".
  https://thebestoftimes.moddinglinked.com/faq.html (the taleoftwowastelands.com/faq link now redirects to a mod.pub
  page whose body did not render: https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions)
- **verified**: installer errors "BASS Init or XD3 Input" are answered with "make sure you have both games installed
  with all DLCs and **in English**, run them once"; "xdelta3.dll was not found" means the archive was not extracted
  first, so the installer is an **xdelta3 binary-patch** applier over the original files. It accepts `-threads:1` to
  run slower when CPUs overheat or the installer closes with an NTDLL error; Intel E-cores make it slower.
  Same FAQ.
- **verified**: install guide: the installer writes into an MO2 mod folder the user creates
  (`<MO2>\mods\Tale of Two Wastelands`); "the audio encoding section is very CPU-intensive. It takes about **40 minutes
  on a Ryzen 5 5600x** but could take several hours or even longer on a slower CPU"; the finished folder should be
  **17 GB**, and a smaller folder means a failed install (missing-mesh red diamonds), fixed by reinstalling.
  https://thebestoftimes.moddinglinked.com/ttw.html
- **verified**: updates: delete and reinstall; a new major or minor version needs a new game; patch versions are safe.
  Verifying game files reverts the Vorbis update and the exe patch. Linux support "planned but not near".
  https://thebestoftimes.moddinglinked.com/faq.html
- What this teaches us (**supported hypothesis**): (1) audio transcoding, not patching, dominates install time, which
  matches our expectation that voice (122,857 `.fuz`) plus textures will dominate; budget the launcher in tens of
  minutes to hours and give it a thread-count switch from day one. (2) A size check on the output folder is the
  community's own install validator; our launcher can do better with the planned per-file hash ledger. (3) TTW
  requires English for both games; we have a reason to do better (see W2-4 in people-story.md: FO4/Starfield voice
  languages overlap in EN/FR/DE/ES/JA).

### W2-2. Cathedral Assets Optimizer and other batch texture tools (answers the CAO gap in §4)

- **verified**: the CAO Nexus page says it aims "to automate asset conversion and optimization for Skyrim Special
  Edition, Skyrim Legendary Edition, Fallout 3, Fallout New Vegas, and Fallout 4"; **Starfield is not mentioned**.
  Version field 5.3.15, newest changelog entry a 7.0 beta, page updated 23 March 2026. Features: uncompressed DDS to
  BC7, resize by divider or absolute size (5.0), mipmap generation (5.0), command-line support added in 4.2.4 (current
  state not documented). https://www.nexusmods.com/skyrimspecialedition/mods/23316
- **verified**: the GitHub repo is MPL-2.0, "in-development, experimental", ~1,000 commits, no GitHub releases; it
  credits DirectXTex, nifly, BSArch/libbsarch and hkxcmd. https://github.com/Guekka/Cathedral-Assets-Optimizer/ ,
  https://github.com/Guekka/Cathedral-Assets-Optimizer/releases . STEP's FO4 CAO profile uses Base Profile FO4 with
  "Necessary optimization" and "Generate mipmaps". https://stepmodifications.org/wiki/Fallout4:Cathedral_Assets_Optimizer
- **verified**: Starfield-specific batch texture tools found on Nexus are image-to-DDS converters (Automatic Image to
  DDS Converter, 12471; Encrypteds Universal DDS Texture Converter, 14825, "smart auto-detection"), Material Editor Lite
  (14659, batch conversion "powered by texconv.exe"), and BA2 Upgrader (1192, v1.3.3, Dec 2025), which rewrites texture
  BA2s to **version 3** (LZ4; two compression levels, the Bethesda-like level taking "tens of minutes to several
  hours"). A 2024 comment on 1192 asks for "Cathedral Assets Optimizer"-style downscaling for Starfield, i.e. none
  existed then; a later commenter notes the CK's Archive2 can write v3 directly (DDS + LZ4).
  Search-result listings: https://www.nexusmods.com/starfield/mods/12471 , https://www.nexusmods.com/starfield/mods/14825 ,
  https://www.nexusmods.com/starfield/mods/14659 ; read: https://www.nexusmods.com/starfield/mods/1192?tab=posts
- **supported hypothesis**: there is no CAO equivalent for Starfield; every Starfield tool found wraps texconv. So our
  own texconv-based step (already in the repo, S3) is the norm, and the remaining choices are ours: BC format per
  texture role, whether to downscale 4K FO4 HD textures, and whether to pack into v3 texture BA2s (users report better
  load times and smoother play with v3 and fewer archives; **supported hypothesis**, user reports only).
- New question for the framework: **Do we pack converted textures into Starfield v3 texture BA2s (via Archive2 or our
  own writer) instead of loose files, and must each BA2 be added to `sResourceIndexFileList`?** One BA2 Upgrader user
  says packed loose files need that INI entry. Evidence: load time and stutter, loose vs v3 BA2, same route. Who: PC probe.

### W2-3. Facegen (answers Q22 in part)

- **verified**: Starfield ships per-NPC face geometry `meshes\Actors\Character\FaceGenData\FaceGeom\Starfield.esm\<FormID>.nif`
  and per-NPC face textures under `textures\actors\character\facecustomization\starfield.esm\`; the CK produces them with
  two bakes, "Bake FCT" (Ctrl+F4: ao/color/normal/rough DDS) and "Bake Chargen Mesh Geometry"; structure edits need the
  geometry bake. Full sources and caveats in people-story.md, "Wave 2 additions", W2-2.
- Changes Q22: the answer is "named NPCs: pre-computed (baked) assets keyed by plugin and FormID; templated
  Use-Traits NPCs: no per-NPC bake" (**supported hypothesis**). Our converter then has to either drive the CK bake
  (GUI, per actor, reported crashes) or write FaceGeom NIFs and the four face DDS itself; Geometry Bridge's morph
  `.dat` support (wave 1) is the closest open reference. **unresolved**: the FaceGeom NIF's internal layout
  (likely `BSFaceGenNiNode` per FORMAT-GAP) versus what our NIF writer already emits; a read-only dump of one vanilla
  FaceGeom NIF answers it.

### Wave 2 sources (asset-conversion)

- https://thebestoftimes.moddinglinked.com/faq.html , https://thebestoftimes.moddinglinked.com/ttw.html ,
  https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions (redirect target; body not rendered)
- https://www.nexusmods.com/skyrimspecialedition/mods/23316 , https://github.com/Guekka/Cathedral-Assets-Optimizer/ ,
  https://github.com/Guekka/Cathedral-Assets-Optimizer/releases , https://stepmodifications.org/wiki/Fallout4:Cathedral_Assets_Optimizer
- https://www.nexusmods.com/starfield/mods/1192?tab=posts , https://www.nexusmods.com/starfield/mods/12471 ,
  https://www.nexusmods.com/starfield/mods/14825 , https://www.nexusmods.com/starfield/mods/14659 (last three: search listings only)
- Facegen sources: see people-story.md, "Wave 2 sources (people-story)".
