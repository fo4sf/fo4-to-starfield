---
description: "Run one session of the Lead's procedure - pick one task and see it through, with the owner watching"
agent: fo4-lead
---
Run ONE session of your operating procedure (your agent file and AGENTS.md). The owner is watching in this terminal.
$ARGUMENTS

Before you hand work to fo4-implement, say in two lines what you will hand over and wait for the owner's yes. This
terminal starts on main with no branch. Commits here are the coding agent's (the owner's choice): fo4-implement makes
the task's branch with `python -I tools/ai-team/agent_git.py branch ai/<issue>-<short-name>` (it starts from main), then
commits with `python -I tools/ai-team/agent_git.py commit 'Implement (local): <what changed>' <files>`. When the
terminal reopens it is back on main: the same `branch` command with the task's branch name switches back to it. Leave
your own docs/ai edits uncommitted unless the owner says to commit them: OpenCode then asks the owner to approve each
agent_git.py command you run, with a message that starts `Lead (local): ` (lead_commit.py is for the unattended Lead's
own branch). OpenCode also asks the owner before each test run, since a test can run any code: answer those with
Allow once, as Allow always stops the asking for the rest of the session. Never push. If a command
is refused, load the fo4-allowed-commands skill.
