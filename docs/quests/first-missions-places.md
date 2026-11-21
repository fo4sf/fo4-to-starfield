# First-Missions Places on the Path (`A3` — Staged Interiors, Two-Way Doors & Set-Pieces)

> **Whole Scope:** Titles: Fallout 4 | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (playable path) — **offline audit & two-way door wiring spec, unproven in game (`R15`)**.
>
> **Zero-Reconversion Rule:** Every interior listed below is **already converted and staged on disk** in the `interiors_b10` port (`FO4Port.esm` + `FO4Port - Main.ba2` + `FO4Port - Textures.ba2` + `FO4PortTextures2.esm` + `FO4PortTextures2 - Textures.ba2`, built at commit `1b661304`, plugin SHA-256 `c12b141c2783...`, `HEDR.nextObjectId = 0x074CD3`, `477,066` records). Do **not** reconvert any interior cell.

---

## 1. Why Today's `candidate-2e` Bundle Cuts Off Outside the Museum Door

Offline audit (`python scripts/terrain/a3_path_places.py audit-stage --port <interiors-b10-port> --core <cand2e-player>`) verified **8/8 staged cells** and **18/18 real-mesh two-way door pairs** (`0` mismatches) across the already-staged interior port and Commonwealth overlay. Two concrete wiring gaps explain why `When Freedom Calls` (`FO4SF_Min00`) still stops outside the Museum of Freedom front door in `candidate-2e`:

1. **Interior port plugins not yet bundled into Track 1 `player`:** `candidate-2e`'s `13`-plugin `--profile player` bundle ships `FO4TerrainCore.esm` (`04`) and `FO4SFMission.esm` (`09`), while `FO4Port.esm` (staged in `interiors_b10/port`) and its companion `FO4PortTextures2.esm` (`42 B`, required for the `476` textures in part 2) are installed separately or absent from the bundle plan.
2. **Only the original 15 exterior/interior doors were promoted into `FO4TerrainCore.esm`:** `interiors_b10/port/doors.json` preserves the `15` earlier doors (`00E175..00E183`, Vault 75, Parsons State, Vault 114, Cambridge Polymer Labs, Fort Hagen, Museum of Witchcraft, Prydwen, Super Duper Mart, etc.). All `13` real-mesh doors for Sanctuary Root Cellar and Concord (plus `5` for Corvega Assembly Plant in `A4`) are **already placed on both sides** — as static `REFR`s in `FO4TerrainCore.esm` and as `DOOR` `REFR`s in `FO4Port.esm` — and only need two-way `FO4SF_LoadDoor` VMAD promotion + persistent `XMarker` arrival pairs (`0x074CD3..0x074CE4` in `FO4Port.esm`, leaving all `15` existing markers untouched via `--keep-markers --allow-new-doors`).

---

## 2. Staged Interior Inventory (`interiors_b10`, Zero Reconversion)

All files required to load the staged port (in `Plugins.txt` order, companions directly after `FO4Port.esm`):
- `FO4Port.esm` (`33,003,221 B`, `HEDR.nextObjectId = 0x074CD3`)
- `FO4Port - Main.ba2` (`279,005,136 B`)
- `FO4Port - Textures.ba2` (`3,864,482,275 B`, part `0`)
- `FO4PortTextures2.esm` (`42 B`, empty full-master companion; in-game archive loading still unverified per `docs/terrain/interior-batches.md`)
- `FO4PortTextures2 - Textures.ba2` (`297,292,310 B`, part `1`)

| Place / Cell EditorID | Tier | Display Name | FO4 Cell FormKey | `FO4Port.esm` `CELL` ID | `FO4Port.esm` `LCTN` ID | Encounter Zone (Min–Max) | Refs | Real Doors | Autoload Doors |
|---|---|---|---|---|---|---|---|---|---|
| `ConcordMuseum01` | **A3 (P0)** | Museum of Freedom | `017DF7:Fallout4.esm` | `0x012540` | `0x0405D1` | `ConcordMuseumZone` (`1–5`) | `3,402` | `3` | `0` |
| `SanctuaryBasementJahani` | **A3** | Root Cellar | `0A36EA:Fallout4.esm` | `0x011918` | `0x0405CE` | None | `217` | `1` | `0` |
| `RedRocket01` | **A3** | Mole Rat Den | `05E62F:Fallout4.esm` | `0x002338` | `0x0405B4` | `RedRocketCaveZone` (`4–9`) | `795` | `0` | `1` |
| `ConcordCivicAccess01` | **A3** | Concord Civic Access | `03776D:Fallout4.esm` | `0x0119AF` | `0x0405CF` | `ConcordUndergroundZone` (`1–5`) | `1,980` | `3` | `0` |
| `ConcordFactory` | **A3** | Workhouse | `0E3CC4:Fallout4.esm` | `0x01202C` | `0x0405D0` | `ConcordZone` (`0–10`) | `598` | `3` | `0` |
| `ConcordSpeakeasy` | **A3** | Concord Speakeasy | `0788D4:Fallout4.esm` | `0x012245` | `0x0405D0` | `ConcordZone` (`0–10`) | `859` | `3` | `0` |
| `CorvegaAssemblyPlant01` | **A4** | Corvega Assembly Plant | `057127:Fallout4.esm` | `0x01535A` | `0x0405DD` | `CorvegaAssemblyPlantZone` (`1–5`) | `10,980` | `5` | `1` |
| `DmndValentines01` | **A4** | Valentine Detective Agency | `001E47:Fallout4.esm` | `0x006B30` | `0x0405AB` | None | `342` | `0`* | `0` |

