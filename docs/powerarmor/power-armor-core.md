# Power Armor Core (`CF-9` + `#806` Dual-Form Architecture)

## Overview

`FO4SFPowerArmor.esm` (sole master `Starfield.esm`) implements Fallout 4's climb-in Power Armor frame gameplay loop alongside Fallout: New Vegas's worn heavy Salvaged NCR Power Armor (`#806`), without modifying existing probe or startup plugins:

| Component | Path |
| :--- | :--- |
| Mutagen plugin builder, checker, fixture & self-test | `dotnet/PowerArmorCore/Program.cs` |
| Persistent runtime quest script | `scripts/powerarmor/FO4SF_PowerArmorCoreQuest.psc` |
| Offline stager, hardlink folder, verifier & log reader | `scripts/powerarmor/make_power_armor_core.py` |
| Reversible ride-along installer (`FO4SFPowerArmor.install.json`) | `scripts/powerarmor/power_armor_core_install.py` |
| User-log & Papyrus-log parser | `src/fo4sf/powerarmor/core_log.py` |
| Synthetic Python & `.NET` unit tests | `tests/test_power_armor_core.py` |

By default, `dotnet/PowerArmorCore build` runs in **clean-room mode** (`0` foreign record overrides), ensuring `FO4SFPowerArmor.esm` cannot interfere with non-Power-Armor gameplay when folded into the clean core set. Passing `--override-dfob` opts in to overriding Starfield's five empty Power Armor `DFOB` records (`PowerArmorRace_DO` `0x05C254`, `PowerArmorDefaultFrameFurniture_DO` `0x22BC97`, `PowerArmorDefaultFrameArmor_DO` `0x15503E`, `PowerArmorArmorKeyword_DO` `0x140C44`, `PowerArmorDefaultBatteryObject_DO` `0x0BD5C5`).

---

## Record Layout (`FO4SFPowerArmor.esm`)

| Local ID | Signature & EditorID | Role |
| :--- | :--- | :--- |
| `0x0800` | `CELL FO4SF_PATestCell` | Self-contained interior test cell (`coc FO4SF_PATestCell`) with arrival marker, frame, exit chair, 3 cores, and salvaged NCR set |
| `0x0801` | `FURN FO4SF_PowerArmorFrameFurn` | Climb-in frame furniture cloned from control chair + `FO4SF_Kw_PowerArmorFrameFurn` (`+ FurnitureTypePowerArmor` & `isPowerArmorFrame` under `--override-dfob`) |
| `0x0802` | `RACE FO4SF_PowerArmorRace` | Cloned from `HumanRace` (`0x00347D`), wired to `FO4SF_PowerArmorBodyPartData` (`0x0803`), `FO4SF_PowerArmorSkin` (`0x0804`), and `ArmorRace = HumanRace` |
| `0x0803` | `BPTD FO4SF_PowerArmorBodyPartData` | Cloned from `HumanBodyPartData` (`0x003481`) with all 6 limb condition `AVIF`s bound at `100%` `HealthPercent` |
| `0x0804` | `ARMO FO4SF_PowerArmorSkin` | Cloned from `Skin_Naked` (`0x000D64`) with cloned `ARMA`s naming both `HumanRace` and `FO4SF_PowerArmorRace` (prevents `f5d38adb` missing 3rd-person body) |
| `0x0805` | `QUST FO4SF_PowerArmorCoreQuest` | `StartGameEnabled` quest (`stages 10, 20, 30, 40`), zero properties, script `FO4SF_PowerArmorCoreQuest` |
| `0x0806` | `KYWD FO4SF_PAArmorKeyword` | Modular climb-in Power Armor piece keyword |
| `0x0807` | `KYWD FO4SF_Kw_SalvagedPowerArmor` | Worn heavy Salvaged NCR Power Armor keyword (no frame, no climb-in, no battery drain) |
| `0x0808` | `KYWD FO4SF_Kw_PowerArmorFrameFurn` | Identifies placed `FO4SF_PowerArmorFrameFurn` references anywhere in the world |
| `0x0809` | `MISC FO4SF_FusionCore` | Battery item carrying vanilla `isPowerArmorBattery` (`0x05BDAA`) in both `Keywords` and `KeywordFormComponent` |
| `0x080A` | `AVIF FO4SF_PAInPowerArmor` | `0..1` state value (`1` inside climb-in frame; remains `0` when wearing Salvaged NCR armor) |
| `0x080B` | `AVIF FO4SF_PAFusionCharge` | `0..100` active Fusion Core charge |
| `0x0810..0x0815` | `AVIF FO4SF_PACond_*` | `Head`, `Torso`, `LeftArm`, `RightArm`, `LeftLeg`, `RightLeg` limb condition `AVIF`s (`0..100`, default `100`) |
| `0x0816` | `ARMO FO4SF_PAFrameArmor` | Non-playable (`0x4`) frame base in `BODY` (`0x8`) + `isPowerArmorFrame` (`0x15503F`) + dual-race `ARMA`s |
| `0x0817..0x0819` | `ARMO FO4SF_PATorso` / `PAHelmet` / `PAPack` | Disjoint `SSBODY`, `SSHelmet`, and `SSBackpack` slots preserving template keywords/stats (`59a76008` & `8fe7c27e` fixes) + dual-race `ARMA`s |
| `0x081A..0x081B` | `ARMO FO4SF_SalvagedNCRPowerArmor` / `Helmet` | Playable worn heavy `ARMO` on `HumanRace`, high ballistic DR (`240` / `80`), zero `isPowerArmorFrame`, `-1` Agility on body |
| `0x081C..0x081D` | `ENCH` / `MGEF` `FO4SF_*_SalvagedNCRAgility` | `ConstantEffect` `Self` `ValueModifier` (`Detrimental`, `SecondActorValue = Agility 0x0002C7`, empty `Archetype.Association`) |

