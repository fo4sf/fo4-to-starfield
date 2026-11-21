"""Source-level and translated-execution bridge contract for FO4SF_LoadDoor.psc.

Native Papyrus compilation and in-game runtime acceptance are separate. These
controls pin the R10 arrival-failure contract (1 initial MoveTo + MoveRetries = 2
for 3 total tries, no SetPosition on failed arrival, return player to Self with
one log line), opt-in coordinate handling, refusal ordering, Papyrus compiler
hygiene, and negative fixtures proving the old main behaviour fails the contract.
"""
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/door_bridge/FO4SF_LoadDoor.psc"
sys.path.insert(0, str(ROOT / "scripts/game"))
import bridge_log  # noqa: E402


# Verbatim pre-J1 main (713ed97a) source used as a negative fixture:
# pins MoveRetries = 1, calls SetPosition even on failed arrival, and neither
# returns the player to Self nor logs `load door arrival failed n=<k> door=<id>`.
OLD_MAIN_SOURCE = """\
Scriptname FO4SF_LoadDoor extends ObjectReference
{Experimental player-only travel. Properties use a plugin-local full-plugin ID,
 never a runtime load-order prefix. Record attachment and native acceptance required.}

string Property DestinationPlugin Auto
int Property DestinationId Auto
; Explicit opt-in: zero is a valid world coordinate, not an unset sentinel.
bool Property UseDestinationPosition = False Auto
float Property DestinationX Auto
float Property DestinationY Auto
float Property DestinationZ Auto
; A missed trip (the player still in the cell they activated from, with the engine's
; "BOUNDARY REACHED"; docs/terrain/border.md) is retried with the same MoveTo this many times, each after
; RetryWaitSeconds. 0 turns retries off.
int Property MoveRetries = 1 Auto
float Property RetryWaitSeconds = 0.5 Auto
; With UseDestinationPosition, the wait between the MoveTo and the SetPosition. The BOUNDARY REACHED popup pauses
; Papyrus, so whether the trace stops before or after phase=settled tells which step raised it (docs/terrain/border.md).
float Property SettleSeconds = 1.0 Auto
bool Moving = False

Event OnLoad()
    Moving = False
EndEvent

Event OnActivate(ObjectReference akActionRef)
    if akActionRef != Game.GetPlayer() || Moving
        return
    endif
    if DestinationPlugin == "" || DestinationId <= 0 || DestinationId > 0x00FFFFFF
        Debug.Trace("FO4SF_LoadDoor refused: invalid destination properties")
        return
    endif
    ObjectReference destination = Game.GetFormFromFile(DestinationId, DestinationPlugin) as ObjectReference
    if destination == None || destination == Self
        Debug.Trace("FO4SF_LoadDoor refused: destination unavailable or self")
        return
    endif
    Moving = True
    Debug.Trace("FO4SF_LoadDoor requested " + DestinationPlugin + ":" + DestinationId)
    TracePosition("marker", destination)
    TracePosition("before_move", akActionRef)
    Cell origin = akActionRef.GetParentCell()
    akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)
    Debug.Trace("FO4SF_LoadDoor MoveTo returned")
    TracePosition("after_move", akActionRef)
    int retries = 0
    while retries < MoveRetries && !Arrived(akActionRef, destination, origin)
        Utility.Wait(RetryWaitSeconds)
        if !Arrived(akActionRef, destination, origin)
            retries += 1
            Debug.Trace("FO4SF_LoadDoor retry " + retries + " of " + MoveRetries)
            akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)
            TracePosition("after_retry", akActionRef)
        endif
    endwhile
    if retries > 0 && !Arrived(akActionRef, destination, origin)
        Debug.Trace("FO4SF_LoadDoor retry gave up after " + retries)
    endif
    if UseDestinationPosition
        string requestedPosition = "FO4SF_LoadDoor requested_position=" + DestinationX + " " + DestinationY + " " + DestinationZ
        Debug.Trace(requestedPosition)
        Debug.TraceUser("fo4sf", requestedPosition)
        Utility.Wait(SettleSeconds)
        TracePosition("settled", akActionRef)
        akActionRef.SetPosition(DestinationX, DestinationY, DestinationZ)
        TracePosition("after_position", akActionRef)
    endif
    Moving = False
EndEvent

bool Function Arrived(ObjectReference target, ObjectReference destination, Cell origin)
    return destination.GetParentCell() == origin || target.GetParentCell() != origin
EndFunction

Function TracePosition(string phase, ObjectReference target)
    string line = "FO4SF_LoadDoor phase=" + phase + " destination=" + DestinationPlugin + ":" + DestinationId
    line += " ref=" + target.GetFormID() + " pos=" + target.GetPositionX() + " " + target.GetPositionY() + " " + target.GetPositionZ()
    line += " angle=" + target.GetAngleZ() + " cell=" + target.GetParentCell() + " world=" + target.GetWorldSpace()
    Debug.Trace(line)
    Debug.TraceUser("fo4sf", line)
EndFunction
"""


