Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (playable path) -- prototype, offline (pushed, not run)

# Round 10 `C5` Binary Forensic & Offline-Provability Report: Actor Looks & Wrist HUD

**Report role & `R15` status:** Required Round 10 `C5` binary root-cause and offline-provability report (`prototype, offline` / `pushed, not run` in game -- **not** a new feature design note). Scope is strictly **Preston Garvey (`0x000801`) + the 5 Concord raiders (`FO4ActorRaider.esm:0xF04800` `FO4_LvlRaider`)** and the wrist HUD audit; no other `NPC_` records in `FO4SFMission.esm` are modified.

**Plain asset summary (`R15` & owner rule):**
- **Preston's outfit & hat = FO4 meshes (offline-proven):** `PrestonGarveyOutfit.nif` + `PrestonGarveyGloves.nif` + `PrestonGarveyHat.nif` rebound onto `HumanRace` `SkinAttach` templates with converted FO4 `.mat`/`.dds` materials.
- **Preston's face = Starfield chargen approximation, because the FO4 FaceGen head is not converted:** `EncFreestarSecurityFaceM04` (`0x000ED1C4`) morphs/tints + Starfield `Human_Male_Beard_ClassicBeard` (`0x0015F5A6`) + `Human_Male_Hair_Faded_Afro` (`0x00006852`) + FO4 `0x00019FD9` weight/colors (`STON=7`, `Black`, `Brown`), replacing `UC_NA_PapaKatz`'s pale/old European face without claiming a converted FO4 FaceGen head mesh.
- **5 Concord raiders' outfit = FO4 meshes & already-converted `FO4ActorRaider - Main.ba2` materials (offline-proven):** `RaiderUnderArmorM.nif` + `Raider04M.nif` + `MaleHands.nif` rebound onto `HumanRace` `SkinAttach` using `raiderunderarmorm.mat`, `raider04.mat`, `basehumanskin.mat`, and `basehumanmaleskinhands.mat` already shipped in `FO4ActorRaider - Main.ba2`.

---

## 1. Why Preston and All 5 Concord Raiders Wore Starfield Spacesuits in `candidate-2f` (`9b5327ff`)

Binary inspection of `FO4SFMission.esm`, `FO4ActorRaider.esm`, `FO4TerrainCore_Mars.esm`, and `Starfield.esm` proves two spacesuit pathways fired on `MarsPlanetWorld` (`PNDT 0x0003F59A MarsPlanetData`, non-breathable `CO2` atmosphere):

### 1.1 Preston Garvey (`FO4SFMission.esm:0x000801` `FO4_PrestonGarvey`, placed `ACHR 0x000802`)
1. **Null `SpaceOutfit` (`SOFT`) triggered `DefaultSpaceSuitOutfit_DO`:**
   - In `9b5327ff`, `dotnet/Mission/Program.cs` duplicated `Starfield.esm:0x0001169C` (`UC_NA_PapaKatz`), set `DefaultOutfit` (`DOFT`) to `0x00208E39` (`Outfit_FreestarRanger_Vest_with_Hat`), and left **`SpaceOutfit` (`SOFT`) = `Null`**.
   - In `Starfield.esm`, **`DFOB 0x001A76BD` (`DefaultSpaceSuitOutfit_DO`)** points to **`OTFT 0x0016D5E5` (`Outfit_Spacesuit_DefaultNPC_NoBoostpack_NOTPLAYABLE`)**. Whenever a `HumanRace` (`0x0000347D`) actor has `SpaceOutfit = Null`, Starfield's outfit manager instantiates `0x0016D5E5` (white/grey Navigator spacesuit body + helmet) into the NPC's inventory.
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

