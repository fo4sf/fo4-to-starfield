# Load doors that open before the trip (phase 2: doors with enter and exit animations)

Author: Claude (cloud), 2026-10-19. Status: **offline prototype, every switch off by default; nothing deployed, nothing
run in game.** Labels as in docs/ai/research-log.md: **verified**, **supported hypothesis**, **unresolved**.

Owner's ask (2026-10-19, roadmap phase 2): doors with their animations working for entering and exiting places.

## What happens today

- Ordinary (non-load) FO4 doors already open in game: the Akila template rig for single hinged leaves, their own rig
  and FO4's keys for multi-part, sliding and lifting doors (docs/spikes/WP-doors-research.md, sliding-doors.md;
  **verified** in game for the hinged path, Hotel Rexford 2026-10-08).
- Every load door is excluded from that: `pipeline.Converter.convert_nif` rigs nothing with `load_door` set
  (src/fo4sf/pipeline.py, the three `not load_door` conditions). Interior pairs get a graph-less DOOR with an XTEL
  (dotnet/PluginSpike/TeleportLinks.cs); exterior <-> interior pairs get FO4SF_LoadDoor (an ACTI on the core side, the
  graph-less DOOR plus a VMAD on the port side; docs/terrain/scripted-doors.md). The player presses E and is moved at
  once; the door never moves. The SDM, library and Vault 95 round trips pass that way (bridge thread).
- Fallout 4's own load-door models mostly carry an Open sequence (16 of 20 in the port cells, check A5 below), but the
  port never used it.
  Starfield does animate its visible load doors: 506 of its 964 XTEL door bases carry an AnimationGraphComponent with
  a `*_Load` graph (**verified**, research-log 2026-10-10; e.g. `IndIntRmSmWallMid_DoorA01_Load` 2AC325,
  `SimpleOpenClose06_Load.agx`). "Enter and exit animations" therefore means Starfield's behaviour on FO4's doors: the
  door opens, then the trip.

## Design (reversible; for the roadmap talk)

1. **The rig.** A load door gets a rig the same way an ordinary door does, from either
   - its own FO4 NIF, when that NIF has an Open sequence (`convert_batch.py --rig-load-doors`), or
   - its **non-load twin**: FO4 often places a static "...Load" copy of an animated door (`UtilMetalDbDoorLoad01` /
     `UtilMetalDbDoor01`). `scripts/door_bridge/load_door_anim.py plan` takes the twin's rigged model and rig when the
     twin's FO4-space bounds equal the load model's within 5 cm (`load_door_anim.TWIN_TOLERANCE_M`); otherwise it says
     why and the door stays as today. Check A5 found no load model in the port cells that needs a twin.
   The result sits in the manifest as `load_door.anim` (graph, skeleton, clips, origin offset, bounds, model,
   `open_seconds` from FO4's Open sequence, `fo4_open_events` = FO4's sound keys). A rigged load door never also
   gets a `door` entry, so it stays one record: a DOOR that opens and then travels.
2. **The record** (dotnet/PluginSpike/Program.cs): a `load_door` item with `anim` becomes the same DOOR as before plus
   the AnimationGraphComponent, the twin's model and bounds; its references shift by the rig's origin offset as the
   opening doors' do. Without `anim` nothing changes (tested: PluginSpike.Tests "Animated load-door checks").
3. **The trip, scripted doors** (exterior <-> interior): `scripts/door_bridge/FO4SF_AnimatedLoadDoor.psc` extends
   FO4SF_LoadDoor. On the player's activation the engine has already started the DOOR's open; the script waits until
   `GetOpenState() == 1` (at most `OpenSeconds` + 0.25 s, else `MaxWaitSeconds` 3 s), calls the parent's travel
   unchanged, then `SetOpen(False)` so the door is shut when the player comes back. VMAD: the same six properties plus
   `OpenSeconds` (`vmad_patch.animated_load_door_scripts` / `animated_load_door_target`), written by
   `vmad_patch.py port --animated-doors <manifest>` (step B, done 2026-10-19). Without the option `port` and `check`
   write and require FO4SF_LoadDoor exactly as before (tested byte for byte).
