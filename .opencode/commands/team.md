---
description: "The team's status - guardian level, model, running requests, failures, warnings (OpenCode's own /status shows its config)"
agent: fo4-lead
---
Run `python tools/ai-team/team.py status` and `python tools/ai-team/models.py list`, then report in at most six short
lines: the guardian's level and mode (and why, if it is not normal), the picked model and whether LM Studio has it
loaded, a model swap that holds or failed, running and queued requests, recent failures, and warnings. Change nothing.