def strip_comments(source: str) -> str:
    return re.sub(r";[^\n]*", "", source)


def on_activate_body(code: str) -> str:
    return code.split("Event OnActivate(", 1)[1].split("EndEvent", 1)[0]


def contract_violations(source: str) -> dict[str, str]:
    """Return {violation_key: reason} for any J1/R10 contract violation."""
    violations: dict[str, str] = {}
    code = strip_comments(source)
    activate = on_activate_body(code)

    if "int Property MoveRetries = 2 Auto" not in code:
        violations["move_retries"] = "MoveRetries default must be 2 (1 initial MoveTo + 2 retries = 3 total tries)"

    after_loop = activate.split("endwhile", 1)[1]
    if "if UseDestinationPosition" not in after_loop:
        violations["use_destination_position"] = "missing UseDestinationPosition block after retry loop"
        return violations

    between_loop_and_pos = after_loop.split("if UseDestinationPosition", 1)[0]
    fail_block = re.search(
        r"if\s+(!didArrive|!Arrived\(akActionRef,\s*destination,\s*origin\))\s+(.*?)\s+endif",
        between_loop_and_pos,
        re.S,
    )
    if fail_block is None:
        violations["failed_arrival_gate"] = (
            "failed arrival must be checked and return before UseDestinationPosition / SetPosition"
        )
        fail_body = ""
    else:
        fail_body = fail_block.group(2)
        if not re.search(r"\breturn\b", fail_body):
            violations["failed_arrival_return"] = "failed-arrival branch must return before SetPosition"
        if "Moving = False" not in fail_body:
            violations["failed_arrival_unlock"] = "failed-arrival branch must clear Moving = False before returning"
        if ".SetPosition(" in fail_body:
            violations["set_position_on_fail"] = "failed-arrival branch must never call SetPosition"

    if "akActionRef.MoveTo(Self, 0.0, 0.0, 0.0, True, False)" not in fail_body:
        violations["return_to_self"] = "failed-arrival branch must MoveTo(Self, ...) to return player to door"

    has_fail_msg = (
        '"FO4SF_LoadDoor load door arrival failed n="' in fail_body
        and '" door="' in fail_body
        and "Self.GetFormID()" in fail_body
    )
    if not has_fail_msg:
        violations["failed_arrival_log"] = (
            "failed-arrival branch must log `load door arrival failed n=<k> door=<id>` with Self.GetFormID()"
        )
    else:
        if "Debug.Trace(" not in fail_body or 'Debug.TraceUser("fo4sf",' not in fail_body:
            violations["failed_arrival_log_channels"] = (
                "failed-arrival log must reach both Debug.Trace and Debug.TraceUser(\"fo4sf\", ...)"
            )

    guarded = re.search(r"if UseDestinationPosition\s+(.*?)\s+endif", after_loop, re.S)
    if guarded is None or "akActionRef.SetPosition(DestinationX, DestinationY, DestinationZ)" not in guarded.group(1):
        violations["set_position_guarded"] = "SetPosition must remain inside UseDestinationPosition"
    elif re.search(r"\bif\b", guarded.group(1)):
        violations["coordinate_truthiness_guard"] = (
            "UseDestinationPosition must not add an inner coordinate-truthiness guard rejecting 0"
        )

    return violations


class _FakeCell:
    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return self.name


class _FakeRef:
    def __init__(self, form_id: int, cell: _FakeCell, pos=(0.0, 0.0, 0.0), angle=0.0, world="TestWorld"):
        self.form_id = form_id
        self.cell = cell
        self.pos = list(pos)
        self.angle = angle
        self.world = world
        self.move_calls: list[tuple[object, float, float, float, bool, bool]] = []
        self.setpos_calls: list[tuple[float, float, float]] = []
        self._on_move = None

    def GetFormID(self) -> int:
        return self.form_id

    def GetParentCell(self) -> _FakeCell:
        return self.cell

    def GetPositionX(self) -> float:
        return self.pos[0]

    def GetPositionY(self) -> float:
        return self.pos[1]

    def GetPositionZ(self) -> float:
        return self.pos[2]

    def GetAngleZ(self) -> float:
        return self.angle

    def GetWorldSpace(self) -> str:
        return self.world

    def MoveTo(self, target, x, y, z, match_rot, rot_offset):
        self.move_calls.append((target, x, y, z, match_rot, rot_offset))
        if self._on_move is not None:
            self._on_move(self, target)

    def SetPosition(self, x, y, z):
        self.setpos_calls.append((x, y, z))
        self.pos = [x, y, z]


