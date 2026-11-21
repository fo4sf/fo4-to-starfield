# Fort Hagen Elevators and Roof Gate Controller

Status: **staged and verified offline (`dotnet/FortHagen` + `FO4SF_FortHagenQuest.pex`); PC in-game run belongs to Claude (PC).**

## 1. Binary Findings Across Both Fort Hagen Systems

Fort Hagen uses two distinct elevator mechanisms plus a roof security gate. Binary inspection of the source records and the converted `FO4Port.esm` / `FO4TerrainCore.esm` plugins established the exact state of each:

### System 1: Interior Two-Stop Shaft in `FO4Port_FortHagen01` (`0x00BA4B`)

1. **Controller and moving platform helper omitted:** Source controller `00134462` (`ElevatorMaster`, carrying `elevatormasterscript` with `bStartDeactivated = True`) and moving platform helper `00134467` (`platformhelperfree01`) are marker/helper activators and are not placed in `FO4Port.esm`.
2. **Stripped scripts, links, and `XESP` enable parents:**
   - Car `00134461` -> `REFR 0x00C580` (`STAT 0x000BF8` `FO4Port_UtilElevatorCar01`) is placed as an immobile static at the lower landing (`[-10.971, 69.486, -3.657] m`). Behind upper outer door `0x00C7AC` (`z = +3.657 m`) there is no upper car floor, leaving an open `4.28 m` drop onto the car roof (`z = -0.625 m`).
   - Upper call button `0x00C7AF` (`z = +4.905 m`), lower call button `0x00C7AD` (`z = -2.405 m`), and inner lift panel `0x00C7AE` (`z = -2.405 m`) are unscripted `ACTI` records (`VMAD` and `XLKR` stripped).
   - Upper outer door `0x00C7AC`, lower outer door `0x00C7B4`, and inner car door `0x00C7AB` are rigged `DOOR` records (`SimpleOpenClose01.agx`) with no controller links.
   - Because `XESP` enable-parent records are stripped, wooden planks `0013A357` -> `REFR 0x00C641` (`STAT 0x0010BE` at `[-10.971, 67.429, +5.029] m`) spawn enabled directly across upper doorway `0x00C7AC`, and pre-stage blocker door/boards (`0x00C7A8`, `0x00C13A`) coexist in the same doorway as post-stage basement door `0x00C7B8`. Maintenance switch `0x00C7B0` (`0013446A`, `DisableOnLoad = True` in source) also spawns enabled.
   - Non-elevator load door `000CD469` -> `0x00C7A7` <-> `0x00DE51` already connects `FO4Port_FortHagen01` and `FO4Port_FortHagen02` via native `XTEL`.

### System 2: Command Center (`FO4Port_FortHagen02` `0x00CFC6`) <-> Exterior Roof (`Ext(-13,-1)` `0x000CE3`)

1. **No quest lock on the load elevator:** All four `LoadElevatorPanelScript` buttons and panels (`00168509`, `0016850C`, `00168528`, `0016852B`) inherit `bStartDeactivated = False` from their base script default; quest stage gating is ruled out.
2. **Cross-plugin load-door bridge already present:**
   - Interior `0016850D` -> `FO4Port.esm:0x00DE53` (`DOOR 0x00DE5E`, `SimpleOpenClose01.agx`) carries `FO4SF_AnimatedLoadDoor` targeting persistent `XMarker` `FO4TerrainCore.esm:0x0A774C` at merged `(-2470.491, -2774.755, 95.086) m`. Outer sliding door `0x00DE52` sits `1.828 m` in front of `0x00DE53`; call button `0x00DC5F` and inner panel `0x00DC62` have stripped `VMAD` / `XLKR`.
   - Exterior roof `0016852C` -> `FO4TerrainCore.esm:0x0547B0` (`ACTI 0x0A7757`) carries `FO4SF_LoadDoor` targeting persistent `XMarker` `FO4Port.esm:0x00E182` at `(19.958, 1.334, -10.971) m`. Outer sliding door `0x0547B1` (`DOOR 0x002C08`, `SimpleOpenClose01.agx`) sits `1.828 m` in front of `0x0547B0`; roof call button `0x0547AC` and inner panel `0x0547AF` are unscripted `ACTI` records.
3. **Roof headhouse security gate blocker:**
   - Exiting `0x00DE53` lands the player at `(-2470.491, -2774.755, 95.086) m` inside the fenced roof headhouse.
   - Security gate `000BF414` -> `FO4TerrainCore.esm:0x0232E1` (`ACTI 0x0A2D9C`, static-converted NIF with `bhkNPCollisionObject` and no animation graph) sits closed across `(-2470.400, -2781.432, 95.086) m`, and wall terminal `000BF413` -> `0x0232E0` (`TERM 0x0A2E3F`) has stripped `VMAD` / `XLKR`, trapping the player inside the cage.

---

## 2. Non-Invasive Runtime Controller (`FO4SFFortHagen.esm`)

To unblock both Fort Hagen elevator paths and the roof exit without rewriting pinned `FO4Port.esm` or `FO4TerrainCore.esm` records:

