"""recon_console.py decodes a console command entry from a synthetic PE32+ image built the way Starfield.exe 1.16.244
initialises its entries (lea rax / mov [rbp+d], rax; parameter count; static parameter table), and the script-function
table's entries, which it stores through the stack pointer (mov [rsp+d], rax). No game file is read."""
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
try:                                   # recon_console.py scans with numpy (the runner's venv); CI has none
    import recon_console  # noqa: E402
except ImportError:
    recon_console = None

BASE = 0x140000000
SECS = {".text": (0x1000, 0x400), ".rdata": (0x2000, 0x800), ".data": (0x3000, 0xC00)}   # va, raw pointer; 0x400 each
IMPULSE_HELP = "Applies an impulse of the passed magnitude to the reference along a passed axis."


def image(rsp=False):
    """rsp=True: the entry is stored through the stack pointer, as Starfield.exe 1.16.244 builds its script-function
    table (ApplyHavokImpulse: four Float parameters, opcode 0x1251, the byte at +0x20 set)."""
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
              "Gets the ref ID for the current reference.", "ApplyHavokImpulse", IMPULSE_HELP, "Float"):
        data[pos:pos + len(s)] = s.encode()
        strings[s] = 0x2000 + pos - 0x800
        pos += len(s) + 1
    struct.pack_into("<QII", data, 0xC00, BASE + strings["TESObjectREFR"], 4, 1)      # one optional reference
    for k in range(4):                                                                 # four required floats
        struct.pack_into("<QII", data, 0xC40 + 16 * k, BASE + strings["Float"], 2, 0)
    code, va = bytearray(), 0x1000

    def lea(target):
        code.extend(bytes([0x48, 0x8D, 0x05]) + struct.pack("<i", target - (va + len(code) + 7)))

    if rsp:
        def store(d):                                    # mov [rsp+d32], rax
            code.extend(bytes([0x48, 0x89, 0x84, 0x24]) + struct.pack("<i", d))
        lea(strings["ApplyHavokImpulse"])
        store(0xCD10)
        code.extend(bytes([0xC7, 0x84, 0x24]) + struct.pack("<iI", 0xCD20, 0x1251))       # opcode
        lea(strings[IMPULSE_HELP])
        store(0xCD28)
        code.extend(bytes([0xC6, 0x84, 0x24]) + struct.pack("<i", 0xCD30) + bytes([1]))   # the byte at +0x20
        code.extend(bytes([0xB8, 4, 0, 0, 0, 0x66, 0x89, 0x84, 0x24]) + struct.pack("<i", 0xCD32))   # four parameters
        lea(0x3040)
        store(0xCD38)
    else:
        def store(d):                                    # mov [rbp+d32], rax
            code.extend(bytes([0x48, 0x89, 0x85]) + struct.pack("<i", d))
        lea(strings["PathToRef"])
        code.extend(bytes([0xC7, 0x85]) + struct.pack("<iI", 0x3D20, 0x1D0))              # opcode
        store(0x3D10)
        lea(strings["PTR"])
        store(0x3D18)
        lea(strings["Force actor to path to reference."])
        store(0x3D28)
        code.extend(bytes([0xB8, 1, 0, 0, 0, 0x66, 0x89, 0x85]) + struct.pack("<i", 0x3D32))   # one parameter
        lea(0x3000)
        store(0x3D38)
    code.extend(bytes([0xC3]))
    data[0x400:0x400 + len(code)] = code
    return bytes(data)


@unittest.skipUnless(recon_console, "numpy not installed")
class ReconConsoleTests(unittest.TestCase):
    def test_decodes_a_command_entry(self):
        img = recon_console.Image(image())
        got = img.commands(["PathToRef", "GetSelf"])
        self.assertEqual(len(got), 1)                       # GetSelf has no console entry here (a script function)
        c = got[0]
        self.assertEqual((c["short"], c["opcode"], c["help"]), ("PTR", 0x1D0, "Force actor to path to reference."))
        self.assertEqual(c["params"], [{"type": "TESObjectREFR", "id": 4, "optional": True}])
        ctx = img.near("GetSelf")[0]
        self.assertEqual(ctx[ctx.index("GetSelf") + 1], "Gets the ref ID for the current reference.")

    def test_decodes_a_stack_pointer_entry(self):
        # the script-function table (ApplyHavokImpulse, SetRigidBodyMass, SetPos) is stored through rsp, not rbp
        img = recon_console.Image(image(rsp=True))
        got = img.commands(["ApplyHavokImpulse", "PathToRef"])
        self.assertEqual(len(got), 1)
        c = got[0]
        self.assertEqual((c["name"], c["short"], c["opcode"], c["help"]), ("ApplyHavokImpulse", None, 0x1251, IMPULSE_HELP))
        self.assertEqual(c["params"], [{"type": "Float", "id": 2, "optional": False}] * 4)

    def test_cli_reads_the_file_only(self):
        p = os.path.join(tempfile.mkdtemp(), "fake.exe.bin")
        with open(p, "wb") as f:
            f.write(image())
        before = os.path.getmtime(p)
        self.assertEqual(recon_console.main([p, "PathToRef,Nope"]), 0)
        self.assertEqual(os.path.getmtime(p), before)


if __name__ == "__main__":
    unittest.main()
