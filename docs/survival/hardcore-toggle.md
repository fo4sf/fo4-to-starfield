# Hardcore & Survival `GPOF` Gameplay Option (`FO4SFHardcore.esm`)

Core Fallout survival and hardcore toggle (`CF-8`, Phase B item `2b`) controlled by a native Starfield `GPOF` (`GameplayOption`) slider in **Settings -> Gameplay Options** (`FO4SF_GPO_Hardcore` inside `GPOG` `FO4SF_GPOG_Hardcore`), turning **Hunger, Thirst, and Sleep meters**, **ammunition weight**, and **Stimpak heal-over-time** ON and OFF cleanly at runtime with **zero conflict with held `SQ_ENV` (`0x248D20`)**.

- **Plugin writer & checker:** `dotnet/HardcoreToggle/Program.cs` (`build`, `check`, `fixture`, `selftest`)
- **Controller quest script:** `scripts/survival/FO4SF_HardcoreQuest.psc`
- **Stager / folder / verifier / log reader:** `scripts/survival/make_hardcore.py` and `src/fo4sf/survival/hardcore_log.py`
- **Ride-along installer:** `scripts/survival/hardcore_install.py` (`Data/FO4SFHardcore.install.json`)
- **Unit tests:** `tests/test_hardcore_toggle.py`

---

## 1. Record Layout (`FO4SFHardcore.esm`, Sole Master `Starfield.esm`)

Adds new `FO4SF_*` records only and overrides **zero** vanilla records (`Check()` explicitly refuses any foreign `ModKey` record or any reference to `SQ_ENV` `0x248D20`):

| Local FormID | Record Type | EditorID | Purpose |
| :--- | :--- | :--- | :--- |
| `0x800` | `GPOF` | `FO4SF_GPO_Hardcore` | Stepped float `GameplayOption` (`0 = OFF`, `1 = ON`, default `0`). |
| `0x801` | `GPOG` | `FO4SF_GPOG_Hardcore` | `GameplayOptionsGroup` leaf surfacing `FO4SF_GPO_Hardcore` in Settings -> Gameplay Options without requiring `SFBGS007.esm` as a master. |
| `0x802` | `GLOB` | `FO4SF_HardcoreEnabled` | `0/1` proxy global synced on `OnQuestInit`, `OnPlayerLoadGame`, and `OnGameplayOptionChanged` (`GameplayOption.NotifyGameplayOptionUpdateFinished()`). |
| `0x803..0x805` | `AVIF` | `FO4SF_Hunger`, `FO4SF_Thirst`, `FO4SF_SleepDeprivation` | `0..1000` (`DefaultToZero \| DamageIsPositive`) meters advancing with `Utility.GetCurrentGameTime()` (`+18/hr`, `+30/hr`, `+12/hr`) when Hardcore is ON. |
| `0x806` | `AVIF` | `FO4SF_AmmoWeightBurden` | Active carried ammunition burden (`lb`) subtracted reversibly from `CarryWeight` when Hardcore is ON (`0.0` when OFF). |
| `0x807..0x809` | `GLOB` | `FO4SF_HungerStage`, `FO4SF_ThirstStage`, `FO4SF_SleepStage` | `0..5` New Vegas `HUNG`/`DEHY`/`SLPD` sickness stages (`200 / 400 / 600 / 800 / 1000`) applying reversible `STR`/`END`/`AGI`/`INT` penalties. |
| `0x80A` | `GLOB` | `FO4SF_HardcoreFastTravelBlocked` | `1` when Hardcore is ON, `0` when OFF (consumed by Pip-Boy `MAP` fast-travel gate). |
| `0x820..0x822` | `ALCH` | `FO4SF_RationFood`, `FO4SF_PurifiedWater`, `FO4SF_Stimpak` | Food (`-250` Hunger), Water (`-250` Thirst), and Stimpak (`+60` HP instant when OFF; `+10` HP x `6` ticks over `6 s` when ON). |
| `0x825..0x828` | `AMMO` + `FLST` | `FO4SF_CaliberLight/Rifle/Heavy` + `FO4SF_WeightedAmmoList` | Base `Weight = 0.0` on `AMMO` records so OFF is truly weightless; when ON, `WeightedAmmoList` (`0.025`, `0.050`, `0.100`, and `0.035` lb/round) updates `CarryWeight` live via `OnItemAdded` / `OnItemRemoved`. |
| `0x830` | `QUST` | `FO4SF_HardcoreQuest` | `StartGameEnabled` quest (`stages 5, 10, 20, 30, 40, 50`) running `FO4SF_HardcoreQuest.pex`. |

