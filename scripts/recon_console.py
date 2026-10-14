"""Read-only: list Starfield console commands (name, short name, help, parameters) from Starfield.exe.

usage: python recon_console.py <Starfield.exe> PathToRef,PickLastRef,...  [--near]

Starfield 1.16.244 builds its console command entries at runtime: the initialiser loads each string with
`lea rax, [rip+X]` (48 8D 05) and stores it with `mov [rbp+D], rax` (48 89 85); the parameter count is stored with
`mov eax, n` + `mov [rbp+D], ax` and the parameter array (16 bytes each: type-name pointer, type id, optional flag) is a
static table in .data. Entry layout (decoded from PathToRef's initialiser, 2026-10-11): +0x00 name, +0x08 short name,
+0x10 opcode (u32), +0x18 help, +0x22 parameter count (u16), +0x28 parameters. The script-function table (SetPos,
PlaceAtMe, ApplyHavokImpulse, SetRigidBodyMass; opcodes 0x1000 and up, 2026-10-13) is built the same way on the stack
pointer instead (`mov [rsp+D], rax` = 48 89 84 24, `mov dword [rsp+D], imm32` = C7 84 24, `mov byte [rsp+D], imm8` =
C6 84 24, `mov [rsp+D], ax` = 66 89 84 24): both forms are read. Some script functions (GetSelf, GetIsID) are
registered yet another way: --near prints the strings next to a name instead (their help text sits beside them).
Nothing is written; the exe is only read."""
import argparse
import re
import struct

import numpy as np


def sections(data):
    """{name: (virtual address, raw size, raw pointer)} and the image base of a PE32+ file."""
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    base = struct.unpack_from("<Q", data, pe + 24 + 24)[0]
    out = {}
    for k in range(nsec):
        s = pe + 24 + optsz + 40 * k
        name = data[s:s + 8].rstrip(b"\0").decode("ascii", "replace")
        _vsize, va, rsize, rptr = struct.unpack_from("<IIII", data, s + 8)
        out[name] = (va, rsize, rptr)
    return out, base


