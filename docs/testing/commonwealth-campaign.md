# Commonwealth runtime campaign

Codex owns the offline campaign builder and artifact verification. Claude retains terrain, runner, staging and live game control. The owner's sequence is Red Rocket → Sanctuary → nearby interiors → wider Commonwealth. Existing interior failures remain regressions. Preserve native Starfield physics and Fallout 4 gameplay.

The core64c experiment on [PR #76](https://github.com/fo4sf/fo4-to-starfield/pull/76) stages 648,358 exterior references across 1,708 populated cells in a 64 × 64-cell, 6.4 km square. This is staged coverage, **not runtime acceptance**. Its current probes cover only about 510 m around Red Rocket. Actors, quests, water, source enable relationships and all door fidelity are not complete.

## Prepare once; verify before each run

Use a reviewed integration checkout containing the terrain planner, installer from #83 and budget-resume fix from #89. Keep the existing full interior batch and its state. Do not repin it to another build by changing a hash. Run these commands with the game's Python environment from the appropriate checkout; all paths below are placeholders.

```powershell
# Terrain checkout: confirm the hard-linked exterior tree is still the checked tree.
python scripts/terrain/make_core64c.py verify-data --out <exterior-staging>
if ($LASTEXITCODE -ne 0) { throw 'Exterior changed; re-check before planning' }

# Reviewed runner checkout: plan into a NEW scratch folder. This does not launch/install.
python scripts/game/testqueue.py plan-terrain --staging <interior-staging> --exp-dir <exterior-staging> --out <source-queue-folder> --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm --fresh
if ($LASTEXITCODE -ne 0) { throw 'Planning failed' }

# Checkout with the campaign builder: prepare metadata/phase queues outside Git.
python scripts/testing/commonwealth_campaign.py prepare --source-queue <source-queue-folder>/queue.json --runner <reviewed-runner-checkout> --out <new-campaign-folder>
if ($LASTEXITCODE -ne 0) { throw 'Campaign preparation failed' }

python scripts/testing/commonwealth_campaign.py verify --campaign <new-campaign-folder>
if ($LASTEXITCODE -ne 0) { throw 'Inputs changed; do not run this campaign' }
```

The builder checks the staged plan matches the source queue and the offline check passed. It hashes the exterior Data tree, plugins, source/target identity map, selection/plan/check metadata, interior plugin/archives/map/manifest, and runner game scripts. It preserves source build/provenance and runner feature requirements. The interior `build_id` alone does not identify the exterior. Changes require a new campaign; existing output is never overwritten. The runner snapshot identifies code, not proof that it implements every required feature; review/adoption is an operator gate.

`verify` means the captured inputs and generated queues still match. It does not accept an archive installed later, game version, gameplay, or any runtime result. Pin installed plugin/archive hashes, active load order, runner revision, Starfield version, queue hash and dedicated test-save identity in each run's evidence before judging. The campaign file is local integrity metadata, not a signed or tamper-resistant attestation. Inputs must stay immutable during preparation and live testing; hashing cannot provide isolation from another writer.

## Initial phases

| Phase | Work | Planning estimate | Gate |
|---|---|---|---|
| 01 smoke | First 3 terrain points; first 4 object points, including repeated Sanctuary roof | 13–17 active minutes | Inspect every capture before continuing |
| 02 nearby baseline | All 20 open-terrain points and 10 roof points; roofs at Sanctuary, Red Rocket and Concord, each twice | 42–62 active minutes | Terrain/object loading and collision observations only |
| 03 informational | 15 original obstructed probes | 21–31 active minutes | Expected HEIGHTS failures; inspect points separately |

Estimates use prior exterior observations of 75–115 seconds per point plus a provisional 120 seconds per fresh arrival. Add retries, packing, loading overruns and owner-idle waits. These are estimates, not measured results from these generated queues. Repeated roof drops distinguish late streaming from repeatable missing collision; stationary repeated XYZ may be valid independent captures and must retain genuine capture provenance.

All phases start fresh and retain the original ordered points or a prefix. The prefix keeps the ground reference and every existing waypoint. The builder rejects nonfinite coordinates, missing ground reference, a setup/point move over 200 m along either axis, and a leg that would require an unverified automatic hop. Every final `beyond` position becomes the last judged point. This intentionally removes the old unjudged long jump and does not test the map boundary.

The 200 m policy follows PR #76's audit: ≤2 cells per axis mostly landed; ≥3-cell moves sometimes relocated the player or hung. It is a **supported hypothesis**, not a safe-distance guarantee. Larger maps require short setup moves or new verified arrivals; increasing `hop_m` is not an expansion strategy.

Before a live run, one controller must adopt the reviewed installer/runner, resolve any interrupted recovery, uninstall conflicting Mars/core64-family experiments using their own receipts, and build/verify the archive before activation. Core64 experiments share filenames; never overwrite an installed experiment. The stored exterior archive is estimated at 3.63 GiB; keep room on the temporary and game drives for preparation, publication and rollback. Observe actual pack size/free space before install; full-resolution textures need a separately implemented multi-archive path.

Once those gates pass, the live controller runs **one phase at a time** from the reviewed runner checkout:

```powershell
python scripts/game/testqueue.py run --queue <campaign-folder>/01-smoke --max-hours 2 --wait-for-idle --refocus
python scripts/game/testqueue.py report --queue <campaign-folder>/01-smoke
```

Inspect the report and captures, verify campaign integrity again, then explicitly select `02-nearby-baseline`. Do not put all phases into a blind chain. The run preserves STOP, Guardian and owner-idle controls. Exit 4 means pending work must resume; exit 0 means terminal results, which may include FAIL or INCONCLUSIVE. Circuit-breaker skips are not observations. A daylight queue requires the lighting-capable runner and a newly prepared campaign; old night captures cannot approve material quality.

## Connected travel comes next

These phases are specifications, not executable walking queues yet. Terrain COC/drop tests cannot satisfy them. Do not reuse a roof, object origin or unverified terrain height as a walking surface.

1. **Red Rocket ↔ Sanctuary:** derive source collision surface checkpoints along the road, bridge approaches, bridge deck, far bank and settlement entry. Include both sides of every crossed 100 m cell border. Walk continuously both ways without `setpos`, `moveto`, flight or collision toggles after initial setup. Record actual XYZ, facing, settled height and uniquely captured screenshots at each checkpoint. Require arrival inside a geometry-derived tolerance and sustained progress; missed targets/unreadable captures are inconclusive. Check bridge rails, gaps, invisible barriers and return streaming. Repeat cold and warm, then save/reload at Sanctuary and walk back. Calibrate walking speed on a vanilla control before choosing segment budgets; do not invent an hours estimate before measuring it.
2. **Nearby interior round trips:** first integrate a same-build source-linked exterior/interior pair. #78's Red Rocket cave slice is currently a separate experiment, not evidence of a connection inside core64c. Walk to its trigger normally, enter, cross a floor/stair checkpoint, return through the source exit, verify exterior XYZ/facing and repeat after save/load. Log both source/target reference identities and closed/open collision. Vault111 requires explicit lift/sliding-door behavior; COC entry is not an acceptable substitute. Keep the shorter interior diagnostic batch independent until both datasets are genuinely integrated and pinned together.
3. **Concord and neighbours:** keep the Red Rocket-Sanctuary route and cave round trip as regressions on every expansion. Add road/intersection and cell-border routes with actual source surfaces. Run short cold/warm loading probes first, then uninterrupted walks and door round trips. Halt expansion on missing ground, boundary relocation, lost frames, wrong destinations or unstable save identities; diagnose the failing segment against the same hashes.

## Regional coverage and stress

The builder derives occupied 16 × 16-cell regions (1.6 km square) directly from `objects.json`, checks reference/cell totals against the offline report, and records regional candidates in `campaign.json`. It selects each region's densest, highest guessed/rigged-collision risk and nearest-region-edge populated cells, merging duplicate choices. Negative coordinates use floor division. These are coverage candidates, **not runnable coordinates**: validate arrival, collision-cleared landing disc and BTD/source expectations before writing a regional queue. Empty regions still need terrain-only edge checks. Do not jump from Red Rocket to a distant cell in one console move.

Start with one fresh arrival per region and a few local probes. Separately test continuous adjacent-region travel and return streaming. Then stress the five densest cells reported by core64c's offline check: `(0,-4)` 6,049 refs, `(2,-4)` 5,539, `(2,-2)` 5,519, `(4,-2)` 5,285, `(3,-1)` 5,171. Those coordinates are cells, not verified spawn points. Add high-relief cells, map corners/edges, guessed-collision collections and shifted rigged doors. Pin source evidence for every expected surface. Region/density selection is coverage planning and cannot certify routes.

Measure launch-to-controllable time, stream-to-visible/settled time, frame-time median/p95, peak process RAM and VRAM, object appearance on first/repeated visit, and save/reload stability. Record measurement method and capture provenance. Compare cold/warm passes on the same inputs; screenshot FPS or a process-memory sample alone cannot approve performance. Choose regression thresholds after the vanilla control and first reproducible baseline, not an arbitrary target.

Run regional batches within a 1–2 hour **active** budget with persisted state. Keep failures tied to individual cells/segments and resume pending work. Only broaden sampling after the early gates pass. Runtime coverage is the set of observed regions/routes/doors, never the entire placed-reference count. Maintain separate statuses for planned, observed PASS, observed FAIL, inconclusive and untested.

## Evidence retention

Keep raw observation JSON, queue/campaign hashes and compact reports beside each phase. Record point/segment IDs, source model/reference, expected vs actual coordinates, controls and exception class. Preserve a small representative screenshot set for successes and all actionable failures; review temporary recordings then delete them under the existing media policy. Public GitHub updates should link concise evidence and state its exact scope. Do not commit game binaries, converted assets, local paths, saves or full recording transcripts. Full-map structures/terrain acceptance and complete Fallout 4 gameplay remain separate milestones.
