"""Codsworth's voiced lines in Fallout 4 (read-only, PC): which RobotMrHandy voice files are his, with their text.

    python scripts/actors/codsworth_lines.py --esm "<FO4 Data>\\Fallout4.esm" --voices "<depot_377164>\\Data\\Fallout4 - Voices.ba2"
        --strings <dir with Fallout4_en.ILSTRINGS> --out <dir>

RobotMrHandy is shared by every Mr. Handy (5,177 .fuz, PC 2026-10-18), so an INFO counts as Codsworth's when its quest's
editor id contains "Codsworth" or one of its conditions is GetIsID (function 72) on his NPC_ 000179FF. Voice files are
sound\\voice\\fallout4.esm\\robotmrhandy\\<INFO id, 8 hex>_<response number>.fuz; only INFOs with a file are kept.
Layouts (UESP / xEdit FO4 definitions; checked against the file by the counts this prints): DIAL fields QNAM (quest),
SNAM (subtype, 4 chars); its INFOs sit in the following GRUP of type 7; INFO TRDT byte 12 = response number, NAM1 =
response text (an ILSTRINGS id in the localized Fallout4.esm), CTDA 32 bytes with the function index at byte 8 and
parameter 1 at byte 12. ILSTRINGS: u32 count, u32 data size, count x (u32 id, u32 offset), then u32 length + text.
Writes <out>/codsworth_lines.tsv and prints counts per quest and topic subtype plus a suggested first batch.
"""
import argparse
import os
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from fo4sf.ba2 import Ba2  # noqa: E402
from fo4sf.fo4land import Plugin, iter_items, iter_subrecords, record_data, zstring  # noqa: E402

CODSWORTH_NPC = 0x0179FF
GET_IS_ID = 72
VOICE_DIR = "sound\\voice\\fallout4.esm\\robotmrhandy\\"
FIRST_BATCH = ("HELO", "GREE", "IDAT", "IDLE", "HIT_", "ASNC", "AGRE")   # short ambient topics first


def read_ilstrings(data: bytes) -> dict:
    count, _size = struct.unpack_from("<II", data, 0)
    base = 8 + 8 * count
    out = {}
    for k in range(count):
        sid, off = struct.unpack_from("<II", data, 8 + 8 * k)
        ln, = struct.unpack_from("<I", data, base + off)
        out[sid] = data[base + off + 4:base + off + 4 + ln].split(b"\0", 1)[0].decode("cp1252", "replace")
    return out


def quests(p: Plugin) -> dict:
    span = p.top_group(b"QUST")
    out = {}
    if span:
        for item in iter_items(p.buf, *span):              # groups (quest children) are 5-tuples: skipped
            if item[0] == b"QUST":
                off, fid = item[1], item[3]
                out[fid] = next((zstring(d) for s, d in iter_subrecords(record_data(p.buf, off)) if s == b"EDID"), "")
    return out


def infos(p: Plugin):
    """Yield (quest id, topic subtype, topic editor id, INFO id, [(response number, text id)], GetIsID targets)."""
    span = p.top_group(b"DIAL")
    if not span:
        return
    topic = None
    for item in iter_items(p.buf, *span):
        if item[0] == b"DIAL":
            q, sub, edid = 0, "", ""
            for s, d in iter_subrecords(record_data(p.buf, item[1])):
                if s == b"QNAM":
                    q, = struct.unpack_from("<I", d)
                elif s == b"SNAM":
                    sub = bytes(d[:4]).decode("latin-1")
                elif s == b"EDID":
                    edid = zstring(d)
            topic = (q, sub, edid)
        elif item[0] == "GRUP" and item[4] == 7 and topic:
            for child in iter_items(p.buf, item[1] + 24, item[2]):
                if child[0] != b"INFO":
                    continue
                off, fid = child[1], child[3]
                responses, ids, number = [], [], None
                for s, d in iter_subrecords(record_data(p.buf, off)):
                    if s == b"TRDT" and len(d) > 12:
                        number = d[12]
                    elif s == b"NAM1" and len(d) >= 4 and number is not None:
                        responses.append((number, struct.unpack_from("<I", d)[0]))
                    elif s == b"CTDA" and len(d) >= 16:
                        func, = struct.unpack_from("<H", d, 8)
                        if func == GET_IS_ID:
                            ids.append(struct.unpack_from("<I", d, 12)[0])
                yield (*topic, fid, responses, ids)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--esm", required=True)
    ap.add_argument("--voices", required=True)
    ap.add_argument("--strings", required=True, help="folder holding Fallout4_en.ILSTRINGS")
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, default=20)
    a = ap.parse_args(argv)
    files = {e.name.lower().replace("/", "\\") for e in Ba2(a.voices).entries}
    with open(os.path.join(a.strings, "Fallout4_en.ILSTRINGS"), "rb") as f:
        text = read_ilstrings(f.read())
    rows = []
    with Plugin(a.esm) as p:
        qn = quests(p)
        for q, sub, edid, fid, responses, ids in infos(p):
            quest = qn.get(q, f"{q:08X}")
            if "codsworth" not in quest.lower() and CODSWORTH_NPC not in ids:
                continue
            for number, sid in responses:
                voice = f"{VOICE_DIR}{fid:08x}_{number}.fuz"
                if voice in files:
                    rows.append((quest, sub, edid, f"{fid:08X}", number, voice, text.get(sid, "")))
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "codsworth_lines.tsv"), "w", encoding="utf-8") as f:
        f.write("quest\tsubtype\ttopic\tinfo\tresponse\tvoice\ttext\n")
        for r in rows:
            f.write("\t".join(str(v) for v in r) + "\n")
    print(f"{len(rows)} voiced Codsworth responses")
    print("by quest:", dict(Counter(r[0] for r in rows).most_common(15)))
    print("by subtype:", dict(Counter(r[1] for r in rows).most_common(20)))
    batch = sorted((r for r in rows if r[1] in FIRST_BATCH and r[6]), key=lambda r: (FIRST_BATCH.index(r[1]), len(r[6])))
    print(f"suggested first batch ({min(a.batch, len(batch))}):")
    for r in batch[:a.batch]:
        print(f"  {r[3]}_{r[4]} {r[1]} {r[0]}: {r[6][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
