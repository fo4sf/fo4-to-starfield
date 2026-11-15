# S3 vanilla overlay control: game-closed identity read

Codex / Lone Wanderer. This is Slice 0 after Scribe FAL-898's
first-entry-control-design rev1 and the completed PC0945 ancestry read.
All four earlier persistent paths matched; that topology hypothesis stays closed.

The unresolved setup needs a vanilla MapMarker without the Initially Disabled
record flag, paired with an actual EditorID-bearing exterior CELL/COC reference
in the same overlay world. The offline LC172 marker003E5E12 has flag0x800, and
no positive first-entry listing was recorded. No Enable or guessed COC is allowed.

## Reader and input

Use the exact independently reviewed source head named on FAL-848's
vanilla-control-offline-pc-card. The small CLI composes existing
census.world_refs/coc_cells and esm.Plugin's read-only mmap/record parser.
It opens one file, hashes that same mapping before/after, scans target headers
for unique stored identities, then parses only the explicitly selected world's
records with the existing reader (including compressed payloads).

Game closed throughout. Use the original Starfield.esm1.16.244 pin from PC0945,
not a renamed plugin or any other Data input. Use the existing project Python
venv with numpy; missing dependencies are NOT_RUN, with no installation.
Fill in only the private path:

```text
python -I scripts/planet/read_overlay_control.py --starfield-esm "<Starfield.esm>" --world 001187EA --marker 003A866E --expect-sha256 1dabed00c3f4282dd3bb54d2e9601e40b577d8742d078b7ccef203adbfef0da7
```

The requested pair is the previously documented LandingOverlay01 world/marker,
not a newly invented ID. The marker must actually be a persistent REFR with
NAME00000010, XMRK and no0x800 flag; the world must contain an overlay component.
These are static record checks, not current runtime-enabled/visible state.
The command requires the original basename Starfield.esm and no masters.
No other world or marker is automatically tried.

Only JSON goes to stdout; errors go to stderr, nonzero exit, no partial stdout.
There is no output/stage/install option or game call. Capture stdout/stderr through
the established private-PC evidence procedure, outside the game folders. Keep
normal independent before/after receipts; mapping hashes do not guarantee against
external path replacement.

## Read oracle and stopping rule

Return actual command, source/script hashes, Python version, exit and stderr,
matching input before/after hashes, world ID/EditorID/offset/overlay fields,
marker ID/offset/raw flags/base and its parent cell, and all returned candidates:
CELL stored ID/EditorID/XCLC grid/offset/raw DATA plus actual COCMarkerHeading
reference ID/offset/raw flags. Existing census policy returns the first COC
reference per cell; initially-disabled COC candidates are excluded. No model,
string-table, LCSR or quest enabling analysis is performed.

- CANDIDATE_IDENTITY_ONLY: one or more actual same-world CELL/COC pairs. Return
  them unchanged; parent chooses any later runtime card. This is a static setup
  candidate, not proof that COC succeeds or the marker appears on a map.
- UNRESOLVED_NO_COC_CANDIDATE: file read succeeded but no eligible pair exists.
  Stop. Do not invent another EditorID, enable a marker or search other worlds.
- Missing/duplicate target, wrong world/marker, hash/master/schema error or
  nonzero exit: comparison UNREAD. Keep stderr and stop, never treat it as a
  missing game marker, a successful candidate or a request to install tools.

Confirm unchanged file receipts and no game-folder changes. This read creates
no save or game state. Earlier TEST2 cleanup chronology is already resolved by
PC0945 and is not a new prerequisite.

## Later runtime question remains gated

Only after a real candidate is returned can a separately implemented/reviewed
read-only session probe resolve that vanilla marker with GetFormFromFile and
read marker/player GetWorldSpace/GetParentCell. Its vanilla first-entry surface
map must positively identify the actual marker. No entry, UNKNOWN or unidentifiable
entry leaves the listing baseline unresolved. Our V111 read must be made with the
map-mover plugin absent, not by racing timers or using --no-reload.

LandingOverlay01 and our LC172-family overlay differ in family; any runtime
difference is a lead, not proof of a source fix. No discovery, AddToMap, setter,
Enable/Disable, hop/reload, hold or lift slowdown belongs in this identity read.
No listing/native/full S3 pass or PC session release follows from the tool.

Correction to FAL-898's design summary: d6 stage10 references retained their core
exterior worlds; stage20's indoor MoveTo left TEST with world/cellNone. Timer
periods alone do not prove order. The proposed mover-absent configuration, not a
timing race, establishes the later no-mutation boundary.
