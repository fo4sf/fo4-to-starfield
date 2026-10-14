"""parse_getpos.py --strict / --angle (door_trip reads, docs/slice/door-frames.md): labelled values of this read's own
session only. The first case is the read of the first live door_trip run (2026-10-13, slice_door_1013 a1): the
default parser took the previous session's Z, this session's X and Z for x, y, z."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "game"))
import parse_getpos as pg  # noqa: E402

# an OCR text that the default parser reads exactly as the live run did: the previous read (the leg's start, z 99.74)
# still on screen, values split from their labels (the column layout) and this read's Y value lost (the HUD's O2 dial
# crosses the console lines in the bottom-left corner: in_cell_cap.png of that run)
GARBLED = """GetPos: Y > >
player.getpos z
GetPos: Z > >
99.74
player.getpos x
GetPos: X > >
-2195.27
player.getpos y
GetPos: Y > >
player.getpos z
GetPos: Z > >
99.41"""


class StrictTests(unittest.TestCase):
    def test_the_live_garbled_read_is_rejected(self):
        self.assertEqual(pg.parse(GARBLED), "99.74 -2195.27 99.41")   # what the live run took for a load
        self.assertEqual(pg.parse_strict(GARBLED), "fail")

    def test_an_echo_followed_by_a_value_is_not_a_reply(self):
        t = "player.getpos x\n-2195.27\nplayer.getpos y\nGetPos: Y >> -1593.51\nplayer.getpos z\nGetPos: Z >> 99.41"
        self.assertEqual(pg.parse_strict(t), "fail")

    def test_a_clean_session(self):
        t = ("player.getpos x\nGetPos: X >> -2195.27\nplayer.getpos y\nGetPos: Y >> -1593.51\nplayer.getpos z\n"
             "GetPos: Z >> 99.41")
        self.assertEqual(pg.parse_strict(t), "-2195.27 -1593.51 99.41")

    def test_ocr_quirks_between_label_and_value(self):
        t = "Get Po s: X > > -2195.27 Get Pos: Y > > -1593.51 GetPos: z 99.41"
        self.assertEqual(pg.parse_strict(t), "-2195.27 -1593.51 99.41")

    def test_a_split_number_is_not_read_short(self):
        # "-1 593.51" is OCR splitting -1593.51: the default parser reads -1.59 (the live arrival read
        # "-2195.27 -1.59 99.41"); strict rejects the read
        t = "GetPos: X >> -2195.27 GetPos: Y >> -1 593.51 GetPos: Z >> 99.41"
        self.assertEqual(pg.parse(t), "-2195.27 -1.59 99.41")
        self.assertEqual(pg.parse_strict(t), "fail")

    def test_an_older_session_line_never_stands_in(self):
        # this session's Y lost: the previous session's Y is before the last X, so nothing to take
        t = ("GetPos: X >> -2195.53 GetPos: Y >> -1595.86 GetPos: Z >> 99.74 player.getpos x GetPos: X >> -2195.27 "
             "player.getpos y player.getpos z GetPos: Z >> 99.41")
        self.assertEqual(pg.parse_strict(t), "fail")
        # this session's X lost: the last X is the previous session's, followed by two Y and two Z replies
        t = ("GetPos: X >> -2195.53 GetPos: Y >> -1595.86 GetPos: Z >> 99.74 player.getpos x player.getpos y "
             "GetPos: Y >> -1593.51 player.getpos z GetPos: Z >> 99.41")
        self.assertEqual(pg.parse_strict(t), "fail")
        # only the previous session's Y and Z remain on screen and this session's X is lost: its echo is after them
        t = "GetPos: X >> 1.00 GetPos: Y >> 2.00 GetPos: Z >> 3.00 player.getpos x"
        self.assertEqual(pg.parse_strict(t), "fail")

    def test_column_layout_is_not_read(self):
        t = "player.getpos x\nGetPos: X > >\nplayer.getpos\nGetPos: Y > >\nplayer.getpos z\nGetPos: Z > >\n-10.07\n43.95\n-10.95"
        self.assertEqual(pg.parse_strict(t), "fail")

    def test_angle(self):
        t = ("GetPos: X >> -2195.53 GetPos: Y >> -1595.86 GetPos: Z >> 99.77 player.getangle z GetAngle: Z >> 181.92")
        self.assertEqual(pg.parse_strict(t, angle=True), "-2195.53 -1595.86 99.77 181.92")
        self.assertEqual(pg.parse_strict(t.replace("GetAngle: Z >> 181.92", ""), angle=True), "fail")
        # an older session's angle before this session's position is not this read's
        t2 = "GetAngle: Z >> 10.00 GetPos: X >> 1.00 GetPos: Y >> 2.00 GetPos: Z >> 3.00 player.getangle z"
        self.assertEqual(pg.parse_strict(t2, angle=True), "fail")
        self.assertEqual(pg.parse_strict("Get Ang le: Z > > -3.50 ".join(["GetPos: X >> 1.00 GetPos: Y >> 2.00 "
                                                                          "GetPos: Z >> 3.00 ", ""]), angle=True),
                         "1.00 2.00 3.00 -3.50")


if __name__ == "__main__":
    unittest.main()
