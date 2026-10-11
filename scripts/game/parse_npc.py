"""Parse the OCR'd console text of one npc_nav console session (qstep.ps1). Prints one JSON object:
{"isid": 1|0|null, "x"/"y"/"z": float|null, "pos": "x y z"|null, "disabled": 1|0|null, "self": "FF0012AB"|null,
 "how": "order"|"inline"|"", "ocr": "<text>"}

usage: parse_npc.py <ocr text file> [--expect isid,x,y,z] [--typed FF000800]
  --expect  the values this session's commands produce, in the order they were typed: isid (GetIsID), x / y / z
            (getpos x/y/z), disabled (GetDisabled), self (GetSelf, parsed apart: an id, not a number)
  --typed   ids this session typed itself (prid <id>): such an id counts as GetSelf's reply only when it is on screen twice

The OCR lays the console out in one of two ways (real console OCR from this PC, 2026-10-11):
  inline: "GetIsID > > 1.00", "Get Pos: X > > -10.07"            each value right after its label;
  column: "Get Pos: X > > ... Get Pos: Z > > ... -10.07 43.95 z -10.95"   all labels first, then all values, with
          command arguments that left their echo ("player.getpos y" read as "player.getpos", the x / z drifting into
          the value column).
Two readings, the first that holds is used:
  order:  the session's values are the numbers on screen in typing order. It holds only when the screen has exactly
          as many numbers as the session expects, no reply label stands before this session's first command echo
          (ClearConsole cleared the log: nothing older is on screen) and the labels found are in the expected order.
          A GetIsID / GetDisabled value other than 0 or 1 means the numbers are misaligned: the reading is dropped.
  inline: label, '>>' / ':' and value next to each other, after this session's first command echo only (a reply left
          over from an earlier session is never read as this one's).
Numbers are decimals as the console prints them ("-10.07"; OCR quirks "-0 85" and "1 00" for "-0.85" and "1.00");
form ids and integers (an echoed "placeatme 0000CF96 1") are never values. GetSelf's reply format is unresolved: hex
(optional 0x / parentheses) or a decimal form id is accepted; only ids of references created at runtime (FFxxxxxx).
"""
import argparse
import json
import re
import sys

I_ = r"[Il1|]"
LABELS = {                                                   # command name as echoed and as the reply's label
    "isid": rf"Get\s?{I_}s\s?{I_}D",
    "self": r"Get\s?Se[l1I|]f",
    "disabled": r"Get\s?Disab[l1I|]ed",
    "pos": r"Get\s?Po\s?s",
}
ARROWS = r"\s*(?::\s*)?(?:>\s*)+|\s*:\s*"                    # '>>', '> >', ':' or ': >>' between label and value
VALUE = r"(?<![\w.,])(-\s?)?(\d{1,6})(?:\s?[.,]\s?(\d{1,3})|\s(\d{2}))(?![\w.,])"
FFID = r"(?<![0-9A-Za-z])(?:0x)?\(?\s*([Ff][Ff][0-9A-Fa-fO]{6})\s*\)?(?![0-9A-Za-z])"
DECID = r"(?<![\w.,])(42\d{8})(?:[.,]\d+)?(?![\w])"         # FF000000..FFFFFFFF written in decimal
KIND_OF = {"isid": "isid", "x": "pos", "y": "pos", "z": "pos", "disabled": "disabled", "self": "self"}


def flat(s):
    return " ".join(s.split())


def value(m):
    sign, whole, frac, frac2 = m.group(1), m.group(2), m.group(3), m.group(4)
    v = float(whole + "." + (frac if frac is not None else frac2))
    return -v if sign else v


def events(text):
    """[(start, end, kind, role, data)] in text order. kind: isid / self / disabled / pos / value / id; role for the
    command names: 'echo' (what was typed) or 'reply' (the label of the game's answer); data: the axis of a GetPos
    reply, the number of a value, the id."""
    ev = []
    for kind, pat in LABELS.items():
        for m in re.finditer(pat, text, re.I):
            rest = text[m.end():m.end() + 24]
            if kind == "pos":
                a = re.match(r"\s*:\s*([XYZ])\b|\s*([XYZ])\s*>", rest, re.I)    # "GetPos: X >>", "Get Pos Z >"
                if a:
                    ev.append((m.start(), m.end() + a.end(), kind, "reply", (a.group(1) or a.group(2)).lower()))
                elif not re.match(r"\s*:", rest):
                    ev.append((m.start(), m.end(), kind, "echo", None))
                continue
            if re.match(r"\s*[:>]", rest) or re.match(r"\s*" + VALUE, rest):    # '>>' / ':' or (OCR dropped them) a value
                ev.append((m.start(), m.end(), kind, "reply", None))
            else:
                ev.append((m.start(), m.end(), kind, "echo", None))
    for m in re.finditer(VALUE, text):
        ev.append((m.start(), m.end(), "value", "", value(m)))
    for m in re.finditer(FFID, text):
        ev.append((m.start(), m.end(), "id", "", m.group(1).upper().replace("O", "0")))
    for m in re.finditer(DECID, text):
        ev.append((m.start(), m.end(), "id", "", f"{int(m.group(1)):08X}"))
    ev.sort()
    out, last_end = [], -1
    for e in ev:                                             # a value inside a label or an id is not a value
        if e[2] == "value" and e[0] < last_end:
            continue
        out.append(e)
        last_end = max(last_end, e[1])
    return out


