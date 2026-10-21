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
        im = self.boxed((1280, 800), (0, 40))
        im.putpixel((5, 5), (40, 40, 40))
        self.assertEqual(game_frame.picture(im), (0, 0, 1280, 800))

    def test_no_hud_is_still_no_on_a_letterboxed_frame(self):
        im = Image.new("RGB", (1280, 800), (0, 0, 0))
        im.paste(Image.new("RGB", (1280, 720), (60, 70, 80)), (0, 40))
        self.assertFalse(hud_visible.visible(self.save(im, "nohud.png")))

    def test_the_capture_scripts_crop_to_the_same_rectangle(self):
        ps = read("game_rect.ps1")
        self.assertIn("-gt %d" % game_frame.DARK, ps)                     # the same black threshold
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