*\*`DmndValentines01` links to `DiamondCityWorld` (`0013FC`, `0013FD`), not Commonwealth; see Section 6 and `docs/quests/next-story-missions-a4.md` for the `DmndGateREF` -> `DmndValentines01` bridge until `DiamondCityWorld` is built.*

---

## 3. Place-by-Place Engineering Breakdown (What Each Needs to Work)

### 3.1 Museum of Freedom (`ConcordMuseum01` — Top Priority for *When Freedom Calls*)

**Two-Way Load Doors (3 pairs, all real converted meshes present on both sides):**
1. **Front Entrance Double Doors (`museum_front`):** Exterior `01AC07:Fallout4.esm` (`FO4TerrainCore.esm:0x004B2B`) <-> Interior `077D22:Fallout4.esm` (`FO4Port.esm:0x01303B`). Unlocked both ways. Exterior merged arrival `(-2011.143, -1697.543, 89.086)` m; interior arrival `(8.057, 0.000, -0.914)` m.
2. **Second-Floor Balcony Door (`museum_balcony`):** Exterior `01D22F:Fallout4.esm` (`FO4TerrainCore.esm:0x005054`) <-> Interior `01B94A:Fallout4.esm` (`FO4Port.esm:0x013045`, `ConcordMuseumBalconyDoorREF`). Carries **`XLOC` lock level `255` (Inaccessible)** on the interior side during `Min00` so the player cannot bypass the upstairs lobby fight; must stay locked until Preston's balcony scene clears or `FO4SF_Min00` unlocks it.
3. **Roof Access Door (`museum_roof`):** Exterior `029AD8:Fallout4.esm` (`FO4TerrainCore.esm:0x00677F`) <-> Interior `02C1C6:Fallout4.esm` (`FO4Port.esm:0x013048`). Leads directly out onto the Museum roof next to the crashed Vertibird and T-45 Power Armor. Exterior merged arrival `(-1990.577, -1724.185, 97.559)` m; interior arrival `(-21.903, 8.683, 9.143)` m.

**Enable States (`XESP` / Initially Disabled), Locks (`XLOC`), Scripted Doors & Terminals Inside `ConcordMuseum01`:**
- **Enable state counts:** `20` Initially Disabled references and `30` `XESP` enable-parented references across `6` interior enable-parent markers (`09A6A8`, `09A6AF`, `09A698`, `09A6A6`, `09A699` — all Initially Disabled `XMarker`s toggling post-fight debris/raider props — plus `0AE9F0`, enabled by default). Because `FO4Port.esm` strips FO4 quest scripts, the mission script must leave `09A698..09A6AF` disabled during the initial fight and toggle only what `FO4SF_Min00` requires.
- **Scripted Doors & Locks (`7` locked refs inside `ConcordMuseum01`):**
  - `PrestonDoorREF` (`01E2EA:Fallout4.esm` -> `FO4Port.esm:0x013047`, `BldWoodPDoor02`, **lock `255` Inaccessible**): Doors off Preston's upstairs sanctuary room until the `7` interior museum raiders (`RaiderA1/A2`, `RaiderB1/B2`, `RaiderC1/C2`, `RaiderMannequin`) are cleared (`Min00` stage `35` -> `SetLockLevel(0)` + `Lock(False)`).
  - `PrestonExitDoor` (`01E2E9:Fallout4.esm` -> `FO4Port.esm:0x013046`, `BldWoodPDoor01`, **lock `255` Inaccessible**): Rear exit of Preston's room leading to the roof stairwell; must unlock at stage `45` once Preston briefs the player about the rooftop Power Armor.
  - `MQ03SecurityGateREF` (`05C66C:Fallout4.esm` -> `FO4Port.esm:0x013042`, `SecurityGateSmLatch02`, **Novice lock `25`**): Basement Fusion Core cage. Can be bypassed either by lockpicking (`Lockpick >= 25`) or by hacking **`ConcordMuseumBasementTerminal`** (`08110D:Fallout4.esm` -> `FO4Port.esm:0x0125AB`, **Novice lock `25`**) which triggers `SetOpen(True)` / `Lock(False)` on `0x013042`.
  - `MQ102SturgesTerminal` (`022AA3:Fallout4.esm` -> `FO4Port.esm:0x013040`, **Novice lock `25`**): Upstairs lore terminal in Preston's room.
  - `MetalGateFancy01` (`0509AD:Fallout4.esm` -> `FO4Port.esm:0x012C4D`, **Advanced lock `50`**): Side gallery loot gate.
