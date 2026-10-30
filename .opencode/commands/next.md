---
description: Run one session of the Lead's procedure - pick one task and see it through, with the owner watching
agent: fo4-lead
---
Run ONE session of your operating procedure (your agent file and AGENTS.md). The owner is watching in this terminal.
$ARGUMENTS

Before you hand work to fo4-implement, say in two lines what you will hand over and wait for the owner's yes. In this
terminal, commit docs/ai edits with `python -I tools/ai-team/agent_git.py commit 'Lead (local): <what changed>' <files>`
(lead_commit.py is for the unattended Lead's own branch). Never push. If a command is refused, load the
fo4-allowed-commands skill.