### 1.3 Scoped Triple-Lock Spacesuit & Helmet Stripping (`dotnet/Mission/FalloutActorLooks.cs`)
`FalloutActorLooks.ApplyActorLooks` modifies **only** Preston (`0x000801`) and an in-place override of `FO4ActorRaider.esm:0xF04800` (`FO4_LvlRaider`, `FormVersion = 581`, preserving `UseTemplateActors = 0x7E3B`, `Coachman` weapon, `raiderRefs[0..4].Base`, and `GetIsID`) in `FO4SFMission.esm`:
1. **`PRPS` Lock (`AVIF 0x000B120E ActorShouldForceHideSpacesuit_AV = 1.0`):** Forces `CNDF 0x00194ABF` clause `[1]` (`GetValue(0x000B120E) != 1`) to `FALSE` unconditionally on non-breathable worlds.
2. **`SOFT` + `DOFT` Lock:** Sets **both** `DefaultOutfit` and `SpaceOutfit` explicitly to local Fallout 4 outfit records (`0x000980` `FO4_Outfit_PrestonMinuteman` on Preston; `0x000988` `FO4_Outfit_ConcordRaider` on `FO4_LvlRaider` `0xF04800`), never leaving `SpaceOutfit = Null` (defeating `DFOB 0x001A76BD`) and never referencing `Outfit_Spacesuit_*` or `ArmorTypeSpacesuit*` (`0x0023C7C0..0x0023C7C2`).
3. **Template & Inventory Hygiene:** Clears `DefaultTemplate`, `TemplateActors`, and `UseTemplateActors = 0` on Preston while keeping `FO4_LvlRaider`'s intentional `0x7E3B` template chain intact, and strips any `Items` entry carrying `ArmorTypeSpacesuit*` keywords. All other NPCs in `FO4SFMission.esm` (`Sturges`, `Piper`, `Nick`, `Amari`, `Kellogg`, `CourserZ247`, etc.) remain completely untouched.

---

## 2. Preston's Outfit & Chargen Face Approximation First, Then the 5 Concord Raiders

### 2.1 Preston Garvey's Face (`0x000801` -- Starfield Chargen Approximation)
- **FO4 source (`Fallout4.esm:0x00019FD9` `PrestonGarvey`):** `HairMale04` (`0x0821DC`), `Beard01` (`0x0E12A4`), `MaleEyesHumanBrown` (`0x0209F4`), `HairColor13JetBlack` (`0x19EE60`), `Height = 1.0`, `Weight = (Thin 0.3566, Muscular 0.3468, Fat 0.2966)`, and pre-baked `Meshes\Actors\Character\FaceGenData\FaceGeom\Fallout4.esm\00019FD9.NIF` (`BSFaceGenNiNodeSkinned` + FO4 `.tri` morphs).
- **Why this is a Starfield chargen approximation (not a converted FO4 head):** Starfield's `HumanRace` (`0x0000347D`) generates faces from Chargen DNA (`FaceDialPositions`, `FaceMorphs`, `MorphBlends`, `Dermaesthetic` tints) rather than Fallout 4 `BSFaceGenNiNodeSkinned` head NIFs, and no FO4 FaceGen-to-Starfield head converter exists in the repository yet.
- **What `ApplyPrestonFalloutFace` writes:** Copies Starfield `0x000ED1C4` (`EncFreestarSecurityFaceM04`) young African-American male morphs/tints (`SkinToneIndex = 7`, `African_Male_yo1_Sk6`, Starfield `Human_Male_Hair_Faded_Afro` `0x00006852`, stripping `*_ol1_*` blends and `Jewelry_*` parts) + Starfield `0x0015F5A6` (`Human_Male_Beard_ClassicBeard`) + FO4 `0x00019FD9`'s `Black` hair/beard/eyebrow colors, `Brown` eyes, `HeightMin = HeightMax = 1.0`, and `Weight = (0.3566, 0.3468, 0.2966)`.

