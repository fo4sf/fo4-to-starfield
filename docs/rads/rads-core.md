# Radiation & Optional Mutations Core (`FO4SFRads.esm`)

Core implementation of radiation sources, dual-rule radiation penalties, RadAway / Rad-X aid, Pip-Boy `STAT` exposure, and optional mutation `PERK`s. Builds on the engine findings proven in [docs/research/rads-probe.md](../research/rads-probe.md) without modifying existing probe or native UI files.

## 1. Architecture Overview

| Component | Path | Responsibility |
|---|---|---|
| Plugin writer & offline validator | `dotnet/RadsCore/Program.cs` | `build`, `check`, `fixture`, `selftest` for `FO4SFRads.esm` (mastered on `Starfield.esm` only; zero overrides) |
| Runtime quest script | `scripts/rads/FO4SF_RadsCoreQuest.psc` | Passive 1.0 s live-play radiation/aid/mutation loop, gameplay-option sync, and deterministic verification stages `5` and `10..60` |
| Stager, core folder, verifier & CLI | `scripts/rads/make_rads_core.py` | `precheck`, `stage`, `fold` (`--hardlink` supported), `verify`, `log`, `console` |
| Ride-along installer | `scripts/rads/rads_core_install.py` | Standalone install/uninstall/status/order/active using `Data/FO4SFRads.install.json` (leaves `FO4SFExp.install.json` untouched) |
| Log reader & reference rules | `src/fo4sf/rads/core_log.py` | Structured `FO4SFRADSCORE` log parser, reference penalty/resistance math, and `PASS` / `INCONCLUSIVE` / `FAIL` report |
| Unit & contract suite | `tests/test_rads_core.py` | Synthetic plugin/script/log/fold/install/raw-byte and `RadsCore selftest` suite |

---

## 2. Dual Radiation Rules (`FO4SF_RadsRule` / `FO4SF_GPO_RadsRule`)

Controlled by `GLOB` `FO4SF_RadsRule` (`0x806`) and Gameplay Option `GPOF` `FO4SF_GPO_RadsRule` (`0x808`, grouped under `GPOG` `FO4SF_GPOG_Radiation` `0x80A`):

1. **Mode A (`FO4SF_RadsRule = 0`, Default — Maximum-HP Cap):**
   - Lowers effective maximum `Health` by `-10%` of base `Health` per `100` rads (`frac = min(0.90, rads / 1000.0)`).
   - Clamped below `1000` rads so effective maximum `Health` stays `>= 10%` of base `Health` (`0..999` rads).
   - `1000` rads is **Fatal** (`FO4SF_RadsStage = 5`, `Actor.Kill` in live play).
2. **Mode B (`FO4SF_RadsRule = 1` — Rad-Sickness Stat Thresholds):**
   - Maximum `Health` is uncapped (`0` Health delta); radiation sickness applies threshold penalties to `Endurance`, `Agility`, and `Strength`:
     - **Stage `0` (`0..199` — None):** `0` penalties
     - **Stage `1` (`200..399` — Minor):** `-1 END`
     - **Stage `2` (`400..599` — Advanced):** `-2 END, -1 AGI`
     - **Stage `3` (`600..799` — Critical):** `-3 END, -2 AGI, -1 STR`
     - **Stage `4` (`800..999` — Deadly):** `-3 END, -2 AGI, -2 STR`
     - **Stage `5` (`1000` — Fatal):** `-3 END, -2 AGI, -2 STR` + **Fatal** (`Actor.Kill` in live play)
3. **Zero-Drift Mode Switching:**
   - `FO4SF_RadsCoreQuest` tracks `AppliedHealth`, `AppliedEnd`, `AppliedAgi`, and `AppliedStr` independently.
   - Changing `FO4SF_RadsRule` (via Settings -> Gameplay Options `OnGameplayOptionChanged` or console/script `SetValue`) immediately unwinds the previous mode's exact `ModValue` deltas and applies the active mode's deltas with zero cumulative drift.

---

## 3. Radiation Sources, Resistance, & RadAway Cure

All three radiation source families feed `FO4SF_Rads` (`0..1000`, `DefaultToZero | DamageIsPositive`) and scale incoming exposure by `FO4SF_RadResist` (`0x804`, `effective = raw * 100 / (100 + max(0, resist))`):

1. **Hazard Zones & Placed Emitters (`HAZD` + `ACTI`):**
   - `HAZD` `FO4SF_RadsHazard` (`0x828`), cloned from a vanilla hazard template (`ENV_PoolHazard_Radiation` when present), fires `SPEL` `FO4SF_RadsHazardSpell` (`0x813`, `FireAndForget` / `Touch`, `+15` rads/tick via `MGEF` `FO4SF_RadsHazardEffect` `0x812` with `Detrimental` kept and `SecondActorValue = FO4SF_Rads`).
   - `ACTI` `FO4SF_RadsEmitter` (`0x82A`), tagged with `KYWD` `FO4SF_Kw_RadsEmitter` (`0x829`), provides `+15` raw rads/s within `8.0 m` for placed barrels, craters, and radioactive props.
