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


def build(memory_list=False, vm_flags=0x7, sys_flags=0x2, extra=(), regs_extra=None):
    """A minidump: Starfield.exe and ntdll.dll, an access violation reading 0x3ca3d70a at Starfield.exe+0x2bf016b,
    and four stack slots at rsp: a plain number, ntdll+0x1234, Starfield.exe+0x10, and 0. extra adds captured memory
    (address, bytes) after the stack; regs_extra sets more registers."""
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
    regs.update(rcx=0x3CA3D70A, r12=0x6666666666666600, rsp=RSP, rip=BASE + 0x2BF016B, **(regs_extra or {}))
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
        ranges = [(RSP, stack)] + list(extra)
        mem = struct.pack("<QQ", len(ranges), mem_at + 16 + 16 * len(ranges))
        mem += b"".join(struct.pack("<QQ", a, len(b)) for a, b in ranges)
        add(mem)
        for _a, b in ranges:
            add(b)
        entries.append((md.MEMORY64_LIST, len(mem), mem_at))
    vm = bytearray(96)                                             # MINIDUMP_PROCESS_VM_COUNTERS_2
    struct.pack_into("<HH", vm, 0, 2, vm_flags)
    struct.pack_into("<QQ", vm, 8, 13 * GIB, 12 * GIB)            # peak working set, working set
    struct.pack_into("<QQ", vm, 56, 14 * GIB, 15 * GIB)           # commit, peak commit
    struct.pack_into("<QQQ", vm, 72, 200 * GIB, 100 * GIB, 13 * GIB)  # peak virtual, virtual, private
    entries.append((md.PROCESS_VM_COUNTERS, len(vm), add(bytes(vm))))
    sysmem = bytearray(160)
    struct.pack_into("<HH", sysmem, 0, 1, sys_flags)
    struct.pack_into("<II", sysmem, 4, 156250, 4096)              # 4-byte packed: TimerResolution, PageSize
    struct.pack_into("<I", sysmem, 12, 8 << 20)                   # NumberOfPhysicalPages (an unpacked read sees it)
    struct.pack_into("<4Q", sysmem, 116, GIB // 4096 // 2, 40 * GIB // 4096, 48 * GIB // 4096, 44 * GIB // 4096)
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
                                                      "peak_commit": 15.0, "virtual": 100.0, "private": 13.0},
                                          "system": {"available": 0.5, "commit": 40.0, "commit_limit": 48.0,
                                                     "peak_commit": 44.0}})

    def test_memory_fields_follow_the_stream_flags(self):
        # Codex on #451: revision 2 puts PeakVirtualSize at 72; PrivateUsage (88) needs flag 0x4, and the system's
        # basic performance numbers need MINIDUMP_SYSMEMINFO1_BASICPERF (0x2)
        mem = md.Dump(build(vm_flags=0x1, sys_flags=0x0)).memory()
        self.assertEqual(sorted(mem), ["process"])
        self.assertEqual(sorted(mem["process"]), ["commit", "peak_commit", "peak_working_set", "working_set"])
        self.assertEqual(md.Dump(build(vm_flags=0x0)).memory().get("process"), None)

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


TEXT, RDATA, PDATA = 0x2BF0000, 0x4000000, 0x4001000   # section RVAs in the synthetic exe
IMAGE_BASE = 0x140000000                                 # the file's preferred base; the dump's is BASE (ASLR)
VTABLE = RDATA + 0x100                                   # a vtable whose locator names "BSGeometry"
HEAP = 0x198B55AC188                                     # rdi's object: its first qword is that vtable


