---
description: "Adversarial QA review of a pull request - give its number"
agent: fo4-qa
subtask: true
---
Review pull request $1 adversarially, following your agent file. Read it with `gh pr view $1`, `gh pr diff $1` and
`gh pr checks $1` (CI's results on the PR's own code). This checkout is main, not the PR, so a test run here says
nothing about the PR: judge the diff by reading it, and name the claims only CI or a run on the PR's branch can settle.
Report each finding with its severity (high, medium or low), the file and line, and the input or state that makes it
fail. You do not edit files and you do not post on GitHub.
