# Bring the runner's own Starfield window to the front without sending any input (testqueue.py --refocus, used only
# after the PC has been idle --min-idle seconds). A plain SetForegroundWindow from a background process is refused by
# Windows (test queue 2026-10-11: a Steam popup kept the foreground); attaching to the foreground thread's input is the
# documented way around that. Exit 0: the game is in front. 1: it is not (or no game).
Add-Type @'
using System; using System.Runtime.InteropServices;
public class Front {
  [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
  [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
  public static void Bring(IntPtr target) {
    uint fg = GetWindowThreadProcessId(GetForegroundWindow(), IntPtr.Zero), me = GetCurrentThreadId();
    bool att = fg != me && AttachThreadInput(me, fg, true);
    ShowWindow(target, 9); BringWindowToTop(target); SetForegroundWindow(target);
    if (att) AttachThreadInput(me, fg, false);
  }
  public static bool IsFront(IntPtr target) { return GetForegroundWindow() == target; }
}
'@
$p = Get-Process Starfield -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p -or $p.MainWindowHandle -eq 0) { "no game window"; exit 1 }
[Front]::Bring($p.MainWindowHandle)
Start-Sleep -Milliseconds 800
if ([Front]::IsFront($p.MainWindowHandle)) { "game in front"; exit 0 }
"game not in front"; exit 1
