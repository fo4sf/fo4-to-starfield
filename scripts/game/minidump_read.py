"""Read the crash out of Windows minidumps, with no debugger (docs/spikes/red-rocket-crash-bisect.md).

    python scripts/game/minidump_read.py <dump.dmp> [<dump.dmp> ...] [--scan 1024] [--strings 80] [--json <out.json>]

For each dump: the exception (code, flags, the faulting address as module+offset, and for an access violation whether it
read or wrote and at which address), the faulting thread's registers, the loaded module's file version, the process's
and the system's memory when the dump was written (from the dump's own memory streams, when present), and a stack
scan: the qwords from rsp upward that point into a loaded module, nearest first. A stack scan is not an unwound stack:
stale return addresses and function pointers show up too, so read it as candidates. Two dumps with the same
module+offset and the same top of scan are very likely the same crash. --strings N lists up to N text strings (ASCII
and UTF-16) in the faulting thread's captured stack and in the memory its registers point at, file paths first: a
loader's stack often holds the name of the file it is reading. Standard library only; read-only, except --json,
which writes a new file.
"""
import argparse
import json
import mmap
import re
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
ASCII = re.compile(rb"[\x20-\x7e]{6,}")
UTF16 = re.compile(rb"(?:[\x20-\x7e]\x00){6,}")
PATHLIKE = re.compile(r"[\\/]|\.(nif|mesh|mat|bgsm|bgem|dds|esm|esp|esl|ba2|hkx|rig|af|agx|psc|pex)\b", re.I)
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
            base, size, _crc, _stamp, name_rva = struct.unpack_from("<QIIII", self.data, o)
            ms, ls = struct.unpack_from("<II", self.data, o + 24 + 8)    # VS_FIXEDFILEINFO dwFileVersionMS, LS
            name = self._string(name_rva)
            out.append({"name": name.replace("/", "\\").rsplit("\\", 1)[-1], "path": name, "base": base, "size": size,
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

    def thread_stack(self, thread_id):
        """(start, size) of a thread's captured stack, from the thread list."""
        if THREAD_LIST not in self.streams:
            return None
        at, _ = self.streams[THREAD_LIST]
        n, = struct.unpack_from("<I", self.data, at)
        for i in range(n):
            o = at + 4 + 48 * i
            tid, = struct.unpack_from("<I", self.data, o)
            if tid == thread_id:
                start, size = struct.unpack_from("<QI", self.data, o + 24)
                return start, size
        return None

    def span(self, addr, length):
        """The captured bytes from addr, up to length (shorter where the capture ends)."""
        for start, size, off in self.ranges:
            if start <= addr < start + size:
                n = min(length, start + size - addr)
                return bytes(self.data[off + addr - start:off + addr - start + n])
        return b""

    def strings(self, thread_id, regs, limit):
        """[{where, text}] of text in the thread's stack and around what its registers point at; path-like text first."""
        regions = []
        stack = self.thread_stack(thread_id)
        if stack:
            regions.append(("stack", stack[0], self.span(stack[0], stack[1])))
        for name, value in regs.items():
            if name not in ("rsp", "rip"):
                raw = self.span(value, 512)
                if raw:
                    regions.append((f"[{name}]", value, raw))
        found, seen = [], set()
        for label, base, raw in regions:
            for rx, codec in ((ASCII, "ascii"), (UTF16, "utf-16-le")):
                for m in rx.finditer(raw):
                    text = m.group().decode(codec)
                    if (label, text) not in seen:
                        seen.add((label, text))
                        found.append({"where": f"{label}+0x{m.start():x}", "addr": f"0x{base + m.start():x}", "text": text})
        found.sort(key=lambda e: not PATHLIKE.search(e["text"]))
        return found[:limit]

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


def summary(path, scan, strings=0):
    # memory-mapped, not read: a full (-ma) dump can be many GB, and only a few small structures are touched
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
        return _summary(path, Dump(data), scan, strings)


def _summary(path, d, scan, strings=0):
    exc, regs = d.exception()
    fault_module = next((m for m in d.modules if exc["at"] and exc["at"].startswith(m["name"] + "+")), None)
    stack = d.stack_scan(regs["rsp"], scan) if "rsp" in regs else []
    return {"dump": path, "exception": exc, "module_version": fault_module and fault_module["version"],
            "registers": {k: f"0x{v:x}" for k, v in regs.items()},
            "stack_scan": [{"rsp+": f"0x{o:x}", "value": f"0x{v:x}", "at": w} for o, v, w in stack],
            "memory_gib": d.memory(), "modules": len(d.modules), "memory_ranges": len(d.ranges),
            "strings": d.strings(exc["thread"], regs, strings) if strings else []}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dumps", nargs="+")
    ap.add_argument("--scan", type=int, default=1024, help="stack qwords to scan from rsp")
    ap.add_argument("--top", type=int, default=24, help="stack scan entries to print per dump")
    ap.add_argument("--strings", type=int, default=0, help="text strings to list from the faulting thread's memory")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    found = []
    for p in a.dumps:
        try:
            s = summary(p, a.scan, a.strings)
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
        for row in s["strings"]:
            print(f"  text {row['where']:<14} {row['text'][:160]}")
        print(f"  {len(s['stack_scan'])} module pointer(s) in {a.scan} stack slots; {s['modules']} modules, "
              f"{s['memory_ranges']} memory ranges")
    if a.json:
        with open(a.json, "x", encoding="utf-8") as f:
            json.dump(found, f, indent=1)
    return 0 if len(found) == len(a.dumps) else 1


if __name__ == "__main__":
    sys.exit(main())
