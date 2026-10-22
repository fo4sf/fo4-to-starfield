"""Offline diagnostics for collision extent clamping and non-finite values.

Used to catch the 0.02 leaf half that crashed Red Rocket (see docs/spikes/red-rocket-crash-bisect.md)
and similar issues. No game data required.
"""
from typing import Iterable, Tuple
import math

from .sfcollision import MIN_LEAF_HALF, MIN_HALF


def report_clamped_halves(halves: Iterable[Tuple[float, float, float]], leaf: bool = False) -> list:
    """Return list of (original, clamped) for any half-extent that was raised to the floor.

    leaf=True uses MIN_LEAF_HALF (0.05); otherwise MIN_HALF (0.005).
    """
    floor = MIN_LEAF_HALF if leaf else MIN_HALF
    clamped = []
    for hx, hy, hz in halves:
        orig = (hx, hy, hz)
        clamped_h = tuple(max(floor, abs(v)) for v in orig)
        if clamped_h != orig and any(abs(v) < floor for v in orig):
            clamped.append((orig, clamped_h))
    return clamped


def has_non_finite(values: Iterable[float]) -> bool:
    """True if any value is NaN or Inf."""
    return any(not math.isfinite(v) for v in values)
