# Red Rocket garage button (playtest row 21)

Author: Grok, 2026-10-17. Status: **writer wire implemented offline** (wire-only). Garage animation/receiver is later
Claude work; this PR does not change the converter or clip names. Nothing deployed; nothing run in game.

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

## This PR (wire only)

- `objects.json` `"garage_buttons"`: the two Commonwealth pairs, only when both ACTI are already promoted.
- TerrainOverlays: on those button REFR, vanilla `DefaultActivateLinkedRefOnActivate` with edited `LinkedRefKeyword` =
  LinkCustom02, and XLKR LinkCustom02 → garage REFR. Script and link use the same keyword (`GetLinkedRef(LinkedRefKeyword)`).
  **No new FormIDs.** Pair matching is `(plugin, form id)`, not the hex spelling.
- No clip alias and no `pipeline.py` `Opening` gate: that path turns both FO4 garage meshes into passable statics
  because `RedRGarageDoor.nif` is skinned and the rigger refuses it.

## Still needed (Claude, later)

Garage receiver: a DOOR record or a scripted ACTI, plus a NIF that can actually rig. The promoted garage is an inert
ACTI, so a correct button wire still activates an object with no open/close graph. Do not stamp a landing overlay;
do not write .pex. Do not treat Opening/Closing as `Open`/`Close` in the converter until skinned rigging exists.
