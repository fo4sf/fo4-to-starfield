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