---

## Offline Stage, Fold & Verify Recipe

```powershell
$env:TMP = $env:TEMP = "<SCRATCH_TMP>"
$py = "<PYTHON_EXE>"
$sfDir = "<SF_DIR>"

# 1. Precheck required Papyrus declarations in ContentResources.zip
& $py scripts/powerarmor/make_power_armor_core.py precheck `
  --content-resources "$sfDir\Tools\ContentResources.zip"

# 2. Stage FO4SFPowerArmor.esm + FO4SF_PowerArmorCoreQuest.pex
& $py scripts/powerarmor/make_power_armor_core.py stage `
  --out "<STAGE_DIR>" `
  --starfield "$sfDir\Data\Starfield.esm" `
  --compiler "$sfDir\Tools\Papyrus Compiler\PapyrusCompiler.exe" `
  --content-resources "$sfDir\Tools\ContentResources.zip"

# 3. Verify standalone stage
& $py scripts/powerarmor/make_power_armor_core.py verify `
  --dir "<STAGE_DIR>" `
  --starfield "$sfDir\Data\Starfield.esm"

# 4. Fold into clean-core with --hardlink (never mutates <CORE_DIR>\README.txt)
& $py scripts/powerarmor/make_power_armor_core.py fold `
  --core-dir "<CORE_DIR>" `
  --stage "<STAGE_DIR>" `
  --out "<FOLDED_DIR>" `
  --hardlink `
  --starfield "$sfDir\Data\Starfield.esm"

# 5. Verify folded output (prints `verify: ok`)
& $py scripts/powerarmor/make_power_armor_core.py verify `
  --dir "<FOLDED_DIR>" `
  --starfield "$sfDir\Data\Starfield.esm"
```

For standalone ride-along installation next to an already-installed core set (game closed):

```powershell
& $py scripts/powerarmor/power_armor_core_install.py install --dir "<STAGE_DIR>" --starfield "<SF_DIR>"
& $py scripts/powerarmor/power_armor_core_install.py uninstall --starfield "<SF_DIR>"
```

---

## In-Game PC Verification Card (Throwaway Save `FO4SF_Throwaway_PowerArmor_DeleteMe`)

> [!IMPORTANT]
> Run with the game closed during install/uninstall. Use **only** the named throwaway save **`FO4SF_Throwaway_PowerArmor_DeleteMe`** for the save-quit-reload check and delete **`FO4SF_Throwaway_PowerArmor_DeleteMe`** at the end of the session.

1. **Install & Enter Test Cell:**
   - Install `<STAGE_DIR>` via `power_armor_core_install.py install` (or install `<FOLDED_DIR>` via `exp_install.py` with the full widened `--plugins` list in `<FOLDED_DIR>\README.txt`).
   - Launch Starfield, load a non-opening test character wearing a spacesuit, helmet, pack, and apparel, open the console, and run:
     ```text
     coc FO4SF_PATestCell
     ```
   - Note the character's worn outfit in third person and inventory. On the right (`-Y`) are `3` placed `FO4SF_FusionCore` items and the `FO4SF_SalvagedNCRPowerArmor` + `FO4SF_SalvagedNCRPowerHelmet` set; ahead (`+X`) is `FO4SF_PowerArmorFrameFurnRef`; on the left (`+Y`) is `FO4SF_PAExitChairRef`.