def _rewrite_papyrus_string_concat(expr: str) -> str:
    """Rewrite Papyrus string `+` concatenations (including inside call args) with `_pstr(...)`."""
    # First recursively rewrite any parenthesized sub-expressions / argument lists.
    out, i, n = [], 0, len(expr)
    while i < n:
        if expr[i] == "(":
            depth, j = 1, i + 1
            while j < n and depth > 0:
                if expr[j] == "(":
                    depth += 1
                elif expr[j] == ")":
                    depth -= 1
                j += 1
            inner = expr[i + 1 : j - 1]
            # Split top-level comma-separated args inside (...) and rewrite each.
            args, buf, d = [], [], 0
            for ch in inner:
                if ch == "(":
                    d += 1
                elif ch == ")":
                    d -= 1
                if ch == "," and d == 0:
                    args.append("".join(buf))
                    buf = []
                else:
                    buf.append(ch)
            args.append("".join(buf))
            rewritten_args = [_rewrite_papyrus_string_concat(a.strip()) if a.strip() else "" for a in args]
            out.append("(" + ", ".join(rewritten_args) + ")")
            i = j
        else:
            out.append(expr[i])
            i += 1
    s = "".join(out)
    if "__STR_" in s and "+" in s:
        parts = _split_plus(s)
        if len(parts) > 1:
            return " + ".join(f"_pstr({p.strip()})" for p in parts)
    return s


def _translate_papyrus_expr(expr: str, instance_fields: set[str], methods: set[str]) -> str:
    """Translate a Papyrus expression used in FO4SF_LoadDoor.psc into Python."""
    # Protect string literals while transforming operators and identifiers.
    literals: list[str] = []

    def _stash(match: re.Match) -> str:
        literals.append(match.group(0))
        return f"__STR_{len(literals) - 1}__"

    s = re.sub(r'"[^"\n]*"', _stash, expr.strip())
    s = re.sub(r"\s+as\s+[A-Za-z_]\w*", "", s)
    s = s.replace("&&", " and ").replace("||", " or ")
    s = re.sub(r"!(?!=)", "not ", s)
    s = re.sub(r"\bSelf\b", "self", s)
    # Prefix bare script properties/fields and script methods with self.
    for name in sorted(instance_fields | methods, key=len, reverse=True):
        s = re.sub(rf"(?<!\.)\b{re.escape(name)}\b", f"self.{name}", s)

    s = _rewrite_papyrus_string_concat(s)

    for idx, lit in enumerate(literals):
        s = s.replace(f"__STR_{idx}__", lit)
    return s


def _split_plus(expr: str) -> list[str]:
    parts, buf, depth = [], [], 0
    for ch in expr:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "+" and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