### 2.2 Fallout 4 Outfit Rebinding onto `HumanRace` `SkinAttach` (`scripts/actors/stage_c5_actor_looks.py`)
- **Starfield `HumanRace` `SkinAttach` binary layout:**
  - `HumanRace` clothing NIFs set `BSSkin::Instance` bone node indices to `[-1, ..., -1]` (`N` slots) and attach a **`SkinAttach`** `NiExtraData` block (`<iI` `name_idx, N` followed by `N` `<I` length-prefixed Starfield bone names) alongside `BSSkin::BoneData` (`4 + 68 * N` bytes).
  - Transforming posed FO4 vertices scaled by `FO4_TO_SF_HUMAN_SCALE = 1.63227 / 120.84` via `wt(tgt)^(-1)` aligns FO4 boots (`Z = -0.0038 m`), cuffs (`Z = 1.01..1.18 m`), collar (`Z = 1.61 m`), and Preston's tricorn hat (`Z = 1.683..1.805 m` vs vanilla `Hat_M` `1.671..1.803 m`) onto `Naked_M.nif` (`0x00012204`, `41` bones, `wpv = 4` normalized to `65535`) and `Outfit_First_Mercenary_01_Hat_M.nif` (`0x00211140`, `['C_Head']`, `wpv = 1`).
- **Local `FO4SFMission.esm` records (`0x980..0x98A`) & staged asset verification (`verify_staged_c5_assets`):**
  1. **Preston (`0x000980` `FO4_Outfit_PrestonMinuteman`):** `ARMA 0x000981` `FO4_AA_PrestonDuster` + `ARMO 0x000983` `FO4_Armor_PrestonMinuteman` (`fo4port/armor/preston_garvey/prestongarveyoutfit_m.nif` = FO4 `PrestonGarveyOutfit.nif` + `PrestonGarveyGloves.nif`, materials `prestonbody1.mat` + `prestongloves1.mat` + `basehumanskin.mat`) and `ARMA 0x000984` `FO4_AA_PrestonHat` + `ARMO 0x000985` `FO4_Armor_PrestonHat` (`fo4port/armor/preston_garvey/prestongarveyhat_m.nif` = FO4 `PrestonGarveyHat.nif`, material `prestonhat1.mat`).
  2. **5 Concord Raiders (`0x000988` `FO4_Outfit_ConcordRaider`):** `ARMA 0x000989` `FO4_AA_ConcordRaider` + `ARMO 0x00098A` `FO4_Armor_ConcordRaider` (`fo4core/armor/raider04/concord_raider_m.nif` = FO4 `RaiderUnderArmorM.nif` + `Raider04M.nif` + `MaleHands.nif`, skipping `BaseMaleBodyRaider:0`), using **100% already-converted** `raiderunderarmorm.mat`, `raider04.mat`, `basehumanskin.mat`, and `basehumanmaleskinhands.mat` in `FO4ActorRaider - Main.ba2`.
  3. **Bundle completeness check (`stage_c5_actor_looks.py --verify-only <dir>`):** Parses all `3` staged NIFs (`28` staged files total: `3` `.nif`, `8` `.mesh`, `4` `.mat`, `12` `.dds`, `1` report JSON) and refuses if any referenced external `.mesh`, `.mat`, or `.dds` is missing before packing into `candidate-2g`.

---

## 3. Explicit `R15` Matrix: Offline-Provable vs Unproven in Game

| Component / Claim | Proven Offline (Binary Verified) | Unproven Until `candidate-2g` Runs in Game (`R15`) |
| :--- | :--- | :--- |
| **Spacesuit & helmet removal on Preston & 5 Raiders** | `AVIF 0x000B120E == 1.0` in `PRPS`, non-null non-spacesuit `DOFT` + `SOFT`, `UseTemplateActors == 0` on Preston, `FO4_LvlRaider` (`0xF04800`) `FormVersion=581` override in `FO4SFMission.esm`, and `0` `ArmorTypeSpacesuit*` keywords/items. | Confirming Starfield's live outfit evaluation on `MarsPlanetWorld` equips `FO4_Outfit_PrestonMinuteman` / `FO4_Outfit_ConcordRaider` on spawn and reload with zero spacesuit geometry. |
| **Preston's outfit & hat + 5 Raiders' FO4 meshes** | **FO4 meshes (offline-proven):** BS 173/175 NIF layout, `SkinAttach` bone count == `BSSkin::Instance` (`-1` refs), `BSSkin::BoneData` spheres, `BSMeshData` v2 normalized 4-weight/1-weight streams (`sum == 65535`) + meshlets/cull data (`tail == 0`), `MaterialID` CRC32, plain shader blocks, world bounds (`Z = 0..1.61 m` body, `1.68..1.80 m` hat), and `28/28` staged file existence check. | First in-game load of a custom `SkinAttach` `HumanRace` outfit NIF: verifying runtime skinning, coat-skirt leg follow during walk/combat animations, and zero head/neck clipping. |
| **Preston's face** | **Starfield chargen approximation** (`STON = 7`, `African_Male_yo1_Sk6`, `Black` hair/beard/eyebrow, `Brown` eyes, Starfield `ClassicBeard` + `Faded_Afro`, FO4 `0x00019FD9` `Weight`), replacing `UC_NA_PapaKatz`; **FO4 FaceGen head is not converted**. | In-game appearance under Commonwealth lighting and lip-sync during `FO4SF_Min00_PrestonScene`. |

