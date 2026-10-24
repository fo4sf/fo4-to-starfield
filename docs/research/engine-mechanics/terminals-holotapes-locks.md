# Terminals, holotapes, books and locks (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved. "xEdit" = TES5Edit dev-4.1.6 `Core/wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas`.

## In short
- FO4 puts a terminal's whole menu inside TERM (body text, menu items, submenus = other TERMs, holotape slots).
  Starfield splits it: TERM is the furniture and points (`DNAM`) to a TMLM "Terminal Menu" that holds body text and
  items; submenus are other TMLMs (**verified**, xEdit). Verdict: **translate** each FO4 TERM into TERM + TMLM tree.
- FO4 holotapes are NOTE records (Sound / Voice / Program / Terminal); NOTE is absent from Starfield.esm (**verified**,
  measurements). Starfield's nearest thing is a BOOK "data slate" with type Text / Image / Audio and a `GNAM` scene
  (**verified**, xEdit). Verdict: **translate** voice/sound holotapes to audio slates; terminal holotapes to TMLM;
  program holotapes (SWF games) **rebuild or drop**.
- Lock data (REFR `XLOC`: level, key, flags) has the same layout and level enum in both games (Novice 1/25, Advanced 50,
  Expert 75, Master 100, Requires Terminal 253, Barred 251, Chained 252, Inaccessible 254, Requires Key 255)
  (**verified**, xEdit). Verdict: **data copy**; the minigame changes (bobby pins to digipicks).
- Hacking: FO4's word-guess minigame is gated by the Hacker perk; Starfield has no terminal hacking minigame in normal
  play that this research found, but TMLM menu items carry their own `XLOC` (**verified** field, xEdit), and the
  hacking perk entry points survive in the list (**verified**). How a locked TMLM item is opened is **unresolved**.

## How Fallout 4 does it
### TERM (778 in Fallout4.esm, docs/measurements/fo4_esm.json) (**verified**, xEdit)
| Subrecord | Meaning |
|---|---|
| `VMAD` | script data with PERK-style fragments (menu item fragments run on selection) |
| `NAM0` / `WNAM` | header text / welcome text |
| `FULL`, `MODL`, `KWDA`, `PRPS`, `SNAM` | name, model, keywords, properties, looping sound |
| `FNAM` | flags incl. "Is a Radio", "Ignored by Sandbox" |
| `COCT` + `CNTO` | holotapes the terminal holds (NOTE, count) |
| `MNAM`, `XMRK`, `SNAM` marker params | furniture markers (the user sits/stands at it) |
| `BSIZ` + `BTXT` + `CTDA` | body text entries, each with conditions |
| `ISIZ` + menu items | `ITXT` item text, `RNAM` response, `ANAM` type (4 Submenu-Terminal, 5 Return to Top, 6 Force Redraw, 8 Display Text, 16 Display Image), `ITID` id, `UNAM` display text, `VNAM` image, `TNAM` submenu TERM, conditions |

