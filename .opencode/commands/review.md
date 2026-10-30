---
description: Adversarial QA review of a pull request - give its number
agent: fo4-qa
subtask: true
---
Review pull request $1 adversarially, following your agent file. Read it with `gh pr view $1` and `gh pr diff $1`, run
`python -m unittest discover -s tests` and `python scripts/guard.py`, and report each finding with its severity (high,
medium or low), the file and line, and the input or state that makes it fail. Say which claims you could not check.
You do not edit files and you do not post on GitHub.
