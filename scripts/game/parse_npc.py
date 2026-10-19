"""Parse the OCR'd console text of one npc_nav console session (qstep.ps1). Prints one JSON object:
{"ref": "FF010D65"|null, "isid": 1|0|null, "x"/"y"/"z": float|null, "pos": "x y z"|null, "disabled": 1|0|null,
 "incell": 1|0|null, "combat": 0..9|null, "target": "00000014"|null, "los": 1|0|null,
 "self": "FF010D65"|"0024A824"|null, "how": "order"|"inline"|"", "ocr": "<text>"}

usage: parse_npc.py <ocr text file> [--expect ref,isid,x,y,z] [--typed FF010D65]
  --expect  what this session's commands produce, in the order they were typed: ref (plr: the id in PickLastRef's
            reply), isid (GetIsID), x / y / z (getpos x/y/z), disabled (GetDisabled), self (GetSelf: the id of the
            console's selection, any form id), incell (player.GetInCell <cell>: door_trip, a condition function's
            reply like GetIsID's, "GetInCell >> 1.00": supported hypothesis, not yet seen in game),
            combat (GetCombatState: the game prints "The actor's combat state: 2.00" on the line after the echo;
            ">> n" is also read), target (GetCombatTarget: "GetCombatTarget >> (00000014)", or bare / 0x), los
            (GetLineOfSight player: "<actor> sees <player>" = 1, "<actor> can't see <player>" = 0; ">> 1" also
            read). Formats verified in game on 2026-10-15 (npc_combat_c1_1015); what does not parse stays null and
            the raw OCR is kept, never a guess
  --typed   ids this session typed itself (prid <id>, GetIsID <npc>): such an id counts as GetSelf's reply only when it
            is on screen twice, and never as GetCombatTarget's

What the console shows (runner sessions of 2026-10-11, N0_base in QASmoke: OCR texts and captures):
  - about nine lines. ClearConsole does NOT clear them: its echo stands below the older lines (N0_base's last capture:
    "GetPos: X >> -7.82 ... GetPos: Z >> 0.00" of the previous session above "ClearConsole / disable / GetDisabled >> 1").
    Every qstep session types ClearConsole first, so its last echo on screen marks where this session begins;
  - lines the game prints itself: three "GetInFaction >> 0.00" right after "player.placeatme 002B211C 1";
  - replies: "PickLastRef: (FF010D65)", "GetIsID >> 0.00", "GetSelf >> (0024a824)", "GetPos: X >> -7.82",
    "GetDisabled >> 1" (an integer, unlike GetIsID's 0.00 / 1.00);
  - OCR quirks: l / 1 / | for I ("GetlsID 002B211C", "GetlslD 0.00", "GetlnFaction"), split words ("Get Po s",
    "Clear Console", "Get Disabled"), "-7 82" for -7.82, '>>' read as "> >" or lost.
Two layouts of the same lines:
  inline: "GetIsID > > 1.00", "Get Pos: X > > -10.07"            each value right after its label;
  column: "Get Pos: X > > ... Get Pos: Z > > ... -10.07 43.95 z -10.95"   all labels first, then all values, with
          command arguments that left their echo ("player.getpos y" read as "player.getpos", x / z in the value column).

Session start: the later of (a) the last ClearConsole echo on screen and (b) the echo of this session's first expected
command (the n-th last echo of it, n = how often the session typed it). Nothing before it is ever read: not the older
lines ClearConsole left on screen, not a reply of the previous session whose echo this session repeats.
Two readings of the values, the first that holds is used:
  order:  the session's values are the decimals after the session start in typing order. It holds only when there are
          exactly as many as the session expects, no '>>' stands before the session start (in the column layout the
          values of older lines would be counted), no more '>>' follow than this session's own reply labels (a line the
          game printed itself) and the labels found are in the expected order. A GetIsID / GetDisabled value other than
          0 or 1 means the numbers are misaligned: the reading is dropped.
  inline: label, '>>' / ':' and value next to each other, after the session start; for GetIsID / GetDisabled also an
          integer 0 / 1 after '>>' or ':'.
Numbers are decimals as the console prints them ("-10.07"; OCR quirks "-0 85" and "1 00" for "-0.85" and "1.00");
form ids and other integers (an echoed "placeatme 0000CF96 1") are never values.
ref: the last FFxxxxxx id after the last PickLastRef label of this session (qstep types plr alone in its session, so
that is PickLastRef's own reply in both layouts). self: the last id after this session's GetSelf echo: FFxxxxxx, a
parenthesised or 0x form id ("(0024a824)": the static the console had selected) or a decimal runtime id. In ids,
O / o read for 0 and l / I / | for 1 are mapped back. Whether an id is the actor's is decided by qstep.ps1 (GetSelf
must not name another ref than PickLastRef, GetIsID 1, position at the player).
"""
import argparse
import json
import re
import sys

