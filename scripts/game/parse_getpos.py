"""Parse OCR'd console text for the most recent GetPos X/Y/Z values. Prints 'x y z' or 'fail'.
OCR quirks handled: 'Get Pos', '> >', number on the next line, '.' read as space ('-4 81'), and the OCR engine
listing a column of labels first and the column of numbers after (then the last three bare numbers are X, Y, Z).

usage: parse_getpos.py <ocr text> [--strict] [--angle] [--angle-only] [--nonce <token>]

--strict (door_trip, docs/slice/door-frames.md): only values printed right after their own label ("GetPos: X >> v"),
         never bare numbers, each with the console's two decimals, all three from this read's session: after the last
         X reply exactly one Y reply and then one Z reply, and no echo of "getpos x" after that X reply (the X line of
         this session lost, an older one still on screen). A value glued to more digits ("-1 593.51": OCR split
         "-1593.51") is rejected, not read as -1.59. In the first live door_trip run (2026-10-13, slice_door_1013 a1)
         the bare-number fallback read "99.74 -2195.27 99.41" for (-2195.27, -1593.51, 99.41): the previous session's Z,
         this session's X and Z (the Y line lost), which the step took for a load 2,372 m away.
--angle  also GetAngle Z ("GetAngle: Z >> 181.92", the format of GetPos: supported hypothesis); prints 'x y z h'.
--angle-only  the one GetAngle Z reply after the nonce (readpos -Angle's second capture); prints 'h'.
--nonce  the token readpos.ps1 typed as an unknown command before this read's commands (fo4sfr<8 hex>; the console
         echoes the typed line): only text after its echo is read, and no echo seen is no read. Without it a full
         older triplet still on screen passed for this read when its own replies were missing (Codex's review of PR
         #107, 2026-10-14). The echo is matched with the OCR's confusions (0/O, 1/l/I, 5/S, 8/B, a space between
         characters).
"""
import re
import sys

LABEL = r"Get\s?Po\s?s"
STRICT_VALUE = r"(-?)\s?(\d{1,6})(?:[.,]\s?|\s)(\d{2})(?![\d.,])"
NONCE_PREFIX = "fo4sfr"
# what the OCR may read for each character of a nonce (the console reads of 2026-10-11/13: "RedRocketOl", "GetlsID")
CONFUSED = {"0": "0oO", "1": "1lI|", "2": "2zZ", "5": "5sS", "6": "6b", "8": "8bB", "9": "9g",
            "a": "ao", "b": "b68", "c": "ce", "e": "ec", "o": "o0", "s": "s5"}


def nonce_pattern(nonce):
    """A regex for the nonce's echo as the OCR may read it: each character or its confusions, optional spaces between."""
    return r"\s?".join("[" + re.escape(CONFUSED.get(c.lower(), c.lower())) + "]" for c in nonce)


def after_nonce(raw, nonce):
    """The text after the last echo of the nonce (its reply may quote it again), or None when no echo is seen."""
    ms = list(re.finditer(nonce_pattern(nonce), raw, re.I))
    return raw[ms[-1].end():] if ms else None


def parse(raw, nonce=None):
    """'x y z' (2 decimals) from OCR'd console text, or 'fail'. With a nonce only the text after its echo (the OCR's
    column layout lists the labels, the echo among them, before the values, so the bare-number fallback still works)."""
    if nonce is not None:
        raw = after_nonce(raw, nonce)
        if raw is None:
            return "fail"
    text = " ".join(raw.split())
    vals = {}
    # The ">>" is optional and "Pos" may be split: the OCR read "GetPos: z 7.95" and "Get Po s: X > > 9.71" (test queue
    # 2026-10-11). Only spaces, ':' and '>' may sit before the number; a broader \W* would swallow the minus sign.
    for m in re.finditer(r"Po\s?s\W*?([XYZ])[\s:>]*(-?\s?\d+)(?:\s*[\.,]\s*|\s)(\d{1,3})\b", text, re.I):
        vals[m.group(1).upper()] = float(m.group(2).replace(" ", "") + "." + m.group(3))
    if len(vals) < 3 and len(re.findall(r"Get\s?Pos", raw, re.I)) >= 3:
        bare = []
        for line in raw.splitlines():
            m = re.fullmatch(r"\s*(-?\d+)\s*[\.,\s]\s*(\d{1,3})\s*", line)
            if m:
                bare.append(float(m.group(1) + "." + m.group(2)))
        if len(bare) >= 3:
            vals = dict(zip("XYZ", bare[-3:]))
    return " ".join(f"{vals[k]:.2f}" for k in "XYZ") if len(vals) == 3 else "fail"


