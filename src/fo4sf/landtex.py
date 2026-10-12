"""Ground textures: Fallout 4 LAND texture layers -> per-vertex weights -> Starfield BTD texture sections.

Fallout 4 (verified on Fallout4.esm, docs/terrain/ground-textures.md 1):
    BTXT  u32 LTEX, u8 quadrant, u8 unused, i16 layer    base texture of one quadrant (no BTXT: the engine default)
    ATXT  u32 LTEX, u8 quadrant, u8 unused, u16 layer    alpha layer header, followed by its
    VTXT  n x (u16 position, u16 unused, f32 opacity)    position = row * 17 + column in the quadrant, row 0 = south
    VCLR  33 x 33 x (r, g, b) u8                          vertex colour, row 0 = south
    Quadrants: 0 = south-west, 1 = south-east, 2 = north-west, 3 = north-east, 17 x 17 vertices each; vertex row/column
    16 is shared by two quadrants. LTEX 0 in an ATXT means the default texture (as a missing BTXT).
    Blending (supported, fo76utils renderPixelTES4): the base, then the layers in ascending layer number, each drawn
    over what is below with its opacity. So with opacities a_1..a_k the weight of layer i is
    a_i * prod_{j > i} (1 - a_j) and the base keeps prod_j (1 - a_j).

Starfield BTD (verified on vanilla files, docs/terrain/ground-textures.md 2):
    LTEX table of n FormIDs; per quadrant (64 x 64 samples, 50 m) 8 bytes, value v -> table[n - v], 0 = empty.
    Bytes 0..4 are layer slots, slot k's alpha is bits 3k..3k+2 (0..7) of the sample's u16 weight; byte 6 is the base
    (no alpha); bytes 5 and 7 are always 0. A quadrant's textures sit in ascending table index; the one with the highest
    index is the bottom. With up to 5 textures there is no byte 6: the last slot is the bottom and its alpha is 7 at
    (nearly) every sample (lc172world, lc001world, cydoniacity 100 %, newatlantis 99.97 %). Blending (supported,
    fo76utils renderPixelFO76 and the alpha-7 bottom slot): from the bottom up, each slot over what is below with
    alpha / 7; slot 0 is the top. decode(encode(decode(vanilla))) == decode(vanilla) for five vanilla overlays.

Arrays are [row, column] with row 0 = south, as in fo4land and btd.
"""
import struct

import numpy as np

QUAD = 17                       # FO4 vertices per quadrant side
CELL = 33                       # FO4 vertices per cell side
SF_QUAD = 64                    # BTD samples per quadrant side
SLOTS = 5                       # BTD layer slots with an alpha
MAX_TEXTURES = 6                # 5 slots + base
ALPHA_MAX = 7
DEFAULT = 0                     # key for the FO4 default texture (no BTXT, or LTEX 0 in an ATXT)


