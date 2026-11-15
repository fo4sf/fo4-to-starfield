# S3 marker ancestry: game-closed file comparison

Codex / Lone Wanderer, Ubuntu. This is the next file read after FAL-848 PC result
`cd413e55-fa51-4480-a187-e9b6721cbb96` and Scribe FAL-887 `marker-record-diff-audit` rev 1.
The previous comparison is complete, including its explicit reader gaps. No setter experiment is repeated.

The pinned Mutagen 0.55.0-alpha.67 schema at
[`414371ee`](https://github.com/Mutagen-Modding/Mutagen/blob/414371eedc94a3e0c28f082180e0492df67ab8ca/Mutagen.Bethesda.Starfield/Records/Major%20Records/PlacedObject.xml)
models UNAM as a translated string. Its localized ID versus an unlocalized empty string is not a demonstrated
integer-width bug. Empty LCID is deliberate initially-disabled-reference policy; the sparse persistent CELL is
constructed in the core and copied by the marker plugin. None of those differences establishes a listing cause.
Ordered GRUP ancestry was **UNREAD** in the PC receipt and is the sole question here.

## Reviewed tool and scope

Use the independently reviewed commit of draft #790 containing `ref_inspect.py --record-path`, in a detached
source checkout. Record its exact commit, the script SHA-256, the actual commands and exit codes. This document
does not grant a PC session or installation release; the current task's reviewed card supplies the handoff.

This mode reuses `fo4sf.planet.esm.Plugin.walk`, opens the plugin with read-only mmap, scans headers across every
top group and prints JSON to stdout. It writes no report, plugin, settings or game file. The old `--ref` inspection
is unchanged. Use the PC's existing project Python environment with `-I`; a missing dependency is **NOT_RUN**,
not permission to install one. Capture stdout/stderr only in a new private evidence report through the established
PC procedure. Do not place the checkout or report under the game folders.

Game closed throughout. Read the original vanilla/core files and the **retained session copy** of the markers,
not the restored normal marker installation. No launch, install, plugin toggles, save/load, console, marker move,
discovery, enable/disable, hop, hold or lift slowdown. No session kit is built or installed.

## Three commands, four stored identities

Replace only the private file paths, keeping these hashes and stored IDs. They come from the actual master
tables in cd413: vanilla has no masters; core has `[Starfield.esm]`; session markers has
`[Starfield.esm, FO4TerrainCore.esm]`. `--record-path` requires eight hex digits and never substitutes a local ID
or runtime load-order prefix. This reader uses the ordinary file master-table namespace; compact/runtime ID
decoding is outside this request.

```text
python -I scripts/terrain/ref_inspect.py --plugin "<Starfield.esm>" --record-path 003E5E12 --expect-sha256 1dabed00c3f4282dd3bb54d2e9601e40b577d8742d078b7ccef203adbfef0da7
python -I scripts/terrain/ref_inspect.py --plugin "<FO4TerrainCore.esm>" --record-path 010A775B --expect-sha256 dc75166449332f113825298adb94ec2c4b528145db440ebff450e6ec3e3c0fd9
python -I scripts/terrain/ref_inspect.py --plugin "<retained FO4SFMapMarkers.esm>" --record-path 010A775B --record-path 02000901 --expect-sha256 0afa47c85a5f5684858975368d4f96eb72efccd1bc5f183f11d5dc9cfd8022f5
```

`010A775B` is **FO4TerrainCore.esm:0A775B** in both core and session override. `02000901` is the session plugin's
own **FO4SFMapMarkers.esm:000901**, whose FULL Waypoint Echo was confirmed in cd413. The input filename supplies
the own-plugin name; retain its original basename. Do not use runtime `03`, `09`, `0A` or `FF` prefixes.

## Fixed read oracle and decision

Each query must have exactly one matching record. Return:

- Input basename, actual masters and identical before/after SHA-256 matching the pin.
- Record signature **REFR**, exact stored and master-qualified identity, record header/end offsets and flags.
- Every enclosing GRUP in root-to-record order: header/end offsets, numeric type and raw four-byte label.
  Types 1, 6, 8, 9 and 10 also show master-qualified label IDs; block/grid labels remain raw. A
  `qualification_error` is **UNREAD** for that identity, never a valid resolved parent.

The result is **read-complete** only if all four identities have complete comparable paths and no qualification
gap. Compare whether the paths traverse the world-children group and the persistent CELL's children/persistent
children (type 8), versus another location such as temporary children (type 9). Record actual types rather than
assuming they must match. A missing/duplicate ID, hash mismatch/change or malformed boundary exits nonzero and
must not be called a missing game record or a successful ancestry read. Preserve stderr and mark that comparison
**UNREAD**. The mode does not decompress record payloads, decode LCSR, look up strings or resolve effective runtime
records. Its hashes refer to the opened file mapping; also retain the normal PC before/after file receipt.

If paths differ, return that exact structural difference for source investigation; do not mutate the plugin.
If paths match, close this topology hypothesis and stop this read. Do not then copy vanilla CELL fields or try
another setter. Either outcome returns to FAL-848 for the next evidence-backed decision. Neither is a map-listing,
named-discovery, Fast Travel, timing, native carrying or full S3 pass. Earlier HOLD results remain closed.

No cleanup of game files or saves should be necessary for this file-only read. Confirm no game-folder changes;
this receipt does not answer the earlier TEST2 save-absence rechecks.
