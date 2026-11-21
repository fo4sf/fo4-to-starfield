# Pip-Boy First-Person Arm & Wrist Visibility Study (T7 / N1)

Status: **Offline analysis only** (not live-verified in game). This document records what is proven offline about Round 6 `T7` (`N1` arm-raise visibility) and the companion boot-sequence font mismatch, and separates what can be resolved via existing Starfield rig/equipment rules from what requires a 3D render-target UI pipeline.

---

## 1. Observed Symptom (Candidate 2c / Round 6)

During Candidate 2c testing (both inside the vault and outdoors), pressing the Pip-Boy/Map key triggered the native raise idle:

- `FO4SFPipboyMenu.dll` invoked `AIProcess::PlayIdle` (`ActionIdle` `0x36`) with Starfield's vanilla `IDLE 0x000C154F` (`idleexaminewatch`), logging `step=arm_play_idle form=000C154F ... played=1 accepted=1` and `step=arm_raise_done ... accepted=1 ... show_in_ms=2000`.
- Despite `accepted=1`, no first-person forearm or wrist device appeared in screenshots captured at 0.7 s, 2 s, and 5 s.
- `FO4SF_PipboyMenu` (and on first open, `pipboybootsequence.swf`) drew as a flat 2D overlay across the viewport over the 3D world rather than on a 3D wrist device.
- On the first outdoor open, `pipboybootsequence.swf` rendered garbled text strips across the top of the viewport.

---

## 2. Offline Proof A — Why the Arm / Wrist Device Is Not Visible on the First-Person Rig

### 2.1 Idle Graph Target (`IDLE 0x000C154F`)

- `IDLE 0x000C154F` (`idleexaminewatch`) plays a `DynamicIdle` on Starfield's first-person animation graph (`Human_1stPersonRoot.agx`), raising the player's left forearm into the first-person camera frustum.
- Because the animation lives on the first-person graph, the raise is only visible when the player camera is in first person and the upper-body arms are free (weapon sheathed).

### 2.2 Biped Slot Occlusion on `FO4SF_PipboyWrist` (`0x00080D`)

- `FO4SF_PipboyWrist` (`FO4SFNewGame.esm:0x00080D`) is duplicated from Starfield's vanilla `Clothes_Chronomark_Mq101_NOTPLAYABLE` (`Starfield.esm:0x0D4893`) with its NonPlayable record flag cleared so the player can equip it.
- That record occupies Starfield's `Chronomark` Biped slot.
- On the first-person rig, the `Chronomark` Biped slot geometry is occluded/suppressed whenever the player has equipped clothing or spacesuit armor occupying any of these Biped slots:
  - **Slot `3`** — `BODY`
  - **Slot `8`** — `SleevesVisOnly`
  - **Slot `35`** — `Spacesuit`
- Consequently, whenever the player wears a standard jumpsuit/outfit (slot `3` / `8`) or a spacesuit (slot `35`), the `Chronomark` slot mesh (`FO4SF_PipboyWrist`) is hidden on the first-person arms even when the wrist item is equipped and `idleexaminewatch` returns `accepted=1`.
- Furthermore, in start paths where `FO4SF_PipboyWrist` (`0x00080D`) has not yet been added and equipped on the player (such as a Warfare start that skips the Vault 111 pickup), no wrist device exists on the first-person skeleton at all.

### 2.3 Vanilla Starfield Reference Pattern (`FrontDoorToLodgeScript`)

Vanilla Starfield solves this exact first-person visibility constraint in `FrontDoorToLodgeScript` when playing the Chronomark watch inspection beat:

1. Call `ForceFirstPerson()` so the active camera uses `Human_1stPersonRoot.agx`.
2. Call `SheatheWeapon()` so weapon-ready upper-body layers do not mask the examine-watch `DynamicIdle`.
3. Temporarily unequip equipped armor occupying Biped slots **`3` (`BODY`)**, **`8` (`SleevesVisOnly`)**, and **`35` (`Spacesuit`)** so the `Chronomark` slot and first-person forearm are unobstructed.
4. Play `IDLE 0x000C154F` (`idleexaminewatch`) while the wrist device is equipped in the `Chronomark` slot.
5. Re-equip the saved slot `3` / `8` / `35` items after the examine-watch animation finishes or the menu closes.

### 2.4 What Would Make the Arm & Device Visible in First Person

Two viable engineering paths follow directly from the offline proof above:

1. **Short-term rig-compatible raise (mirrors vanilla `FrontDoorToLodgeScript`):**
   - Ensure `FO4SF_PipboyWrist` (`0x00080D`) is equipped on the player across both Story (post-pickup) and Warfare starts.
   - Before playing `IDLE 0x000C154F`, ensure first-person camera (`ForceFirstPerson`) and sheathed weapon (`SheatheWeapon`), and temporarily unequip/restore occluding armor in Biped slots `3`, `8`, and `35` (or suppress sleeves/spacesuit during the raise window), restoring them cleanly on menu close or abort.
