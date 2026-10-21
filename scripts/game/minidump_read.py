"""Read the crash out of Windows minidumps, with no debugger (docs/spikes/red-rocket-crash-bisect.md).

    python scripts/game/minidump_read.py <dump.dmp> [<dump.dmp> ...] [--scan 1024] [--json <out.json>]

For each dump: the exception (code, flags, the faulting address as module+offset, and for an access violation whether it
read or wrote and at which address), the faulting thread's registers, the loaded module's file version, and a stack
scan: the qwords from rsp upward that point into a loaded module, nearest first. A stack scan is not an unwound stack:
stale return addresses and function pointers show up too, so read it as candidates. Two dumps with the same
module+offset and the same top of scan are very likely the same crash. Standard library only; read-only, except --json,
which writes a new file.
"""
import argparse
import json
import struct
import sys

THREAD_LIST, MODULE_LIST, MEMORY_LIST, EXCEPTION, MEMORY64_LIST = 3, 4, 5, 6, 9
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


def summary(path, scan):
    with open(path, "rb") as f:
        d = Dump(f.read())
    exc, regs = d.exception()
    fault_module = next((m for m in d.modules if exc["at"] and exc["at"].startswith(m["name"] + "+")), None)
    stack = d.stack_scan(regs["rsp"], scan) if "rsp" in regs else []
    return {"dump": path, "exception": exc, "module_version": fault_module and fault_module["version"],
            "registers": {k: f"0x{v:x}" for k, v in regs.items()},
            "stack_scan": [{"rsp+": f"0x{o:x}", "value": f"0x{v:x}", "at": w} for o, v, w in stack],
            "modules": len(d.modules), "memory_ranges": len(d.ranges)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dumps", nargs="+")
    ap.add_argument("--scan", type=int, default=1024, help="stack qwords to scan from rsp")
    ap.add_argument("--top", type=int, default=24, help="stack scan entries to print per dump")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    found = []
    for p in a.dumps:
        try:
            s = summary(p, a.scan)
        except (OSError, ValueError, struct.error) as e:
            print(f"{p}: {e}")
            continue
        found.append(s)
        e = s["exception"]
        print(f"{p}")
        print(f"  {e['name']} ({e['code']}) at {e['at'] or e['address']} (module version {s['module_version']}), "
              f"thread {e['thread']}" + (f", {e['access']} of {e['target']}" if "access" in e else ""))
        print("  " + " ".join(f"{k} {v}" for k, v in s["registers"].items()))
        for row in s["stack_scan"][:a.top]:
            print(f"  rsp+{row['rsp+']:<7} {row['value']}  {row['at']}")
        print(f"  {len(s['stack_scan'])} module pointer(s) in {a.scan} stack slots; {s['modules']} modules, "
              f"{s['memory_ranges']} memory ranges")
    if a.json:
        with open(a.json, "x", encoding="utf-8") as f:
            json.dump(found, f, indent=1)
    return 0 if len(found) == len(a.dumps) else 1


if __name__ == "__main__":
    sys.exit(main())
