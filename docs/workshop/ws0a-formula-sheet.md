# Fallout 4 Workshop Formula Sheet (WS0a Reference)

- **Authoritative source inspected (`VERIFIED`):** Fallout 4 `Scripts\Source\Base\Base.zip` (`7,857` archive entries / `7,854` total `.psc` files, `7,822` non-CreationClub `.psc` scripts; clean-room formula summary — no Bethesda `.psc` source copied).

---

## 1. Settlement Attack Chance (`WorkshopScript.psc` — `VERIFIED`)

| Symbol / Constant | Verified FO4 Value | Role |
|---|---|---|
| `attackChanceBase` | `0.02` (`const`) | Base daily attack probability (`2%`) |
| `attackChanceResourceMult` | `0.001` (`const`) | Added per unit of `(FoodRating + WaterRating)` (`+0.1%` per point) |
| `attackChanceSafetyMult` | `0.01` (`const`) | Subtracted per point of `Safety` (`-1.0%` per point) |
| `attackChancePopulationMult` | `0.005` (`const`) | Subtracted per settler (`-0.5%` per settler) |
| `minDaysSinceLastAttack` | `7.0` (`const`) | Minimum in-game days between random attack rolls |
| `CheckForAttack(bool bForceAttack = false)` | Per-workbench method | Gated per workbench by `AllowAttacks` (global/quest opt-out, e.g. Castle) and `AllowAttacksBeforeOwned` |

**Daily attack probability formula** (when `daysSinceLastAttack >= 7.0` and `AllowAttacks == true`):
$$\text{chance} = 0.02 + 0.001 \times (\text{Food} + \text{Water}) - 0.01 \times \text{Safety} - 0.005 \times \text{Population}$$
Clamped by floor `0.02` (`minAttackChance`) in daily resolution when resources exceed safety/defense. *(Owner's Rule 12 open question: final Starfield-layer attack cadence waits on owner confirmation.)*

---

## 2. Core Resource, Happiness, and Production Design Equations

1. **Beds (`WorkshopRatingBeds`):** `1` covered/sheltered bed per settler required; shortfall adds happiness penalty (`-10` cap factor), covered bonus satisfies baseline safety/shelter check in `Min01` (`5` beds target in Sanctuary milestone `1000/1050`).
2. **Water (`WorkshopRatingWater`):** `1` water per settler (`Min01` target `5` clean water at stage `1200/1250`). Surplus stored into workshop container up to `5 + floor(Population / 4)` cap per cycle.
3. **Food (`WorkshopRatingFood`):** `1` food per settler (`Min01` target `5` food at stage `1300/1350`); each assigned farmer tends up to `6` food worth of crops.
4. **Defense / Safety (`WorkshopRatingSafety`):** Recommended minimum target $\text{Safety} \ge \text{Food} + \text{Water}$ to offset the `+0.001*(Food+Water)` attack pressure (`Min01` target `2` defense at stage `1400/1450`).
5. **Power (`WorkshopRatingPower`):** Objects requiring power must lie within powered state / grid supply (`WorkshopPowerConnectionKeyword`); P4 probe tests whether wireless radius (`AV 0x32F`) or wired splines (`BNDS 0x1D1D6A`/`0x3162C7`) govern Starfield outpost powered lights (`Owner Q: power wires confirmed`).
6. **Scrap conversion:** `CMPO` (`31` components in `Fallout4.esm`) -> mapped `IRES` / `MISC` yields in `WorkshopCore` (`18` locked archetypes in `core_log.py:38-57`) alongside `157` `COBJ` scrap recipes (`FNAM 00106D8F`) and `620` `CVPA`-tagged junk items.
