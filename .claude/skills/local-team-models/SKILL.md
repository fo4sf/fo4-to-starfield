---
name: local-team-models
description: Check or switch the model the fo4 local AI team runs on (the LM Studio presets, or any downloaded model) with tools/ai-team/models.py - on the owner's PC only, never during a running request, and only when the owner asked.
---
# Switch the local team's model

On the owner's PC (Claude Code in the repo), and only when the owner asked: a load takes GPU memory and RAM that the
game needs too.

```
python tools/ai-team/models.py list
python tools/ai-team/models.py pick qwen3.6-35b
python tools/ai-team/models.py pick qwen3.6-35b-128k
python tools/ai-team/models.py pick qwen3-14b
python tools/ai-team/models.py pick --model <an id from list> --context 32768
```

- `pick` refuses while requests run or wait (`python tools/ai-team/guardian/guardian.py status`). It pauses the
  guardian during the load, unloads the team's other models (a model the owner loaded for something else stays),
  loads the new one, saves the pick and resumes.
- The proxy sends every agent to the pick at once. A terminal or Lead session opened before the switch keeps the old
  window and output limits until it is reopened: terminal.ps1 and run-lead.ps1 pass the pick's limits at start.
- The presets and their measured RAM and VRAM are in tools/ai-team/config.json under "models". The 128K window held
  requests at 87-91% RAM. A new preset goes into config.json with its measurements, by PR.
- A model outside the presets must call tools (OpenCode needs tool calls), and its output limit stays at or below
  half its context; `pick` checks the numbers, not the model.
- While Starfield or Fallout 4 runs, the guardian blocks inference; free the GPU for a game test only when the owner
  asks (stop-team.ps1 says how).
