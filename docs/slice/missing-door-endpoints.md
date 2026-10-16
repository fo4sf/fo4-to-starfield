# Explicit missing interior door endpoints

Codex: the optional ReferenceLinks post-pass accepts
`--door-bases=path/to/door-bases.json`. This prepares a missing interior endpoint
whose source door was skipped as editor-marker geometry. It does not construct
an exterior endpoint, resolve worldspace merge placement, or establish a working
cross-plugin trip.

The JSON object maps an exported source reference FormKey to an explicitly
selected target DOOR FormKey. Example syntax using synthetic identities:

```json
{"000123:Source.esm": "000900:Starfield.esm"}
```

Use the normal input plugin, persistent formids map, fresh output directory and
original cell exports. STARFIELD_DATA supplies the actual native master. The
selected source must occur exactly once with type Door, and the base must resolve
to an active DOOR with local override precedence. A filename or numeric ID alone
does not prove a usable base.

For a missing reference, the writer reuses its existing source-map reservation,
or allocates above all existing mapped and occupied IDs. Occupied reservations
and exhausted IDs refuse. Position is converted using the existing /70 unit
mapping; rotation, positive scale, initial disabled and open state are preserved.
The endpoint is placed in its original interior cell's persistent group with
flag0x400. An existing reference must have that same base and cell and be active;
the option never silently changes its base. Reapplication preserves identity and
does not duplicate the endpoint.

Normal relationship translation follows. No XTEL or reciprocal link is invented.
Unresolved exported relationships still prevent output unless the existing
`--allow-unresolved` option explicitly permits a partial build. A partial build
must not be called a connected cave. Report CreatedDoors counts new references.

Seven synthetic actual-CLI controls cover allocation, reservation/reapplication,
non-door bases, wrong source types, occupied IDs, invalid scale and absent source
selections. The prior eleven native-base/persistence CLI controls also pass.
Before implementation all seven new controls failed; evidence is retained
privately. This is author-tested offline code awaiting independent peer review.
No source stage, installed plugin, game input or save was changed. Integration
must carry the resulting map forward and separately construct the core-owned
exterior endpoint and interior return override without a master cycle.

## Current Red Rocket export check (October 16)

Using code63131c6 and a private snapshot of integ_1016 Port
`1ff6e4dadf59ec0aeae8ee0df79c5d21ca835ca2a0b6876c72a0f630fb41b8fc`,
the unchanged RedRocket01 export and selected native AutoloadDoor_Cave base
produce one new endpoint. Source `05E844:Fallout4.esm` receives plugin-local
`00DE5D` in the **candidate's** persistent map. All54,877 prior entries remain
identical. This ID is a candidate reservation, not an installed/runtime identity;
integration must carry forward this map or explicitly reconcile new allocations.

Strict mode refuses with the missing exterior `08EB65:Fallout4.esm` destination
and publishes no plugin. An explicitly partial output permits raw inspection:
persistent cell ownership/flag, native base, source position/rotation/scale and
active state match; XTEL remains absent. Independent raw parsing shows no removed
records and only the new REFR, TES4 HEDR update, and three existing references'
persistence/group changes. Those three are sources05F97B,05FAA0,05FAA3; each is
explicitly persistent in the original export. Their subrecord bytes are unchanged.
They are additional normal post-pass changes, not a claim of a one-record patch.

Partial output SHA256:
`cdd69d7bec515fefba1193c2904ab0ab3cc52dc2cf4e8d9aca1fa2620c5a0491`.
Source plugin/map/export and native master hashes were rechecked unchanged.
Private evidence lives in `test-plans/missing-cave-production-20261016`, including
an initial harness failure from assuming net8.0 instead of this project's net9.0;
that attempt ran no writer. Corrected strict/partial outputs are separate.
This author-run raw audit is not peer review or native acceptance. No deployment
package was made, and this unlinked partial candidate must not replace a build
being used for gameplay tests.