- **Plugin (`dotnet/FortHagen`):** Writes `FO4SFFortHagen.esm`, mastered on `Starfield.esm` only (`QUST 0x800` `FO4SF_FortHagenElevators`, `StartGameEnabled`, no `CELL`/`WRLD` overrides, hidden from HUD). `inspect`, `write`, and `check` verify all 24 Fort Hagen references, bases, persistent markers, and `FO4SF_AnimatedLoadDoor` / `FO4SF_LoadDoor` VMAD bindings against `FO4Port.esm` and `FO4TerrainCore.esm`.
- **Runtime quest (`scripts/fort_hagen/FO4SF_FortHagenQuest.psc`):**
  - Resolves references when the player enters each zone using `Game.GetFormFromFile` first and `Game.FindClosestReferenceOfType(baseForm, x, y, z, 2.5)` as a coordinate-verified fallback so merged planet-overlay runtime `FF00xxxx` instances resolve identically to direct `01xxxxxx` references.
  - **Zone 1 (`FO4Port_FortHagen01`, detected via persistent COC marker `0x00C5E3`):**
    - Disables stripped-`XESP` planks `0x00C641`, duplicate pre-stage blocker door/boards `0x00C7A8` + `0x00C13A`, and maintenance switch `0x00C7B0`.
    - Activating upper call button `0x00C7AF` or upper outer door `0x00C7AC` opens `0x00C7AC`, opens lower doors `0x00C7AB` + `0x00C7B4`, transfers the player into the lower car at `(-10.971, 69.000, -3.550) m` facing south (`180 deg`), and closes `0x00C7AC` so the player cannot step into the empty upper shaft.
    - Activating lower call button `0x00C7AD` opens lower doors `0x00C7B4` + `0x00C7AB`.
    - Activating inner lift panel `0x00C7AE` closes the lower doors, opens `0x00C7AC`, transfers the player onto the verified upper lobby floor tile (`0x00BEC9` at `(-10.971, 66.200, +3.750) m`, `1.46 m` south of `0x00C7AC`), and closes `0x00C7AC`.
  - **Zone 2 (`FO4Port_FortHagen02`, detected via persistent arrival marker `0x00E182`):**
    - Activating call button `0x00DC5F` opens outer sliding door `0x00DE52`.
    - Activating inner lift panel `0x00DC62` opens `0x00DE52` and dispatches `0x00DE53.Activate(player)` (`FO4SF_AnimatedLoadDoor` to roof). Direct activation of `0x00DE53` remains unchanged.
  - **Zone 3 (Exterior Roof within `80 m` of merged `(-2470.491, -2774.755, 95.086) m`):**
    - Activating roof terminal `0x0232E0` or roof security gate `0x0232E1` sets `roofGateOpened = True` and calls `Disable()` on the unrigged static gate `0x0232E1` (re-applied on subsequent roof visits).
    - Activating roof call button `0x0547AC` opens outer sliding door `0x0547B1`; activating roof inner panel `0x0547AF` dispatches `0x0547B0.Activate(player)` (`FO4SF_LoadDoor` back to `FO4Port_FortHagen02`).

---

## 3. PC Card for Claude (PC)

### Preconditions

- Game closed; active Commonwealth core (`FO4TerrainCore.esm`) and interior port (`FO4Port.esm`) installed.
- Stage and verify offline first:

```powershell
python scripts/fort_hagen/make_fort_hagen.py stage `
  --out <stage_dir> `
  --starfield <Starfield_Data>/Starfield.esm `
  --port <Starfield_Data>/FO4Port.esm `
  --core <Starfield_Data>/FO4TerrainCore.esm `
  --compiler <PapyrusCompiler.exe> `
  --content-resources <ContentResources.zip>

python scripts/fort_hagen/make_fort_hagen.py verify `
  --exp-dir <stage_dir> `
  --plan <stage_dir>/plan.json `
  --port <Starfield_Data>/FO4Port.esm `
  --core <Starfield_Data>/FO4TerrainCore.esm
```

- Fold/pack `FO4SFFortHagen.esm` and `Data/Scripts/FO4SF_FortHagenQuest.pex` alongside the active core + port set via `scripts/game/exp_install.py` (`--pack`) with `FO4SFFortHagen.esm` appended to `Plugins.txt`.

### In-Game Steps

1. Enter `FO4Port_FortHagen01` and walk to the upper elevator lobby (`z = +3.657 m`). Confirm wooden planks `0x00C641` across upper elevator door `0x00C7AC` are disabled automatically.
2. Activate upper call button `0x00C7AF`: confirm `0x00C7AC` opens and the player arrives inside the lower elevator car (`z ~ -3.55 m`) with lower doors `0x00C7AB` + `0x00C7B4` open, without falling down the shaft.
3. Activate inner car panel `0x00C7AE`: confirm the player returns cleanly to the upper hallway floor (`z ~ +3.75 m`) in front of `0x00C7AC`, then ride back down to the lower floor and walk through basement doorway `0x00C7B8` (unblocked by disabled `0x00C7A8` / `0x00C13A`) to native load door `0x00C7A7` into `FO4Port_FortHagen02`.
4. In `FO4Port_FortHagen02`, activate command-center call button `0x00DC5F` (outer door `0x00DE52` opens), then activate inner panel `0x00DC62` or load door `0x00DE53` to ride to the Fort Hagen exterior roof.
5. On the roof headhouse arrival (`(-2470.5, -2774.8, 95.1) m`), activate roof terminal `0x0232E0` (or security gate `0x0232E1`) and walk out onto the roof past the cleared gate; then activate roof call button `0x0547AC` and inner panel `0x0547AF` (or `0x0547B0`) to return to `FO4Port_FortHagen02`.

### Acceptance (`PASS` Criteria)

Run the log judge on `fo4sf_forthagen.0.log`:

```powershell
python scripts/fort_hagen/make_fort_hagen.py log --file <Logs/Script/User/fo4sf_forthagen.0.log>
```

`PASS` requires exit code `0` with:
- `fh01_ready: true` and `fh01_planks_cleared: true`
- `fh01_rode_down: true` and `fh01_rode_up: true`
- `fh_roof_gate_opened: true`
- Clean round-trip between `FO4Port_FortHagen02` and the exterior roof with zero `tcl` or console `disable` commands.