I_ = r"[Il1|]"                                               # OCR reads I as l, 1 or | (re.I: also i and L)
LABELS = {                                                   # command name as echoed and as the reply's label
    "isid": rf"Get\s?{I_}s\s?{I_}D",
    "self": rf"Get\s?Se{I_}f",
    "disabled": rf"Get\s?D{I_}sab{I_}ed",
    "pos": r"Get\s?Po\s?s",
    "ref": rf"P{I_}ck\s?{I_}ast\s?Ref",                      # only the game writes PickLastRef: qstep types plr
    "incell": rf"Get\s?{I_}n\s?Ce{I_}{I_}",                      # GetInCell (door_trip): "GetInCell >> 1.00"
    "combat": r"Get\s?Combat\s?State",                           # npc_nav combat_reads: formats unverified in game
    "target": r"Get\s?Combat\s?Target",
    "los": rf"Get\s?L{I_}ne\s?Of\s?S{I_}ght",
}
CLEAR = rf"C{I_}ear\s?Conso{I_}e"                            # ClearConsole's echo: this session's first line
PLR = rf"(?<![\w.])p{I_}r(?!\w)"                             # plr's echo
ARROWS = r"\s*(?::\s*)?(?:>\s*)+|\s*:\s*"                    # '>>', '> >', ':' or ': >>' between label and value
VALUE = r"(?<![\w.,])(-\s?)?(\d{1,6})(?:\s?[.,]\s?(\d{1,3})|\s(\d{2}))(?![\w.,])"
FLAG = r"(?<![\w.,])([01])(?![\w.,])"                         # an integer reply: "GetDisabled >> 1"
SMALL = r"(?<![\w.,])(\d)(?![\w.,])"                          # a small integer reply: "GetCombatState >> 1"
HEX = r"[0-9A-Fa-fOoIl|]"                                    # a hex digit as OCR may read it
# the FF may be read apart from the rest: "PickLastRef (F F 01102B)" (movable_1019c 0001 / 0003, 2026-10-18)
FFID = rf"(?<![0-9A-Za-z])(?:0x)?\(?\s*([Ff] ?[Ff] ?{HEX}{{6}})\s*\)?(?![0-9A-Za-z])"
ANYID = rf"\(\s*({HEX}{{8}})\s*\)|(?<![0-9A-Za-z])0x({HEX}{{8}})(?![0-9A-Za-z])"   # "(0024a824)", "0x0024a824"
DECID = r"(?<![\w.,])(42\d{8})(?:[.,]\d+)?(?![\w])"         # FF000000..FFFFFFFF written in decimal
# GetCombatTarget's reply as it may be written: "(00000014)", "0x00000014" or bare "00000014" (the player: 00000014)
TARGET_ID = rf"(?<![0-9A-Za-z])(?:0x)?\(?\s*({HEX}{{8}})\s*\)?(?![0-9A-Za-z])"
KIND_OF = {"ref": "ref", "isid": "isid", "x": "pos", "y": "pos", "z": "pos", "disabled": "disabled", "self": "self",
           "incell": "incell", "combat": "combat", "target": "target", "los": "los"}
FLAGS = ("isid", "disabled", "incell", "los")
IDS = ("self", "ref", "target")                              # replies that are ids, not numbers
SMALLS = ("combat",)                                         # replies that are a small integer 0..9


def flat(s):
    return " ".join(s.split())


def value(m):
    sign, whole, frac, frac2 = m.group(1), m.group(2), m.group(3), m.group(4)
    v = float(whole + "." + (frac if frac is not None else frac2))
    return -v if sign else v


def hexid(s):
    return s.upper().replace(" ", "").replace("O", "0").replace("I", "1").replace("L", "1").replace("|", "1")