# ------------------------------------------------------------------------------------------------------------ FO4
def parse_land_textures(fields):
    """(sig, bytes) fields of one LAND record -> 4 quadrants, each {"base": fid or None, "layers": [(layer, fid,
    opacity[17, 17] float32)]} in file order. Opacities are clipped to 0..1; positions >= 289 are ignored."""
    quads = [{"base": None, "layers": []} for _ in range(4)]
    cur = None
    for sig, d in fields:
        if sig == b"BTXT" and len(d) >= 8:
            fid, q = struct.unpack_from("<IB", d)
            quads[q & 3]["base"] = fid
            cur = None
        elif sig == b"ATXT" and len(d) >= 8:
            fid, q, _u, layer = struct.unpack_from("<IBBH", d)
            cur = np.zeros((QUAD, QUAD), np.float32)
            quads[q & 3]["layers"].append((layer, fid, cur))
        elif sig == b"VTXT" and cur is not None:
            n = len(d) // 8
            if n:
                rec = np.frombuffer(bytes(d[:8 * n]), dtype=[("pos", "<u2"), ("unused", "<u2"), ("a", "<f4")])
                ok = rec["pos"] < QUAD * QUAD
                pos = rec["pos"][ok].astype(np.int64)
                cur[pos // QUAD, pos % QUAD] = np.clip(np.nan_to_num(rec["a"][ok]), 0.0, 1.0)
    return quads


def quadrant_weights(quad, default=DEFAULT):
    """{fid: weights[17, 17]} of one quadrant, summing to 1 at every vertex (over compositing, layers ascending)."""
    base = quad["base"] if quad["base"] else default
    w = {base: np.ones((QUAD, QUAD), np.float64)}
    for _layer, fid, a in sorted(quad["layers"], key=lambda t: t[0]):     # stable: same layer keeps file order
        fid = fid or default
        a = a.astype(np.float64)
        for k in w:
            w[k] *= 1.0 - a
        w[fid] = w.get(fid, 0.0) + a
    return w


def cell_weights(quads, default=DEFAULT):
    """{fid: weights[33, 33]} of one cell; a vertex shared by two or four quadrants gets their mean."""
    acc, cnt = {}, np.zeros((CELL, CELL))
    for q, quad in enumerate(quads):
        r0, c0 = 16 * (q >> 1), 16 * (q & 1)
        for fid, w in quadrant_weights(quad, default).items():
            acc.setdefault(fid, np.zeros((CELL, CELL)))[r0:r0 + QUAD, c0:c0 + QUAD] += w
        cnt[r0:r0 + QUAD, c0:c0 + QUAD] += 1
    return {fid: a / cnt for fid, a in acc.items()}


def decode_vclr(data):
    """VCLR -> uint8 [33, 33, 3] (row 0 = south). Raises on a short field."""
    if len(data) < CELL * CELL * 3:
        raise ValueError(f"VCLR too short: {len(data)}")
    return np.frombuffer(bytes(data[:CELL * CELL * 3]), np.uint8).reshape(CELL, CELL, 3).copy()


class WeightGrid:
    """Per-texture weights on a merged FO4 vertex grid ((32 ny + 1) x (32 nx + 1), origin = SW vertex of cell (x0, y0)).
    Textures are added under any key (FO4 LTEX or an already mapped Starfield LTEX). Vertices on a cell border get the
    mean of the cells that hold them; vertices of missing cells hold weight 1 for `missing`."""

    def __init__(self, x0, y0, nx, ny, missing=DEFAULT):
        self.x0, self.y0, self.nx, self.ny = x0, y0, nx, ny
        self.shape = (32 * ny + 1, 32 * nx + 1)
        self.missing = missing
        self.w = {}
        self.cnt = np.zeros(self.shape, np.float32)

    def add_cell(self, cx, cy, weights, key=lambda fid: fid):
        r0, c0 = 32 * (cy - self.y0), 32 * (cx - self.x0)
        if not (0 <= r0 < self.shape[0] - 1 and 0 <= c0 < self.shape[1] - 1):
            raise ValueError(f"cell ({cx}, {cy}) outside the grid")
        for fid, w in weights.items():
            k = key(fid)
            if k not in self.w:
                self.w[k] = np.zeros(self.shape, np.float32)
            self.w[k][r0:r0 + CELL, c0:c0 + CELL] += w
        self.cnt[r0:r0 + CELL, c0:c0 + CELL] += 1

    def finish(self):
        """(keys, list of weight arrays) normalised; missing vertices go to `missing`."""
        empty = self.cnt == 0
        if empty.any():
            self.w.setdefault(self.missing, np.zeros(self.shape, np.float32))[empty] = 1.0
        c = np.where(empty, 1.0, self.cnt).astype(np.float32)
        keys = sorted(self.w)
        return keys, [self.w[k] / c for k in keys]


# ------------------------------------------------------------------------------------------------- Starfield BTD
def table_order(keys, coverage):
    """LTEX table order for the BTD: rarest first (top layers), the most common last (bottom), ties by key."""
    return sorted(keys, key=lambda k: (coverage[k], k))


def _alphas(wq, forced_bottom, search=True):
    """Top-down 3-bit alphas for weights wq[k, h, w] (k = slots, top first) that sum to 1 per sample: slot j's final
    weight is a_j * prod_{i < j} (1 - a_i), and what is left goes to the bottom (the last slot, forced to alpha 7, or
    the base byte when forced_bottom is False and wq holds the five slots only). Each free slot may round its exact
    alpha down or up; of those 2^free combinations the one with the smallest summed |weight error| (including the
    bottom's) is kept per sample, so quantisation errors do not pile up on the lower layers. search=False rounds each
    exact alpha to the nearest step instead (the comparison in ground-textures.md 4)."""
    k = wq.shape[0]
    free = k - 1 if forced_bottom else k
    shape = wq.shape[1:]
    if not search:
        q = np.zeros(wq.shape, np.int64)
        rem = np.ones(shape)
        for j in range(free):
            a = np.where(rem > 1e-9, wq[j] / np.maximum(rem, 1e-9), 0.0)
            q[j] = np.clip(np.rint(a * ALPHA_MAX), 0, ALPHA_MAX)
            rem = rem * (1.0 - q[j] / ALPHA_MAX)
        if forced_bottom:
            q[k - 1] = ALPHA_MAX
        return q
    qs = np.zeros((1, max(free, 1)) + shape, np.int64)
    rem = np.ones((1,) + shape)
    err = np.zeros((1,) + shape)
    for j in range(free):
        a = np.where(rem > 1e-9, wq[j] / np.maximum(rem, 1e-9), 0.0)
        lo = np.clip(np.floor(a * ALPHA_MAX + 1e-9), 0, ALPHA_MAX)
        cand = np.concatenate([lo, np.minimum(lo + 1, ALPHA_MAX)])
        rem2 = np.concatenate([rem, rem])
        err = np.concatenate([err, err]) + np.abs(cand / ALPHA_MAX * rem2 - wq[j])
        rem = rem2 * (1.0 - cand / ALPHA_MAX)
        qs = np.concatenate([qs, qs])
        qs[:, j] = cand
    err = err + np.abs(rem - (1.0 - wq[:free].sum(0)))
    best = np.argmin(err, axis=0)
    q = np.zeros(wq.shape, np.int64)
    if free:
        idx = np.broadcast_to(best[None, None], (1, free) + shape)
        q[:free] = np.take_along_axis(qs, idx, axis=0)[0]
    if forced_bottom:
        q[k - 1] = ALPHA_MAX
    return q


def encode_quadrant(wq, idx, n, search=True):
    """One quadrant. wq[m, 64, 64]: weights of the table entries idx[m] (ascending table index), > 0 somewhere,
    summing to 1 per sample. Returns (8 quadrant bytes, u16 alpha words [64, 64])."""
    m = len(idx)
    if not 1 <= m <= MAX_TEXTURES or list(idx) != sorted(idx):
        raise ValueError("1..6 textures in ascending table index expected")
    b = [0] * 8
    if m == MAX_TEXTURES:
        slots, base = list(idx[:SLOTS]), idx[SLOTS]
        q = _alphas(wq[:SLOTS], forced_bottom=False, search=search)
        b[6] = n - base
    else:
        slots = list(idx)
        q = _alphas(wq, forced_bottom=True, search=search)
    for j, t in enumerate(slots):
        b[j] = n - t
    word = np.zeros(wq.shape[1:], np.int64)
    for j in range(len(slots)):
        word |= q[j] << (3 * j)
    return bytes(b), word.astype(np.uint16)


def encode(weights, n=None, search=True):
    """weights[n, H, W] float in table order (index = table index), summing to 1 per sample, H and W multiples of 64.
    Returns (quad_map uint8 [H/64, W/64, 8], alpha words uint16 [H, W], stats). Per quadrant the 6 textures with the
    largest summed weight are kept; the rest is renormalised onto them (stats["dropped"] = weight lost)."""
    n = n or weights.shape[0]
    _, H, W = weights.shape
    if H % SF_QUAD or W % SF_QUAD:
        raise ValueError("weights must cover whole quadrants")
    qm = np.zeros((H // SF_QUAD, W // SF_QUAD, 8), np.uint8)
    words = np.zeros((H, W), np.uint16)
    dropped, counts = 0.0, np.zeros(MAX_TEXTURES + 1, np.int64)
    for qy in range(H // SF_QUAD):
        for qx in range(W // SF_QUAD):
            sl = (slice(qy * SF_QUAD, (qy + 1) * SF_QUAD), slice(qx * SF_QUAD, (qx + 1) * SF_QUAD))
            blk = weights[(slice(None),) + sl].astype(np.float64)
            s = blk.sum(axis=(1, 2))
            used = [int(i) for i in np.argsort(-s, kind="stable")[:MAX_TEXTURES] if s[i] > 1e-9]
            if not used:
                used = [int(np.argmax(s))]
            dropped += float(s.sum() - s[used].sum())
            used.sort()
            wq = blk[used]
            tot = wq.sum(0)
            zero = tot <= 1e-12
            if zero.any():                          # all of a sample's weight was dropped: give it the main texture
                main = int(np.argmax(s[used]))
                wq[main][zero] = 1.0
                tot = np.where(zero, 1.0, tot)
            wq = wq / tot
            b, wd = encode_quadrant(wq, used, n, search)
            qm[qy, qx] = np.frombuffer(b, np.uint8)
            words[sl] = wd
            counts[len(used)] += 1
    return qm, words, {"dropped": dropped / (H * W), "textures_per_quadrant": counts.tolist()}


def quadrant_textures(qbytes, n):
    """(slot table indices top first, base table index) of one quadrant, as the decoder reads them: the base is byte 6,
    or without it the last filled slot (fo76utils getCellTextureSet: last valid byte = default texture)."""
    slots = [n - int(v) for v in qbytes[:SLOTS] if 0 < int(v) <= n]
    b6 = int(qbytes[6])
    base = n - b6 if 0 < b6 <= n else (slots[-1] if slots else None)
    return slots, base


def decode(quad_map, words, n):
    """Effective weights [n, H, W] (float32) of a BTD texture section under the over-compositing reading above."""
    H, W = words.shape
    out = np.zeros((n, H, W), np.float32)
    w = words.astype(np.int64)
    for qy in range(quad_map.shape[0]):
        for qx in range(quad_map.shape[1]):
            sl = (slice(qy * SF_QUAD, (qy + 1) * SF_QUAD), slice(qx * SF_QUAD, (qx + 1) * SF_QUAD))
            qb = quad_map[qy, qx]
            rem = np.ones((SF_QUAD, SF_QUAD))
            for k in range(SLOTS):
                v = int(qb[k])
                if not 0 < v <= n:
                    continue
                a = ((w[sl] >> (3 * k)) & 7) / ALPHA_MAX
                out[(n - v,) + sl] += a * rem
                rem = rem * (1.0 - a)
            _slots, base = quadrant_textures(qb, n)
            if base is not None:
                out[(base,) + sl] += rem
    return out
