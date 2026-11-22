# Round 10 `C5` Binary Forensic & Offline-Provability Audit: Actor Looks & Wrist HUD

**Whole-scope context:** Fallout 4 to Starfield conversion (`When Freedom Calls` opening slice through `candidate-2g` on `FO4Core_Commonwealth` / `MarsPlanetWorld`).  
**Document role & `R15` status:** Required Round 10 `C5` binary root-cause and offline-provability report (`pushed, not run` in game — **not** a speculative feature design note). Every statement below separates **offline-proven binary facts** (verified directly in `.esm`, `.nif`, `.mesh`, `.mat`, and `.swf` bytes) from **unproven in-game rendering behavior** awaiting `candidate-2g` execution.

---

## 1. Why Preston and All 5 Concord Raiders Wore Starfield Spacesuits in `candidate-2f` (`9b5327ff`)

Binary inspection of `FO4SFMission.esm`, `FO4ActorRaider.esm`, `FO4TerrainCore_Mars.esm`, and `Starfield.esm` proves two distinct spacesuit pathways fired on `MarsPlanetWorld` (`PNDT 0x0003F59A MarsPlanetData`, non-breathable `CO2` atmosphere):

### 1.1 Preston Garvey (`FO4SFMission.esm:0x000801` `FO4_PrestonGarvey`, placed `ACHR 0x000802`)
1. **Null `SpaceOutfit` (`SOFT`) triggered `DefaultSpaceSuitOutfit_DO`:**
   - In `9b5327ff`, `dotnet/Mission/Program.cs` duplicated `Starfield.esm:0x0001169C` (`UC_NA_PapaKatz`), set `DefaultOutfit` (`DOFT`) to `0x00208E39` (`Outfit_FreestarRanger_Vest_with_Hat`), and left **`SpaceOutfit` (`SOFT`) = `Null`**.
   - In `Starfield.esm`, **`DFOB 0x001A76BD` (`DefaultSpaceSuitOutfit_DO`)** resolves to **`OTFT 0x0016D5E5` (`Outfit_Spacesuit_DefaultNPC_NoBoostpack_NOTPLAYABLE`)**. Whenever a `HumanRace` (`0x0000347D`) actor has `SpaceOutfit = Null`, Starfield's outfit manager instantiates `0x0016D5E5` (white/grey Navigator spacesuit body + helmet) into the NPC's inventory.
   - `npc.UseTemplateActors` also remained `0x6C12` (`27666`) from `UC_NA_PapaKatz` even though `DefaultTemplate` and `TemplateActors` were cleared.
2. **Non-breathable planet condition (`CNDF 0x00194ABF` & `0x000BEA53`) evaluated `TRUE`:**
   - **`DFOB 0x000C33DB` (`ActorShouldShowSpacesuit_DO`) -> `CNDF 0x00194ABF` (`ActorShouldShowSpacesuit`)** evaluates `TRUE` on `MarsPlanetWorld` because all clauses hold simultaneously:
     - `[0]` `HumanRaceORChildRaceORHumanCorpseRaceORRaceAllowSpacesuit` (`0x003198D6`) == `1` (`HumanRace` `0x0000347D`),
     - `[1]` `GetValue(0x000B120E ActorShouldForceHideSpacesuit_AV) != 1` (unset = `0.0`),
     - `[2]` `WornHasKeyword(0x0023C7C0 ArmorTypeSpacesuitBody) == 1` (supplied by `0x0016D5E5`),
     - `[4]` `ActorShouldShowSpacesuitGameplay` (`0x000E55E5`) -> `ActorShouldShowSpacesuitGameplayNotBreathable` (`0x000B1205`) == `1`.
   - **`DFOB 0x000C33DA` (`ActorShouldShowSpacesuitHelmet_DO`) -> `CNDF 0x000BEA53` (`ActorShouldShowSpacesuitHelmet`)** likewise evaluates `TRUE` when `WornHasKeyword(0x0023C7C1 ArmorTypeSpacesuitHelmet) == 1` and `ActorShouldHideSpacesuitHelmetCosmetic == 0`.
3. **Old European face retained from `UC_NA_PapaKatz`:**
   - Duplicating `0x0001169C` left `SkinToneIndex = 4` (pale), `HairColor = "SaltAndPepper"`, `HeadParts = [Human_Male_Beard_PencilMoustache, Human_Male_LeftEye_Bloodshot, ...]`, `Tints = [European_Male_Md2_Sk3, ...]`, and `MorphBlends = [male_eu_ol1_*]`.

