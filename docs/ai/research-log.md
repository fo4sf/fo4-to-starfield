# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

## 2026-10-11 Claude: Starfield terrain architecture
- Question: how can native Starfield terrain carry the exact Commonwealth geography (S5 / WP-12)?
  Full write-up: [docs/terrain/architecture.md](../terrain/architecture.md).
- Method: raw record walk of both ESMs; new read-only SfInspect commands (`wrld`, `sfbk`, `planetworlds`, `wcells`,
  `form`); index-only listing of the terrain BA2s and a 44-byte header survey of all 2,112 `.btd`; BTD decoder after
  fo76utils (MIT) checked on vanilla files (re-encode byte-identical per section and per decompressed block, not per
  file: the zlib streams differ); ref-vs-terrain fits; xEdit's Starfield definitions read for
  field names; FO4 `LAND.VHGT` decoded for all Commonwealth cells.
- Evidence: Starfield.esm has 0 `LAND` (Fallout4.esm 37,020). 430/433 WRLD point through an overlay component to an
  SFBK whose `ANAM` is `Data\TERRAIN\<EditorID>.btd`; 72 WRLD are registered by planets (`PNDT.MasterWorldspaces`,
  lat/long). BTD: 128 samples per 100 m cell, u16 heights linear in metres between a per-file min/max, LOD0-4,
  vanilla up to 100 x 100 cells. Commonwealth LAND: 192 x 192 cells, -118.86..641.03 m.
- Status: format, record chain and sizes **verified**; height scale in metres and grid alignment (BTD cell i = world
  cell i - n//2) **supported hypothesis** (pad at 111.4 m vs refs at 112-113.5 m; 130/133 NewAtlantis object cells inside
  the predicted footprint); whether a plugin worldspace with its own BTD loads, and whether it needs a planet entry,
  **unresolved** until experiment 1 (staged in `C:\Modding\staging\terrain_exp1`, not deployed). Recommendation:
  option A, a dedicated worldspace with a native BTD.
- Update (in game, 2026-10-11, unattended runner; `C:\Modding\testqueue\terrain_*`): loose files are disabled on this
  install (`sResourceDataDirsFinal=STRINGS\`), so loose BTDs were never readable (**verified**). A worldspace's own BTD
  only applies to an overlay activated on a planet (PNDT `CNAM`); unregistered World01 and World02 showed identical
  procedural ground (**verified**), and World03 (no overlay component) hangs on load (**verified**, twice). Activation
  merges cells at a whole-cell offset plus a Z offset (LC172World -500 / -2300 m, Z -3.62 m), so "world z = BTD
  height" is **refuted** in absolute form and **verified** only relative to that offset (0.02 m in LC172World's
  authored cell). SFBK `FNAM` as "8 connections" is **refuted** (one u16 per BTD cell). Largest overlay BTD in vanilla:
  14 x 14 cells, not 100. Registered runs with our packed BTD were flat at its raw-0 height; cause (compressed BA2
  entry) is a **supported hypothesis**, rerun pending. Option A now needs B's planet activation.

## 2026-10-09 Claude: which FO4 collision bodies are movable?
- Question: how does an FO4 `bhkPhysicsSystem` mark a body as movable (pushable), so the converter can stop turning
  physics objects into fixed obstacles (Vault 114 door `05C7DC` is blocked by a ragdoll skeleton)?
- Method: compared `SkeletonClothed01.nif` (ragdoll) with `SubPlatformWall01.nif` (static) in the
  `hknpPhysicsSystemData` packfile, then scanned all 4,014 converted models (local script, not in the repo).
- Evidence: body cinfo +12 (u32) is a motion index: skeleton bodies 0..16 with 17 motion entries and 16 constraints
  (`hkpRagdollConstraintData`, `hkpLimitedHingeConstraintData`), layer 10; static wall `0x7FFFFFFF`, layer 1.
- Scan (motion index != 0x7FFFFFFF): 490 models / 5,340 placements with one moving body; 59 / 345 with several and no
  joints (cryo pods, roof hatches); 29 / 167 ragdolls with joints (skeletons, V111 gear-room gates, gurney).
- Status: "+12 = motion index, 0x7FFFFFFF = static": **supported hypothesis** (2 files). "Motion index means
  pushable": **refuted as stated**: placed Statics like `BldgShellWoodStairsRailing01` also have one, so it also covers
  keyframed / animated bodies. **Unresolved:** the motion entries' mass / motion type, which separates pushable
  (dynamic) from keyframed bodies.
- Follow-up (same day): system +32 holds motion *properties* (present only for dynamic bodies; values like 104.375 /
  31.57 / 0.1 / 0.05 identical in skeleton and pencil) and +48 the motion *cinfos*: u16 motion-properties id at +0,
  inverse mass f32 at +4. Skeleton: id 0, inverse mass 0.1 (10 kg); pencil: id 0, 2.0 (0.5 kg); stair railing and cryo
  pod: id 0xFFFF, inverse mass 0 (keyframed). Rule "dynamic = motion index != 0x7FFFFFFF, its cinfo id != 0xFFFF and
  inverse mass > 0": **supported hypothesis** (4 files, consistent across the scan). Rescan of 4,014 models: 373 single
  dynamic (4,642 placements: loose items), 22 multi-body without joints (156: breakable railings, gore), 29 ragdolls
  (167). Railings and cryo pods move to static, which is correct for them.

## 2026-10-09 Starfield `.af` animation header (door rigs)
- Question: what are the u16 fields at 0x28 of `open.af`?
- Method: compared four door families' `open.af` with their `characterassets\skeleton.rig` name tables
  (docs/spikes/WP-doors-research.md, "Header fields vs rig bone tables").
- Evidence: Akila 6 bones / field 6; generic 21/21; ship small 24/24; ship large 49/49.
- Status: field 2 = rig bone count: **verified** (4 of 4). Field 1 = format version: **supported hypothesis**.
  Field 3 = frame count: **supported hypothesis** (30 fps unconfirmed). Field 4: **unresolved**.

## 2026-10-09 FO4 precombine collision bodies with "shared vertex index out of range"
- Question: what primitive encoding do these `SCOL\CM*.NIF` bodies use?
- Evidence: 0 packed vertices, shared-index entries in triples (2130, start, x), primitives like (3,2,2,2);
  docs/JOURNAL.md "Precombine debris parts" and its correction.
- Status: **unresolved**. The "thin rods" reading was **refuted** (groups up to ~3 m in every axis).
