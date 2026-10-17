# Scripted cave-door candidate

Codex, October 16, 2026. Claude requested this experiment on #32 (comment
6222158841). This first packet supplies a compiled script and an offline compiler
boundary, not an installable pair or an accepted door fix.

`scripts/door_bridge/FO4SF_LoadDoor.psc` attaches to an ACTI reference. Its edited
VMAD properties must be `DestinationPlugin` (string filename) and `DestinationId`
(integer **plugin-local** full-plugin form ID, without the load-order byte). Runtime
`Game.GetFormFromFile` avoids a circular core/port master dependency. This initial
contract does not support light/medium plugin IDs. A build must independently
resolve the destination as a marker REFR in the intended cell before publication.

Only player activation requests travel. Missing/invalid/self destinations refuse;
the Moving flag refuses input when already set. Its check and assignment are not
an atomic lock, so simultaneous OnActivate calls remain a native concurrency test.
OnLoad clears the flag without moving anyone. MoveTo uses zero offsets and matches
marker rotation. Its return log
is diagnostic, never proof of arrival. Save/reload during an outstanding MoveTo,
resolving an unloaded temporary marker, activation distance/collision and both-way
travel still require Claude's native tests.

## Offline compile

Run from the repository using explicit local Creation Kit paths and a **new**
private directory **outside every Git checkout**. Receipts and compiler logs contain
local paths and are not automatically ignored by Git:

```powershell
python -I -B scripts/door_bridge/compile_load_door.py --compiler <PapyrusCompiler.exe> --content-resources <ContentResources.zip> --out <new-private-directory>
```

The helper reuses the telemetry bridge's CK import allowlist, but compiles only a
frozen copy of this script. Compiler, CK archive, extracted imports, source and PEX
are pinned; failed output is retained with a failed receipt. Existing output is
refused. Neither exit zero nor a stale/empty PEX is sufficient. No game configuration,
plugin, deployment manifest or installer plan is written. Keep the CK sources and
PEX private. The separate directory avoids adding this script to make_bridge.py's
existing source glob.

The actual installed Starfield compiler accepted the script (one private 1,713-byte PEX,
SHA256 `a59e24848b7c3d74158a5cbca84c95ebd9eb70f886550496634ddb1f6eb9fcfc`).
This is the identity of that preserved artifact, not a reproducible-build hash.
Claude's independent PR243 review compiled the same pinned inputs twice and found
different hashes: PEX includes compile/debug timestamps and compiling account/machine
metadata. Keep the PEX, receipt and compiler logs private. A later compile may have
a different output hash without input drift; compare its own source/compiler/import
pins and preserve its own output hash. No normalized or semantic PEX hash is claimed.
The CK source signatures independently confirm GetFormFromFile takes an integer
and filename, and MoveTo accepts match-rotation and rotate-offset booleans. Compile
acceptance does not prove engine behavior. Nine synthetic boundary tests cover
failed/missing/empty products, existing output and input drift; they do not emulate
the Papyrus VM.

## Record/stage dependencies

The preserved old cave params identify source exterior `08EB65:Fallout4.esm` and
interior `05E844:Fallout4.esm`. The old core64c builder explicitly skips the exterior
editor marker, and its paired port has no cave load-door reference. Therefore a
retained reference slot cannot be assumed. Claude supplied current core64h and
integ_1016 Port stage pins in [#32 comment6223300086](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6223300086).
The usable ACTI interaction model and record design remain pending; Claude asked
that no door slots be allocated until that choice is supplied. Do not mutate old
stages, invent IDs, or use the old runtime `04002338` as a plugin-local destination ID.

## Step 0: the two unknowns, before any door record (Claude, 2026-10-16; staged, not run)

One queue answers, with the bridge's console probe and no door record: (1) does `Game.GetFormFromFile` resolve a
**temporary** reference of an unloaded exterior cell from inside an interior (the return trip's destination)? (2) where
does `MoveTo` put the player for the **persistent** core anchor `0x800` (persistent overlay references read their
unmerged position in game), with no offset and with the merge offset (-1200, -2700, 0)?

- `scripts/bridge/FO4SF_Probe.psc`: `Resolve(plugin, id)` and `MoveTo(plugin, id, dx, dy, dz)` take this script's
  contract (file name + plugin-local id) and make its call (`MoveTo(target, dx, dy, dz, True, False)`); line formats in
  docs/ai/test-queue.md "Bridge". Compiled by `make_bridge.py stage` into `C:\Modding\staging\bridge_t2` (both scripts
  "Compilation succeeded"; the plugin is byte-identical to bridge_t0's; its QUST VMAD carries `FO4SF_Bridge` only, the
  probe is reached through `cgf`).
- `scripts/bridge/door_probe.py stage --core terrain_core64i --out door_probe_1017`: the targets read from
  FO4TerrainCore.esm: anchor `000800` = 2048 (persistent, the world's only persistent reference), the Stimpak `0116FB` =
  71419 (temporary, in the arrival's own cell, 6.8 m away), the Super Duper Mart door `02D22C` = 184876 (temporary,
  727.8 m away); the core's plugins and Data hard-linked (51,821 files, 0 copies); four fresh-launch terrain tests:
  (a) at the Red Rocket arrival, the three `Resolve` lines; (b) inside `FO4Port_RedRocket01`, the same three; (c) inside,
  `MoveTo` the anchor with offset 0 0 0, then `Pos 20` and the anchor and Stimpak again; (d) the same with -1200 -2700 0.
- Queue `C:\Modding\testqueue\door_probe_1017` (plan-terrain on integ_1017 with `--bridge bridge_t2 --fresh`); its
  README.txt says which `bridge.log` line decides which unknown (`door_probe.py readme`). Needs runner feature
  `probe_moveto`. Before it runs, the installed bridge_t0 has to be uninstalled (game closed): bridge_install.py refuses
  a second bridge.

Measured cost: a fresh-launch terrain test took 10.8 and 11.6 min in core64h_accept_1016, so the four tests take about
45-50 min of one window, not 15.

Next packet: allocate/check both activator references and destination markers in
their own plugins, preserve every existing identity, serialize/read back the VMAD
properties, verify source and output pins, and prepare the separate `door_script_rr`
stage. No exterior-cell override experiment. Script packing is required on the
owner's install; Claude retains installation, controller and native door_trip/
return/save-reload acceptance. Zero-offset analysis remains the second item.
