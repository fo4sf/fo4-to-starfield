"""LZ4 block decompression (raw block format, no frame header), pure Python.

Starfield's texture archives (BA2 version 3, compression 3) store every DX10 chunk as one LZ4 block. Only the small
tail chunks (the low mips, a few tens of KB) are read with this, for average colours and previews, so speed does not
matter. Format (lz4 block spec): sequences of
    token          high nibble = literal length, low nibble = match length - 4 (15 = more bytes follow)
    [len bytes]    255, 255, ..., last < 255 added to the length
    literals
    offset         u16 little endian, 1..65535 back from the current output end
    [len bytes]    match length extension
The last sequence has literals only.
"""


class Lz4Error(ValueError):
    pass


def _length(src, i, n):
    while True:
        if i >= len(src):
            raise Lz4Error("truncated length")
        b = src[i]
        i += 1
        n += b
        if b != 255:
            return n, i


def decompress(src: bytes, size: int) -> bytes:
    """Decompress one LZ4 block whose decompressed size is `size` bytes."""
    out = bytearray()
    i, end = 0, len(src)
    while i < end:
        token = src[i]
        i += 1
        lit = token >> 4
        if lit == 15:
            lit, i = _length(src, i, lit)
        if i + lit > end:
            raise Lz4Error("literals past the end of the block")
        out += src[i:i + lit]
        i += lit
        if i >= end:
            break                                   # last sequence: literals only
        if i + 2 > end:
            raise Lz4Error("truncated offset")
        off = src[i] | (src[i + 1] << 8)
        i += 2
        if off == 0 or off > len(out):
            raise Lz4Error(f"bad match offset {off}")
        mlen = token & 15
        if mlen == 15:
            mlen, i = _length(src, i, mlen)
        mlen += 4
        start = len(out) - off
        if off >= mlen:
            out += out[start:start + mlen]
        else:                                       # overlapping copy (run-length style)
            for k in range(mlen):
                out.append(out[start + k])
    if len(out) != size:
        raise Lz4Error(f"decompressed {len(out)} bytes, expected {size}")
    return bytes(out)
