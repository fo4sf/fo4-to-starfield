# Economy, vendors and barter (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved. "xEdit" = TES5Edit dev-4.1.6 `wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas`.

Related: faction records and crime in [factions-crime-relationships.md](factions-crime-relationships.md) (FACT
layout incl. vendor subrecords), items and values in [items-crafting-modding.md](items-crafting-modding.md), the
barter menu in [ui-pipboy-hud-menus.md](ui-pipboy-hud-menus.md), settlement vendor income in
[workshop-and-settlements.md](workshop-and-settlements.md). This file covers currency, vendor setup, prices,
restock and pickpocketing.

## In short
- Both engines use **one MISC item as currency at FormID 0000000F**: FO4 `Caps001` (Bottlecap, value 1, weight 0),
  Starfield Credits (**verified** as documented: fallout.wiki for Caps001, Shacknews console list for Credits).
- Vendors are set up the same way in both: a vendor FACT with `VEND` buy/sell FLST, `VENC` merchant container REFR,
  `VENV` hours/radius/stolen flags, `PLVD` location and conditions (**verified**, xEdit both files). Only the radius
  type changed (u16 to float).
- Prices: base value times a Charisma-driven factor (FO4 GMSTs `fBarterMax`/`fBarterMin`) times perk entry points
  "Mod Buy Prices" / "Mod Sell Prices" (**verified** entry points; formula and GMST values **supported hypothesis**).
- Verdict: vendor data **carries** (translate); currency is a **decision** (reuse Starfield's 0000000F renamed, or
  our own Caps MISC with a script shim); price rules **carry** if Starfield uses the same GMST names (unresolved);
  Starfield's credits economy (ship sales, contraband, outposts) is **fenced out**.

## How Fallout 4 does it

### Currency
- `Caps001` MISC 0000000F, value 1, weight 0 (**verified** as documented, fallout.wiki Bottlecap (Fallout 4)).
  Papyrus `Game.GetCaps` / `GivePlayerCaps` (**verified** names, falloutck via [papyrus-and-script-extenders.md](papyrus-and-script-extenders.md)).
  Condition `GetGold` 48 counts the currency (**verified** index, ctda_FO4; that it counts caps is **supported**).
- Misc stats "Caps Found", "Most Caps Carried" (**verified**, xEdit 5006, 5056).
- Quest rewards are paid by script (`AddItem` of caps) (**supported hypothesis**); FO4 QUST has no reward subrecord
  ([quests.md](quests.md)).

### Vendors
| Piece | Detail | Label |
|---|---|---|
| Vendor faction | FACT DATA flag 0x4000 "Vendor"; `VEND` buy/sell FLST (keywords); `VENC` merchant container REFR; `VENV` Start Hour, End Hour (default 24), Radius u16, Buys Stolen Items (default true), "Buy/Sell Everything Not In List?", Buys NonStolen Items (default true); `PLVD` vendor location; `CITC` + conditions | verified (xEdit 6800-6845) |
| Stolen goods | FACT `STOL` stolen goods container, `PLCN` player inventory container (jail) | verified (xEdit) |
| Measured | of the first 300 FACT in Fallout4.esm: 300 carry `VENV`, 26 `VEND`, 27 `VENC`, 27 `PLVD` | verified (docs/measurements/fo4_esm.json subrecord sample) |
| Vendor stock | the merchant container (often in a hidden cell) holds leveled lists including the vendor's caps; respawn on a timer | supported hypothesis |
| Dialogue | INFO subtype `BarterExit` (79); a "Help Barter" topic `HBBR` | verified (xEdit 6423, 8438) |
| Settlement stores | workshop vendor objects owned by a settler; income from the workshop script ([workshop-and-settlements.md](workshop-and-settlements.md)) | verified as documented there |

