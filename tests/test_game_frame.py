"""game_frame.py / game_rect.ps1: screen checks written for shot.ps1's 1280x720 frames read a letterboxed (16:10) or
pillarboxed (21:9) desktop too (the v6e doors retry, 2026-10-21: 1280x800 frames, every check missed)."""
import os
import re
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "scripts", "game")
sys.path.insert(0, GAME)
import game_frame  # noqa: E402
import hud_visible  # noqa: E402
import loadorder_row  # noqa: E402
import prompt_visible  # noqa: E402


def read(name):
    with open(os.path.join(GAME, name), encoding="utf-8") as f:
        return f.read()


def frame():
    """A 1280x720 game picture with the HUD (oxygen ring, health bar), the prompt bar and a highlighted 'Current' row."""
    im = Image.new("RGB", (1280, 720), (60, 70, 80))
    d = ImageDraw.Draw(im)
    d.ellipse((70, 550, 185, 670), outline=(255, 255, 255), width=12)
    d.rectangle((1020, 628, 1210, 638), fill=(255, 255, 255))
    d.rectangle((800, 176, 1040, 189), fill=(255, 255, 255))
    d.rectangle((520, 368, 750, 384), fill=(140, 140, 140))
    return im


class GameFrameTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def save(self, im, name):
        p = os.path.join(self.d, name)
        im.save(p)
        return p

    def boxed(self, size, at, picture_size=(1280, 720), bar=(0, 0, 0)):
        canvas = Image.new("RGB", size, bar)
        canvas.paste(frame().resize(picture_size), at)
        return canvas

    def test_a_16_9_frame_is_read_as_before(self):
        p = self.save(frame(), "f.png")
        self.assertEqual(game_frame.picture(Image.open(p)), (0, 0, 1280, 720))
        self.assertTrue(hud_visible.visible(p))
        self.assertTrue(prompt_visible.visible(p))
        self.assertEqual(loadorder_row.row(p), "current")

    def test_a_letterboxed_16_10_frame_is_read_inside_its_bars(self):
        # shot.ps1's old output of a 2560x1600 desktop: 1280x800, the picture between 40 px bars
        p = self.save(self.boxed((1280, 800), (0, 40)), "lb.png")
        self.assertEqual(game_frame.picture(Image.open(p)), (0, 40, 1280, 720))
        self.assertTrue(hud_visible.visible(p))
        self.assertTrue(prompt_visible.visible(p))
        self.assertEqual(loadorder_row.row(p), "current")

    def test_a_pillarboxed_ultrawide_frame_is_read_between_its_bars(self):
        p = self.save(self.boxed((1720, 720), (220, 0)), "pb.png")
        self.assertEqual(game_frame.picture(Image.open(p)), (220, 0, 1280, 720))
        self.assertTrue(hud_visible.visible(p))

    def test_a_game_drawn_over_the_whole_16_10_screen_is_not_cropped(self):
        im = frame().resize((1280, 800))
        self.assertEqual(game_frame.picture(im), (0, 0, 1280, 800))
        # a bar that is not black (a HUD pixel, a scene) is part of the picture
        for xy in ((5, 5), (1277, 797), (641, 13)):                    # anywhere in either bar, off any grid
            im = self.boxed((1280, 800), (0, 40))
            im.putpixel(xy, (40, 40, 40))
            self.assertEqual(game_frame.picture(im), (0, 0, 1280, 800), xy)

    def test_the_hud_of_a_game_drawn_over_a_whole_16_10_screen_is_found(self):
        # doors retry 3 (2026-10-21): in play the game filled the 2560x1600 screen, no bars, and the stretched boxes
        # missed the HUD; a width-wide 16:9 layout, centred or held to the bottom edge, is read too
        hud = Image.new("RGB", (1280, 720), (60, 70, 80))
        d = ImageDraw.Draw(hud)
        d.ellipse((70, 550, 185, 670), outline=(255, 255, 255), width=12)
        d.rectangle((1020, 628, 1210, 638), fill=(255, 255, 255))
        d.rectangle((800, 176, 1040, 189), fill=(255, 255, 255))
        for top, name in ((40, "centred"), (80, "bottom")):
            with self.subTest(layout=name):
                im = Image.new("RGB", (1280, 800), (60, 70, 80))       # scene to every edge: no bars to crop
                im.paste(hud.crop((0, 0, 1280, 720)), (0, top))
                p = self.save(im, name + ".png")
                self.assertEqual(game_frame.picture(Image.open(p)), (0, 0, 1280, 800))
                self.assertTrue(hud_visible.visible(p))
                self.assertTrue(prompt_visible.visible(p))
                got = {n: (r > hud_visible.RING[2] and b > hud_visible.BAR[2]) for n, r, b in hud_visible.readings(p)}
                self.assertTrue(got[name], got)
        # the console overlay (everything dark) is still no in every layout
        dark = self.save(Image.new("RGB", (1280, 800), (20, 20, 20)), "dark.png")
        self.assertFalse(hud_visible.visible(dark))
        self.assertFalse(prompt_visible.visible(dark))

    def test_centre_ui_reads_the_centred_layout_on_a_whole_16_10_screen(self):
        # the real frames (PR #443): the prompt bar sat 40 px lower in 1280x800 (centred), the HUD 80 px (bottom)
        im = Image.new("RGB", (1280, 800), (60, 70, 80))
        im.paste(frame(), (0, 40))
        self.assertEqual(game_frame.centred(im)(800, 176, 1040, 189), (800, 216, 1040, 229))
        self.assertEqual(loadorder_row.row(self.save(im, "c.png")), "current")
        lb = self.boxed((1280, 800), (0, 40))                          # between bars: the crop, the same place
        self.assertEqual(game_frame.centred(lb)(800, 176, 1040, 189), (800, 216, 1040, 229))
        self.assertEqual(game_frame.centred(frame())(800, 176, 1040, 189), (800, 176, 1040, 189))

    def test_no_hud_is_still_no_on_a_letterboxed_frame(self):
        im = Image.new("RGB", (1280, 800), (0, 0, 0))
        im.paste(Image.new("RGB", (1280, 720), (60, 70, 80)), (0, 40))
        self.assertFalse(hud_visible.visible(self.save(im, "nohud.png")))

    def test_the_capture_scripts_crop_to_the_same_rectangle(self):
        ps = read("game_rect.ps1")
        self.assertIn("-gt %d" % game_frame.DARK, ps)                     # the same black threshold
        # every pixel of a bar, not a sample of them (Codex on #442): one off-grid HUD pixel keeps the whole frame
        self.assertIn("[FO4SF.Frame]::MaxLuma($bmp, $bar[0], $bar[1], $bar[2], $bar[3]) -gt", ps)
        self.assertIn("for (int i = 0; i < row.Length; i += 4)", ps)
        self.assertNotIn("GetPixel", ps)
        # and each pixel's luminance rounded as Pillow's "L" (Codex on #442: (0, 22, 0) is 13 there, 12 truncated)
        m = re.search(r"int l = \(row\[i \+ 2\] \* (\d+) \+ row\[i \+ 1\] \* (\d+) \+ row\[i\] \* (\d+) \+ 0x8000\) >> 16;", ps)
        self.assertIsNotNone(m)
        wr, wg, wb = (int(x) for x in m.groups())
        luma = lambda r, g, b: (r * wr + g * wg + b * wb + 0x8000) >> 16
        for rgb in ((0, 22, 0), (0, 21, 0), (12, 12, 12), (13, 13, 13), (255, 0, 0), (0, 0, 255), (40, 200, 7)):
            with self.subTest(rgb=rgb):
                self.assertEqual(luma(*rgb), Image.new("RGB", (1, 1), rgb).convert("L").getpixel((0, 0)))
        self.assertIn("$w * 9 * %g" % game_frame.TOLERANCE, ps)           # and the same 16:9 tolerance
        for name in ("shot.ps1", "shot_region.ps1"):
            with self.subTest(script=name):
                src = read(name)
                self.assertIn(". (Join-Path $PSScriptRoot 'game_rect.ps1')", src)
                self.assertRegex(src, r"\$r = Get-GameRect \$\w+")
        shot = read("shot.ps1")
        self.assertIn("$g2.DrawImage($bmp, (New-Object System.Drawing.Rectangle 0, 0, $w, $h), $r, 'Pixel')", shot)


if __name__ == "__main__":
    unittest.main()
