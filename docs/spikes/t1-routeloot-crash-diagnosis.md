# T1 Diagnosis: `FO4SFRouteLoot.esm` Exterior Arrival Crash (`0x1F0`)

## Status
- **Live game reproduction (Candidate 2c):** **Verified (`2/2` crash ON, `2/2` clean OFF)** — Warfare arrival near Sanctuary Hills crashed `2/2` runs ~5 s after `warfare gear n=4` at `Starfield.exe+0x41efd6` reading `[null + 0x1F0]` when `FO4SFRouteLoot.esm` was active, and landed cleanly `2/2` runs (`warfare move ok=true`, `stage 210`) when only `FO4SFRouteLoot.esm` was toggled off.
- **Pointer member at `+0x1F0`:** **Verified** in `CommonLibSF` (`RE/T/TESWorldSpace.h`, `RE::TESWorldSpace`): offset `+0x1F0` is `TESWorldSpace::lightingTemplate` (`BGSLightingTemplate*`), immediately above `TESWorldSpace::parentWorld` (`+0xE0`).
- **Root-cause mechanism:** **Supported hypothesis (pending 1-session `bases-only` vs `ext-overrides-only` split run)** — secondary-plugin exterior `WRLD` + grid `CELL` overrides over the planet-overlaid `FO4Core_Commonwealth` worldspace (`FO4TerrainCore.esm` + `FO4TerrainCore_Mars.esm`) attach with a null runtime `TESWorldSpace*`, matching the `FAL-273` Run 4 `cell-only` control (`src/fo4sf/plugin_verify.py`).

## Offline Record Audit of `FO4SFRouteLoot.esm`
1. **Dedicated `CONT` base records (`0x000820..0x000872`, `83` records):**
   - Every record duplicates an existing non-deleted `FO4TerrainCore.esm` `CONT` base, keeps its exact NIF path, clears scripts, and populates `Items` solely from verified `Starfield.esm` (`WEAP`, `AMMO`, `MISC`) and `FO4SFCoreValues.esm` (`ALCH`) masters.
   - `0` `LVLI` leveled lists, `0` `TPLT` templates, `0` missing models, and `0` FormID collisions (`0x000800..0x000872` are owned by `FO4SFRouteLoot.esm`).
2. **Vault 111 interior records (`CELL 0x0011F3` in `FO4Port.esm`, `CONT 0x000800`, `REFR 0x000801..0x000807`):**
   - Present in the earlier interior-only `FO4SFRouteLoot.esm` build before `B10`, which ran without an exterior cell-load crash, and uninvolved in the Warfare Sanctuary arrival (which never loads `0x0011F3`).
3. **Exterior worldspace & grid cell overrides added in `B10` (`WRLD 0x000802`, `TopCell 0x001805`, `88` exterior grid `CELL`s, `460` corridor `REFR` overrides):**
   - All `460` overridden `REFR` FormKeys exist in `FO4TerrainCore.esm` (`4` persistent in `TopCell`, `456` temporary across `88` grid cells within `<= 600 m` of the Sanctuary-to-Concord polyline).
   - However, overriding exterior grid `CELL` records of `FO4TerrainCore.esm` from a secondary plugin reproduces the `FAL-273` Run 4 failure mode: when exterior grid cells stream in around Sanctuary ~5 s after `SetPosition`, the cell attach path reads `worldspace->lightingTemplate` (`[rdi + 0x1F0]`) on a null `TESWorldSpace*`.

## One-Session Split Build & Player-Bundle Gate
- `dotnet/RouteLoot/Program.cs` and `scripts/loot/make_route_loot.py` now support `--split full|bases-only|ext-overrides-only` (default `full`):
  1. **`--split bases-only`** (masters: `Starfield.esm`, `FO4SFCoreValues.esm`, `FO4SFRads.esm`, `FO4SFWorkshop.esm`, `FO4Port.esm`): writes all `83` dedicated `CONT` bases + the Vault 111 interior armory, with **`0` `WRLD`, `0` exterior `CELL`, and `0` exterior `REFR` overrides**.
  2. **`--split ext-overrides-only`** (masters: `Starfield.esm`, `FO4TerrainCore.esm`): writes **only** the `WRLD` + exterior `CELL` + `460` corridor `REFR` overrides pointing at their original `FO4TerrainCore.esm` `CONT` bases, with **`0` `CONT` records and `0` interior `CELL` records**.
- Until proven in game, `scripts/core/make_core_bundle.py` omits `FO4SFRouteLoot.esm` from `PLAYER_BUNDLE_PLUGINS` (`21` plugins on `--profile player`; opt-in via `--with-route-loot` only), and `verify_bundle` refuses any default `player` bundle that includes `FO4SFRouteLoot.esm`.