### 1.2 All 5 Concord Raiders (`ACHR 0x000803..0x000807`, base `FO4ActorRaider.esm:0xF04800` `FO4_LvlRaider`)
- `FO4ActorRaider.esm:0xF04800` (`FO4_LvlRaider`) has `UseTemplateActors = 0x7E3B` (Inventory bit `0x0080` is `0`, so its own outfits apply) and explicitly authors:
  - `DOFT` (`DefaultOutfit`) = `0x0005B422` (`Outfit_Clothes_Mechanic_Tanktop_Brown`),
  - **`SOFT` (`SpaceOutfit`) = `0x003D094D` (`Outfit_Spacesuit_Spacer_AssaultOrNoRole`)** -> `LL_Armor_Spacer_Backpack_Leveled_Any` (`0x00079208`), `LL_Armor_Spacer_Body_Leveled_Any` (`0x0007920A`), and `LL_Armor_Spacer_Helmet_Leveled_Any` (`0x0007920C`), with `ActorShouldForceHideSpacesuit_AV` (`0x000B120E`) unset (`0.0`).
- On `MarsPlanetWorld`, Starfield selected `SOFT` (`0x003D094D`) over `DOFT` (`0x0005B422`), dressing all five Concord raiders in Spacer spacesuits and helmets.

### 1.3 Triple-Lock Spacesuit & Helmet Stripping (`dotnet/Mission/FalloutActorLooks.cs`)
`FalloutActorLooks.ApplyActorLooks` eliminates all three preconditions across Preston (`0x000801`), an override of `FO4ActorRaider.esm:0xF04800` (`FO4_LvlRaider`, `FormVersion = 581`) in `FO4SFMission.esm`, and every other `HumanRace` NPC in `FO4SFMission.esm`:
1. **`PRPS` Lock (`AVIF 0x000B120E ActorShouldForceHideSpacesuit_AV = 1.0`):** Forces `CNDF 0x00194ABF` clause `[1]` (`GetValue(0x000B120E) != 1`) to `FALSE` unconditionally on non-breathable worlds.
2. **`SOFT` + `DOFT` Lock:** Sets **both** `DefaultOutfit` and `SpaceOutfit` explicitly to non-spacesuit clothes `OTFT` records (`0x000980` `FO4_Outfit_PrestonMinuteman` on Preston; `0x000988` `FO4_Outfit_ConcordRaider` on `FO4_LvlRaider` `0xF04800` and raider bosses), never leaving `SpaceOutfit = Null` (defeating `DFOB 0x001A76BD`) and never referencing `Outfit_Spacesuit_*` or `ArmorTypeSpacesuitBody`/`Helmet`/`Backpack` (`0x0023C7C0..0x0023C7C2`).
3. **Template & Inventory Hygiene:** Clears stale `UseTemplateActors = 0` on standalone non-templated NPCs and removes any `Items` entry carrying `ArmorTypeSpacesuit*` keywords. Overriding `FO4ActorRaider.esm:0xF04800` in place preserves `raiderRefs[0..4].Base == FO4ActorRaider.esm:0xF04800` and `GetIsID` checks without touching `FO4ActorRaider.esm` on disk.

---

## 2. Preston's Own Fallout 4 Outfit & Face First, Then the 5 Concord Raiders

### 2.1 Preston Garvey's Face & Proportions (`Fallout4.esm:0x00019FD9` -> `FO4SFMission.esm:0x000801`)
- **Source record (`Fallout4.esm:0x00019FD9` `PrestonGarvey`):**
  - `HeadParts`: `MaleHeadHuman` (`0x01EEBB`), `HairMale04` (`0x0821DC`), `Beard01` (`0x0E12A4`), `MaleEyesHumanBrown` (`0x0209F4`).
  - `HairColor`: `0x19EE60` (`HairColor13JetBlack`); `Height = 1.0`; `Weight = (Thin 0.3566, Muscular 0.3468, Fat 0.2966)`.
- **Why FO4's `FaceGeom\Fallout4.esm\00019FD9.NIF` is not directly attachable:** Fallout 4 pre-bakes NPC heads as `BSFaceGenNiNodeSkinned` + FO4 `.tri` morphs, whereas Starfield's `HumanRace` (`0x0000347D`) drives faces through Chargen DNA (`FaceDialPositions` + `FaceMorphs` + `MorphBlends` + `Dermaesthetic` `male_af_*` post-blend textures). No FaceGen-to-Starfield DNA solver exists in the repository.
- **Implemented `HumanRace` conversion (`ApplyPrestonFalloutFace`):**
  - Replaces `UC_NA_PapaKatz`'s pale/old European face blocks with valid Starfield `HumanRace` young African-American male morphs/tints from `Starfield.esm:0x000ED1C4` (`EncFreestarSecurityFaceM04`: `SkinToneIndex = 7`, `TintName = "African_Male_yo1_Sk6"`, `Human_Male_Hair_Faded_Afro` `0x00006852`, stripping `*_ol1_*` blends and `Jewelry_*` parts) paired with `0x0015F5A6` (`Human_Male_Beard_ClassicBeard`, matching FO4 `Beard01`), `HairColor = "Black"`, `FacialHairColor = "Black"`, `EyebrowColor = "Black"`, `EyeColor = "Brown"`, `HeightMin = HeightMax = 1.0`, and FO4 `0x00019FD9`'s exact `Weight = (0.3566, 0.3468, 0.2966)`.

