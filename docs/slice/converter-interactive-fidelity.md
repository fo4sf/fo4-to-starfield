# Converter Interactive Fidelity (`CF-5` Part 1)

## Overview

`CF-5` part 1 restores five interactive placement subrecord families previously stripped or partially dropped during Fallout 4 -> Starfield cell and worldspace conversion:

1. **`XESP` (Enable Parent & Initial Visibility):** Remaps `PlacedObject.EnableParent` (`Reference` + `SetEnableStateToOppositeOfParent` `0x01` and `PopIn` `0x02` flags) across placed references and recreated invisible control markers (`STAT` `0x010D8D` `EnableMarker`, `0x00003B` `XMarker`, `0x000034` `XMarkerHeading`, `0x0001F7` `LightBox`). When a parent or ancestor reference is outside converted scope (such as a deferred `ACHR` or unconverted trigger), the recursive effective initial enable state (`parent_disabled ^ opposite`) is folded directly into `MajorRecordFlagsRaw` bit `0x00000800` (`InitiallyDisabled`) so opposite-state props never double-spawn enabled on cell load.
2. **`XLOC` (Locks on `DOOR`, `CONT`, and `TERM`):** Preserves `PlacedObject.Lock` (`LockData`: `Novice1` `1`, `Novice25` `25`, `Advanced` `50`, `Expert` `75`, `Master` `100`, `RequiresKey` `255`, and `LeveledLock` flag `0x01`) across doors, promoted containers, and promoted terminals. Converted `KEYM` records remap through `formids.json`; pickable locks (`1..100`) whose source `KEYM` is not yet converted fall back cleanly to `Key = Null` so they remain pickable in Starfield, while unmapped `RequiresKey` (`255`), non-translated `251..254` (`Barred` / `Chained` / `RequiresTerminal` / `Inaccessible`), and `level = 0` Creation Kit stubs are skipped so no unopenable softlock is created.
3. **`XLKR` (Linked References):** Remaps `(KeywordOrReference, Reference)` pairs across placed references and recreated control markers. Generic Fallout 4 `KYWD` records (`Type == None`, `record_flags == 0`, `AttractionRule == Null`) are emitted deterministically with `EditorID` and `Color` only (zero `Name` or `Notes` game text). Fallout 4 `MultirefLOD` (`0x195411`) and dangling unplaced target references are skipped cleanly without crashing or emitting unresolved links.
4. **`XAPR` / `XAPD` (Activate Parent Chains, Delays & `ParentActivateOnly`):** Starfield `1.16.244` contains `0` `XAPD` / `XAPR` subrecords across all `REFR` records in `Starfield.esm`, and binary validation rejects raw `XAPD` / `XAPR` subrecords on `REFR`. Activation chains are therefore carried in Starfield's native `VMAD` format via `scripts/slice/FO4SF_ActivateChain.psc` (`FO4SF_ActivateChain extends ObjectReference`):
   - Multi-child fanout (`ObjectReference[] Targets`), per-edge delays (`float[] Delays`), and child unblock flags (`bool[] UnblockTargets`) are attached to each placed parent (appending without clobbering existing scripts such as `FO4SF_LoadDoor`, and upgrading legacy single-target `DefaultActivateLinkedRefOnActivate` wires without double-firing).
   - Children flagged `ParentActivateOnly` (`XAPD` bit `0x01`) that have at least one placed parent receive `ParentActivateOnly = True` (`Self.BlockActivation(True, False)` on `OnInit` / `OnCellAttach` / `OnLoad`), temporarily unblocked when triggered by their parent.
5. **`XTEL` (Load-Door Teleports & Navmesh Door Triangles):** Preserves `TeleportDestination` (`Door`, `Position / 70`, `Rotation`, `Flags` `0x01..0x03`, persistent `0x400` endpoints) between placed `DOOR` records, supports `--port-reference` cross-cell `DOOR` endpoint resolution during single-cell re-conversions, recreates connected `AutoloadDoor` (`0x01ED77` -> `0x24F9CE:Starfield.esm` `AutoloadDoor_Cave`) pairs when both endpoint cells are converted, preserves existing `FO4SF_LoadDoor` / `FO4SF_AnimatedLoadDoor` scripted bridges, and validates `NavmeshGeometry.DoorTriangles`.

