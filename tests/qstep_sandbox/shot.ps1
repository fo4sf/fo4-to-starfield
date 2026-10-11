# SANDBOX ONLY: writes a placeholder file instead of a screenshot.
param([string]$Out)
[IO.File]::WriteAllBytes($Out, [byte[]](137, 80, 78, 71)); "saved (sandbox)"