- Hacking: a terminal REFR with `XLOC` gets the hacking minigame; the Hacker perk ranks open Advanced / Expert / Master
  terminals and rank 4 removes lockout (**supported hypothesis** for the XLOC route; perk ranks from
  https://fallout-archive.fandom.com/wiki/Hacker). Perk entry points `Mod Auto Hacking Chance` (92), `Set Player Gate
  Hacking` (98), `Mod Hacking Guesses` (126), `Mod Terminal Lockout Time` (127) (**verified**, xEdit).
- Doors and safes locked with level 253 "Requires Terminal" are opened by a terminal menu fragment (**supported
  hypothesis**: enum verified, the fragment pattern not dumped; Preston's door in B4 uses `Unlock`/`SetOpen`,
  docs/spikes/B4-mission-anatomy.md:71).
- `NTRM` "Native Terminal" on other forms points at a TERM (**verified**, xEdit; which records use it **unresolved**).

### NOTE holotapes (167, FO4-only) (**verified**, xEdit)
- `DNAM` type: Sound, Voice, Program, Terminal; `SNAM` union: SNDR (sound), SCEN (voice: a scene plays the recording),
  TERM (a terminal shown on the Pip-Boy); `PNAM` program file (the Pip-Boy games such as Atomic Command, Red Menace;
  **supported hypothesis** for the names); `DATA` value + weight.
- Terminals can play/eject holotapes; the Pip-Boy has a load-holotape action (`APLH` "Action Pipboy Load Holotape"
  default object, **verified** xEdit).

### BOOK (327) and magazines (**verified**, xEdit)
- `DESC` text, `DATA` value + weight, `DNAM` flags (Advance Actor Value, Can't be Taken, Add Spell, Add Perk) with a
  "teaches" union (AVIF / SPEL / PERK), text offset, `INAM` inventory art. Magazines are BOOKs that add a perk
  (**supported hypothesis**: Add Perk flag verified, magazine records not dumped).

### Locks and lockpicking
- `XLOC` on REFRs (doors, containers, terminals) as above; `Leveled Lock` flag (**verified**, xEdit). Bobby pins are a
  MISC (BobbyPinBox 50 kg mass is a converted clutter item, docs/ai/research-log.md:350, not the pick itself).
- Perk entry points: Mod Lockpick Sweet Spot (59), Set Player Gate Lockpick (62), Set Lockpick Starting Arc (63), Set
  Lockpicks Unbreakable (65), Mod lockpicking crime chance (86), key reward chance (90), Mod Auto Lockpicking Chance
  (91) (**verified**, xEdit). The Locksmith perk gates Advanced/Expert/Master (**supported hypothesis**).

## How Starfield does it
### TERM (368) + TMLM (700) (**verified**, xEdit; counts from docs/measurements/sf_esm.json)
- TERM: `DNAM` Terminal Menu (TMLM), `NAM1` art theme (Constellation, Freestar Collective, Generic, NASA, Ryujin,
  Slayton, United Colonies, Crimson Fleet, House Varuun, ...), `RADR` radio receiver, furniture markers, `NTRM`; no body
  text, no menu items, no holotape list.
- TMLM: `VMAD` with TMLM fragments, `FULL`, `TMVT` Show Body Text (Folder / Document), `DNAM` button style (Can Be
  Desktop, Use Long Kiosk Entry), `SNAM` style (Windows / Kiosk), body text items (`BTXT`, conditions, `TPLT` templated
  text), menu items (`ITXT`, `ISTX` short text, `ISET` type: Display Text, Submenu-TerminalMenu, Return to Desktop,
  Return to Previous, Force Redraw, DataSlate-BOOK; flags Template Item, Starts Open, Override Item Text, Creates New
  Window; `ITID`; **`XLOC` lock data per item**; `UNAM` text / `TNAM` submenu TMLM / `BNAM` BOOK; conditions).
- Quest aliases can carry `ALTM` "Alias Terminals" (TMLM) (**verified**, xEdit): menus can be injected per quest alias.
- Locks: same XLOC; Security skill ranks gate Advanced / Expert / Master and add banked auto-attempts; digipicks are
  spent to enter and reset the minigame (**verified** as documented, https://starfieldwiki.net/wiki/Starfield:Security_(Tech_Skill)).
  The digipick item is `Starfield.esm:00000A` (**verified** use, scripts/terrain/clusters/container_table.json).
- Lockpick perk entry points 59-91 kept, plus a `BGSLockPickActivity` challenge activity (**verified**, xEdit).
- BOOK (992): adds `DNAM` "Data Slate Type" (None, Text, Image, Audio), data slate headers `ENAM`/`FNAM`, and `GNAM`
  Scene (**verified**, xEdit). An audio slate plus a scene is the holotape-voice equivalent (**supported hypothesis**).
- Gone: NOTE (xEdit still defines it, Starfield.esm has 0), the FO4 TERM menu layout, Pip-Boy holotape programs.

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| TERM (furniture, model, markers) | TERM | translate | written today with Name, Model, Menu, Background = Default |
| TERM body text + `WNAM`/`NAM0` | TMLM body text | translate | conditions carry if the condition functions exist |
| TERM menu item (display text) | TMLM item type Display Text | translate | |
| menu item submenu (TERM) | TMLM submenu (TMLM) | translate | one TMLM per FO4 TERM used as submenu |
| menu item Display Image (`VNAM`) | none found | rebuild | image items **unresolved**; maybe an image data slate |
| TERM VMAD fragments | TMLM VMAD fragments | rebuild | own Papyrus (unlock door, toggle turret); fragment format differs |
| NOTE Voice (scene) | BOOK audio slate + `GNAM` scene | translate | voice files: see voice note |
| NOTE Sound | BOOK audio slate | translate | **unresolved** whether a slate can play a plain sound without a scene |
| NOTE Terminal | BOOK text slate or TMLM | translate | |
| NOTE Program (SWF games) | none | drop or SFSE/UI rebuild | optional extra |
| BOOK (notes, magazines) | BOOK | data copy + translate | magazines need our own perks |
| REFR `XLOC` | REFR `XLOC` | data copy | key KEYM must be built; Mutagen field check pending (next-phase P3) |
| Hacking minigame | none confirmed | rebuild or map | options: treat terminal lock as a digipick lock; or SFSE/UI minigame later |
| Bobby pins (MISC) | digipick | map | one decision: reuse Digipick 00000A or our own pick item |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- TERM to TMLM converter: body text, items and submenu tree, conditions, our own fragment scripts.
- Hacking: no native counterpart found. Cheapest: put FO4's hack level on the terminal REFR `XLOC` (or TMLM item XLOC)
  and let the digipick game stand in; a real word-guess game needs UI work (SFSE / Scaleform) and is polish.
- Holotape player: audio slates cover voice and sound tapes; FO4 Pip-Boy games need a UI layer (SFSE) or stay out.
- The CK helps to inspect vanilla TMLM fragments and slates; not needed for writing the data.

## Port status and links
- 140 terminals promoted to 91 TERM + 91 TMLM bases, each TMLM with one body line "FO4 terminal (text not ported yet)"
  and no items, layout copied from vanilla `RI04_NyxProgram_Menu_Camden` 0788A8 (**verified** offline,
  docs/terrain/commonwealth-build-plan.md:93-97, docs/terrain/stations.md:107). Reading one in game is **unresolved**
  (docs/terrain/port-promotions.md:46).
- Door locks are read by the export but not written (docs/spikes/door-behaviour.md:20;
  ../next-phase/doors-activators-workshops.md 2.1 and P3).
- Voice/slates: ../next-phase/voice-lipsync-companions.md. UI: ../next-phase/animations-ui-and-start.md.

## Open questions and cheap checks
- Dump vanilla TMLM items with a non-empty `XLOC` (how many, which levels) and their fragment scripts: answers how
  Starfield locks terminal entries.
- Grep ContentResources.zip for `Hack`, `Lockout` and TMLM fragment scripts that call `Unlock`.
- Dump 5 vanilla audio slates (BOOK type 3): does each use `GNAM` scene or a sound?
- Fo4Export: count FO4 TERM by feature (submenus, images, holotape slots, VMAD) to size the converter.
- Count FO4 terminal REFRs with `XLOC` and their levels.

## Sources
- xEdit definitions: https://github.com/TES5Edit/TES5Edit (Core/wbDefinitionsFO4.pas, Core/wbDefinitionsSF1.pas)
- https://starfieldwiki.net/wiki/Starfield:Security_(Tech_Skill)
- https://fallout-archive.fandom.com/wiki/Hacker
- https://www.shacknews.com/article/136876/lockpicking-starfield
- Repo: docs/measurements/*.json; docs/terrain/commonwealth-build-plan.md; docs/terrain/stations.md;
  docs/terrain/port-promotions.md; docs/spikes/door-behaviour.md; scripts/terrain/clusters/container_table.json