- **Basement Fusion Core & Generator (`PowerGenerator01`):**
  - `09A147:Fallout4.esm` (`FO4Port.esm:0x012585`, `PowerGenerator01`, FO4 `FusionGeneratorSCRIPT`) holds the quest Fusion Core. In FO4, `237B27:Fallout4.esm` (`DummyNoEdit_FusionCore`) is a non-placed dummy marker (`NOT_PLACED` in `FO4Port.esm`).
  - **Wiring needed:** Attach a lightweight `OnActivate` pickup/extractor script on `0x012585` (or place a persistent `FO4SFPowerArmor.esm:0x000809` `FO4SF_FusionCore` ref directly on the generator housing) that awards `1x FO4SF_FusionCore` (`0x000809`) and advances `Min00` stage `50` / Objective `90` -> `105`.
- **Exterior Laser Musket (`MQ102LaserMusketREF`):**
  - FO4 `01F22E:Fallout4.esm` at local `(-815.41, 1002.87, 88.19)` m -> merged **`(-2015.41, -1697.13, 88.19)` m** (not placed in `FO4TerrainCore.esm` because `MISC` dummy item was skipped). Spawn a pickup weapon/activator ref at that exact merged spot during `Min00` stage `20` (Optional Objective `70`).

**Roof Power Armor (`T-45`) + Fusion Core + Crashed Vertibird Minigun Set-Piece (Exterior Museum Roof):**
- **Crashed Vertibird (`Vertibird03`):** `0AB4FD:Fallout4.esm` -> **ALREADY placed** in `FO4TerrainCore.esm:0x01EC87` at local `(-804.43, 982.25, 98.93)` m (merged `(-2004.43, -1717.75, 98.93)` m), with left/right wings `0AEEC7` and `0AEEC4`.
- **Vertibird Rip-Off Minigun (`MQ102MinigunREF`):** `01F583:Fallout4.esm` -> **ALREADY promoted as an activator** in `FO4TerrainCore.esm:0x005119` (base `ACTI 0x0A2D4A`) at local `(-804.72, 984.60, 102.68)` m (merged **`(-2004.72, -1715.40, 102.68)` m**)!
  - **Wiring needed:** Bind `RegisterForRemoteEvent` (`OnActivate`) on `0x005119` from `FO4SF_Min00Quest`: verify `FO4SF_PAInPowerArmor` (`FO4SFPowerArmor.esm:0x00080A >= 1.0`, or `STR >= 8` fallback in Open Mode), disable `0x005119`, add a heavy minigun weapon + `500` rounds to the player, and advance Objective `115` -> `120` (Wave 2 + Deathclaw!).
- **Roof T-45 Power Armor (`PowerArmorFurniture`):** `0370E3:Fallout4.esm` -> placed as static `FO4TerrainCore.esm:0x008913` at local `(-795.73, 976.90, 97.54)` m (merged **`(-1995.73, -1723.10, 97.54)` m**).
  - **Wiring needed:** Disable/hide static placeholder `0x008913` when `FO4SF_Min00` enters stage `45+` and place an interactive `FO4SF_PowerArmorFrameFurn` (`FO4SFPowerArmor.esm:0x000801`) at merged `(-1995.73, -1723.10, 97.54)` m requiring `FO4SF_FusionCore` (`0x000809`) to enter (`FO4SF_PAInPowerArmor == 1`), completing Objectives `105` and `110`.
- **Roof Leave Trigger (`DN092SetStage76TriggerREF`):** FO4 `023C1E` at local `(-796.63, 990.34, 101.37)` m + `03D23B` at `(-796.12, 977.69, 99.34)` m trigger Wave-2 street raiders (`RaiderBoss`, `WaveRaider01..03`, `RaiderLookout`) once the player equips Power Armor & Minigun or drops to street level (`Z < 93.0 m`).