### Worldspace & Vault 111 Exit Safety Invariants

- **Zero exterior grid persistent children:** In Starfield planetary overlay worldspaces (`FO4Core_Commonwealth`), exterior grid `REFR` overrides remain in `gridCell.Temporary` (preserving the `(-1200, -2700)` m runtime merge offset), while recreated exterior control markers and `AutoloadDoor_Cave` endpoints are placed exclusively in `Worldspace.TopCell.Persistent` (`0x400`). `FidelityCheck` rejects any plugin with `Persistent.Count > 0` on an exterior grid cell.
- **Vault 111 exit isolation:** Only base `0x01ED77` (`AutoloadDoor`, `Flags == Automatic`) is recreated as `AutoloadDoor_Cave`. `0x062624` (`AutoloadDoorNoText` on `0x01F180` at the top of the Vault 111 shaft) and `Hidden` / `MinimalUse` elevator doors (`0x248AAD`) are excluded so `FO4SF_NewGameQuest`'s shaft ascent and merged Commonwealth arrival remain untouched.

---

## Implementation Surfaces

- **`dotnet/PluginSpike` (`InteractiveFidelity.cs`, `Program.cs`):** Opt-in `--interactive-fidelity` (and `--port-reference=<FO4Port.esm>`) pass during direct interior cell conversion, writing `<out>/interactive_fidelity.json` alongside `<out>/FO4Port.esm` while leaving default flagless `PluginSpike` builds unchanged.
- **`dotnet/InteractiveFidelity` (`OverlayBuilder.cs`, `FidelityCheck.cs`, `SelfTest.cs`):** Builds and checks `FO4SFInteractiveFidelity.esm` (ride-along overlay mastering `Starfield.esm`, `FO4TerrainCore.esm`, and `FO4Port.esm`) across both interior and exterior cells, plus offline `ImmutableLinkCache` verification (`check`) and synthetic positive + negative mutation tests (`selftest`).
- **`scripts/slice/FO4SF_ActivateChain.psc`:** Runtime `ObjectReference` script executing `XAPR` multi-target fanout, delays, and `ParentActivateOnly` blocking.
- **`scripts/slice/make_interactive_fidelity.py`:** Unified CLI driver providing `precheck`, `reconvert`, `stage`, `fold`, `verify`, and `diff-counts` (`measure`).

---

## Measured Before & After Counts (`CF-5` Target Cells)

Measured offline against `Fallout4.esm`, `Starfield.esm`, `FO4TerrainCore.esm`, and `FO4Port.esm` across the four target locations (`16` converted cells / `20,420` active `REFR` records total; counts, hex FormIDs, and 100 m Starfield exterior grids only):

### Summary by Target Location

| Group | Target Cells (`FO4Port.esm` / Exterior Grid) | `XESP` (`B -> A`) | `XLOC` (`B -> A`) | `XLKR` (`B -> A`) | `XAPR` (`B -> A`) | `XTEL` (`B -> A`) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `vault_111` | `0x0011F3`, `ext(-13,12)`, `ext(-13,13)` | `0 -> 24 (+24)` | `0 -> 0 (+0)` | `0 -> 31 (+31)` | `0 -> 0 (+0)` | `0 -> 0 (+0)` |
| `red_rocket` | `0x002338`, `ext(-10,11)`, `ext(-11,11)` | `0 -> 2 (+2)` | `0 -> 1 (+1)` | `0 -> 22 (+22)` | `1 -> 1 (+0)` | `0 -> 2 (+2)` |
| `concord` | `ext(-9,10)`, `ext(-9,9)`, `ext(-8,10)`, `ext(-10,10)`, `ext(-9,11)` | `0 -> 1 (+1)` | `0 -> 4 (+4)` | `0 -> 0 (+0)` | `0 -> 0 (+0)` | `0 -> 0 (+0)` |
| `fort_hagen` | `0x00BA4B`, `0x00CFC6`, `ext(-13,-2)`, `ext(-13,-1)`, `ext(-12,-2)` | `0 -> 40 (+40)` | `0 -> 8 (+8)` | `0 -> 48 (+48)` | `0 -> 7 (+7)` | `2 -> 2 (+0)` |
| **Total** | **16 cells (`4` interior + `12` exterior)** | **`0 -> 67 (+67)`** | **`0 -> 13 (+13)`** | **`0 -> 101 (+101)`** | **`1 -> 8 (+7)`** | **`2 -> 4 (+2)`** |

