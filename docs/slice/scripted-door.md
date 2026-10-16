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

Next packet: allocate/check both activator references and destination markers in
their own plugins, preserve every existing identity, serialize/read back the VMAD
properties, verify source and output pins, and prepare the separate `door_script_rr`
stage. No exterior-cell override experiment. Script packing is required on the
owner's install; Claude retains installation, controller and native door_trip/
return/save-reload acceptance. Zero-offset analysis remains the second item.
