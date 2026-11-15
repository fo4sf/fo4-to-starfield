"""relayer.py: the layer-55 bodies of an already converted model are rewritten to L_STATIC and nothing else changes
(synthetic tagfiles and NIFs, no game data). S2 yellow gates, FAL-976."""
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
sys.path.insert(0, HERE)
from fo4sf import nif, relayer, sfbodies, sfnif  # noqa: E402
from test_sfbodies import TagWriter, add_bodies, add_convex, body_types, cube  # noqa: E402


def blob_with(layers):
    """One physics system with one hull body per layer word (a body's own layer in its collisionFilterInfo)."""
    v, f = cube((0, 0, 0), (1, 1, 1))
    w = TagWriter()
    body_types(w, "hknpConvexShape")
    shapes = [add_convex(w, v, f) for _ in layers]
    add_bodies(w, [(s, (0, 0, 0), (0, 0, 0, 1)) for s in shapes])
    blob = bytearray(w.build())
    return blob, w


def words(blob):
    from fo4sf import hktagfile
    tf = hktagfile.Tagfile(bytes(blob))
    it = next(i for k, i in enumerate(tf.items) if k and tf.type_name(i.type) == relayer.BODY)
    return [struct.unpack_from("<I", blob, tf.data_start + it.offset + 64 * j + 48)[0] for j in range(it.count)]


def set_words(blob, values):
    from fo4sf import hktagfile
    tf = hktagfile.Tagfile(bytes(blob))
    it = next(i for k, i in enumerate(tf.items) if k and tf.type_name(i.type) == relayer.BODY)
    for j, value in enumerate(values):
        struct.pack_into("<I", blob, tf.data_start + it.offset + 64 * j + 48, value)
    return bytes(blob)


class RelayerBlobTests(unittest.TestCase):
    def test_layer_55_bodies_become_l_static_and_the_rest_are_byte_identical(self):
        blob, _ = blob_with((1, 2, 3))
        blob = set_words(blob, [0x8037, 0x8001, 0x0037])
        new, notes = relayer.relayer_blob(blob)
        self.assertEqual(words(new), [0x1, 0x8001, 0x1])                      # bit 15 on a static layer is kept
        self.assertEqual(len(new), len(blob))
        diff = [i for i in range(len(blob)) if blob[i] != new[i]]
        self.assertEqual(len(diff), 3)                                          # 0x37->0x01 and 0x80->0 (first), 0x37->0x01 (third)
        self.assertEqual(len(notes), 2)
        self.assertIn("L_CLUTTER_NOCUT", notes[0])
        self.assertIn("body 0", notes[0])
        self.assertIn("body 2", notes[1])

    def test_a_blob_without_layer_55_comes_back_unchanged_with_no_notes(self):
        blob, _ = blob_with((1, 2))
        blob = set_words(blob, [0x8001, 0x4])
        new, notes = relayer.relayer_blob(blob)
        self.assertEqual((new, notes), (blob, []))

    def test_running_it_twice_changes_nothing_more(self):
        blob, _ = blob_with((1,))
        once, _ = relayer.relayer_blob(set_words(blob, [0x8037]))
        twice, notes = relayer.relayer_blob(once)
        self.assertEqual((twice, notes), (once, []))

    def test_unreadable_bytes_are_refused(self):
        with self.assertRaises(relayer.RelayerError):
            relayer.relayer_blob(b"not a tagfile at all")


class RelayerNifTests(unittest.TestCase):
    def nif_with(self, layers):
        blob, _ = blob_with(layers)
        blob = set_words(blob, layers)
        n = sfnif.build_static_nif(b"Gate", [], child_collision_blobs=[blob])
        return nif.serialize(n)

    def test_the_gate_model_walks_on_after_the_rewrite(self):
        raw = self.nif_with([0x8037, 0x8037])
        before = [b["layer"] for b in sfbodies.nif_bodies(raw)]
        new, notes = relayer.relayer_nif(raw)
        after = [b["layer"] for b in sfbodies.nif_bodies(new)]
        self.assertEqual((before, after), ([55, 55], [1, 1]))
        self.assertEqual(len(notes), 2)
        self.assertEqual(len(new), len(raw))                                   # sizes and block layout stay

    def test_a_truncated_physics_block_is_refused_not_sliced(self):
        raw = self.nif_with([0x8037])
        f = nif.parse(raw)
        i = next(k for k in range(len(f.blocks)) if f.type_of(k) == "bhkPhysicsSystem")
        f.blocks[i] = f.blocks[i][:-8]                                          # the size word now over-claims
        with self.assertRaises(relayer.RelayerError):
            relayer.relayer_nif(nif.serialize(f))
        f.blocks[i] = f.blocks[i][:2]
        with self.assertRaises(relayer.RelayerError):
            relayer.relayer_nif(nif.serialize(f))

    def test_a_model_without_layer_55_is_returned_byte_for_byte(self):
        raw = self.nif_with([0x1])
        new, notes = relayer.relayer_nif(raw)
        self.assertEqual((new, notes), (raw, []))


if __name__ == "__main__":
    unittest.main()