2. **Climb-In Frame + 6-Limb `BPTD` + `FusionCore` Load:**
   - Pick up **2** of the `3` `FO4SF_FusionCore` items on the right (leave the 3rd on the floor for step 4).
   - Walk to `FO4SF_PowerArmorFrameFurnRef` ahead and activate it to climb in. Stand up (`E` / move) once `"Power Armor ON"` appears.
   - Verify in third person: full character body and Mark 1-plated Power Armor suit/helmet/pack render cleanly (no missing torso/hands), empty frame furniture disappears while worn, `1` `FO4SF_FusionCore` was consumed (`1` spare remains), `FO4SF_PAFusionCharge = 100`, `FO4SF_PAInPowerArmor = 1`, and all 6 `FO4SF_PACond_*` limb values read `100`.

3. **Movement Drain + Save, Quit & Reload Persistence (`FO4SF_Throwaway_PowerArmor_DeleteMe`):**
   - Walk around the platform for `10-15 s` so `FO4SF_PAFusionCharge` visibly drains below `100`.
   - Open the console and create the named throwaway save while inside the frame:
     ```text
     save FO4SF_Throwaway_PowerArmor_DeleteMe
     ```
   - Quit completely to desktop, relaunch Starfield, and load **`FO4SF_Throwaway_PowerArmor_DeleteMe`**.
   - Verify after reload: player is still inside Power Armor (`4/4` PA pieces equipped, `FO4SF_PAInPowerArmor = 1`, partial `FO4SF_PAFusionCharge` preserved, 6 limb conditions at `100`, and `FO4SFPACore.0.log` records `reload_sync inpa=true equipped_pa=4 saved_worn=...`).

4. **Auto-Reload & Zero-Charge Over-Encumbered Slow-Walk Penalty:**
   - Walk around (or run `setstage <QuestHex> 20` from the `quest form id` printed by `make_power_armor_core.py log`) until the first core reaches `0%`: verify `"Fusion Core loaded (charge 100%, spare cores: 0)"` auto-consumes the spare core and resets charge to `100%`.
   - Drain the second core to `0%` with `0` spare cores: verify `"Fusion Core depleted (0% charge, 0 spare cores): slow-walk penalty active"` applies native over-encumbrance slow walk.
   - Pick up the **3rd** `FO4SF_FusionCore` from the floor: verify it auto-loads to `100%` and immediately clears the slow-walk penalty.

5. **Exit Frame + Standing `FURN` + Exact Prior Outfit Restore:**
   - Activate `FO4SF_PAExitChairRef` on the left (or run `setstage <QuestHex> 30` anywhere in the world) and stand up.
   - Verify: all 4 PA pieces are unequipped and removed, `HumanRace` is restored, `FO4SF_PAInPowerArmor = 0`, `FO4SF_PowerArmorFrameFurnRef` stands enabled at the exit spot ready for re-entry, and **every piece of the player's prior outfit is re-equipped** in third person and inventory.

6. **FNV Salvaged NCR Power Armor (`#806` Plain Worn Heavy `ARMO`):**
   - Pick up `FO4SF_SalvagedNCRPowerArmor` and `FO4SF_SalvagedNCRPowerHelmet` on the right (`-Y`) and equip both directly from the inventory menu.
   - Verify: equips directly on `HumanRace` with **no** `FURN` frame and **no** climb-in, provides heavy ballistic DR (`240` body / `80` helmet), applies `-1` `Agility` while worn (restored when unequipped), keeps `FO4SF_PAInPowerArmor = 0`, and causes **zero** `FusionCore` drain while walking.

7. **Read Log Verdict & Delete Throwaway Save:**
   - Quit without overwriting any permanent save. Run:
     ```powershell
     & $py scripts/powerarmor/make_power_armor_core.py log
     ```
     Confirm `PASS: climb-in, FusionCore drain, save/reload, exit outfit restore, and salvaged NCR worn ARMO all verified` with zero `Papyrus.0.log` errors.
   - Delete the throwaway save file **`FO4SF_Throwaway_PowerArmor_DeleteMe`** from the Starfield `Saves` folder (or in-game Load menu) and run `power_armor_core_install.py uninstall` when finished.
