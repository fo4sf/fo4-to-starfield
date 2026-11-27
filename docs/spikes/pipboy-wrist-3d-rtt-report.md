# Pip-Boy Live 3D Wrist Screen (`ScreenSource=3d_rtt`): Engine Route & Minimal Probe Plan (`I2(b)`)

Status: **Offline analysis & proposal only** (grounded in repository sources, `PR #780` / `origin/claude/fal739-pb-probe-1`, `world.cpp`, and `pipboy_screen_source.h`; flat `2d_imenu` remains the shipping base and automatic fallback).

---

## 1. Evidence Grounded in This Repository

### 1.1 `World=` Census & `ScaleformToTextureRenderPass` (`docs/JOURNAL.md:2801-2806`, `sfse/FO4SFPipboyMenu/src/world.{h,cpp}`, `README.md:440-553`)

- `Interface/testmenus_dynamictexturedgeo.swf` was inspected and ruled out: it is a 4.9 kB renderer test of shapes with one `Scene` symbol, not a menu-on-world-object implementation.
- Starfield's executable (`1.16.244.0`) contains `ScaleformToTextureRenderPass`.
- `World=1` (`world.cpp`) provides a read-only census of `UI::menuMap` (`step=census_registered`) and SFSE's `IMenu::LoadMovie` callback (`step=census_movie` logging RTTI class, `flags`, `uiMovie`, `depth`, and `lead=1` for `slate`/`terminal`/`kiosk`/`watch`/`3d`/`display`/`screen` candidates, including `DataSlateMenu`).

### 1.2 `PR #780` (`origin/claude/fal739-pb-probe-1`, FAL-739 / FAL-794): `UICellRenderer_InventoryItem` & `BSMenu3D::Scene`

`PR #780` (`da38e386`) extracted and verified 9 Address Library IDs on Starfield `1.16.244.0` (`kProbeIds` in `sfse/FO4SFPipboyMenu/src/main.cpp:1685-1695`):

| AddressLib ID | Name | Verified Role in `PR #780` |
|---:|---|---|
| `43207` | `UICellRenderer_InventoryItem.ctor` | Allocates `0x190` (16-byte aligned) item renderer in a cell; takes `ProbeSceneParams{scale=-1.0f, fov=0.0f, BSFixedString name, view=0xFFFFFF, zero=0}` (`sizeof == 0x18`). |
| `43209` | `UICellRenderer_InventoryItem.dtor` | Destroys renderer before `IMenu` destruction. |
| `43211` | `UICellRenderer_InventoryItem.RequestModel` | Requests a `TESForm*` (`mode = 2`) into the offscreen cell. |
| `44195` | `IMenu.scenes.Push` | Appends `renderer + 0x60` (`BSMenu3D::Scene` shared ptr) onto `IMenu + 0x98` so `ScaleformToTextureRenderPass` discovers the menu's scene. |
| `140022` | `BSMenu3D.Scene.CreateTexture` | Allocates render texture at `scene + 0x08` from a 12-qword descriptor; texture readiness is in `texture + 0x14` bits `28..30` (`2` = making, `3` = ready, `4` = ready/taken, `5` = failed). |
| `130595` | `BSMenu3D.Scene.BindDisplayShape` | Takes `ProbeBindArgs{const BSFixedString* prefix, bool* ok, uintptr_t scene}` and a `BSGeometry*`, binding the scene's render texture onto matching display geometry. |
| `909463` | `MenuDataSlate3DRenderCell_DO` | DefaultObject whose `+0x48` holds the `TESObjectCELL*` used by `DataSlateMenu` 3D rendering. |
| `47401` | `TESForm.LookupByID` | Looks up form by FormID (`TESObjectBOOK` in `#780`). |
| `43215` | `UICellRenderer_InventoryItem.Update` | `bool(renderer*, float dt)`, called per frame from `IMenu` slot `0x0B` (`void(IMenu*, float dt, uint64_t)`) when `IMenu::flags & 0x40` and `menu + 0xCD..0xCE` are non-zero. |

### 1.3 Why `PR #780` Stops Short of the Worn Wrist Pip-Boy

