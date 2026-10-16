"""The Transform adapter (docs/ai/leader-core.md §9): one reference matrix for the core, in the rotation order PR #102
verified on FO4's own precombined references (146,463 of 146,728 tilted references with a unique instance, 2026-10-13).

Bethesda angles turn clockwise seen from the positive axis, so the matrix uses the negated angles, and the model
turns about Z first, then Y, then X (fixed axes): R = Rx(-x) Ry(-y) Rz(-z). A pure Z rotation (most stairs, doors
and walls) is the same under any order; the orders differ only for a reference with an x or y rotation (332,641 of
core64c's 648,358 references, #102). Pure Python, no numpy.

Who agrees today and who does not (tests/test_core_transform.py keeps this true):
  scripts/game/routes.py ref_matrix              Z first since 2026-10-13: equal on every rotation
  src/fo4sf/exterior.py ref_matrix / to_world     X first (R = Rz Ry Rx): equal on heading-only rotations, differs on tilted
  dotnet/PluginSpike/Program.cs RotateOffset      X first (applied X, then Y, then Z): NOT changed by the core (§9 says what it costs)
"""
import math
from dataclasses import dataclass

ROTATION_ORDER = "Z-first"          # R = Rx(-x) Ry(-y) Rz(-z): the model turns about Z, then Y, then X (fixed axes)
UNITS_PER_METRE = 70.0              # Creation Engine units per metre (src/fo4sf/exterior.py UNITS_PER_METRE)
IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def matmul(a, b):
    """Row-major 3x3 product."""
    return tuple(sum(a[3 * r + k] * b[3 * k + c] for k in range(3)) for r in range(3) for c in range(3))


def transpose(m):
    return (m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8])


def apply(m, v):
    """m (row-major 3x3) times the column vector v."""
    return tuple(m[3 * i] * v[0] + m[3 * i + 1] * v[1] + m[3 * i + 2] * v[2] for i in range(3))


def ref_matrix(rot):
    """Row-major 3x3 world rotation of a reference from its (x, y, z) angles in radians: R = Rx(-x) Ry(-y) Rz(-z)."""
    cx, sx = math.cos(-rot[0]), math.sin(-rot[0])
    cy, sy = math.cos(-rot[1]), math.sin(-rot[1])
    cz, sz = math.cos(-rot[2]), math.sin(-rot[2])
    rx = (1.0, 0.0, 0.0, 0.0, cx, -sx, 0.0, sx, cx)
    ry = (cy, 0.0, sy, 0.0, 1.0, 0.0, -sy, 0.0, cy)
    rz = (cz, -sz, 0.0, sz, cz, 0.0, 0.0, 0.0, 1.0)
    return matmul(rx, matmul(ry, rz))


def to_world(v, pos, rot, scale=1.0):
    """A model-space point of a reference placed at pos (same unit as v) with rot (radians) and scale."""
    m = ref_matrix(rot)
    r = apply(m, v)
    return tuple(pos[i] + scale * r[i] for i in range(3))


def to_local(w, pos, rot, scale=1.0):
    """The model-space point that to_world maps onto w (the inverse of a rotation is its transpose)."""
    d = tuple((w[i] - pos[i]) / scale for i in range(3))
    return apply(transpose(ref_matrix(rot)), d)


def metres(units):
    return tuple(float(u) / UNITS_PER_METRE for u in units)


def units(m):
    return tuple(float(x) * UNITS_PER_METRE for x in m)


@dataclass(frozen=True)
class Transform:
    """Where a reference stands: position in metres, (x, y, z) rotation in radians, uniform scale."""
    pos: tuple
    rot: tuple = (0.0, 0.0, 0.0)
    scale: float = 1.0

    def __post_init__(self):
        if len(self.pos) != 3 or len(self.rot) != 3:
            raise ValueError("pos and rot are (x, y, z)")
        try:
            scale = float(self.scale)
        except (TypeError, ValueError):
            raise ValueError("scale is positive") from None
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("scale is positive")
        object.__setattr__(self, "pos", tuple(float(x) for x in self.pos))
        object.__setattr__(self, "rot", tuple(float(x) for x in self.rot))
        object.__setattr__(self, "scale", float(self.scale))

    @classmethod
    def from_units(cls, pos_units, rot, scale=1.0):
        """From a record's position in engine units (70 per metre) and its rotation in radians."""
        return cls(metres(pos_units), tuple(rot), scale)

    @property
    def matrix(self):
        return ref_matrix(self.rot)

    def world(self, v):
        return to_world(v, self.pos, self.rot, self.scale)

    def local(self, w):
        return to_local(w, self.pos, self.rot, self.scale)