**Concord Deathclaw Emergence from Civic Access (`DN092` / `Min00` Wave 2):**
- **Deathclaw Actor (`ConcordAmbushDeathclaw`):** FO4 `ACHR 01F15B:Fallout4.esm` (`NPC_ 02C969 DN092AmbushDeathclaw`), **Initially Disabled `True`**, positioned directly over the Concord sewer pit at local `(-868.22, 1059.82, 88.22)` m -> merged **`(-2068.22, -1640.18, 88.22)` m**.
- **Emergence Trigger & Sewer Pit Geometry:**
  - `09A144` (`DN092ForceSpawnDeathclawTrigger`, local `(-868.22, 1059.77, 88.22)` m) + `10FD49` (`ConcordUnderNavblocker`, `CollisionMarker`, Initially Disabled `True`, local `(-866.62, 1060.08, 85.42)` m) + `ExtSewerWall*` / `ExtSewerArch*` (`11E677..11E6AC`, already in `FO4TerrainCore.esm` exterior street cell `(-15, 18)`/`(-15, 17)`).
  - Inside `ConcordCivicAccess01`, `DeathclawFenceEnabler` (`0B1EB3` `XESP` parent with `4` children) swaps the tunnel fence from intact to broken after the emergence.
- **Anti-Stuck Guard (`WFC-06`):** Because the street pit sits `~6 m` below street grade (`Z = 82.3..88.2 m`), spawn the Deathclaw actor at street grade `(-2068.22, -1640.18, 88.50)` m (or climb-out marker) when Wave 2 begins (`DN092` stage trigger or player within `55 m` of the pit while on Objective `120`) and run a `20 s` subterranean Z-leash (`if Z < 84.5 m` -> `MoveTo` open street node `(-2060.0, -1648.0, 88.6)` m) so it can never wedge inside sewer geometry.

---

### 3.2 Sanctuary Hills Houses & Sanctuary Root Cellar (`SanctuaryBasementJahani`)