### Prices (community-derived, **supported hypothesis**: Nexus article 5093, not read from the game's GMSTs)
| Item | Value |
|---|---|
| Base price factor | `fBarterMax - (fBarterMax - fBarterMin) * (Charisma / 10)` = 3.5 - 0.15 x CHA in vanilla |
| GMSTs | `fBarterMax` 3.5, `fBarterMin` 2.0, `fBarterBuyMax` 1.20 and `fBarterSellMax` 0.80 (caps reached at CHA 16+) |
| Buy price | base value x "Mod Buy Prices" multipliers x factor |
| Sell price | base value x "Mod Sell Prices" multipliers / factor |
| Perk effects | Cap Collector 1: buy x0.90 sell x1.10; rank 2: x0.80 / x1.20 (stack); rank 3: +500 vendor caps; Barter bobblehead x0.95 / x1.05; Speech bobblehead +100 vendor caps |
| Entry points | PERK entry points 8 "Mod Buy Prices", 60 "Mod Sell Prices", 129 "Invest In Vendor" (**verified**, xEdit 3441, 3493, 3562) |

### Restock
Vendor stock and caps reset after some in-game days; the interval and the GMST that holds it are **unresolved**
(no primary source found; Skyrim-era lore says 48 hours, not checked for FO4).

### Pickpocketing
- PERK entry points 56 "Mod Pickpocket Chance", 61 "Set Pickpocket Equipped Item" (**verified**, xEdit 3489-3494).
- RACE flag "Allow Pickpocket" (**verified**, xEdit 11106). Crime value `CRVA` Pickpocket (u16) and FACT flag "Ignore
  Crimes: Pickpocket" (**verified**). INFO subtypes `PickpocketCombat`, `PickpocketNC`, `PickpocketTopic` (**verified**).
- Condition `WouldBeStealing` 79, `GetAmountSoldStolen` 190 (**verified**, ctda_FO4). Actor values "Bypass Vendor
  Stolen Check" (93) and "Bypass Vendor Keyword Check" (94) exist in the AV enum (**verified**, xEdit 4747-4748; use
  in FO4 **unresolved**, possibly Skyrim leftovers).
- Success chance formula: **unresolved**.

## How Starfield does it
- **Currency:** Credits, MISC 0000000F (**verified** as documented, Shacknews). Papyrus adds `Game.GetCredits` and
  keeps `GetCaps` / `GivePlayerCaps` (**verified** names, Starfield wiki, papyrus note). QUST stage reward data
  carries `QRCR` "Currency" (a GLOB amount) next to `QRXP` XP and `QRRD` items (**verified**, wbDefinitionsSF1.pas
  16420-16435).
- **Vendors:** same FACT `VEND` / `VENC` / `VENV` / `PLVD` + conditions; `VENV` Radius is now a float; xEdit labels
  the flags "Fence" (buys stolen) and "Specialized Inventory" (**verified**, wbDefinitionsSF1.pas 11923-11940).
  No `STOL` stolen goods container; instead a `PRIS` prisons array with contraband containers and ship landing marker;
  CRVA adds Piracy and Smuggle Multiplier (**verified**, xEdit 11895-11920). Sample: of the first 300 FACT, 300 have
  `VENV`, 41 `VEND`, 36 `VENC`, 18 `PLVD` (**verified**, docs/measurements/sf_esm.json).
- **Prices:** the same PERK entry points 8 "Mod Buy Prices", 60 "Mod Sell Prices", 129 "Invest In Vendor" keep their
  numbers (**verified**, wbDefinitionsSF1.pas 2592, 2644, 2713). Whether Starfield still reads `fBarterMax` /
  `fBarterMin` is **unresolved** (Starfield has 2,312 GMST vs FO4 2,037, **verified** counts; names not dumped).
- **Restock:** vendor credits refresh every 24 in-game hours, inventory every 48 (**supported hypothesis**, GGRecon
  guide; a Nexus mod page also cites 48 hours).
- **Pickpocket:** entry points 56 "Mod Pickpocket Chance", 61 "Can Pickpocket Equipped Item", 207 "Allow Pickpocket"
  (**verified**, xEdit). Perk activity types "Barter" (TrackCreditsEarned/Spent, ItemsBought/Sold) and "Player
  Pickpocket" feed skill challenges (**verified**, xEdit 4845-4861, 5243-5468).
