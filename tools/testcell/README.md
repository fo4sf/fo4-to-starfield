# Object test room (FO4SFTestCell.esm)

One interior cell, `FO4SF_TestCell`, where converted objects stand alone on a flat, evenly lit floor next to vanilla
Starfield controls. It answers one question: does an object misbehave on its own (mesh, collision, material, physics),
or only where it sits in its home cell (placement, neighbours, the terrain or structure under it)?

- **Writer:** `dotnet/TestCell` (Mutagen, like `dotnet/MergeProbe`). It reads the installed `FO4Port.esm` to find the
  converted bases by editor ID, so it is built on the PC against the exact port that is installed, and rebuilt whenever
  the port is (the port's FormIDs are stable, but a rebuild can add or drop bases).
- **Layout:** `layout.json`, rows of items. Each item is a converted base by editor ID (`edid`), a vanilla
  `Starfield.esm` base by FormID (`vanilla`), or the distinct bases of one type the port places in a cell
  (`from_cell` + `type`, with an optional `max` that keeps the first ones in the port's FormID order, which is not FO4's
  placement order). Anything not found is listed as MISSING and its spot stays empty.
- **Placement:** spot `<row><n>` at x = (n - 1) * spacing, y = row index * spacing, z 0, unrotated, scale 1. `coc
  FO4SF_TestCell` arrives one spacing before A1, facing along row A; rows B, C, ... lie to the left. There are no labels in
  the room: `spots.md` (written next to the plugin) names every spot, so a screenshot can say "B4".
- **Vanilla parts** are the ones `dotnet/PluginSpike`'s door test cell (`FO4PORT_DOORTEST`) writes: platform tile 050776
  (8 x 8 m), omni light 03D38C, COC marker 000032, lighting template 006658, image space 122393. **Unresolved:** the
  tile's extent along y is not recorded, so the floor reaches one tile past the spots on every side.
- **Masters:** Starfield.esm, FO4Port.esm. It overrides nothing and only adds its own cell, so it loads after the port
  in any position.

## First stock (layout.json)

| Row | What | Why |
|---|---|---|
| A | The Akila door (vanilla), then every door base the port places in Vault95, MuseumOfWitchcraft01 and PrydwenHull01 | Job 6's three failed exit legs (research log, #383): is the door itself at fault, or its landing? |
| B | Four vanilla movable items, each next to the converted item the movable queue pairs it with | Walking contact versus applied impulse, without QASmoke's own clutter |
| C | The five stair models of the library stairs queue | Climb each flight on a flat floor, away from the helper and floor crossings of BostonPublicLibrary02 |

Limits: the room says nothing about load-door teleports or exterior landings (a door here leads nowhere), and the port's
per-base placement offset for posed or own-rig models is not applied, so such a model stands at its mesh origin.

## Build and check

```
dotnet run --project dotnet/TestCell -c Release -- build <Starfield Data>\FO4Port.esm tools/testcell/layout.json <out dir>
python -m unittest tests.test_test_cell
```

The build prints how many spots resolved and every MISSING one. Installing the plugin is a swap like any other.
