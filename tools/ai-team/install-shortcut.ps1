# Make the "FO4SF AI" desktop shortcut, which opens menu.ps1. Run it once; running it again replaces the shortcut.
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\ai-team\install-shortcut.ps1
# It writes only the shortcut file on the desktop. Delete the shortcut to remove it.
$menu = Join-Path $PSScriptRoot 'menu.ps1'
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'FO4SF AI.lnk'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$menu`""
$shortcut.WorkingDirectory = Split-Path (Split-Path $PSScriptRoot)
$shortcut.Description = 'FO4SF AI: the local team, its terminal, Claude Code, status, model, stop'
$shortcut.Save()
"made $lnk"
