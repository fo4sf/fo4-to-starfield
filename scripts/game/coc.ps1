# Move the player to a converted cell with `coc` and VERIFY the arrival before anything else runs.
# usage: coc.ps1 -Cell Vault111Cryo -CellJson <staging>\Vault111Cryo.json [-Wait 30000]
# Exit 0: the player stands within 5 m of the cell's COC marker. Exit 1: not there (load failed or the jump didn't
# happen): route tests must not run, they would teleport to this cell's coordinates inside another cell and fall.
# Exit 2/3/4: the console could not be opened safely (console_open.ps1 codes); nothing was typed.
# -Bridge (the observation bridge is installed): the arrival is read from the bridge's log first, a fresh loaded line,
# with no console and no OCR; readpos's OCR only when no such line comes. v6e stairs 2026-10-21: on the 2560x1600
# display the HUD's O2/CO2 dial overlaps the console's last lines, the OCR read Z -1.81 as "81" and the nonce as
# "f04sfr2De589b8", and every arrival in BostonPublicLibrary02 failed although the player stood on the marker.
param([Parameter(Mandatory)][string]$Cell, [Parameter(Mandatory)][string]$CellJson, [int]$Wait = 30000, [switch]$Bridge)
$env:LEGACY = '1'
$i = Join-Path $PSScriptRoot 'input.ps1'
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'console_open.ps1') | Out-Null
if ($LASTEXITCODE -ne 0) { "console not opened safely (code $LASTEXITCODE)"; exit $LASTEXITCODE }
powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq "type:coc FO4Port_$Cell|key:enter|wait:400|key:grave|wait:$Wait" | Out-Null
$marker = (Get-Content $CellJson -Raw | ConvertFrom-Json).refs | Where-Object { $_.base_editor_id -eq 'COCMarkerHeading' } | Select-Object -First 1
if (-not $marker) { "no COC marker in ${CellJson}: arrival not verifiable"; exit 1 }
$mx = $marker.pos[0] / 70; $my = $marker.pos[1] / 70
if ($Bridge) {
  $py = if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }
  $cmd = @((Join-Path $PSScriptRoot 'bridge_log.py'), 'latest', '--max-age', '2')
  if ($env:FO4SF_BRIDGE_LOG) { $cmd += @('--log', $env:FO4SF_BRIDGE_LOG) }
  for ($n = 0; $n -lt 12; $n++) {                    # about 8 s: the game resumes writing a few seconds after the console
    $j = $null
    try { $j = (& $py @cmd) | ConvertFrom-Json } catch { $j = $null }
    if ($j -and $j.ok -and $j.loaded -eq $true -and @($j.pos).Count -eq 3) {
      $d = [Math]::Sqrt([Math]::Pow([double]$j.pos[0] - $mx, 2) + [Math]::Pow([double]$j.pos[1] - $my, 2))
      if ($d -le 5) { "at FO4Port_$Cell (bridge line $($j.n) rt $($j.rt): $(@($j.pos) -join ' '), {0:N1} m from the COC marker)" -f $d; exit 0 }
    }
    Start-Sleep -Milliseconds 700
  }
  "no fresh bridge line within 5 m of the COC marker: reading with the console"
}
# up to 3 reads: OCR sometimes shifts a column ("0.00 29.26 60.11" for "29.26 60.11 ...") and a single read then
# looked like a failed jump (Vault 81 and the library were skipped although the player had arrived)
$d = 1e9
for ($n = 0; $n -lt 3 -and $d -gt 5; $n++) {
  $p = powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'readpos.ps1')
  if ("$p" -like 'fail console*') { "console not opened safely: $p"; exit 2 }
  $v = "$p".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
  try { $d = [Math]::Sqrt([Math]::Pow([double]$v[0] - $mx, 2) + [Math]::Pow([double]$v[1] - $my, 2)) } catch { $d = 1e9 }
}
if ($d -gt 5) { "not at FO4Port_$Cell (last read $p, marker {0:N2} {1:N2})" -f $mx, $my; exit 1 }
"at FO4Port_$Cell (read $p, {0:N1} m from the COC marker)" -f $d
exit 0
