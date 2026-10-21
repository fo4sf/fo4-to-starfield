# Get-GameRect: where Starfield's 16:9 picture sits in a screen capture (dot-source; game_frame.py is the same rule).
# On a display that is not 16:9 the game draws its 16:9 picture centred between black bars: the v6e doors retry
# (2026-10-21, a 2560x1600 desktop) captured 1280x800 frames with bars top and bottom, and every check written for
# shot.ps1's 1280x720 output missed (main menu, save loaded, HUD). The centred 16:9 rectangle when the parts outside it
# are black (no pixel above luminance 12), else the whole capture (a 16:9 screen, or a game drawn over a whole 16:10 screen).
if (-not ('FO4SF.Frame' -as [type])) {
  Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System; using System.Drawing; using System.Drawing.Imaging; using System.Runtime.InteropServices;
namespace FO4SF {
  public static class Frame {
    // the brightest pixel of a rectangle, as luminance (ITU-R 601, as PIL's "L"): every pixel, not a sample (Codex, #442)
    public static int MaxLuma(Bitmap bmp, int x0, int y0, int x1, int y1) {
      var d = bmp.LockBits(new Rectangle(x0, y0, x1 - x0, y1 - y0), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
      try {
        var row = new byte[(x1 - x0) * 4]; int max = 0;
        for (int y = 0; y < y1 - y0; y++) {
          Marshal.Copy(IntPtr.Add(d.Scan0, y * d.Stride), row, 0, row.Length);
          for (int i = 0; i < row.Length; i += 4) {
            int l = (row[i + 2] * 299 + row[i + 1] * 587 + row[i] * 114) / 1000;
            if (l > max) max = l;
          }
        }
        return max;
      } finally { bmp.UnlockBits(d); }
    }
  }
}
'@
}
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
    if ([FO4SF.Frame]::MaxLuma($bmp, $bar[0], $bar[1], $bar[2], $bar[3]) -gt 12) { return $full }
  }
  return $rect
}