`PR #780` (`README.md:456-462`) explicitly documents two boundaries:
1. **Off-world `MenuDataSlate3DRenderCell_DO` vs. Player Skeleton:** `#780` spawns a separate `TESObjectCELL` (`909463`) and loads a standalone `TESObjectBOOK` model (`dataslate01.nif` with `Display:4`) inside `BSMenu3D::Scene`. It explicitly notes: *"Shapes outside the menu scene (a world object, the player's first-person hands). The probe has no way yet to..."*
2. **Post-update camera/view setup & 2D suppression:** `#780` did not yet determine which `IMenu::flags` (e.g., `DataSlateMenu`'s flags from `World=1` census) suppress fullscreen 2D compositing of `uiMovie` so `ScaleformToTextureRenderPass` draws *only* into the offscreen texture.

---

## 2. What `I2(a)` & `I2(c)` Already Provide for `3d_rtt`

1. **Deterministic Target Geometry (`PipboyScreen`):** Every staged wrist NIF (`pipboy_wrist_housing_{m,f,1st,1st_f}.nif` and `pipboy_wrist_screen_{m,f,1st,1st_f}.nif`) has **exactly one** `BSGeometry` named `PipboyScreen`, rigidly weighted (`1.0`) to `L_Wrist_Twist2` (slot 3) with full `[0,1]x[0,1]` UVs matching `FO4SF_Fo4Shell.swf` (`876 x 700`).
2. **Non-Occluded Worn Slot (`bit 55`):** `FO4SF_PipboyWrist` (`0x80D`) and its single combined ARMA (`0x823`, `FO4SF_PipboyWristAA`) sit on bit 55 only (`0x0080000000000000`), completely off bit 54 (`SSChronoMark`), so spacesuits (`1E2B18`) no longer collide with or hide the wrist device.
3. **Runtime Dispatch & Fallback Seam (`pipboy_screen_source.h` + `main.cpp`):**
   - `ScreenSource=2d_imenu|3d_rtt` in `FO4SFPipboyMenu.ini` (default `2d_imenu`), overridden by `FO4SF_PipboyScreenSource` (`FO4SFCoreValues.esm:0x000868`: `0` = follow INI, `1` = force 2D, `2` = force 3D).
   - `OpenPipboyScreenViaSource` attempts `OpenPipboy3DRTTMainThread()` when `3d_rtt` is requested; any `false` return falls back automatically to `2d_imenu` (`fellBackTo2D = true`, `reason = "fallback_2d_imenu"`), logging `step=pipboy_screen wrist_draw=none|static|rtt`.

---

## 3. Smallest Concrete `3d_rtt` Probe Proposal (`PipboyScreen`)

To bridge `FO4SF_PipboyMenu` (`FO4SF_Fo4Shell.swf`) onto the player's worn `PipboyScreen` behind `ScreenSource=3d_rtt` without risking the `2d_imenu` baseline:

### Probe Phase A — Live `PipboyScreen` Node Lookup & Texture Bind Test (Read-Only + Single Bind Call)

1. **Menu Open (`OpenPipboy3DRTTMainThread`):**
   - Require `g_stage == 2 && !g_movie.empty()` (`FO4SF_Fo4Shell`) and verify the 9 `#780` AddressLib IDs (`44195`, `140022`, `130595`, etc.) plus `PlayerCharacter` 1P/3P `NiAVObject` root lookup (`loadedData->data3D` at `+0xB8/+0x08` for 3P, or first-person `NiNode` via `PlayerCharacter` RTTI check).
   - If any ID or RTTI check fails, log `refuse step=pipboy_rtt what=<check>` and return `false` (`OpenPipboyScreenViaSource` opens flat `2d_imenu`).
2. **Locate `PipboyScreen` on the Player's Loaded 3D:**
   - Walk the player's loaded 1P (and/or 3P) `NiNode` hierarchy (`kProbeNodeChildrenAt = 0x138`, `kProbeNodeCountAt = 0x142`, RTTI `BSGeometry@@` check) for `name == "PipboyScreen"`.
   - Log `step=pipboy_rtt_node view=1p|3p found=<0|1> geom=<addr>`. (Complements Papyrus `HasNode("PipboyScreen")` added in `I2(d)`.)
3. **Create `BSMenu3D::Scene` + Render Texture (`876 x 700` or `1024 x 1024`):**
   - Push a `BSMenu3D::Scene` named `FO4SF_PipboyMenu` onto `IMenu + 0x98` (`44195`) and allocate the render texture via `140022` (`BSMenu3D.Scene.CreateTexture`) without spawning `MenuDataSlate3DRenderCell_DO` (since the geometry already lives in the world on the player's wrist).
   - Once `texture + 0x14` reaches phase `3` or `4` (`usable == 1`), invoke `130595` (`BSMenu3D.Scene.BindDisplayShape`) passing prefix `"PipboyScreen"`, `&ok`, `scene`, and the player's `PipboyScreen` `BSGeometry*`, logging `step=pipboy_rtt_bind result=<0|1>`.
4. **Verify What `130595` + `ScaleformToTextureRenderPass` Needs:**
   - **Case 1 (`BindDisplayShape` returns `1` and `uiMovie` renders onto `PipboyScreen`):** Confirm via `World=1` census flags (`DataSlateMenu`'s `IMenu::flags` bitmask) which flag bit disables the fullscreen 2D pass while keeping `ScaleformToTextureRenderPass` active. Add that flag only when `wrist_draw=rtt` succeeds.
   - **Case 2 (`BindDisplayShape` returns `0` or requires `BSMenu3D::Scene` ownership):** Check `130595` disassembly/behaviour on why `BindDisplayShape` inspects `BSLightingShaderProperty` / `BSMaterial` on `PipboyScreen` (e.g., whether `pipboy_screen_2d.mat` needs a specific shader/decal property like `Dataslate_Screen01.mat`, or whether `PipboyScreen`'s shader texture slot `0`/`7` can be pointed to the `BSMenu3D` render texture directly).
   - **Case 3 (Watchdog/Fallback):** If texture creation or `BindDisplayShape` fails or stalls past a bounded timeout, tear down the `BSMenu3D::Scene` entry and return `false` so `2d_imenu` opens cleanly with zero blank screen.

### Minimal Acceptance Criteria for That Probe (Future PC Card)

- With `ScreenSource=2d_imenu` (shipped default): zero probe IDs loaded, `step=pipboy_screen wrist_draw=static` (when wrist worn), identical behavior to `candidate-2h-3`.
- With `ScreenSource=3d_rtt`:
  - `step=pipboy_rtt_node ... found=1`
  - `step=pipboy_rtt_bind result=1`
  - `step=pipboy_screen wrist_draw=rtt` (or `fallback_2d_imenu` -> `wrist_draw=static` if any gate refuses), zero crash on open/tab/close/save/reload.
