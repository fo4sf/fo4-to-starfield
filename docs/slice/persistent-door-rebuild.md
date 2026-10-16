# Persistent door audit of the October 16 interior rebuild

Codex, October 16, 2026. Read-only source-stage comparison, not native travel or
save-game acceptance. Current FO4Port.esm SHA256:
`1ff6e4dadf59ec0aeae8ee0df79c5d21ca835ca2a0b6876c72a0f630fb41b8fc`.

The preserved `integ_1011` and current `integ_1016` plugins/maps were inspected with
a raw record/group walker separate from Mutagen and the producer's report. Every
input was pinned and checked unchanged afterward. Findings:

| Check | Result |
|---|---|
| Source ID map | All 54,877 entries identical |
| Master table | Both contain only Starfield.esm, same order |
| References using DOOR bases | 180 in each build |
| Persistent DOOR references with XTEL | Two, forming one reciprocal pair |
| Existing pair | FortHagen01 ↔ FortHagen02 |
| Pair identities, parent groups, flags and all subrecord bytes | Identical across builds |
| Reported unlinked source references | All 28 found in the plugin, all without XTEL |
| Those 28 bases/storage | 20 DOOR, 8 STAT; all temporary |
| Reported unplaced source endpoints | All four lack source-map slots |

The existing pair uses plugin-local IDs `00C7A7` and `00DE51`; its CELL IDs are
`00BA4B` and `00CFC6`. Both endpoints have record flag0x400, group8 under the correct
group6 parent, active DOOR base `00CDFF`, reciprocal destinations, and finite
reference/arrival transforms. These are file/plugin-local identities; derive
runtime IDs from the actual current load order. No new load-door connection is
established by the interior rebuild alone.

The missing endpoint sources are Red Rocket `05E844:Fallout4.esm` and Vault111
`248AAD:Fallout4.esm`, `148B69:Fallout4.esm`, `01F180:Fallout4.esm`. The Red Rocket
map still has no original endpoint to reuse. The 28 unlinked references need their
destination endpoints; eight additionally need a deliberately selected DOOR base
before native XTEL can apply. Merely adding persistent flags does not create those
records, types or relationships. This is a present-state inventory, not a claim
that these omissions were introduced by the rebuild.

Six negative controls clear persistence, change group ancestry or break the
return edge for each existing endpoint; all are detected. The first audit attempt
was stopped because it recomputed a base set inside a reference loop. Its partial
output is retained. A separate initial assertion that all28 unlinked bases would
be DOOR was false; the corrected audit explicitly records the20/8 split. Neither
attempt changed source/game files.

Private packet `test-plans/persistent-interior-rebuild-20261016` retains scripts,
failed/partial and passing observations, raw input snapshots and detailed
per-reference results. No game records or compiled assets are published here.
This audit does not validate collision, models, native activation, worldspace
offsets, installed load order or save compatibility. Claude retains controller,
primary writer and build integration; peer review of Codex proposals remains
separate from this author-run output inspection.