4. **The trip, XTEL doors** (interior <-> interior, today only FortHagen01 <-> FortHagen02 in the pinned cells):
   vanilla uses a `*_Load` graph for this. Which `_Load` graph goes with which rig is check A1; until then an animated
   XTEL door would carry `SimpleOpenClose01.agx`, whose behaviour with an XTEL is **unresolved** (in-game check G2).
5. **The exterior side** (FO4TerrainCore.esm) is an ACTI, which cannot open. Making it the same animated DOOR is a
   change to the core writer (dotnet/TerrainOverlays, make_core64c `cluster_doors`), which the v6e Red Rocket build
   depends on, so it is **not in this branch**: it comes after v6e's test, behind its own switch (step C).

Starfield's own door animations come first (owner, 2026-10-19): the template doors play the Akila clips; FO4's own
keys play only where the door already gets its own rig. FO4 clips can replace the template later per door.

## Switches (all off by default)

| Where | Switch | Off (default) | On |
|---|---|---|---|
| converter | `convert_batch.py --rig-load-doors` (needs `--starfield-data`) | load doors stay static | animated load-door NIFs rigged into `load_door.anim`; checkpoint signature gains `rig_load_doors` |
| manifest | `scripts/door_bridge/load_door_anim.py plan --out <new>` | input manifest untouched | a new manifest with twins filled in; `<out>.load_doors.json` lists every load door and why |
| writer | `load_door.anim` present in the manifest | graph-less DOOR (as every pinned build) | DOOR with graph, twin model, offset |
| VMAD | `vmad_patch.py port --animated-doors <manifest>` | every door FO4SF_LoadDoor, byte for byte as before | doors whose DOOR base (by EDID) has `load_door.anim` get FO4SF_AnimatedLoadDoor + OpenSeconds; doors.json records it and `check` requires it |

Unit tests: tests/test_load_door_anim.py (converter switch on/off, twins, CLI, survey, VMAD, compile wrapper, batch
signature) and dotnet/PluginSpike.Tests. The suite passes with the switches off, so every existing build path is the
same: 2184 Python tests OK (123 skipped), PluginSpike.Tests all pass (2026-10-19, cloud).

## PC data reads (read-only; exact steps relayed by the coordinator to the install thread)

All at Idle priority, outputs under `D:\Modding\scratch\loaddoor_anim`, from a worktree of this branch at the PR's
head commit. Nothing is installed, nothing touches Starfield's Data folder or the load order.

- **A1 vanilla door rigs and graphs.** `SfInspect doortsv` over Starfield.esm. Offline afterwards: every `*_Load`
  graph and the non-load DOOR sharing its BNAM / CNAM (same rig, other graph) shows whether a `_Load` graph is only a
  graph swap for the same rig (then XTEL doors take the `_Load` twin of `SimpleOpenClose01`).
- **A2 two vanilla load doors in full.** `SfInspect doorrec IndIntRmSmWallMid_DoorA01_Load` and
  `doorrec ElvGen_ExSm_DoorFull01_Load`: sounds, keywords, flags a visible animated load door carries.
- **A3 Papyrus door API.** From `Tools\ContentResources.zip`: the lines of `ObjectReference.psc` naming
  `GetOpenState`, `SetOpen`, `OnOpen`, `OnClose`, `PlayAnimationAndWait`, `BlockActivation`; FO4SF_AnimatedLoadDoor
  relies on the first two and on `Utility.Wait`.
- **A4 compile.** `compile_animated_load_door.py` with the game's PapyrusCompiler into a new folder (no install).
- **A5 FO4 load-door NIFs.** `load_door_anim.py survey` over the port staging's cell exports with the clean FO4 data:
  which load models animate, how long, their sound keys, and which have an animated twin.
- **A6 manifest report.** `load_door_anim.py report` on the installed port's manifest: how many load doors would get
  a rig today (twins only, since the pinned build was converted without `--rig-load-doors`).

## PC results (2026-10-19, install thread, worktree at 027e210; outputs in D:\Modding\scratch\loaddoor_anim)

