# Round 14 Travel Probe & Option B Loading-Screen Card (`r14-travel-probe`)

> - **Reachability Labels:**
>   - `Commonwealth` (`FO4TerrainCore.esm` / `FO4Core_Commonwealth`): **`REACHABLE`**
>   - `FarHarbor` (`FO4WorldFarHarbor.esm` / `FO4FH_FarHarbor`): **`TEST-STATION (coc only)`**
> - **Status:** `STAGED OFFLINE ONLY — NOT INSTALLED INTO <STARFIELD_DIR>, UNPROVEN IN GAME`
> - **Pending Owner Decisions (Rule 12):**
>   - Loading screens use **Option B (recommended default)**: override all `304` `Starfield.esm` `LSCR`s off via `FO4SF_SuppressVanillaLoadScreens == 0.0` + `4` `FO4SF_LSCR_*` records (`== 1.0`) with **blank tip text** (`DESC = ""`, **recommended default** pending owner decision).
>   - Reload recovery uses `finish_if_dest_ready_else_abort_clear` (**recommended default**).
> - **Rule 13:** Zero player-facing HUD debug text (`Debug.MessageBox` / `Debug.Notification`). All telemetry writes exclusively to `FO4SF_TravelProbe.0.log` and `GLOB`s `0x800..0x80B`.

---

## 1. Offline Stage Contents & Commands

Stage directory holds:
- `Data/FO4SFTravelProbe.esm` (`masters = ["Starfield.esm"]`; `GLOB`s `0x800..0x80B`, `MISC` `FO4SF_TravelToken` `0x810`, `QUST` `FO4SF_TravelProbeQuest` `0x820`, `CELL` `FO4SF_TravelTransitCell` `0x830`, persistent `REFR` `FO4SF_TravelTransitMarker` `0x831`)
- `Data/Scripts/FO4SF_TravelProbeQuest.pex` (compiled with Starfield `PapyrusCompiler.exe`)
- `Data/FO4SFLoadScreens.esm` (`masters = ["Starfield.esm"]`; `GLOB` `FO4SF_SuppressVanillaLoadScreens = 1.0`, `304` vanilla `LSCR` overrides gated `== 0.0`, `4` `FO4SF_LSCR_*` records gated `== 1.0`)
- `Data/textures/interface/loadscreens/fo4sf_load_blank_color.dds` (`8x8` generated black RGBA DDS)
- `probe_manifest.json` (SHA-256 inventory and offline check summary)

Offline build & verify commands:

```powershell
python scripts/world/make_travel_probe.py stage `
  --starfield "<STARFIELD_DIR>/Data/Starfield.esm" `
  --out "<STAGE_DIR>" `
  --compiler "<STARFIELD_DIR>/Tools/Papyrus Compiler/PapyrusCompiler.exe" `
  --content-resources "<STARFIELD_DIR>/Tools/ContentResources.zip"

python scripts/world/make_travel_probe.py check `
  --dir "<STAGE_DIR>" `
  --starfield "<STARFIELD_DIR>/Data/Starfield.esm"
```

---

## 2. In-Game Verification Plan (For Claude (PC) — Do Not Run Here)

Prerequisite: `FO4TerrainCore.esm` (`REACHABLE`) and `FO4WorldFarHarbor.esm` (`TEST-STATION (coc only)`) installed alongside `FO4SFTravelProbe.esm` and `FO4SFLoadScreens.esm`.

| Step | Console Command (`~`) | What It Tests | Expected Pass Signal (`FO4SF_TravelProbe.0.log` + `GLOB`) |
|---:|---|---|---|
| 1 | `setstage FO4SF_TravelProbeQuest 10` | **CW -> Far Harbor (`MoveTo` + `SetPosition`)** | Player moves to `FO4FH_FarHarbor` dry anchor; `FO4SF_TravelState == 0` (`CLEARED -> IDLE`), `FO4SF_TravelLoadedOK == 1`, `FO4SF_TravelFollowerOK == 1`, `FO4SF_TravelItemsOK == 1`, no Starfield `LSCR` art/text. |
| 2 | `setstage FO4SF_TravelProbeQuest 30` | **Exterior -> Transit Interior -> Exterior** | Transitions through `FO4SF_TravelTransitCell` (`0x000831`) and exits to `FO4FH_FarHarbor`; black placeholder screen with blank text only. |
| 3 | `setstage FO4SF_TravelProbeQuest 20` | **Far Harbor -> Commonwealth (`MoveTo` + `SetPosition`)** | Returns to `FO4Core_Commonwealth`; carried token & followers preserved (`FO4SF_TravelFollowerOK == 1`, `FO4SF_TravelItemsOK == 1`). |
| 4 | `setstage FO4SF_TravelProbeQuest 40` | **`Game.FastTravel` Comparison** | Evaluates `Game.FastTravel` timing & final worldspace vs Stage 10/20 `MoveTo` baseline. |
| 5 | `set FO4SF_TravelState to 2` + quickload (`F9`) | **Mid-Transition Reload Recovery (`OnPlayerLoadGame`)** | Logs `reload_recovery state=2`; clears fade + releases lock back to `FO4SF_TravelState == 0`. |
| 6 | `set FO4SF_SuppressVanillaLoadScreens to 0` + load screen | **Reversibility Check** | Re-enables vanilla `LSCR` conditions cleanly without removing plugins. |
