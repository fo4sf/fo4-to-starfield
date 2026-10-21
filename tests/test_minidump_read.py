"""Synthetic tests for scripts/game/minidump_read.py. No real dump: a minimal minidump is built byte by byte with a
module list, an exception stream with an x64 context, and a Memory64 list holding a few stack slots."""
import contextlib
import importlib.util
import io
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("minidump_read", ROOT / "scripts" / "game" / "minidump_read.py")
md = importlib.util.module_from_spec(spec)
spec.loader.exec_module(md)

BASE, SIZE = 0x7FF600000000, 0x5000000          # "Starfield.exe"
DLL, DLL_SIZE = 0x7FFA00000000, 0x100000        # "ntdll.dll"
RSP = 0x10000
GIB = 1 << 30


def build(memory_list=False):
    """A minidump: Starfield.exe and ntdll.dll, an access violation reading 0x3ca3d70a at Starfield.exe+0x2bf016b,
    and four stack slots at rsp: a plain number, ntdll+0x1234, Starfield.exe+0x10, and 0."""
    stack = struct.pack("<4Q", 42, DLL + 0x1234, BASE + 0x10, 0)
    names = [("C:\\Games\\Starfield.exe", BASE, SIZE, (1 << 16 | 16, 244 << 16)), ("C:\\Windows\\ntdll.dll", DLL, DLL_SIZE, (0, 0))]
    blob = bytearray(32 + 12 * 5)                # header, then up to 5 directory entries
    entries = []

    def add(payload):
        at = len(blob)
        blob.extend(payload)
        return at

    name_rvas = [add(struct.pack("<I", len(n.encode("utf-16-le"))) + n.encode("utf-16-le") + b"\0\0") for n, *_ in names]
    mods = struct.pack("<I", len(names))
    for (n, base, size, (ms, ls)), rva in zip(names, name_rvas):
        ffi = struct.pack("<13I", 0xFEEF04BD, 0x10000, ms, ls, *([0] * 9))
        mods += struct.pack("<QIIII", base, size, 0, 0, rva) + ffi + b"\0" * 32
    entries.append((md.MODULE_LIST, len(mods), add(mods)))
    ctx = bytearray(1232)
    regs = dict.fromkeys(md.REGS, 0)
    regs.update(rcx=0x3CA3D70A, r12=0x6666666666666600, rsp=RSP, rip=BASE + 0x2BF016B)
    struct.pack_into("<17Q", ctx, 0x78, *(regs[k] for k in md.REGS))
    ctx_rva = add(bytes(ctx))
    exc = struct.pack("<II", 7, 0) + struct.pack("<IIQQII", 0xC0000005, 0, 0, BASE + 0x2BF016B, 2, 0) \
        + struct.pack("<15Q", 0, 0x3CA3D70A, *([0] * 13)) + struct.pack("<II", len(ctx), ctx_rva)
    entries.append((md.EXCEPTION, len(exc), add(exc)))
    if memory_list:
        data_rva = add(stack)
        mem = struct.pack("<I", 1) + struct.pack("<QII", RSP, len(stack), data_rva)
        entries.append((md.MEMORY_LIST, len(mem), add(mem)))
    else:
        mem_at = len(blob)
        mem = struct.pack("<QQ", 1, mem_at + 16 + 16) + struct.pack("<QQ", RSP, len(stack))
        add(mem)
        add(stack)
        entries.append((md.MEMORY64_LIST, len(mem), mem_at))
    vm = bytearray(80)
    struct.pack_into("<QQ", vm, 8, 13 * GIB, 12 * GIB)            # peak working set, working set
    struct.pack_into("<QQQ", vm, 56, 14 * GIB, 15 * GIB, 14 * GIB)  # commit, peak commit, private
    entries.append((md.PROCESS_VM_COUNTERS, len(vm), add(bytes(vm))))
    sysmem = bytearray(160)
    struct.pack_into("<I", sysmem, 12, 4096)
    struct.pack_into("<4Q", sysmem, 128, GIB // 4096 // 2, 40 * GIB // 4096, 48 * GIB // 4096, 44 * GIB // 4096)
    entries.append((md.SYSTEM_MEMORY_INFO, len(sysmem), add(bytes(sysmem))))
    struct.pack_into("<4sIIIIIQ", blob, 0, b"MDMP", 0xA793, len(entries), 32, 0, 0, 0)
    for i, e in enumerate(entries):
        struct.pack_into("<III", blob, 32 + 12 * i, *e)
    return bytes(blob)


class MinidumpRead(unittest.TestCase):
    def test_exception_module_offset_registers_and_stack_scan(self):
        for memory_list in (False, True):
            d = md.Dump(build(memory_list))
            exc, regs = d.exception()
            self.assertEqual((exc["name"], exc["at"], exc["access"], exc["target"], exc["thread"]),
                             ("ACCESS_VIOLATION", "Starfield.exe+0x2bf016b", "read", "0x3ca3d70a", 7))
            self.assertEqual((regs["rcx"], regs["r12"]), (0x3CA3D70A, 0x6666666666666600))
            self.assertEqual([(o, w) for o, _v, w in d.stack_scan(regs["rsp"], 64)],
                             [(8, "ntdll.dll+0x1234"), (16, "Starfield.exe+0x10")])
            self.assertEqual(d.modules[0]["version"], "1.16.244.0")
            self.assertEqual(d.memory(), {"process": {"working_set": 12.0, "peak_working_set": 13.0, "commit": 14.0,
                                                      "peak_commit": 15.0, "private": 14.0},
                                          "system": {"available": 0.5, "commit": 40.0, "commit_limit": 48.0,
                                                     "peak_commit": 44.0}})

    def test_main_reports_each_dump_and_refuses_a_non_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad, out = (os.path.join(tmp, n) for n in ("a.dmp", "b.dmp", "out.json"))
            with open(good, "wb") as f:
                f.write(build())
            with open(bad, "wb") as f:
                f.write(b"not a dump")
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(md.main([good, bad, "--json", out]), 1)
            self.assertIn("ACCESS_VIOLATION (0xC0000005) at Starfield.exe+0x2bf016b (module version 1.16.244.0)",
                          text.getvalue())
            self.assertIn("not a minidump", text.getvalue())
            with open(out) as f:
                self.assertEqual([s["exception"]["at"] for s in json.load(f)], ["Starfield.exe+0x2bf016b"])


if __name__ == "__main__":
    unittest.main()