class Image:
    def __init__(self, data):
        self.data = data
        self.secs, self.base = sections(data)

    def rva2off(self, rva):
        for va, rs, rp in self.secs.values():
            if va <= rva < va + rs:
                return rp + rva - va
        return None

    def off2rva(self, off):
        for va, rs, rp in self.secs.values():
            if rp <= off < rp + rs:
                return va + off - rp
        return None

    def cstr(self, rva):
        o = self.rva2off(rva) if rva else None
        if o is None:
            return None
        e = self.data.find(b"\0", o, o + 200)
        s = self.data[o:e]
        return s.decode("ascii") if s and all(32 <= b < 127 for b in s) else None

    def lea_rax_targets(self):
        """(code offsets, target rvas) of every `lea rax, [rip+disp32]` in .text (computed once)."""
        va, rs, rp = self.secs[".text"]
        a = np.frombuffer(self.data, dtype=np.uint8, count=rs, offset=rp)
        idx = np.nonzero((a[:-7] == 0x48) & (a[1:-6] == 0x8D) & (a[2:-5] == 0x05))[0]
        d = (a[idx + 3].astype(np.int64) | (a[idx + 4].astype(np.int64) << 8) | (a[idx + 5].astype(np.int64) << 16)
             | (a[idx + 6].astype(np.int64) << 24))
        d = np.where(d >= 1 << 31, d - (1 << 32), d)
        return idx, va + idx + 7 + d

    def stores(self, text_off):
        """{rbp or rsp offset: value} from the store sequence that starts at a name's lea (see the module doc)."""
        va, rs, rp = self.secs[".text"]
        i, rax, eax, out = text_off, None, None, {}
        for _ in range(40):
            b = self.data[rp + i:rp + i + 12]
            if b[:3] == b"\x48\x8d\x05":
                rax = va + i + 7 + struct.unpack_from("<i", b, 3)[0]
                i += 7
            elif b[:3] == b"\x48\x89\x85":
                out[struct.unpack_from("<i", b, 3)[0]] = rax
                i += 7
            elif b[:4] == b"\x48\x89\x84\x24":                 # mov [rsp+d32], rax
                out[struct.unpack_from("<i", b, 4)[0]] = rax
                i += 8
            elif b[:2] == b"\xc7\x85":
                d, imm = struct.unpack_from("<iI", b, 2)
                out[d] = imm
                i += 10
            elif b[:3] == b"\xc7\x84\x24":                     # mov dword [rsp+d32], imm32
                d, imm = struct.unpack_from("<iI", b, 3)
                out[d] = imm
                i += 11
            elif b[:1] == b"\xb8":
                eax = struct.unpack_from("<I", b, 1)[0]
                i += 5
            elif b[:2] == b"\x33\xc0":
                eax = 0
                i += 2
            elif b[:3] == b"\x66\x89\x85":
                out[struct.unpack_from("<i", b, 3)[0]] = eax
                i += 7
            elif b[:4] == b"\x66\x89\x84\x24":                 # mov [rsp+d32], ax
                out[struct.unpack_from("<i", b, 4)[0]] = eax
                i += 8
            elif b[:2] == b"\xc6\x85":
                out[struct.unpack_from("<i", b, 2)[0]] = b[6]
                i += 7
            elif b[:3] == b"\xc6\x84\x24":                     # mov byte [rsp+d32], imm8
                out[struct.unpack_from("<i", b, 3)[0]] = b[7]
                i += 8
            elif b[:4] in (b"\xc5\xf8\x11\x85", b"\xc5\xfc\x11\x85"):
                i += 8
            elif b[:5] in (b"\xc5\xf8\x11\x84\x24", b"\xc5\xfc\x11\x84\x24"):
                i += 9
            else:
                break
        return out

    def commands(self, names):
        """[{name, short, opcode, help, params}] for each console command entry found."""
        idx, tgt = self.lea_rax_targets()
        found = []
        for n in names:
            for m in re.finditer(re.escape(b"\0" + n.encode() + b"\0"), self.data):
                rva = self.off2rva(m.start() + 1)
                for code in idx[tgt == rva]:
                    st = self.stores(int(code))
                    base = [d for d, v in st.items() if v == rva]
                    if not base:
                        continue
                    b = min(base)
                    npar, pp = st.get(b + 0x22), st.get(b + 0x28)
                    params = []
                    if npar and pp and self.rva2off(pp) is not None:
                        q = self.rva2off(pp)
                        for k in range(min(npar, 8)):
                            p, typ, opt = struct.unpack_from("<QII", self.data, q + 16 * k)
                            params.append({"type": self.cstr(p - self.base) if p > self.base else None,
                                           "id": typ, "optional": bool(opt)})
                    found.append({"name": n, "short": self.cstr(st.get(b + 0x08)), "opcode": st.get(b + 0x10),
                                  "help": self.cstr(st.get(b + 0x18)), "params": params})
        return found

    def near(self, name, before=2, after=4):
        """The printable strings around each exact occurrence of name."""
        strs = [(m.start(), m.group().decode("ascii")) for m in re.finditer(rb"[\x20-\x7e]{3,}", self.data)]
        hits = [k for k, (_, s) in enumerate(strs) if s == name]
        return [[s for _, s in strs[max(0, k - before):k + after]] for k in hits]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exe")
    ap.add_argument("names", help="comma-separated command names, e.g. PathToRef,PickLastRef")
    ap.add_argument("--near", action="store_true", help="print neighbouring strings instead (script functions)")
    a = ap.parse_args(argv)
    with open(a.exe, "rb") as f:
        img = Image(f.read())
    names = [n.strip() for n in a.names.split(",") if n.strip()]
    if a.near:
        for n in names:
            for ctx in img.near(n):
                print(f"{n}: " + " | ".join(ctx))
        return 0
    got = img.commands(names)
    for c in got:
        ps = ", ".join(f"{p['type']}{'?' if p['optional'] else ''}" for p in c["params"]) or "-"
        print(f"{c['name']} ({c['short']}): {c['help']!r}  params: {ps}")
    for n in sorted(set(names) - {c["name"] for c in got}):
        print(f"{n}: no console command entry decoded (a script function? try --near)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
