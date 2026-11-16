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


def sprite_ids(movie):
    return [t.get("id") for t in movie["tags"] if t.get("code") == swf.DEFINE_SPRITE and t.get("id")]


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
        self.assertTrue(payload["empty_slot_clips"])
        self.assertTrue(payload["kill_green_fill"])
        self.assertEqual(payload["bind_class"], "Fo4sfDialogueSlots")
        self.assertEqual(payload["bind_on"], "unnamed_container")
        self.assertTrue(payload["kill_bind_on_sealed_dialogue_menu"])

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
            self.assertNotIn(name, list_sprite["instances"])
        nested_names = [n for s in sprites if host.HOST_LIST not in s["instances"] for n in s["instances"]]
        for name in wheel.SLOT_NAMES:
            self.assertIn(name, nested_names)
        self.assertIn(host.HOST_ROOT, overlay.root_instances(movie))

    def test_inject_adds_no_filled_slot_shapes(self):
        raw = host_shaped_movie()
        before = sum(1 for t in swf.read_movie(raw)["tags"] if t.get("code") == swf.DEFINE_SHAPE3)
        patched = overlay.overlay_inject(raw)
        after = sum(1 for t in swf.read_movie(patched)["tags"] if t.get("code") == swf.DEFINE_SHAPE3)
        self.assertEqual(before, after)

    def test_refuses_our_wheel_as_host(self):
        reason = overlay.refuse_own_replacement(wheel.movie_bytes())
        self.assertIsNotNone(reason)
        self.assertIn("Menu_mc", reason)

    def test_inject_skips_placeobject3_depth(self):
        po3 = swf.tag(overlay.PLACE_OBJECT3, bytes([0x06, 0x00]) + struct.pack("<HH", 10, 1) + bytes([0x00]))
        W, H = 1920 * swf.TWIPS, 1080 * swf.TWIPS
        box = (0, 0, 40 * swf.TWIPS, 20 * swf.TWIPS)
        body = swf.rect(0, W, 0, H) + struct.pack("<HH", swf.FRAME_RATE << 8, 1)
        body += swf.tag(swf.FILE_ATTRIBUTES, bytes([swf.AS3, 0, 0, 0]))
        body += swf.define_shape3(1, [box], swf.PIPBOY_GREEN)
        places = [swf.place_named(1, i + 1, name) for i, name in enumerate(host.HOST_CHILDREN)]
        body += swf.define_sprite(2, places + [po3])
        body += swf.place_named(2, 1, host.HOST_ROOT)
        body += swf.tag(swf.SHOW_FRAME) + swf.tag(swf.END)
        raw = b"CWS" + bytes([swf.VERSION]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body, 9)
        patched = overlay.overlay_inject(raw)
        blob = zlib.decompress(patched[8:])
        r = swf.BitReader(blob)
        swf.read_rect(r)
        pos = r.align() + 4
        depths = []
        for code, data in overlay._raw_tags(blob, pos):
            if code != swf.DEFINE_SPRITE:
                continue
            sid = struct.unpack_from("<H", data, 0)[0]
            if sid != 2:
                continue
            depths = [overlay._place_depth(nc, nd) for nc, nd in overlay._raw_tags(data, 4)]
        self.assertIn(10, depths)
        self.assertIn(11, depths)

    def test_inject_skips_importassets_id_9000(self):
        extra = swf.tag(overlay.IMPORT_ASSETS, struct.pack("<HH", 1, 9000) + b"x\x00")
        patched = self._patched_ids(extra)
        movie = swf.read_movie(patched)
        shape_ids = [t.get("id") for t in movie["tags"] if t.get("code") == swf.DEFINE_SHAPE3]
        self.assertTrue(all(i != 9000 for i in shape_ids if i))
        self.assertTrue(any(i and i > 9000 for i in sprite_ids(movie)))

    def test_inject_skips_importassets2_url_id_3(self):
        extra = swf.tag(
            overlay.IMPORT_ASSETS2,
            b"a\x00" + bytes([1, 0]) + struct.pack("<HH", 1, 3) + b"Font\x00",
        )
        patched = self._patched_ids(extra)
        movie = swf.read_movie(patched)
        shape_ids = [t.get("id") for t in movie["tags"] if t.get("code") == swf.DEFINE_SHAPE3]
        self.assertTrue(all(i != 3 for i in shape_ids if i))
        self.assertTrue(any(i and i > 3 for i in sprite_ids(movie)))

    def test_inject_skips_importassets2_digest_id_3(self):
        extra = swf.tag(
            overlay.IMPORT_ASSETS2,
            b"fonts.swf\x00" + bytes([1, 1]) + bytes(20 * [0x11]) + struct.pack("<HH", 1, 3) + b"Font\x00",
        )
        patched = self._patched_ids(extra)
        movie = swf.read_movie(patched)
        shape_ids = [t.get("id") for t in movie["tags"] if t.get("code") == swf.DEFINE_SHAPE3]
        self.assertTrue(all(i != 3 for i in shape_ids if i))
        self.assertTrue(any(i and i > 3 for i in sprite_ids(movie)))

    def test_inject_skips_importassets2_zero_digest_id_3(self):
        extra = swf.tag(
            overlay.IMPORT_ASSETS2,
            b"fonts.swf\x00" + bytes([1, 1]) + bytes(20) + struct.pack("<HH", 1, 3) + b"Font\x00",
        )
        patched = self._patched_ids(extra)
        movie = swf.read_movie(patched)
        shape_ids = [t.get("id") for t in movie["tags"] if t.get("code") == swf.DEFINE_SHAPE3]
        self.assertTrue(all(i != 3 for i in shape_ids if i))
        self.assertTrue(any(i and i > 3 for i in sprite_ids(movie)))

    def test_inject_skips_importassets_url_id_29807(self):
        extra = swf.tag(
            overlay.IMPORT_ASSETS,
            b"fonts.swf\x00" + struct.pack("<HH", 1, 29807) + b"Font\x00",
        )
        patched = self._patched_ids(extra)
        movie = swf.read_movie(patched)
        shape_ids = [t.get("id") for t in movie["tags"] if t.get("code") == swf.DEFINE_SHAPE3]
        self.assertTrue(all(i != 29807 for i in shape_ids if i))
        self.assertTrue(any(i and i > 29807 for i in sprite_ids(movie)))

    def test_inspect_skips_edittext_flags_we_do_not_write(self):
        extra = swf.tag(
            swf.DEFINE_EDIT_TEXT,
            struct.pack("<H", 13) + swf.rect(0, 20, 0, 20) + bytes([0x02, 0xA0]) + b"v\x00",
        )
        extra += swf.tag(swf.DEFINE_SHAPE3, struct.pack("<H", 66) + swf.rect(0, 10, 0, 10) + bytes([0, 0, 0x11, 0x00]))
        W, H = 1920 * swf.TWIPS, 1080 * swf.TWIPS
        box = (0, 0, 40 * swf.TWIPS, 20 * swf.TWIPS)
        body = swf.rect(0, W, 0, H) + struct.pack("<HH", swf.FRAME_RATE << 8, 1)
        body += swf.tag(swf.FILE_ATTRIBUTES, bytes([swf.AS3, 0, 0, 0]))
        body += swf.define_shape3(1, [box], swf.PIPBOY_GREEN)
        body += extra
        places = [swf.place_named(1, i + 1, name) for i, name in enumerate(host.HOST_CHILDREN)]
        body += swf.define_sprite(2, places)
        body += swf.place_named(2, 1, host.HOST_ROOT)
        body += swf.tag(swf.SHOW_FRAME) + swf.tag(swf.END)
        raw = b"CWS" + bytes([swf.VERSION]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body, 9)
        with self.assertRaises(swf.SwfError):
            swf.read_movie(raw)
        self.assertIsNone(overlay.refuse_own_replacement(raw))
        patched = overlay.overlay_inject(raw)
        self.assertTrue(patched.startswith(b"CWS"))
        self.assertIsNone(overlay.refuse_own_replacement(patched))

    def test_archive_hint_beats_aaa_mod(self):
        order = overlay.archive_search_order(
            ["AAA-mod.ba2", "Starfield - Interface.ba2", "zzz.ba2", "readme.txt"])
        self.assertEqual(order[0], "Starfield - Interface.ba2")
        self.assertEqual(order[1], "AAA-mod.ba2")

    def test_inject_skips_existing_id_9000(self):
        W, H = 1920 * swf.TWIPS, 1080 * swf.TWIPS
        box = (0, 0, 40 * swf.TWIPS, 20 * swf.TWIPS)
        body = swf.rect(0, W, 0, H) + struct.pack("<HH", swf.FRAME_RATE << 8, 1)
        body += swf.tag(swf.FILE_ATTRIBUTES, bytes([swf.AS3, 0, 0, 0]))
        body += swf.define_shape3(1, [box], swf.PIPBOY_GREEN)
        body += swf.define_shape3(9000, [box], swf.PIPBOY_GREEN)
        places = [swf.place_named(1, i + 1, name) for i, name in enumerate(host.HOST_CHILDREN)]
        body += swf.define_sprite(2, places)
        body += swf.place_named(2, 1, host.HOST_ROOT)
        body += swf.tag(swf.SHOW_FRAME) + swf.tag(swf.END)
        raw = b"CWS" + bytes([swf.VERSION]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body, 9)
        patched = overlay.overlay_inject(raw)
        movie = swf.read_movie(patched)
        ids = [t.get("id") for t in movie["tags"] if t.get("code") == swf.DEFINE_SHAPE3]
        self.assertIn(9000, ids)
        self.assertEqual(ids.count(9000), 1)
        self.assertTrue(any(i and i > 9000 for i in sprite_ids(movie)))

    def _patched_ids(self, extra_root_tags):
        W, H = 1920 * swf.TWIPS, 1080 * swf.TWIPS
        box = (0, 0, 40 * swf.TWIPS, 20 * swf.TWIPS)
        body = swf.rect(0, W, 0, H) + struct.pack("<HH", swf.FRAME_RATE << 8, 1)
        body += swf.tag(swf.FILE_ATTRIBUTES, bytes([swf.AS3, 0, 0, 0]))
        body += swf.define_shape3(1, [box], swf.PIPBOY_GREEN)
        body += extra_root_tags
        places = [swf.place_named(1, i + 1, name) for i, name in enumerate(host.HOST_CHILDREN)]
        body += swf.define_sprite(2, places)
        body += swf.place_named(2, 1, host.HOST_ROOT)
        body += swf.tag(swf.SHOW_FRAME) + swf.tag(swf.END)
        raw = b"CWS" + bytes([swf.VERSION]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body, 9)
        return overlay.overlay_inject(raw)

    def test_inject_skips_font2_and_text_id_9000(self):
        extra = swf.tag(48, struct.pack("<H", 9000)) + swf.tag(11, struct.pack("<H", 9000))
        patched = self._patched_ids(extra)
        movie = swf.read_movie(patched)
        shape_ids = [t.get("id") for t in movie["tags"] if t.get("code") == swf.DEFINE_SHAPE3]
        self.assertTrue(all(i != 9000 for i in shape_ids if i))
        self.assertTrue(any(i and i > 9000 for i in sprite_ids(movie)))

    def test_inject_skips_font_and_videostream_id_9000(self):
        extra = swf.tag(10, struct.pack("<H", 9000)) + swf.tag(60, struct.pack("<H", 9000))
        patched = self._patched_ids(extra)
        movie = swf.read_movie(patched)
        shape_ids = [t.get("id") for t in movie["tags"] if t.get("code") == swf.DEFINE_SHAPE3]
        self.assertTrue(all(i != 9000 for i in shape_ids if i))
        self.assertTrue(any(i and i > 9000 for i in sprite_ids(movie)))

    def test_inject_skips_videostream_nested_in_menu_mc(self):
        W, H = 1920 * swf.TWIPS, 1080 * swf.TWIPS
        box = (0, 0, 40 * swf.TWIPS, 20 * swf.TWIPS)
        body = swf.rect(0, W, 0, H) + struct.pack("<HH", swf.FRAME_RATE << 8, 1)
        body += swf.tag(swf.FILE_ATTRIBUTES, bytes([swf.AS3, 0, 0, 0]))
        body += swf.define_shape3(1, [box], swf.PIPBOY_GREEN)
        video = swf.tag(60, struct.pack("<H", 9000))
        places = [swf.place_named(1, i + 1, name) for i, name in enumerate(host.HOST_CHILDREN)]
        body += swf.define_sprite(2, [video] + places)
        body += swf.place_named(2, 1, host.HOST_ROOT)
        body += swf.tag(swf.SHOW_FRAME) + swf.tag(swf.END)
        raw = b"CWS" + bytes([swf.VERSION]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body, 9)
        patched = overlay.overlay_inject(raw)
        movie = swf.read_movie(patched)
        shape_ids = [t.get("id") for t in movie["tags"] if t.get("code") == swf.DEFINE_SHAPE3]
        self.assertTrue(all(i != 9000 for i in shape_ids if i))
        self.assertTrue(any(i and i > 9000 for i in sprite_ids(movie)))

    def test_inject_skips_shape_two_sprites_deep(self):
        W, H = 1920 * swf.TWIPS, 1080 * swf.TWIPS
        box = (0, 0, 40 * swf.TWIPS, 20 * swf.TWIPS)
        inner = swf.define_shape3(9000, [box], swf.PIPBOY_GREEN)
        sprite_inner = swf.tag(swf.DEFINE_SPRITE, struct.pack("<HH", 5, 1) + inner + swf.tag(swf.SHOW_FRAME) + swf.tag(swf.END))
        sprite_outer = swf.tag(swf.DEFINE_SPRITE, struct.pack("<HH", 6, 1) + sprite_inner + swf.tag(swf.SHOW_FRAME) + swf.tag(swf.END))
        patched = self._patched_ids(sprite_outer)
        movie = swf.read_movie(patched)

        def shape_ids(tags):
            out = []
            for t in tags:
                if t.get("code") == swf.DEFINE_SHAPE3 and t.get("id") is not None:
                    out.append(t["id"])
                if t.get("code") == swf.DEFINE_SPRITE:
                    out.extend(shape_ids(t.get("tags") or []))
            return out

        ids = shape_ids(movie["tags"])
        self.assertEqual(ids.count(9000), 1)
        self.assertTrue(any(i > 9000 for i in sprite_ids(movie)))

    def test_short_hint_archive_does_not_abort(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "Data")
            os.makedirs(data)
            with open(os.path.join(data, overlay.HOST_ARCHIVE_HINT), "wb") as f:
                f.write(b"short")
            with self.assertRaisesRegex(overlay.OverlayError, "not in the player's archives"):
                overlay.extract_host_movie(tmp)

    def test_lz4_ba2_read_does_not_abort(self):
        import tempfile
        from fo4sf.ba2 import Ba2Error
        class Boom:
            def __init__(self, path):
                pass
            def find(self, name):
                return 0
            def read(self, name):
                raise Ba2Error("LZ4-compressed (v3) textures are not supported")
        saved = overlay.Ba2
        overlay.Ba2 = Boom
        try:
            with tempfile.TemporaryDirectory() as tmp:
                data = os.path.join(tmp, "Data")
                os.makedirs(data)
                with open(os.path.join(data, overlay.HOST_ARCHIVE_HINT), "wb") as f:
                    f.write(b"x")
                with self.assertRaisesRegex(overlay.OverlayError, "not in the player's archives"):
                    overlay.extract_host_movie(tmp)
        finally:
            overlay.Ba2 = saved


class HostNamesOverlayTest(unittest.TestCase):
    def test_host_payload_matches_pc_pass(self):
        payload = host.check(host.host_names())
        self.assertEqual(payload["menu_mc_role"], "child")
        self.assertIsNone(payload["document_class"])
        self.assertTrue(payload["shuttle_in_movie"])
        self.assertTrue(payload["kill_root_named_menu_mc"])


if __name__ == "__main__":
    unittest.main()