- **Starfield-only economy:** ship buying and selling at Ship Services, contraband and smuggling, outpost resources
  and cargo links, the Trade Authority as a fence (**supported hypothesis** for the last; contraband and piracy fields
  **verified** above). None of it belongs in the port.

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| `Caps001` 0000000F | Credits 0000000F | decision (below) | same slot; FormIDs are remapped anyway |
| FACT VEND / VENC / VENV / PLVD | same subrecords | translate | radius u16 to float; flag names same meaning |
| FACT STOL (stolen goods) | none (PRIS prisons array) | translate | our own crime layer; see factions note |
| Merchant container REFR + leveled stock | same | data copy | caps in leveled lists become the chosen currency item |
| Barter GMSTs | same names? | data copy if present | dump Starfield GMST names first |
| Perk entry points 8 / 60 / 129 / 56 | same numbers | data copy | Cap Collector etc. carry |
| Speech/bobblehead vendor caps bonus | perk/AV | data + script | check how FO4 adds vendor caps |
| Quest caps rewards (script AddItem) | script, or QUST `QRCR` | translate | `QRCR` is a cheap option for new rewards |
| `GetCaps` / `GivePlayerCaps` | present in Starfield Game | shim if needed | they likely address 0000000F (unresolved) |
| Ship sales, contraband, smuggling | none in our world | fence out | never place Ship Services vendors |

### Currency decision (open, for the owner)
| Option | For | Against |
|---|---|---|
| A. Reuse Starfield's 0000000F, renamed "Caps" in our plugin, with the bottle cap model | Barter menu, HUD and `GetCredits` work natively | interface strings may still say "credits" (Scaleform/translation); touches a Starfield record |
| B. Own `FO4Caps` MISC as currency | clean ecosystem | the barter menu almost surely pays in 0000000F (supported hypothesis); needs script or SFSE to swap |
| C. Today's state: Starfield credits as is | zero work | not Fallout |
Recommendation: A, plus a check of which UI strings name the currency. B only if A's strings cannot be changed.

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Nothing structural: vendors, prices and perks are data. Script work: quest caps rewards (or `QRCR`), settlement
  vendor income, Nuka-World/Far Harbor vendor quests.
- SFSE: only for option B (a currency other than 0000000F in the barter menu) (**unresolved** whether even SFSE can).
- Fencing out: no Ship Services Technicians, Trade Authority or outpost economy in our world.

## Port status and links
- The port prices items in Starfield credits today: scripts/terrain/clusters/item_table.json says "Values are
  credits"; loose `Caps*` items become a MISC "Bottlecaps" (value 1, weight 0); the R05 first-aid kit container shows
  "Credits 25" in tests/test_activate_step.py; the mission harness logs `reward credits=100`
  (scripts/mission/make_mission.py) (**verified**, repo). So option C is the current state.
- Plan notes: [../next-phase/npcs-ai-factions-dialogue-quests.md](../next-phase/npcs-ai-factions-dialogue-quests.md)
  (NPCs and factions; it does not cover vendors yet).

## Open questions and cheap checks
- Dump GMST editor ids from Starfield.esm and Fallout4.esm (existing walker); diff the `fBarter*` names and values.
- ContentResources.zip: read `Game.psc` around `GetCaps` / `GetCredits` (what item they count).
- Starfield `Interface` / translation strings: grep for "Credits" to size option A's string work.
- FO4 xEdit: one vendor FACT (a Diamond City trader) with its VENC container and stock lists; the vendor caps item.
- FO4 GMST search for a vendor respawn day count (`iDaysToRespawnVendor` is a Skyrim-era name, existence in FO4
  **unresolved**).

## Sources
- xEdit: https://github.com/TES5Edit/TES5Edit (local wbDefinitionsFO4.pas, wbDefinitionsSF1.pas, condition tables)
- https://fallout.wiki/wiki/Bottlecap_(Fallout_4) (Caps001, 0000000F)
- https://www.shacknews.com/article/136971/starfield-console-commands (Credits 0000000F)
- https://www.nexusmods.com/fallout4/articles/5093 (FO4 barter formula and GMST values, community)
- https://www.ggrecon.com/guides/starfield-vendor-credits/ ; https://www.nexusmods.com/starfield/mods/6329
- Project: docs/measurements/fo4_esm.json, sf_esm.json; scripts/terrain/clusters/item_table.json;
  scripts/mission/make_mission.py; tests/test_activate_step.py