> [!NOTE]
> - In `vault_111` (`0x0011F3`, source `0x0016D8`), the `3` source `XLOC` records use lock levels `253` / `254` (`RequiresTerminal` / `Inaccessible`) and are intentionally left unlocked so doors are not softlocked; `15` of the `24` preserved `XESP` records carry `SetEnableStateToOppositeOfParent` (`0x01`).
> - In `red_rocket`, `ext(-11,11)` already carried `1` legacy single-target `DefaultActivateLinkedRefOnActivate` wire (`1 -> 1`), which is upgraded in place to `FO4SF_ActivateChain` with its source delay preserved (`0 -> 1` delayed edge), while `0x002338` (`0x05E62F`) <-> `ext(-10,11)` gains its mutual `0x05E844 <-> 0x08EB65` `XTEL` pair (`0 -> 2`).
> - In `concord`, the `11` exterior load doors in `ext(-9,10)` target interior cells not yet present in `FO4Port.esm`, so they remain shut with `0` dangling `XTEL` links.
> - In `fort_hagen`, both existing native `XTEL` links (`0x0CD469 <-> 0x0CD46A` between `0x00BA4B` and `0x00CFC6`) and all `6` existing `FO4SF_*LoadDoor` interior/exterior scripted bridges (`3` interior + `3` in `ext(-13,-1)`) are preserved alongside `+40` `XESP`, `+8` `XLOC`, `+48` `XLKR`, and `+7` `XAPR` edges.

### Per-Cell Breakdown

