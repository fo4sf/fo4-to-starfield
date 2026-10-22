"""Source-level bridge contract; native compilation/runtime checks are separate.

These controls protect opt-in, refusal ordering and observable call order, not
Papyrus execution or success of the engine's movement functions.
"""
from pathlib import Path
import re
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/door_bridge/FO4SF_LoadDoor.psc"


class ArrivalContractTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text(encoding="utf-8")
        self.code = re.sub(r";[^\n]*", "", self.source)
        self.activate = self.code.split("Event OnActivate(", 1)[1].split("EndEvent", 1)[0]

    def test_existing_doors_default_to_no_position_override(self):
        self.assertIn("bool Property UseDestinationPosition = False Auto", self.code)
        for axis in "XYZ":
            self.assertIn(f"float Property Destination{axis} Auto", self.code)
        guarded = re.search(r"if UseDestinationPosition\s+(.*?)\s+endif", self.activate, re.S)
        self.assertIsNotNone(guarded)
        self.assertIn("akActionRef.SetPosition(DestinationX, DestinationY, DestinationZ)", guarded[1])
        self.assertEqual(self.code.count(".SetPosition("), 1)
        # In particular there is no coordinate-truthiness condition rejecting 0.
        self.assertNotRegex(guarded[1], r"\bif\b")

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

    def test_traces_bracket_move_then_optional_position_and_release(self):
        steps = [
            "Moving = True",
            'TracePosition("marker", destination)',
            'TracePosition("before_move", akActionRef)',
            "akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)",
            'TracePosition("after_move", akActionRef)',
            "while retries < MoveRetries && !Arrived(akActionRef, destination)",
            'TracePosition("after_retry", akActionRef)',
            "if UseDestinationPosition",
            "akActionRef.SetPosition(DestinationX, DestinationY, DestinationZ)",
            'TracePosition("after_position", akActionRef)',
            "Moving = False",
        ]
        indices = [self.activate.index(step) for step in steps]
        self.assertEqual(indices, sorted(indices))
        self.assertNotIn(".SetAngle(", self.code)
        load = self.code.split("Event OnLoad()", 1)[1].split("EndEvent", 1)[0]
        self.assertEqual(load.strip(), "Moving = False")

    def test_a_missed_trip_is_retried_a_bounded_number_of_times(self):
        self.assertIn("int Property MoveRetries = 1 Auto", self.code)
        self.assertIn("float Property RetryWaitSeconds = 0.5 Auto", self.code)
        loop = re.search(r"while (.*?)\n(.*?)endwhile", self.activate, re.S)
        self.assertIsNotNone(loop)
        self.assertEqual(loop[1].strip(), "retries < MoveRetries && !Arrived(akActionRef, destination)")
        body = loop[2]
        # wait, look again, and only then count and repeat the same MoveTo
        steps = ["Utility.Wait(RetryWaitSeconds)", "if !Arrived(akActionRef, destination)", "retries += 1",
                 "akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)"]
        indices = [body.index(step) for step in steps]
        self.assertEqual(indices, sorted(indices))
        self.assertEqual(self.activate.count(".MoveTo("), 2)
        arrived = self.code.split("bool Function Arrived(", 1)[1].split("EndFunction", 1)[0]
        # by this door's cell, never by world (the player's may be the runtime instance)
        self.assertNotIn("GetWorldSpace", arrived)
        self.assertIn("Cell here = GetParentCell()", arrived)
        self.assertIn("return destination.GetParentCell() == here || target.GetParentCell() != here", arrived)
        self.assertIn('"FO4SF_LoadDoor retry gave up after "', self.activate.split("endwhile", 1)[1])

    def test_logs_identify_reference_frame_and_do_not_assert_success(self):
        trace = self.code.split("Function TracePosition(", 1)[1]
        for field in ("GetFormID()", "GetPositionX()", "GetPositionY()", "GetPositionZ()",
                      "GetAngleZ()", "GetParentCell()", "GetWorldSpace()"):
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


if __name__ == "__main__":
    unittest.main()