2. **Irradiated Water (`WATR` + Passive Immersion Detector + Dirty Water):**
   - `WATR` `FO4SF_IrradiatedWater` (`0x82B`, flagged `Dangerous`) links `ConsumeSpell = FO4SF_WaterDrinkSpell` (`+25` rads) and `ContactSpell = FO4SF_WaterContactSpell` (`+5` rads).
   - Passive `SPEL` `FO4SF_AbWaterDetect` (`0x817`, `Ability` / `ConstantEffect` / `Self`, conditioned on `IsInWater == 1`) sets `AVIF` `FO4SF_InWater` (`0x805`) to `1` while wading (`+5` raw rads/s), and `OnPlayerSwimming` tracks active swimming (`+10` raw rads/s).
3. **Irradiated Ingestibles & Medical Aid (`ALCH`):**
   - `FO4SF_IrradiatedFood` (`0x822`): `+50` raw rads on consumption.
   - `FO4SF_DirtyWater` (`0x823`): `+25` raw rads on consumption.
   - `FO4SF_RadX` (`0x821`, Medicine): `+100` `FO4SF_RadResist` for `60 s` (halves incoming radiation at `+100` resist).
   - `FO4SF_RadAway` (`0x820`, Medicine): cures `-300` rads identically in Mode A and Mode B via the verified script `ModValue` route on `OnItemEquipped` + inventory consumption tracking.

---

## 4. Optional Mutations (`FO4SF_MutationsEnabled` / `FO4SF_GPO_Mutations`)

- **Default `0` (OFF)** via `GLOB` `FO4SF_MutationsEnabled` (`0x807`) and `GPOF` `FO4SF_GPO_Mutations` (`0x809`).
- When set to `1` (ON), gaining radiation above `200` rads across a `100`-rad threshold rolls an unowned mutation `PERK` from `FLST` `FO4SF_MutationPerks` (`0x835`), backed by `ConstantEffect` `Self` ability spells:
  - `0x830` `FO4SF_Mut_Marsupial` (`FO4SF_AbMut_Marsupial` `0x838`: `JumpSpeedMult +0.5`, `CarryWeight +20`, `Intelligence -1`)
  - `0x831` `FO4SF_Mut_SpeedDemon` (`FO4SF_AbMut_SpeedDemon` `0x839`: `SpeedMult +20`, `PlayerReloadSpeedMult +0.2`)
  - `0x832` `FO4SF_Mut_HealingFactor` (`FO4SF_AbMut_HealingFactor` `0x83A`: `HealRateMult +50`)
  - `0x833` `FO4SF_Mut_ScalySkin` (`FO4SF_AbMut_ScalySkin` `0x83B`: `DamageResist +50`, `EnergyResist +50`)
- Holding `PERK` `FO4SF_Perk_StarchedGenes` (`0x834`) locks mutations: radiation grants no new mutations and `FO4SF_RadAway` removes none.
- When `FO4SF_MutationsEnabled == 1` and `FO4SF_Perk_StarchedGenes` is not held, each `FO4SF_RadAway` cures `1` active mutation in addition to `-300` rads.

---

## 5. Pip-Boy `STAT` Data Contract (`FO4SFPipboyMenu`)

`FO4SFRads.esm` exposes deterministic local FormIDs so `FO4SFPipboyMenu` works immediately today **without editing `sfse/FO4SFPipboyMenu/*`** and gives `PopulatePipboyInfoObj` (`DataObj`) fixed IDs to resolve via `KitFileForm("FO4SFRads.esm", localId, ...)`:

| Local ID | Type | EditorID | Range | Pip-Boy `STAT` / `PopulatePipboyInfoObj` Role |
|---|---|---|---|---|
| `0x000800` | `AVIF` | `FO4SF_Rads` | `0..1000` | Automatically discovered today by `FO4SFPipboyMenu` (`kRadsLocalId = 0x800`, `Row=RADS\|rads` on `STAT/STATUS`) |
| `0x000801` | `AVIF` | `FO4SF_RadsCapPct` | `0..100` | Player Actor Value (`rads / 10.0`) for `STAT` health-bar red cap (`DataObj.CurrentHPGain = capPct / 100.0`) or `av:<XX>000801` |
| `0x000802` | `GLOB` | `FO4SF_RadsDisplayPct` | `0..100` | Global mirror of `FO4SF_RadsCapPct` (`0..100`%) for HUD/UI readers |
| `0x000803` | `GLOB` | `FO4SF_RadsStage` | `0..5` | Current radiation sickness tier (`0`=None .. `5`=Fatal) for `STAT/STATUS` `ActiveEffects` badge |
| `0x000820` | `ALCH` | `FO4SF_RadAway` | Inventory | Listed in `INV/ITEMS` today; supplies `DataObj.RadawayCount` and `UseRadaway()` target |
| `0x000821` | `ALCH` | `FO4SF_RadX` | Inventory | Listed in `INV/ITEMS` today; supplies `FO4SF_RadResist` (`0x000804`) buff readout |

