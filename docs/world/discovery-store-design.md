# Map-Marker Discovery Store Design Beyond 336 Markers (`R14`)

> **Status / Rule 12 Notice:** Design-only specification for scaling discovered-marker bitsets beyond the current `336`-marker Pip-Boy limit. No live gameplay or bundle behavior is altered here.
> **Recommended Default (pending owner decision):** **Per-World Fixed `GLOB` Pages + Save-Co-Synced Bitset (`WorldPages-16`)** for immediate backward compatibility, paired with an optional **SFSE Co-Save Array** fast-path when native SFSE hooks expand.

---

## 1. Current `336`-Marker Limit vs. `world_registry.json` Needs

`scripts/ui/pipboy_map_store.py` and `scripts/mapmarkers/FO4SF_PipboyTravel.psc` currently pack live marker discovery into **`14` `GLOB` records** (`FO4SF_MapDisc00..13`, `0x000810..0x00081D` in `FO4SFPipboyTravel.esm`), where each `float32` mantissa holds `24` lossless bits:

$$14 \times 24 = 336\text{ markers total}$$

Comparing against `src/fo4sf/core/world_registry.json`:

| World | `pipboy_plugin_code` | Marker Range / Count | Cumulative Total | Fits `336` Limit? |
|---|---:|---:|---:|---|
| **Commonwealth (`FO4TerrainCore.esm`)** | `1` | `0..311` (`311`) | `311` | Yes (`25` bits free) |
| **Far Harbor (`FO4WorldFarHarbor.esm`)** | `5` | `326..373` (`47`) | `358` | **No (`+22` over `336`)** |
| **Nuka-World (`FO4WorldNukaWorld.esm`)** | `6` | `~60+` planned | `418+` | **No** |
| **Capital Wasteland (`FO4CapitalWasteland.esm`)** | `2` | Full wasteland (~`160+`) | `578+` | **No** |
| **Mojave Wasteland (`FO4Mojave.esm`)** | `3` | Full wasteland (~`180+`) | `758+` | **No** |

Notice `FarHarbor`'s reserved `marker_index_range = [326, 373]` already overflows bit `335`.

---

## 2. Two Architectural Options

### Option 1 — SFSE Binary Co-Save Bitset Store

- **Mechanism:** `FO4SFPipboyMenu.dll` maintains an expandable vector (`std::vector<uint32_t>`) keyed by `(plugin_code, local_formid)` or global marker index, persisted directly in an `.sfse` co-save record alongside vanilla `.fos` saves, and exposed to SWF/Papyrus via Scaleform/SFSE native functions.
- **Pros:** Zero fixed marker ceiling (supports `4,096+` markers cleanly across all 5 Fallout worlds without touching ESM `GLOB` IDs).
- **Cons / Risk:** Requires matching SFSE co-save serialization hooks and keeping save/load ordering synchronized if a player uninstalls/reorders an optional world plugin mid-playthrough.

### Option 2 — Per-World `GLOB` Pages (`WorldPages-16`, **Recommended Default**)

- **Mechanism:** Keep `FO4SFPipboyTravel.esm` `0x810..0x81D` (`336` bits) backward-compatible for Commonwealth (`plugin_code = 1`), and allocate per-world discovery banks indexed cleanly by `plugin_code` (or per-world registration `*_TravelDisc.esm` / reserved `GLOB` range `(plugin_code * 32)` `float32` 24-bit buckets = **`768` markers per world** with zero cross-world index collision):
  - `plugin_code = 1` (Commonwealth): `32` `GLOB`s -> `768` markers (preserving `0..335` bit-for-bit on slots `0..13`)
  - `plugin_code = 2` (Capital Wasteland): `32` `GLOB`s -> `768` markers
  - `plugin_code = 3` (Mojave Wasteland): `32` `GLOB`s -> `768` markers
  - `plugin_code = 5` (Far Harbor): `16` `GLOB`s -> `384` markers
  - `plugin_code = 6` (Nuka-World): `16` `GLOB`s -> `384` markers
- **Pros:**
  - Zero SFSE co-save dependency; 100% persisted automatically by Starfield's native `.sfs` save serializer alongside existing `FO4SF_MapDisc*` `GLOB`s.
  - Per-world indexing prevents one world's marker count changes from shifting bit indices in another world.
- **Cons:** Fixed cap per world (`768` max for main wastelands, `384` for DLCs — already `> 2x` measured `Fallout4.esm` / `DLCCoast.esm` counts).

---

## 3. Recommended Migration Path

1. Keep existing `0..335` (`FO4SF_MapDisc00..13`) untouched so `candidate-2g` saves stay unbroken.
2. Adopt **Option 2 (`WorldPages-16` / per-world `(plugin_code, local_index)` `GLOB` banks)** as the **recommended default** pending owner decision, migrating global index `326..373` (`FarHarbor`) to local `plugin_code = 5` slot offsets `0..47` when multi-world UI activation lands.
3. Reserve **Option 1 (SFSE Co-Save Store)** if total custom player markers or multi-mod expansion worlds later require dynamic allocation above `768` markers per world.