### 2.2 Fallout 4 Outfit Rebinding onto Starfield `HumanRace` `SkinAttach` (`scripts/actors/stage_c5_actor_looks.py`)
- **Starfield `HumanRace` `SkinAttach` layout (verified across vanilla `Starfield - Meshes*.ba2`):**
  - Unlike `MiniBotA` (`Codsworth`), `HumanRace` clothing NIFs set `BSSkin::Instance` bone node indices to `[-1, ..., -1]` (`N` slots) and attach a **`SkinAttach`** `NiExtraData` block (`<iI` `name_idx, N` followed by `N` `<I` length-prefixed Starfield bone names such as `C_Chest`, `C_Hips`, `C_Spine*`, `C_Neck1`, `C_Head`, `L/R_Clavicle`, `L/R_Biceps*`, `L/R_Forearm`, `L/R_Wrist*`, `L/R_Thigh*`, `L/R_Calf`, `L/R_Foot`, `L/R_Toe`) alongside `BSSkin::BoneData` (`4 + 68 * N` bytes).
  - Applying the inverse of the template `BSGeometry` world transform (`wt(tgt)^(-1)`) to Fallout 4 posed vertices scaled by `FO4_TO_SF_HUMAN_SCALE = 1.63227 / 120.84` aligns FO4 boots (`Z = -0.0038 m`), cuffs (`Z = 1.01..1.18 m`), collar (`Z = 1.61 m`), and Preston's tricorn hat (`Z = 1.683..1.805 m` vs vanilla `Hat_M` `1.671..1.803 m`) onto `Naked_M.nif` (`0x00012204`, `41` bones, `4` normalized weights/vertex) and `Outfit_First_Mercenary_01_Hat_M.nif` (`0x00211140`, `['C_Head']`, `1` weight/vertex).
- **Local `FO4SFMission.esm` records (`0x980..0x98A`, disjoint from `0x800..0x979` and `A4` `0xA00+`):**
  1. **Preston (`0x000980` `FO4_Outfit_PrestonMinuteman`):**
     - `ARMA 0x000981` `FO4_AA_PrestonDuster` + `ARMO 0x000983` `FO4_Armor_PrestonMinuteman` (`fo4port/armor/preston_garvey/prestongarveyoutfit_m.nif` = FO4 `PrestonGarveyOutfit.nif` + `PrestonGarveyGloves.nif`, materials `prestonbody1.mat` + `prestongloves1.mat` converted via existing `fo4sf.pipeline.Converter` + `basehumanskin.mat` from `FO4ActorRaider - Main.ba2`).
     - `ARMA 0x000984` `FO4_AA_PrestonHat` + `ARMO 0x000985` `FO4_Armor_PrestonHat` (`fo4port/armor/preston_garvey/prestongarveyhat_m.nif` = FO4 `PrestonGarveyHat.nif`, material `prestonhat1.mat`).
  2. **5 Concord Raiders (`0x000988` `FO4_Outfit_ConcordRaider`):**
     - `ARMA 0x000989` `FO4_AA_ConcordRaider` + `ARMO 0x00098A` `FO4_Armor_ConcordRaider` (`fo4core/armor/raider04/concord_raider_m.nif` = FO4 `RaiderUnderArmorM.nif` + `Raider04M.nif` + `MaleHands.nif`, skipping redundant bare-chest `BaseMaleBodyRaider:0`), using **100% already-converted** Starfield `.mat`/`.dds` assets already packed inside `FO4ActorRaider - Main.ba2`:
       - `materials/fo4core/armor/raiderunderarmor/raiderunderarmorm.mat`
       - `materials/fo4core/armor/raider04/raider04.mat`
       - `materials/fo4core/actors/character/basehumanmale/basehumanskin.mat`
       - `materials/fo4core/actors/character/basehumanmale/basehumanmaleskinhands.mat`

---

## 3. Explicit `R15` Matrix: Offline-Provable vs Requires In-Game Verification

