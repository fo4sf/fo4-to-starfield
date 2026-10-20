"""FO4 physics systems that mix anchored and dynamic bodies (hinged gates, breakable rails, standpipes) keep their FO4
bodies as static Starfield bodies (synthetic data, no game files).

Regression: once the rigid merge had reported such a system (motion["rigid_reported"]), convert_bodies took every
body that has a "stays static" reason for a dynamic one and called _dynamic_body without a template. That raised
"TypeError: object of type 'NoneType' has no len()" and the whole model lost its FO4 collision (29 models in the
integ_1011 build, among them V111GearRoomGate01 / 02, which then got guessed surface boxes instead)."""
import os
import struct
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
sys.path.insert(0, HERE)
from fo4sf import convert_static, fo4collision as fc, hkpackfile, meshcollision, nif  # noqa: E402
from test_review_fixes import av_fields  # noqa: E402

IDENT = (1, 0, 0, 0, 1, 0, 0, 0, 1)
BODIES_AT = 100
SPHERE, LEAF_R, LEAF_L = 1000, 2000, 3000
GATE_REASON = "3-body system (2 dynamic): 1 anchored / keyframed bodies: joints not converted"


class GateSystem:
    """hkpackfile.Packfile stand-in for the gate's one physics system: body 0 a sphere (FO4's anchored
    RIGID_BODY_DUMMY), bodies 1 and 2 convex leaves (GateR, GateL). Body records are fc.BODY_SIZE apart."""

    def __init__(self, shapes=(SPHERE, LEAF_R, LEAF_L)):
        self.shapes = shapes

    def objects(self):
        return [(1, "hknpPhysicsSystemData"), (SPHERE, "hknpSphereShape"),
                (LEAF_R, "hknpConvexPolytopeShape"), (LEAF_L, "hknpConvexPolytopeShape")]

    def array(self, at):
        return (BODIES_AT, len(self.shapes))

    def pointer(self, at):
        k, rest = divmod(at - BODIES_AT, fc.BODY_SIZE)
        return self.shapes[k] if rest == 0 and 0 <= k < len(self.shapes) else None

    def unpack(self, fmt, at):
        if fmt == "<4f":
            return (0.0, 0.0, 0.0, 1.0)            # body position / orientation (finite, unrotated)
        if fmt == "<I":
            return (0,)                             # collision filter: layer 0
        raise AssertionError(f"unexpected read {fmt} @{at}")


class StubTemplate:
    """meshcollision._Tmpl stand-in: every type and field resolves, item bytes are zeros."""

    def __init__(self, blob):
        self.blob = blob

    def type(self, name):
        return 1

    def field(self, type_idx, name):
        return SimpleNamespace(offset=0, type=1)

    def item_bytes(self, name, k=0, count=None):
        return bytes(64)


def gate_mass(p, sysobj, k):
    return None if k == 0 else 10.0                 # V111GearRoomGate01: dummy anchored, both leaves 10 kg


def emitted(w, *args, **kwargs):
    return w.add(1, 0x10, bytes(16), 1)


def gate_nif():
    """V111GearRoomGate01's layout: root -> RIGID_BODY_DUMMY, GateR, GateL; one collision object per node, all three on
    ONE physics system (body 0 anchored, bodies 1 and 2 the swinging leaves)."""
    f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
    f.string_index(b"Gate")
    f.add_block("NiNode", av_fields(0, (0, 0, 0), IDENT, 1.0) + struct.pack("<Iiii", 3, 1, 2, 3))   # 0 root
    f.add_block("NiNode", av_fields(0, (0, 0, 0), IDENT, 1.0) + struct.pack("<I", 0))              # 1 dummy
    f.add_block("NiNode", av_fields(0, (0, 35, 0), IDENT, 1.0) + struct.pack("<I", 0))             # 2 GateR
    f.add_block("NiNode", av_fields(0, (0, 140, 0), IDENT, 1.0) + struct.pack("<I", 0))            # 3 GateL
    for node, body in ((1, 0), (2, 1), (3, 2)):
        f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", node, 0x80, 7, body))           # 4, 5, 6
    f.add_block("bhkPhysicsSystem", struct.pack("<I", 4) + b"gate")                               # 7
    f.footer = struct.pack("<II", 1, 0)
    return nif.parse(nif.serialize(f))


