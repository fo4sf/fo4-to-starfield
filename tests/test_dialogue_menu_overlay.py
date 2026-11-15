"""scripts/dialogue/dialogue_menu_overlay.py: overlay four slots on a host-shaped movie. No game files."""
import os
import struct
import sys
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "dialogue"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import dialogue_menu_host as host  # noqa: E402
import dialogue_menu_overlay as overlay  # noqa: E402
import make_probe_swf as swf  # noqa: E402
import make_dialogue_wheel_swf as wheel  # noqa: E402


def host_shaped_movie():
    """Plain root, Menu_mc child sprite that places DialogueList_mc. No game bytes."""
    W, H = 1920 * swf.TWIPS, 1080 * swf.TWIPS
    box = (0, 0, 40 * swf.TWIPS, 20 * swf.TWIPS)
    body = swf.rect(0, W, 0, H) + struct.pack("<HH", swf.FRAME_RATE << 8, 1)
    body += swf.tag(swf.FILE_ATTRIBUTES, bytes([swf.AS3, 0, 0, 0]))
    body += swf.define_shape3(1, [box], swf.PIPBOY_GREEN)
    places = [swf.place_named(1, i + 1, name) for i, name in enumerate(host.HOST_CHILDREN)]
    body += swf.define_sprite(2, places)
    body += swf.place_named(2, 1, host.HOST_ROOT)
    body += swf.tag(swf.SHOW_FRAME) + swf.tag(swf.END)
    length = 8 + len(body)
    return b"CWS" + bytes([swf.VERSION]) + struct.pack("<I", length) + zlib.compress(body, 9)


class OverlayPlanTest(unittest.TestCase):
    def test_pc_pass_layout(self):
        payload = overlay.check_overlay_plan(overlay.overlay_plan())
        self.assertIsNone(payload["document_class"])
        self.assertEqual(payload["menu_mc_role"], "child")
        self.assertTrue(payload["shuttle_in_movie"])
        self.assertEqual(payload["slots_go"], "inside Menu_mc next to DialogueList_mc")

    def test_refuses_document_named_menu_mc(self):
        payload = overlay.overlay_plan()
        payload["menu_mc_role"] = "document"
        with self.assertRaisesRegex(overlay.OverlayError, "child"):
            overlay.check_overlay_plan(payload)

    def test_inject_keeps_list_and_adds_slots(self):
        raw = host_shaped_movie()
        info = overlay.inspect_host(raw)
        self.assertEqual(info["menu_mc_role"], "child")
        self.assertTrue(info["has_dialogue_list"])
        self.assertIsNone(overlay.refuse_own_replacement(raw))
        patched = overlay.overlay_inject(raw)
        movie = swf.read_movie(patched)
        sprites = overlay.sprite_instances(movie)
        list_sprite = next(s for s in sprites if host.HOST_LIST in s["instances"])
        for name in wheel.SLOT_NAMES:
            self.assertIn(name, list_sprite["instances"])
        self.assertIn(host.HOST_ROOT, overlay.root_instances(movie))

    def test_refuses_our_wheel_as_host(self):
        reason = overlay.refuse_own_replacement(wheel.movie_bytes())
        self.assertIsNotNone(reason)
        self.assertIn("Menu_mc", reason)


class HostNamesOverlayTest(unittest.TestCase):
    def test_host_payload_matches_pc_pass(self):
        payload = host.check(host.host_names())
        self.assertEqual(payload["menu_mc_role"], "child")
        self.assertIsNone(payload["document_class"])
        self.assertTrue(payload["shuttle_in_movie"])
        self.assertTrue(payload["kill_root_named_menu_mc"])


if __name__ == "__main__":
    unittest.main()
