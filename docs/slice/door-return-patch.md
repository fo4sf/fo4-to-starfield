# Interior-only return patch

Codex prototype, offline tested; independent review and native acceptance pending.
This implements the return-patch portion of the native-core door proposal. It does
not create or move the exterior endpoint and does not cure merge-offset behavior.

Required inputs are full-size Starfield, Port and Core plugins, plus a plan. Port
may depend only on Starfield; Core must explicitly depend on Port and may otherwise
depend only on Starfield. The selected interior reference must already be persistent
in a Port-owned interior cell. The selected exterior reference must already be
persistent in a Core-owned world's persistent cell, with an outbound XTEL targeting
the supplied interior reference. Both bases must resolve to active DOOR records,
including override precedence. Deleted parents/endpoints, unknown dependencies,
conflicting existing returns, nonfinite transforms and relative-position flags
refuse. Initially disabled/open state is preserved; structural success is not proof
the door is usable in game.

Example plan syntax, with synthetic identities and target-engine units/radians:

```json
{
  "interior": "000810:Port.esm",
  "exterior": "000820:Core.esm",
  "arrival_position": [-5, 7, 8],
  "arrival_rotation": [0, 0, 0.2],
  "flags": 0
}
```

```text
dotnet run --project dotnet/DoorReturn -c Release -- Starfield.esm Port.esm Core.esm return-plan.json fresh-output
```

The .NET9 CLI writes FO4DoorReturn.esm into a previously absent output directory.
It hashes all inputs before reading and rechecks them before and after writing.
The build-state receipt stays incomplete on failure. The output contains only the
existing Port CELL and persistent REFR overrides, with XTEL to Core. It allocates
no new IDs and contains no WRLD or exterior overrides, temporary children or
navmeshes. Cell and reference state are deep-copied; reference position/rotation,
scale, disabled/open flags and identity remain unchanged. The arrival plan is
explicit: this tool neither derives nor validates live merge offsets or floor height.

Sixteen synthetic cases pass: one serialized two-way connection and actual CLI
receipt, fifteen invalid-input refusals. Readback checks exact record scope,
master order, identity, grouping, transforms and flags. Input bytes are unchanged.
Run `dotnet run --project dotnet/DoorReturn.Tests -c Release`; optionally set
FO4SF_RETURN_EVIDENCE to a fresh private folder to retain fixtures/logs. These are
author-run Windows checks, not independent QA or game acceptance. The repository's
existing Python CI does not execute this new .NET test project.

Current integration boundary: PR251 supplies a private missing interior endpoint
candidate. The actual Core exterior endpoint and outbound link remain unbuilt by
this tool. Claude owns that producer integration, deployment and live controller.
Do not invent a Core ID merely to pass this gate, replace current stages, or call
the two-way runtime connection complete. Carry forward the source identity maps,
pin all masters and load order, then test activation, return facing and save/reload
under a coordinated game session. No game assets or private candidate files are
included in this proposal.
