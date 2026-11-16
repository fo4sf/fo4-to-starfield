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

## A3. Discover Vault 111 AFTER the door load (FAL-1007; follows A2 result FAL-1021, FAL-1017 rule 2)

Minuteman Copy. **Pending Courier Copy re-review (FAL-1030 changes applied); Windows/Papyrus/game NOT_RUN by the author.**
Diagnostic only; the probe kit is unchanged (no patching on the PC).

Input, A2 (PC result, FAL-1021 comment 39f846d6, evidence `fal848-arrA2-55bb428b-20261116T003909Z`): one real door load fills the
surface list, but every entry is UNKNOWN; the pre-load `V111.SetMarkerDiscovered` did not stick, also not after save/menu/load.
A2 exited about 1 km from Vault 111 and could not tell which UNKNOWN entry was Vault 111 (tilted map, one tile around the
player, 50-90 of about 309 entries).

Same build, kit and heads as A and A2 (#796 `4aaaa2c0`, kit `bb2d385b`, `--landing-undiscovered --no-reload`; the bridge may
be set on for the session only, as in A2, for `FO4SF_LoadDoor`; record the resulting probe quest id and every deviation).
Stage 10/30/40/50 only; leave 20/60/70 unset. Stage 30 is the only `V111.SetMarkerDiscovered()`; stages 10/40/50 only read.

1. `coc FO4Core_RedRocketSpawn`, let the mover finish. **Do not run stage 30 yet.** Run stage 10 (baseline) and record the
   stage-10 V111 position (its merged target).
2. One real door load in and back out, with the A2 door pair where possible (exterior FO4TerrainCore `02D22B`, interior FO4Port
   `007D0B`); record ids, worlds and load lengths. No save, menu, or other discovery call.
3. **Bring Vault 111's tile on screen BEFORE the baseline map.** After the door, move to the stage-10 V111 position (console
   hops with each axis under 200 m, as on the A2 door approach, or a walk). Record the method and distance, and that nothing was
   discovered by it. Open the surface map, lock the view and zoom you will reuse, and confirm the locked view contains the
   stage-10 V111 position. **If it does not, the run is invalid** (it is not a "no entry changes" result).
4. Baseline capture on that locked view, before stage 30: entries (count, icons), the entry nearest the V111 position, any
   named entry, and the compass. **Stop, and report the run as invalid, if:** (a) there is no surface list (the door load did
   not repeat A2); (b) any named or discovered entry is already visible, including Vault 111 (the approach changed the list).
   A walk or hop that discovers anything before the baseline is the same stop. Do not run stage 30 to test anything here:
   its before-lines are printed inside the stage that also runs the discovery call.
5. Run **stage 30 only**, once, with its before/after/+2 s lines. **After it runs, read its before-lines (they are printed inside the same stage that makes the call):** if V111 and the player
   are not in the same exterior world, or V111 is not at its merged target (as in section A), the run is invalid and the result
   rules do not apply; do not run stage 30 again. Close the console, reopen the map at the **same locked view and
   zoom**, and capture again. Do not travel or walk before this capture.
6. Judge by difference on the locked view: which entries changed (icon, name, UNKNOWN to named) and whether the changed entry is
   the one nearest the stage-10 V111 position. Hover all changed entries and record the name text. Then check Fast Travel (do not
   travel). If it is refused because the player is near Vault 111, take a short walk that discovers nothing and check again;
   that walk does not revise the two captures. If the walk discovers another location, record the Fast Travel check separately
   and fail the other-locations check. Also record entry counts before and after.
7. Persistence, recorded **separately** from steps 3-6: save, menu, load, stage 50, the map at the same view. Is Vault 111
   still named and discovered?
8. Cleanup receipts and kit removal as in A and A2.

Result rules (on a valid run):
- **PASS:** exactly one entry changes; it is named `Vault 111` and discovered; Fast Travel is offered; no other entry changes;
  it is the entry nearest the stage-10 V111 position on the locked tile; and the Fast Travel walk (if any) discovered nothing. The arrival design is proven for the route
  (markers moved during the ride, FO4's load at the top, then `SetMarkerDiscovered` on Vault 111 only after the load). S5 can
  be built.
- **One entry changes to named, discovered `Vault 111` with Fast Travel, but it is not the nearest to the stage-10 V111 position:**
  not PASS, Partial, other-entries or no-change. Report the entries and stop; build no S5 and open no SetScanned card.
- **Fast Travel walk discovers another location:** record Fast Travel separately and fail the other-locations check; this is
  not PASS even when the two captures match the PASS bullet, and it opens no SetScanned card.
- **Partial:** exactly one entry changes, nothing else changes, and it is unnamed, named something other than `Vault 111`,
  not discovered, or has no Fast Travel offer. The next card tests Gemini (PC)'s `SetScanned(true)` /
  `SetRequiresScanning(false)` or `AddToMapScanned(true)` on a separately reviewed kit change; that change is outside A3.
- **Other entries also change:** report which. This is outside PASS and outside the SetScanned card.
- **No entry changes** on a valid baseline whose locked tile contains the stage-10 V111 position: discovery does not take
  effect after a load; replan with Sole (FAL-1017). No hold, slowdown, hop or reload is added to force any outcome.
