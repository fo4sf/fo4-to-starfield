# What changed between two builds (scripts/game/regress.py)

Claude-cloud (bridge thread), 2026-10-19. This is T-regress from the next-phase testing note: once tests number in the
thousands, the most useful report after a new build is the list of things that passed before and fail now.

```
python scripts/game/regress.py --old <queues of the old build> --new <queues of the new build> [--out report.json]
```

## How tests are matched
- Tests are matched by what they check, not by test number, so a re-planned queue still lines up.
- Door round legs are keyed by interior cell, leg and FO4 door. Terrain tests are keyed by their coc, side and label,
  since several walks can start from one coc. Every other test is keyed by kind, cell, ref and side, so a door's two
  sides are two matches.
- Two tests of one queue with the same key can not be told apart: the tool refuses (exit 2) rather than keep one.
- A door queue's `door_rounds_judge.json` replaces the runner's own verdicts for that queue.

## How each match is classed
| Class | Meaning |
|---|---|
| regressed | PASS before, FAIL now |
| lost | PASS before, but INCONCLUSIVE or not run now: the proof is gone, but nothing shows the test broke |
| new_failure | INCONCLUSIVE or not run before, FAIL now |
| fixed | not PASS before, PASS now |
| still_failing | FAIL both times |
| changed | any other change of verdict, such as FAIL to INCONCLUSIVE |
| unchanged | the same verdict |
| new | only in the new build's results |
| gone | only in the old build's results |

Every class but unchanged, new and gone is printed line by line. The tool exits 1 when anything regressed, was lost
or newly failed, so a chain can stop on it. It exits 2, writing no report, when a queue cannot be read as evidence: a
key repeated inside one queue, a missing or torn `queue.json`, an unreadable `door_rounds_judge.json`, or a
door rounds queue that has not been judged yet, known by its tests' "door round N IN/OUT" labels even when its stage folder
has moved (run `scripts/bridge/door_rounds.py judge --queue <queue>` first).

## Limits
- The verdicts are only as good as each test's own judge.
- Keys from hand-planned queues whose refs are labels with ids in them, such as old terrain hops, change when the ids
  change. Those tests show up as gone and new rather than matched.
- Generated queues (door_rounds, presence) carry stable keys.
