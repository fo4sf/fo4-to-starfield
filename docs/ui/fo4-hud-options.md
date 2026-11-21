# Fallout 4 HUD in Starfield: Architecture Options & Store Mapping

Owner decision note (design comparison only; nothing built in this step, zero game text).

## 1. Measured Structure of Fallout 4's `HUDMenu.swf`

Inspection of `HUDMenu.swf` (`127,856` bytes, ActionScript 3 `HUDMenu extends Shared.IMenu`) via `scripts/ui/swf_names.py` shows modular child widgets driven from a plain `BGSCodeObj:Object` (`onCodeObjCreate` / `onCodeObjDestruction`):
- **Left cluster (`LeftMeters`)**: Health bar + inline radiation red cap bar (`FO4SF_Rads` / `FO4SF_RadsCapPct`), Power Armor / hazard warning text (`PAWarningText`).
- **Bottom-center (`HUDCompassWidget`)**: Horizontal degree strip, quest target markers, nearby discovered/undiscovered map markers, hostile pips.
- **Right cluster (`RightMeters_mc` / `ActionPointMeter`)**: Action Points bar, equipped clip / reserve ammo counter, throwable/grenade count, critical meter.
- **Contextual widgets**: `HUDConditionBoyWidget` (crippled-limb Vault-Boy flash), `HUDActiveEffectsWidget` (active aid/rad/survival icons), `HUDObjectiveUpdates` (quest stage banners), `EnemyHealthOptionalBar`, `Messages` (top-left toast feed), and `QuickContainerWidget` (quick-loot).

## 2. Three HUD Options for the Owner

### Option A — Replace Starfield's `hudmenu.gfx` Directly
- **How it works:** Stage a replacement `Data/Interface/hudmenu.gfx` matching Starfield's internal HUD widget paths.
- **Pros:** Single HUD movie in memory; Starfield's native C++ HUD controller drives crosshair and interaction prompts directly.
- **Cons:** Tightly coupled to Starfield's internal `HUDDataModel` AS3 class layout (breaks on game updates, collides with any HUD mod, and still draws Starfield's O2/CO2 watch dial unless stripped inside the binary movie).

### Option B — Separate Fallout 4 HUD Overlay Menu (Recommended Default)
- **How it works:** Register a lightweight, non-pausing, cursorless SFSE `IMenu` (`FO4SF_HudMenu`, `IMenu` flags keeping gameplay input active, hidden automatically whenever `fo4sf::FindOpenBlockingMenu` or `FO4SF_PipboyMenu` is open) hosting staged widgets from Fallout 4's `HUDMenu.swf`, while suppressing overlapping Starfield HUD meters (`Game.SetCharGenHUDMode` / targeted HUD visibility flags for the Starfield watch/O2/CO2 dial and health/ammo bars, keeping Starfield's crosshair and `E` interaction prompt).
- **Pros:** Reuses the exact `FO4SFPipboyMenu` vtable + plain-`Object` `BGSCodeObj` + throttled main-thread snapshot architecture; reads directly from `FO4SFCoreValues.esm` with zero coupling to Starfield's `hudmenu.gfx` internals; cleanly hides Starfield's O2/CO2 watch dial without losing interaction prompts.
- **Cons:** Requires hiding the redundant Starfield HUD sub-widgets so two health bars never appear simultaneously.

### Option C — Restyle Starfield's Native HUD Only
- **Pros:** Lowest maintenance cost; native crosshair, quick-loot, and objective banners work untouched.
- **Cons:** Cannot display Fallout 4's red inline radiation cap bar on the HP meter, horizontal Fallout compass, or Vault-Boy limb-cripple widget, and leaves Starfield's round planetary watch (`O2/CO2`, gravity/temperature) on screen.

## 3. Shared Store Mapping & Log Verification Contract

Every HUD element reads from the single shared `FO4SFCoreValues.esm` store (or vanilla `Starfield.esm` AVIFs), never a private duplicate:

| HUD Element | Source Plugin & Record / FormID | C++ / Papyrus Reader | Planned Verification Log Line |
|---|---|---|---|
| **HP Bar** | `Starfield.esm` AVIF `Health` (`0x000002D4`) | `ActorValueOwner::GetActorValue` + formula/rad cap | `step=hud_sync hp=<cur>/<max>` |
| **Radiation Bar (Red Cap)** | `FO4SFCoreValues.esm` AVIF `FO4SF_Rads` (`0x800`), GLOB `FO4SF_RadsDisplayPct` (`0x802`) | `GetActorValue` / `TESGlobal +0x48` | `step=hud_sync ... rads=<val> rad_pct=<pct>` |
| **AP Bar** | `Starfield.esm` AVIF `Oxygen` (`0x000002E2`) + `FO4SF_Special_Agility` (`0x815`) | `ActorValueOwner::GetActorValue` | `step=hud_sync ... ap=<cur>/<max>` |
| **Starfield O2/CO2 Watch Suppression** | `Starfield.esm` HUD watch widget | Hidden when `FO4SF_HudMenu` active (`Oxygen` repurposed as AP) | `step=hud_watch_suppressed state=1` |
| **Limb Condition / Condition Boy** | `Starfield.esm` AVIFs `0x0000036C..0x00000371` (`FO4SFCombat`) | `GetActorValue` (`0..100`, crippled `<= 0.5`) | `step=hud_limbs crippled_mask=<hex>` |
| **Compass Heading & Markers** | Player yaw (`+0x88`) + `FO4SFPipboyMapMarkers.tsv` / `FO4SF_MapDisc00..13` (`0x810..0x823` in `FO4SFPipboyTravel.esm`) | Shared with `PipboyMap` snapshot | `step=hud_compass deg=<deg> nearby=<n>` |
| **Ammo & Grenade Counter** | Equipped `TESObjectWEAP` clip/ammo + `BGSInventoryList` stack count (`FO4SFCombat` subtype) | Main-thread inventory & equipped weapon read | `step=hud_ammo clip=<c> reserve=<r>` |
| **Survival / Active Effects Icons** | `FO4SFCoreValues.esm` `FO4SF_HardcoreEnabled` (`0x820`), `FO4SF_HungerStage`..`SleepStage` (`0x821..0x823`), `FO4SF_RadResist` (`0x804`) | `TESGlobal +0x48` / `GetActorValue` | `step=hud_effects count=<n> hardcore=<0\|1>` |
| **Power Armor HUD Mode & Charge** | `FO4SFPowerArmor.esm` `FO4SF_InPowerArmor` (`0x801`), `FO4SF_FusionCoreCharge` (`0x802`) | Main-thread `TESGlobal` / AVIF read | `step=hud_pa active=<0\|1> core=<pct>` |
| **Quest Objective Banners** | Native quest HUD (`SetObjectiveDisplayed` on `FO4SF_Min00` / `FO4SF_NewGame`; developer `Debug.Notification` gated on `FO4SF_TestModeEnabled` `0x860`) | Engine quest objective feed | `FO4SF_MISSION rt=<t> stage <s>` |
