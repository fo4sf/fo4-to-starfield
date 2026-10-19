# VATS (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

## In short
- FO4: VATS is an engine mode: the world slows (not stops), the player queues shots on body parts at a hit chance,
  each costing Action Points; a critical meter fills and is spent on a chosen shot; a cinematic camera plays the
  queue. Data hooks: BPTD body-part "VATS Target" and "To Hit Chance", WEAP "Action Point Cost" and CRDT, PROJ "VATS
  Projectile", DEST "VATS Targetable", ~25 VATS perk entry points, and condition functions (GetVATSMode,
  GetVATSValue ...).
- Starfield has no player VATS mode, but much of the plumbing is still in the data format: the same VATS condition
  functions at the same indices, the VATS perk entry points (AP renamed Oxygen), BPTD "VATS Target", DEST "VATS
  Targetable", WEAP "Attack Action Point Cost", PROJ-side "VATS Projectile". **verified** (xEdit). Whether the engine
  code behind them still runs is **unresolved**.
- Starfield's ship "targeting" mode (lock on to ship subsystems) is a plausible VATS descendant: entry point 184 is
  "Mod Ship Targeting Fire AP Cost". **supported hypothesis**.
- Verdict: **rebuild**. Data hooks carry, the mode itself needs SFSE (time scale, target selection, hit chance, camera)
  plus a Scaleform menu. PLAN.md calls VATS a non-goal ("Starfield-native equivalents"); ROADMAP C2 reopens it.

## How Fallout 4 does it
| Piece | Where | Label |
|---|---|---|
| Body-part targets | BPTD body part: BPTN name, BPNN node, BPNT "VATS Target", BPND {Damage Mult, Part Type enum (Torso, Head1, Eye, LeftArm1 ... Brain, Weapon), Health Percent, Actor Value (limb condition AV), To Hit Chance, cripple and dismember data} | verified (xEdit) |
| AP cost | WEAP DNAM "Action Point Cost" (default 20.0); attack data "Action Points Mult" | verified (xEdit) |
| Criticals | WEAP CRDT {Crit Damage Mult (default 2.0), Crit Charge Bonus, Crit Effect SPEL}; WEAP flag "Crit Effect - on Death" | verified (xEdit) |
| Projectile | PROJ DATA "VATS Projectile" | verified (xEdit) |
| Destructibles | DEST flag "VATS Targetable" | verified (xEdit) |
| Conditions | GetVATSMode (224), GetVatsTargetHeight (235), GetVATSValue (407; function enum: Weapon Is, Target Part, VATS Action, Is Success, Is Critical, Is Fatal, Cripple Part, Is Stranger, Is Paralyzing Palm ...), GetVATS*AreaFree / *TargetVisible (515-525, 772, 806-810), GetVATSQueuedTargetsUnique (796) | verified (xEdit) |
| Perk entry points | 79 Mod VATS Attack Action Points, 105-123 (penetration, AP on kill, crit fill on hit, concentrated fire, crit count, hold em steady, gun-fu, reload AP, crit charge, head shot chance, hit chance), 135-153 (crit fill, shoot explosive, penetration full damage, gun-fu dmg, blitz), 155 Paralyzing Palm | verified (xEdit) |
| Game stat | "Critical Strikes" misc stat | verified (xEdit) |
| Time | world slows, player queue continues | supported hypothesis (GamesRadar, Todd Howard quote) |
| Camera | VATS cinematic kill cam | records/settings behind it unresolved (no CAMS/CPTH link checked) |
| GMSTs | VATS hit chance, time multiplier, camera settings live in GMSTs | names unresolved (none invented; see checks) |
| UI | VATS HUD is a Scaleform movie in Interface | supported hypothesis |

Behaviour notes: hit chance depends on distance, weapon accuracy, Perception, cover and target movement; FO4
criticals are banked, not random (GamesRadar). Many perks (Grim Reaper's Sprint, Gun Fu, Blitz, Concentrated Fire,
Critical Banker, Four Leaf Clover, Mister Sandman via conditions) only work through these hooks. **supported
hypothesis** for the perk-to-hook pairing beyond the entry point names.

## How Starfield does it
- No player VATS. Body-part damage exists (BPTD, 27 records; BPD2 data keeps Damage Mult, Part Type, Health Percent,
  Actor Value, To Hit Chance and cripple fields, drops dismember/explode). **verified** (xEdit; counts from sf_esm.json).
- Entry points 79, 105-153 keep their FO4 names with AP -> Oxygen; 155 Paralyzing Palm is now Mod Jumping Oxygen;
  136 Bloody Mess is now Mod Oxygen Use. **verified** (xEdit diff of the two enums).
- Condition functions GetVATSMode, GetVATSValue, GetVATS*AreaFree, GetVATSTargetLimbVisible exist at FO4's indices.
  **verified** (xEdit).
- WEAP has both "Attack Oxygen Cost" and "Attack Action Point Cost"; DEST keeps "VATS Targetable"; attack data keeps
  "Action Points Mult". **verified** (xEdit).
- Time slowing exists as a magic effect archetype: MGEF archetype 37 "Slow Time" is in both games' enums. **verified**
  (xEdit). A Starborn power ("Time Dilation") plausibly uses it. **supported hypothesis** (record not checked).
