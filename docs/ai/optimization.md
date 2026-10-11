# Optimization log

Ongoing (AGENTS.md "Keep optimizing"). Every entry: date, agent, what, **measured before / after** (same command,
same input), and the commit. Use the `optimization` label on the issue or PR.

## Baselines (measured 2026-10-09 on the owner's PC; Ryzen 9 7950X3D, RTX 4070 Ti 12 GB, 32 GB)

| What | Command | Measured | Source |
|---|---|---|---|
| Full conversion build, 15 cells / 4,014 models | `scripts/convert_batch.py --cell-json merged.json` (no `--resume`) | 311–373 s | Claude, journal 2026-10-09 |
| Plugin write, 15 cells | `dotnet/PluginSpike` | ~10 s (not timed precisely) | Claude |
| Unit tests (241) | `python -m unittest discover -s tests` | 2.4 s | Claude |
| Deploy + launch + load cell | `research/s1/cycle.ps1` | ~3 min | Claude |
| Parsons route run, 45 routes | `scripts/game/route_run.ps1` | ~2 min per door route (prompt search + console checks) | Claude, in progress |
| Door prompt search, 149 door routes / 9 runs | `scripts/game/prompt_rounds.py <run dirs>` | 2.50 screenshot+OCR rounds per door route, 2.07 s each (~5.2 s); 102.8 s per door route (Rexford r10 -> r11; library 2026-10-11: median 102.9 s over 28 consecutive door routes) | Claude, entry 2026-10-10 |
| Guardian status (one sample) | `guardian.py status` | 1.1 s | Claude |
| Remote usage report, 24 h | `remote_usage.py` | 2.7 s | Claude |
| Local model tokens per task | `guardian.py report` | no data yet (no model) | n/a |

## Candidates (not done; each needs a before/after)
- Build: `--resume` checkpoints (Codex) instead of full rebuilds when only a few models change. The last six
  Claude rebuilds were full (~6 min each) for changes touching 2–118 models.
- Route runs: the prompt search takes up to 9 screenshot+OCR rounds per door; start the tilt from the last
  successful pitch per cell. Implemented 2026-10-10 (`scripts/game/prompt_memory.py`, `route_run.ps1 -PitchMemory`,
  PR `claude/route-prompt-memory`); the "before" is measured (entry below: 2.50 rounds per door route, not 9), the
  "after" needs a live run.
- Route runs: the console typing is the larger cost. Rexford 2026-10-09: 102.8 s from one door route's first prompt
  shot to the next route's (`r10_pre.png` -> `r11_pre.png` creation times), of which 70.7 s lie between the end
  shot `r10.png` and `r11_pre.png`: console open, `prid` + `setopenstate 0`, five `player.setpos` / `setangle`
  commands, the camera levelling and three `getpos` reads, typed at 240 ms per key (`input.ps1` Tap: 160 ms down +
  80 ms up). The prompt search is 2.1-6.3 s of the 102.8 s. Candidates: shorter per-key waits, or `player.moveto` of
  a placed marker; both need a measured in-game check that the console still takes every key.
- Remote usage: Codex 102 M input tokens in 24 h, 96% cached; Claude 160 M cache reads; Grok 73 M input.
  Long single sessions dominate. Shorter sessions with handoff notes may cut cached-context cost; measure first.

## Entries

### 2026-10-10 Claude: route runner remembers the prompt pitch per cell (before measured, after pending)
Change: `scripts/game/prompt_memory.py` + `route_run.ps1 -PitchMemory`. The pitch (mouse counts below the top clamp)
at which `prompt_visible.py` saw the door prompt is saved per cell, door model and ref in `prompt_pitch.json` next
to the routes file. The next door route of that cell levels the camera straight to it and takes one shot; a miss
re-levels and runs the unchanged 9-round sweep, and a pitch that misses twice in a cell is dropped. With no memory
file, or `-PitchMemory off`, the input sequence is the old one exactly (same level sequence, 700 + 150 counts per
round, 9 rounds); the additions are two Python calls per door route (`get` before levelling, `hit` after a found
prompt) and three result fields (`prompt_rounds`, `prompt_pitch`, `pitch_source`). Not run in game yet.

Before (measured 2026-10-10/11 from the pinned-build run folders `staging\multi_next\run_*`, runs of 2026-10-09 to
11; `run_PrydwenHull01` has no door routes; rounds per door route = 1 + (last write - creation) of `r<k>_pre.png` /
2.07 s, the runner overwriting that file once per round; `python scripts/game/prompt_rounds.py <run dirs>`):

