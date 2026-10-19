# The elevated test run (proposal, for review; nothing is registered)

Claude-cloud (bridge thread), 2026-10-19. Labels: **verified**, **supported**, **unresolved**.

## Why
- **Verified.** The night run's `steam://` launch at 07:46Z failed with Steam's dialog "Starfield failed to start
  (error code 84)". #377's crash budget stopped the run after that one dead start.
- **Unresolved: what error 84 is.** On the PC (the install thread, 2026-10-19 14:30Z), Starfield.exe has no
  RUNASADMIN compatibility flag in HKCU or HKLM, and Steam has run non-elevated since Oct 17. So the owner's
  "run as admin" habit may not be what makes their launches work. The Steam, runner and event logs from 07:46Z are
  being read first. A launch route that needs no elevation is preferred over this task.
- **Supported.** If the game does have to run elevated, the runner has to run elevated too. Windows drops input sent
  to a higher integrity level (UIPI), and the runner drives the game with SendInput.

## What the task is
`scripts/game/admin_task/make_task.py` writes `FO4SF\ElevatedRun` as Task Scheduler XML. The task:
- has no trigger: it starts only when someone runs `schtasks /run /tn "FO4SF\ElevatedRun"`;
- runs only while the owner is logged on (an interactive token), with their highest privileges, one instance at a
  time, for at most 8 hours;
- has one fixed action: `<python> scripts\game\campaign_arm.py run --campaign <campaign.json>` in a fixed checkout.

`campaign_arm.py run` does this:
1. Checks the campaign first. It refuses caps other than one launch, a stop at the first crash or dead start, and
   at least 40 GB free on the dump drive. It also refuses a queue that would install anything but the installed set,
   and a held cell such as the Red Rocket arrival, unless the campaign's `released` list names it.
2. Runs each queue with those caps, then its judge and the gate.
3. Stops at the first queue that is not clean.

Its `launch` field ("steam" by default, or "exe") becomes `FO4SF_LAUNCH` for cycle.ps1. With "exe", cycle.ps1 starts
Starfield.exe directly, so the game inherits the task's elevation. Every step goes to `<campaign>.run.log`.

## The owner's steps (only after Codex's review)
```
python scripts\game\admin_task\make_task.py --user <whoami> --checkout <runner checkout> --python <venv python.exe> --campaign <campaign.json> --out <task.xml>
schtasks /create /tn "FO4SF\ElevatedRun" /xml <task.xml>      (in an admin prompt: the one approval)
schtasks /run /tn "FO4SF\ElevatedRun"                         (each run)
schtasks /delete /tn "FO4SF\ElevatedRun" /f                   (to remove it)
```

## Limits
- The checkout and the campaign file can be changed without elevation, and the task runs whatever they hold. On a
  one-user PC that is the same trust as the owner's own shell. The campaign check runs inside the task, so a changed
  campaign is checked again. Changed code is not checked: run the task only from a reviewed commit.
- It doesn't put FO4Port back first in the owner's load order. That stays the install thread's step after a run.
