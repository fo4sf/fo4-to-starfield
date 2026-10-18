"""Codsworth line picker on a synthetic Fallout4.esm, voices BA2 and ILSTRINGS."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ba2_fixture import general_archive  # noqa: E402

spec = importlib.util.spec_from_file_location("codsworth_lines", ROOT / "scripts/actors/codsworth_lines.py")
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)


def field(sig, data):
    return sig + struct.pack("<H", len(data)) + data


def record(typ, fid, fields):
    body = b"".join(fields)
    return struct.pack("<4sIII", typ, len(body), 0, fid) + bytes(8) + body


def group(label, gtype, items):
    body = b"".join(items)
    return struct.pack("<4sI4si", b"GRUP", 24 + len(body), label, gtype) + bytes(8) + body


def info(fid, sid, ctda_npc=None, op=0, value=1.0):
    trdt = bytes(12) + b"\x01" + bytes(11)
    fields = [field(b"TRDT", trdt), field(b"NAM1", struct.pack("<I", sid))]
    if ctda_npc is not None:
        fields.append(field(b"CTDA", struct.pack("<B3xfH2xII", op << 5, value, 72, ctda_npc, 0) + bytes(12)))
    return record(b"INFO", fid, fields)


def ilstrings(table):
    data, idx = b"", b""
    for sid, s in table.items():
        enc = s.encode("cp1252") + b"\0"
        idx += struct.pack("<II", sid, len(data))
        data += struct.pack("<I", len(enc)) + enc
    return struct.pack("<II", len(table), len(data)) + idx + data


class CodsworthLinesTest(unittest.TestCase):
    def test_picks_codsworth_lines_with_files(self):
        esm = (record(b"TES4", 0, [field(b"HEDR", bytes(12))])
               + group(b"QUST", 0, [record(b"QUST", 0x100, [field(b"EDID", b"COMCodsworth\0")]),
                                    group(struct.pack("<I", 0x100), 10, [record(b"DLBR", 0x101, [])]),
                                    record(b"QUST", 0x200, [field(b"EDID", b"DialogueGeneric\0")])])
               + group(b"DIAL", 0, [
                   record(b"DIAL", 0x10, [field(b"EDID", b"CodsHello\0"), field(b"QNAM", struct.pack("<I", 0x100)),
                                          field(b"SNAM", b"HELO")]),
                   group(struct.pack("<I", 0x10), 7, [info(0x11, 1), group(b"\0\0\0\0", 7, []), info(0x12, 2)]),
                   record(b"DIAL", 0x20, [field(b"QNAM", struct.pack("<I", 0x200)), field(b"SNAM", b"IDAT")]),
                   group(struct.pack("<I", 0x20), 7, [info(0x21, 3, ctda_npc=0x0179FF), info(0x22, 4),
                                                       info(0x23, 4, ctda_npc=0x0179FF, value=0.0),
                                                       info(0x24, 4, ctda_npc=0x0179FF, op=1, value=0.0)]),
               ]))
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "Fallout4.esm").write_bytes(esm)
            (d / "Fallout4_en.ILSTRINGS").write_bytes(ilstrings({1: "Good morning, mum!", 2: "No file", 3: "Sir!", 4: "Generic"}))
            (d / "v.ba2").write_bytes(general_archive({
                "Sound\\Voice\\Fallout4.esm\\RobotMrHandy\\00000011_1.fuz": b"x",
                "Sound\\Voice\\Fallout4.esm\\RobotMrHandy\\00000021_1.fuz": b"x",
                "Sound\\Voice\\Fallout4.esm\\RobotMrHandy\\00000022_1.fuz": b"x",
                "Sound\\Voice\\Fallout4.esm\\RobotMrHandy\\00000023_1.fuz": b"x",
                "Sound\\Voice\\Fallout4.esm\\RobotMrHandy\\00000024_1.fuz": b"x"}))
            self.assertEqual(cl.main(["--esm", str(d / "Fallout4.esm"), "--voices", str(d / "v.ba2"), "--strings", str(d),
                                      "--out", str(d / "out")]), 0)
            rows = (d / "out" / "codsworth_lines.tsv").read_text(encoding="utf-8").splitlines()[1:]
        self.assertEqual([r.split("\t")[3] for r in rows], ["00000011", "00000021", "00000024"])
        # 12 has no file, 22 no condition, 23 GetIsID == 0 (excludes him); 24 GetIsID != 0 (him)
        self.assertTrue(rows[0].endswith("Good morning, mum!"))


if __name__ == "__main__":
    unittest.main()
