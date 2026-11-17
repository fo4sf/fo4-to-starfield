# Second-Archive Plan: Multi-BA2 Bundle Splitting, Verification, and Rollback

The 19-plugin Core Candidate (`#816` at `cd03411a`) packs `52,746` `Data/` files into a single stored `General` (`GNRL`) archive of `4,015,457,857 B` (`3.740 GiB`), leaving `0.260 GiB` (`279,509,438 B`) below the unsigned 32-bit BA2 ceiling (`4,294,967,295 B`).

`src/fo4sf/archive_split.py` and the multi-archive extensions in `scripts/game/exp_install.py` split any staged `Data/` tree deterministically across multiple active plugin archives (`<PluginStem> - Main.ba2`), with full per-archive SHA-256 verification, atomic publication, and byte-clean uninstall/rollback.

---

## 1. Starfield BA2 Naming and Loading: Confirmed vs Unconfirmed

Offline inspection of the installed Starfield configuration (`Starfield.ini` `[Archive]` section) and `Data/` inventory establishes what the engine mounts automatically versus what requires INI edits or remains unconfirmed in-game:

### Confirmed from the Installed Game
1. **Loose `Data/` files are ignored by default:** Base `Starfield.ini` sets `sResourceDataDirsFinal=STRINGS\`, so loose `meshes\`, `geometries\`, `textures\`, `materials\`, `Terrain\`, `Interface\`, `Scripts\`, and `sound\` files are not read unless packed into a mounted `.ba2` archive (or overridden in `StarfieldCustom.ini`).
2. **Base-game numbered archives (`01..11`) are INI-driven, not automatic:** `Starfield - Meshes01.ba2`, `Starfield - Meshes02.ba2`, `Starfield - Textures01.ba2` .. `Textures11.ba2` (topping out at `4,294,946,755 B`, just `20,540 B` under `2^32 - 1`) load only because `Starfield.ini` explicitly lists every numbered filename in `SResourceArchiveList` and `sResourceIndexFileList`.
3. **Non-base `.esm` plugins auto-mount `<PluginStem> - Main.ba2` and `<PluginStem> - Textures.ba2`:** Official add-on masters (`SFBGS003.esm`, `SFBGS004.esm`, `SFBGS008.esm`, `SFBGS00D.esm`, `SFBGS047.esm`) and our verified in-game experiment plugins (`FO4Port.esm`, `FO4ActorRaider.esm`, `FO4TerrainCore.esm`, `FO4SFBridge.esm`, `FO4SFMapMarkers.esm`) are absent from `Starfield.ini` and automatically mount `<PluginStem> - Main.ba2` (`GNRL`) and `<PluginStem> - Textures.ba2` (`DX10`) whenever `*<PluginStem>.esm` is active in `Plugins.txt`.
4. **Cross-plugin VFS resolution works across active `.esm` masters:** Once mounted in Starfield's virtual file system, resources in `<PluginB> - Main.ba2` resolve by virtual `Data/...` path for records in `<PluginA>.esm` and vice versa, as already proven by converted world/interior runs reading shared assets from `FO4Port - Main.ba2`.

### Not Confirmed / Avoided Without In-Game Proof
1. **Numbered plugin suffixes (`<PluginStem> - Main01.ba2`, `Main02.ba2`):** Zero official non-base plugins in `Data/` use numbered `- Main01.ba2` names without an explicit INI entry. **Not assumed.**
2. **Empty dummy `.esm` archive carriers:** Record-less `.esm` files created solely to carry an extra `.ba2` (`interior_batch.py`) have not yet been verified in-game. **Not needed** because the Core Candidate already activates 19 real `.esm` plugins with real records (`19 * 4 GiB = 76 GiB` of standard `<ActivePlugin> - Main.ba2` capacity with zero dummy plugins and zero INI edits).
3. **Live VFS override precedence across two split `GNRL` archives:** We guarantee disjoint archive contents (`verify_split_archives` rejects any duplicate `Data/...` key across buckets), so two split archives never compete on the same virtual path. Live runtime loading of the 2-archive split remains a Claude (PC) game check.

---

## 2. Split Modes, Verification, Install, and Rollback

### `src/fo4sf/archive_split.py`
- **`--split-by size` (`plan_split_by_size`, default `--max-archive-bytes 3221225472` = `3.000 GiB`):**
  Groups non-texture directories (`geometries`, `meshes`, `Terrain`, `materials`, `Interface`, `Scripts`, `sound`) ahead of `textures`, splitting cleanly at the non-texture / texture boundary first and spilling into `plugins[2]`, `plugins[3]`, ... whenever any group exceeds `max_archive_bytes`.
- **`--split-by plugin` (`plan_split_by_plugin`):**
  Uses `bundle_plan.json` component output maps to assign each folded component's `Data/*` outputs to its owning `<ComponentPlugin> - Main.ba2`, assigns base world assets to `FO4TerrainCore - Main.ba2`, and spills any overflowing bucket onto remaining active plugins.
- **`verify_split_archives`:**
  Runs `verify_archive` (`BTDX` header, `GNRL` entries, uncompressed/compressed payload SHA-256s) on **every** built `.ba2`, enforces `actual_size <= min(max_archive_bytes, 4 GiB - 1)`, rejects any duplicate `Data/...` path across buckets, and proves the disjoint union of all split archives equals the staged `Data/` SHA-256 inventory.

### `scripts/game/exp_install.py`
- Adds `--split-archives {none,size,plugin}`, `--max-archive-bytes`, and `--prepacked-dir <split_dir>`.
- Publishes every split `<Plugin> - Main.ba2` atomically via `deployment.publish_files`, records `"archives": [...]` and `"archive_inputs": {archive_name: {Data/...: sha256}}` in `Data/FO4SFExp.install.json`, verifies every archive on `verify_relaunch` / `order`, and removes every recorded `.ba2` cleanly on `uninstall` or mid-install rollback.

---

## 3. Offline Build & Verification of the `#816` (`cd03411a`) Bundle Split into Two Archives

Built and verified offline using Starfield's `Archive2.exe` (`General`, `Compression=None`) against the 19-plugin `#816` Core Candidate (`52,746` `Data/` files, `--split-by size --max-archive-bytes 3221225472`):

| Archive Name | Carrier Plugin | Entries | Built `.ba2` Bytes | Size (`GiB`) | Free Headroom Below `4.000 GiB` | SHA-256 Prefix | Verification |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `FO4ActorRaider - Main.ba2` | `FO4ActorRaider.esm` | `43,678` | `1,238,692,793` | `1.154 GiB` | **`+2.846 GiB`** | `a4865ef17bc4c14e` | `PASS` (`verify_archive`) |
| `FO4TerrainCore - Main.ba2` | `FO4TerrainCore.esm` | `9,068` | `2,776,765,096` | `2.586 GiB` | **`+1.414 GiB`** | `b12dd4be9a2b8d58` | `PASS` (`verify_archive`) |
| **Combined Split Total** | **2 of 19 plugins** | **`52,746`** | **`4,015,457,889`** | **`3.740 GiB`** | **`+4.260 GiB` (across 2 archives)** | Disjoint union verified | **`split verify: ok`** |

*(Planning `--split-by plugin` at a `3.000 GiB` cap across the same `52,746` files also succeeded cleanly across `17` component archives: `FO4TerrainCore - Main.ba2` at `3.000 GiB` / `50,133` entries, `FO4ActorRaider - Main.ba2` at `0.737 GiB` / `2,459` entries, `FO4SFVaultGearDoor - Main.ba2` at `89` entries, `FO4SFExitLift - Main.ba2` at `48` entries, and `1–4` `.pex`/asset entries per gameplay plugin.)*
