"""Read the crash out of Windows minidumps, with no debugger (docs/spikes/red-rocket-crash-bisect.md).

    python scripts/game/minidump_read.py <dump.dmp> [<dump.dmp> ...] [--scan 1024] [--json <out.json>]
        [--exe <Starfield.exe>]

For each dump: the exception (code, flags, the faulting address as module+offset, and for an access violation whether it
read or wrote and at which address), the faulting thread's registers, the loaded module's file version, the process's
and the system's memory when the dump was written (from the dump's own memory streams, when present), and a stack
scan: the qwords from rsp upward that point into a loaded module, nearest first. A stack scan is not an unwound stack:
stale return addresses and function pointers show up too, so read it as candidates. Two dumps with the same
module+offset and the same top of scan are very likely the same crash. Standard library only; read-only, except --json,
which writes a new file.

With --exe (the faulting module's own file, the same version as in the dump; it is only read) the report adds what the
dump alone cannot give, because a minidump rarely holds the module's code and read-only data:
- the code bytes around the fault and the start of the function it is in (the exe's .pdata), so the instruction can be
  disassembled elsewhere;
- for each stack-scan entry into the exe, whether the bytes before it look like a call (a real return address's do; a
  stale function pointer's usually do not; a byte-pattern match, not a decode) and its function start;
- the C++ class (MSVC RTTI) of every object a register or a stack slot points at, when the dump holds the object's first
  qword and that qword is a vtable in the exe: the vtable's complete object locator gives the class name.
"""
import argparse
import json
import mmap
import struct
import sys

THREAD_LIST, MODULE_LIST, MEMORY_LIST, EXCEPTION, MEMORY64_LIST = 3, 4, 5, 6, 9
SYSTEM_MEMORY_INFO, PROCESS_VM_COUNTERS = 21, 22
GIB = 1 << 30
CODES = {0xC0000005: "ACCESS_VIOLATION", 0xC0000409: "STACK_BUFFER_OVERRUN", 0xC00000FD: "STACK_OVERFLOW",
         0x80000003: "BREAKPOINT", 0xC0000374: "HEAP_CORRUPTION", 0xC000001D: "ILLEGAL_INSTRUCTION",
         0xE06D7363: "C++ exception"}