def session_start(ev, expect):
    """Text position of the echo of this session's first expected command (expect is in typing order): the n-th last
    echo of that command, n = how often the session typed it (getpos x, y, z: three getpos echoes). None when it is
    not on screen."""
    if not expect:
        return None
    first = KIND_OF[expect[0]]
    n = sum(1 for k in expect if KIND_OF[k] == first)
    echoes = [e[0] for e in ev if e[2] == first and e[3] == "echo"]
    return echoes[-n] if len(echoes) >= n else None


def read_order(ev, nums, start):
    """Values in typing order (see the module doc), or None."""
    vals = [e[4] for e in ev if e[2] == "value"]
    if len(vals) != len(nums) or start is None:
        return None
    replies = [e for e in ev if e[3] == "reply"]
    if any(e[0] < start for e in replies):                   # an older session's answer is still on screen
        return None
    got = [e[4] if e[2] == "pos" else e[2] for e in replies if e[2] != "self"]
    it = iter(nums)
    if not all(g in it for g in got):                        # the labels found are in the expected order
        return None
    out = dict(zip(nums, vals))
    if any(out[k] not in (0.0, 1.0) for k in ("isid", "disabled") if k in out):
        return None
    return out


def read_inline(text, nums, start):
    """Values right after their labels, after the session start only, or {}."""
    if start is None:
        return {}
    seg, out = text[start:], {}
    for k in nums:
        if k in ("isid", "disabled"):
            hits = [(m.start(), m) for m in re.finditer(LABELS[k] + "(?:" + ARROWS + r"|\s+)" + VALUE, seg, re.I)]
        else:
            # a reply has "Pos:" or an arrow after the axis ("getpos x" followed by a number is an echo)
            pat = LABELS["pos"] + rf"\s*(?::\s*{k}\b(?:{ARROWS}|\s+)|{k}(?:{ARROWS}))" + VALUE
            hits = [(m.start(), m) for m in re.finditer(pat, seg, re.I)]
        if hits:
            m = hits[-1][1]
            v = value(re.search(VALUE + r"$", m.group(0)))
            if k in ("isid", "disabled") and v not in (0.0, 1.0):
                continue
            out[k] = v
    return out


def read_self(ev, typed):
    """GetSelf's runtime id: an FFxxxxxx id after the last GetSelf echo. An id the session typed (prid <id>) counts
    only when it is on screen twice (the echoed argument and the reply)."""
    echoes = [e[0] for e in ev if e[2] == "self" and e[3] == "echo"]
    if not echoes:
        return None
    ids = [e[4] for e in ev if e[2] == "id" and e[0] > echoes[-1] and re.fullmatch(r"FF[0-9A-F]{6}", e[4])]
    every = [e[4] for e in ev if e[2] == "id"]
    typed = {t.upper() for t in typed}
    ids = [i for i in ids if i not in typed or every.count(i) >= 2]
    return ids[-1] if ids else None


def parse(raw, expect=("isid", "x", "y", "z", "self", "disabled"), typed=()):
    text = flat(raw)
    ev = events(text)
    expect = list(expect)
    nums = [k for k in expect if k != "self"]
    start = session_start(ev, expect)
    got, how = read_order(ev, nums, start), "order"
    if got is None:
        got, how = read_inline(text, nums, start), "inline"
    r = {k: got.get(k) for k in ("isid", "x", "y", "z", "disabled")}
    for k in ("isid", "disabled"):
        if r[k] is not None:
            r[k] = int(r[k])
    r["pos"] = " ".join(f"{r[k]:.2f}" for k in "xyz") if all(r[k] is not None for k in "xyz") else None
    r["self"] = read_self(ev, typed) if "self" in expect else None
    r["how"] = how if any(v is not None for v in got.values()) else ""
    r["ocr"] = text[:600]
    return r


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--expect", default="isid,x,y,z,self,disabled")
    ap.add_argument("--typed", default="")
    a = ap.parse_args(argv)
    expect = [k for k in a.expect.split(",") if k]
    if any(k not in KIND_OF for k in expect):              # empty: the OCR text only (the walk session)
        sys.exit(f"bad --expect {a.expect!r}")
    with open(a.text, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    print(json.dumps(parse(raw, expect, [t for t in a.typed.split(",") if t])))


if __name__ == "__main__":
    main()
