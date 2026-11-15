# S3 exterior discovery and map listing: next PC evidence card

Codex / Lone Wanderer, Ubuntu 26.04.1 LTS. FAL-848, draft #790.
**Pending Courier Copy review; Windows/Papyrus/game NOT_RUN here.** This card is a
bounded diagnostic precursor, not an owner-installable lift or install authorization.

## Input and fixed decision

Reuse the PC's 14 November receipt `d6a04cf2` and private folder
`fal848-marker-20261114T232829Z`. Indoor MoveTo reached XYZ with world=None;
indoor discovery produced no named discovered map marker. Outdoor repair and a
save/load held. Do not repeat those indoor stages or credit outdoor repair to them.

Candidate hiding route: world attachment at the beginning of the unchanged final
exterior ascent, followed by marker movement during its remaining motion. No extra
beat, blackout, slowdown or hop. The 26-second old result includes hold/reload and
is not the candidate budget. A surface map that requires re-entry rejects this route.
This card tests that prerequisite first, before building the final exterior ascent.

## A. Diagnostic prerequisite: discover after exterior attachment, no hop

Use an independently reviewed checkout of #790; record its **actual full head**.
Use the unchanged marker probe from the reviewed first-slice head `bb2d385b`,
not any uncommitted warmed-anchor extension in the author's workspace. Record that
separate kit source head. Do not patch the kit on the PC.

1. Record game-closed before-install and cleanup receipts. Use the established guarded
   session installer/uninstaller, a fresh throwaway start, and the PC's session-only
   logging/launcher procedure. Keep the owner's normal build/settings and saves.
2. Stage map markers with the installed build's recorded options, adding
   `--landing-undiscovered --no-reload`. Keep the installed core pinned; record its
   head/hash and every marker/plugin/PEX hash. Confirm all quests have
   ShowLandingMarker=false and no HopMarker; the no-hop condition also prevents the
   script's dark hold. Confirm Vault 111, landing and ordinary markers start without
   Discovered. Any mismatch stops the affected result.
3. Stage/precheck the existing probe with its established tools. Close the console
   between stages and wait for stage completion. Use numeric quest id (load index
   plus `000800`), never its editor name. Start directly outdoors by the established
   `coc FO4Core_RedRocketSpawn` route; **do not run stage 20 or indoor stage 30**.
4. Record attachment time, runtime player world/core cell and target position. Run
   stage 10 for baseline. Let the outdoor mover finish, without a hold/reload.
   Do not equate “in place or out of moves” with success: retain every quest's move,
   refusal and budget lines. All required map markers must be in the same runtime
   world at their staged merged targets; the known immovable pad is a separate
   limitation, not a missing map marker that may be silently ignored.
5. Open the surface map **before discovery**, capture all
   visible UNKNOWN entries and any automatic named/discovered entry. If Vault 111
   is already discovered, this state cannot measure the call's discovery effect.
6. Back in the loaded exterior, stage 30 calls **only V111.SetMarkerDiscovered**.
   Its before lines must show V111/player in the same real exterior world and V111
   at its merged target; otherwise this result is invalid. Record before/after/+2 s
   lines and global fast travel. Stage 40 then reads all four references. Use stages
   10/30/40/50 in that order, without 20/60/70. Open the map immediately,
   with no re-entry/reload or player movement that could auto-discover a location.
   Identify V111 by a named `Vault 111` entry at its pinned target. Capture its
   discovered icon/state and an available **Fast Travel** offer; do not travel.
   UNKNOWN, a proxy staying true, a log without error, or global fast=true is not proof.
7. Landing and one ordinary location must remain undiscovered. If UNKNOWN prevents
   identifying the landing entry by target, report that check unresolved; two
   arbitrary unknown entries do not prove the landing marker stayed undiscovered.
8. Save under a new throwaway name, return to the main menu, load, then stage 50.
   Repeat the actual map and destination reads. Mark persistence separately from
   whether reload was needed for the **first** listing. Remove session kits with
   their uninstallers; verify the before/after receipt and throwaway-save cleanup.

