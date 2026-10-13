"""Score terrain probe evidence without calling the game.

A PASS needs every one of these. Anything missing is UNREAD, never a pass:

- plan, plugin and archive SHA-256 match the pinned hashes exactly
- when the record includes those files' bytes, the bytes hash to the pin
- ground is "plugin" (a procedural or unnamed ground cannot pass)
- a recorded offset is a finite x, y, z (a bad value is not treated as zero)
- at least two finite position frames, all within reach_m of the point in X/Y (identical positions are allowed)
- those frames agree in Z within settle_m
- the settled height is within tol_m of the expected height, after that offset
- reach_m, settle_m and tol_m are finite and nonnegative

A complete reading on the point at the wrong height is FAIL.
judge_probe PASSes only when every planned point PASSes. One dropped point
does not let the others count as a finished probe.
This does not deploy, launch, or rescore a run whose files are not in this bundle.
"""
import hashlib
import math
import re

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_IDENTITY = ("plan_sha256", "plugin_sha256", "archive_sha256")
_BODY = (("plan_sha256", "plan"), ("plugin_sha256", "plugin"), ("archive_sha256", "archive"))


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


def _parse_capture(value):
    """Return ((x, y, z), ident, timestamp) or None. Accepts str/list or dict with pos + optional id/time."""
    ident = None
    timestamp = None
    if isinstance(value, dict):
        ident = value.get("id") or value.get("capture")
        timestamp = value.get("time") or value.get("timestamp") or value.get("t")
        value = value.get("pos") or value.get("xyz") or value.get("position")
    parts = _parse_frame(value)
    if parts is None:
        return None
    return parts, ident, timestamp


def _hash_ok(value):
    return isinstance(value, str) and _HEX64.fullmatch(value.strip()) is not None


def _control(value):
    """Finite nonnegative metres, or None. Booleans are not numbers here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return float(value)


def _shift(evidence):
    """(offset, error). An omitted offset is zero unless the probe requires one.

    A present value that is null, short, or non-finite is unreadable. It must not
    fall through to zero and let the height pass in the wrong frame.
    """
    if "offset" not in evidence:
        if evidence.get("require_offset"):
            return None, "overlay offset was not read"
        return [0.0, 0.0, 0.0], None
    parsed = _parse_frame(evidence.get("offset"))
    if parsed is None:
        return None, "offset is not a finite x, y, z"
    return parsed, None


def _bodies(evidence, pinned):
    """None when the bytes match, or an UNREAD reason. No bodies key means unchecked."""
    if "bodies" not in evidence:
        return None
    bodies = evidence.get("bodies")
    if not isinstance(bodies, dict):
        return "recorded bytes are not a record"
    for hash_key, body_key in _BODY:
        if body_key not in bodies:
            return f"{body_key} bytes were not recorded"
        blob = bodies[body_key]
        if isinstance(blob, str):
            blob = blob.encode()
        if not isinstance(blob, (bytes, bytearray)):
            return f"{body_key} bytes are not readable"
        digest = hashlib.sha256(blob).hexdigest()
        if digest != pinned[hash_key].strip().lower():
            return f"{body_key} bytes do not match the pinned hash"
    return None


def judge(evidence, reach_m=2.0, settle_m=0.05, tol_m=0.5):
    """Return (verdict, why). verdict is PASS, FAIL, or UNREAD."""
    reach_m, settle_m, tol_m = _control(reach_m), _control(settle_m), _control(tol_m)
    if reach_m is None or settle_m is None or tol_m is None:
        return "UNREAD", "tolerance is not a finite nonnegative number"
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
    mismatch = _bodies(evidence, pinned)
    if mismatch:
        return "UNREAD", mismatch
    ground = evidence.get("ground")
    if ground != "plugin":
        return "UNREAD", f"ground is {ground!r}, not the plugin terrain"
    point = evidence.get("point")
    if not isinstance(point, dict):
        return "UNREAD", "no probe point"
    target = _parse_frame((point.get("x"), point.get("y"), point.get("expect")))
    if target is None:
        return "UNREAD", "probe point is not a finite x, y and expected height"
    shift, why = _shift(evidence)
    if shift is None:
        return "UNREAD", why
    frames = evidence.get("frames")
    if not isinstance(frames, list) or len(frames) < 2:
        return "UNREAD", "fewer than two settled frames"
    parsed = [_parse_capture(frame) for frame in frames]
    if any(item is None for item in parsed):
        return "UNREAD", "a frame did not parse"
    reads = [item[0] for item in parsed]
    idents = [item[1] for item in parsed]
    times = [item[2] for item in parsed]
    # Identical positions are allowed: independent stationary captures can match exactly.
    # When the collector records capture identifiers or timestamps, a reused one is UNREAD.
    seen_ids = set()
    for ident in idents:
        if ident is not None:
            if ident in seen_ids:
                return "UNREAD", "capture identifier reused"
            seen_ids.add(ident)
    seen_times = set()
    for ts in times:
        if ts is not None:
            if ts in seen_times:
                return "UNREAD", "capture timestamp reused"
            seen_times.add(ts)
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


def judge_probe(evidence, reach_m=2.0, settle_m=0.05, tol_m=0.5):
    """Score every planned point. PASS only when each one PASSes.

    `points` is the plan. `reads` maps a label to that point's frames.
    A missing label is UNREAD. Extra labels are ignored, so they cannot fill a gap.
    """
    if not isinstance(evidence, dict):
        return "UNREAD", "evidence is not a record"
    points = evidence.get("points")
    reads = evidence.get("reads")
    if not isinstance(points, list) or not points:
        return "UNREAD", "no planned points"
    if not isinstance(reads, dict):
        return "UNREAD", "readings were not recorded by label"
    rows = []
    verdicts = []
    for point in points:
        if not isinstance(point, dict) or not point.get("label"):
            return "UNREAD", "a planned point has no label"
        label = point["label"]
        one = {key: evidence[key] for key in ("pinned", "identity", "ground", "require_offset", "bodies")
               if key in evidence}
        if "offset" in evidence:
            one["offset"] = evidence["offset"]
        one["point"] = point
        one["frames"] = reads[label] if isinstance(reads.get(label), list) else []
        verdict, why = judge(one, reach_m, settle_m, tol_m)
        rows.append(f"{label} {verdict}")
        verdicts.append(verdict)
        if verdict != "PASS":
            rows[-1] = f"{label} {verdict}: {why}"
    detail = "; ".join(rows)
    if any(verdict == "FAIL" for verdict in verdicts):
        return "FAIL", detail
    if any(verdict != "PASS" for verdict in verdicts):
        return "UNREAD", detail
    return "PASS", detail
