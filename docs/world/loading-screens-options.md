# Loading Screens Proposal: Suppressing Starfield's 304 `LSCR` Records (`WL3`)

Scope: read-only structural analysis of how `Starfield.esm` selects among its `304` `LSCR` loading-screen records (`scripts/terrain/sf_location_census.py`), followed by two concrete implementation options for the owner to choose between before building an `LSCR` plugin. Per rule `R9`, `Starfield.esm` remains untouched; per rule `R4`, zero in-game tip prose (`DESC`/`FULL`) is reproduced here.

---

## 1. Measured Structure of `Starfield.esm`'s `304` `LSCR` Records

Read-only census across `Starfield.esm` (1.16.244) via [sf_location_census.py](../../scripts/terrain/sf_location_census.py) establishes:

| Metric | Measured Count | Consequence for FO4SF |
|---|---:|---|
| Total `LSCR` records in `Starfield.esm` | `304` | Every base-game loading screen lives in the `LSCR` top group |
| `LSCR` records carrying `KWDA` keywords | `0` | Starfield does **not** filter loading screens by keyword |
| `LSCR` records carrying `CTDA` conditions | `90` (`215` total `CTDA` subrecords) | Only `29.6%` of vanilla loading screens carry any condition |
| **Unconditioned `LSCR` records (`0` `CTDA`)** | **`214`** (`70.4%`) | **`214` Starfield loading screens (lore/gameplay tips, ships, weapons, factions) remain globally eligible in every worldspace, planet, and star system — including our isolated `FO4SFHome.esm` star system** |
| `LSCR` records carrying `DESC` tip text | `304` | All `304` display Starfield tip strings unless suppressed or out-prioritised |
| `LSCR` records carrying `NNAM` 3D static/pack-in art | `279` | `279` spin a 3D Starfield model/scene during load |
| `LSCR` records carrying `ICON` 2D image path | `28` | `28` render a static 2D background texture |

### Breakdown of the `215` `CTDA` Conditions on the `90` Conditioned `LSCR` Records

Across the `90` conditioned `LSCR` records, conditions test:
- **Location checks (`GetInCurrentLocation`, function `359`, `100` occurrences):** Scope city/station loading screens to vanilla `LCTN` trees (`NewAtlantis`, `Cydonia`, `AkilaCity`, `Neon`, `TheKey`, `TheClinic`, `RedMile`, `Den`, `Gagarin`, `NewHomestead`). Moving FO4SF onto `FO4SFHome.esm` (`W2`/`W3`) automatically makes all `100` of these location checks evaluate false.
- **Random weight gates (`GetRandomPercent`, function `77`, `82` occurrences):** Throttle how frequently specific conditioned screens win selection.
- **Quest stage / completion checks (functions `56`, `58`, `59`, `543`, `29` occurrences):** Gate spoiler screens on `MQ101` (`0x0001295A`), `UC03`/`UC04`/`UC08`, `CF`, `FS`, and `RI` quest stages (already held off by `FO4SFNewGame.esm`, so positive stage checks stay false, while `== 0` pre-quest checks can still pass).
- **Faction membership checks (function `497`, `4` occurrences):** Test player membership in vanilla factions.

Because **`214` of `304` `LSCR` records have zero `CTDA` conditions**, isolating our host planet (`W2`) and holding Starfield quests (`FO4SFNewGame.esm`) cannot stop Starfield loading screens from appearing on exterior/interior load transitions. An explicit `LSCR` plugin lever is required.

---

## 2. Two Options for Owner Decision

### Option A — Condition All `304` Vanilla `LSCR` Records Off (`FO4SFLoadScreens_Off.esm`)

- **Mechanism:** Generate a tiny override plugin (`master: Starfield.esm`) containing `304` `LSCR` overrides (`0x00XXXXXX`), each preserving the record header and prepending a single `CTDA` condition that always evaluates **false** while FO4SF is active — e.g. `GetGlobalValue(FO4SF_SuppressVanillaLoadScreens) == 0` (with `FO4SF_SuppressVanillaLoadScreens` defaulting to `1`), or `GetInCurrentLocation(SSol) == 1` (false everywhere in `FO4SFHome.esm` and `FO4Port.esm`), with `DESC` emptied on the override or left unreached.
- **Visual result during loads:** Black/fade transition screen with the loading spinner only — zero Starfield 3D models, zero Starfield 2D concept art, and zero Starfield tip text.
- **Pros:**
  - Zero asset conversion required; builds offline in `< 1 s` (`~35 KB` plugin).
  - Eliminates `100%` of Starfield loading-screen bleed immediately and deterministically.
  - Reversible via `TESGlobal` or plugin untick (`R9`).
- **Cons:**
  - Load transitions show a plain dark screen rather than Fallout 4 3D vignettes or Fallout 4 survival/lore tips.

### Option B — Condition Vanilla `304` Off + Ship One FO4SF `LSCR` Set (`FO4SFLoadScreens.esm`)

- **Mechanism:** Include Option A's `304` false-conditioned overrides so no vanilla `LSCR` stays in the random pool, **plus** author a set of new `FO4SF_*` `LSCR` records in `FO4SFLoadScreens.esm` conditioned on `FO4SFHome.esm` / `FO4Port.esm` locations (or unconditioned while `FO4SF_SuppressVanillaLoadScreens == 1`):
  - `NNAM` pointing to already-converted Fallout 4 `STAT` models from `FO4TerrainCore.esm` / `FO4Port.esm` (e.g., Red Rocket sign, Vault-Tec crate, Nuka-Cola machine, workbench, power armor frame — using `LSCR` transform/camera subrecords `TNAM`/`RNAM`/`ONAM`), or `ICON` pointing to converted Fallout 4 loading-screen textures;
  - `DESC` populated from `Fallout4.esm`'s own `LSCR` records (`Fallout4.esm` user-installed copy read at build time on the user's PC, never committed to Git per `R4`), or left empty (`""`) for clean model-only screens.
- **Visual result during loads:** Fallout 4 3D models (and optional user-converted Fallout 4 `LSCR` text) on every interior door and fast-travel load, with zero Starfield screens.
- **Pros:**
  - Authentic Fallout 4 load transition presentation alongside `100%` Starfield `LSCR` suppression.
  - Reuses `STAT` meshes already converted on the user's PC (`zero` new mesh pipeline needed for static `NNAM` props).
- **Cons:**
  - Requires calibrating `LSCR` camera/scale subrecords in `Starfield` (`1` in-game visual pass by Claude (PC) for owner sign-off per `R8`), and deciding whether `DESC` shows converted `Fallout4.esm` tip strings or stays blank.

---

## 3. Decision Prompt for Owner

1. **Pick Option A (clean black spinner load screens now) or Option B (converted Fallout 4 `LSCR` set + all `304` vanilla `LSCR` conditioned off)?**
2. **If Option B:** Should `FO4SFLoadScreens.esm` display converted `Fallout4.esm` `LSCR` tip text + 3D models, or 3D models / artwork only with blank text?
