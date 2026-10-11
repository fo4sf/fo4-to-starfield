"""Parse the OCR'd console text of one npc_nav console session (qstep.ps1). Prints one JSON object:
{"isid": 1|0|null, "self": "FF0012AB"|null, "pos": "x y z"|null, "disabled": 1|0|null, "ocr": "<text>"}

Each session starts with ClearConsole, so normally only its own lines are on screen. In case the log was not cleared,
a value is only taken from the text after the LAST echo of its own command (the console echoes typed lines, e.g.
"GetIsID 0000CF96"), so a reply left over from an earlier session is never read as this session's; no echo, no value.
Positions are read only after a GetIsID echo: every position read of the actor confirms the selection first.
A reply needs '>>' / ':' before its value or a decimal value ("1.00"), so an echoed id is never read as a reply.
GetSelf's reply format is not known yet (FO4 style "GetSelf >> FF000D6E" assumed; parentheses, 0x, a bare id on the
next line and a decimal form id are accepted too); only ids of references created at runtime (FFxxxxxx) are returned."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_getpos import parse as parse_pos  # noqa: E402

ISID = r"Get\s?[Il1|]s\s?[Il1|]D"
ISID_ECHO = ISID + r"\s+[0-9A-FO]{8}\b"                     # the typed line: GetIsID <8 hex>
SELF = r"Get\s?Se[l1I|]f"
SELF_ECHO = SELF + r"(?!\s*[:>(])"                          # typed "GetSelf"; the reply goes on with '>>' or ':'
DISABLED = r"Get\s?Disab[l1I|]ed"
DISABLE_ECHO = r"(?<![A-Za-z])disable\b"                    # typed lower case; the reply label is "GetDisabled"


def after_last(raw, pattern, flags=0):
    """The text after the last match of pattern, or None when it does not occur."""
    ms = list(re.finditer(pattern, raw, flags))
    return raw[ms[-1].end():] if ms else None


def flat(s):
    return " ".join(s.split())


def flag(text, name):
    """Last 0/1 reply of a condition function, e.g. 'GetIsID >> 1.00' or 'GetIsID: 1.00' or 'GetIsID 1 00'."""
    hits = []
    for pat in (name + r"\s*:?\s*>\s*>?\s*([01])(?:\s*[\.,]\s*\d+)?\b",          # '>>' (or '>') before the value
                name + r"\s*[:\s]\s*([01])(?:\s*[\.,]\s*|\s)(\d\d)\b"):         # decimals (OCR may drop '>>')
        hits += [(m.start(), int(m.group(1))) for m in re.finditer(pat, text, re.I)]
    return max(hits)[1] if hits else None


def ref_id(text):
    """FFxxxxxx id from GetSelf's reply: hex (optional 0x / parentheses), a bare id right after the echo, or decimal."""
    found = []
    for m in re.finditer(SELF + r"\s*[:>\s]*\(?\s*(?:0x)?([0-9A-FO]{8})\b", text, re.I):
        found.append((m.start(), m.group(1).upper().replace("O", "0")))
    for m in re.finditer(SELF + r"\s*[:>\s]*(\d{10})(?:[\.,]\d+)?\b", text, re.I):
        found.append((m.start(), f"{int(m.group(1)):08X}"))
    m = re.match(r"\s*\(?\s*(?:0x)?([0-9A-FO]{8})\b", text, re.I)    # no label: the id is the next line
    if m:
        found.append((-1, m.group(1).upper().replace("O", "0")))
    ids = [v for _, v in sorted(found) if re.fullmatch(r"FF[0-9A-F]{6}", v)]
    return ids[-1] if ids else None


def parse(raw):
    isid_seg = after_last(raw, ISID_ECHO, re.I)
    self_seg = after_last(raw, SELF_ECHO, re.I)
    dis_seg = after_last(raw, DISABLE_ECHO)
    pos = parse_pos(isid_seg) if isid_seg is not None else "fail"
    return {"isid": flag(flat(isid_seg), ISID) if isid_seg is not None else None,
            "self": ref_id(flat(self_seg)) if self_seg is not None else None,
            "pos": None if pos == "fail" else pos,
            "disabled": flag(flat(dis_seg), DISABLED) if dis_seg is not None else None,
            "ocr": flat(raw)[:600]}


if __name__ == "__main__":
    print(json.dumps(parse(open(sys.argv[1], encoding="utf-8-sig", errors="replace").read())))
