# Multi-World Travel-Service Contract & Pending-Trip State Machine (`R14`)

> **Pending owner decisions (Rule 12):**
> - **Reload recovery policy:** `finish_if_dest_ready_else_abort_clear` (**recommended default**, reversible without saving incompatible records; final policy awaits owner decision).
> - **Loading screens during travel:** **Option B** (`304` Starfield `LSCR`s conditioned off + `FO4SF_LSCR_*` pool with blank `DESC` tip text) is the **recommended default** implemented offline in `FO4SFLoadScreens.esm`; Option A (`black spinner only`) or populated `Fallout4.esm` tip text remain trivial toggle alternatives (see [loading-screens-options.md](loading-screens-options.md)).

---

## 1. SFSE vs. Papyrus Responsibility Split

| Layer | Owns | Must NOT Own |
|---|---|---|
| **SFSE UI / Menu Layer (`FO4SFPipboyMenu.dll` + SWF)** | Map marker selection, map coordinate display, plugin code lookup (`world_registry.json`), writing selection target parameters (`Target`, `PluginCode`, `Index`, `X/Y/Z/H`) and invoking `FO4SF_PipboyTravel.Go` / `FO4SF_TravelProbeQuest`. | Worldspace `MoveTo`, `WaitFor3DLoad`, follower teleporting, fade sequencing, or mutating travel lock state mid-transition. |
| **Papyrus Travel Service (`FO4SF_PipboyTravel.psc` / `FO4SF_TravelProbeQuest.psc`)** | Single-trip lock enforcement, writing the **pending-trip record** into save-persisted `GLOB`s **before** `FadeOutGame`, resolving destination `WorldSpace` anchors (`ResolveHostWorld` / `Game.GetFormFromFile`), `FadeOutGame -> MoveTo -> WaitFor3DLoad -> SetPosition/SetAngle -> SQ_FollowersScript.TeleportFollowers -> FadeIn`, post-arrival state clearing, and `Actor.OnPlayerLoadGame` recovery. | Hardcoding world coordinates, calling `Starfield.esm` map/planet menus, or showing debug popups/notifications (`Debug.MessageBox` / `Debug.Notification`) to the player (Rule 13). |

---

## 2. Pending-Trip Record & State Machine (`src/fo4sf/world/travel_service.py`)

A single `PendingTripRecord` is persisted in `GLOB`s (`FO4SF_TravelState`, `FO4SF_TravelSourceCode`, `FO4SF_TravelDestCode`, `FO4SF_TravelMode`, `FO4SF_TravelSeq`, `FO4SF_TravelDestX/Y/Z`) **before** any fade or cell transition begins:

| State (`FO4SF_TravelState`) | Meaning | Legal Next States | Crash / Save-Reload Action (`OnPlayerLoadGame`) |
|---|---|---|---|
| `0` (`IDLE`) | No active transition; lock released. | `PENDING_WRITE (1)` | No-op. |
| `1` (`PENDING_WRITE`) | Pending destination coords, plugin codes, and incremented `Seq` committed to save `GLOB`s **before** `FadeOutGame`. | `FADING_OUT (2)`, `RECOVERED (6)`, `FAILED (-1)` | Abort lock cleanly -> `RECOVERED (6)` -> `IDLE (0)`. |
| `2` (`FADING_OUT`) | `Game.FadeOutGame(True, ...)` active; waiting fade duration before `MoveTo`. | `MOVING (3)`, `RECOVERED (6)`, `FAILED (-1)` | Fade back in (`FadeOutGame(False, ...)`), clear lock -> `IDLE (0)`. |
| `3` (`MOVING`) | `player.MoveTo(dest, ...)` or `Game.FastTravel(dest)` executing. | `WAITING_3D (4)`, `RECOVERED (6)`, `FAILED (-1)` | Fade in, verify loaded world/cell -> finish or abort & clear lock. |
| `4` (`WAITING_3D`) | `player.WaitFor3DLoad()`, `SetPosition`/`SetAngle`, `SQ_FollowersScript.TeleportFollowers`, and item persistence verification. | `ARRIVED (5)`, `RECOVERED (6)`, `FAILED (-1)` | Fade in, verify `GetParentCell() != None`, finalize & clear lock. |
| `5` (`ARRIVED`) | Fade-in started; telemetry logged cleanly without HUD debug text. | `CLEARED (7)` | Transition directly to `CLEARED (7)` -> `IDLE (0)`. |
| `6` (`RECOVERED_FROM_RELOAD`) | `OnPlayerLoadGame` intercepted interrupted trip (`1..4`). | `WAITING_3D (4)`, `CLEARED (7)`, `FAILED (-1)` | Always terminates in `CLEARED (7)` -> `IDLE (0)`. |
| `7` (`CLEARED`) / `0` (`IDLE`) | Pending record retired and ready for next trip. | `IDLE (0)`, `PENDING_WRITE (1)` | No-op. |

---

## 3. Compliance with Travel Design Decisions (`D1`–`D6`)

- **D1 (No lost state across reload):** Pending record written into `GLOB`s before `FadeOutGame`; `RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")` detects interrupted states `1..4`. States `1..2` (pending write, fading out) always abort and clear the lock, even if the destination form is already loaded. States `3..4` (moving, waiting for 3D) finish only when the player is already in the destination world or transit cell; otherwise they abort and clear. This is `finish_if_dest_ready_else_abort_clear` (recommended default, pending owner decision).
- **D2 (Anchor resolution without cross-master dependency):** Destination plugins are never hard masters of `FO4SFTravelProbe.esm`; anchors resolve dynamically via `Game.GetFormFromFile` and `ResolveHostWorld` (`anchor.GetWorldSpace()`).
- **D3 (Follower & carried inventory continuity):** `SQ_FollowersScript.GetScript().TeleportFollowers(player, None, True, False, True, False, False)` runs post-`WaitFor3DLoad`; `GetItemCount` confirms quest/inventory items survive exterior <-> transit <-> opposite exterior transitions.
- **D4 (`MoveTo`+`SetPosition` vs `Game.FastTravel`):** `FO4SF_TravelProbeQuest.psc` exercises both modes (`MODE_MOVETO_SETPOS = 0` and `MODE_FAST_TRAVEL = 1`) and records `Is3DLoaded()`, `GetWorldSpace()`, follower status, item count, and wall-clock duration to `FO4SF_TravelProbe.0.log`.
- **D5 (Single active trip lock):** `IsTravelLocked()` rejects re-entrant requests while `state` is in `1..4`.
- **D6 (Zero HUD debug text):** Only `Debug.TraceUser("FO4SF_TravelProbe", ...)` and `GLOB` telemetry; zero player-facing debug popups.
