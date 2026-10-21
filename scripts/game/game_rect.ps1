# Get-GameRect: where Starfield's 16:9 picture sits in a screen capture (dot-source; game_frame.py is the same rule).
# On a display that is not 16:9 the game draws its 16:9 picture centred between black bars: the v6e doors retry
# (2026-10-21, a 2560x1600 desktop) captured 1280x800 frames with bars top and bottom, and every check written for
# shot.ps1's 1280x720 output missed (main menu, save loaded, HUD). The centred 16:9 rectangle when the parts outside it
# are black (no sample above 12), else the whole capture (a 16:9 screen, or a game drawn over a whole 16:10 screen).
function Get-GameRect([System.Drawing.Bitmap]$bmp) {
  $w = $bmp.Width; $h = $bmp.Height
  $full = New-Object System.Drawing.Rectangle 0, 0, $w, $h
  if ([math]::Abs($w * 9 - $h * 16) -le $w * 9 * 0.01) { return $full }
  if ($w * 9 -lt $h * 16) {
    $ch = [int][math]::Round($w * 9 / 16.0); $top = [int][math]::Floor(($h - $ch) / 2)
    $rect = New-Object System.Drawing.Rectangle 0, $top, $w, $ch
    $bars = @(@(0, 0, $w, $top), @(0, ($top + $ch), $w, $h))
  } else {
    $cw = [int][math]::Round($h * 16 / 9.0); $left = [int][math]::Floor(($w - $cw) / 2)
    $rect = New-Object System.Drawing.Rectangle $left, 0, $cw, $h
    $bars = @(@(0, 0, $left, $h), @(($left + $cw), 0, $w, $h))
  }
  foreach ($bar in $bars) {
    if ($bar[2] -le $bar[0] -or $bar[3] -le $bar[1]) { return $full }
    $sx = [math]::Max(1, [int](($bar[2] - $bar[0]) / 64)); $sy = [math]::Max(1, [int](($bar[3] - $bar[1]) / 16))
    for ($y = $bar[1]; $y -lt $bar[3]; $y += $sy) {
      for ($x = $bar[0]; $x -lt $bar[2]; $x += $sx) {
        $c = $bmp.GetPixel($x, $y)
        if ((0.299 * $c.R + 0.587 * $c.G + 0.114 * $c.B) -gt 12) { return $full }
      }
    }
  }
  return $rect
}