class MixedSystemTests(unittest.TestCase):
    def setUp(self):
        self.dynamic_calls = []
        real_dynamic_body = meshcollision._dynamic_body

        def spy(template, *args, **kwargs):
            self.dynamic_calls.append(template)
            return real_dynamic_body(template, *args, **kwargs)
        for target, name, kw in ((meshcollision.hkpackfile, "Packfile", {"return_value": GateSystem()}),
                                 (fc, "body_mass", {"side_effect": gate_mass}),
                                 (meshcollision, "_Tmpl", {"new": StubTemplate}),
                                 (meshcollision.hktagfile, "sections", {"return_value": [("TYPE", 8, 8), ("SDKV", 8, 8)]}),
                                 (meshcollision, "_emit_sphere", {"side_effect": emitted}),
                                 (meshcollision, "_emit_convex", {"side_effect": emitted}),
                                 (meshcollision, "_dynamic_body", {"side_effect": spy})):
            p = patch.object(target, name, **kw)
            p.start()
            self.addCleanup(p.stop)

    def test_gate_keeps_its_three_fo4_bodies_as_static_bodies(self):
        report, motion = {}, {}
        blobs = convert_static.fo4_native_collision(gate_nif(), b"native template", report,
                                                    dynamic_template=b"dynamic template", motion=motion)
        self.assertNotIn("fo4_collision_error", report)       # was "TypeError: object of type 'NoneType' has no len()"
        self.assertEqual(report, {"source": "fo4-native", "bodies": 3, "dynamic_kept_static": [GATE_REASON]})
        self.assertNotIn("dynamic", motion)                   # nothing movable: the leaves need their joints
        self.assertEqual(self.dynamic_calls, [])
        self.assertEqual(len(blobs), 3)
        for blob, translation, rotation in blobs:            # each body a tagfile, on its own FO4 node
            self.assertEqual(blob[4:8], b"TAG0")
            self.assertEqual(tuple(rotation), IDENT)
        self.assertAlmostEqual(blobs[1][1][1], 0.5, places=6)  # GateR: 35 FO4 units = 0.5 m
        self.assertAlmostEqual(blobs[2][1][1], 2.0, places=6)  # GateL: 140 units = 2 m

    def test_reported_system_body_stays_static_without_a_dynamic_template(self):
        # the state the rigid merge leaves behind for this system, then the per-body path for GateR alone
        motion = {"kept_static": [GATE_REASON], "rigid_reported": True}
        out = meshcollision.convert_bodies(b"gate", b"native template", select=[1], dynamic_template=None, motion=motion)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], bytes)                  # a plain static body blob
        self.assertEqual(self.dynamic_calls, [])
        self.assertEqual(motion, {"kept_static": [GATE_REASON], "rigid_reported": True})   # no second reason

    def test_unreported_system_body_still_gets_its_own_reason(self):
        motion = {}
        out = meshcollision.convert_bodies(b"gate", b"native template", select=[1], dynamic_template=None, motion=motion)
        self.assertEqual(len(out), 1)
        self.assertEqual(motion["kept_static"],
                         ["body 1 (10 kg): one of 3 bodies (ragdoll / breakable: constraints not converted)"])

    def test_lone_dynamic_body_with_a_template_is_still_movable(self):
        with patch.object(meshcollision.hkpackfile, "Packfile", return_value=GateSystem(shapes=(LEAF_R,))), \
                patch.object(fc, "body_mass", return_value=10.0), \
                patch.object(meshcollision, "_dynamic_body", return_value=b"DYNAMIC") as dynamic_body:
            motion = {}
            out = meshcollision.convert_bodies(b"can", b"native template", dynamic_template=b"dynamic template",
                                               motion=motion)
        self.assertEqual(out, [b"DYNAMIC"])
        self.assertEqual(dynamic_body.call_args.args[0], b"dynamic template")
        self.assertEqual(motion["dynamic"], 10.0)

    def test_requested_mass_scale_reaches_the_serialized_body_mass(self):
        with patch.object(meshcollision.hkpackfile, "Packfile", return_value=GateSystem(shapes=(LEAF_R,))), \
                patch.object(fc, "body_mass", return_value=10.0), \
                patch.object(meshcollision, "_dynamic_body", return_value=b"DYNAMIC") as dynamic_body:
            motion = {}
            meshcollision.convert_bodies(b"can", b"native template", dynamic_template=b"dynamic template",
                                         motion=motion, mass_scale=0.2)
        self.assertAlmostEqual(motion["dynamic"], 2.0)
        self.assertAlmostEqual(dynamic_body.call_args.args[4], 2.0)

    def test_invalid_mass_scale_never_emits_a_dynamic_body(self):
        for scale in (0, -1, float("nan"), float("inf")):
            with self.subTest(scale=scale), \
                    patch.object(meshcollision, "_dynamic_body", side_effect=AssertionError("emitted")):
                with self.assertRaises(ValueError):
                    meshcollision.convert_bodies(b"can", b"native template",
                                                 dynamic_template=b"dynamic template",
                                                 motion={}, mass_scale=scale)

    def test_dynamic_body_without_a_template_fails_with_a_clear_reason(self):
        with self.assertRaisesRegex(hkpackfile.PackfileError, "needs the vanilla dynamic template"):
            meshcollision._dynamic_body(None, GateSystem(), [("convex", LEAF_R, IDENT, (0.0, 0.0, 0.0))], 0, 10.0)


class BodyCinfoMassTests(unittest.TestCase):
    class Template:
        class tf:
            @staticmethod
            def size_of(_type):
                return 4

        def field(self, _type_idx, name):
            return SimpleNamespace(offset={"motionType": 0, "flags": 4, "mass": 8, "motionPropertiesId": 12}[name],
                                   type=1)

    def packed_mass(self, mass):
        body = bytearray(16)
        meshcollision._dynamic_body_fields(self.Template(), 1, body, mass)
        return struct.unpack_from("<f", body, 8)[0]

    def test_valid_scale_writes_a_finite_positive_float32_mass(self):
        self.assertAlmostEqual(self.packed_mass(2.0), 2.0)
        self.assertAlmostEqual(self.packed_mass(10.0), 10.0)

    def test_invalid_masses_are_rejected_at_the_writer(self):
        for mass in (0, -10, float("nan"), float("inf"), 1e40, 1e-46):
            with self.subTest(mass=mass):
                with self.assertRaises(ValueError):
                    self.packed_mass(mass)


if __name__ == "__main__":
    unittest.main()
