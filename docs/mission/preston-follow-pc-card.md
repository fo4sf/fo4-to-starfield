# Preston follows — PC session

Courier. First companion slice: Preston leaves the museum door and comes with the player. Run this only after a
mission stage built from the reviewed head is on the owner's game, game closed for that install. Until
`FO4SF_COMPreston.pex` is in that stage, he stays at the door. This card does not install anything and does not
launch the game by itself.

Script logging on, the same way the mission log is already read. No affinity check. No host follower quest.

## Not this session

- A restrained or essential hold at the museum door is the old result, and it is a fail here.
- Wait, trade and dismiss are later slices. Do not judge them.
- The Concord talk is not required. The command below is test-only and stands in for that talk.
- Offline tests do not show him walking.

## 1. Before the command

Load a save where Preston is at the museum door and held. Walk a few metres. He should stay. If he already follows,
say so and stop. That is not this slice's before-state.

## 2. The command

One console line:

    cgf "FO4SF_COMPreston.FollowTest"

The mission log should then contain, in order:

- `follow preston armed by=mission`
- `follow preston armed by=keeper` (absent only if that install has no keeper quest; say which lines appeared)
- `follow preston test-only` with `filled=1`, `linked=player` and `released=True`
- about two seconds later, `follow preston package=` and a number

`refused` instead of `test-only` is a fail. Record the package number. The low six hex digits `0301C5` mean the
host follow package. Walking is still the pass, even if the number differs. Write the number either way.

## 3. Walk

Outdoors, walk more than 20 m away from the museum door and stop. He should leave the door and close the gap.
Then read the log. Any `hold preston` line after the `test-only` line is a fail: the door hold came back.

Standing near him can still finish the mission. That rule is unchanged and is not the follow result.

## Verdict

- PASS: he leaves the door and stays with the player, the test-only line has `filled=1 linked=player released=True`,
  and no `hold preston` line follows it.
- FAIL: he stays at the door, the command logs `refused`, or a hold line returns.
- NOT_RUN: the stage with `FO4SF_COMPreston.pex` is not on the game yet.
