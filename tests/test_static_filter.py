"""A FO4 body frozen static on layer 55 L_CLUTTER_NOCUT is written as L_STATIC; every other filter word is kept
(synthetic data, no game files).

The Vault 111 gear-room gates (V111GearRoomGate01 / 02) are FO4 swing gates: two 10 kg leaves on hinges, filter word
0x8037 (layer 55 + bit 15). Their joints are not converted, so the leaves are static Starfield bodies, and the player
walked through them in integ_1018 (playtest row 19). Starfield's own static bodies on layer 55 are the New Atlantis
lobby turnstile leaves, STAT records placed across walkways the player passes (word 0x8037 exactly), while bit 15 on
L_STATIC is walked on (the MAST plaza): the layer is what lets the controller through (research log 2026-10-17)."""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
sys.path.insert(0, HERE)
from fo4sf import convert_static, fo4collision as fc, meshcollision  # noqa: E402
from test_mixed_system_collision import (BODIES_AT, GATE_REASON, LEAF_L, LEAF_R, SPHERE, GateSystem,  # noqa: E402
                                         StubTemplate, emitted, gate_mass, gate_nif)

GATE_FILTER, DUMMY_FILTER = 0x8037, 0xF                  # FO4 V111GearRoomGate01: leaves 0x8037, RIGID_BODY_DUMMY 0xf
BODY_TYPE, FILTER_OFFSET = 2, 8


class FilteredGate(GateSystem):
    """The gate system with FO4's real filter words (body + 20): the dummy sphere 0xf, both leaves 0x8037."""

    def __init__(self, shapes=(SPHERE, LEAF_R, LEAF_L), filters=(DUMMY_FILTER, GATE_FILTER, GATE_FILTER)):
        super().__init__(shapes)
        self.filters = filters

    def unpack(self, fmt, at):
        if fmt == "<I" and (at - BODIES_AT) % fc.BODY_SIZE == meshcollision.FO4_BODY_FILTER:
            return (self.filters[(at - BODIES_AT) // fc.BODY_SIZE],)
        return super().unpack(fmt, at)


class FilterTemplate(StubTemplate):
    """Body cinfos get their own type index and the filter word its own offset, so the test can read it back."""

    def type(self, name):
        return BODY_TYPE if name == "hknpPhysicsSystemData::bodyCinfoWithAttachment" else 1

    def field(self, type_idx, name):
        return SimpleNamespace(offset=FILTER_OFFSET if name == "collisionFilterInfo" else 0, type=1)


class RecordingWriter(meshcollision._Writer):
    """Keeps every item it is given, so the body words can be checked without parsing the tagfile."""
    added = []

    def add(self, type_idx, flags, payload, count):
        RecordingWriter.added.append((type_idx, bytes(payload)))
        return super().add(type_idx, flags, payload, count)


def written_filters():
    return [int.from_bytes(payload[FILTER_OFFSET:FILTER_OFFSET + 4], "little")
            for ti, payload in RecordingWriter.added if ti == BODY_TYPE]


class StaticFilterTests(unittest.TestCase):
    def test_layer_55_becomes_static_and_says_why(self):
        for word in (0x8037, 0x37, 0x8137):
            filt, note = meshcollision.static_filter(word)
            self.assertEqual(filt, 0x1, hex(word))
            self.assertIn("L_CLUTTER_NOCUT", note)
            self.assertIn("L_STATIC", note)

    def test_every_other_word_is_kept_bit_15_included(self):
        for word in (0x1, 0x8001, 0x4, 0x8004, 0xF, 0x1F, 0x801F, 0x1D, 0x3, 0x2):
            self.assertEqual(meshcollision.static_filter(word), (word, None), hex(word))


class GateBodiesTests(unittest.TestCase):
    def setUp(self):
        RecordingWriter.added = []
        for target, name, kw in ((meshcollision.hkpackfile, "Packfile", {"return_value": FilteredGate()}),
                                 (fc, "body_mass", {"side_effect": gate_mass}),
                                 (meshcollision, "_Tmpl", {"new": FilterTemplate}),
                                 (meshcollision, "_Writer", {"new": RecordingWriter}),
                                 (meshcollision.hktagfile, "sections", {"return_value": [("TYPE", 8, 8), ("SDKV", 8, 8)]}),
                                 (meshcollision, "_emit_sphere", {"side_effect": emitted}),
                                 (meshcollision, "_emit_convex", {"side_effect": emitted})):
            p = patch.object(target, name, **kw)
            p.start()
            self.addCleanup(p.stop)

    def test_frozen_leaves_are_written_on_l_static_the_dummy_keeps_its_layer(self):
        motion = {}
        out = meshcollision.convert_bodies(b"gate", b"native template", dynamic_template=None, motion=motion)
        self.assertEqual(len(out), 3)
        self.assertEqual(written_filters(), [DUMMY_FILTER, 0x1, 0x1])        # was [0xf, 0x8037, 0x8037]
        self.assertEqual([r[:7] for r in motion["relayered"]], ["body 1:", "body 2:"])
        self.assertIn("0x8037", motion["relayered"][0])

    def test_the_report_names_the_relayered_leaves(self):
        report, motion = {}, {}
        blobs = convert_static.fo4_native_collision(gate_nif(), b"native template", report,
                                                    dynamic_template=b"dynamic template", motion=motion)
        self.assertEqual(len(blobs), 3)
        self.assertEqual(report["source"], "fo4-native")
        self.assertEqual(report["dynamic_kept_static"], [GATE_REASON])
        self.assertEqual(len(report["relayered"]), 2)
        self.assertEqual(written_filters(), [DUMMY_FILTER, 0x1, 0x1])

    def test_a_lone_movable_leaf_keeps_fo4s_word(self):
        # a single dynamic body is converted movable (pushable clutter as in FO4): its word is passed on untouched
        with patch.object(meshcollision.hkpackfile, "Packfile",
                          return_value=FilteredGate(shapes=(LEAF_R,), filters=(GATE_FILTER,))), \
                patch.object(fc, "body_mass", side_effect=lambda p, s, k: 10.0), \
                patch.object(meshcollision, "_dynamic_body", return_value=b"DYNAMIC") as dynamic_body:
            motion = {}
            out = meshcollision.convert_bodies(b"leaf", b"native template", dynamic_template=b"dynamic template",
                                               motion=motion)
        self.assertEqual(out, [b"DYNAMIC"])
        self.assertEqual(dynamic_body.call_args.args[3], GATE_FILTER)
        self.assertNotIn("relayered", motion)


if __name__ == "__main__":
    unittest.main()
