"""recon_console.py decodes a console command entry from a synthetic PE32+ image built the way Starfield.exe 1.16.244
initialises its entries (lea rax / mov [rbp+d], rax; parameter count; static parameter table). No game file is read."""
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import recon_console  # noqa: E402

BASE = 0x140000000
SECS = {".text": (0x1000, 0x400), ".rdata": (0x2000, 0x800), ".data": (0x3000, 0xC00)}   # va, raw pointer; 0x400 each


def image():
    data = bytearray(0x1000)
    pe = 0x80
    struct.pack_into("<I", data, 0x3C, pe)
    data[pe:pe + 4] = b"PE\0\0"
    struct.pack_into("<HH", data, pe + 4, 0x8664, len(SECS))
    struct.pack_into("<H", data, pe + 20, 0xF0)
    struct.pack_into("<Q", data, pe + 24 + 24, BASE)
    for k, (name, (va, raw)) in enumerate(SECS.items()):
        s = pe + 24 + 0xF0 + 40 * k
        data[s:s + 8] = name.encode().ljust(8, b"\0")
        struct.pack_into("<IIII", data, s + 8, 0x400, va, 0x400, raw)
    strings = {}
    pos = 0x800 + 1
    for s in ("PathToRef", "PTR", "Force actor to path to reference.", "TESObjectREFR", "GetSelf",
              "Gets the ref ID for the current reference."):
        data[pos:pos + len(s)] = s.encode()
        strings[s] = 0x2000 + pos - 0x800
        pos += len(s) + 1
    struct.pack_into("<QII", data, 0xC00, BASE + strings["TESObjectREFR"], 4, 1)      # one optional reference
    code, va = bytearray(), 0x1000

    def lea(target):
        code.extend(b"\x48\x8d\x05" + struct.pack("<i", target - (va + len(code) + 7)))

    def store(d):
        code.extend(b"\x48\x89\x85" + struct.pack("<i", d))
    lea(strings["PathToRef"])
    code.extend(b"\xc7\x85" + struct.pack("<iI", 0x3D20, 0x1D0))                      # opcode
    store(0x3D10)
    lea(strings["PTR"])
    store(0x3D18)
    lea(strings["Force actor to path to reference."])
    store(0x3D28)
    code.extend(b"\xb8\x01\x00\x00\x00" + b"\x66\x89\x85" + struct.pack("<i", 0x3D32))   # one parameter
    lea(0x3000)
    store(0x3D38)
    code.extend(b"\xc3")
    data[0x400:0x400 + len(code)] = code
    return bytes(data)


class ReconConsoleTests(unittest.TestCase):
    def test_decodes_a_command_entry(self):
        img = recon_console.Image(image())
        got = img.commands(["PathToRef", "GetSelf"])
        self.assertEqual(len(got), 1)                       # GetSelf has no console entry here (a script function)
        c = got[0]
        self.assertEqual((c["short"], c["opcode"], c["help"]), ("PTR", 0x1D0, "Force actor to path to reference."))
        self.assertEqual(c["params"], [{"type": "TESObjectREFR", "id": 4, "optional": True}])
        self.assertEqual(img.near("GetSelf")[0][-1], "Gets the ref ID for the current reference.")

    def test_cli_reads_the_file_only(self):
        p = os.path.join(tempfile.mkdtemp(), "fake.exe.bin")
        with open(p, "wb") as f:
            f.write(image())
        before = os.path.getmtime(p)
        self.assertEqual(recon_console.main([p, "PathToRef,Nope"]), 0)
        self.assertEqual(os.path.getmtime(p), before)


if __name__ == "__main__":
    unittest.main()