def replies(text, label=LABEL, axes="XYZ"):
    """[(start, axis, value)] of every labelled reply ("<label>: <axis> >> <value>"; only ':', '>' and spaces between
    the label and the value, as OCR reads them) in text order."""
    # a reply has a ':' after its label or '>' after its axis; the echo "player.getpos x" followed by a value line (the
    # reply's label lost) has neither and is not a reply
    ax = "([" + axes + "])"
    pat = r"(?:" + label + r")\s*(?::\s*" + ax + r"\s*:?\s*(?:>\s*)*|" + ax + r"\s*(?:>\s*)+)" + STRICT_VALUE
    out = []
    for m in re.finditer(pat, text, re.I):
        v = float(m.group(4) + "." + m.group(5))
        out.append((m.start(), (m.group(1) or m.group(2)).upper(), -v if m.group(3) else v))
    return out


def parse_angle(raw, nonce):
    """'h' from the one GetAngle Z reply after this read's nonce, else 'fail' (readpos -Angle's second capture: the
    console shows about nine lines, too few for a nonce, three getpos and a getangle with their replies)."""
    raw = after_nonce(raw, nonce) if nonce else None
    hs = replies(" ".join(raw.split()), r"Get\s?Ang\s?le", "Z") if raw is not None else []
    return f"{hs[0][2]:.2f}" if len(hs) == 1 else "fail"


def parse_strict(raw, angle=False, nonce=None):
    """'x y z' (or 'x y z h' with angle) from this read's own labelled replies only, else 'fail' (module doc). With a
    nonce only replies after its echo count, and no echo is no read."""
    if nonce is not None:
        raw = after_nonce(raw, nonce)
        if raw is None:
            return "fail"
    text = " ".join(raw.split())
    pos = replies(text)
    xs = [r for r in pos if r[1] == "X"]
    if not xs:
        return "fail"
    x = xs[-1]
    after = [r for r in pos if r[0] > x[0]]
    ys, zs = [r for r in after if r[1] == "Y"], [r for r in after if r[1] == "Z"]
    if len(ys) != 1 or len(zs) != 1 or not x[0] < ys[0][0] < zs[0][0]:
        return "fail"
    # an echo of "getpos x" after the X reply: this session's X line was lost and the X found is an older one
    for m in re.finditer(LABEL + r"\s+x\b(?!\s*[:>])(?!\s*-?\d)", text, re.I):
        if m.start() > x[0]:
            return "fail"
    out = [x[2], ys[0][2], zs[0][2]]
    if angle:
        hs = [r for r in replies(text, r"Get\s?Ang\s?le", "Z") if r[0] > zs[0][0]]
        if len(hs) != 1:
            return "fail"
        out.append(hs[0][2])
    return " ".join(f"{v:.2f}" for v in out)


if __name__ == "__main__":
    args = sys.argv[1:]
    raw = open(args[0], encoding="utf-8-sig", errors="replace").read()
    nonce = args[args.index("--nonce") + 1] if "--nonce" in args else None
    if "--angle-only" in args:
        print(parse_angle(raw, nonce or ""))
    elif "--strict" in args or "--angle" in args:
        print(parse_strict(raw, angle="--angle" in args, nonce=nonce))
    else:
        print(parse(raw, nonce=nonce))
