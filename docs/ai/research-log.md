# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

## 2026-10-11 Claude: converting one Fallout 4 raider into a native Starfield NPC_
- Question: what does a converted FO4 actor need to run on Starfield's own actor systems, and can Mutagen write it?
  Full write-up: docs/actors/raider-conversion.md.
- Method: `dotnet/ActorRaider` (read-only on both ESMs): `export-fo4` follows the template chain of ACHR 00046458
  `DN092concordRaider01` (Concord); `sf-dump`, `sf-tplstats`, `rawcount`, and `roundtrip` (Mutagen writes 6 vanilla
  NPC_ records back; every subrecord is compared with Starfield.esm).
- Evidence and status:
  - **Verified:** the FO4 chain is LvlRaider 0002898B -> LCharRaider 00022E48 -> EncRaider01Template 0003183A at
    player level 1, with traits from LCharRaiderFaceAndGender 000FD3A3 (14 faces). Starfield's LvlSpacer 0027BB7B ->
    LCharSpacer 0027BB7D (10 tiers) + LCharSpacerFaceAndGender 0027BB7C (7 faces) has the same shape.
  - **Verified:** hostility works differently. FO4 RaiderFaction has no relation to PlayerFaction (9 relations); its
    raiders are VeryAggressive. SpacerFaction 0027BB8C is Enemy to PlayerFaction 01C21C; Spacers are Unaggressive /
    Brave and carry 6 RDSA reaction radii.
  - **Verified:** Starfield NPC_ have 15 template slots; Mutagen 0.55.0-alpha.67 names 13 of them (slots 13 and 14 are
    `TemplateActors.Unknown1/2`, flag bits unnamed). 5,445 of 7,131 NPC_ use templates (bit 13: 2,825, bit 14: 4,253).
    Slots 13 and 14 almost always share the behaviour template, never Traits alone. What they mean is **unresolved**.
  - **Verified:** Mutagen round trip. 1 of 6 records came back byte-identical. 2 differ only in FULL (localized string
    ID -> inline string). 3 gain an empty STOP after RDSA; 4,310 of 7,131 vanilla NPC_ carry STOP before CNAM (32 right
    after RDSA), so that it is harmless is a **supported hypothesis**. Everything else matched, including TPTA, AIDT,
    RDSA and the raw subrecords.
  - **Verified:** the Coachman WEAP 0026D96B has `NpcsUseAmmo` False. FO4Port.esm's highest local FormID is DE5C, so
    the raider's F04800 cannot collide.
  - **Supported hypothesis:** the plugin's console ID is 02F04800 (first plugin in Plugins.txt = slot 02, as for the
    terrain anchor 02000800).
  - **Supported hypothesis:** a direct NPC_ template, with no leveled list in the chain, keeps `GetIsID` working.
  - **Unresolved until N2a / N2b run:** whether Starfield spawns, animates and paths the converted record, and
    whether it engages the player.

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
