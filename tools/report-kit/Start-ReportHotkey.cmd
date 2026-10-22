@echo off
rem FO4SF report hotkey for players: Ctrl+Alt+L = screenshot, Ctrl+Alt+K = screenshot and a box to describe the problem.
rem Each capture opens the filled-in Player report form; paste the screenshot (Ctrl+V) and press Submit.
rem Captures are also kept in Documents\FO4SF Reports. Close this window to stop. Guide: docs\community\reporting-tool.md
if not defined FO4SF_SNAPSHOT_ROOT set "FO4SF_SNAPSHOT_ROOT=%USERPROFILE%\Documents\FO4SF Reports"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\scripts\game\look_hotkey.ps1" -Submit %*
