"""Game-side scripts: every scripts/game/*.ps1 (and tools/ai-team/*.ps1) parses (PowerShell's own parser; skipped where
PowerShell is absent), and the screen checks that gate key presses behave on synthetic images (no game, no input)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "scripts", "game")
TEAM = os.path.join(ROOT, "tools", "ai-team")
sys.path.insert(0, GAME)

POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


@unittest.skipIf(POWERSHELL is None, "PowerShell not available")
class ParseTests(unittest.TestCase):
    def parse_all(self, folder):
        script = ("$bad = @(); foreach ($f in Get-ChildItem -Path '%s' -Filter *.ps1) { $e = $null; "
                  "[void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$null, [ref]$e); "
                  "if ($e.Count) { $bad += $f.Name + ': ' + $e[0].Message } }; $bad -join \"`n\"; exit $bad.Count"
                  % folder.replace("'", "''"))
        out = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_every_game_script_parses(self):
        self.parse_all(GAME)

    def test_every_team_script_parses(self):
        self.parse_all(TEAM)


class PromptVisibleTests(unittest.TestCase):
    """prompt_visible.py: a solid white activation-prompt bar right of the crosshair says 'yes'; nothing there says 'no'."""

    def setUp(self):
        try:
            from PIL import Image
        except ImportError:                              # pragma: no cover
            self.skipTest("Pillow not installed")
        self.Image = Image
        import prompt_visible
        self.visible = prompt_visible.visible

    def shot(self, bar, size=(1280, 720)):
        im = self.Image.new("RGB", size, (20, 24, 28))
        if bar:
            sx, sy = size[0] / 1280.0, size[1] / 720.0
            im.paste((250, 250, 250), (int(780 * sx), int(174 * sy), int(1060 * sx), int(191 * sy)))
        path = os.path.join(tempfile.mkdtemp(), "shot.png")
        im.save(path)
        return path

    def test_bar_is_seen_and_dark_screen_is_not(self):
        self.assertTrue(self.visible(self.shot(True)))
        self.assertFalse(self.visible(self.shot(False)))

    def test_scales_with_the_screenshot_size(self):
        self.assertTrue(self.visible(self.shot(True, size=(1920, 1080))))
        self.assertFalse(self.visible(self.shot(False, size=(1920, 1080))))

    def test_half_covered_bar_is_not_a_prompt(self):
        im = self.Image.new("RGB", (1280, 720), (20, 24, 28))
        im.paste((250, 250, 250), (800, 176, 900, 189))   # less than 60 percent of the strip
        path = os.path.join(tempfile.mkdtemp(), "half.png")
        im.save(path)
        self.assertFalse(self.visible(path))


if __name__ == "__main__":
    unittest.main()
