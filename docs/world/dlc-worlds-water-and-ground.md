# DLC Terrain Worlds, Coastal Sea Water, and BTD Land-Texture Mapping

## 1. Starfield Coastal Overlay Sea-Water Records (`WRLD`, `SFBK`, `CELL`)

Vanilla dry Mars surface overlays such as `LC172World` (`0x02DF8C`) and `OverlayBlockLC172World` (`0x102382`) carry `WRLD.DNAM = (-2048.0, -200.0)`, `SFBK.WHGT = -FLT_MAX` (`-3.4028235e+38`), and omit water flags on exterior `CELL` records.

A raw record survey of coastal, island, and ocean overlays in `Starfield.esm` (`settleparadisoworld` `0x244CAA` at `55.0 m`, `lc133world` `0x184DDA` at `60.0 m`, `LC135World` `0x246BC9` at `95.0 m`, and `NeonCity` `0x27CF9E` at `236.0 m` / `OverlayBlockNeonCity` `SFBK.WHGT = 195.0 m`) establishes the three record fields that turn on sea water across an overlay tile:

1. **`WRLD` water height and water forms:**
   - `DNAM`: two `float32` values `(default_land_m, water_height_m)` in metres (for example `(-2048.0, 6.428571)` for Far Harbor and `(-2048.0, 4.642857)` for Nuka-World).
   - `NAM2`: 4-byte `WATR` FormID (`0x000018` `WaterClear` or `0x0560D0` `WaterOceanDark`).
   - `NAM3`: 4-byte LOD water `WATR` FormID (`0x000018`).
   - `NAM4`: `float32` LOD water height (`0.0` or `water_height_m`).
2. **`SFBK` block water height (`WHGT`):**
   - Out of `1,753` `SFBK` records in `Starfield.esm`, `1,640` dry blocks store `-FLT_MAX` (`0xFF7FFFFF`) and `113` water-bearing blocks store a finite `float32` `WHGT` in metres. Setting `SFBK.WHGT = water_height_m` aligns the surface block's water plane with `WRLD.DNAM`.
3. **Exterior `CELL` water inheritance (`DATA` + `XCLW`):**
   - Every exterior `CELL` in a water-bearing overlay carries `DATA = 0x00000002` (`HasWater`) before `XCLC` and `XCLW = +FLT_MAX` (`0x7F7FFFFF`, `+3.4028235e+38`), the Creation Engine sentinel instructing the cell to inherit its water elevation from `WRLD.DNAM`.

`src/fo4sf/terrain/overlay_postpatch.py` applies these `WRLD`, `SFBK`, and exterior `CELL` water fields cleanly at the raw record level after `dotnet/TerrainOverlays` writes a terrain-only overlay plugin, without altering the default dry Commonwealth path.

## 2. Staged Terrain-Only DLC Worlds (`WD2` Far Harbor, `WD3` Nuka-World — `TEST-STATION`, Console Only)

Both Fallout 4 expansion worldspaces are staged offline as **`TEST-STATION (coc only)`** terrain-and-water probes through the parameterized `scripts/terrain/make_cw_overlays.py` (`--fo4-world`, `--fo4-masters`, `--water-height-m`, `--planet-min-gap-cells`), `dotnet/TerrainOverlays`, and `src/fo4sf/terrain/overlay_postpatch.py`. Each world currently holds `3` persistent `REFR` records (`XMarker` anchor, `COCMarkerHeading`, and `1` arrival `MapMarker`), `0` placed exterior objects, `0` ship landing markers, `0` exterior-to-world load doors, and unwired Pip-Boy travel codes (`pipboy_plugin_code = 5` and `6` are reserved in `src/fo4sf/core/world_registry.json`, while `scripts/mapmarkers/FO4SF_PipboyTravel.psc` handles `1..4` only today). Arrival is strictly via developer console (`coc FO4FH_FarHarborSpawn` and `coc FO4NW_NukaWorldSpawn`), and coastal sea-water rendering (`WRLD.DNAM`, `SFBK.WHGT`, `CELL.XCLW`) remains unproven in game until the swap probe:

| Worldspace | Plugin | `WRLD` EditorID & Console Spawn | Reachability | Tile (`100 m` SF cells) | FO4 `LAND` Coverage | Height Range (`m`) | Water Height (`m`) | `CNAM` `(lat, lon)` rad |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `DLC03FarHarbor` (`0x000B0F`, `DLCCoast.esm`) | `FO4WorldFarHarbor.esm` | `FO4FH_FarHarbor` (`coc FO4FH_FarHarborSpawn`) | `TEST-STATION (coc only)` | `34 x 34` (`1,156` cells, `--pad centre`) | `2,067` `VHGT` cells in `[-29..20, -21..31]` (`16,834` total cells) | `-22.51 .. 117.37` | `6.428571` (`450 / 70`, unproven in game) | `(0.374542773, -1.121475735)` |
| `NukaWorld` (`0x00290F`, `DLCNukaWorld.esm`) | `FO4WorldNukaWorld.esm` | `FO4NW_NukaWorld` (`coc FO4NW_NukaWorldSpawn`) | `TEST-STATION (coc only)` | `40 x 40` (`1,600` cells, `--pad origin`) | `4,225` `VHGT` cells in `[-32..32, -32..32]` (`100%` of cells) | `-0.57 .. 212.69` | `4.642857` (`325 / 70`, unproven in game) | `(0.212300885, -1.306361158)` |

Key geometric and planet-separation invariants (`C11`):

- **Coastal sea-floor continuity (`DLC03FarHarbor`):** `DLC03FarHarbor` stores `DNAM = (0.0, 450.0)` in FO4 units. Every coastal `VHGT` vertex bordering an ocean cell without a `LAND` record sits at exact `0.0` units (`7,788` border vertices verified), so filling missing ocean cells inside the `34 x 34` tile with `DNAM[0] = 0.0` joins the island coastline with zero step below the `6.43 m` sea plane.
- **Outer desert border clamping (`NukaWorld`):** `NukaWorld` defines `VHGT` on all `65 x 65 = 4,225` cells in `[-32..32, -32..32]` (`52.34..117.26 m` along the outer ring) and `DNAM = (-2048.0, 325.0)`. Clamping bilinear sampling to the `[-32..32, -32..32]` vertex lattice preserves the exact `-0.57..212.69 m` height range across the `40 x 40` Starfield tile margin without introducing artificial `-2048` cliffs.
- **Dry-land arrival spawn:** When `--water-height-m` is set, `make_cw_overlays.py` restricts flat arrival-vertex selection to vertices at least `1.0 m` above sea level so the persistent `XMarker` anchor and `COCMarkerHeading` never spawn underwater.
- **Planet separation on Mars radius vs. Home-planet Earth radius (`>= 2,000` cells; `±45`-cell = `±4,500 m` playable landing area):** Commonwealth sits at `(0.3, -1.2)` rad (`Mars` cell `(-12, -27)`) and all vanilla Mars `PNDT` `CNAM` entries lie within `lat = -0.51..+0.72, lon = -0.38..-0.09` rad. Evaluated across both `MarsPlanetData` (`R = 3,390.0 km` in `Starfield.esm` `FNAM`; `3,389.5 km` IAU mean radius differs by `0.5–0.7` cells) and `FO4SFHome.esm`'s Earth-radius home planet (`R = 6,371.0 km` in `PNDT` `FNAM`), both DLC worlds sit dozens to hundreds of `±45`-cell (`±4,500 m`) playable landing-area half-widths outside any Commonwealth landing:

| World Pair | Mars Radius (`3,390.0 km` `FNAM` / `3,389.5 km` IAU) | Mars `±45`-Cell (`±4.5 km`) Half-Widths | Home Planet Earth Radius (`6,371.0 km` `FNAM`) | Home `±45`-Cell (`±4.5 km`) Half-Widths |
| :--- | :--- | :--- | :--- | :--- |
| `FO4FH_FarHarbor` <-> `FO4Core_Commonwealth` | `3,563.1` cells (`356.31 km`; `3,562.6` at `3,389.5 km`) | `79.18 x` (`79.17 x`) | **`6,696.4` cells (`669.64 km`)** | **`148.81 x`** |
| `FO4NW_NukaWorld` <-> `FO4Core_Commonwealth` | `4,583.1` cells (`458.31 km`; `4,582.4` at `3,389.5 km`) | `101.85 x` (`101.83 x`) | **`8,613.3` cells (`861.33 km`)** | **`191.41 x`** |
| `FO4FH_FarHarbor` <-> `FO4NW_NukaWorld` | `8,139.2` cells (`813.92 km`; `8,138.0` at `3,389.5 km`) | `180.87 x` (`180.84 x`) | **`15,296.4` cells (`1,529.64 km`)** | **`339.92 x`** |

## 3. BTD Land-Texture (`LTEX`) Encoding and Starfield `.mat` Materials (`WG1`)

Starfield `BTD` v6 terrain archives (`src/fo4sf/btd.py`) select per-vertex ground materials through three tables:

1. **`ltex` table (`N` `uint32` FormIDs):** `LTEX` FormIDs resolved against the overlay plugin's load order.
2. **`quad_map` (`[ncy * 2, ncx * 2, 8]` `uint8`):** Four quadrants per `100 m` Starfield cell (`SW`, `SE`, `NW`, `NE` in `(qy, qx)` order). A non-zero byte `1 <= b <= N` addresses `ltex[N - b]`:
   - Slots `i = 0..4` assign overlay layers `t[5 - i]`.
   - The last valid non-zero byte in `quad_map[qy, qx, 0..7]` assigns the opaque base layer `t[0]`.
3. **`weights` (`[ncy * 128, ncx * 128]` `uint16`):** Five 3-bit alpha weights (`0..7`, scaled by `1/7`) packed in bits `0..14` (`bits 0..2` = `t[1]`, `3..5` = `t[2]`, `6..8` = `t[3]`, `9..11` = `t[4]`, `12..14` = `t[5]`, `bit 15 = 0`), blended sequentially from `t[0]` through `t[5]`.

Fallout 4 `LAND` records store per-quadrant base textures in `BTXT` (`quadrant` `0..3`: `SW`, `SE`, `NW`, `NE`) and up to eight alpha-blended layers in `ATXT` + `VTXT` (`17 x 17` vertex opacities in `0.0..1.0` per `29.26 m` FO4 quadrant). Transforming Commonwealth coordinates (`FO4 units / 70` minus tile origin) onto the `128 x 128` BTD sample lattice per `100 m` Starfield cell maps each BTD `50 m x 50 m` quadrant's dominant base + top 5 active FO4 `LTEX` layers into `quad_map` and quantizes bilinearly interpolated FO4 opacities into 3-bit `weights`.

Each mapped `LTEX` record in Starfield carries:
- `EDID`: deterministic identifier (`FO4WG1_L<fo4_edid>`),
- `BNAM`: `Materials\Terrain\<name>.mat`,
- `MNAM`: `MATT` material-type FormID (e.g. `0x00012F3E` / `0x00012F48` in `Starfield.esm`),
- `HNAM`: `0x1E1E`, `QNAM`: `0`.

Each generated `.mat` JSON file inherits `Data\MATERIALS\Layered\ShaderModels\Terrain1Layer.mat` and binds converted BC7 color (`_color.dds`), BC5 normal (`_normal.dds`), and BC4 roughness (`_rough.dds`) textures derived from Fallout 4's `LTEX -> TXST` chain.