Player `Health` (`0x0002D4`), `Strength` (`0x0002C2`), `Endurance` (`0x0002C4`), and `Agility` (`0x0002C7`) are updated directly via `Actor.ModValue`, so `[Page STAT/STATUS]` (`HEALTH`) and `[Page STAT/SPECIAL]` (`STRENGTH`, `ENDURANCE`, `AGILITY`) reflect Mode A and Mode B in real time.

---

## 6. PC Card (Build, Fold, Install, & In-Game Verification)

### Offline Stage & Clean-Core Fold (Game Closed)

```powershell
python scripts\rads\make_rads_core.py precheck --content-resources "<game-dir>\Tools\ContentResources.zip"
python scripts\rads\make_rads_core.py stage --out "<stage-dir>" --starfield "<game-dir>\Data\Starfield.esm" --compiler "<game-dir>\Tools\Papyrus Compiler\PapyrusCompiler.exe" --content-resources "<game-dir>\Tools\ContentResources.zip"
python scripts\rads\make_rads_core.py fold --stage "<stage-dir>" --core-dir "<core-dir>" --out "<folded-dir>" --starfield "<game-dir>\Data\Starfield.esm" --hardlink
python scripts\rads\make_rads_core.py verify --exp-dir "<folded-dir>" --plan "<stage-dir>\plan.json" --starfield "<game-dir>\Data\Starfield.esm"
```

Expected offline outputs:
- `precheck: ok`
- `all checks pass` (in `<stage-dir>\offline_check.txt`)
- `folded <folded-dir>: ... + FO4SFRads.esm + 1 script(s); verify ok`
- `verify: ok`

### Install Options (Game Closed, Authorized Runner Only)

- **Option A — Ride-along beside an existing install (reversible, own receipt `FO4SFRads.install.json`):**
  ```powershell
  python scripts\rads\rads_core_install.py install --dir "<stage-dir>" --starfield "<game-dir>"
  ```
- **Option B — Full folded core set:**
  Use the widened `exp_install.py install ... --plugins <core-plugins>,FO4SFRads.esm --pack` line printed at the bottom of `<folded-dir>\README.txt`.

### Automated Console Verification (`stages 10..60`, No Save Needed)

1. Launch with `FO4SFRads.esm` active, enter play (or load a throwaway test state; do not save), wait `5 s` for `init` in `FO4SFRadsCore.0.log`, and print this session's load-order quest ID commands:
   ```powershell
   python scripts\rads\make_rads_core.py console
   ```
2. In the in-game console (`~`), run the six printed stage commands (`<Q>` = quest FormID from `console`):
   - `setstage <Q> 10` (wait `3 s`: `ModValue` Health control + `FO4SF_Rads` write/read baseline)
   - `setstage <Q> 20` (wait `4 s`: `Rad-X` `-50%` resist check + `HAZD`/`FO4SF_RadsEmitter` + `FO4SF_RadsSpell` -> `200` rads, Mode A `-20%` HP cap)
   - `setstage <Q> 30` (wait `4 s`: irradiated water + `FO4SF_DirtyWater` + `FO4SF_IrradiatedFood` -> `600` rads, Mode A `-60%` HP cap)
   - `setstage <Q> 40` (wait `3 s`: `FO4SF_RadsRule` switch Mode A `0` <-> Mode B `1` at `600` rads; unwinds HP cap, applies `-3 END, -2 AGI, -1 STR` with zero drift)
   - `setstage <Q> 50` (wait `3 s`: enables `FO4SF_MutationsEnabled = 1`, grants mutation `PERK`, locks with `StarchedGenes` across `RadAway` #1 `650 -> 350`, unlocks and cures mutation + rads `350 -> 50` on `RadAway` #2)
   - `setstage <Q> 60` (wait `3 s`: verifies Mode A `>= 10%` floor at `950` rads, `1000` Fatal tier `5`, cures to `0` rads, verifies `0` drift across all stats)
3. Open Pip-Boy (`F10`) once on `STAT/STATUS` (`RADS` row) and `STAT/SPECIAL` (`STR`/`END`/`AGI` rows) to confirm live readout, then quit without saving and run:
   ```powershell
   python scripts\rads\make_rads_core.py log
   ```
4. **Expected `PASS` line** (exit code `0`):
   ```text
   PASS: stages 10..60 verified (Health ... (ModValue +10/-10); sources=..., mode_switches=2, mutations=3, radaways=6, drift=0)
   ```
5. **(Optional By-Hand Check):** Run `setstage <Q> 5` to add `3` `RadAway`, `2` `Rad-X`, `3` `Dirty Water`, and `3` `Irradiated Food` to inventory, consume them from the Aid tab or wade/swim in water, toggle **Radiation Penalty Rule** / **Radiation Mutations** in Settings -> Gameplay Options, and observe HUD notifications and Pip-Boy `STAT` updates.
6. Remove ride-along install when finished (game closed):
   ```powershell
   python scripts\rads\rads_core_install.py uninstall --starfield "<game-dir>"
   ```
