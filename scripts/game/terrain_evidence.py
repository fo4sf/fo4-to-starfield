"""Score one terrain probe without calling the game.

A PASS needs every one of these. Anything missing is UNREAD, never a pass:

- plan, plugin and archive SHA-256 match the pinned hashes exactly
- ground is "plugin" (a procedural or unnamed ground cannot pass, even if the height matches)
- at least two finite position frames, all within reach_m of the point in X/Y
- those frames agree in Z within settle_m (a single frame, or a Z still changing, is not settled)
- the settled height is within tol_m of the expected height, after the recorded offset

A complete reading that landed on the point and is still the wrong height is FAIL.
This does not deploy, launch, or rescore a run whose files are not in this bundle.
"""
import math
import re

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_IDENTITY = ("plan_sha256", "plugin_sha256", "archive_sha256")


def _parse_frame(value):
    if isinstance(value, str):
        try:
            parts = [float(x) for x in value.split()]
        except ValueError:
            return None
    elif isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            parts = [float(x) for x in value]
        except (TypeError, ValueError):
            return None
    else:
        return None
    if len(parts) != 3 or not all(math.isfinite(x) for x in parts):
        return None
    return parts


def _hash_ok(value):
    return isinstance(value, str) and _HEX64.fullmatch(value.strip()) is not None


def _offset(evidence):
    raw = evidence.get("offset")
    if raw is None:
        return None
    parsed = _parse_frame(raw)
    return parsed


def judge(evidence, reach_m=2.0, settle_m=0.05, tol_m=0.5):
    """Return (verdict, why). verdict is PASS, FAIL, or UNREAD."""
    if not isinstance(evidence, dict):
        return "UNREAD", "evidence is not a record"
    pinned = evidence.get("pinned")
    got = evidence.get("identity")
    if not isinstance(pinned, dict) or not isinstance(got, dict):
        return "UNREAD", "plan, plugin and archive hashes were not both recorded"
    for key in _IDENTITY:
        if not _hash_ok(pinned.get(key)) or not _hash_ok(got.get(key)):
            return "UNREAD", f"{key} missing"
        if pinned[key].strip().lower() != got[key].strip().lower():
            return "UNREAD", f"{key} does not match the pinned build"
    ground = evidence.get("ground")
    if ground != "plugin":
        return "UNREAD", f"ground is {ground!r}, not the plugin terrain"
    point = evidence.get("point")
    if not isinstance(point, dict):
        return "UNREAD", "no probe point"
    target = _parse_frame((point.get("x"), point.get("y"), point.get("expect")))
    if target is None:
        return "UNREAD", "probe point is not a finite x, y and expected height"
    if evidence.get("require_offset"):
        shift = _offset(evidence)
        if shift is None:
            return "UNREAD", "overlay offset was not read"
    else:
        shift = _offset(evidence) or [0.0, 0.0, 0.0]
    frames = evidence.get("frames")
    if not isinstance(frames, list) or len(frames) < 2:
        return "UNREAD", "fewer than two settled frames"
    reads = [_parse_frame(frame) for frame in frames]
    if any(read is None for read in reads):
        return "UNREAD", "a frame did not parse"
    tx, ty, expect = target
    ox, oy, oz = shift
    for read in reads:
        if math.hypot(read[0] - (tx + ox), read[1] - (ty + oy)) > reach_m:
            return "UNREAD", "not at the probe point"
    heights = [read[2] - oz for read in reads]
    if max(heights) - min(heights) > settle_m:
        return "UNREAD", "z still changing"
    settled = sum(heights) / len(heights)
    if abs(settled - expect) > tol_m:
        return "FAIL", f"settled {settled:.2f} m, want {expect:.2f} m"
    return "PASS", f"settled {settled:.2f} m, want {expect:.2f} m"
