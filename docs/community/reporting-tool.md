# Reporting problems (players and testers)

Found something wrong while playing the Fallout 4 to Starfield port? Thank you. This page explains the report hotkey the
project owner uses himself, and where reports go.

## How reports are handled

1. Open a **Player report** from the repository's **Issues → New issue** page (the form labels it `community` and
   `needs-triage`).
2. The owner reviews it. Until `needs-triage` is removed, no AI agent or contributor treats it as a task, so a report
   cannot redirect the work on its own (AGENTS.md, "Community reports").
3. After review it is either turned into a normal task (`ready`), merged into an existing issue, or closed with a reason.

## The report hotkey (Windows)

Two PowerShell scripts in `scripts/game/` take a screenshot of your whole screen and save it with what the game reports
about where you are. They type nothing into the game and send nothing anywhere: you decide what to attach.

**Start it:** download the repository (Code → Download ZIP), unzip it, and double-click
`tools/report-kit/Start-ReportHotkey.cmd`. Keep its window open while you play (minimise it; close it to stop).

| Keys | What it does |
|------|--------------|
| **Ctrl+Alt+L** | Screenshot only (a short beep). |
| **Ctrl+Alt+K** | Screenshot, then a box asks *what is wrong?* Type it and press **Save**, or **Screenshot only** to skip. |

**Want every Ctrl+Alt+L to ask too?** Run once (from the unzipped folder):

```
powershell -ExecutionPolicy Bypass -File scripts\game\look_hotkey.ps1 -SetAsk on
```

`-SetAsk off` switches it back to screenshots only. It takes effect on the next press, no restart. Other keys:
`Start-ReportHotkey.cmd -Key F13 -AskKey F14 -Mods none` (F13 to F24 suit a macro key on a gaming keyboard).

**What you get**, one folder per press in `Documents\FO4SF Reports\<date-time>\`:

- `screen.png`: the screenshot (taken before the box opens, so the box is never in it).
- `description.txt`: what you typed, if anything.
- `state.json`: time, whether the game was running, your position and cell (only when the port's `FO4SFBridge.esm` is
  active), and your active plugin list.
- `papyrus_tail.txt`: the last lines of the game's script log, if script logging is on.

Attach `screen.png` to the report and paste `description.txt` and the useful parts of `state.json`. **Read
`state.json` first**: it can contain folder paths with your Windows user name; delete those lines.

**If the box does not appear over the game**, switch Starfield to borderless/windowed (exclusive fullscreen can hide
other windows), or press Alt+Tab once.

Position and cell need Python (the scripts look for `FO4SF_PYTHON`, else skip that part); the screenshot and the box
need nothing beyond Windows PowerShell.

## For the owner

Your PC copy lives in `C:\Modding\tools\look\` and also listens for F13; compare it with the new `look_hotkey.ps1`
and `snapshot.ps1` before copying them over, then restart the hotkey. Captures still go to `C:\Modding\snapshots`, and `description.txt` / `state.json`'s `description` carry your
text for the session that watches that folder.