def build_exe():
    """A PE32+ "Starfield.exe" with SizeOfImage SIZE: .text holding the fault and a call before Starfield.exe+0x2bf0200,
    .rdata holding a complete object locator, its type descriptor and the vtable, and .pdata with one function
    (0x2bf0100 to 0x2bf0300)."""
    head = bytearray(0x400)
    head[:2] = b"MZ"
    struct.pack_into("<I", head, 0x3C, 0x80)
    head[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", head, 0x84, 0x8664, 3)                # machine, sections
    struct.pack_into("<H", head, 0x80 + 20, 240)                  # optional header size
    opt = 0x80 + 24
    struct.pack_into("<H", head, opt, 0x20B)
    struct.pack_into("<Q", head, opt + 24, IMAGE_BASE)
    struct.pack_into("<I", head, opt + 56, SIZE)
    struct.pack_into("<II", head, opt + 112 + 24, PDATA, 12)
    text = bytearray(0x1000)
    text[0x16B] = 0x8B                                           # the fault byte, for the code window
    text[0x1FB:0x200] = b"\xE8\0\0\0\0"                          # call rel32, returning to +0x2bf0200
    rdata = bytearray(0x1000)
    col, td = RDATA + 0x10, RDATA + 0x40
    struct.pack_into("<IIIIII", rdata, 0x10, 1, 0, 0, td, 0, col)
    rdata[0x50:0x50 + 17] = b".?AVBSGeometry@@\0"
    struct.pack_into("<Q", rdata, 0xF8, IMAGE_BASE + col)        # vtable[-1]: the locator, against ImageBase
    pdata = struct.pack("<III", TEXT + 0x100, TEXT + 0x300, 0)
    body, sections = bytes(head), []
    for va, data in ((TEXT, bytes(text)), (RDATA, bytes(rdata)), (PDATA, pdata)):
        sections.append((va, len(data), len(body)))
        body += data
    body = bytearray(body)
    for i, (va, n, off) in enumerate(sections):
        struct.pack_into("<IIII", body, opt + 240 + 40 * i + 8, n, va, n, off)
    return bytes(body)


class MinidumpWithExe(unittest.TestCase):
    def dump(self):
        obj = struct.pack("<QQ", BASE + VTABLE, 0)
        return build(extra=[(HEAP, obj)], regs_extra={"rdi": HEAP, "r13": HEAP + 8})

    def test_function_call_check_and_rtti(self):
        img = md.Image(build_exe())
        self.assertEqual(img.function(TEXT + 0x16B), TEXT + 0x100)
        self.assertIsNone(img.function(TEXT + 0x50))               # before the one .pdata entry
        self.assertEqual(img.function(TEXT + 0x200), TEXT + 0x100)
        self.assertTrue(img.after_call(TEXT + 0x200))
        self.assertFalse(img.after_call(TEXT + 0x180))
        self.assertEqual(md.rtti_name(img, BASE, BASE + VTABLE), ".?AVBSGeometry@@")
        self.assertIsNone(md.rtti_name(img, BASE, BASE + RDATA + 0x200))   # no locator before it
        self.assertIsNone(md.rtti_name(img, BASE, 0x3CA3D70A))               # rcx's float is not a vtable

    def test_call_forms(self):
        self.assertEqual(md._modrm_length(bytes([0xD0])), 1)               # call rax
        self.assertEqual(md._modrm_length(bytes([0x15, 0, 0, 0, 0])), 5)   # call [rip+disp32]
        self.assertEqual(md._modrm_length(bytes([0x50, 8])), 2)            # call [rax+disp8]
        self.assertEqual(md._modrm_length(bytes([0x54, 0x24, 8])), 3)      # call [rsp+disp8], with SIB

    def test_main_with_exe_names_the_object_and_the_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            dmp, exe, out = (os.path.join(tmp, n) for n in ("a.dmp", "Starfield.exe", "out.json"))
            with open(dmp, "wb") as f:
                f.write(self.dump())
            with open(exe, "wb") as f:
                f.write(build_exe())
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(md.main([dmp, "--exe", exe, "--json", out]), 0)
            self.assertIn("object rdi        0x198b55ac188  .?AVBSGeometry@@", text.getvalue())
            with open(out) as f:
                im = json.load(f)[0]["image"]
            self.assertEqual(im["code"]["from"], "Starfield.exe+0x2bf012b")
            self.assertEqual(bytes.fromhex(im["code"]["hex"])[64], 0x8B)
            self.assertEqual([o["in"] for o in im["objects"]], ["rdi"])     # r13 points past the vtable qword

    def test_code_from_the_function_start(self):
        img = md.Image(build_exe())
        im = md._summary("a.dmp", md.Dump(self.dump()), 64, img, -1)["image"]
        self.assertEqual((im["code"]["from"], im["code"]["fault_at_byte"]), ("Starfield.exe+0x2bf0100", 0x6B))
        self.assertEqual(bytes.fromhex(im["code"]["hex"])[0x6B], 0x8B)

    def test_exe_of_another_size_is_refused(self):
        exe = bytearray(build_exe())
        struct.pack_into("<I", exe, 0x80 + 24 + 56, SIZE + 0x1000)
        with self.assertRaises(ValueError):
            md._summary("a.dmp", md.Dump(self.dump()), 64, md.Image(bytes(exe)))


if __name__ == "__main__":
    unittest.main()
