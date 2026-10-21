# Tiered test queues for a build (`scripts/game/inventory.py`)

Claude-cloud, 2026-10-19. Task T-inventory in `research/next-phase/testing-automation.md` (2.1 and 2.2). Offline
tooling, unit tested on synthetic stagings; **no queue from it has run in game yet**.

## What it does

- **Tier 1, smoke:** one `fall` test per cell (`testqueue.py plan --kinds fall --per-cell 1`). The runner cocs into the
  cell, drops the player onto a floor point from `probe_points.py`, and reads where they land.
- **Tier 2, interaction:** stairs, doors, movables and travel (`testqueue.py plan`), planned only for the cells whose
  every smoke test has a final PASS. A cell that fell through, crashed or was never read stays out of tier 2.

```
python scripts/game/inventory.py plan --staging <port staging> --out <dir> [--cells A,B | --batch interior-batches.json --batch-number N]
python scripts/game/testqueue.py run --queue <dir>\tier1 <the usual caps>
python scripts/game/inventory.py promote --inventory <dir> [--kinds stairs,door,movable,travel]
python scripts/game/testqueue.py run --queue <dir>\tier2 <the usual caps>
```

## Files

- `inventory.json`: the staging, the plugin's sha256 and build id, and every cell's state.
  - `smoke`, with its test ids.
  - `no_point`: probe_points.py found no floor.
  - `not_in_staging`: the cell was not exported.
- `tier1/queue.json`: the smoke queue.
- `promotion.json`: each cell `promoted` or `held`, with the reason (the first failing verdict, `not run`, or its tier 1
  state).
- `tier2/queue.json`: the interaction queue. A travel test is kept only when both of its cells were promoted.

Both queues carry the staging fingerprint (`staging_files`, every staged file's sha256). `testqueue.py run` stops
before every test, a live game included, when any staged file changed since the plan, not only `FO4Port.esm`. Files
are rehashed only when a size or mtime changed since the last match.

## Refusals

- `plan` refuses:
  - an existing `--out`;
  - a cell name that isn't a plain name;
  - a batch number not in the file;
  - a run where no cell gets a smoke test.
  It leaves nothing behind.
- `promote` refuses:
  - a staging whose `FO4Port.esm` changed since the plan (another build's ids);
  - a second tier 2;
  - unknown kinds;
  - a tier 1 with no passing cell. That case still writes `promotion.json` and no queue.
  A tier 2 plan that `testqueue.py plan` refuses (a missing `--bridge`, ...) leaves no `tier2/` behind.

For #396's interior batches, `--batch docs/terrain/data/interior-batches.json --batch-number N` takes that batch's own
cells from the batch staging. Smoke only needs `coc FO4Port_<Cell>`, so it doesn't wait for a wired core. The door
round trips do (`scripts/bridge/door_batch.py`, #397).
