"""Small texture previews from BA2 archives: the low mips of a DX10 entry, decoded with texconv, and colour helpers.

Only the tail chunk(s) of a texture are read (mips at most `max_dim` wide), so a 2048 px Starfield albedo costs a few
tens of KB of LZ4 instead of 2.8 MB. Used for average colours (choosing the ground-texture mapping) and for the
top-down reference renders (docs/terrain/ground-textures.md). Nothing here is written into the game folder.
"""
import os
import struct
import subprocess
import tempfile
import zlib

import numpy as np

from . import lz4block
from .ba2 import _dds_header_dx10


def tail_dds(archive, name, max_dim=256):
    """DDS bytes (DX10 header) holding the mips of `name` whose width and height are <= max_dim (at least the last
    chunk). Works for Fallout 4 (v1, zlib) and Starfield (v2 zlib, v3 LZ4) texture archives."""
    i = archive.find(name)
    if i is None:
        raise KeyError(name)
    e = archive.entries[i]
    if e.kind != "DX10":
        raise ValueError(f"{name}: not a texture entry")
    chunks = sorted(e.chunks, key=lambda c: c[3])
    keep = [c for c in chunks if max(e.width >> c[3], 1) <= max_dim and max(e.height >> c[3], 1) <= max_dim] or chunks[-1:]
    first = keep[0][3]
    w, h = max(e.width >> first, 1), max(e.height >> first, 1)
    out = [_dds_header_dx10(w, h, e.mips - first, e.dxgi, e.cubemap)]
    with open(archive.path, "rb") as f:
        for off, pk, up, _s, _e in keep:
            f.seek(off)
            raw = f.read(pk or up)
            if not pk:
                out.append(raw)
            elif archive.version == 3 and archive.compression == 3:
                out.append(lz4block.decompress(raw, up))
            else:
                out.append(zlib.decompress(raw))
    return b"".join(out)


SRGB_TO_UNORM = {29: 28, 72: 71, 75: 74, 78: 77, 91: 87, 93: 88, 99: 98}   # DXGI *_SRGB -> same layout, UNORM


def decode_dds(dds, texconv_exe, work=None):
    """RGBA uint8 [h, w, 4] of the first mip of a DDS (any BC format), via texconv -> uncompressed DDS. The stored
    (gamma-encoded) values are returned for sRGB formats too: the DX10 format is relabelled UNORM first, otherwise
    texconv would linearise BC1_UNORM_SRGB (Starfield) but not BC1_UNORM (Fallout 4, also sRGB content)."""
    own = work is None
    work = work or tempfile.mkdtemp(prefix="fo4sf_tex_")
    src = os.path.join(work, "in.dds")
    if dds[84:88] == b"DX10":
        fmt = struct.unpack_from("<I", dds, 128)[0]
        dds = dds[:128] + struct.pack("<I", SRGB_TO_UNORM.get(fmt, fmt)) + dds[132:]
    with open(src, "wb") as f:
        f.write(dds)
    r = subprocess.run([texconv_exe, "-nologo", "-y", "-m", "1", "-f", "R8G8B8A8_UNORM", "-dx10", "-o", work, src],
                       capture_output=True, text=True)
    out = os.path.join(work, "in.dds")
    try:
        if r.returncode != 0 or "FAILED" in r.stdout:
            raise ValueError(f"texconv failed: {r.stdout.strip()[-200:]}")
        data = open(out, "rb").read()
        hgt, wid = struct.unpack_from("<II", data, 12)
        off = 148 if data[84:88] == b"DX10" else 128
        return np.frombuffer(data, np.uint8, wid * hgt * 4, off).reshape(hgt, wid, 4).copy()
    finally:
        if own:
            for p in os.listdir(work):
                os.remove(os.path.join(work, p))
            os.rmdir(work)


def srgb_to_linear(c):
    c = np.asarray(c, np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055) * 255.0


def mean_color(rgba):
    """Average colour of an sRGB image, averaged in linear light, returned as sRGB 0..255 floats."""
    lin = srgb_to_linear(rgba[..., :3].reshape(-1, 3))
    return tuple(float(v) for v in linear_to_srgb(lin.mean(0)))


def srgb_to_lab(rgb):
    """CIE L*a*b* (D65) of sRGB 0..255 colours [..., 3]."""
    lin = srgb_to_linear(rgb)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def delta_e(a, b):
    """CIE76 colour difference of two sRGB colours."""
    return float(np.linalg.norm(srgb_to_lab(np.asarray(a, np.float64)) - srgb_to_lab(np.asarray(b, np.float64))))