def events(text):
    """[(start, end, kind, role, data)] in text order. kind: isid / self / disabled / pos / ref / clear / value / id;
    role for the command names: 'echo' (what was typed) or 'reply' (the label of the game's answer); data: the axis of
    a GetPos reply, the number of a value, the id."""
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
            if kind == "ref" or re.match(r"\s*[:>]", rest) or re.match(r"\s*" + VALUE, rest):
                ev.append((m.start(), m.end(), kind, "reply", None))   # '>>' / ':' or (OCR dropped them) a value
            else:
                ev.append((m.start(), m.end(), kind, "echo", None))
    for m in re.finditer(PLR, text, re.I):
        ev.append((m.start(), m.end(), "ref", "echo", None))
    for m in re.finditer(CLEAR, text, re.I):
        ev.append((m.start(), m.end(), "clear", "echo", None))
    for m in re.finditer(VALUE, text):
        ev.append((m.start(), m.end(), "value", "", value(m)))
    ids = {}
    for m in re.finditer(FFID, text):
        ids[m.start()] = (m.start(), m.end(), "id", "", hexid(m.group(1)))
    for m in re.finditer(ANYID, text):
        if not any(s <= m.start() < e or m.start() <= s < m.end() for s, e, *_ in ids.values()):
            ids[m.start()] = (m.start(), m.end(), "id", "", hexid(m.group(1) or m.group(2)))
    for m in re.finditer(DECID, text):
        ids[m.start()] = (m.start(), m.end(), "id", "", f"{int(m.group(1)):08X}")
    ev += ids.values()
    ev.sort()
    out, last_end = [], -1
    for e in ev:                                             # a value inside a label or an id is not a value
        if e[2] == "value" and e[0] < last_end:
            continue
        out.append(e)
        last_end = max(last_end, e[1])
    return out


def session_start(ev, expect):
    """(start, begin): start = where this session's own lines begin (module doc), begin = the end of the last
    ClearConsole echo; either None when not on screen."""
    clears = [e[1] for e in ev if e[2] == "clear"]
    begin = clears[-1] if clears else None
    first = None
    if expect:
        kind = KIND_OF[expect[0]]
        n = sum(1 for k in expect if KIND_OF[k] == kind)
        echoes = [e[0] for e in ev if e[2] == kind and e[3] == "echo"]
        if len(echoes) >= n:
            first = echoes[-n]
    found = [p for p in (begin, first) if p is not None]
    return (max(found) if found else None), begin


def read_order(ev, text, nums, start):
    """Values in typing order (see the module doc), or None."""
    if start is None or not nums:
        return None
    vals = [e[4] for e in ev if e[2] == "value" and e[0] >= start]
    if len(vals) != len(nums):
        return None
    replies = [e for e in ev if e[3] == "reply"]
    if any(e[0] < start for e in replies):                   # an older session's answer is still on screen
        return None
    arrows = [m.start() for m in re.finditer(r">\s*>", text)]
    if any(a < start for a in arrows) or len(arrows) > len(replies):   # older lines, or a line the game printed
        return None
    got = [e[4] if e[2] == "pos" else e[2] for e in replies if e[2] not in IDS]
    it = iter(nums)
    if not all(g in it for g in got):                        # the labels found are in the expected order
        return None
    out = dict(zip(nums, vals))
    if any(out[k] not in (0.0, 1.0) for k in FLAGS if k in out):
        return None
    if any(not (0.0 <= out[k] <= 9.0 and out[k] == int(out[k])) for k in SMALLS if k in out):
        return None
    return out


def read_inline(text, nums, start):
    """Values right after their labels, after the session start only, or {}."""
    if start is None:
        return {}
    seg, out = text[start:], {}
    for k in nums:
        if k in FLAGS or k in SMALLS:
            hits = [(m.start(), value(re.search(VALUE + r"$", m.group(0))))
                    for m in re.finditer(LABELS[k] + "(?:" + ARROWS + r"|\s+)" + VALUE, seg, re.I)]
            hits += [(m.start(), float(m.group(m.lastindex)))          # integer replies need the '>>' or ':'
                     for m in re.finditer(LABELS[k] + "(?:" + ARROWS + ")" + (FLAG if k in FLAGS else SMALL), seg, re.I)]
        else:
            # a reply has "Pos:" or an arrow after the axis ("getpos x" followed by a number is an echo)
            pat = LABELS["pos"] + rf"\s*(?::\s*{k}\b(?:{ARROWS}|\s+)|{k}(?:{ARROWS}))" + VALUE
            hits = [(m.start(), value(re.search(VALUE + r"$", m.group(0)))) for m in re.finditer(pat, seg, re.I)]
        if hits:
            v = max(hits)[1]                                  # the last reply on screen
            if k in FLAGS and v not in (0.0, 1.0):
                continue
            if k in SMALLS and not (0.0 <= v <= 9.0 and v == int(v)):
                continue
            out[k] = v
    return out


def read_ref(ev, start):
    """PickLastRef's id: the last FFxxxxxx id after the last PickLastRef label of this session, or None."""
    if start is None:
        return None
    labels = [e[1] for e in ev if e[2] == "ref" and e[3] == "reply" and e[0] >= start]
    if not labels:
        return None
    ids = [e[4] for e in ev if e[2] == "id" and e[0] >= labels[-1] and re.fullmatch(r"FF[0-9A-F]{6}", e[4])]
    return ids[-1] if ids else None