Return exact heads, hashes, native/compile/install results, attachment-to-final-move
elapsed time, per-quest completeness/refusals, stage tables, map observations before
and after the call/load, other-location check, and private evidence/cleanup location.
A diagnostic call is not evidence the new production quest has run.

**Decision:** no named discovered Vault 111 plus usable destination before reload =
HOLD on this candidate, with the boundary recorded. A first listing only after a load
is a listing failure for this route even if it persists thereafter. No black-hold fallback.
A map-only pass permits building the final exterior segment; it does not prove timing.

## B. Production exact-build follow-up (not runnable by this source slice yet)

After the floor lift/console/ascent and all-marker coordinator are wired and reviewed,
stage the exact build against the owner's assets. In a fresh normal new game, operate
the vault console, walk through the colliding gates and ride from the waiting floor
without console movement. Capture actual exterior-attachment time and unchanged
ascent-finish time. Require every marker at its target and listed by finish, with no
hop/blackout/slowdown. Compare **measured** all-marker elapsed time against that window;
no subtraction of the old 24.4-second hold predicts this value.

At arrival capture `surface setposition ok=True`, later `landed ... confirmed=True`,
`arrival discovery requested` for the canonical V111 reference, and absence of
`exit failed`. Then repeat A's named discovered icon/Fast Travel/other-location and
save/menu/load checks. If the game refuses travel because the player is already at
Vault 111, record that separately and check the offer again after a short safe walk
without discovering another location. Those map reads prove discovery; the script logs only confirm
which guarded call ran. A failed arrival, marker not attached or missing map destination
is failure, not completion. The new source intentionally does not force the global
fast-travel switch to conceal a failed destination. Owner install and complete S3 remain
open until this full exit result is recorded.

## A2. Does discovery survive one real door load? (FAL-1007; route decision FAL-1017 comment 2bcf4983)

Minuteman Copy. **Pending Courier Copy review; Windows/Papyrus/game NOT_RUN by the author.** Diagnostic only.

Input: section A's PC result (FAL-1007 comment 39f3f7cf, evidence `fal848-arrA-4aaaa2c0-20261115T223905Z`): with the exterior
attached and one `V111.SetMarkerDiscovered`, the map listed none of our markers before a load (not even UNKNOWN); after
save/menu/load only UNKNOWN entries were seen. The Scribe's `elevator-map` is not on main and is not relied on here.
Same build and kit as A (#796 `4aaaa2c0` / kit `bb2d385b`, `--landing-undiscovered --no-reload`, stages 10, 30, 40 in
order, no 20/60/70, hashes recorded as in A).

1. `coc FO4Core_RedRocketSpawn`, let the mover finish, stage 30 once on Vault 111. Read the map: no list is expected (as A).
2. Take **one real door load** into an interior and back out. No save, no menu, no console movement, no other
   `SetMarkerDiscovered`. Record the door (ids, world/cell before and after) and the **length of each load**. Read the map
   **inside** the interior and **after exiting**.
3. After exiting, run stage 40 and check: (a) Vault 111 named and discovered; (b) a Fast Travel offer (do not travel; if the
   game refuses because the player is already at Vault 111, take a short safe walk that discovers nothing and check again);
   (c) the landing marker and one ordinary location (identified by target) undiscovered, or UNKNOWN; if UNKNOWN hides the
   landing entry, that one check is unresolved; (d) the rough count of listed entries against the expected about 309.
   Visible/canfast and global fast travel were already true at stage 10 and are not proof.
4. Then save, return to the main menu, load, stage 50: is Vault 111 still named and discovered?
5. Remove the session kits with their uninstallers and return the before/after receipts and throwaway-save cleanup.

Result rules (Sole, FAL-1017):
- **PASS** (listed after the door load, Vault 111 discovered, the others undiscovered): route E (no extra load; list fills at
  the first natural load) can be built, or D (one short ordinary loading screen) if the owner says so.
- **Listed but Vault 111 not discovered:** a re-request of Vault 111 discovery at the first load becomes required; the next
  card tests that.
- **Not listed after a door load:** only a save/load builds the list; E and D both fail and only the plugin-placed-marker
  research remains. No black hold, slowdown or hop is added to make any outcome pass.
