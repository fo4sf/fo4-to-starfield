"""Independent, read-only continuous evidence audit; no runner/judge imports or game control.

MATCH describes only the documented checks, never full runtime acceptance.
See docs/testing/continuous-evidence.md for required capture and pin metadata.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys


HASH = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
REPLY_NUMBER = r"-?[0-9]+\.[0-9]{2}"
POSITION_LABEL = re.compile(r"^[ \t]*Get[ \t]*Pos[ \t]*:[ \t]*([XYZ])\b", re.I)
POSITION = re.compile(r"[ \t]*Get[ \t]*Pos[ \t]*:[ \t]*([XYZ])[ \t]*>>[ \t]*("
                      + REPLY_NUMBER + r")[ \t]*", re.I)
ANGLE_LABEL = re.compile(r"^[ \t]*Get[ \t]*Angle[ \t]*:[ \t]*Z\b", re.I)
ANGLE = re.compile(r"[ \t]*Get[ \t]*Angle[ \t]*:[ \t]*Z[ \t]*>>[ \t]*("
                   + REPLY_NUMBER + r")[ \t]*", re.I)
SESSION_MARKER = re.compile(r"FO4SF_READ_[0-9a-f]{64}\Z")
SELF_REPLY = re.compile(r"[ \t]*GetSelf[ \t]*>>[ \t]*\(([0-9a-f]{8})\)[ \t]*", re.I)
COMMAND = re.compile(r"ClearConsole|(?:player\.)?getpos [xyz]|prid [0-9A-Fa-f]{8}|"
                     r"GetSelf|player\.getangle z|player\.setangle [xz] " + NUMBER, re.I)
MAX_EVENTS = 1600
SCOPES = {
    "source": "pinned bundled source/plan bytes and recorded source commit",
    "installed": "planned identities compared to retained install snapshot; no live disk/process verification",
    "reads": "labelled current-session OCR, read selection, finite XYZ and independently settled pairs",
    "freshness": "invocation-bound visible console challenges required; actual producer emission pending runtime proof",
    "captures": "native PNG bytes/physical identity and invocation identities; equal pixels are allowed",
    "continuity": "recorded commands, holds, ordered read geometry and route witnesses",
    "ground": "exact planned file SHA/schema and bridge node witnesses; full ground/contact validation out of scope",
    "merge_probes": "exact same-session selected reference before diagnostic local/merged residuals",
    "runtime": "engine, materials, visuals, controls, STOP behavior and full acceptance out of scope",
}


def _session_marker(invocation_id):
    """Protocol value only: this does not assert a game command can emit the challenge."""
    if not isinstance(invocation_id, str) or not ID.fullmatch(invocation_id):
        return None
    return "FO4SF_READ_" + hashlib.sha256(invocation_id.encode("utf-8")).hexdigest()


def _shared():
    """Lazy sibling loading also works when the parent is being imported or run as __main__."""
    existing = sys.modules.get("commonwealth_evidence")
    if existing is not None and hasattr(existing, "file_bytes"):
        return existing
    spec = importlib.util.spec_from_file_location(
        "_continuous_commonwealth_helpers", Path(__file__).with_name("commonwealth_evidence.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Audit:
    def __init__(self, test, obs, folder, kind):
        self.h = _shared()
        self.test = test if isinstance(test, dict) else {}
        self.obs = obs if isinstance(obs, dict) else {}
        self.folder = Path(folder)
        self.report = {"id": self.test.get("id"), "kind": kind, "issues": [], "rows": [],
                       "capture_identities": [], "file_identities": [], "check_scopes": dict(SCOPES),
                       "runtime_accepted": False, "acceptance_gate": False}
        self.physical, self.invocations, self.native, self.ocr_files = {}, set(), set(), set()
        self.event_count = 0
        if not isinstance(test, dict) or not isinstance(obs, dict):
            self.issue("SCHEMA", "test and obs must be objects")
        if self.test.get("kind") != kind:
            self.issue("KIND", "expected " + kind)
        if not isinstance(self.test.get("id"), str) or not ID.fullmatch(self.test["id"]):
            self.report["id"] = None
            self.issue("SCHEMA", "bounded test id required")
        if self.obs.get("stopped"):
            self.issue("STOPPED", "producer recorded a stopped step")

    def issue(self, cls, detail, label=None, mismatch=False):
        item = {"status": "MISMATCH" if mismatch else "INCONCLUSIVE", "class": cls, "detail": detail}
        if label is not None:
            item["label"] = label
        self.report["issues"].append(item)

    def finish(self):
        issues = self.report["issues"]
        self.report["status"] = ("INCONCLUSIVE" if any(i["status"] == "INCONCLUSIVE" for i in issues)
                                 else "MISMATCH" if issues else "MATCH")
        return self.report

    def number(self, value, lo, hi, label):
        if not self.h.finite(value) or not lo <= value <= hi:
            self.issue("NUMBER", f"{label} must be finite in [{lo}, {hi}]")
            return None
        return value

    def vec(self, value, label):
        if not self.h.vector(value) or any(abs(v) > 1e6 for v in value):
            self.issue("VECTOR", "expected finite bounded XYZ", label)
            return None
        return value

    def file(self, name, label, image=False):
        try:
            if image:
                identity = self.h.capture(self.folder, name)
                key = tuple(identity["physical_identity"])
                if key in self.physical:
                    self.issue("CAPTURE_REUSE", "native file already used by " + self.physical[key],
                               label, True)
                else:
                    self.physical[key] = label
                self.report["capture_identities"].append(dict(identity, label=label))
                return None, identity
            raw, identity = self.h.file_bytes(self.folder, name)
            self.report["file_identities"].append(dict(identity, label=label))
            return raw, identity
        except (OSError, ValueError, TypeError, SyntaxError, self.h.Image.DecompressionBombError) as error:
            self.issue("CAPTURE" if image else "FILE", str(error), label)
            return None, None

    def provenance(self, event, label, prefix="read", screen=False):
        meta = event.get(prefix + "_invocation")
        _, cap = self.file(event.get(prefix + "_capture"), label, True)
        if not isinstance(meta, dict):
            self.issue("PROVENANCE", "missing invocation object", label)
            return None, None
        for field, seen in (("id", self.invocations), ("capture_id", self.native)):
            value = meta.get(field)
            if not isinstance(value, str) or not ID.fullmatch(value):
                self.issue("PROVENANCE", "missing/invalid invocation " + field, label)
            elif value in seen:
                self.issue("CAPTURE_REUSE", "reused invocation " + field, label, True)
            else:
                seen.add(value)
        if meta.get("source") != ("native_screen" if screen else "native_console"):
            self.issue("PROVENANCE", "capture source must identify a native invocation", label)
        t = self.number(meta.get("t"), 0, 86400, label + ".t")
        if cap:
            self.report["capture_identities"][-1].update(
                invocation_id=meta.get("id") if isinstance(meta.get("id"), str) else None,
                native_capture_id=meta.get("capture_id") if isinstance(meta.get("capture_id"), str) else None,
                t=t, source=meta.get("source") if isinstance(meta.get("source"), str) else None)
        if cap and meta.get("capture_sha256") != cap["sha256"]:
            self.issue("CAPTURE_BINDING", "invocation hash does not match native PNG", label, True)
        if screen:
            return t, None
        raw, identity = self.file(event.get(prefix + "_ocr"), label + ".ocr")
        if identity:
            physical = tuple(identity["physical_identity"])
            if physical in self.ocr_files:
                self.issue("CAPTURE_REUSE", "one OCR file reused for independent read invocations", label, True)
            self.ocr_files.add(physical)
        if identity and (meta.get("ocr_sha256") != identity["sha256"]
                         or meta.get("ocr_capture_id") != meta.get("capture_id")):
            self.issue("OCR_BINDING", "OCR is not bound to this capture", label, True)
        if raw is None:
            return t, None
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeError:
            self.issue("OCR", "OCR must be UTF-8", label)
            return t, None
        challenge = meta.get("session_marker")
        expected = _session_marker(meta.get("id"))
        if not isinstance(challenge, str) or not SESSION_MARKER.fullmatch(challenge) \
                or expected is None or challenge != expected:
            self.issue("FRESHNESS", "session_marker is missing or not bound to this invocation id", label)
            return t, None
        clears = list(re.finditer(r"\bClear\s*Console\b", text, re.I))
        if not clears:
            self.issue("FRESHNESS", "ClearConsole context absent; challenge freshness unverified", label)
            return t, None
        lines = text[clears[-1].end():].splitlines()
        markers = [n for n, line in enumerate(lines) if line.strip() == challenge]
        if len(markers) != 1:
            self.issue("FRESHNESS", "need exactly this invocation's visible session challenge after ClearConsole", label)
            return t, None
        current = lines[markers[0] + 1:]
        reply_lines = [line for line in current if POSITION_LABEL.match(line)]
        matches = [POSITION.fullmatch(line) for line in reply_lines]
        if len(matches) != 3 or any(m is None for m in matches) \
                or [m[1].lower() for m in matches] != list("xyz"):
            self.issue("OCR_SESSION", "need exactly three complete two-decimal XYZ reply lines without residue", label)
            return t, None
        values = [float(m[2]) for m in matches]
        if not self.h.vector(values) or any(abs(v) > 1e6 for v in values):
            self.issue("OCR", "position outside finite coordinate bounds", label)
            return t, None
        head_lines = [line for line in current if ANGLE_LABEL.match(line)]
        heads = [ANGLE.fullmatch(line) for line in head_lines]
        echoes = [line.strip().lstrip("> ").lower() for line in current
                  if COMMAND.fullmatch(line.strip().lstrip("> "))]
        return t, {"xyz": values, "heading": float(heads[0][1])
                   if len(heads) == 1 and heads[0] is not None else None, "echoes": echoes,
                   "lines": current}

    def diagnostic_selection(self, parsed, ref, label):
        """Bind object XYZ to one successful selection, never merely an echoed prid.

        Deliberately narrow consumer protocol, not a fuzzy native OCR adapter. The
        complete ordered block also rules out a refusal or another selection/query
        between the identity reply and the coordinates.
        """
        lines = [line.strip() for line in parsed["lines"] if line.strip()]
        self_replies = [SELF_REPLY.fullmatch(line) for line in lines
                        if re.match(r"GetSelf\b.*>>", line, re.I)]
        if len(self_replies) == 1 and self_replies[0] is not None \
                and self_replies[0][1].lower() != ref:
            self.issue("REFERENCE_SELECTION", "GetSelf identifies a different selected reference", label, True)
            return False
        if len(lines) != 9 or lines[0].lstrip("> ").lower() != "prid " + ref \
                or lines[1].lstrip("> ").lower() != "getself" \
                or len(self_replies) != 1 or self_replies[0] is None \
                or SELF_REPLY.fullmatch(lines[2]) is None:
            self.issue("REFERENCE_SELECTION", "need one current prid/GetSelf/reply block before object XYZ", label)
            return False
        for n, axis in enumerate("xyz"):
            query, reply = lines[3 + 2 * n:5 + 2 * n]
            position = POSITION.fullmatch(reply)
            if query.lstrip("> ").lower() != "getpos " + axis \
                    or position is None or position[1].lower() != axis:
                self.issue("REFERENCE_SELECTION", "object XYZ must follow selection proof without intervening commands",
                           label)
                return False
        return True

    def commands(self, event, label, heading=False, diagnostic=False):
        cmds = event.get("cmds")
        if not isinstance(cmds, list) or not 4 <= len(cmds) <= 32 or any(
                not isinstance(c, str) for c in cmds):
            self.issue("COMMANDS", "missing complete typed command list", label)
            return
        for cmd in cmds:
            if not COMMAND.fullmatch(cmd):
                self.issue("TYPED", "route-time command outside read/turn whitelist: " + cmd, label, True)
            turn = re.fullmatch(r"player\.setangle ([xz]) (" + NUMBER + ")", cmd, re.I)
            if turn:
                value = float(turn[2])
                lo, hi = (-90, 90) if turn[1].lower() == "x" else (0, 360)
                if not self.h.finite(value) or not lo <= value <= hi:
                    self.issue("TYPED", "turn outside finite angle bounds", label, True)
        lowered = [c.lower() for c in cmds]
        ref = event.get("ref")
        if diagnostic:
            if not isinstance(ref, str) or not re.fullmatch(r"[0-9a-fA-F]{8}", ref):
                self.issue("COMMANDS", "invalid diagnostic reference", label)
            required = ["clearconsole", "prid " + str(ref).lower(), "getself"] + ["getpos " + k for k in "xyz"]
        else:
            required = ["clearconsole"] + ["player.getpos " + k for k in "xyz"]
        if any(c not in lowered for c in required):
            self.issue("COMMANDS", "missing ClearConsole/player.getpos X/Y/Z", label)
        if heading and "player.getangle z" not in lowered:
            self.issue("FACING", "missing getangle command", label)
        sequence = [c for c in lowered if not c.startswith("player.setangle ")]
        expected = required + (["player.getangle z"] if heading or "player.getangle z" in lowered else [])
        if lowered[0] != "clearconsole" or sequence != expected:
            self.issue("COMMANDS", "commands must clear, select the allowed actor and read XYZ/angle in order",
                       label, True)

    def read(self, event, label, key="read", heading=False, commands=True, diagnostic=False):
        issue_start = len(self.report["issues"])
        self.event_count += 1
        if self.event_count > MAX_EVENTS:
            raise ValueError("too many read events")
        if not isinstance(event, dict):
            event = {"read": event} if isinstance(event, str) else {}
        if not diagnostic and event.get("ref") is not None:
            self.issue("COMMANDS", "object references cannot supply player position evidence", label, True)
        p = self.h.xyz(event.get(key))
        if p is None or any(abs(v) > 1e6 for v in p):
            self.issue("UNREAD", "missing/malformed finite XYZ", label)
            p = None
        t, parsed = self.provenance(event, label, key)
        if commands:
            self.commands(event, label, heading, diagnostic)
        if parsed is not None:
            queries = [c for c in parsed["echoes"] if "getpos " in c or "getangle " in c]
            expected = [("" if diagnostic else "player.") + "getpos " + axis for axis in "xyz"]
            if heading:
                expected.append("player.getangle z")
            elif "player.getangle z" in queries:
                expected.append("player.getangle z")
            if queries != expected:
                self.issue("OCR_ACTOR", "current-session command echoes do not establish the required actor/XYZ order",
                           label, bool(queries))
            selected = [c[5:] for c in parsed["echoes"] if c.startswith("prid ")]
            if (diagnostic and selected != [str(event.get("ref")).lower()]) or (not diagnostic and selected):
                self.issue("OCR_ACTOR", "current-session object selection contradicts the permitted read actor",
                           label, bool(selected))
        if p is not None and parsed is not None and math.dist(p, parsed["xyz"]) > 0.011:
            self.issue("READ_SELECTION", "reported XYZ disagrees with current-session OCR", label, True)
        h = event.get("heading") if heading else None
        if heading:
            h = self.number(h, 0, 360, label + ".heading")
            if parsed and (not self.h.finite(parsed["heading"]) or h is None):
                self.issue("FACING", "heading missing from current-session OCR", label)
            elif parsed and not 0 <= parsed["heading"] <= 360:
                self.issue("FACING", "OCR heading outside 0..360 degrees", label, True)
            elif parsed and abs((h - parsed["heading"] + 180) % 360 - 180) > 0.011:
                self.issue("FACING", "heading disagrees with OCR", label, True)
        selection_verified = None
        if diagnostic:
            ref = str(event.get("ref")).lower()
            proof = parsed is not None and self.diagnostic_selection(parsed, ref, label)
            # A correct-looking self reply cannot authorize metadata-derived
            # residuals when this read's commands, XYZ or capture binding failed.
            selection_verified = proof and len(self.report["issues"]) == issue_start
            if not selection_verified:
                p = None
        row = {"label": label, "observed": p, "t": t, "heading": h}
        if diagnostic:
            row["selection_verified"] = selection_verified
        self.report["rows"].append(row)
        return p, t, h

    def settled(self, owner, label, summary="read", records="reads", heading=False, after=None):
        events = owner.get(records)
        if not isinstance(events, list) or not 2 <= len(events) <= 16:
            self.issue("SETTLED", "need 2..16 independently retained read events", label)
            events = []
        readings = [self.read(e, f"{label}.{n}", heading=heading) for n, e in enumerate(events)]
        if after is not None and (not readings or readings[0][1] is None or readings[0][1] <= after):
            self.issue("TIME", "settled read window must begin after the preceding stage", label)
        if any(a[1] is None or b[1] is None or b[1] <= a[1] for a, b in zip(readings, readings[1:])):
            self.issue("TIME", "raw settled reads must be in strict time order", label)
        p = self.h.xyz(owner.get(summary))
        if len(readings) < 2 or p is None:
            self.issue("SETTLED", "summary or settled pair absent", label)
            return None, None, None
        a, b = readings[-2:]
        if a[0] is None or b[0] is None or a[1] is None or b[1] is None \
                or not 3 <= b[1] - a[1] <= 120 or any(abs(x - y) >= 0.3 for x, y in zip(a[0], b[0])):
            self.issue("SETTLED", "final consecutive reads do not independently establish settling", label)
        if b[0] is None:
            self.issue("READ_SELECTION", "summary cannot be bound to unread raw data", label)
        elif math.dist(p, b[0]) > 0.011:
            self.issue("READ_SELECTION", "summary differs from the last raw read", label, True)
        return p, b[1], b[2] if heading else None

    def anchor(self):
        offset = self.vec(self.obs.get("offset"), "offset")
        local = self.vec(self.test.get("spawn_local"), "spawn_local")
        self.report["offset"] = offset
        owner = {"read": self.obs.get("spawn_read"), "reads": self.obs.get("spawn_reads")}
        spawn, t, _ = self.settled(owner, "spawn")
        if self.obs.get("offset_from") != "spawn" or self.obs.get("spawn_settled") is not True:
            self.issue("FRAME", "offset must be derived from a reported settled spawn")
        if offset is not None and local is not None and spawn is not None:
            if any(abs(a - b - c) > 0.011 for a, b, c in zip(spawn, local, offset)):
                self.issue("FRAME", "spawn-local does not equal the finite offset", mismatch=True)
        return offset, spawn, t

    def pins(self):
        pins = self.test.get("evidence_pins")
        if not isinstance(pins, dict):
            self.issue("PINS", "planned source/plan/experiment pins absent")
            return
        commit = pins.get("source_commit")
        if not isinstance(commit, str) or not COMMIT.fullmatch(commit) \
                or self.obs.get("source_commit") != commit:
            self.issue("SOURCE_PIN", "exact source commit missing or different")
        sources = pins.get("source_files")
        if not isinstance(sources, dict) or not 1 <= len(sources) <= 64:
            self.issue("SOURCE_PIN", "nonempty bundled source file hashes required")
        else:
            for name, digest in sources.items():
                raw, identity = self.file(name, "source." + str(name))
                if not isinstance(digest, str) or not HASH.fullmatch(digest):
                    self.issue("SOURCE_PIN", "invalid planned source SHA")
                elif identity and identity["sha256"] != digest:
                    self.issue("SOURCE_PIN", "source bytes differ from plan", str(name), True)
        plan = pins.get("plan")
        if not isinstance(plan, dict):
            self.issue("PLAN_PIN", "planned normalized test snapshot absent")
        else:
            raw, identity = self.file(plan.get("file"), "plan")
            if not isinstance(plan.get("sha256"), str) or not HASH.fullmatch(plan["sha256"]):
                self.issue("PLAN_PIN", "invalid planned plan SHA")
            elif identity and identity["sha256"] != plan["sha256"]:
                self.issue("PLAN_PIN", "plan snapshot bytes changed", mismatch=True)
            if raw is not None:
                snapshot = json.loads(raw.decode("utf-8-sig"))
                normalized = {k: v for k, v in self.test.items() if k != "evidence_pins"}
                if snapshot != {"test": normalized}:
                    self.issue("PLAN_PIN", "snapshot does not describe the audited test", mismatch=True)
        raw, _ = self.file(self.obs.get("install_file"), "install")
        if raw is None:
            self.issue("INSTALL_PIN", "independent retained install snapshot required")
            return
        receipt = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(receipt, dict) or receipt.get("complete") is not True:
            self.issue("INSTALL_PIN", "install snapshot absent/incomplete")
            return
        for planned, recorded in (("experiment_files", "files"), ("experiment_source_files", "source_files")):
            values = pins.get(planned)
            if not isinstance(values, dict) or not values or len(values) > 100000 \
                    or any(not isinstance(k, str) or not isinstance(v, str)
                           or not HASH.fullmatch(v) for k, v in values.items()):
                self.issue("INSTALL_PIN", "nonempty installed and experiment source hashes required")
            elif receipt.get(recorded) != values:
                self.issue("INSTALL_PIN", "retained experiment identities differ from plan", mismatch=True)

    def motion(self, previous, current, hold, label):
        if previous is None or current is None:
            return
        p, t = previous
        q, u = current
        if p is None or q is None or t is None or u is None or hold is None:
            self.issue("CONTINUITY", "read/time/hold gap cannot establish continuity", label)
            return
        if not hold / 1000 <= u - t <= hold / 1000 + 120:
            self.issue("TIME", "read chronology contradicts the hold bounds", label)
        if math.dist(p, q) > 9 * (hold / 1000 + 2) + 1:
            self.issue("JUMP", "XYZ displacement exceeds the bounded walking allowance", label, True)

    def hud(self, event, label):
        if event.get("hud") is not True:
            self.issue("HUD", "positive HUD observation missing", label)
        t, _ = self.provenance(event, label + ".hud", "hud", True)
        read_meta = event.get("read_invocation", {})
        if isinstance(read_meta, dict) and self.h.finite(read_meta.get("t")) and t is not None \
                and not 0 <= t - read_meta["t"] <= 120:
            self.issue("TIME", "HUD capture is outside the read invocation window", label)
        if event.get("popup"):
            self.issue("POPUP", "screen text requires independent review", label)


def _poly(value, audit, label, walk=False):
    if not isinstance(value, list) or not 2 <= len(value) <= (400 if walk else 64):
        audit.issue("ROUTE", "need a nonempty bounded planned route", label)
        return None
    points = []
    for n, point in enumerate(value):
        if not isinstance(point, list) or len(point) not in ((4, 5) if walk else (3,)):
            audit.issue("ROUTE", "malformed waypoint", label)
            return None
        p = audit.vec(point[:3], f"{label}.{n}")
        if p is None:
            return None
        if walk and (audit.number(point[3], 0.3, 20, label + ".reach") is None
                     or len(point) == 5 and (type(point[4]) not in (int, float) or point[4] not in (0, 1))):
            audit.issue("ROUTE", "invalid reach/keep flag", label)
            return None
        points.append(p)
    if sum(math.dist(a[:2], b[:2]) for a, b in zip(points, points[1:])) <= 0:
        audit.issue("ROUTE", "route has no horizontal length", label)
        return None
    return points


def _project(poly, p):
    best, length = (math.inf, 0), 0
    for a, b in zip(poly, poly[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        size = math.hypot(dx, dy)
        t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / size**2)) if size else 0
        d = math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
        if d < best[0]:
            best = d, length + t * size
        length += size
    return best


def _route(audit, poly, reads, label, radius, offroute, required=None):
    readable = [p for p in reads if p is not None]
    if not readable:
        audit.issue("ROUTE", "no continuous readable route steps", label)
        return
    for p in readable:
        if _project(poly, p)[0] > offroute:
            audit.issue("OFFROUTE", "read is outside the route corridor", label, True)
    wanted = required if required is not None else [(p, radius) for p in poly]
    cursor = 0
    for point, reach in wanted:
        hit = next((n for n in range(cursor, len(reads))
                    if reads[n] is not None and math.dist(reads[n], point) <= reach), None)
        if hit is None:
            audit.issue("ROUTE_WITNESS", "planned waypoint lacks an ordered XYZ read witness", label)
            return
        cursor = hit  # one read may genuinely reach overlapping waypoint radii
    if reads[-1] is None or math.dist(reads[-1], poly[-1]) > radius:
        audit.issue("GOAL", "last raw read does not reach the XYZ goal", label)


def _cell(p):
    return tuple(math.floor(v / 100) for v in p[:2])


def _borders(poly):
    """Exact translated polyline borders, including repeated occurrences and endpoint semantics."""
    current, out = _cell(poly[0]), []
    budget = 10000
    for a, b in zip(poly, poly[1:]):
        delta = [b[k] - a[k] for k in range(2)]
        times = {0.0, 1.0}
        for k in range(2):
            if delta[k]:
                lo, hi = sorted((a[k], b[k]))
                budget -= math.floor(hi / 100) - math.ceil(lo / 100) + 1
                if budget < 0:
                    raise ValueError("border enumeration exceeds bounds")
                for grid in range(math.ceil(lo / 100), math.floor(hi / 100) + 1):
                    t = (grid * 100 - a[k]) / delta[k]
                    if 0 <= t <= 1:
                        times.add(t)
        for t in sorted(times):
            sample = min(1.0, t + 1e-8) if t < 1 else 1.0
            cell = _cell([a[k] + delta[k] * sample for k in range(2)])
            if cell != current:
                if sum(abs(x - y) for x, y in zip(current, cell)) != 1:
                    raise ValueError("simultaneous/ambiguous cell borders")
                out.append((current, cell))
                current = cell
    return out


def _ground(audit):
    test = audit.test
    path = test.get("ground_path")
    name = test.get("ground")
    digest = test.get("ground_sha256")
    if not isinstance(digest, str) or not HASH.fullmatch(digest):
        audit.issue("GROUND_PIN", "exact planned ground SHA missing")
        return None
    try:
        if path is not None:
            if not isinstance(path, str):
                raise ValueError("ground_path must name the exact planned file")
            p = Path(path)
            if not p.is_absolute():
                if p.name != path:
                    raise ValueError("relative ground_path must be a confined filename")
                p = audit.folder / p
            raw, identity = audit.h.file_bytes(p.parent, p.name)
        else:
            raw, identity = audit.h.file_bytes(audit.folder, name)
        audit.report["file_identities"].append(dict(identity, label="ground"))
        if identity["sha256"] != digest:
            audit.issue("GROUND_PIN", "exact planned ground bytes changed", mismatch=True)
            return None
        ground = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(ground, dict) or not all(k in ground for k in ("terrain", "surfaces", "owners", "path")):
            raise ValueError("pinned ground lacks terrain/surfaces/owners/path schema")
        terrain = ground["terrain"]
        if not isinstance(terrain, dict) or not all(audit.h.finite(terrain.get(k)) for k in ("x0", "y0", "step")) \
                or terrain["step"] <= 0:
            raise ValueError("malformed finite terrain grid")
        rows = terrain.get("rows")
        if not isinstance(rows, list) or not 2 <= len(rows) <= 10000 \
                or not isinstance(rows[0], list) or not 2 <= len(rows[0]) <= 10000 \
                or len(rows) * len(rows[0]) > 1000000 \
                or any(not isinstance(row, list) or len(row) != len(rows[0])
                       or not all(audit.h.finite(z) for z in row) for row in rows):
            raise ValueError("malformed/oversized/nonfinite terrain rows")
        path_points = ground["path"]
        if not isinstance(path_points, list) or not 2 <= len(path_points) <= 4000 \
                or any(not isinstance(p, list) or len(p) != 2
                       or not audit.h.vector(p + [0]) for p in path_points):
            raise ValueError("malformed ground path")
        return ground
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        audit.issue("GROUND_PIN", str(error))
        return None


def _bridge(audit, ground, poly, reads):
    bridge = audit.test.get("bridge")
    if not isinstance(bridge, dict) or not bridge:
        audit.issue("BRIDGE", "planned bridge identity/span required")
        return
    span = bridge.get("span")
    count = bridge.get("min_reads", 2)
    src = bridge.get("src")
    if not isinstance(src, str) or not 1 <= len(src) <= 128 \
            or not isinstance(span, list) or len(span) != 2 or not all(audit.h.finite(v) for v in span) \
            or not 0 <= span[0] < span[1] or type(count) is not int or not 2 <= count <= 50:
        audit.issue("BRIDGE", "invalid bridge progression specification")
        return
    if ground is None:
        audit.issue("BRIDGE", "pinned surface data unavailable")
        return
    surfaces, owners = ground["surfaces"], ground["owners"]
    if not isinstance(surfaces, dict) or not isinstance(owners, list) or any(
            not isinstance(o, dict) or not isinstance(o.get("src"), str) or not o["src"] for o in owners):
        audit.issue("BRIDGE", "malformed pinned surface schema")
        return
    origin = [surfaces.get("x0"), surfaces.get("y0")]
    step, nodes = surfaces.get("step"), surfaces.get("nodes")
    if not all(audit.h.finite(v) for v in origin) or not audit.h.finite(step) \
            or not 0.1 <= step <= 10 or not isinstance(nodes, dict):
        audit.issue("BRIDGE", "invalid surface grid")
        return
    on, progression = [], []
    for n, p in enumerate(reads):
        if p is None:
            continue
        s = _project(poly, p)[1]
        progression.append((n, s))
        indices = [round((p[k] - origin[k]) / step) for k in range(2)]
        reach = math.ceil(0.75 / step)
        contact = False
        for i in range(indices[0] - reach, indices[0] + reach + 1):
            for j in range(indices[1] - reach, indices[1] + reach + 1):
                if math.hypot(origin[0] + i * step - p[0], origin[1] + j * step - p[1]) > 0.75:
                    continue
                for node in nodes.get(f"{i},{j}", []):
                    if not isinstance(node, list) or len(node) != 2 or not audit.h.finite(node[0]) \
                            or type(node[1]) is not int or not 0 <= node[1] < len(owners) \
                            or not isinstance(owners[node[1]], dict):
                        audit.issue("BRIDGE", "malformed surface node")
                        return
                    if owners[node[1]].get("src") == bridge.get("src") and abs(p[2] - node[0]) <= 0.6:
                        contact = True
        if contact and span[0] - 0.75 <= s <= span[1] + 0.75:
            on.append((n, s))
    if len(on) < count or on[-1][1] - on[0][1] < max(1, (span[1] - span[0]) - 3) \
            or any(b[1] <= a[1] + 0.1 for a, b in zip(on, on[1:])) \
            or not any(n < on[0][0] and s < span[0] - 0.5 for n, s in progression) \
            or not any(n > on[-1][0] and s > span[1] + 0.5 for n, s in progression):
        audit.issue("BRIDGE_PROGRESS", "need ordered deck progression across the span, bracketed by reads")


def _inspect_walk(audit):
    audit.pins()
    offset, origin, origin_t = audit.anchor()
    ground = _ground(audit)
    poly = _poly(audit.test.get("waypoints"), audit, "waypoints", True)
    if offset is None or poly is None:
        return
    legs = audit.obs.get("legs")
    if not isinstance(legs, list) or not 2 <= len(legs) <= 401 \
            or any(not isinstance(x, dict) for x in legs):
        audit.issue("LEGS", "need 2..401 leg objects")
        return
    if audit.test.get("setup") is True:
        setup = audit.obs.get("setup")
        if not isinstance(setup, dict):
            audit.issue("START", "setup evidence absent")
            setup = {}
        spawn_t = origin_t
        origin, origin_t, _ = audit.settled(setup, "setup", after=spawn_t)
        if setup.get("settled") is not True or spawn_t is None or origin_t is None or origin_t <= spawn_t:
            audit.issue("START", "setup settling/chronology not established")
        target = audit.vec(audit.test.get("start"), "start")
        if origin and target and math.dist(origin, [target[k] + offset[k] for k in range(3)]) > 3:
            audit.issue("START", "setup settled away from the planned XYZ start", mismatch=True)
    elif audit.test.get("setup") not in (None, False):
        audit.issue("SCHEMA", "setup must be boolean")
    previous, hold, local_reads = (origin, origin_t), 0, []
    for n, leg in enumerate(legs):
        label = f"leg.{n}"
        if type(leg.get("n")) is not int or leg["n"] != n:
            audit.issue("LEG_SEQUENCE", "n must be contiguous from zero", label)
        p, t, _ = audit.read(leg, label)
        finished_t = t
        if t is not None and previous[1] is not None and hold is not None \
                and t - previous[1] < hold / 1000:
            audit.issue("TIME", "primary read precedes completion of the previous leg's hold", label)
        used = audit.h.xyz(leg.get("used"))
        chosen = leg.get("used_from")
        if "confirmed" in leg and type(leg["confirmed"]) is not bool:
            audit.issue("CONFIRMATION", "confirmation must be boolean", label)
        if leg.get("confirmed") is True and "reread" not in leg:
            audit.issue("CONFIRMATION", "confirmed data lacks an independent reread", label)
        if "reread" in leg:
            q, u, _ = audit.read(leg, label + ".reread", "reread", commands=False)
            finished_t = u
            if t is None or u is None or not 0 < u - t <= 120:
                audit.issue("TIME", "reread chronology absent/inconsistent", label)
            if leg.get("confirmed") is True and (p is None or q is None or math.dist(p, q) > 1):
                audit.issue("CONFIRMATION", "claimed agreeing confirmation disagrees with raw data", label, True)
            if chosen == "reread":
                if p and q and math.dist(p, q) > 1:
                    limit = 9 * ((hold or 0) / 1000 + 2) + 1
                    if leg.get("read_rejected") != "implausible" or previous[0] is None \
                            or math.dist(previous[0], p) <= limit or math.dist(previous[0], q) > limit:
                        audit.issue("REREAD", "disagreeing replacement is not independently justified", label)
                p, t = q, u
        if chosen not in ("read", "reread") or chosen == "reread" and "reread" not in leg:
            audit.issue("READ_SELECTION", "explicit read/reread selection required", label)
        if used is None or p is None:
            audit.issue("READ_SELECTION", "selected raw XYZ or used value missing", label)
        elif math.dist(used, p) > 0.011:
            audit.issue("READ_SELECTION", "used differs from the selected actual raw read", label, True)
        if n == 0:
            if origin is None or p is None or math.dist(origin, p) > 3:
                audit.issue("START_CONTINUITY", "first leg is not linked to settled arrival/setup")
        audit.motion(previous, (p, t), hold, label)
        audit.hud(leg, label)
        local_reads.append([p[k] - offset[k] for k in range(3)] if p else None)
        action = leg.get("action")
        if n < len(legs) - 1:
            if action != "aim":
                audit.issue("LEG_ACTION", "nonterminal leg must aim", label)
            hold = audit.number(leg.get("hold_ms"), 100, 10000, label + ".hold")
            heading = audit.number(leg.get("heading"), 0, 360, label + ".heading")
            expected_cmd = re.compile(r"player\.setangle z (" + NUMBER + r")\Z", re.I)
            turns = [float(m[1]) for c in leg.get("cmds", []) if isinstance(c, str)
                     and (m := expected_cmd.fullmatch(c))]
            if heading is None or not turns or abs((turns[-1] - heading + 180) % 360 - 180) > 0.011:
                audit.issue("COMMANDS", "heading lacks matching typed turn", label)
        elif action != "done" or audit.obs.get("walk_stopped") != "goal":
            audit.issue("LEG_ACTION", "terminal goal decision absent")
        previous = p, finished_t
    radius = audit.number(audit.test.get("goal_radius", 3), 0.5, 20, "goal_radius")
    offroute = audit.number(audit.test.get("offroute_m", 10), 2, 50, "offroute_m")
    if radius is not None and offroute is not None:
        required = [(p, w[3]) for p, w in zip(poly, audit.test["waypoints"])
                    if len(w) == 4 or w[4] == 1]
        _route(audit, poly, local_reads, "walk", radius, offroute, required)
    translated = [[p[k] + offset[k] for k in range(3)] for p in poly]
    expected = _borders(translated)
    actual = []
    for a, b in zip(local_reads, local_reads[1:]):
        if a is None or b is None:
            audit.issue("CROSSING", "read gap prevents ordered border verification")
            continue
        ca = _cell([a[k] + offset[k] for k in range(3)])
        cb = _cell([b[k] + offset[k] for k in range(3)])
        if ca != cb:
            if sum(abs(x - y) for x, y in zip(ca, cb)) != 1:
                audit.issue("CROSSING", "multiple/ambiguous borders between two reads")
            actual.append((ca, cb))
    if actual != expected:
        audit.issue("CROSSING", "ordered translated border occurrences do not match read transitions")
    declared = audit.test.get("crossings")
    if declared is not None:
        if not isinstance(declared, list) or any(not isinstance(c, dict) for c in declared):
            audit.issue("CROSSING_PLAN", "malformed declared crossings")
        else:
            pairs = [(c.get("from"), c.get("to")) for c in declared]
            if pairs != [(list(a), list(b)) for a, b in _borders(poly)]:
                audit.issue("CROSSING_PLAN", "declared occurrence inventory disagrees with route geometry")
    _bridge(audit, ground, poly, local_reads)


def _facing(audit, observed, expected, label):
    want = audit.number(expected, 0, 360, label + ".expected_heading")
    if observed is None or want is None:
        audit.issue("FACING", "actual/expected arrival facing absent", label)
    elif abs((observed - want + 180) % 360 - 180) > 20:
        audit.issue("FACING", "arrival facing differs by more than 20 degrees", label, True)


def _inspect_door(audit):
    audit.report["check_scopes"]["ground"] = (
        "door route XYZ and recorded experiment pins only; full terrain/contact validation out of scope")
    audit.pins()
    if any(k in audit.test for k in ("ground", "ground_path", "ground_sha256")):
        _ground(audit)  # never silently ignore an explicitly planned ground identity
    offset, origin, origin_t = audit.anchor()
    legs = audit.obs.get("legs")
    outside, inside = audit.test.get("outside"), audit.test.get("inside")
    if offset is None or not isinstance(outside, dict) or not isinstance(inside, dict) \
            or not isinstance(legs, list) or len(legs) != 2 \
            or any(not isinstance(x, dict) for x in legs) \
            or [x.get("name") for x in legs] != ["in", "out"]:
        audit.issue("DOOR_SCHEMA", "need outside/inside and ordered in/out legs")
        return
    previous_arrival, previous_t, out_heading = origin, origin_t, None
    radius = audit.number(audit.test.get("radius", 4), 0.5, 50, "radius")
    if radius is None:
        return
    for leg, side, destination, exterior in ((legs[0], outside, inside, True),
                                              (legs[1], inside, outside, False)):
        label = leg["name"]
        route = _poly(side.get("route"), audit, label + ".route")
        shift = offset if exterior else [0, 0, 0]
        if leg.get("trigger") == "near":
            audit.issue("NEARONLY", "last-try teleport cannot establish continuous door travel", label)
        elif leg.get("trigger") not in ("walk", "e"):
            audit.issue("DOOR_TRIGGER", "retained walk/activation trigger required", label)
        if leg.get("mode") != "route":
            audit.issue("ROUTE_MODE", "continuous evidence requires the planned route mode", label)
        if type(leg.get("teleports")) is not int or leg["teleports"] != 0:
            audit.issue("TELEPORT", "route must explicitly record zero teleports", label,
                        leg.get("trigger") != "near" and type(leg.get("teleports")) is int)
        start, t, _ = audit.read(leg, label + ".start", "start_read")
        if start is None or previous_arrival is None or math.dist(start, previous_arrival) > 3 \
                or t is None or previous_t is None or not 0 <= t - previous_t <= 120:
            audit.issue("START_CONTINUITY", "door route start is not connected to prior settled arrival", label)
        steps = leg.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= 400 \
                or any(not isinstance(s, dict) for s in steps):
            audit.issue("DOOR_STEPS", "nonempty readable continuous steps required", label)
            steps = []
        reads, previous, total = [start], (start, t), 0
        for n, step in enumerate(steps):
            slabel = f"{label}.step.{n}"
            if type(step.get("n")) is not int or step["n"] != n:
                audit.issue("LEG_SEQUENCE", "step n must be contiguous from zero", slabel)
            p, u, _ = audit.read(step, slabel)
            ms = audit.number(step.get("ms"), 100, 10000, slabel + ".ms")
            audit.motion(previous, (p, u), ms, slabel)
            audit.hud(step, slabel)
            if step.get("state") != "here":
                audit.issue("DOOR_STEPS", "pre-load step must retain a readable position on this side", slabel)
            if ms is not None:
                total += ms
            previous = p, u
            reads.append(p)
        if total > 600000 or not audit.h.finite(leg.get("walked_ms")) or leg["walked_ms"] != total:
            audit.issue("TIME", "walked_ms does not equal bounded recorded holds", label)
        if route:
            merged = [[p[k] + shift[k] for k in range(3)] for p in route]
            if leg.get("route") != merged:
                audit.issue("ROUTE_MODE", "recorded route differs from expected coordinate frame", label, True)
            _route(audit, merged, reads, label, 3, 3)
            door = audit.vec(side.get("door"), label + ".door")
            if door and (reads[-1] is None or math.dist(reads[-1], [door[k] + shift[k] for k in range(3)]) > 3):
                audit.issue("DOOR_REACH", "no retained pre-load XYZ read within activation range", label)
        arrival_owner = {"read": leg.get("arrival_read"), "reads": leg.get("arrival_reads")}
        arrival, arrival_t, head = audit.settled(arrival_owner, label + ".arrival", heading=True,
                                               after=previous[1])
        if previous[1] is None or arrival_t is None or arrival_t <= previous[1]:
            audit.issue("TIME", "arrival chronology does not follow readable route steps", label)
        target = audit.vec(destination.get("arrival"), label + ".arrival_target")
        target_shift = [0, 0, 0] if exterior else offset
        if arrival and target and math.dist(arrival, [target[k] + target_shift[k] for k in range(3)]) > radius:
            audit.issue("ARRIVAL", "XYZ arrival differs from expected interior/merged exterior", label, True)
        if leg.get("arrival_settled") is not True:
            audit.issue("SETTLED", "producer did not record settled arrival", label)
        if not audit.h.finite(leg.get("arrival_heading")) or head is None \
                or abs((leg["arrival_heading"] - head + 180) % 360 - 180) > 0.011:
            audit.issue("FACING", "arrival heading summary differs from final settled heading", label)
        _facing(audit, head, destination.get("arrival_heading"), label)
        previous_arrival, previous_t, out_heading = arrival, arrival_t, head
    reload = audit.obs.get("reload")
    if not isinstance(reload, dict):
        audit.issue("RELOAD", "reload evidence absent")
        return
    away, away_t, _ = audit.read(reload, "reload.away", "away_read")
    if away_t is None or previous_t is None or away_t <= previous_t:
        audit.issue("TIME", "movement away must follow the settled out-arrival")
    if away is None or previous_arrival is None or math.dist(away, previous_arrival) <= 5:
        audit.issue("RELOAD", "no independently read movement away from saved XYZ")
    restored, restored_t, head = audit.settled(reload, "reload", heading=True, after=away_t)
    if restored is None or previous_arrival is None:
        audit.issue("RELOAD", "reload did not restore saved XYZ")
    elif math.dist(restored, previous_arrival) > radius:
        audit.issue("RELOAD", "retained reload XYZ differs from saved position", mismatch=True)
    if away_t is None or restored_t is None or restored_t <= away_t:
        audit.issue("TIME", "reload chronology absent/inconsistent")
    _facing(audit, head, out_heading, "reload")
    if not audit.h.finite(reload.get("heading")) or head is None \
            or abs((reload["heading"] - head + 180) % 360 - 180) > 0.011:
        audit.issue("FACING", "reload heading summary differs from final settled heading")
    if reload.get("settled") is not True:
        audit.issue("SETTLED", "reload settling not recorded")
    save = audit.obs.get("save")
    if not isinstance(save, dict) or save.get("found") is not True \
            or save.get("name") != audit.test.get("save"):
        audit.issue("SAVE", "named save record missing; save-file contents remain out of scope")
    planned = audit.test.get("probes", [])
    observed = audit.obs.get("probe_reads", [])
    if not isinstance(planned, list) or not isinstance(observed, list) or len(planned) != len(observed):
        audit.issue("MERGE_PROBE", "planned diagnostic probes not retained")
    else:
        for n, (plan, event) in enumerate(zip(planned, observed)):
            label = f"merge_probe.{n}"
            if not isinstance(plan, dict) or not isinstance(event, dict) or plan.get("ref") != event.get("ref"):
                audit.issue("MERGE_PROBE", "diagnostic reference identity mismatch", label)
                continue
            p, _, _ = audit.read(event, label, diagnostic=True)
            local = audit.vec(plan.get("local"), label + ".local")
            if p and local:
                row = audit.report["rows"][-1]
                row.update(diagnostic=True, local_residual_m=math.dist(p, local),
                           merged_residual_m=math.dist(p, [local[k] + offset[k] for k in range(3)]))


def _inspect(test, obs, folder, kind):
    audit = _Audit(test, obs, folder, kind)
    try:
        (_inspect_walk if kind == "walk" else _inspect_door)(audit)
    except (OSError, ValueError, TypeError, KeyError, OverflowError, UnicodeError) as error:
        audit.issue("SCHEMA", str(error))
    return audit.finish()


def inspect_walk(test: dict, obs: dict, folder: Path) -> dict:
    """Audit a completed walk record without invoking the controller or its judge."""
    return _inspect(test, obs, folder, "walk")


def inspect_door_trip(test: dict, obs: dict, folder: Path) -> dict:
    """Audit routed in/out/reload evidence; sparse legacy records remain inconclusive."""
    return _inspect(test, obs, folder, "door_trip")
