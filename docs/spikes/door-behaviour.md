# Doors: how Fallout 4 sets each one up, and what the port keeps (spike, 2026-10-18)

Owner's ask (2026-10-18): "review how fallout 4 treats doors and give them their activation notice as if they should be
accessible or not, how they work, their activation, triggers, and all of that". Reports behind it: the Red Rocket side
door swings instead of sliding, Fort Hagen's elevator entry does not work from outside and its doors do not show
properly, the Museum of Witchcraft roof hatch is not a door from inside, and some doors that should not be usable are.

Status: **plan and tooling**; the per-door facts need the PC's export (step 1 below). Nothing here is verified in game.

## What decides a door's behaviour in Fallout 4

Where each fact lives in the plugin. The field names are those of Mutagen 0.55 (the library the exporter uses); the
byte layout was not checked here, so the list is a **supported hypothesis** until the export shows it on real records.

| Behaviour | FO4 record | Our export (dotnet/Fo4Export) | Our plugin today |
|---|---|---|---|
| Teleports (load door) | REFR XTEL: destination door, arrival point | `teleport_destination` | Interiors: XTEL when both ends are built (TeleportLinks.cs); exterior to interior: FO4SF_LoadDoor VMAD (vmad_patch.py) |
| Is a load door at all | the base is a DOOR and the reference has an XTEL | `type` + `teleport_destination` | Until 2026-10-18 by file name only (LOAD_DOOR_RE "door...load"); now also by record (see below) |
| How it opens | the NIF's Open / Close sequences | the model | hinged template, own rig (sliding, multi-part), or passable |
| Locked, needs a key | REFR XLOC: level, key, flags | `lock_data` | **not written** (PluginSpike counts them only) |
| Open at start | REFR "open by default" | `open_by_default` | written |
| Hidden until a quest enables it | REFR initially disabled, enable parent XESP | `disabled`, `enable_parent` | disabled kept; **enable parent not written**, so such a door never appears or always appears |
| Opened by something else (button, terminal, lever) | REFR activate parents XAPD, linked refs | `activate_parents`, `linked_references` | not written for doors |
| Automatic, hidden, minimal use, sliding, no "to" text | DOOR FNAM flags | **new**: `door_bases[..].record.Flags` | not used |
| Name in the prompt ("Open Roof Hatch") | DOOR FULL | **new**: `door_bases[..].record.Name` | interior load doors: graph-less DOOR; exterior: ACTI with the FO4 FULL or "Door" |
| Open / close sounds | DOOR sound fields | **new**: in `door_bases[..].record` | none |
| Scripted (elevators, quest doors, default lock scripts) | VMAD on the DOOR or the REFR | **new**: `scripts` on refs, `door_bases[..].scripts` | none, except FO4SF_LoadDoor |

FO4 elevators (Fort Hagen) are, as far as we know, an elevator car with scripted doors and a panel that triggers the
move, not one load door; which records and scripts take part is **unresolved** until the export lists them.

## What changed on 2026-10-18

- Load doors by record: `convert_batch.py --cell-json` hands the converter every model FO4 places as a Door reference
  with an XTEL (`teleport_models`), and the converter makes those load doors whatever their name. RoofHatch01 and
  MetalTrapdoorLadder01 were STATs before (research log 2026-10-08 already noted it). Takes effect on the next port build.
  The outdoor core does the same (make_core64c `convert_list` marks a model placed as a teleporting Door): Fort Hagen's
  and Vault 95's elevator entrances fail from outside only, and the **supported hypothesis** is that their animated
  elevator models became passable (no collision, nothing to aim the prompt at) because the outdoor core is converted
  without the door library. door_audit.py on the installed build confirms or refutes it before a rebuild.
- Skinned door panels: a shape skinned wholly to one rig bone rides that bone (RedRPedDoor.nif's two shapes, PC check).
- `scripts/terrain/door_audit.py`: per scripted load door of a core build, what the exterior model became (rig,
  passable, error) and what the interior door's base is (DOOR, ACTI or STAT). A STAT, or a passable model with no
  collision to aim at, cannot be activated.
- `scripts/terrain/door_survey.py`: over exported cells, one row per Door reference with its FO4 set-up (above) and
  its build result, and a count per behaviour class.
- Exporter: `door_bases` (each placed Door base: its record and scripts) and `scripts` on every reference.

## Plan

1. PC, read-only: build Fo4Export, re-export the door cells (the 15 with scripted doors, FortHagen01, FortHagen02,
   MuseumOfWitchcraft01 first), run `door_survey.py` over them with the port and exterior manifests, and
   `door_audit.py` on the installed core and port. The rows answer Fort Hagen and the hatch per door.
2. Write what the survey shows matters most, each with a synthetic test: locks (XLOC level and key on the reference),
   enable parents (so quest-hidden doors stay hidden and come back when FO4 would show them), the FO4 name in the prompt,
   and doors FO4 makes unusable (no-activation or inaccessible set-ups the survey finds).
3. Elevators and scripted doors: map FO4's scripts to a small Starfield script set as FO4SF_LoadDoor does for teleports;
   design after step 1, since it depends on which scripts appear and how often.