| Group | Kind | Target ID | Source Cell | `XESP` (`B -> A`) | `XLOC` (`B -> A`) | `XLKR` (`B -> A`) | `XAPR` (`B -> A`) | `XTEL` (`B -> A`) | Scripted Doors (`B -> A`) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `vault_111` | `CELL_INT` | `FO4Port.esm:0011F3` | `0x0016D8` | `0 -> 24` | `0 -> 0` | `0 -> 31` | `0 -> 0` | `0 -> 0` | `0 -> 0` |
| `vault_111` | `CELL_EXT` | `ext(-13,12)` | grid `(-13, 12)` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` |
| `vault_111` | `CELL_EXT` | `ext(-13,13)` | grid `(-13, 13)` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` |
| `red_rocket` | `CELL_INT` | `FO4Port.esm:002338` | `0x05E62F` | `0 -> 0` | `0 -> 1` | `0 -> 0` | `0 -> 0` | `0 -> 1` | `0 -> 0` |
| `red_rocket` | `CELL_EXT` | `ext(-10,11)` | grid `(-10, 11)` | `0 -> 1` | `0 -> 0` | `0 -> 9` | `0 -> 0` | `0 -> 1` | `0 -> 0` |
| `red_rocket` | `CELL_EXT` | `ext(-11,11)` | grid `(-11, 11)` | `0 -> 1` | `0 -> 0` | `0 -> 13` | `1 -> 1` | `0 -> 0` | `0 -> 0` |
| `concord` | `CELL_EXT` | `ext(-9,10)` | grid `(-9, 10)` | `0 -> 0` | `0 -> 1` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` |
| `concord` | `CELL_EXT` | `ext(-9,9)` | grid `(-9, 9)` | `0 -> 0` | `0 -> 1` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` |
| `concord` | `CELL_EXT` | `ext(-8,10)` | grid `(-8, 10)` | `0 -> 1` | `0 -> 1` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` |
| `concord` | `CELL_EXT` | `ext(-10,10)` | grid `(-10, 10)` | `0 -> 0` | `0 -> 1` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` |
| `concord` | `CELL_EXT` | `ext(-9,11)` | grid `(-9, 11)` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` | `0 -> 0` |
| `fort_hagen` | `CELL_INT` | `FO4Port.esm:00BA4B` | `0x0BB078` | `0 -> 7` | `0 -> 3` | `0 -> 16` | `0 -> 4` | `1 -> 1` | `2 -> 2` |
| `fort_hagen` | `CELL_INT` | `FO4Port.esm:00CFC6` | `0x0CD2AE` | `0 -> 33` | `0 -> 2` | `0 -> 16` | `0 -> 0` | `1 -> 1` | `1 -> 1` |
| `fort_hagen` | `CELL_EXT` | `ext(-13,-2)` | grid `(-13, -2)` | `0 -> 0` | `0 -> 3` | `0 -> 3` | `0 -> 3` | `0 -> 0` | `0 -> 0` |
| `fort_hagen` | `CELL_EXT` | `ext(-13,-1)` | grid `(-13, -1)` | `0 -> 0` | `0 -> 0` | `0 -> 12` | `0 -> 0` | `0 -> 0` | `3 -> 3` |
| `fort_hagen` | `CELL_EXT` | `ext(-12,-2)` | grid `(-12, -2)` | `0 -> 0` | `0 -> 0` | `0 -> 1` | `0 -> 0` | `0 -> 0` | `0 -> 0` |

---

## PC Card — Single-Cell Re-Conversion & Count Diff

Run offline (game closed) using your local tool and staging paths (`<PYTHON_EXE>`, `<FO4_DATA>`, `<SF_DATA>`, `<PORT_DIR>`, `<CORE_DIR>`, `<CONTENT_ZIP>`, `<PAPYRUS_COMPILER>`, `<STAGE>`):

### 1. Re-Convert One Cell (`0x000BB078` -> `FO4Port.esm:0x00BA4B`) and Diff Counts

Cell `0x000BB078` exercises all five subrecord families in a single interior conversion (`XESP`, `XLOC`, `XLKR`, `XAPR`, and cross-cell `XTEL` resolved against `<PORT_DIR>/FO4Port.esm`):

```powershell
<PYTHON_EXE> scripts/slice/make_interactive_fidelity.py reconvert `
  --fo4 <FO4_DATA>/Fallout4.esm `
  --starfield <SF_DATA>/Starfield.esm `
  --port-dir <PORT_DIR> `
  --cell 0x000BB078 `
  --out <STAGE>/reconvert-000BB078
```

Expected output lines (exit `0`):

```text
PASS  esm master flag: Master
PASS  masters resolvable in load order: Starfield.esm
PASS  keywords free of game text: 2 keywords clean
PASS  exterior grid cells have zero persistent children: 0 exterior grid persistent refs
PASS  XESP enable parents valid: 7 XESP records verified
PASS  XLOC locks valid and openable: 3 XLOC records verified
PASS  XLKR linked references resolved: 16 XLKR pairs verified
PASS  XAPR activation chains valid: 4 XAPR edges verified
PASS  XTEL teleport links valid: 1 XTEL doors verified
PASS  NAVM door triangles resolved: 0 NAVM door triangles verified
all 10 checks pass
...
PASS  reconvert 0x0BB078 -> FO4Port.esm:0x00BA4B: XESP=+7, XLOC=+3, XLKR=+16, XAPR=+4, XTEL=+0
```

You can also run `diff-counts` standalone against any before/after `.esm` pair:

```powershell
<PYTHON_EXE> scripts/slice/make_interactive_fidelity.py diff-counts `
  --before <PORT_DIR>/FO4Port.esm `
  --after <STAGE>/reconvert-000BB078/FO4Port.esm `
  --cells FO4Port.esm:00BA4B `
  --require-positive-delta `
  --out <STAGE>/reconvert-000BB078/manual_diff.json
```

Expected final line (exit `0`):

```text
PASS  diff-counts: XESP=+7, XLOC=+3, XLKR=+16, XAPR=+4, XTEL=+0
```

---

### 2. Stage, Fold into a Core Set, and Verify (`FO4SFInteractiveFidelity.esm`)

To stage the full multi-cell interactive-fidelity overlay (`FO4SFInteractiveFidelity.esm` + `Data/Scripts/FO4SF_ActivateChain.pex`) and fold it into a core experiment directory without mutating any hardlinked `README.txt` in place:

```powershell
<PYTHON_EXE> scripts/slice/make_interactive_fidelity.py precheck `
  --content-resources <CONTENT_ZIP> `
  --out <STAGE>/precheck.json

<PYTHON_EXE> scripts/slice/make_interactive_fidelity.py stage `
  --out <STAGE>/stage `
  --fo4 <FO4_DATA>/Fallout4.esm `
  --starfield <SF_DATA>/Starfield.esm `
  --port <PORT_DIR>/FO4Port.esm `
  --port-ids <PORT_DIR>/formids.json `
  --core <CORE_DIR>/FO4TerrainCore.esm `
  --core-ids <CORE_DIR>/formids.json `
  --compiler <PAPYRUS_COMPILER> `
  --content-resources <CONTENT_ZIP>

<PYTHON_EXE> scripts/slice/make_interactive_fidelity.py fold `
  --stage <STAGE>/stage `
  --core-dir <CORE_DIR> `
  --out <STAGE>/folded-set `
  --port <PORT_DIR>/FO4Port.esm

<PYTHON_EXE> scripts/slice/make_interactive_fidelity.py verify `
  --exp-dir <STAGE>/folded-set `
  --plan <STAGE>/stage/plan.json `
  --port <PORT_DIR>/FO4Port.esm
```

*(If `<CORE_DIR>` already contains an earlier `FO4SFInteractiveFidelity.esm`, pass `--clean-prior` to `fold`.)*

Expected output lines (exit `0`):
- `precheck: ok`
- `all 10 checks pass`
- `folded <STAGE>/folded-set: FO4SFInteractiveFidelity.esm + 1 script(s); verify: ok`
- `verify: ok`

---

### 3. Optional In-Game Spot Checks (Only When Game Access Is Authorized)

After installing `<STAGE>/folded-set` with `exp_install.py` (game closed, using the exact `--plugins ...,FO4SFInteractiveFidelity.esm --pack` line printed by `fold`):

1. **`XLOC` lock prompt (`FO4Port.esm:002338` / `0x00BA4B`):** Enter `FO4Port.esm:00BA4B` or `FO4Port.esm:002338` and inspect one of the locked `DOOR` / `CONT` references; confirm Starfield displays the native digipick lock prompt at the expected lock tier (`Novice` / `Advanced` / `Expert`) and opens cleanly when picked.
2. **`XESP` opposite-state props (`FO4Port.esm:0011F3` / `0x00BA4B`):** Confirm the `15` opposite-enable (`0x01`) references in `0x0011F3` and `5` in `0x00BA4B` start hidden rather than overlapping enabled geometry.
3. **`XAPR` switch chain (`FO4Port.esm:00BA4B` / `ext(-11,11)`):** Activate a wired parent activator / button and confirm `FO4SF_ActivateChain` triggers its linked target door(s) once (no double-toggle on `ext(-11,11)`).
4. **`XTEL` transition (`FO4Port.esm:002338` <-> `ext(-10,11)` and `0x00BA4B` <-> `0x00CFC6`):** Walk into `0x05E844` inside `0x002338` (or `0x0CD469` inside `0x00BA4B`) and confirm clean native `XTEL` transition to the paired cell.
