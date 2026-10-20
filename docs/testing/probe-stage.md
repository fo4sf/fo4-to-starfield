# Reading a quest's stage through the bridge (design, T-probe-stage)

Claude-cloud, 2026-10-19. Task T-probe-stage in `research/next-phase/testing-automation.md` 2.5.

**Status: proposal.** The log parser's half is in this PR (`bridge_log.parse_probe`, tests in
`tests/test_bridge_log.py` StageLineTests). The Papyrus below is **not** in `scripts/bridge/` yet. `make_bridge.py`
compiles every `.psc` there, so an uncompiled function would break the next bridge build. It moves there after one
compile on the PC.

## Why

Tier 3 (scenario) tests need to know where a quest stands:
- the new-game start (#393: MQ101 in FO4SFNewGame.esm);
- the cut-down When Freedom Calls (#353).

Typed `GetStage` output would have to be read by OCR. It would also need a new console whitelist entry, which is the
owner's decision (testing-automation.md 2.5). A cgf global in FO4SF_Probe answers in the bridge's own log, like
Resolve does today, so the runner reads it the way it reads positions. It uses the existing `cgf` syntax, but
both console allowlists list each FO4SF_Probe function by name, and neither lists `Stage` today
(**verified**: `console_plan.allowed` in scripts/game/console_plan.py and `$consoleOk` in scripts/game/qstep.ps1
accept the `Resolve` call and refuse the `Stage` call below). So `Stage` needs its own entry in both lists, on the
owner's word (step 5).

## The function (proposed, for FO4SF_Probe.psc)

```papyrus
Function Stage(string plugin, int id) global
    {Where the quest with this plugin-local form id stands: its current stage, running and completed.}
    Form f = Game.GetFormFromFile(id, plugin)
    string line = "FO4SF stage plugin=" + plugin + " id=" + id
    if f == None
        Debug.TraceUser("fo4sf", line + " form=none")
        return
    endif
    line += " form=" + f.GetFormID()
    Quest q = f as Quest
    if q == None
        Debug.TraceUser("fo4sf", line + " quest=false")
        return
    endif
    line += " quest=true stage=" + q.GetStage() + " running=" + q.IsRunning() + " completed=" + q.IsCompleted()
    Debug.TraceUser("fo4sf", line + " name=" + EditorId(q))
EndFunction
```

The call is `cgf "FO4SF_Probe.Stage" "FO4SFNewGame.esm" 2049`, with the plugin-local id in decimal. It has the same
shape as `Resolve`.

The line:
```
FO4SF stage plugin=FO4SFNewGame.esm id=2049 form=16779265 quest=true stage=10 running=true completed=false name=MQ101
```

`name` comes last because GetFormEditorID is DebugOnly (the same reason as Where()).

## What is known about each call

| Call | Status | Evidence |
|---|---|---|
| `Game.GetFormFromFile(id, plugin)` | **supported** | FO4SF_Probe.Lookup and scripts/door_bridge/FO4SF_LoadDoor.psc compile with it |
| `Quest.GetStage()` | **supported** | scripts/mission/FO4SF_Min00Quest.psc uses it; that mission compiled and passed in game on v6 |
| `Quest.IsRunning()`, `Quest.IsCompleted()` | **unresolved** | Fallout 4's Quest.psc has both. Starfield's Quest.psc is in ContentResources.zip on the PC and hasn't been read. If either is missing, drop it from the line; the parser treats every field as optional |
| `Quest` in make_bridge.IMPORTS | **verified** | scripts/bridge/make_bridge.py IMPORTS already lists Quest |

## Steps to make it real (each one small)

1. **PC, read-only:** list `Scripts/Source/Quest.psc`'s functions from ContentResources.zip
   (`findstr /i "Function" Quest.psc` on the extracted copy), to settle the unresolved row.
2. **Cloud:** move the function into FO4SF_Probe.psc. Add `Stage` to make_bridge's README line and to
   bridge_log's docstring. Extend `test_make_bridge`'s IMPORTS check.
3. **PC:** `make_bridge.py stage` into a new folder. That compiles it but installs nothing. Bridge restaging changes the
   bridge sha pins, so queues planned against the old bridge need replanning.
4. **Game, on the owner's word:** one call on a known quest (MQ101 after a new game, or the mission quest) and compare
   the stage with the quest's own trace lines.

5. **Cloud, on the owner's word:** add exactly one `Stage` signature to both allowlists, shaped like `Resolve`'s:
   `cgf "FO4SF_Probe\.Stage" "<plugin>\.es[mpl]" \d{1,8}` in `console_plan.PATTERN` and in qstep.ps1's
   `$consoleOk`, with tests that the Stage call passes and that no other new FO4SF_Probe call does. No wildcard.

Only then a `quest_stage` test kind: travel to a trigger, wait, `cgf` Stage, and PASS when `stage` reaches the
planned value within the timeout.