ACCESS = {0: "read", 1: "write", 8: "execute (DEP)"}
# x64 CONTEXT: general registers from Rax at 0x78, eight bytes apart, then Rip at 0xF8
REGS = ("rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "rip")


class Dump:
    def __init__(self, data):
        if data[:4] != b"MDMP":
            raise ValueError("not a minidump (no MDMP signature)")
        self.data = data
        count, rva = struct.unpack_from("<II", data, 8)
        self.streams = {}
        for i in range(count):
            kind, size, at = struct.unpack_from("<III", data, rva + 12 * i)
            self.streams.setdefault(kind, (at, size))
        self.modules = self._modules()
        self.ranges = self._ranges()

    def _string(self, rva):
        n, = struct.unpack_from("<I", self.data, rva)
        return self.data[rva + 4:rva + 4 + n].decode("utf-16-le", "replace")

    def _modules(self):
        if MODULE_LIST not in self.streams:
            return []
        at, _ = self.streams[MODULE_LIST]
        n, = struct.unpack_from("<I", self.data, at)
        out = []
        for i in range(n):
            o = at + 4 + 108 * i
            base, size, _crc, stamp, name_rva = struct.unpack_from("<QIIII", self.data, o)
            ms, ls = struct.unpack_from("<II", self.data, o + 24 + 8)    # VS_FIXEDFILEINFO dwFileVersionMS, LS
            name = self._string(name_rva)
            out.append({"name": name.replace("/", "\\").rsplit("\\", 1)[-1], "path": name, "base": base, "size": size, "stamp": stamp,
                        "version": f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}" if ms or ls else None})
        return sorted(out, key=lambda m: m["base"])

    def _ranges(self):
        """[(start, length, file offset)] of the captured memory."""
        out = []
        if MEMORY64_LIST in self.streams:
            at, _ = self.streams[MEMORY64_LIST]
            n, base_rva = struct.unpack_from("<QQ", self.data, at)
            off = base_rva
            for i in range(n):
                start, size = struct.unpack_from("<QQ", self.data, at + 16 + 16 * i)
                out.append((start, size, off))
                off += size
        if MEMORY_LIST in self.streams:
            at, _ = self.streams[MEMORY_LIST]
            n, = struct.unpack_from("<I", self.data, at)
            for i in range(n):
                start, size, rva = struct.unpack_from("<QII", self.data, at + 4 + 16 * i)
                out.append((start, size, rva))
        return sorted(out)

    def read(self, addr, length):
        for start, size, off in self.ranges:
            if start <= addr and addr + length <= start + size:
                return self.data[off + addr - start:off + addr - start + length]
        return None

    def where(self, addr):
        for m in self.modules:
            if m["base"] <= addr < m["base"] + m["size"]:
                return f"{m['name']}+0x{addr - m['base']:x}"
        return None

    def exception(self):
        if EXCEPTION not in self.streams:
            raise ValueError("no exception stream: the dump was not written for a crash")
        at, _ = self.streams[EXCEPTION]
        thread, = struct.unpack_from("<I", self.data, at)
        code, flags, _rec, addr, nparams = struct.unpack_from("<IIQQI", self.data, at + 8)
        params = struct.unpack_from(f"<{min(nparams, 15)}Q", self.data, at + 8 + 32)
        ctx_size, ctx_rva = struct.unpack_from("<II", self.data, at + 8 + 152)
        regs = {}
        if ctx_size >= 0x100:
            regs = dict(zip(REGS, struct.unpack_from("<17Q", self.data, ctx_rva + 0x78)))
        out = {"thread": thread, "code": f"0x{code:08X}", "name": CODES.get(code, "unknown"), "flags": flags,
               "address": f"0x{addr:x}", "at": self.where(addr)}
        if code == 0xC0000005 and len(params) >= 2:
            out["access"] = ACCESS.get(params[0], str(params[0]))
            out["target"] = f"0x{params[1]:x}"
        return out, regs

    def memory(self):
        """The process's and the system's memory when the dump was written, in GiB, from the dump's own streams (Windows
        10 and later write them): commit charge, private bytes and working set of the process; available memory, commit
        charge and commit limit of the system. Missing streams are left out."""
        out = {}
        if PROCESS_VM_COUNTERS in self.streams:
            at, size = self.streams[PROCESS_VM_COUNTERS]
            rev, flags = struct.unpack_from("<HH", self.data, at) if size >= 4 else (0, 0)
            # revision 1: PrivateUsage at 72. Revision 2: the basic counters only with flag 0x1 (VM_COUNTERS),
            # PeakVirtualSize and VirtualSize at 72 and 80 with 0x2 (VIRTUALSIZE), PrivateUsage at 88 with 0x4 (EX)
            if size >= 72 and (rev == 1 or flags & 0x1):
                peak_ws, ws = struct.unpack_from("<QQ", self.data, at + 8)
                pagefile, peak_pagefile = struct.unpack_from("<QQ", self.data, at + 56)
                proc = {"working_set": ws / GIB, "peak_working_set": peak_ws / GIB, "commit": pagefile / GIB,
                        "peak_commit": peak_pagefile / GIB}
                if rev == 1 and size >= 80:
                    proc["private"] = struct.unpack_from("<Q", self.data, at + 72)[0] / GIB
                if rev >= 2 and flags & 0x2 and size >= 88:
                    proc["virtual"] = struct.unpack_from("<Q", self.data, at + 80)[0] / GIB
                if rev >= 2 and flags & 0x4 and size >= 96:
                    proc["private"] = struct.unpack_from("<Q", self.data, at + 88)[0] / GIB
                out["process"] = proc
        if SYSTEM_MEMORY_INFO in self.streams:
            at, size = self.streams[SYSTEM_MEMORY_INFO]
            flags, = struct.unpack_from("<H", self.data, at + 2) if size >= 4 else (0,)
            if size >= 148 and flags & 0x2:
                # MINIDUMP_SYSTEM_MEMORY_INFO_1, 4-byte packed (minidumpapiset.h): basic information at 4 (PageSize at
                # 8), the file cache at 56, the basic performance information at 116 (available pages, committed
                # pages, commit limit, peak commit), valid only with flag 0x2 (MINIDUMP_SYSMEMINFO1_BASICPERF)
                page, = struct.unpack_from("<I", self.data, at + 8)
                avail, committed, limit, peak = struct.unpack_from("<4Q", self.data, at + 116)
                if page in (4096, 8192, 16384, 65536):
                    out["system"] = {"available": avail * page / GIB, "commit": committed * page / GIB,
                                     "commit_limit": limit * page / GIB, "peak_commit": peak * page / GIB}
        for part in out.values():
            for k, v in part.items():
                part[k] = round(v, 2)
        return out

    def stack_scan(self, rsp, count):
        """[(slot offset from rsp, value, module+offset)] for qwords on the stack that point into a module."""
        out = []
        for i in range(count):
            raw = self.read(rsp + 8 * i, 8)
            if raw is None:
                break
            v, = struct.unpack("<Q", raw)
            w = self.where(v)
            if w:
                out.append((8 * i, v, w))
        return out


class Image:
    """A PE32+ file on disk, read by RVA: its sections, its .pdata function table and the MSVC RTTI behind a vtable."""

    def __init__(self, data):
        if data[:2] != b"MZ":
            raise ValueError("not a PE file (no MZ signature)")
        self.data = data
        pe, = struct.unpack_from("<I", data, 0x3C)
        if data[pe:pe + 4] != b"PE\0\0":
            raise ValueError("not a PE file (no PE signature)")
        nsec, self.stamp = struct.unpack_from("<HI", data, pe + 6)   # COFF NumberOfSections, TimeDateStamp
        opt_size, = struct.unpack_from("<H", data, pe + 20)
        opt = pe + 24
        if struct.unpack_from("<H", data, opt)[0] != 0x20B:
            raise ValueError("not a 64-bit PE file")
        self.image_base, = struct.unpack_from("<Q", data, opt + 24)   # the preferred base the file's pointers assume
        self.size_of_image, = struct.unpack_from("<I", data, opt + 56)
        # data directory 3 is the exception table (.pdata): RUNTIME_FUNCTION {begin, end, unwind} RVAs, sorted by begin
        self.pdata = struct.unpack_from("<II", data, opt + 112 + 8 * 3)
        self.sections = []
        for i in range(nsec):
            o = opt + opt_size + 40 * i
            vsize, va, rsize, roff = struct.unpack_from("<IIII", data, o + 8)
            self.sections.append((va, max(vsize, rsize), rsize, roff))

    def read(self, rva, length):
        for va, vsize, rsize, roff in self.sections:
            if va <= rva and rva + length <= va + vsize:
                if rva + length > va + rsize:
                    return None
                return bytes(self.data[roff + rva - va:roff + rva - va + length])
        return None

    def function(self, rva):
        """The begin RVA of the .pdata entry holding rva, or None (a leaf function has no entry)."""
        at, size = self.pdata
        lo, hi = 0, size // 12
        while lo < hi:
            mid = (lo + hi) // 2
            raw = self.read(at + 12 * mid, 8)
            if raw is None:
                return None
            begin, end = struct.unpack("<II", raw)
            if rva < begin:
                hi = mid
            elif rva >= end:
                lo = mid + 1
            else:
                return begin
        return None

    def after_call(self, rva):
        """True when the bytes just before rva could end a call instruction, as a return address's do. A byte-pattern
        match, not a decode from a known instruction boundary: an E8 or FF byte inside another instruction's immediate
        or displacement matches too (Codex on #453), so it filters stale pointers out but does not prove a call."""
        b = self.read(rva - 7, 7) if rva >= 7 else None
        if b is None:
            return False
        if b[-5] == 0xE8:                                    # call rel32
            return True
        for n in (2, 3, 4, 6, 7):                            # call r/m64: FF /2, then SIB and displacement bytes
            if b[-n] == 0xFF and (b[-n + 1] >> 3) & 7 == 2 and _modrm_length(b[-n + 1:]) == n - 1:
                return True
        return False


def _modrm_length(b):
    """The length of a ModRM byte with its SIB and displacement (64-bit addressing), from the bytes that follow it."""
    mod, rm = b[0] >> 6, b[0] & 7
    if mod == 3:
        return 1
    n = 1
    if rm == 4:
        n += 1
        if mod == 0 and len(b) > 1 and b[1] & 7 == 5:      # SIB with no base: disp32
            return n + 4
    if mod == 0:
        return n + 4 if rm == 5 else n                       # rm 5: RIP-relative disp32
    return n + (1 if mod == 1 else 4)


def rtti_name(img, base, vtable):
    """The decorated class name (".?AVBSGeometry@@") for a vtable address in the image loaded at base, or None."""
    if not (base <= vtable < base + img.size_of_image):
        return None
    raw = img.read(vtable - base - 8, 8)
    if raw is None:
        return None
    # vtable[-1] holds the locator's address against the file's preferred ImageBase, not the module's runtime base
    # (Codex on #453: Starfield is ASLR-relocated), so it becomes an RVA through ImageBase
    col = struct.unpack("<Q", raw)[0] - img.image_base
    if not (0 <= col < img.size_of_image):
        return None
    # x64 RTTICompleteObjectLocator: signature 1, offset, cdOffset, then the type descriptor's RVA
    head = img.read(col, 16)
    if head is None:
        return None
    sig, _off, _cd, td = struct.unpack("<IIII", head)
    if sig != 1:
        return None
    # TypeDescriptor: pVFTable, spare, then the zero-ended decorated name
    name = img.read(td + 16, 256)
    if not name or not name.startswith(b".?A"):
        return None
    return name.split(b"\0", 1)[0].decode("ascii", "replace")


def code_around(d, img, base, rip, before=64, after=32):
    """The bytes from rip-before to rip+after, from the dump when it holds them, else from the exe."""
    raw = d.read(rip - before, before + after)
    if raw is None and img is not None and base <= rip < base + img.size_of_image:
        raw = img.read(rip - base - before, before + after)
    return raw


def objects(d, img, base, regs, stack_slots):
    """[(where, pointer, class)] for registers and stack slots that point at an object whose vtable has RTTI."""
    out = []
    seen = set()
    for where, v in [(k, regs[k]) for k in REGS if k in regs and k != "rip"] + stack_slots:
        raw = d.read(v, 8) if v > 0x10000 else None
        if raw is None:
            continue
        vt, = struct.unpack("<Q", raw)
        name = rtti_name(img, base, vt)
        if name and (where, v) not in seen:
            seen.add((where, v))
            out.append((where, v, name))
    return out


def summary(path, scan, exe=None, before=64):
    # memory-mapped, not read: a full (-ma) dump can be many GB, and only a few small structures are touched
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
        if not exe:
            return _summary(path, Dump(data), scan)
        with open(exe, "rb") as g, mmap.mmap(g.fileno(), 0, access=mmap.ACCESS_READ) as pe:
            return _summary(path, Dump(data), scan, Image(pe), before)


def _summary(path, d, scan, img=None, before=64):
    exc, regs = d.exception()
    fault_module = next((m for m in d.modules if exc["at"] and exc["at"].startswith(m["name"] + "+")), None)
    stack = d.stack_scan(regs["rsp"], scan) if "rsp" in regs else []
    out = {"dump": path, "exception": exc, "module_version": fault_module and fault_module["version"],
            "registers": {k: f"0x{v:x}" for k, v in regs.items()},
            "stack_scan": [{"rsp+": f"0x{o:x}", "value": f"0x{v:x}", "at": w} for o, v, w in stack],
            "memory_gib": d.memory(), "modules": len(d.modules), "memory_ranges": len(d.ranges)}
    if img is not None and fault_module:
        out["image"] = _image_report(d, img, fault_module, regs, stack, scan, before)
    return out


def _image_report(d, img, mod, regs, stack, scan, before=64):
    base, name = mod["base"], mod["name"]
    if img.size_of_image != mod["size"]:
        raise ValueError(f"--exe is not the dump's {name}: SizeOfImage 0x{img.size_of_image:x}, "
                         f"the dump's 0x{mod['size']:x}")
    if img.stamp and mod.get("stamp") and img.stamp != mod["stamp"]:   # another build of the same size (Codex on #453)
        raise ValueError(f"--exe is not the dump's {name}: PE timestamp 0x{img.stamp:08x}, the dump's 0x{mod['stamp']:08x}")
    rip = regs.get("rip", 0)
    fn = img.function(rip - base) if base <= rip < base + img.size_of_image else None
    if before < 0 and fn is not None:                    # -1: from the start of the fault's function
        before = rip - base - fn
    before = max(before, 0)
    code = code_around(d, img, base, rip, before)
    calls = []
    for o, v, w in stack:
        if base <= v < base + img.size_of_image:
            f = img.function(v - base)
            calls.append({"rsp+": f"0x{o:x}", "at": w, "after_call": img.after_call(v - base),
                          "function": f"{name}+0x{f:x}" if f is not None else None})
    slots = []
    for i in range(scan):
        raw = d.read(regs["rsp"] + 8 * i, 8) if "rsp" in regs else None
        if raw is None:
            break
        slots.append((f"rsp+0x{8 * i:x}", struct.unpack("<Q", raw)[0]))
    return {"fault_function": f"{name}+0x{fn:x}" if fn is not None else None,
            "code": {"from": f"{name}+0x{rip - base - before:x}", "fault_at_byte": before,
                     "hex": code.hex() if code else None},
            "stack_calls": calls,
            "objects": [{"in": w, "pointer": f"0x{v:x}", "class": c} for w, v, c in objects(d, img, base, regs, slots)]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dumps", nargs="+")
    ap.add_argument("--scan", type=int, default=1024, help="stack qwords to scan from rsp")
    ap.add_argument("--top", type=int, default=24, help="stack scan entries to print per dump")
    ap.add_argument("--json", default="")
    ap.add_argument("--exe", default="", help="the faulting module's file (same version): code bytes, call checks, RTTI")
    ap.add_argument("--code-before", type=int, default=64,
                    help="code bytes to print before the fault with --exe; -1 starts at the fault's function")
    a = ap.parse_args(argv)
    found = []
    for p in a.dumps:
        try:
            s = summary(p, a.scan, a.exe or None, a.code_before)
        except (OSError, ValueError, struct.error) as e:
            print(f"{p}: {e}")
            continue
        found.append(s)
        e = s["exception"]
        print(f"{p}")
        print(f"  {e['name']} ({e['code']}) at {e['at'] or e['address']} (module version {s['module_version']}), "
              f"thread {e['thread']}" + (f", {e['access']} of {e['target']}" if "access" in e else ""))
        print("  " + " ".join(f"{k} {v}" for k, v in s["registers"].items()))
        mem = s["memory_gib"]
        for part in ("process", "system"):
            if part in mem:
                print(f"  {part} memory (GiB): " + ", ".join(f"{k} {v}" for k, v in mem[part].items()))
            else:
                print(f"  {part} memory: not in the dump")
        for row in s["stack_scan"][:a.top]:
            print(f"  rsp+{row['rsp+']:<7} {row['value']}  {row['at']}")
        print(f"  {len(s['stack_scan'])} module pointer(s) in {a.scan} stack slots; {s['modules']} modules, "
              f"{s['memory_ranges']} memory ranges")
        im = s.get("image")
        if im:
            print(f"  fault function {im['fault_function']}; code from {im['code']['from']} "
                  f"(fault at byte {im['code']['fault_at_byte']}): {im['code']['hex']}")
            for c in im["stack_calls"][:a.top]:
                print(f"  rsp+{c['rsp+']:<7} {c['at']:<28} {'call?' if c['after_call'] else 'no call':<8} "
                      f"in {c['function']}")
            for o in im["objects"][:a.top]:
                print(f"  object {o['in']:<10} {o['pointer']}  {o['class']}")
            if not im["objects"]:
                print("  objects: none found (the dump may not hold the heap, or no pointed-at qword is a vtable)")
    if a.json:
        with open(a.json, "x", encoding="utf-8") as f:
            json.dump(found, f, indent=1)
    return 0 if len(found) == len(a.dumps) else 1


if __name__ == "__main__":
    sys.exit(main())
