---
description: "Hand work to Claude - posts a short handoff on issue 32 that Claude reads"
agent: fo4-lead
---
Hand this to Claude: $ARGUMENTS

Post ONE comment on #32, at most 1200 characters, in this shape:
`gh issue comment 32 --body 'Lead (local): for Claude: <what the owner asked>. Done: <what the team did, with branch and
commit ids from git log --oneline -5>. Open: <what is left>. Next for Claude: <the one thing to do>.'`
One line of plain text, with no quote marks, apostrophes, dollar signs, backslashes, exclamation marks, backticks,
ampersands, pipes, carets, percent signs or angle brackets (the guard refuses those, and > anywhere in a command). Only
this terminal can post a comment that starts `Lead (local): for Claude:`. Change nothing else.
