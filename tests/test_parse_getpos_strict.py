"""parse_getpos.py --strict / --angle (door_trip reads, docs/slice/door-frames.md): labelled values of this read's own
session only. The first case is the read of the first live door_trip run (2026-10-13, slice_door_1013 a1): the
default parser took the previous session's Z, this session's X and Z for x, y, z."""
import os
import subprocess
import sys
import tempfile
import unittest

GAME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "game")
sys.path.insert(0, GAME)
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


OLD = "GetPos: X >> -2195.53 GetPos: Y >> -1595.86 GetPos: Z >> 99.74"          # a full older triplet still on screen
NEW = "player.getpos x GetPos: X >> -2195.27 player.getpos y GetPos: Y >> -1593.51 player.getpos z GetPos: Z >> 99.41"
NONCE = "fo4sfr1a2b3c4d"
ECHO = f'{NONCE} Script command "{NONCE}" not found.'          # the typed line echoed, then the console's refusal


class NonceTests(unittest.TestCase):
    """Codex's review of PR #107: a strict read was not tied to its own request, so OLD passed for a read whose own
    echoes and replies were missing. readpos types a nonce first; only replies after its echo are this read's."""
    def test_an_old_triplet_without_the_nonce_is_no_read(self):
        self.assertEqual(pg.parse_strict(OLD), "-2195.53 -1595.86 99.74")           # without a nonce: as before
        self.assertEqual(pg.parse_strict(OLD, nonce=NONCE), "fail")                 # no echo seen: no read
        self.assertEqual(pg.parse(OLD, nonce=NONCE), "fail")
        self.assertEqual(pg.parse_strict(f"{OLD} fo4sfr1a2b3c4e {NEW}", nonce=NONCE), "fail")   # another read's nonce

    def test_a_triplet_before_the_nonce_is_rejected(self):
        t = f"{OLD} {ECHO} player.getpos x player.getpos y player.getpos z"           # this read's replies all lost
        self.assertEqual(pg.parse_strict(t, nonce=NONCE), "fail")
        self.assertEqual(pg.parse(t, nonce=NONCE), "fail")
        self.assertEqual(pg.parse_strict(f"{OLD} {ECHO} player.getpos x GetPos: X >> -2195.27 player.getpos y "
                                         f"player.getpos z GetPos: Z >> 99.41", nonce=NONCE), "fail")   # Y lost

    def test_a_triplet_after_the_nonce_is_accepted(self):
        self.assertEqual(pg.parse_strict(f"{OLD} {ECHO} {NEW}", nonce=NONCE), "-2195.27 -1593.51 99.41")
        self.assertEqual(pg.parse(f"{OLD}\n{ECHO}\n{NEW}", nonce=NONCE), "-2195.27 -1593.51 99.41")
        # the default parser's column layout: the echo sits among the labels, before the values
        col = f"{NONCE}\nplayer.getpos\nGetPos: X > >\nplayer.getpos\nGetPos: Y > >\nplayer.getpos z\nGetPos: Z > >\nx\n-10.07\n43.95\n-10.95"
        self.assertEqual(pg.parse(col, nonce=NONCE), "-10.07 43.95 -10.95")
        # the echo as the OCR may read it: 0 as O, 1 as l, 5 as S, 8 as B, a space inside, any case
        for seen in ("fo4sfr la2b3c4d", "fO4sfr1a2b3c4d", "FO4SFR1A2B3C4D", "fo4 sfr1a2b3c4d", "fo45fr1a2b3c4d"):
            self.assertEqual(pg.parse_strict(f"{OLD} {seen} {NEW}", nonce=NONCE), "-2195.27 -1593.51 99.41", seen)
        self.assertEqual(pg.parse_strict("x " + ECHO.replace(NONCE, "fo4sfr5b8e0c1d") + " " + NEW, nonce="fo4sfr5b8e0c1d"),
                         "-2195.27 -1593.51 99.41")
        self.assertEqual(pg.parse_strict("fo4sfrSbBeOcld " + NEW, nonce="fo4sfr5b8e0c1d"), "-2195.27 -1593.51 99.41")
        # strict labels still: the live garble after the nonce is no read either
        self.assertEqual(pg.parse_strict(f"{ECHO}\n{GARBLED}", nonce=NONCE), "fail")

    def test_a_column_read_never_joins_an_older_value(self):
        # #215: in the column layout an older reply's label sits before the echo and its value after it; with this
        # read's Y value lost the last three numbers were the old Z plus this X and Z
        col = ("GetPos: Z > >\n" + NONCE + "\nScript command \"" + NONCE + "\" not found.\nplayer.getpos x\n"
               "GetPos: X > >\nplayer.getpos y\nGetPos: Y > >\nplayer.getpos z\nGetPos: Z > >\n99.74\n-2195.27\n99.41")
        self.assertEqual(pg.parse(col, nonce=NONCE), "fail")
        whole = col.replace("\n99.74\n-2195.27\n99.41", "\n99.74\n-2195.27\n-1593.51\n99.41")   # every value read
        self.assertEqual(pg.parse(whole, nonce=NONCE), "-2195.27 -1593.51 99.41")

    def test_the_angle_after_its_own_nonce(self):
        n2 = "fo4sfr9e8d7c6b"
        t = f"{NEW} GetAngle: Z >> 10.00 {n2} player.getangle z GetAngle: Z >> 181.92"
        self.assertEqual(pg.parse_angle(t, n2), "181.92")
        self.assertEqual(pg.parse_angle(f"{NEW} GetAngle: Z >> 10.00 player.getangle z", n2), "fail")   # no echo
        self.assertEqual(pg.parse_angle(f"GetAngle: Z >> 10.00 {n2} player.getangle z", n2), "fail")   # reply lost
        self.assertEqual(pg.parse_angle(t, ""), "fail")

    def test_the_command_line(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "ocr.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"{OLD}\n{ECHO}\n{NEW}\nfo4sfr9e8d7c6b\nplayer.getangle z\nGetAngle: Z >> 181.92\n")
        def run(*a):
            return subprocess.run([sys.executable, os.path.join(GAME, "parse_getpos.py"), p, *a],
                                  capture_output=True, text=True).stdout.strip()
        self.assertEqual(run("--strict", "--nonce", NONCE), "-2195.27 -1593.51 99.41")
        self.assertEqual(run("--strict", "--nonce", "fo4sfr00000000"), "fail")
        self.assertEqual(run("--nonce", NONCE), "-2195.27 -1593.51 99.41")
        self.assertEqual(run("--angle-only", "--nonce", "fo4sfr9e8d7c6b"), "181.92")
        self.assertEqual(run("--angle-only", "--nonce", "fo4sfr00000000"), "fail")


if __name__ == "__main__":
    unittest.main()
