# Red Rocket garage button (playtest row 21)

Author: Grok, 2026-10-17. Status: **writer wire implemented offline**; garage animation needs a scratch reconvert with
`--door-anim-dll`. Nothing deployed; nothing run in game.

## FO4 pair (**verified**, Fallout4.esm depot_377163)

Red Rocket Ext (−17/18, 19). Commonwealth has exactly two `RedRGarageDoor` refs, both XAPR’d to a `RedR_ButtonBox`:

| | Button `056BBA` | Garage `056331` |
|---|---|---|
| flags | persistent `0x400` | temporary |
| base | ACTI `05815F` `RedR_ButtonBox` FULL “Button” | ACTI `056330` `RedRGarageDoor` (no FULL) |
| model | `RedR_ButtonBox.nif` Stage1 / Stage2 | `RedRGarageDoor.nif` Closed / Opening / Opened / Closing |
| VMAD | base `Default1StateActivator` (`Anim`=stage2); REFR none | base `Default2StateActivator` (`isOpen`=true); REFR none |
| wire | no XLKR | **XAPR → `056BBA` delay 0.1** |

The other pair is `0866C7` → `0866C0`. Fo4Export/band JSON omit XAPR, so the cluster looks unlinked. Mutagen 0.55
Starfield has no ActivateParents.

## What core64k already did

Both are promoted ACTI in original slots. TerrainOverlays wrote model+name only: no VMAD, no XLKR, no graph. The
garage NIF converted as a static (`collision: fo4-native`). The owner sees BUTTON / Activate and nothing moves.

Interior `convert_multipart_door` / PluginSpike ONAM are for FO4 **DOOR** records with an `Open` sequence. This garage
is an **ACTI** whose sequences are Opening/Opened, not `Open`, so that gate would not take it. Load-door
ACTI+`FO4SF_LoadDoor` is a different class (Codex/Claude).

## Starfield-native wire (**verified**)

`DefaultActivateLinkedRefOnActivate` (ContentResources; debug ACTI `002CBE61` VMAD is the script name only, no extra
properties). Paradiso elevator-switch `000C7311` uses the same script plus XLKR `LinkCustom02` `0005D5E7` → the linked
ref. Button Activate() → linked door Activate(). No new .pex (Codex owns Papyrus).

## This PR

- Clip alias: FO4 `Opening`/`Closing` → Starfield `Open`/`Close` (`door_rig.alias_clips`). Rest poses dropped. Pipeline
  treats `Opening` as an animated door sequence so `--door-anim-dll` can rig `RedRGarageDoor.nif`.
- `objects.json` `"garage_buttons"`: the two Commonwealth pairs, only when both ACTI are already promoted.
- TerrainOverlays: on those button REFR, vanilla `DefaultActivateLinkedRefOnActivate` + XLKR LinkCustom02 → garage
  REFR. **No new FormIDs.**

## Still needed (Claude scratch overlay)

Reconvert `RedRGarageDoor.nif` with `--door-anim-dll` so the garage ACTI (or a follow-up DOOR record) has
SimpleOpenClose01 + Open/Close clips. Until then Activate() on the garage is a no-op visually. Do not stamp a landing
overlay; do not write .pex.
