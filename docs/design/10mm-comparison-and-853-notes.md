# Vault 111 10mm Pistol Comparison & PR `#853` Notes

Updated for `2g-fix6` (`2026-11-25`).

## 1. Side-by-Side Comparison: Vault 111 Pistol vs Fallout 4 `0x00004822`

| Attribute | Pre-`2g-fix6` (`0x24561C` `XM2311`) | `2g-fix6` Local `WEAP` (`0x000822` `FO4SF_Vault111_10mm`) | Fallout 4 Reference (`0x00004822` `10mm`) |
|---|---|---|---|
| **EditorID / Plugin** | `Starfield.esm:0x24561C` (`XM2311`) | `FO4SFNewGame.esm:0x000822` (`FO4SF_Vault111_10mm`) | `Fallout4.esm:0x00004822` (`10mm`) |
| **Display Name** | `"XM2311"` | `"10mm Pistol"` | `"10mm Pistol"` |
| **Placed Vault Ref** | `0x820 -> Starfield.esm:0x24561C` | `0x820 -> FO4SFNewGame.esm:0x000822` | Vault 111 Overseer desk (`10mm`) |
| **Magazine Capacity** | `9` | `12` | `12` (`10mmMag01`) |
| **Base Damage** | Vanilla `XM2311` (`~19-20` + templates) | `18` (`AttackDamage = 18.0f`) | `18` |
| **Ammo Form** | `.45` Caliber (`Starfield.esm:0x2B5598`) | `.45` Caliber (`0x2B5598` interim until `10mmAmmo` lands) | `10mm` (`Fallout4.esm:0x0001F276`) |
| **Model / Receiver Mesh** | `BullpupDummyReceiver.nif` (`XM2311`) | Cloned `XM2311` chassis (keeps B5 pickup compatibility) | `10mmpistol_1.nif`, `10mmgrip_1.nif`, `10mmmag01_1.nif` |
| **Muzzle / FX / Sighting** | Starfield `XM2311` muzzle node & iron sights | Starfield `XM2311` muzzle node & iron sights | FO4 `ProjectileNode`, `10mm` barrel/iron sight |
| **Rate of Fire & Reload** | Semi-auto `XM2311` speed/reload anim | Starfield `XM2311` ROF & reload anims | Semi-auto `46` ROF, `~2.1s` empty reload |
| **Audio** | Starfield `XM2311` shot/reload WEMs | Starfield `XM2311` shot/reload WEMs | FO4 `10mm` shot/reload Wwise cues |

> [!NOTE]
> `FO4SF_NewGameQuest.VaultPistolBase` remains bound to `Starfield.esm:0x24561C` to satisfy cross-plugin check `B5` with `FO4SFRouteLoot.esm`, while `EnsureVaultInteractivesRegistered()` adds an inventory event filter for both `VaultPistolBase` and `FO4SFNewGame.esm:0x000822` so picking up `0x820` (`FO4SF_Vault111_10mm`) logs `pistol picked` and auto-equips cleanly.

## 2. Notes on `#853` (`b8c359c2` / `scripts/weapons/stage_r11_10mm.py`)
- **What `#853` provides:** Welds 8 rigid Fallout 4 weapon shapes from `10mmpistol_1.nif`, `10mmgrip_1.nif`, and `10mmmag01_1.nif` onto Starfield's `XM2311` base weapon architecture (`fo4_10mmpistol.nif`) paired with a `10mmAmmo` record (`0x0001F276` stand-in).
- **Status & next step:** Held on `#853` pending P1 re-verification and live-game first-person muzzle/reload alignment check by Claude. Once `#853` lands in `main`, point `FO4SF_Vault111_10mm` (`0x822`) and `Vault111AmmoRef` (`0x821`) at `#853`'s `fo4_10mmpistol.nif` and `10mmAmmo` records instead of `XM2311` `.45`.
