---
name: local-team-models
description: "Check or switch the model the fo4 local AI team runs on (the LM Studio presets, or any downloaded model) with tools/ai-team/models.py - on the owner's PC only, never during a running request, and only when the owner asked."
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

- `pick` refuses while a request runs or another load is under way (`python tools/ai-team/guardian/guardian.py
  status`). It holds the guardian's proxy during the load (new requests wait, then go to the new model), unloads the
  team's other models and the last pick (a model the owner loaded for something else stays), loads the new one and
  saves the pick. The owner's pause and stop are left as they are.
- A load that fails leaves the hold as "failed" (`model_hold` in the status): the proxy refuses requests until a load
  works, so run `python tools/ai-team/models.py ensure` or pick another model, and tell the owner what failed.
- The proxy sends every agent to the pick at once. A terminal or Lead session opened before the switch keeps the old
  window and output limits until it is reopened: terminal.ps1 and run-lead.ps1 pass the pick's limits at start.
- The presets and their measured RAM and VRAM are in tools/ai-team/config.json under "models". The 128K window held
  requests at 87-91% RAM. A new preset goes into config.json with its measurements, by PR.
- A model outside the presets must call tools (OpenCode needs tool calls), and its output limit stays at or below
  half its context; `pick` checks the numbers, not the model.
- While Starfield or Fallout 4 runs, the guardian blocks inference; free the GPU for a game test only when the owner
  asks (stop-team.ps1 says how).