- **Sanctuary Hills Houses (Verified Open Exterior Shells — Zero Load Doors):**
  - Direct scan of `Fallout4.esm` Sanctuary Hills (`x in [-85000, -72000], y in [86000, 96000]`) found **`21` placed `DOOR` records**: `12` `PicketFenceB_Gate01`, `7` ruined kitchen refrigerator doors, `1` non-load `Res01ModernDoor05RR`, and `1` load door (`0A36EB` `RoofHatch01` -> `SanctuaryBasementJahani`).
  - **Result:** All enterable pre-war houses in Sanctuary Hills (including the player's home and the workbench house) are **open exterior shells already built into `FO4TerrainCore.esm`** with no interior load cells!
  - **What they need to work:** Keep all house doorways unobstructed (the single `Res01ModernDoor05RR` and `12` fence gates should either be open-by-default or promoted to swinging `DOOR`s so settlers and the player walk freely through yards); Sanctuary's workshop **`0250FE:Fallout4.esm`** is **already promoted** at `FO4TerrainCore.esm:0x005C50` (base `0x0A2ECD`, merged `(-2329.250, -1420.193, 112.086)` m).
- **Sanctuary Root Cellar (`SanctuaryBasementJahani`, `FO4Port.esm:0x011918`):**
  - **Two-Way Load Door (`sanctuary_root_cellar_hatch`):** Exterior `0A36EB:Fallout4.esm` (`FO4TerrainCore.esm:0x01CF77`, `RoofHatch01`, behind the house northeast of the cul-de-sac) <-> Interior `0A3701:Fallout4.esm` (`FO4Port.esm:0x0119AE`, `LadderMetalTall01`).
  - **Coordinates:** Exterior merged arrival `(-2288.797, -1364.037, 110.818)` m; interior arrival `(-2.965, 3.099, 0.000)` m.
  - **State & Locks:** `0` Initially Disabled refs, `0` `XESP` parents, `0` scripts. Contains `1` locked container: `Loot_Prewar_Safe` (`0A413B:Fallout4.esm` -> `FO4Port.esm:0x01195B`, Advanced lock `50`), plus pre-war food/gold bars/bed (critical Survival-mode shelter right out of Vault 111!).

---

### 3.3 Red Rocket Truck Stop & Mole Rat Den (`RedRocket01`)

- **Red Rocket Exterior & Garage State (`FO4TerrainCore.esm`):**
  - **Workshop Workbench (`RedRocketWorkshopREF`):** `054BAE:Fallout4.esm` -> **ALREADY promoted** in `FO4TerrainCore.esm:0x00D271` (base `0x0A2ECD`, merged `(-2205.490, -1564.001, 105.143)` m).
  - **Garage Door & Button (`docs/terrain/garage-button.md`):** `056BBA` (`RedR_ButtonBox` -> `FO4TerrainCore.esm:0x00DCC6`, base `0x0A2D5A`) is **already `XLKR`-wired** via `DefaultActivateLinkedRefOnActivate` to `056331` (`RedRGarageDoor` -> `FO4TerrainCore.esm:0x00D9B7`, base `0x0A2D5F`) in `candidate-2e`'s `objects.json["garage_buttons"]`. **Remaining gap:** `RedRGarageDoor.nif` is a skinned mesh whose `Opening`/`Closing` clips are refused by the static door rigger, so `0x00D9B7` is currently an inert `ACTI`. **Practical A3 fix:** Attach a lightweight toggle script on `0x00D9B7` (or keep it open/disable-on-activate toggle until skinned door rigging lands) so pressing the button opens physical walk-in access to the garage!
  - **Pedestrian Doors (`4x RedRPedDoor01`):** `05632F` (`0x00D9B6`), `056332` (`0x00D9B8`), `056333` (`0x00D9B9`), `056334` (`0x00D9BA`) are currently static `REFR`s in `FO4TerrainCore.esm`. Promote to swinging `DOOR`s (or open-by-default) so the player can walk into the Red Rocket office (`RedRocketTerminal` `048506`) and garage without jumping through broken windows.
  - **Dogmeat & Mole Rat Ambush:** `DogmeatRef` (`01D162:Fallout4.esm`, `NPC_ 01D15C`) stands at merged `(-2186.02, -1543.74, 105.24)` m; `5` `LvlMoleratAmbush` `ACHR`s (`01D969..02570D`, Initially Disabled `True`) ambush when approaching the workshop.
- **Red Rocket Mole Rat Den (`RedRocket01`, `FO4Port.esm:0x002338`):**
  - **Special Wiring Requirement (`autoload_activator`):** Both the exterior cave entrance (`08EB65:Fallout4.esm`, local `(-994.948, 1109.490, 98.684)` m -> merged `(-2194.948, -1590.510, 98.684)` m) and interior exit (`05E844:Fallout4.esm`, `(-1.659, 2.416, 0.0)` m) use `AutoloadDoor` (`AutoLoadMarker01.nif`), which both `FO4TerrainCore.esm` and `FO4Port.esm` skip as `editor_marker`.
  - **A3 Fix (Zero Reconversion):** Place an explicit pair of `FO4SF_LoadDoor` activator references in a thin companion plugin (or `FO4SFMission` / `FO4SFPathDoors.esm`) at the cave mouth merged `(-2194.948, -1590.510, 98.684)` m -> `FO4Port_RedRocket01` arrival `(0.049, -6.622, -0.006)` m, and interior exit `(-1.659, 2.416, 0.0)` m -> exterior merged `(-2195.530, -1595.857, 99.771)` m.
  - **State & Locks:** `0` Initially Disabled refs, `0` `XESP` parents, `1` Novice-locked safe (`08CC2F` -> `FO4Port.esm:0x0024D7`, lock `1`), plus the Fusion Core pickup behind the cave brain fungus (valuable alternate core for `Min00`!).

---

### 3.4 Concord Buildings on the Route

| Building | Cell / Shell | Two-Way Doors | Locks, Enable States & Route Mechanics |
|---|---|---|---|
| **Concord Civic Access** | `ConcordCivicAccess01` (`FO4Port:0x0119AF`) | `3` real-mesh pairs: south drainage pipe (`02C9A5`/`0x0072A9` <-> `023F6C`/`0x012024`), NE manhole (`04C3DE`/`0x00BAF2` <-> `04BD48`/`0x012025`), SW manhole (`04C3E0`/`0x00BAF3` <-> `04C38B`/`0x012026`) | `3` Initially Disabled, `8` `XESP` (`078BA4` x4, `0B1EB3` `DeathclawFenceEnabler` x4). Contains **chained shortcut door** `0645DA` (`0x012027`, `ChainedDoor`) + chain activator `0645DB` (`0x012028`, `DoorChain`) — needs one-way unchain script or unlocked default so players exiting the Deathclaw tunnel aren't trapped. Contains `2` Novice containers (`06554A`, `0EEF22`) and mirelurk/radroach spawns. |
| **Concord Workhouse** | `ConcordFactory` (`FO4Port:0x01202C`) | `3` real-mesh pairs: upper (`0E3DAD`/`0x02AD45` <-> `0E3D69`/`0x012240`), east (`0E3DA1`/`0x02AD42` <-> `0E3D94`/`0x012241`), west (`0E3DAB`/`0x02AD43` <-> `0E3D95`/`0x012242`) | `0` Initially Disabled, `0` `XESP`. `1` Advanced locked safe (`0E3D84` -> `0x0120DD`, lock `50`). Clean combat/loot flanking building on north Concord street. |
| **Concord Speakeasy** | `ConcordSpeakeasy` (`FO4Port:0x012245`) | `3` real-mesh pairs: upper (`07895C`/`0x013FCD` <-> `0788F7`/`0x012536`), east (`07895D`/`0x013FCE` <-> `0788F6`/`0x012537`), south (`07895F`/`0x013FCF` <-> `07895E`/`0x012538`) | `0` Initially Disabled, `0` `XESP`. `1` Advanced locked bedroom door (`0789BB` -> `0x01228D`, lock `50`) and `1` Advanced safe (`0855A6` -> `0x012342`, lock `50`). Key sniper/cover building directly facing the Museum street fight. |
| **Concord Church** | **Open exterior shell** (`BldChurch01Open` `03D7D9` in `FO4TerrainCore.esm`, cell `(-14, 16)`) | None (open doorway & interior stairs `08193E` + attic `21A298`) | **No interior cell needed.** Already placed in `FO4TerrainCore.esm` directly south of the Museum (`(-2017.14, -1726.79, 88.55)` m); players can climb the church steeple stairs and jump straight onto the crashed Vertibird tail (`0AB4FD`) as an alternate out-of-order roof approach! |

---

## 4. Two-Way `FO4SF_LoadDoor` Wiring Table (`R10` 3-Retry Safe)

Every real-mesh door pair below uses the exact 6-property `FO4SF_LoadDoor` VMAD layout (`DestinationPlugin`, `DestinationId`, `DestinationX`, `DestinationY`, `DestinationZ`, `UseDestinationPosition = True`) verified in `scripts/terrain/vmad_patch.py` and `scripts/door_bridge/FO4SF_LoadDoor.psc`:
- **`R10` 3-Try Safety:** `FO4SF_LoadDoor.psc` defaults `MoveRetries = 2` (`1` initial `MoveTo` + `2` retries = `3` total tries at `0.5 s` interval). If arrival still fails after `3` attempts, the script returns the player to `Self`, skips `SetPosition`, and logs `FO4SF_LoadDoor load door arrival failed n=3 door=<id>` once.
- **Persistent Arrival Markers:** Exterior arrival markers live in `FO4Core_Commonwealth`'s persistent cell (`0x001805`, flags `0x400`, starting at `0x0A7800` after existing markers); interior arrival markers live in each `FO4Port.esm` cell's persistent children group (`flags 0x400`), starting cleanly at `interiors_b10`'s `HEDR.nextObjectId = 0x074CD3` (`0x074CD3..0x074CDF` for A3, `0x074CE0..0x074CE4` for A4 Corvega), preserving all `15` earlier markers (`00E175..00E183`) byte-identically!
- **Merged Exterior Coordinates:** Every interior -> exterior return VMAD uses `local + (-1200.0, -2700.0, 0.0)` (measured `MERGE_MEASURED` offset).

| # | Door ID | Cell (`FO4Port`) | Mode | Ext Core `REFR` (`FO4`) | Int Port `REFR` (`FO4`) | Port Marker | Core Marker | Merged Exterior Arrival `(X, Y, Z)` m | Interior Arrival `(X, Y, Z)` m | Lock |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `museum_front` | `ConcordMuseum01` (`012540`) | `real_mesh` | `004B2B` (`01AC07`) | `01303B` (`077D22`) | `074CD3` | `0A7800` | `(-2011.14, -1697.54, 89.09)` | `(8.06, 0.00, -0.91)` | — |
| 2 | `museum_balcony` | `ConcordMuseum01` (`012540`) | `real_mesh` | `005054` (`01D22F`) | `013045` (`01B94A`) | `074CD4` | `0A7801` | `(-2010.06, -1698.45, 98.49)` | `(12.04, 0.03, 9.14)` | `255` (int) |
| 3 | `museum_roof` | `ConcordMuseum01` (`012540`) | `real_mesh` | `00677F` (`029AD8`) | `013048` (`02C1C6`) | `074CD5` | `0A7802` | `(-1990.58, -1724.18, 97.56)` | `(-21.90, 8.68, 9.14)` | — |
| 4 | `sanctuary_root_cellar_hatch` | `SanctuaryBasementJahani` (`011918`) | `real_mesh` | `01CF77` (`0A36EB`) | `0119AE` (`0A3701`) | `074CD6` | `0A7803` | `(-2288.80, -1364.04, 110.82)` | `(-2.97, 3.10, 0.00)` | — |
| 5 | `red_rocket_mole_rat_cave` | `RedRocket01` (`002338`) | `autoload_activator` | *(explicit ACTI)* (`08EB65`) | *(explicit ACTI)* (`05E844`) | *(companion)* | *(companion)* | `(-2195.53, -1595.86, 99.77)` | `(0.05, -6.62, -0.01)` | — |
| 6 | `civic_access_south_pipe` | `ConcordCivicAccess01` (`0119AF`) | `real_mesh` | `0072A9` (`02C9A5`) | `012024` (`023F6C`) | `074CD7` | `0A7804` | `(-2073.20, -1653.64, 82.55)` | `(136.85, -64.90, 10.83)` | — |
| 7 | `civic_access_ne_manhole` | `ConcordCivicAccess01` (`0119AF`) | `real_mesh` | `00BAF2` (`04C3DE`) | `012025` (`04BD48`) | `074CD8` | `0A7805` | `(-2001.83, -1656.00, 86.61)` | `(68.33, -90.40, 15.56)` | — |
| 8 | `civic_access_sw_manhole` | `ConcordCivicAccess01` (`0119AF`) | `real_mesh` | `00BAF3` (`04C3E0`) | `012026` (`04C38B`) | `074CD9` | `0A7806` | `(-2067.47, -1679.32, 88.32)` | `(89.26, -44.73, 12.66)` | — |
| 9 | `workhouse_upper` | `ConcordFactory` (`01202C`) | `real_mesh` | `02AD45` (`0E3DAD`) | `012240` (`0E3D69`) | `074CDA` | `0A7807` | `(-2034.81, -1617.77, 103.92)` | `(4.51, -0.89, 6.49)` | — |
| 10 | `workhouse_east` | `ConcordFactory` (`01202C`) | `real_mesh` | `02AD42` (`0E3DA1`) | `012241` (`0E3D94`) | `074CDB` | `0A7808` | `(-2030.65, -1620.52, 88.49)` | `(4.93, -6.10, -8.17)` | — |
| 11 | `workhouse_west` | `ConcordFactory` (`01202C`) | `real_mesh` | `02AD43` (`0E3DAB`) | `012242` (`0E3D95`) | `074CDC` | `0A7809` | `(-2044.22, -1616.50, 88.32)` | `(-4.72, -0.32, -8.14)` | — |
| 12 | `speakeasy_upper` | `ConcordSpeakeasy` (`012245`) | `real_mesh` | `013FCD` (`07895C`) | `012536` (`0788F7`) | `074CDD` | `0A780A` | `(-2036.24, -1651.03, 91.97)` | `(7.18, 16.14, 7.31)` | — |
| 13 | `speakeasy_east` | `ConcordSpeakeasy` (`012245`) | `real_mesh` | `013FCE` (`07895D`) | `012537` (`0788F6`) | `074CDE` | `0A780B` | `(-2029.26, -1653.08, 88.49)` | `(15.25, 10.44, 3.66)` | — |
| 14 | `speakeasy_south` | `ConcordSpeakeasy` (`012245`) | `real_mesh` | `013FCF` (`07895F`) | `012538` (`07895E`) | `074CDF` | `0A780C` | `(-2038.16, -1663.66, 88.49)` | `(4.46, -2.17, 3.77)` | — |
| 15 | `corvega_main_lower` (A4) | `CorvegaAssemblyPlant01` (`01535A`) | `real_mesh` | `00DF1B` (`057280`) | `017957` (`057B0E`) | `074CE0` | `0A780D` | `(-1712.43, -2219.93, 53.61)` | `(-9.14, 22.86, -3.66)` | — |
| 16 | `corvega_main_upper` (A4) | `CorvegaAssemblyPlant01` (`01535A`) | `real_mesh` | `00DF1C` (`057281`) | `017956` (`057B0F`) | `074CE1` | `0A780E` | `(-1712.41, -2220.02, 60.79)` | `(-9.14, 22.85, 1.83)` | — |
| 17 | `corvega_east_roof` (A4) | `CorvegaAssemblyPlant01` (`01535A`) | `real_mesh` | `00DF1E` (`057283`) | `017955` (`057B11`) | `074CE2` | `0A780F` | `(-1676.86, -2226.40, 64.44)` | `(24.82, 18.22, 5.49)` | — |
| 18 | `corvega_west_hatch` (A4) | `CorvegaAssemblyPlant01` (`01535A`) | `real_mesh` | `06B3E6` (`1A842A`) | `017953` (`1A8429`) | `074CE3` | `0A7810` | `(-1744.63, -2215.32, 68.11)` | `(-42.02, 29.38, 3.87)` | — |
| 19 | `corvega_south_door` (A4) | `CorvegaAssemblyPlant01` (`01535A`) | `real_mesh` | `09CB27` (`22F1EB`) | `017950` (`22F1EC`) | `074CE4` | `0A7811` | `(-1695.33, -2248.37, 64.48)` | `(6.50, -3.69, 5.53)` | — |
| 20 | `corvega_sewer_pipe` (A4) | `CorvegaAssemblyPlant01` (`01535A`) | `autoload_activator` | *(explicit ACTI)* (`0CFB19`) | *(explicit ACTI)* (`0CFA97`) | *(companion)* | *(companion)* | `(-1661.76, -2195.70, 45.74)` | `(56.71, 63.89, -21.17)` | — |

---

## 5. Offline Reproduction & Door Patching Commands (Zero Reconversion)

```bash
# 1. Verify all 8 staged cells + 18 real-mesh doors against pinned interiors_b10 & candidate core (read-only)
python scripts/terrain/a3_path_places.py audit-stage --port <interiors-b10-port> --core <cand-core-dir>

# 2. Generate deterministic R10-safe FO4SF_LoadDoor wiring plan for A3 (+ optional A4 Corvega)
python scripts/terrain/a3_path_places.py plan --groups a3_all --out <scratch>/a3_doors_plan.json
python scripts/terrain/a3_path_places.py plan --groups all --out <scratch>/a3_a4_doors_plan.json

# 3. Once FO4TerrainCore.esm promotes those exterior doors into a new core build, patch a NEW copy of interiors_b10:
python scripts/terrain/a3_path_places.py patch-port \
  --port <interiors-b10-port> \
  --core <new-core-with-a3-doors> \
  --out <new-port-a3-stage> \
  --keep-markers <interiors-b10-port>/doors.json \
  --allow-new-doors
```

---

## 6. PC Verification Card Rows (`OFFLINE ONLY — UNPROVEN IN GAME`, `P3`-Safe)

> Every ```` ```console ```` block below obeys `P3` (zero `M`, `N`, or `V` letters). `coc` commands live inside `<starfield-dir>/a3*.txt` batch files.

| Card Row | Place / Check | Player Action / Batch | Expected In-Game & `fo4sf.0.log` Result |
|---|---|---|---|
| **A3-1** | Museum of Freedom front door round trip | Walk up to Museum front doors (`04004B2B`), press **`E`** -> inspect lobby -> activate interior double door (`0201303B`) | `FO4SF_LoadDoor requested FO4Port.esm:...`, `phase=after_move` in `FO4Port_ConcordMuseum01` (`02012540`), clean return to `(-2011.14, -1697.54, 89.09)` without `arrival failed` |
| **A3-2** | Museum roof door + Vertibird / Power Armor | Exit roof door (`02013048`) -> confirm crashed Vertibird (`0401EC87`), Minigun activator (`04005119`), and Power Armor spot (`(-1995.73, -1723.10, 97.54)`) -> re-enter roof door (`0400677F`) | Roof arrival at `(-1990.58, -1724.18, 97.56)`, clean return inside upper gallery at `(-21.90, 8.68, 9.14)` |
| **A3-3** | Sanctuary Root Cellar hatch round trip | Walk behind northeast Sanctuary house -> press **`E`** on cellar hatch (`0401CF77`) -> inspect Root Cellar (`02011918`) -> press **`E`** on ladder (`020119AE`) | Forward arrival `(-2.97, 3.10, 0.00)` inside `FO4Port_SanctuaryBasementJahani`; return arrival `(-2288.80, -1364.04, 110.82)` |
| **A3-4** | Red Rocket exterior + Mole Rat Den (`coc` / activator) | Verify Red Rocket workbench (`0400D271`), garage button (`0400DCC6`), and Mole Rat Den entry (`bat a3rr` until activator plugin installs) | Workbench interactive; `FO4Port_RedRocket01` (`02002338`) loads textured with no missing-texture magenta |
| **A3-5** | Concord Route (`Civic Access`, `Workhouse`, `Speakeasy`, `Church`) | Test 1 round-trip door per building (`040072A9`, `0402AD42`, `04013FCE`) and walk through Concord Church open stairs to attic | All 3 interior cells load and return cleanly; Church open shell requires zero load door |

```console
bat a3sf
bat a3rr
```

```bat
; <starfield-dir>/a3sf.txt (diagnostic cell check ONLY if FO4Port.esm + FO4PortTextures2.esm are active without wired doors)
coc FO4Port_ConcordMuseum01

; <starfield-dir>/a3rr.txt
coc FO4Port_RedRocket01
```

---

## 7. Questions for the Owner

1. **Red Rocket Garage Door Receiver (`056331` / `0x00D9B7`):** Until skinned door rigging exists for `RedRGarageDoor.nif`, should pressing `RedR_ButtonBox` (`0x00DCC6`) temporarily toggle-disable/hide the garage door mesh so players can walk straight into the bay, or keep the bay open by default?
2. **`FO4PortTextures2.esm` Bundle Inclusion (`candidate-2f`+):** Should `candidate-2f` bundle `FO4Port.esm` + `FO4PortTextures2.esm` directly into the Track 1 `--profile player` install set (adds `~4.4 GB` of BA2s already staged in `interiors_b10/port`) or keep `FO4Port` as a separate `deploy_starfield.py install --batch` step paired with the player bundle?