def build_translated_load_door(source: str):
    """Translate FO4SF_LoadDoor.psc into a runnable Python class."""
    code = strip_comments(source)
    code = re.sub(r"\{[^}]*\}", "", code)

    fields: dict[str, object] = {}
    for m in re.finditer(
        r"(?m)^\s*(string|int|float|bool)\s+Property\s+(\w+)(?:\s*=\s*([^\n]+?))?\s+Auto\b",
        code,
    ):
        kind, name, default = m.group(1), m.group(2), m.group(3)
        if default is None:
            fields[name] = {"string": "", "int": 0, "float": 0.0, "bool": False}[kind]
        else:
            fields[name] = eval(default.strip(), {"True": True, "False": False})
    for m in re.finditer(r"(?m)^\s*(bool|int|float|string)\s+(\w+)\s*=\s*([^\n]+)", code):
        # Top-level script variables only (before first Event/Function).
        if m.start() < code.index("Event "):
            fields[m.group(2)] = eval(m.group(3).strip(), {"True": True, "False": False})

    instance_fields = set(fields)
    methods = {"OnLoad", "OnActivate", "Arrived", "TracePosition"}

    def translate_block(header_re: str, end_kw: str, py_name: str, params: list[str]) -> str:
        m = re.search(header_re + r"(.*?)" + end_kw, code, re.S)
        assert m is not None, f"missing {py_name}"
        raw_lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
        out = [f"    def {py_name}(self{''.join(', ' + p for p in params)}):"]
        indent = 2
        for ln in raw_lines:
            low = ln.lower()
            if low in ("endif", "endwhile"):
                indent -= 1
                continue
            pad = "    " * indent
            if low.startswith("if "):
                cond = _translate_papyrus_expr(ln[3:], instance_fields, methods)
                out.append(f"{pad}if {cond}:")
                indent += 1
            elif low.startswith("while "):
                cond = _translate_papyrus_expr(ln[6:], instance_fields, methods)
                out.append(f"{pad}while {cond}:")
                indent += 1
            elif low == "return":
                out.append(f"{pad}return")
            elif low.startswith("return "):
                val = _translate_papyrus_expr(ln[7:], instance_fields, methods)
                out.append(f"{pad}return {val}")
            else:
                # Strip local type declaration (`int retries = 0`, `Cell origin = ...`).
                stmt = re.sub(r"^(?:string|int|float|bool|Cell|ObjectReference)\s+", "", ln)
                if "+=" in stmt:
                    lhs, rhs = stmt.split("+=", 1)
                    lhs_t = _translate_papyrus_expr(lhs, instance_fields, methods)
                    rhs_t = _translate_papyrus_expr(rhs, instance_fields, methods)
                    out.append(f"{pad}{lhs_t} = _pstr({lhs_t}) + _pstr({rhs_t})" if '"' in rhs else f"{pad}{lhs_t} += {rhs_t}")
                elif "=" in stmt and not re.search(r"==|!=|<=|>=", stmt.split("=", 1)[0] + "="):
                    lhs, rhs = stmt.split("=", 1)
                    lhs_t = _translate_papyrus_expr(lhs, instance_fields, methods)
                    rhs_t = _translate_papyrus_expr(rhs, instance_fields, methods)
                    out.append(f"{pad}{lhs_t} = {rhs_t}")
                else:
                    out.append(f"{pad}{_translate_papyrus_expr(stmt, instance_fields, methods)}")
        return "\n".join(out)

    py_src = "\n\n".join([
        "class TranslatedLoadDoor(_FakeRef):",
        "    def __init__(self, form_id, cell, Game, Debug, Utility):",
        "        super().__init__(form_id, cell)",
        "        self._Game = Game",
        "        self._Debug = Debug",
        "        self._Utility = Utility",
        *[f"        self.{k} = {v!r}" for k, v in fields.items()],
        translate_block(r"Event OnLoad\(\)\s*", "EndEvent", "OnLoad", []),
        translate_block(r"Event OnActivate\(ObjectReference akActionRef\)\s*", "EndEvent", "OnActivate", ["akActionRef"]),
        translate_block(
            r"bool Function Arrived\(ObjectReference target, ObjectReference destination, Cell origin\)\s*",
            "EndFunction",
            "Arrived",
            ["target", "destination", "origin"],
        ),
        translate_block(
            r"Function TracePosition\(string phase, ObjectReference target\)\s*",
            "EndFunction",
            "TracePosition",
            ["phase", "target"],
        ),
    ])

    def _pstr(val) -> str:
        if isinstance(val, bool):
            return "True" if val else "False"
        return str(val)

    ns: dict[str, object] = {"_FakeRef": _FakeRef, "_pstr": _pstr}

    def instantiate(door_id: int, origin_cell: _FakeCell, game, debug, utility):
        ns.update({"Game": game, "Debug": debug, "Utility": utility})
        exec(py_src, ns)
        return ns["TranslatedLoadDoor"](door_id, origin_cell, game, debug, utility)

    return instantiate


class _FakeEnv:
    def __init__(self, player: _FakeRef, form_map: dict[tuple[str, int], object], on_wait=None):
        self.player = player
        self.form_map = form_map
        self.traces: list[str] = []
        self.user_traces: list[tuple[str, str]] = []
        self.waits: list[float] = []
        self._on_wait = on_wait

    def GetPlayer(self):
        return self.player

    def GetFormFromFile(self, form_id: int, plugin: str):
        return self.form_map.get((plugin, form_id))

    def Trace(self, text: str):
        self.traces.append(text)

    def TraceUser(self, log_name: str, text: str):
        self.user_traces.append((log_name, text))

    def Wait(self, seconds: float):
        self.waits.append(seconds)
        if self._on_wait is not None:
            self._on_wait(len(self.waits), seconds)


class ArrivalContractTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text(encoding="utf-8")
        self.code = strip_comments(self.source)
        self.activate = on_activate_body(self.code)

    def test_existing_doors_default_to_no_position_override(self):
        self.assertIn("bool Property UseDestinationPosition = False Auto", self.code)
        for axis in "XYZ":
            self.assertIn(f"float Property Destination{axis} Auto", self.code)
        guarded = re.search(r"if UseDestinationPosition\s+(.*?)\s+endif", self.activate, re.S)
        self.assertIsNotNone(guarded)
        self.assertIn("akActionRef.SetPosition(DestinationX, DestinationY, DestinationZ)", guarded[1])
        self.assertEqual(self.activate.count(".SetPosition("), 1)
        self.assertEqual(self.code.count(".SetPosition("), 1)
        # In particular there is no coordinate-truthiness condition rejecting 0;
        # failed arrivals are rejected before entering UseDestinationPosition.
        self.assertNotRegex(guarded[1], r"\bif\b")
        self.assertEqual(contract_violations(self.source), {})

    def test_refusals_precede_both_native_movement_calls(self):
        before = self.activate.split("Moving = True", 1)[0]
        for guard in (
            "akActionRef != Game.GetPlayer() || Moving",
            'DestinationPlugin == "" || DestinationId <= 0 || DestinationId > 0x00FFFFFF',
            "destination == None || destination == Self",
        ):
            self.assertIn(guard, before)
        self.assertEqual(before.count("return"), 3)
        self.assertNotIn(".MoveTo(", before)
        self.assertNotIn(".SetPosition(", before)

    def test_traces_bracket_move_then_arrival_check_then_optional_position_and_release(self):
        steps = [
            "Moving = True",
            'TracePosition("marker", destination)',
            'TracePosition("before_move", akActionRef)',
            "akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)",
            'TracePosition("after_move", akActionRef)',
            "while retries < MoveRetries && !Arrived(akActionRef, destination, origin)",
            'TracePosition("after_retry", akActionRef)',
            "bool didArrive = Arrived(akActionRef, destination, origin)",
            "if !didArrive",
            "akActionRef.MoveTo(Self, 0.0, 0.0, 0.0, True, False)",
            '"FO4SF_LoadDoor load door arrival failed n="',
            "if UseDestinationPosition",
            "Utility.Wait(SettleSeconds)",
            'TracePosition("settled", akActionRef)',
            "akActionRef.SetPosition(DestinationX, DestinationY, DestinationZ)",
            'TracePosition("after_position", akActionRef)',
        ]
        indices = [self.activate.index(step) for step in steps]
        self.assertEqual(indices, sorted(indices))
        self.assertGreater(self.activate.rindex("Moving = False"), indices[-1])
        self.assertNotIn(".SetAngle(", self.code)
        load = self.code.split("Event OnLoad()", 1)[1].split("EndEvent", 1)[0]
        self.assertEqual(load.strip(), "Moving = False")

    def test_a_missed_trip_is_retried_for_three_total_tries_then_returns_to_self_without_set_position(self):
        self.assertIn("int Property MoveRetries = 2 Auto", self.code)
        self.assertIn("float Property RetryWaitSeconds = 0.5 Auto", self.code)
        loop = re.search(r"while (.*?)\n(.*?)endwhile", self.activate, re.S)
        self.assertIsNotNone(loop)
        self.assertEqual(loop[1].strip(), "retries < MoveRetries && !Arrived(akActionRef, destination, origin)")
        body = loop[2]
        # wait, look again, and only then count and repeat the same MoveTo
        steps = [
            "Utility.Wait(RetryWaitSeconds)",
            "if !Arrived(akActionRef, destination, origin)",
            "retries += 1",
            "akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)",
        ]
        indices = [body.index(step) for step in steps]
        self.assertEqual(indices, sorted(indices))
        # 2 destination MoveTo calls (initial + retry) plus 1 fallback MoveTo(Self)
        self.assertEqual(self.activate.count("akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)"), 2)
        self.assertEqual(self.activate.count("akActionRef.MoveTo(Self, 0.0, 0.0, 0.0, True, False)"), 1)
        self.assertEqual(self.activate.count(".MoveTo("), 3)
        arrived = self.code.split("bool Function Arrived(", 1)[1].split("EndFunction", 1)[0]
        # by this door's cell, never by world (the player's may be the runtime instance)
        self.assertNotIn("GetWorldSpace", arrived)
        # against the player's cell taken before the first MoveTo, not the door's
        self.assertIn("return destination.GetParentCell() == origin || target.GetParentCell() != origin", arrived)
        before = self.activate.split(".MoveTo(", 1)[0]
        self.assertIn("Cell origin = akActionRef.GetParentCell()", before)
        after_loop = self.activate.split("endwhile", 1)[1]
        self.assertIn('"FO4SF_LoadDoor load door arrival failed n="', after_loop)
        self.assertNotIn("retry gave up", after_loop)

    def test_the_position_step_waits_and_traces_after_the_move(self):
        self.assertIn("float Property SettleSeconds = 1.0 Auto", self.code)
        guarded = re.search(r"if UseDestinationPosition\s+(.*?)\s+endif", self.activate, re.S)[1]
        before_position = guarded.split("akActionRef.SetPosition(", 1)[0]
        self.assertEqual(before_position.count("Utility.Wait(SettleSeconds)"), 1)
        self.assertEqual(before_position.count('TracePosition("settled", akActionRef)'), 1)

    def test_the_destination_marker_is_never_moved(self):
        # bridge t6 (#512) set the marker's position before the MoveTo; on the PC (28 Oct 2026, 20 Vault 95 exits) the
        # MoveTo then left the player in the interior every time, so the only SetPosition is the player's, after the move
        self.assertNotIn("PlaceDestination", self.code)
        self.assertNotIn("destination.SetPosition(", self.code)
        self.assertNotIn("marker_placed", self.code)
        self.assertEqual(self.code.count(".SetPosition("), 1)
        self.assertIn("akActionRef.SetPosition(DestinationX, DestinationY, DestinationZ)", self.activate)
        self.assertLess(self.activate.index(".MoveTo("), self.activate.index("akActionRef.SetPosition("))

    def test_logs_identify_reference_frame_and_do_not_assert_success(self):
        trace = self.code.split("Function TracePosition(", 1)[1]
        for field in (
            "GetFormID()",
            "GetPositionX()",
            "GetPositionY()",
            "GetPositionZ()",
            "GetAngleZ()",
            "GetParentCell()",
            "GetWorldSpace()",
        ):
            self.assertIn("target." + field, trace)
        self.assertIn('Debug.TraceUser("fo4sf", line)', trace)
        self.assertIn("DestinationPlugin", trace)
        self.assertIn("DestinationId", trace)
        self.assertNotRegex(self.code, r'"[^"\n]*(?:PASS|success)[^"\n]*"')

    def test_requested_coordinates_do_not_depend_on_an_open_user_log(self):
        guarded = re.search(r"if UseDestinationPosition\s+(.*?)\s+endif", self.activate, re.S)[1]
        before_position = guarded.split("akActionRef.SetPosition(", 1)[0]
        strings = dict(re.findall(r"string (\w+) = ([^\n]+)", before_position))

        def requests(pattern):
            arguments = re.findall(pattern, before_position)
            expressions = [strings.get(arg.strip(), arg.strip()) for arg in arguments]
            return [expr for expr in expressions if '"FO4SF_LoadDoor requested_position="' in expr]

        normal = requests(r"Debug.Trace\(([^\n]+)\)")
        user = requests(r'Debug.TraceUser\("fo4sf", ([^\n]+)\)')
        self.assertEqual(len(normal), 1, "requested coordinates must reach the normal log without the bridge quest")
        self.assertEqual(normal, user)
        for axis in "XYZ":
            self.assertIn("Destination" + axis, normal[0])

    def test_papyrus_compiler_hygiene(self):
        # No "Version" token after line 18 (Starfield Papyrus reserved-header rule).
        tail = "\n".join(self.source.splitlines()[18:])
        self.assertNotRegex(tail, r"\bVersion\b", "Papyrus source must not use Version after line 18")
        # No local variable or parameter matches a property or script variable case-insensitively.
        props = {
            m.group(1).lower()
            for m in re.finditer(r"(?m)^\s*\w+\s+Property\s+(\w+)\b", self.code)
        }
        props.add("moving")
        locals_declared = {
            m.group(1).lower()
            for m in re.finditer(
                r"(?m)^\s+(?:string|int|float|bool|Cell|ObjectReference)\s+(\w+)\s*=",
                self.code,
            )
        }
        self.assertEqual(props & locals_declared, set())

    def test_old_main_behaviour_fails_contract_as_negative_fixture(self):
        """Pin the pre-J1 main script as a negative fixture so every defect is caught."""
        violations = contract_violations(OLD_MAIN_SOURCE)
        self.assertIn("move_retries", violations)
        self.assertIn("failed_arrival_gate", violations)
        self.assertIn("return_to_self", violations)
        self.assertIn("failed_arrival_log", violations)

    def test_single_defect_mutations_are_each_caught(self):
        mutations = {
            "move_retries": self.source.replace(
                "int Property MoveRetries = 2 Auto",
                "int Property MoveRetries = 1 Auto",
            ),
            "failed_arrival_return": self.source.replace(
                "Moving = False\n        return",
                "Moving = False",
            ),
            "failed_arrival_unlock": self.source.replace(
                "Moving = False\n        return",
                "return",
            ),
            "return_to_self": self.source.replace(
                "akActionRef.MoveTo(Self, 0.0, 0.0, 0.0, True, False)\n",
                "",
            ),
            "failed_arrival_log": self.source.replace(
                'string failedLine = "FO4SF_LoadDoor load door arrival failed n=" + attempts + " door=" + Self.GetFormID()',
                'string failedLine = "FO4SF_LoadDoor retry gave up after " + retries',
            ),
        }
        for expected_key, mutated in mutations.items():
            self.assertNotEqual(mutated, self.source, f"mutation {expected_key} did not alter source")
            violations = contract_violations(mutated)
            self.assertIn(expected_key, violations, f"expected {expected_key} violation, got {violations}")


