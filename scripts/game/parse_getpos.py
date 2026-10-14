"""Parse OCR'd console text for the most recent GetPos X/Y/Z values. Prints 'x y z' or 'fail'.
OCR quirks handled: 'Get Pos', '> >', number on the next line, '.' read as space ('-4 81'), and the OCR engine
listing a column of labels first and the column of numbers after (then the last three bare numbers are X, Y, Z).

usage: parse_getpos.py <ocr text> [--strict] [--angle]

--strict (door_trip, docs/slice/door-frames.md): only values printed right after their own label ("GetPos: X >> v"),
         never bare numbers, each with the console's two decimals, all three from this read's session: after the last
         X reply exactly one Y reply and then one Z reply, and no echo of "getpos x" after that X reply (the X line of
         this session lost, an older one still on screen). A value glued to more digits ("-1 593.51": OCR split
         "-1593.51") is rejected, not read as -1.59. In the first live door_trip run (2026-10-13, slice_door_1013 a1)
         the bare-number fallback read "99.74 -2195.27 99.41" for (-2195.27, -1593.51, 99.41): the previous session's Z,
         this session's X and Z (the Y line lost), which the step took for a load 2,372 m away.
--angle  also GetAngle Z ("GetAngle: Z >> 181.92", the format of GetPos: supported hypothesis); prints 'x y z h'.
"""
import re
import sys

LABEL = r"Get\s?Po\s?s"
STRICT_VALUE = r"(-?)\s?(\d{1,6})(?:[.,]\s?|\s)(\d{2})(?![\d.,])"


def parse(raw):
    """'x y z' (2 decimals) from OCR'd console text, or 'fail'."""
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


def parse_strict(raw, angle=False):
    """'x y z' (or 'x y z h' with angle) from this read's own labelled replies only, else 'fail' (module doc)."""
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
    if "--strict" in args or "--angle" in args:
        print(parse_strict(raw, angle="--angle" in args))
    else:
        print(parse(raw))
