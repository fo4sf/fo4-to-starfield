# SANDBOX ONLY: writes a placeholder file instead of a screen capture.
param([string]$Out, [double]$FX = 0, [double]$FY = 0, [double]$FW = 0, [double]$FH = 0)
[IO.File]::WriteAllBytes($Out, [byte[]](137, 80, 78, 71)); "saved (sandbox)"