| Component / Claim | Proven Offline (Binary Verified) | Unproven Until `candidate-2g` Runs in Game (`R15`) |
| :--- | :--- | :--- |
| **Spacesuit & helmet removal on Preston & 5 Raiders** | `AVIF 0x000B120E == 1.0` in `PRPS`, non-null non-spacesuit `DOFT` + `SOFT`, `UseTemplateActors == 0` on Preston, `FO4_LvlRaider` (`0xF04800`) `FormVersion=581` override in `FO4SFMission.esm`, and `0` `ArmorTypeSpacesuit*` keywords/items. | Confirming Starfield's live outfit evaluation on `MarsPlanetWorld` equips `FO4_Outfit_PrestonMinuteman` / `FO4_Outfit_ConcordRaider` on fresh spawn and reload with zero spacesuit geometry. |
| **Preston's face, hair, beard & body build** | `STON = 7`, `African_Male_yo1_Sk6` dermaesthetic tint, `Black` hair/beard/eyebrow colors, `Brown` eye color, `Human_Male_Beard_ClassicBeard` (`0x0015F5A6`), `0` `*_ol1_*` or `European_Male_*` entries, and `Weight = (0.3566, 0.3468, 0.2966)` round-tripped in `FO4SFMission.esm`. | Visual likeness, skin/beard shading under Commonwealth exterior lighting, and lip-sync/facial animation during `FO4SF_Min00_PrestonScene`. |
| **Staged FO4 Preston & Raider `SkinAttach` NIFs** | Valid BS 173/175 NIF block structure, `SkinAttach` bone list == `BSSkin::Instance` slot count (`-1` refs), `BSSkin::BoneData` spheres, `BSMeshData` v2 normalized 4-weight/1-weight skin streams (`sum == 65535`) + meshlets/cull data (`tail == 0`), `MaterialID` CRC32, plain shader blocks, and millimetre-matched world bounds (`Z = 0..1.61 m` body, `1.68..1.80 m` hat). | First in-game load of a custom `SkinAttach` `HumanRace` outfit NIF: verifying Starfield binds `SkinAttach` slots without mesh distortion, coat-skirt stretching during walk/combat animations, or head/neck clipping. *(One-flag rollback: building `FO4SFMission.esm` without `--actor-looks-dir` keeps 100% of spacesuit stripping + Preston's face on vanilla non-spacesuit colonial apparel.)* |

---

## 4. Wrist HUD Audit (`MARS` with `O2` and `CO2`)

Binary inspection of `Starfield - Interface.ba2` (`interface/hudmenu.swf` `262,458` B and `interface/playerhudcomponents.swf` `336,534` B uncompressed) plus `Starfield.esm` `PNDT` / `GMST` / `DFOB` records establishes the exact data sources of the lower-left planetary watch:

1. **Where `MARS`, `O2`, and `CO2` come from (proven offline in `.swf` & `.esm` bytes):**
   - `interface/hudmenu.swf` instantiates the watch container (`Watch` / `_Watch`, `WatchIconsWidget`, `_RemoveWatch`, `WATCH_RADIUS`).
   - `interface/playerhudcomponents.swf` defines `WatchFaceComponent_mc` containing:
     - **`Planet_tf`:** Dynamic text field bound to `HUDDataModel` `sBodyName`, populated by the engine from **`PNDT 0x0003F59A` (`MarsPlanetData`)** `ANAM` (`"MARS"`).
     - **`O2Txt_mc` & `CO2Txt_mc` (`O2CO2_mc`, `O2Anim_mc`, `CO2Anim_mc`):** **Hardcoded movieclip labels (`$O2` / `"O2"` and `"CO2"`)** baked directly inside `playerhudcomponents.swf`'s `WatchFaceComponent_mc` timeline alongside the circular oxygen/carbon-dioxide arc meters (`Oxygen` `AVIF 0x000002D5`).
2. **Offline-provable vs in-game levers (and why no `.swf` replacement is shipped in this slice):**
   - **Plugin `PNDT.ANAM` override (`FO4TerrainCore_Mars.esm`):** Overriding `PNDT 0x0003F59A` `ANAM` changes `Planet_tf` text (`"MARS"` -> `"COMMONWEALTH"`), which is provable in `.esm` bytes, **but** leaves the baked `"O2"` / `"CO2"` watch arcs on screen and renames Mars globally across Starfield's starmap.
   - **Binary `.swf` replacement (`Data/Interface/playerhudcomponents.swf` / `hudmenu.swf`):** Not used — replacing vanilla Starfield Scaleform movies on disk risks `HUDDataModel` AS3 class-layout mismatches (`#792`).
   - **Recommended runtime lever (`docs/ui/fo4-hud-options.md` Option B, `NOT BUILT` in `2g`):** Suppressing the watch container at runtime on the open `HUDMenu` Scaleform movie via SFSE `GFx::Value::SetDisplayInfo` / `_visible = false` (while keeping crosshair and `E` prompt active) paired with the separate non-pausing `FO4SF_HudMenu` Fallout 4 HUD overlay (`HP`/`Rads`, horizontal compass, `AP`/`Ammo`).