- **A5, FO4 load-door NIFs: 16 of the 20 models FO4 places as teleporting doors in the 16 port cells have their own
  Open sequence** (**verified**, survey.json), so the earlier hypothesis that FO4 load doors are mostly static is
  **refuted**: `--rig-load-doors` is the main path, twins matter little (0 needed). Open lengths 0.13 s (the three
  `VltDoorResLoad01A/B/C`) to 1.33 s; FO4 sound keys present on 6 (e.g. `Sound: DRSWoodMuseumAOpen` on
  `BldWoodPDbDoorLoad01`, `Sound: DRSVaultDoorVerticalOpen` on the vault doors). No Open sequence: `MetalTrapdoorLadder01`,
  `AutoLoadMarker01`, `PrySmRoomLadder01`, `InvisibleDoor01` (markers and ladders; they stay as today).
- **A6, installed port manifest:** 18 load doors, 0 with a rig (the build predates the switch); twin planning finds
  none usable (8 names without "load", 10 twins whose bounds differ by more than 5 cm). Expected: the pinned build was
  converted without `--rig-load-doors`.
- **A1, vanilla graphs** (**verified**, doortsv 339 DOORs): 32 rigs carry both `SimpleOpenClose01.agx` and one `*_Load`
  graph on the same skeleton and clips, so a load graph is a graph swap for the same rig. **The Akila template rig has
  a vanilla load variant:** `AK_Ext_Bld_WallA_DoorA_Load_01` (1C42C2) and `_Load_03/04/05` use
  `SimpleOpenClose02_Load.agx` with `ak_ext_bld_walla_doora_01`'s skeleton and clips. The converter records it as
  `load_door.anim.xtel_anim_graph` for template-rigged load doors (for step B; the writer does not use it yet). The most
  common pair is `SimpleOpenClose01` / `SimpleOpenClose06_Load` (11 rigs): the candidate for own-rig XTEL doors,
  **supported hypothesis**.
- **A2:** vanilla load doors use the same NIF as their non-load sibling (`IndIntRmSmWallMid_DoorA01_Load_Neon` uses
  `indintrmsmwallmid_doora01.nif`) and carry OpenSound / CloseSound and NativeTerminal 227D93; our records have no sounds.
- **A3, Papyrus** (**verified**, ObjectReference.psc): `GetOpenState()`, `SetOpen(bool)`, `BlockActivation`,
  `PlayAnimationAndWait`, events `OnOpen` / `OnClose` all exist, as the script assumes.
- **A4, compile:** FO4SF_LoadDoor compiled (3,578 bytes); FO4SF_AnimatedLoadDoor failed on a local variable named
  `state`, a Papyrus keyword (lines 25-26). Renamed `openState`; a test now refuses a local of that name. Rerun at
  28a63af: both compiled (**verified**), nothing installed.

## Next steps

- **B, done 2026-10-19** (after A3 and A4 passed): `vmad_patch.py port --animated-doors <manifest>` writes
  FO4SF_AnimatedLoadDoor with `OpenSeconds` from `load_door.anim`; `check` reads which doors from doors.json and requires
  it there. Both compiled PEX files (A4 rerun: FO4SF_LoadDoor 3,578 bytes sha256 35d8b66b..., FO4SF_AnimatedLoadDoor
  1,985 bytes sha256 5662f5d9..., from 28a63af) must ride in the port's archive.
- **C** (after the v6e test): the core writer places the exterior side as the same animated DOOR (FO4 name, rig,
  VMAD) behind a switch; compare-ids must show only the door ACTIs replaced.
- **G** (in game, owner's window only): G1 the SDM pair with both sides animated: E, the leaf swings, then the trip,
  both ways; G2 the FortHagen01 <-> 02 XTEL pair with an animated base; G3 come back through a door you used: it is
  shut. Pass = a screenshot of the open leaf before each load screen and the bridge log's arrival line.
- Sounds: FO4's sound keys (`fo4_open_events`) are recorded, not mapped; vanilla load doors' sound fields (A2) decide
  the mapping.