def read_self(ev, typed, start, begin):
    """GetSelf's reply: the last id after this session's last GetSelf echo. An id the session typed (prid <id>) counts
    only when it is on screen twice since the session's ClearConsole (the echoed argument and the reply)."""
    echoes = [e[0] for e in ev if e[2] == "self" and e[3] == "echo" and (start is None or e[0] >= start)]
    if not echoes:
        return None
    ids = [e[4] for e in ev if e[2] == "id" and e[0] > echoes[-1] and re.fullmatch(r"[0-9A-F]{8}", e[4])]
    every = [e[4] for e in ev if e[2] == "id" and (begin is None or e[0] >= begin)]
    typed = {t.upper() for t in typed}
    ids = [i for i in ids if i not in typed or every.count(i) >= 2]
    return ids[-1] if ids else None


def read_target(ev, text, typed, start):
    """GetCombatTarget's reply: the last form id after this session's last GetCombatTarget label (echo or reply),
    never an id the session typed itself (prid <id>, GetIsID <npc>: in the column layout their arguments drift into
    the value column). None when there is no label or no id after it: the format is unverified in game."""
    if start is None:
        return None
    labels = [e[1] for e in ev if e[2] == "target" and e[0] >= start]
    if not labels:
        return None
    typed = {t.upper() for t in typed}
    ids = [hexid(m.group(1)) for m in re.finditer(TARGET_ID, text[labels[-1]:])]
    ids = [i for i in ids if re.fullmatch(r"[0-9A-F]{8}", i) and i not in typed]
    return ids[-1] if ids else None


def parse(raw, expect=("isid", "x", "y", "z", "self", "disabled"), typed=()):
    text = flat(raw)
    ev = events(text)
    expect = list(expect)
    nums = [k for k in expect if k not in IDS]
    start, begin = session_start(ev, expect)
    got, how = read_order(ev, text, nums, start), "order"
    if got is None:
        got, how = read_inline(text, nums, start), "inline"
    r = {k: got.get(k) for k in ("isid", "x", "y", "z", "disabled", "incell", "combat", "los")}
    # the combat replies as the game really prints them (npc_combat_c1_1015, 2026-10-15, OCR of every sample):
    # GetCombatState answers "The actor's combat state: 2.00" on the line after its echo (never ">> n");
    # GetLineOfSight player answers "<actor> sees <player>" / "<actor> can't see <player>" (the actor's and the
    # player's names). GetCombatTarget's ">> (00000014)" was as hypothesised. Only after the session start, last one.
    seg = text[start:] if start is not None else ""
    if "combat" in expect and r["combat"] is None:
        hits = [float(m.group(1)) for m in re.finditer(r"combat\s?state\s*[:;]\s*(\d)(?:[.,]\s?\d{1,2})?\b", seg, re.I)]
        if hits:
            r["combat"] = hits[-1]
    if "los" in expect and r["los"] is None:
        hits = [m.group(1).lower() for m in re.finditer(r"\b(sees|can.?t\s?see|cannot\s?see|does\s?n.?t\s?see)\b", seg, re.I)]
        if hits:
            r["los"] = 1.0 if hits[-1] == "sees" else 0.0
    for k in FLAGS + SMALLS:
        if r[k] is not None:
            r[k] = int(r[k])
    r["pos"] = " ".join(f"{r[k]:.2f}" for k in "xyz") if all(r[k] is not None for k in "xyz") else None
    r["ref"] = read_ref(ev, start) if "ref" in expect else None
    r["self"] = read_self(ev, typed, start, begin) if "self" in expect else None
    r["target"] = read_target(ev, text, typed, start) if "target" in expect else None
    r["how"] = how if any(v is not None for v in got.values()) else ""
    if "incell" in expect:
        # the console's refusal (first live door_trip run, 2026-10-13: "Item 'FO4Port_RedRocket01' not found for
        # parameter Cell." and "Compiled script not saved!", OCR'd "pararneter", "Cornpiled"): the cell was not
        # resolved, so there is no answer; never a 0
        seg = text[start:] if start is not None else text
        m = re.search(r"not\s?found\s?for\s?par\w{0,9}\s?Ce[l1I|]{2}|Co\w{1,3}p[il1|]{1,2}ed\s?scr[il1|]pt\s?not\s?saved",
                      seg, re.I)
        r["incell_error"] = ("not found for parameter Cell" if m and "found" in m.group(0).lower()
                             else "compiled script not saved" if m else None)
        if m:
            r["incell"] = None
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