| Run | Door routes | Rounds | Rounds: routes | Never saw the prompt (9 rounds) |
|---|---|---|---|---|
| run_GoodneighborHotelRexford | 23 | 53 | 2: 18, 3: 3, 4: 2 | 0 |
| run_lib_1011 (2026-10-11) | 32 | 77 | 2: 24, 3: 5, 4: 2, 6: 1 | 0 |
| run_parsons | 32 | 84 | 2: 25, 3: 4, 4: 1, 9: 2 | 2 |
| run_parsons_doors2 | 25 | 61 | 2: 20, 3: 4, 9: 1 | 1 |
| run_parsons_doors3 | 2 | 6 | 2: 1, 4: 1 | 0 |
| run_parsons_doors4 | 5 | 12 | 2: 3, 3: 2 | 0 |
| run_v81_1010 | 6 | 12 | 2: 6 | 0 |
| run_Vault111Cryo | 2 | 4 | 2: 2 | 0 |
| run_Vault114 | 22 | 64 | 2: 14, 3: 6, 9: 2 | 2 |
| **Total** | **149** | **373** (2.50 per route) | 2: 113, 3: 24, 4: 6, 6: 1, 9: 5 | 5 |

- Seconds per round: 2.05-2.07 (the five full sweeps span 16.4-16.6 s for 8 tilts); a round is `shot.ps1` +
  `prompt_visible.py` + `input.ps1 move:0,150|wait:450`. The search is ~5.2 s per door route on average: 2.1 s at
  2 rounds, 6.3 s at 4, 10.4 s at 6 (one library door, `0FFCA5`), 16.5 s when nothing is found. A door route takes
  102.8 s (Rexford r10 -> r11 pre shots); the library run's 28 consecutive door routes are 102.0-146.7 s apart,
  median 102.9 s (`r<k>_pre.png` creation times).
- No door route saw the prompt at the levelled pitch (round 1); 76% (113/149) saw it one tilt lower (850 counts).
- Ceiling: the 184 rounds beyond the first (~381 s over 149 routes, 2.6 s per route) are all a memory can save if
  every remembered pitch hits. The 5 no-prompt sweeps stay at 9 rounds, plus one shot and a re-level after a miss.

After (plan; same command, same pinned build, same routes file; the game is not run from this branch):
1. `route_run.ps1 -Routes routes_<cell>.json -Out run_<cell>_a` with no `prompt_pitch.json` next to the routes
   file: the first door route sweeps as before and writes the memory; the later door routes of the run use it.
2. `route_run.ps1 ... -Out run_<cell>_b` for the same cell: every door route starts from memory.
3. `python scripts/game/prompt_rounds.py run_<cell>_a run_<cell>_b` against the before folder of the same cell:
   rounds per door route (now recorded in results.jsonl), `pitch_source` counts (memory / sweep / sweep-after-miss),
   `misses` in `prompt_pitch.json`, and the route period from the `_pre` creation times. `route_eval.py` verdicts
   must not change (a faster wrong E press is a regression).
   Expected if the pitch repeats as the before data suggests: 1 round per door route instead of 2.50, about 3 s less
   per door route (~3% of 102.8 s). If more than about one door route in five misses, the pitch is not reproducible
   enough and the memory should be removed rather than tuned.

### 2026-10-09 Claude: model load without memory mapping (local team)
Before: `lms load qwen3-14b --gpu max` -> LM Studio held 10.5 GB of system RAM for a model fully in VRAM; RAM 88.2%,
the guardian held every request (restrict/block). After: `tools/ai-team/load_model.py` (tryMmap=false,
keepModelInMemory=false) -> LM Studio 5.4 GB, RAM 71.4%, VRAM unchanged (10,890 -> 10,930 MiB). Requests admitted.

### 2026-10-09 Claude: 32K context at the cost of 16K (local team)
OpenCode's own system prompt + tools is ~12K tokens; at 16K context it compacted and re-continued in a loop.
Before: 16K, f16 KV cache, VRAM 10,952 MiB. After: 32K, q8_0 K/V cache + flash attention, VRAM 11,061 MiB (90.1%,
below the 92% restrict level with a resident model). Twice the context for +109 MiB.

### 2026-10-09 Claude: wake remote agents with a fresh session, not a fork
Before: `wake_agent.py` forked Codex's last session; one headless turn reported **5,677,999 tokens used** (the
whole long session history replayed) and, in the default read-only sandbox, could not fix or post anything.
After: default is a fresh session with a short brief pointing at #32 / handoff / AGENTS.md, with workspace-write +
network. `--fork` stays available when the old context is really needed. After (measured): the next fresh-session wake fixed the bug it was briefed on, ran the tests and the guard, and
opened PR #34 using **54,793 tokens** (99% less than the fork's 5,677,999).
