
## Slice 1 (2026-10-15): the first-aid kit as a native container, in core64c's own build

`make_core64c.py stage --cluster scripts/terrain/clusters/r05_medkit.json` takes the Red Rocket first-aid kit
(`19EE52:Fallout4.esm`, 6 m from the arrival) out of the STAT placement and emits it as `objects.json "containers"`;
`TerrainOverlays` writes a native CONT (`FO4Core_cont_19ee52`, the converted model, name "First Aid Kit", 25 Credits
and 1 Digipick: vanilla items, since FO4's leveled lists do not resolve) and one temporary REFR in cell (-10, 11),
allocated after every other record so the 648,358 other references keep their ids (`check`: every new FormID after
core64's last, one CONT, REFR count + 1, per-cell counts). Vanilla has 98 containers without components (e.g. a
Shipping Crate with a plain model), so a CONT on a static model is a valid pattern; whether the converted mesh's
collision gives an activation prompt is the in-game question. Staged as `C:\Modding\staging\terrain_core64d`
(core64c's Data hard-linked, a new plugin). Acceptance: the arrival, `cgf "FO4SF_Probe.Pos" <container ref>` in the
bridge log (loaded, position), a screenshot at the kit, then the owner opens it (the runner has no activate step yet).

Build result (15 Oct): `terrain_core64d` = CONT `FO4Core_cont_19ee52` 0A2AA4 + REFR 0A2AA5 (cell (-10, 11), local
-993.14 1151.66 105.30), allocated after core64c's last id; `check` 245 of 245 ok (every core64 record unchanged, every
new FormID after 0x001805, 648,360 REFR = 648,357 objects + COC marker + anchor + 1 container, the Mars plugin
byte-identical to core64c's). The first writer run crashed: Mutagen 0.55's `Container.Items` is null by default and
must be created before adding entries. Acceptance queue `r05_medkit_1015` (experiment `r05_medkit_accept`: `cgf
"FO4SF_Probe.Pos" 34220709` = 0x020A2AA5 at load index 02, probe `by_the_kit` at (-992, 1150) expecting 105.26).
