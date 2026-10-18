# look_hotkey.ps1 (Claude, 2026-10-16): the owner's "look" button. Registers one global hotkey (default Ctrl+Alt+L; map a
# spare key of the keyboard to it in the keyboard's own software, e.g. a Womier macro key) and on every press runs
# snapshot.ps1 in the background (a screenshot, the bridge's position and cell, the Papyrus tail; nothing is typed into the
# game) and beeps once. Claude's session watches C:\Modding\snapshots and answers each new snapshot.
# docs/owner/in-game-test-sheet.md section 7.
# The description box (2026-10-18): a second hotkey (default Ctrl+Alt+K) always asks "what is wrong?" after the screenshot;
# the main key asks too only while the setting is on (look.settings.json beside this script, {"ask": true}), switched with
# -SetAsk on|off, read at every press (no restart). Off = screenshots only. docs/community/reporting-tool.md.
# usage: look_hotkey.ps1 [-Key L] [-AskKey K] [-Mods Ctrl,Alt] [-TestFire] [-TestAsk] [-SetAsk on|off]
#   -Key   a letter, digit or F1..F24 (F13..F24 suit a macro key: no keyboard has them, so nothing else uses them)
#   -Mods  any of Ctrl, Alt, Shift, Win (comma-separated), or none (fine for an F13..F24 key)
#   -AskKey  the key that always asks for a description ('none' = no second hotkey)
#   -TestFire  run the press handler once and exit (the test; no hotkey registered); -TestAsk: the ask key's handler
#   -SetAsk  on|off: whether the main key also asks; writes the setting and exits
param([string]$Key = 'L', [string]$AskKey = 'K', [string[]]$Mods = @('Ctrl', 'Alt'), [switch]$TestFire, [switch]$TestAsk,
      [ValidateSet('', 'on', 'off')][string]$SetAsk = '')
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$snapshot = Join-Path $here 'snapshot.ps1'
$settings = $(if ($env:FO4SF_LOOK_SETTINGS) { $env:FO4SF_LOOK_SETTINGS } else { Join-Path $here 'look.settings.json' })   # tests: a temp file
function AskSetting {
  try { return [bool]((Get-Content -LiteralPath $settings -Raw | ConvertFrom-Json).ask) } catch { return $false }
}
if ($SetAsk) {
  @{ ask = ($SetAsk -eq 'on') } | ConvertTo-Json | Set-Content -LiteralPath $settings -Encoding utf8
  "description box on the main key: $SetAsk ($settings)"; exit 0
}
function Press([bool]$ask) {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $snapshot, '-Note', 'hotkey')
  if ($ask) { $a += '-Ask' }
  Start-Process powershell -WindowStyle Hidden -ArgumentList $a | Out-Null   # the box is its own top-most window
  try { [console]::Beep(880, 120) } catch { }
  "pressed $stamp ask=$ask"
}
if ($TestFire) { Press (AskSetting); exit 0 }
if ($TestAsk) { Press $true; exit 0 }
$modBits = 0
foreach ($m in ($Mods -join ',').Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -ne 'none' }) {
  switch -Regex ($m) { '^(?i)alt$' { $modBits = $modBits -bor 1 } '^(?i)ctrl$' { $modBits = $modBits -bor 2 } '^(?i)shift$' { $modBits = $modBits -bor 4 } '^(?i)win$' { $modBits = $modBits -bor 8 } default { throw "unknown modifier $m" } }
}
function VirtualKey([string]$k) {
  if ($k -match '^(?i)F([1-9]|1[0-9]|2[0-4])$') { return 0x6F + [int]$Matches[1] }     # F1 = 0x70 .. F24 = 0x87
  if ($k -match '^[A-Za-z0-9]$') { return [int][char]$k.ToUpper() }
  throw "unsupported key $k"
}
$vk = VirtualKey $Key
$askVk = $(if ($AskKey -and $AskKey -ne 'none') { VirtualKey $AskKey } else { 0 })
Add-Type -ReferencedAssemblies System.Windows.Forms -TypeDefinition @'
using System; using System.Runtime.InteropServices; using System.Windows.Forms;
public class LookHotKey : NativeWindow {
  [DllImport("user32.dll")] static extern bool RegisterHotKey(IntPtr h, int id, uint mods, uint vk);
  [DllImport("user32.dll")] static extern bool UnregisterHotKey(IntPtr h, int id);
  public event EventHandler Pressed, AskPressed;
  public LookHotKey(uint mods, uint vk, uint askVk) {
    CreateHandle(new CreateParams());
    if (!RegisterHotKey(Handle, 1, mods | 0x4000, vk)) throw new InvalidOperationException("RegisterHotKey failed: the combination is taken by another program");
    if (askVk != 0 && !RegisterHotKey(Handle, 2, mods | 0x4000, askVk)) throw new InvalidOperationException("RegisterHotKey failed for the ask key: the combination is taken by another program");
  }
  protected override void WndProc(ref Message m) {
    if (m.Msg == 0x0312) { var p = ((int)m.WParam == 2) ? AskPressed : Pressed; if (p != null) p(this, EventArgs.Empty); }
    base.WndProc(ref m);
  }
  public void Release() { UnregisterHotKey(Handle, 1); UnregisterHotKey(Handle, 2); DestroyHandle(); }
}
'@
$hk = New-Object LookHotKey ([uint32]$modBits), ([uint32]$vk), ([uint32]$askVk)
$hk.add_Pressed({ Press (AskSetting) | Out-Null })
$hk.add_AskPressed({ Press $true | Out-Null })
"look hotkey ready: $($Mods -join '+')+$Key (description box $(if (AskSetting) { 'on' } else { 'off' }))$(if ($askVk) { ", $($Mods -join '+')+$AskKey always asks" }) (pid $PID)"
try { [System.Windows.Forms.Application]::Run() } finally { $hk.Release() }