class TranslatedExecutionTests(unittest.TestCase):
    """Execute translated FO4SF_LoadDoor.psc (and the old main negative fixture)."""

    def _setup_door(self, source: str, *, move_behavior, use_dest_pos=True, dest_xyz=(-1669.4, -2063.9, 42.4),
                    move_retries=None, on_wait=None, same_cell=False):
        origin = _FakeCell("FO4Port_Vault95")
        dest_cell = origin if same_cell else _FakeCell("FO4Core_Commonwealth")
        player = _FakeRef(0x14, origin, pos=(1.0, 2.0, 3.0))
        dest_marker = _FakeRef(0x0A7749, dest_cell, pos=(10.0, 20.0, 30.0))
        player._on_move = lambda ref, target: move_behavior(ref, target, origin, dest_cell)

        env = _FakeEnv(player, {("FO4TerrainCore.esm", 0x0A7749): dest_marker}, on_wait=on_wait)
        door = build_translated_load_door(source)(0x041DC1, origin, env, env, env)
        door.DestinationPlugin = "FO4TerrainCore.esm"
        door.DestinationId = 0x0A7749
        door.UseDestinationPosition = use_dest_pos
        door.DestinationX, door.DestinationY, door.DestinationZ = dest_xyz
        if move_retries is not None:
            door.MoveRetries = move_retries
        return door, player, dest_marker, env

    def test_failed_arrival_makes_three_tries_skips_set_position_and_returns_to_self(self):
        # Every MoveTo to destination leaves the player in origin (simulating BOUNDARY REACHED).
        def fail_move(ref, target, origin, _dest_cell):
            if target is not None:
                ref.cell = origin

        source = SOURCE.read_text(encoding="utf-8")
        door, player, dest_marker, env = self._setup_door(source, move_behavior=fail_move, use_dest_pos=True)
        door.OnActivate(player)

        dest_moves = [c for c in player.move_calls if c[0] is dest_marker]
        self_moves = [c for c in player.move_calls if c[0] is door]
        self.assertEqual(len(dest_moves), 3, "1 initial MoveTo + 2 retries = 3 total destination tries")
        self.assertEqual(len(self_moves), 1, "failed arrival must return player to Self")
        self.assertEqual(player.setpos_calls, [], "SetPosition must NEVER run on failed arrival")
        self.assertFalse(door.Moving, "door must unlock Moving=False after failed arrival")

        expected_line = f"FO4SF_LoadDoor load door arrival failed n=3 door={door.GetFormID()}"
        fail_traces = [ln for ln in env.traces if "load door arrival failed" in ln]
        fail_user = [ln for log, ln in env.user_traces if log == "fo4sf" and "load door arrival failed" in ln]
        self.assertEqual(fail_traces, [expected_line])
        self.assertEqual(fail_user, [expected_line])
        self.assertEqual(bridge_log.parse_event(expected_line), {"kind": "loaddoor", "phase": None})
        self.assertFalse(any("requested_position=" in ln for ln in env.traces))
        self.assertFalse(any("phase=settled" in ln for ln in env.traces))

        # Door is not stranded locked: a second activation works if travel succeeds next time.
        player._on_move = lambda ref, target: setattr(ref, "cell", dest_marker.GetParentCell())
        door.OnActivate(player)
        self.assertEqual(len(player.setpos_calls), 1)
        self.assertFalse(door.Moving)

    def test_failed_arrival_with_zero_retries_skips_set_position_and_logs_n_1(self):
        def fail_move(ref, _target, origin, _dest_cell):
            ref.cell = origin

        source = SOURCE.read_text(encoding="utf-8")
        door, player, dest_marker, env = self._setup_door(
            source, move_behavior=fail_move, use_dest_pos=True, move_retries=0
        )
        door.OnActivate(player)

        self.assertEqual(len([c for c in player.move_calls if c[0] is dest_marker]), 1)
        self.assertEqual(len([c for c in player.move_calls if c[0] is door]), 1)
        self.assertEqual(player.setpos_calls, [])
        self.assertEqual(env.waits, [])
        expected = f"FO4SF_LoadDoor load door arrival failed n=1 door={door.GetFormID()}"
        self.assertEqual([ln for ln in env.traces if "load door arrival failed" in ln], [expected])
        self.assertFalse(door.Moving)

    def test_arrival_on_second_retry_applies_set_position_and_never_returns_to_self(self):
        calls = {"n": 0}

        def succeed_on_third_move(ref, target, origin, dest_cell):
            calls["n"] += 1
            ref.cell = dest_cell if calls["n"] >= 3 else origin

        source = SOURCE.read_text(encoding="utf-8")
        door, player, dest_marker, env = self._setup_door(
            source, move_behavior=succeed_on_third_move, use_dest_pos=True, dest_xyz=(0.0, 0.0, 0.0)
        )
        door.OnActivate(player)

        self.assertEqual(len([c for c in player.move_calls if c[0] is dest_marker]), 3)
        self.assertEqual([c for c in player.move_calls if c[0] is door], [])
        self.assertEqual(player.setpos_calls, [(0.0, 0.0, 0.0)])
        self.assertFalse(any("load door arrival failed" in ln for ln in env.traces))
        self.assertFalse(door.Moving)

    def test_arrival_settling_after_second_retry_wait_counts_as_arrived(self):
        state = {"ref": None, "dest_cell": None}

        def fail_moves(ref, _target, origin, dest_cell):
            state["ref"] = ref
            state["dest_cell"] = dest_cell
            ref.cell = origin

        def settle_on_third_wait(wait_index, _seconds):
            if wait_index == 3:
                state["ref"].cell = state["dest_cell"]

        source = SOURCE.read_text(encoding="utf-8")
        door, player, dest_marker, env = self._setup_door(
            source, move_behavior=fail_moves, use_dest_pos=True, on_wait=settle_on_third_wait
        )
        door.OnActivate(player)

        self.assertEqual(len([c for c in player.move_calls if c[0] is dest_marker]), 3)
        self.assertEqual([c for c in player.move_calls if c[0] is door], [])
        self.assertEqual(len(player.setpos_calls), 1)
        self.assertFalse(any("load door arrival failed" in ln for ln in env.traces))
        self.assertFalse(door.Moving)

    def test_immediate_arrival_without_position_override_skips_set_position(self):
        def arrive(ref, _target, _origin, dest_cell):
            ref.cell = dest_cell

        source = SOURCE.read_text(encoding="utf-8")
        door, player, dest_marker, env = self._setup_door(source, move_behavior=arrive, use_dest_pos=False)
        door.OnActivate(player)

        self.assertEqual(len([c for c in player.move_calls if c[0] is dest_marker]), 1)
        self.assertEqual(player.setpos_calls, [])
        self.assertFalse(any("load door arrival failed" in ln for ln in env.traces))
        self.assertFalse(door.Moving)

    def test_old_main_negative_fixture_exhibits_all_fixed_bugs_at_runtime(self):
        """Executing the old main script under failed arrival reproduces its defects."""
        def fail_move(ref, _target, origin, _dest_cell):
            ref.cell = origin

        door, player, dest_marker, env = self._setup_door(
            OLD_MAIN_SOURCE, move_behavior=fail_move, use_dest_pos=True
        )
        door.OnActivate(player)

        # Old main only retried once (2 attempts), still called SetPosition on failed arrival,
        # never moved the player back to Self, and never emitted the R10 failure line.
        self.assertEqual(len([c for c in player.move_calls if c[0] is dest_marker]), 2)
        self.assertEqual(len(player.setpos_calls), 1)
        self.assertEqual([c for c in player.move_calls if c[0] is door], [])
        self.assertFalse(any("load door arrival failed" in ln for ln in env.traces))


if __name__ == "__main__":
    unittest.main()
