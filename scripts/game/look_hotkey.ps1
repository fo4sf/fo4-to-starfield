# look_hotkey.ps1 (Claude, 2026-10-16): the owner's "look" button. Registers one global hotkey (default Ctrl+Alt+L; map a
# spare key of the keyboard to it in the keyboard's own software, e.g. a Womier macro key) and on every press runs
# snapshot.ps1 in the background (a screenshot, the bridge's position and cell, the Papyrus tail; nothing is typed into the
# game) and beeps once. Claude's session watches C:\Modding\snapshots and answers each new snapshot.
# docs/owner/in-game-test-sheet.md section 7.
# usage: look_hotkey.ps1 [-Key L] [-Mods Ctrl,Alt] [-TestFire]
#   -Key   a letter, digit or F1..F24 (F13..F24 suit a macro key: no keyboard has them, so nothing else uses them)
#   -Mods  any of Ctrl, Alt, Shift, Win (comma-separated), or none (fine for an F13..F24 key)
#   -TestFire  run the press handler once and exit (the test; no hotkey registered)
param([string]$Key = 'L', [string[]]$Mods = @('Ctrl', 'Alt'), [switch]$TestFire)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$snapshot = Join-Path $here 'snapshot.ps1'
function Press {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  Start-Process powershell -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $snapshot, '-Note', 'hotkey') | Out-Null
  try { [console]::Beep(880, 120) } catch { }
  "pressed $stamp"
}
if ($TestFire) { Press; exit 0 }
$modBits = 0
foreach ($m in ($Mods -join ',').Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -ne 'none' }) {
  switch -Regex ($m) { '^(?i)alt$' { $modBits = $modBits -bor 1 } '^(?i)ctrl$' { $modBits = $modBits -bor 2 } '^(?i)shift$' { $modBits = $modBits -bor 4 } '^(?i)win$' { $modBits = $modBits -bor 8 } default { throw "unknown modifier $m" } }
}
if ($Key -match '^(?i)F([1-9]|1[0-9]|2[0-4])$') { $vk = 0x6F + [int]$Matches[1] }        # F1 = 0x70 .. F24 = 0x87
elseif ($Key -match '^[A-Za-z0-9]$') { $vk = [int][char]$Key.ToUpper() }
else { throw "unsupported key $Key" }
Add-Type -ReferencedAssemblies System.Windows.Forms -TypeDefinition @'
using System; using System.Runtime.InteropServices; using System.Windows.Forms;
public class LookHotKey : NativeWindow {
  [DllImport("user32.dll")] static extern bool RegisterHotKey(IntPtr h, int id, uint mods, uint vk);
  [DllImport("user32.dll")] static extern bool UnregisterHotKey(IntPtr h, int id);
  public event EventHandler Pressed;
  public LookHotKey(uint mods, uint vk) {
    CreateHandle(new CreateParams());
    if (!RegisterHotKey(Handle, 1, mods | 0x4000, vk)) throw new InvalidOperationException("RegisterHotKey failed: the combination is taken by another program");
  }
  protected override void WndProc(ref Message m) {
    if (m.Msg == 0x0312) { var p = Pressed; if (p != null) p(this, EventArgs.Empty); }
    base.WndProc(ref m);
  }
  public void Release() { UnregisterHotKey(Handle, 1); DestroyHandle(); }
}
'@
$hk = New-Object LookHotKey ([uint32]$modBits), ([uint32]$vk)
$hk.add_Pressed({ Press | Out-Null })
"look hotkey ready: $($Mods -join '+')+$Key (pid $PID)"
try { [System.Windows.Forms.Application]::Run() } finally { $hk.Release() }
