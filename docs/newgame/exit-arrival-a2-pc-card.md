# S3 section A2: does Vault 111's discovery survive one door load? (narrow PC card)

Minuteman Copy, Ubuntu. FAL-1007 / FAL-848. **Pending Courier Copy review; Windows/Papyrus/game NOT_RUN by the author.**
Diagnostic only: no install authorization beyond the established guarded session kit, no source change.

## Input

Section A at #796 `4aaaa2c0` / kit `bb2d385b` (PC result, FAL-1007 comment 39f3f7cf, evidence
`fal848-arrA-4aaaa2c0-20261115T223905Z`): with the exterior attached and one `V111.SetMarkerDiscovered`, the map listed
none of our markers (not even UNKNOWN) before a load; after save/menu/load only UNKNOWN entries were seen and no named
discovered Vault 111. Reading by Claude (PC): the map builds its list of our markers at load time. Fallout 4's own ride
ends in an automatic load door (`Vault111InteriorAutoLoadDoorREF` 0001F180 -> 000998E3), so a load at the top is expected.
(The Scribe's `elevator-map` §1.4/§5 is cited by Claude (PC); it is not on main, and I have not read it.)

Open question this card answers: **after one load through a door (not save/menu/load), is Vault 111 named and
discovered, with Fast Travel, while the landing marker and one ordinary location stay undiscovered?**

## Procedure (same kit, stage order, no-hop build as section A)

1. Repeat section A steps 1-6 unchanged: same heads/hashes, `--landing-undiscovered --no-reload`, outdoors by
   `coc FO4Core_RedRocketSpawn`, stages 10, 30, 40 in order, with the before/after/+2 s lines. Record the pre-discovery map
   (expected from A: empty). Do not open the map after stage 30 as the measurement; A already gave that.
2. Walk through **one ordinary load door** and, if needed, back out (an installed exterior/interior door pair, e.g. the
   Super Duper Mart `FO4SF_LoadDoor` pair already PASSed on 17 Oct; record exactly which door, its ids, and the player
   world/cell before and after). No save, no menu, no console movement, and no other `SetMarkerDiscovered`.
3. Immediately after the load, run stage 40 (read the four references and fast travel) and open the surface map.
   Capture: named `Vault 111` entry at its pinned target, its discovered icon, a **Fast Travel** offer (do not travel);
   the landing marker and one ordinary location (identify by target; if UNKNOWN hides the landing entry, that one check is
   unresolved). Proxies (visible/canfast, global fast) are not proof: they were already true at stage 10.
4. If the door brought you back inside the vault-side exterior world already, state it. If the first load does not list
   it, record whether a **second** load through a door lists it (still no save/menu/load).
5. Only then, as a separate persistence note, repeat A's save/menu/load and stage 50 once, and report whether a named
   discovered Vault 111 exists there. Remove kits with their uninstallers; before/after receipts and throwaway saves.

## Report and decision

Return heads/hashes, the door and worlds, stage lines, the map observations after the first door load (and second, if run),
the other-location check, and cleanup. Outcomes:

- Named discovered Vault 111 + Fast Travel after one door load = the arrival design (discover during the ride, listed after
  the unavoidable arrival load, as in FO4) is supported; the production slice may be built. Timing during the ride is
  still unmeasured.
- Listed but undiscovered, or UNKNOWN only = the call is not taking effect across the load: discovery needs another
  mechanism (e.g. a build-time flag or a call after the load); report which, no further guess here.
- Not listed after one or two door loads = HOLD; replan with Sole (FAL-1017).
- No black hold, slowdown, hop or reload added to make any outcome pass.