### Zero Conflict With Held `SQ_ENV` (`0x248D20`)
`FO4SFNewGame.esm` stops Starfield's `SQ_ENV` (`0x248D20`) at cold start. `FO4SFHardcore.esm` never overrides `SQ_ENV`, never touches `ENV_*` Actor Values, and never starts `SQ_ENV` or `SQ_PEO_Sustenance`. On init, reload, every `GPOF` change, and every card stage, `FO4SF_HardcoreQuest` queries `SQ_ENV.IsRunning()` read-only and logs `sq_env_running=false`.

---

## 2. PC Card for Claude (PC)

### Step 1 — Offline Unit Tests, Precheck, Stage, Clean-Core Fold & Verify (Game Closed)
```powershell
$env:FO4SF_DOTNET_TESTS = '1'
python -m unittest tests.test_hardcore_toggle
python scripts/guard.py

python scripts/survival/make_hardcore.py precheck `
  --content-resources "<STARFIELD_DIR>\Tools\ContentResources.zip"

python scripts/survival/make_hardcore.py stage `
  --out "<STAGE_DIR>\hardcore-stage" `
  --starfield "<STARFIELD_DIR>\Data\Starfield.esm" `
  --compiler "<STARFIELD_DIR>\Tools\Papyrus Compiler\PapyrusCompiler.exe" `
  --content-resources "<STARFIELD_DIR>\Tools\ContentResources.zip"

python scripts/survival/make_hardcore.py fold `
  --stage "<STAGE_DIR>\hardcore-stage" `
  --core-dir "<CLEAN_CORE_DIR>" `
  --out "<STAGE_DIR>\folded-hardcore" `
  --starfield "<STARFIELD_DIR>\Data\Starfield.esm" `
  --hardlink

python scripts/survival/make_hardcore.py verify `
  --exp-dir "<STAGE_DIR>\folded-hardcore" `
  --plan "<STAGE_DIR>\hardcore-stage\plan.json" `
  --starfield "<STARFIELD_DIR>\Data\Starfield.esm"
```
- **Offline PASS lines:**
  - `Ran ... tests ... OK` and `guard: ok`
  - `precheck: ok`
  - `FO4SFHardcore.esm: header Master, masters [Starfield.esm], next 0x831, zero foreign overrides (SQ_ENV 0x248D20 untouched)` and `all checks pass`
  - `verify: ok`

### Step 2 — Ride-Along In-Game Verification (Paired With Installed Core Hold-Off)
1. With Starfield closed, install the ride-along package (`Data/FO4SFHardcore.install.json` leaves `FO4SFExp.install.json` untouched):
   ```powershell
   python scripts/survival/hardcore_install.py install --dir "<STAGE_DIR>\hardcore-stage" --starfield "<STARFIELD_DIR>"
   ```
2. Launch Starfield into a throwaway New Game / post-stage-20 core session (where `FO4SFNewGame.esm` has held `SQ_ENV` stopped).
3. *(Menu check)* Open **Settings -> Gameplay Options**, locate **Survival & Hardcore Options -> Hardcore Survival Mode**, flip **OFF -> ON -> OFF**, and close the menu (`FO4SFHardcore.0.log` records `reason=gpof_menu` and `sq_env_running=False`).
4. *(Deterministic stage sequence — `<XX>` is `FO4SFHardcore.esm`'s 2-hex load index)* Run in console, waiting `2 s` between commands:
   ```text
   setstage <XX>000830 10
   setstage <XX>000830 20
   setstage <XX>000830 30
   setstage <XX>000830 40
   setstage <XX>000830 50
   ```
5. Quit without saving, read the log, and uninstall the ride-along package:
   ```powershell
   python scripts/survival/make_hardcore.py log
   python scripts/survival/hardcore_install.py uninstall --starfield "<STARFIELD_DIR>"
   ```
- **In-Game PASS lines (`make_hardcore.py log`, exit code `0`):**
  - `PASS  sq_env_never_conflicted`
  - `PASS  stage10_meters_and_ammo_on`
  - `PASS  stage20_relief_reduced_meters`
  - `PASS  stage30_off_reverted_cleanly`
  - `PASS  stimpak_hot_when_on`
  - `PASS  stimpak_instant_when_off`
  - `PASS  all_stages_completed`
  - `verdict: PASS`
