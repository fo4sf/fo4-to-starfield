# Character Looks Screen Study: Replacing `ShowRaceMenu` with Our Own UI (`S4`)

> **Author:** Gemini (PC)  
> **Status:** **STUDY ONLY — ZERO CODE BUILT THIS ROUND.**  
> **Scope:** Technical requirements on Starfield `1.16.244` (`libxse/commonlibsf 9d090c4`) for building a character appearance screen **of our own** (`FO4SF_LooksMenu`) so pre-world set-up no longer calls Starfield's `Game.ShowRaceMenu(None, 2)` (labelled **`NOT OURS`** in `N2`).

---

## 1. Why `Game.ShowRaceMenu` (`RE::ChargenMenu`) Is `NOT OURS` and Cannot Be Reskinned Cleanly

1. **Starfield Fiction Baked into `ChargenMenu`:**
   - Even when invoked in looks-only mode (`uiMode = 2`, hiding Starfield's Background and Traits tabs), `RE::ChargenMenu` (`sizeof == 0x650`, `Interface/ChargenMenu.swf`) renders Starfield's ** Argos Extractors / ENHANCE! Genetic Salon** biometric chrome, employee ID serial framing, Starfield font styling, and Starfield audio stingers.
2. **Engine Menu Teardown & Chargen State Side Effects:**
   - `ChargenMenu` mutates global engine chargen/HUD state (`SetInChargen`, camera lock states, `UIBlurManager`) on close; in Session 1 (`Card 4`), calling `Message.Show()` immediately during `ChargenMenu` teardown stranded `MessageBoxMenu` until we moved S.P.E.C.I.A.L. ahead of `ShowRaceMenu` and added a `2.0 s` post-close settle.
3. **Unmapped `ChargenMenu` Internals in CommonLibSF:**
   - In `libxse/commonlibsf` (`9d090c4`), `RE::ChargenMenu`'s `39` `CharGen_*` `UIEvent` callbacks (`CharGen_SwitchBodyType`, `CharGen_RotatePaperdoll`, `CharGen_SetSlider`, `CharGen_CloseMenu`, etc.) are all `REL::ID{ 0 }`. Hooking or patching `ChargenMenu` in place is brittle compared to registering an `IMenu` of our own (`FO4SF_LooksMenu`) using the proven vtable-copy pattern in `FO4SFPipboyMenu.dll` (`FO4SF_PipboyMenu`, `FO4SF_SpecialMenu`, `FO4SF_SetupMenu`).

---

## 2. What Our Own Character Screen (`FO4SF_LooksMenu`) Needs

Building a self-contained Vault-Tec / Fallout appearance creator requires **four layers**:

### 2.1 Layer 1 — Portrait Stage, Camera Rig & Lighting in `FO4SF_StartRoomCell`
Unlike `FO4SF_SetupMenu` (which is a full-frame opaque 2D screen with `ShowFirstPersonGeometry(false)`), a looks creator must show the live 3D player character cleanly while keeping the UI panel unobstructed:

1. **Dedicated Portrait Alcove in `FO4SF_StartRoomCell` (`FO4SFNewGame.esm:0x00081C`):**
   - Keep `FO4SF_StartRoomCell` completely Starfield-free, and add `3` neutral Fallout/Vault-toned point/spot `LIGH` references (key, fill, rim) aimed at a portrait marker (`0x000820+`) against a clean dark backdrop wall so skin tones, hair colors, and scars read accurately instead of sitting in pitch black.
2. **Third-Person Portrait Camera Framing & Orbit:**
   - Toggle third-person view and frame either **Head/Shoulders** (when editing Face/Hair) or **Full Body** (when editing Body Build / Sex) around the player's world Z-rotation:
     - `PlayerCamera::GetSingleton()` (Address Library ID **`878627`**), `ForceThirdPerson` (**`113398`**), `SetCameraState` (**`113375`**).
   - `A` / `D` or right-mouse drag rotates the player's heading (`SetAngle`) on the portrait marker so the player can inspect profile and 3/4 angles without moving the camera into a wall.
3. **Side-Panel Scaleform Movie (`Interface/FO4SF_LooksMenu.swf`):**
   - Left `42%` of the `1920x1080` stage holds our Pip-Boy / Vault-Tec category tabs (`IDENTITY`, `BODY`, `HEAD PRESET`, `HAIR & BEARD`, `EYES & SKIN`, `CONFIRM`), leaving the right `58%` clear over the lit 3D character.
   - Registered as `FO4SF_LooksMenu` in `FO4SFPipboyMenu.dll` (and added to `sfse/common/blocking_menus.h`'s own-menu constants while keeping external `kBlockingMenus` guarded), opened and acknowledged through a `FO4SFCoreValues.esm` store global (`R13`), with an automatic `R10` fallback to `Use preset look` (default preset) if the SWF or DLL is absent.

---

### 2.2 Layer 2 — `1.16.244` Native Appearance Primitives (Three Incremental Tiers)

All player appearance state lives on `PlayerCharacter::GetSingleton()` (`ID 922868`) and its base `RE::TESNPC*` (`FormID 0x00000007`, `sizeof(TESNPC) == 0x458` in `libxse 9d090c4`), rebuilt onto the live 3D actor via **`Actor::UpdateChargenAppearance` (`ID 97399`)** (`Update3DModel` / facegen refresh):

#### Tier 1 — Identity & Whole-Face Presets (Lowest Risk, Proven RVAs)
- **Sex (`Male` / `Female`):** `TESActorBaseData::actorData.flags` (`kFemale = 1 << 0` at `TESActorBaseData + 0x08`) + `TESNPC::GetSex()` (`+0x2E8` helper) followed by swapping to the matching sex's default `NPC_` preset template.
- **Pronoun (`He/Him`, `She/Her`, `They/Them`):** `TESNPC::pronoun` (`std::uint8_t` at `TESNPC + 0x450`).
- **Character Name:** `TESFullName::fullName` (`BSFixedStringCS` at `TESFullName + 0x08` on `PlayerRef`'s base `TESNPC`), captured via a clean keyboard text-entry modal on our SWF (letters, spaces, hyphens, apostrophes; `1..26` chars) while `SetupShouldHandleEvent` stops gameplay hotkeys.
- **Curated Face Presets (`12–20` Fallout-Archetype Presets):**
  - `Starfield.esm` already ships `ChargenPreset*` `NPC_` templates (`HumanRace 0x0000347D`), or we can author our own preset `NPC_` records in `FO4SFNewGame.esm`.
  - **`TESNPC::CopyAppearance(TESNPC* sourcePreset)` (`ID 68122`)** + **`Actor::UpdateChargenAppearance()` (`ID 97399`)** copies face bone morphs, headparts, skin tone, and tint layers in one engine-owned call without manual `BSTArray` heap reallocation.

#### Tier 2 — Hair, Facial Hair, Eyes, Brow, Scars & Body Triangle (Medium Scope)
- **Modular Headparts (`BGSHeadPart`, FormType `kHDPT`):**
  - Enumerate playable `BGSHeadPart` forms from `TESRace::headparts[sex]` (`HumanRace + 0x9D0`) filtered by `BGSHeadPart::type` (`Hair = 3`, `FacialHair = 4`, `Eyebrows = 6`, `Eyes = 2`, `Scars = 5`, `Teeth = 9`, `Jewelry = 13`) and `kPlayable` flag.
  - Swap the active slot on `TESNPC::headParts` (`BSTArray<BGSHeadPart*>` at `TESNPC + 0x3C0`) using an engine headpart mutator (`Actor::ChangeHeadPart` / `TESNPC` slot replacement verified by RVA check before use) + `UpdateChargenAppearance` (`97399`).
- **Hair, Beard, Eye & Skin Colors:**
  - Skin tone index via **`Actor::SetSkinTone` (`ID 97400`)**.
  - Hair/eye/beard material colors via `BGSAVMData` (`AVMD` forms) referenced on `TESNPC` (`+0x408..0x430`).
- **Body Weight Triangle (`Thin` / `Muscular` / `Heavy`):**
  - `TESNPC::morphWeight` (`3 x float` at `TESNPC + 0x350`: `thin`, `muscular`, `fat`, normalized so `thin + muscular + fat <= 1.0`) + `UpdateChargenAppearance` (`97399`).

#### Tier 3 — Fine Sculpting Sliders & Makeup/Dirt Layers (Highest Reverse-Engineering Cost)
- **Per-Feature `.tri` Morph Sliders (`Nose`, `Jaw`, `Cheeks`, `Brow`, `Mouth`, `Ears`):**
  - Stored in `TESNPC::shapeBlendData` (`BSTHashMap<BSFixedString, float>*` at `TESNPC + 0x448`) and `morphRegionSliderValues` (`+0x438`). Mutating hash maps directly from a plugin risks allocator mismatch unless driven through the engine's own slider mutator function (currently unmapped `REL::ID` in `libxse`; requires an Address Library RVA signature check on `1.16.244` first).
- **Layered Complexion / Dirt / Facepaint (`tintAVMData`):**
  - Stored in `TESNPC::tintAVMData` (`BSTArray<TintEntry>` at `TESNPC + 0x3F0`, `0x28` bytes per layer: category, texture `AVMD`, color, intensity `0.0..1.0`). Adjusting opacity on existing preset layers is a safe in-place float write, while inserting/removing layers requires the engine's `MemoryManager` allocator (`ScrapHeap` / `MemoryManager` RVA verification).

---

### 2.3 Layer 3 — Save-File (`.sfs`) Persistence & `R13` Store Mirror

Mutations made directly to `TESNPC` (`0x00000007`) in memory only survive `.sfs` save/reload if the engine serializes the changed subrecords — or if our plugin re-applies deterministic choices on `OnPlayerLoadGame`:

1. **Engine Change Flags on `PlayerNPC`:**
   - Setting `TESForm::AddChange` / `TESActorBaseData` change flags (`kHeadParts`, `kFaceData`, `kBodyWeight`, `kGender`, `kFullName`) marks `0x00000007` dirty for Starfield's `.sfs` save writer; this must be verified in a dedicated PC save -> quit -> reload test card before relying on engine serialization alone.
2. **Guaranteed Store Mirror (`R13` Belt-and-Suspenders):**
   - Record the deterministic appearance recipe in `FO4SFCoreValues.esm` globals (`Sex`, `PresetIndex`, `HairIndex`, `BeardIndex`, `EyeIndex`, `SkinToneIndex`, `HairColorIndex`, `Thin/Muscular/Fat`) so even if an engine patch or `.sfs` reload drops a runtime `TESNPC` field, `FO4SFPipboyMenu.dll` can deterministically re-apply Tier 1 + Tier 2 choices at `kPostLoadGame` in `< 5 ms`.

---

### 2.4 Layer 4 — Clean Integration with `S1` Flow (`--looks-ui`)

- Just like `--start-choice-backdrop empty_cell|setup_menu` (`S1`), `RunPreworldLooksChoice` in `FO4SF_NewGameQuest.psc` can switch by **one parameter** (`--looks-ui starfield_racemenu|fo4sf_looks|none`):
  1. Player finishes **Mode / Start Place / Survival / Difficulty** (`S1`) and **S.P.E.C.I.A.L.** in `FO4SF_StartRoomCell`.
  2. Quest moves player onto the lit portrait marker in `FO4SF_StartRoomCell`, sets `FO4SF_LooksMenuOpen = 1.0`, and waits for `FO4SF_LooksMenuDone == 1.0` (with `LooksWait` timeout + `R10` fallback to preset `Use preset look`).
  3. Zero `ChargenMenu` opens, zero Starfield ENHANCE! text appears, and zero post-`ShowRaceMenu` UI teardown delay is needed before spawning at Vault 111 or the chosen Warfare start place.

---

## 3. Recommended Phased Path (If Owner Approves Building `FO4SF_LooksMenu`)

1. **Phase L1 (Tier 1 + Tier 2 Core — Recommended First Deliverable):**
   - `FO4SF_LooksMenu.swf` + portrait lighting/camera rig in `FO4SF_StartRoomCell` + **Name, Sex, Pronoun, Curated Presets (`CopyAppearance` `68122`), Body Weight Triangle (`+0x350`), Skin Tone (`97400`), Hair, Beard, and Eye Color** + `.sfs` save/reload verification card. Eliminates `ShowRaceMenu` (`NOT OURS`) completely with zero unverified hash-map allocations.
2. **Phase L2 (Tier 3 Fine Sculpting & Makeup):**
   - Optional follow-up after RVA verification of the engine's `.tri` `shapeBlendData` and `tintAVMData` mutators on `1.16.244`.