---

## 4. Wrist HUD Audit (`MARS` with `O2` and `CO2`)

Binary inspection of `Starfield - Interface.ba2` (`interface/hudmenu.swf` `262,458` B and `interface/playerhudcomponents.swf` `336,534` B uncompressed) plus `Starfield.esm` `PNDT` / `GMST` / `DFOB` records establishes:
- **Dynamic `MARS` (`Planet_tf`):** `hudmenu.swf` hosts `_Watch` / `WatchIconsWidget`, and `playerhudcomponents.swf`'s `WatchFaceComponent_mc` binds `Planet_tf` to `HUDDataModel` `sBodyName`, fed from **`PNDT 0x0003F59A` (`MarsPlanetData`)** `ANAM` (`"MARS"`).
- **Hardcoded `O2` and `CO2` (`O2Txt_mc`, `CO2Txt_mc`):** Baked directly as Flash movieclip labels (`$O2` / `"O2"` and `"CO2"` inside `O2CO2_mc` / `O2Anim_mc` / `CO2Anim_mc`) inside `playerhudcomponents.swf`.
- **Offline vs runtime levers:** Overriding `PNDT 0x0003F59A` `ANAM` in `FO4TerrainCore_Mars.esm` is offline-provable for `Planet_tf` text only (cannot remove the baked `"O2"`/`"CO2"` clips and renames Mars globally on the starmap), while replacing vanilla `.swf` files on disk risks AS3 layout mismatches (`#792`). Suppressing `_Watch._visible = false` at runtime via SFSE Scaleform `GFx::Value` alongside the separate `FO4SF_HudMenu` Fallout 4 HUD overlay (`docs/ui/fo4-hud-options.md` Option B, `NOT BUILT` in `2g`) hides the entire watch without touching `.swf` files on disk.

---

## 5. Open Questions for the Owner

1. **Preston's face (`Starfield chargen approximation` vs `FO4 FaceGen head conversion`):** Under the rule that Starfield's content is not shown beside ours, do you accept the Starfield chargen approximation (`EncFreestarSecurityFaceM04` + `ClassicBeard` + FO4 `0x00019FD9` weight/colors) for `candidate-2g` while Preston wears his converted FO4 Minuteman outfit & hat, or should we build a dedicated `FaceGeom\Fallout4.esm\00019FD9.NIF` (`BSFaceGenNiNodeSkinned`) -> `HumanRace` head-part converter before shipping Preston's look?
2. **Later-mission human NPCs (`Sturges`, `Piper`, `Nick`, `Amari`, `Kellogg`, etc.):** Should later story-mission human NPCs stay untouched until their own Fallout 4 outfits/heads are converted, or receive the spacesuit-strip property (`0x000B120E = 1.0` + FO4 Raider/settler outfits once converted)?
3. **Planetary wrist HUD (`MARS` / `O2` / `CO2`):** Should we hide Starfield's `_Watch` widget immediately via a standalone SFSE `HUDMenu` visibility flag, or wait until the Fallout 4 `FO4SF_HudMenu` overlay (`HP`/`Rads`, horizontal compass, `AP`/`Ammo`) replaces it in the same step?
