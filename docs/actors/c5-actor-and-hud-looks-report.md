Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (playable path) -- prototype, offline (pushed, not run on D2/A2.3 delta; C5 duster & spacesuit strip ran in game on 2g)

# Round 10 `C5` + Round 11 `D2` & `A2.3` Binary Forensic Report: Actor Looks & Wrist HUD

**Report role & `R15` status:** Binary root-cause and offline-provability report for Preston Garvey (`0x000801`) and the Concord raiders (`0x000986` `FO4_ConcordRaider`, placed `ACHR 0x000803..0x000807`) plus the wrist HUD audit (**not** a new feature design note).
- **`ran in game` (`candidate-2g`, `#32` comment `7085816241`, Stills `05`–`08`):** Spacesuit and helmet removal passed on Preston and all 5 Concord raiders; Preston's Fallout 4 Minuteman duster, boots, and Starfield chargen face approximation rendered cleanly in dialogue (`"Fallout 4 duster, gloves and boots, no spacesuit, no helmet, face reads as Preston in the dialogue close-up"`).
- **`pushed, not run` (Round 11 `D2` + `A2.3` + Review #7 delta for `candidate-2g-fix` / `candidate-2h`):** `D2` fix for Preston's missing hat (`MO2F`/`MO3F` `HasFaceBonesModel` strip + `0x10`/`0x12` hat `BO64` + `0x68` gloved `Hands` mask fixing Still `07` duplicate bare fingers), `A2.3` scoping to local `0x000986` `FO4_ConcordRaider` (removing the global override of `FO4ActorRaider.esm:0xF04800`), and Review #7 stripping of `0x003D094D` Spacer spacesuit outfits on all 3 later-mission `FO4_LvlRaider`-cloned `NPC_` records in `FO4SFMission.esm` (`0x0A23` `FO4_CorvegaBoss`, `0x0AD1` `FO4_Kellogg`, `0x0B31` `FO4_CourserZ247`).

**Plain asset summary (`R15` & owner rule):**
- **Preston's outfit & hat = FO4 meshes (offline-proven; duster ran in game on `2g`, hat fix pushed, not run):** `PrestonGarveyOutfit.nif` + `PrestonGarveyGloves.nif` + `PrestonGarveyHat.nif` rebound onto `HumanRace` `SkinAttach` templates with converted FO4 `.mat`/`.dds` materials.
- **Preston's face = Starfield chargen approximation, because the FO4 FaceGen head is not converted (`ran in game` on `2g`):** `EncFreestarSecurityFaceM04` (`0x000ED1C4`) morphs/tints + Starfield `Human_Male_Beard_ClassicBeard` (`0x0015F5A6`) + `Human_Male_Hair_Faded_Afro` (`0x00006852`) + FO4 `0x00019FD9` weight/colors (`STON=7`, `Black`, `Brown`), replacing `UC_NA_PapaKatz`'s pale/old European face without claiming a converted FO4 FaceGen head mesh.
- **Concord raiders' outfit = FO4 meshes & already-converted `FO4ActorRaider - Main.ba2` materials (`ran in game` at `40 m` on `2g`; close-up corpse inspection step added on `2h` card):** `RaiderUnderArmorM.nif` + `Raider04M.nif` + `MaleHands.nif` rebound onto `HumanRace` `SkinAttach` using `raiderunderarmorm.mat`, `raider04.mat`, `basehumanskin.mat`, and `basehumanmaleskinhands.mat` already shipped in `FO4ActorRaider - Main.ba2`.

---

## 1. Why Preston and All 5 Concord Raiders Wore Starfield Spacesuits in `candidate-2f` (`9b5327ff`) — Fixed & Passed in `2g`

Binary inspection of `FO4SFMission.esm`, `FO4ActorRaider.esm`, `FO4TerrainCore_Mars.esm`, and `Starfield.esm` proved two spacesuit pathways fired on `MarsPlanetWorld` (`PNDT 0x0003F59A MarsPlanetData`, non-breathable `CO2` atmosphere):

### 1.1 Preston Garvey (`FO4SFMission.esm:0x000801` `FO4_PrestonGarvey`, placed `ACHR 0x000802`)
1. **Null `SpaceOutfit` (`SOFT`) triggered `DefaultSpaceSuitOutfit_DO` (`DFOB 0x001A76BD` -> `OTFT 0x0016D5E5`):** Leaving `SpaceOutfit = Null` on a `HumanRace` (`0x0000347D`) actor caused Starfield to instantiate `Outfit_Spacesuit_DefaultNPC_NoBoostpack_NOTPLAYABLE` (`0x0016D5E5`), while `UseTemplateActors` remained `0x6C12` (`27666`) from `UC_NA_PapaKatz` (`0x0001169C`).
2. **Non-breathable planet condition (`CNDF 0x00194ABF` & `0x000BEA53`) evaluated `TRUE`:** Because `AVIF 0x000B120E` (`ActorShouldForceHideSpacesuit_AV`) was unset (`0.0`) and `0x0016D5E5` supplied `ArmorTypeSpacesuitBody` (`0x0023C7C0`) + `ArmorTypeSpacesuitHelmet` (`0x0023C7C1`), Starfield rendered the white/grey Navigator spacesuit and helmet.

### 1.2 Concord Raiders (`ACHR 0x000803..0x000807`, cloned from `FO4ActorRaider.esm:0xF04800` `FO4_LvlRaider`)
- `FO4ActorRaider.esm:0xF04800` (`FO4_LvlRaider`) authored `SpaceOutfit` (`SOFT`) = `0x003D094D` (`Outfit_Spacesuit_Spacer_AssaultOrNoRole`) with `ActorShouldForceHideSpacesuit_AV` (`0x000B120E`) unset (`0.0`), dressing all five raiders in Spacer spacesuits and helmets on `MarsPlanetWorld`.

### 1.3 Scoped Triple-Lock Spacesuit Stripping, Round 11 `A2.3` Dedicated `0x000986` `FO4_ConcordRaider`, & Review #7 Later-Mission Bosses
In Round 10 (`2g`), `FalloutActorLooks.ApplyActorLooks` overrode `FO4ActorRaider.esm:0xF04800` directly in `FO4SFMission.esm`, which meant every raider built on `0xF04800` inherited the override globally and any future rebuild of `FO4ActorRaider.esm` would be silently shadowed by a build-time copy (`A2.3`).

In Round 11 (`A2.3` + Review #7), `FalloutActorLooks.ApplyActorLooks` eliminates the foreign override while ensuring **zero** `NPC_` records in `FO4SFMission.esm` retain `0x003D094D`:
1. **Zero foreign `NPC_` overrides:** `FO4SFMission.esm` emits **zero** `NPC_` records in `FO4ActorRaider.esm`'s FormID space (`!plug.Npcs.Any(n => n.FormKey.ModKey == raiderModKey)`).
2. **Dedicated local `0x000986` (`FO4_ConcordRaider`, `FormVersion = 581`):** Cloned from `FO4ActorRaider.esm:0xF04800` (`FO4_LvlRaider`, preserving `UseTemplateActors = 0x7E3B`) with `AVIF 0x000B120E = 1.0` in `PRPS`, `DefaultOutfit = 0x000988` (`FO4_Outfit_ConcordRaider`), and `SpaceOutfit = 0x000988`.
3. **Strict Concord `ACHR` scoping (`0x000803..0x00080F`):** Only Concord's placed raider `ACHR`s (`IsConcordRaiderRefId`, `0x803..0x807` today) are repointed to `0x000986` (`FO4_ConcordRaider`). Non-Concord raider `ACHR`s (`0xA24` Corvega boss, etc.) are not rewritten to `0x000986`.
4. **Review #7 later-mission `FO4_LvlRaider`-cloned `NPC_` stripping (`0x0A23` `FO4_CorvegaBoss`, `0x0AD1` `FO4_Kellogg`, `0x0B31` `FO4_CourserZ247`):** Because `NextStoryMissionsA4` and `NextStoryMissionsA7cd` build these three local boss `NPC_` records by duplicating `FO4ActorRaider.esm:0xF04800` (which copies `SOFT = 0x003D094D`), `ApplyActorLooks` strips `0x003D094D` on all three (`DOFT = SOFT = 0x000988` `FO4_Outfit_ConcordRaider`, `AVIF 0x000B120E = 1.0`, `preserveIntentionalTemplates: true`) and `CheckActorLooks` enforces that **zero** `NPC_` records in `FO4SFMission.esm` carry `0x003D094D`, while leaving non-raider NPCs (`FO4_Sturges`, etc.) and `FO4ActorRaider.esm:0xF04800` untouched. *(Integration sync hooks on `gemini/round11-first-mission`: `dotnet/Mission/Program.cs` `Check()` `masters` allow `["Starfield.esm", core]` or `["Starfield.esm", core, raider]`, `raiders.All(r => r.Base.FormKey == new FormKey(key, FalloutActorLooks.ConcordRaiderNpcId))`, and `src/fo4sf/core/cross_plugin_check.py` `(0x986, "NPC_", "FO4_ConcordRaider")`.)*

---

## 2. Round 11 `D2` Forensic Diagnosis & Fix: Why Preston's Hat Was Missing in `2g` Stills `07` & `08`

Direct subrecord comparison of `2g`'s installed `FO4SFMission.esm` (`0x980..0x985`), `FO4ActorRaider - Main.ba2`, and `Starfield.esm` / `Starfield - Meshes01.ba2` proves the exact cause offline without guesswork:

### 2.1 Primary Root Cause — Inherited `MO2F = 0x01` / `MO3F = 0x01` (`HasFaceBonesModel`) Redirected to a Non-Existent `*_facebones.nif`
1. **Both NIFs and `.mesh`/`.mat`/`.dds` assets were present and valid in `2g`:**
   - `meshes/fo4port/armor/preston_garvey/prestongarveyhat_m.nif` (`996 B`, `SkinAttach = ['C_Head']`, `wpv = 1`, `Z = +0.0506..+0.1724 m` local -> `+1.6829..+1.8047 m` world), its `geometries/36a66dbb2573e1a892e2/08ca2f8c9270abec4971.mesh` (`12,126 B`, `365` verts, `620` tris), `materials/fo4port/armor/preston/prestonhat1.mat`, and `prestonhat1_{color,normal,rough}.dds` were all present in `2g`'s BA2s, and `OTFT 0x000980` (`FO4_Outfit_PrestonMinuteman`) contained both `0x000983` (duster) and `0x000985` (hat).
2. **Why `0x000981` (duster) rendered while `0x000984` (hat) silently failed to load:**
   - `ARMA 0x000981` (`FO4_AA_PrestonDuster`) duplicated `Starfield.esm:0x00012204` (`AA_Naked_Body`), whose `MOD2`/`MOD3` subrecords carry **no** `MO2F`/`MO3F` model flags — so Starfield loaded `prestongarveyoutfit_m.nif` directly.
   - `ARMA 0x000984` (`FO4_AA_PrestonHat`) duplicated `Starfield.esm:0x00211140` (`AA_Clothes_First_Mercenary_01_Hat`), whose `MOD2` and `MOD3` subrecords carry **`MO2F = 0x01` / `MO3F = 0x01` (`Model.Flag.HasFaceBonesModel`) + `XFLG = 0x01`**. In `Starfield - Meshes01.ba2`, every `MO2F = 0x01` hat ships a paired `*_facebones.nif` (`outfit_first_mercenary_01_hat_m_facebones.nif`, skinned to `17` `faceBone_*` joints) that Starfield loads instead of the base `.nif` on FaceGen/Chargen human actors.
   - Because `SetWorldModels` mutated `arma.WorldModel.Male.File` in place without replacing the `SF.Model` wrapper, `0x000984` emitted `MO2F = 0x01` and `MO3F = 0x01` into `2g`'s `FO4SFMission.esm`. On Preston (`0x000801`), Starfield appended `_facebones` and requested `meshes/fo4port/armor/preston_garvey/prestongarveyhat_m_facebones.nif` (absent from BA2), so the hat mesh silently failed to load while `Human_Male_Hair_Faded_Afro` (`0x00006852`) rendered unmasked.
   - By contrast, vanilla `Starfield.esm` `C_Head` headgear without `_facebones.nif` variants (e.g. `0x01D206` `AA_Clothes_Miner_UtilitySuit_Headgear_01`, `0x165719` `AA_Clothes_Security_Guard_Helmet_01`) uses the **exact same 9-block `['C_Head']` NIF layout** as `prestongarveyhat_m.nif` with **`MO2F`/`MO3F` omitted (`Flags = null`)**.

### 2.2 Secondary Biped-Slot (`BO64`) Fixes — Hat Slot Alignment & Still `07` Bare-Hands Masking
1. **Hat `BO64` alignment (`0x10` on `ARMO 0x000985`, `0x12` on `ARMA 0x000984`):**
   - Across all `74` `ArmorTypeApparelHead` (`0x000E048B`) `ARMO`s in `Starfield.esm`, **zero** `NonPlayable` hats set bit `0x01` (`HEAD`); `0x21113E` (`BO64 = 0x11`) was one of only `3` playable hats setting `0x01`. Setting `ARMO 0x000985` `FirstPersonFlags = 0x10` (`HairTop`) + `ARMA 0x000984` `FirstPersonFlags = 0x12` (`Hair | HairTop`) matches Sam Coe's `NonPlayable` companion hat (`0x1C8E0A` `Clothes_Colonist_Adventurous_Hat_SamCoe_NOTPLAYABLE` -> `ARMA 0x25DEEB`) bit-for-bit, activating `Human_Male_Hair_Faded_Afro`'s `FadedAfro_Cap_Mask` (`NAM3`) under the hat crown without conflicting with `HEAD` (`0x01`).
2. **Gloved full-body `BO64 = 0x68` (`BODY | UpperBody | Hands`) on `0x981`/`0x983` & `0x989`/`0x98A`:**
   - Inspection of `2g` Still `07` (`07-preston-fo4-duster-no-hat.png`) also revealed `HumanRace`'s default `AA_Naked_Hands` (`0x00030580`, `BO64 = 0x40`) drawing bare fingers behind Preston's leather gloves because `0x981` had `BO64 = 0x08` and `0x983` had `BO64 = 0x28` (missing `0x40` `Hands`). Both `prestongarveyoutfit_m.nif` (`PrestonGarveyGloves.nif`) and `concord_raider_m.nif` (`MaleHands.nif`) include full hands/gloves; setting `BO64 = 0x68` (matching vanilla gloved outfits `0x21BBF2` `Clothes_NewAtlantis_Security` and `0x25E8D4` `Clothes_UCPolice`) masks both `AA_Naked_Body` (`0x08`) and `AA_Naked_Hands` (`0x40`).
3. **Close-up Concord raider inspection (`D2`):** After defeating the Concord exterior raiders with god mode off, walking up to any downed `FO4_ConcordRaider` corpse on the Museum steps gives a console-free `1–2 m` close-up check of `concord_raider_m.nif` (`RaiderUnderArmorM` + `Raider04M` harness + `MaleHands`, no helmet, no spacesuit).

---

## 3. Explicit `R15` Matrix: Ran in Game (`2g`) vs Proven Offline (`2h` Delta) vs Unproven Until `2h` Runs

| Component / Claim | Status Today | Proven Offline (Binary Verified) | Needs `candidate-2h` In-Game Verification (`R15`) |
| :--- | :--- | :--- | :--- |
| **Spacesuit & helmet removal + Preston duster & chargen face** | **`ran in game` (`2g`, pass)** | `AVIF 0x000B120E == 1.0`, non-spacesuit `DOFT` + `SOFT`, `UseTemplateActors == 0`, `STON = 7`, `African_Male_yo1_Sk6`, `ClassicBeard` + `Faded_Afro`, FO4 `0x00019FD9` weight (`0.3566, 0.3468, 0.2966`). | Regression check after `D2` + `A2.3` rebuild. |
| **`D2` Preston's Minuteman hat (`0x984`/`0x985`) & `0x68` glove mask** | **`pushed, not run`** | `SetWorldModels` emits **zero** `MO2F`/`MO3F`/`XFLG` (`HasFaceBonesModel`) subrecords on `0x981`, `0x984`, `0x989`; `0x985` `BO64 = 0x10`, `0x984` `BO64 = 0x12`, `0x981`/`0x983`/`0x989`/`0x98A` `BO64 = 0x68`; `prestongarveyhat_m.nif` (`['C_Head']`, `Z = +1.683..+1.805 m`) + `.mesh`/`.mat`/`.dds` verified. | Confirming in `2h` dialogue & exterior stills that Preston's Minuteman cavalier hat renders on his head with `FadedAfro_Cap_Mask` and zero duplicate bare hands at his wrists. |
| **`A2.3` + Review #7 Scoped `0x000986` `FO4_ConcordRaider` & later-mission bosses** | **`pushed, not run`** | `0` foreign `NPC_` overrides of `FO4ActorRaider.esm` in `FO4SFMission.esm`; `0x000986` (`FormVersion = 581`, `DOFT = SOFT = 0x988`, `0x0B120E = 1.0`) referenced by Concord `ACHR 0x803..0x807` while `0x0A23` (`FO4_CorvegaBoss`), `0x0AD1` (`FO4_Kellogg`), and `0x0B31` (`FO4_CourserZ247`) also have `0x003D094D` stripped (`0` `NPC_`s in `FO4SFMission.esm` carry `0x003D094D`). | Close-up inspection (`1–2 m`) of downed Concord raider bodies after the fight (`D2`) and later-mission boss visual verification when Corvega / Fort Hagen / Greenetech run. |

---

## 4. Wrist HUD Audit (`MARS` with `O2` and `CO2` — Implemented on `R11-W4` for `D7`)

Binary inspection of `Starfield - Interface.ba2` (`interface/hudmenu.swf` and `interface/playerhudcomponents.swf`) plus `Starfield.esm` establishes:
- **Dynamic `MARS` (`Planet_tf`):** `hudmenu.swf` hosts `_Watch` / `WatchIconsWidget`, and `playerhudcomponents.swf`'s `WatchFaceComponent_mc` binds `Planet_tf` to `HUDDataModel` `sBodyName`, fed from **`PNDT 0x0003F59A` (`MarsPlanetData`)** `ANAM` (`"MARS"`).
- **Hardcoded `O2` and `CO2` (`O2Txt_mc`, `CO2Txt_mc`):** Baked as Flash movieclip labels inside `playerhudcomponents.swf`.
- **Round 11 `D7` disposition:** Suppressing `_Watch` / `WatchFaceComponent_mc` visibility at runtime via our SFSE Scaleform sidecar behind `HideStarfieldWatch=1` (ON in the player bundle INI, one-line `HideStarfieldWatch=0` rollback — owned by `R11-W4`) hides the entire Starfield watch without replacing vanilla `.swf` files on disk.

---

## 5. Open Questions for the Owner

1. **Preston's face (`Starfield chargen approximation` vs `FO4 FaceGen head conversion`):** Preston's Starfield chargen approximation (`EncFreestarSecurityFaceM04` + `ClassicBeard` + FO4 `0x00019FD9` weight/colors) ran and passed in `candidate-2g` (`"face reads as Preston in the dialogue close-up"`). Should we keep this chargen approximation for Round 11 (`2h`/`2i`) alongside his converted FO4 Minuteman duster and hat, or build a dedicated `BSFaceGenNiNodeSkinned` -> `HumanRace` head-part converter in a later round?
2. **Museum interior settlers (`Sturges`, `Mama Murphy`, `Marcy Long`, `Jun Long` in `S6`/`S9`):** When Preston's group is added inside `ConcordMuseum01` after Plan PR approval, should each receive the same C5 pattern (converted FO4 outfit NIF rebound onto `HumanRace` `SkinAttach`, `MO2F`-free `ARMA`, `BO64 = 0x68`, `0x000B120E = 1.0`, and matching chargen face traits)?