- Oxygen (O2) and CarbonDioxide (CO2) replace AP and Fatigue as the stamina pair. **supported hypothesis** from the
  entry point renames.

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| BPTD VATS Target / To Hit Chance | BPTD BPNT / BPD2 | data copy (subset) | dismember fields drop |
| WEAP Action Point Cost | WEAP Attack Action Point Cost | data copy | whether SF reads it is unresolved |
| WEAP CRDT | WEAP crit fields (WCCB/WCDM/WCRT OMOD props exist) | translate | |
| PROJ VATS Projectile | SF PROJ DATA "VATS Projectile" (offset 77) | data copy | |
| VATS entry points | same index | data copy | inert without a VATS mode |
| GetVATS* conditions | same function | data copy | always false without the mode (supported hypothesis) |
| ActionPoints AV | Oxygen AV or a new AV | translate / new AVIF | decision: reuse O2 as AP (sprint drains it too in both) or add our own AP |
| VATS mode, time slow, queue, camera | none | rebuild (SFSE) | |
| VATS HUD | none | rebuild (Scaleform) | |
| Critical meter | none | rebuild (AV + UI) | |

## What must be rebuilt, and what needs SFSE or the Creation Kit
Minimal VATS (in order, each provable alone):
1. **Time slow**: Papyrus has no global time scale call in FO4 vanilla that we checked; the console `sgtm` exists in
   older CE titles, and in Starfield a published mod binds `setglobaltimemultiplier 0.45` to console hotkeys (Nexus SF
   939), Slow Time SFSE (GPL-3) scales the global multiplier while keeping the player at normal speed, and vanilla ship
   targeting mode already runs at 0.65x (SF 8063) (verified as documented on the mod pages; our own test still open). A Slow Time MGEF archetype applied to the player is the no-SFSE path
   (verified the archetype exists; behaviour under player cast unresolved). An SFSE plugin setting the engine's time
   multiplier is the robust path.
2. **Target selection**: find actors in a cone, pick body parts from their BPTD nodes, compute hit chance. Papyrus can
   enumerate actors (FindAllReferencesWithKeyword-style calls; exact SF API unresolved); node world positions need SFSE
   or a native helper.
3. **UI**: Scaleform menu that draws the target list and percentages; opened via SFSE (same menu framework decision as
   the Pip-Boy, ../next-phase/animations-ui-and-start.md).
4. **Execution**: fire queued shots with forced aim (SFSE or scripted `Actor.StartCombat`-style workaround; unresolved),
   apply perk hooks through our own code since engine VATS entry points will not fire.
5. **Camera**: optional; a scripted camera path or none.
Community precedent: no Starfield VATS mod with body-part targeting was found in two later passes either (only
time-scale mods; **unresolved**, absence of evidence). FO4's VATS rewrites (VAFS, Bullet Time VATS VR, Fallout 76 VATS
for F4SE) all had to redesign the same group of VATS perks (Gun Fu, Concentrated Fire, Critical Banker, Penetrator),
because perk entry points tied to the engine mode stop firing; per-limb tracking in Papyrus was "too heavy on the
script engine" (verified, mod pages). Plan the VATS perk list together with the mode. Framework questions:
[../framework/engine-mechanics.md](../framework/engine-mechanics.md).

## Port status and links
- No VATS work in the repo. PLAN.md non-goal: "VATS, Pip-Boy, settlements get Starfield-native equivalents";
  ROADMAP.md C2 revisits this; docs/WORK-PACKAGES.md lists "replacements for VATS" under Papyrus shims.
- Related: [health-damage-effects.md](health-damage-effects.md) (limbs, BPTD), [special-perks-leveling.md](special-perks-leveling.md)
  (entry points), [../next-phase/animations-ui-and-start.md](../next-phase/animations-ui-and-start.md) (menus, SFSE).

## Open questions and cheap checks
- xEdit: Fallout4.esm GMSTs whose editor id contains "VATS" (names + values), same in Starfield.esm.
- xEdit: does any Starfield.esm PERK use entry points 79 or 105-153 (proves the engine still reads them)?
- xEdit: Starfield.esm AVIF editor ids `ActionPoints`, `Oxygen`, `CarbonDioxide` present?
- ContentResources.zip: grep `*.psc` for `VATS`, `SetTimeMultiplier`, `sgtm`-like natives.
- SFSE source (ianpatt/sfse): search for a time multiplier / `VATS` class in the RE headers.
- In game console: `sgtm 0.3` (if accepted, Starfield keeps the global time multiplier; read-only test, reverts with 1).
- Interface.ba2 (Starfield): any `vats*.swf` left in the 250 SWFs (verified count in the next-phase note).

## Sources
- xEdit definitions, TES5Edit dev-4.1.6: [wbDefinitionsFO4.pas](https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsFO4.pas),
  [wbDefinitionsSF1.pas](https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsSF1.pas) (BPTD, WEAP,
  PROJ, DEST, condition function table, wbVatsValueFunctionEnum, entry point enums, MGEF archetypes)
- [Fallout 4's VATS isn't a time-stopping panic button any more (GamesRadar)](https://gamesradar.com/fallout-4-vats-info)
- [Universal Timescale (Nexus SF 3891)](https://www.nexusmods.com/starfield/mods/3891) (only calendar time scale, not
  combat time: shows the search found no VATS precedent)
- Project: docs/PLAN.md, docs/ROADMAP.md, docs/WORK-PACKAGES.md, docs/measurements/*_esm.json