2. **Dedicated Pip-Boy first-person wrist `ARMA` (longer-term, avoids outfit unequip flash):**
   - Author/port a first-person wrist `ARMA` (`FO4SF_PipboyWrist`) bound to a non-occluded first-person slot or a custom `ARMO`/`ARMA` pairing whose first-person mesh renders cleanly over sleeve/spacesuit meshes without requiring slot `3`/`8`/`35` unequip.

---

## 3. Offline Proof B — Why the Menu Draws as a 2D Overlay Over the World

Even when the first-person arm and wrist device are visibly raised in front of the camera, `FO4SF_PipboyMenu` currently draws as a flat 2D overlay over the 3D viewport:

- `FO4SFPipboyMenu.dll` registers `FO4SF_PipboyMenu` as a standard Scaleform `IMenu` hosting `FO4SF_Fo4Shell.swf` (and `pipboybootsequence.swf` on first open).
- Starfield composites standard `IMenu` movies onto the 2D HUD/UI pass over the rendered 3D scene rather than binding their output to a 3D mesh surface.
- By contrast, Fallout 4's diegetic Pip-Boy renders its Scaleform movie into an offscreen UI render-target texture mapped onto the 3D Pip-Boy wrist NIF's screen submesh, driven by a dedicated 3D-UI menu renderer and screen shader.
- Starfield's `Chronomark` wrist mesh does not expose a Fallout 4-style interactive Scaleform render-target screen pipeline.
- **Boundary:** Fixing first-person arm/wrist visibility (Section 2) makes the raised arm and wrist device appear during the open transition (`arm_raise_done`), whereas projecting the live interactive Pip-Boy SWF *onto* a 3D wrist screen mesh is a separate render-to-texture / NIF material project.

---

## 4. Companion Fix — Garbled Boot-Sequence Text (`pipboybootsequence.swf`)

Round 6 also observed `pipboybootsequence.swf` drawing garbled text strips across the top of the screen on the first outdoor open.

- **Root cause (proven offline):** Binary tag inspection of Fallout 4's `Interface/PipboyBootSequence.swf` shows a `DefineEditText` tag (`tag 37`, `HasFontClass = 1`) whose `FontClass` string is `$Terminal_Font`.
- Fallout 4's `fonts_en.swf` exports `$Terminal_Font`, whereas Starfield's `fonts_en.swf` does **not** — Starfield exports `$ConsoleFont` (Consolas) and `$MAIN_Font`.
- When Scaleform opens `pipboybootsequence.swf` inside Starfield without `$Terminal_Font` registered, glyph resolution fails and renders corrupted horizontal text strips.
- **Stage-time fix:** `scripts/ui/pipboy_map_store.py` (`patch_boot_movie_swf`, invoked by `stage_fo4_boot_movie`) rewrites `$Terminal_Font\x00` to `$ConsoleFont\x00` inside `DefineEditText` (`tag 37`), recalculating the tag length header and CWS `FileLength` so the output passes container validation (`pipboy_probe_install.swf_problem == None`).
- Note that this font patch fixes boot-text legibility only; the boot movie remains a 2D `IMenu` overlay until a 3D render-target screen exists (Section 3).

---

## 5. Offline Proven vs Live-In-Game Gates

| Item | Status | Evidence |
| --- | --- | --- |
| `IDLE 0x000C154F` targets `Human_1stPersonRoot.agx` via `DynamicIdle` | Proven offline | Starfield `IDLE` record + `FO4SFPipboyMenu.dll` `AIProcess::PlayIdle` (`ActionIdle` `0x36`) |
| `FO4SF_PipboyWrist` (`0x00080D`) inherits `Chronomark` Biped slot from `0x0D4893` | Proven offline | `dotnet/NewGame/Program.cs` duplication of `0x0D4893` with NonPlayable flag cleared |
| Biped slots `3` (`BODY`), `8` (`SleevesVisOnly`), `35` (`Spacesuit`) occlude `Chronomark`; vanilla `FrontDoorToLodgeScript` unequips `3`/`8`/`35` + `ForceFirstPerson` + `SheatheWeapon` | Proven offline | Starfield Biped slot masks + vanilla `FrontDoorToLodgeScript` watch choreography |
| `FO4SF_PipboyMenu` composites as a 2D `IMenu` overlay rather than a 3D mesh render target | Proven offline | `sfse/FO4SFPipboyMenu/src/main.cpp` `IMenu` registration and Scaleform movie loading |
| `pipboybootsequence.swf` `tag 37` (`DefineEditText`) requests `$Terminal_Font`, missing from Starfield `fonts_en.swf` (`$ConsoleFont` / `$MAIN_Font`) | Proven offline | SWF tag inspection + `patch_boot_movie_swf` unit test (`tests/test_pipboy_map.py`) |
| Visible first-person arm/wrist raise in motion and legible `$ConsoleFont` boot sequence in game | **Requires live PC + owner-eyes test** | Still screenshots can miss short motion; must be observed in a live session after staging |
