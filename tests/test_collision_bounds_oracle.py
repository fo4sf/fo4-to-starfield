"""Synthetic tests for scripts/oracles/collision_bounds.py (no game assets)."""
import dataclasses
import importlib.util
import io
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "tests"))
from fo4sf import fo4collision, hktagfile, nif, sfcollision, sfnif  # noqa: E402
from test_collision import fake_template as untagged_template          # header and words only: not a tagfile
import test_sfbodies
from test_sfbodies import (BODY, PSD, TagWriter, _sec, _v, add_bodies, add_body, add_convex, body_types, cube,
                           convex_blob, mesh_blob)

spec = importlib.util.spec_from_file_location(
    "collision_bounds_oracle",
    Path(__file__).resolve().parents[1] / "scripts/oracles/collision_bounds.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def template_tagfile(bodies=None):
    """A 6,168-byte box template that is a real tagfile, as vanilla's is: sfcollision.check_template's header, type name
    and identity rows at 528 / 544 / 560, inside an hknpBoxShape item that spans the words box_blob writes. The root
    system lists bodies(w, box item) [(shape item, position, quaternion)]: by default one identity body on the box."""
    def build(pad):
        w = TagWriter()
        body_types(w, "hknpBoxShape")
        w.type("hknpBoxShape", 800)
        w.type("p" * pad, 4)                           # each character is one byte of the type strings
        box = w.item("hknpBoxShape", bytes(800))
        add_bodies(w, bodies(w, box) if bodies else [(box, (0, 0, 0), (0, 0, 0, 1))])
        return bytearray(w.build())
    blob = build(1 + sfcollision.BLOB_SIZE - len(build(1)))
    tf = hktagfile.Tagfile(bytes(blob))
    box = next(it for it in tf.items[1:] if tf.type_name(it.type) == "hknpBoxShape")
    assert len(blob) == sfcollision.BLOB_SIZE and tf.data_start + box.offset <= 528 < 784 <= tf.data_start + box.offset + 800
    for k in range(3):
        struct.pack_into("<3f", blob, 528 + 16 * k, *(float(a == k) for a in range(3)))
    return bytes(blob)


def fake_template():
    return template_tagfile()


def shape(box, name=b"Prop:0"):
    sphere = (*box[:3], max(box[3:]))
    return sfnif.StaticShape(name, b"a" * 20 + b"\\" + b"b" * 20, 6, 4, "m.mat", sphere, box)


def nif_bytes(mesh_box, collision=None, children=None):
    blob = collision
    extra = children
    return nif.serialize(sfnif.build_static_nif(b"Prop", [shape(mesh_box)],
                                                collision_blob=blob, child_collision_blobs=extra))


def truncate_block(data, block_type, size, nth=0):
    """Cut the nth block of block_type to its first size bytes; the NIF container stays valid."""
    f = nif.parse(data)
    hits = [i for i in range(len(f.blocks)) if f.type_of(i) == block_type]
    f.blocks[hits[nth]] = f.blocks[hits[nth]][:size]
    return nif.serialize(f)


def raw_tagfile(tst, tna, tbdy, items=()):
    """TAG0 with hand-written type strings / names / bodies (TagWriter only writes well-formed types) and items
    [(type, data offset, count)]."""
    types = _sec(b"TST1", tst) + _sec(b"TNA1", tna) + _sec(b"FST1", b"") + _sec(b"TBDY", tbdy)
    item = bytes(12) + b"".join(struct.pack("<III", *it) for it in items)
    body = (_sec(b"SDKV", b"20190200") + _sec(b"DATA", bytes(16)) + _sec(b"TYPE", types, leaf=False)
            + _sec(b"INDX", _sec(b"ITEM", item) + _sec(b"PTCH", b""), leaf=False))
    return _sec(b"TAG0", body, leaf=False)


def own_parent_blob(name, size):
    """A one-body tagfile whose type `name` (of `size`; 0 makes size_of ask the parent) is its own parent."""
    w = TagWriter()
    body_types(w, "hknpConvexShape")
    w.type("hknpConvexShape", 80)
    add_body(w, w.item("hknpConvexShape", bytes(80)))
    w.types = [(n, size, f, n) if n == name else (n, sz, f, p) for n, sz, f, p in w.types]
    return w.build()


def _any_varint(x):
    """Havok varint of any size (test_sfbodies._v stops at 14 bits): 0xF8 + 8 big-endian bytes."""
    return _v(x) if x < 0x4000 else b"\xf8" + x.to_bytes(8, "big")


def huge_offset_blob():
    """A convex body whose convexRadius field sits at offset 2**63: struct offsets past ssize_t raise OverflowError."""
    w = TagWriter()
    body_types(w, "hknpConvexShape")
    w.type("hull", 48, [("vertices", 0, "ptr"), ("faces", 16, "ptr"), ("indices", 32, "ptr")])
    w.type("hknpConvexShape", 80, [("convexRadius", 1 << 63, "float3"), ("hull", 16, "hull")])
    add_body(w, w.item("hknpConvexShape", bytes(80)))
    with mock.patch.object(test_sfbodies, "_v", _any_varint):
        return w.build()


IDENT = (1, 0, 0, 0, 1, 0, 0, 0, 1)


def node(children=(), t=(0, 0, 0), rot=IDENT, scale=1.0, coll=-1, extra=(), controller=-1):
    """An unnamed NiNode block: NiAVObject (extra refs, controller, flags, transform, collision ref), child table."""
    return (struct.pack("<iI", -1, len(extra)) + struct.pack(f"<{len(extra)}i", *extra)
            + struct.pack("<iI3f9ffiI", controller, 0xE, *t, *rot, scale, coll, len(children))
            + struct.pack(f"<{len(children)}i", *children))


def root(children=(4,), coll=2, **av):
    """box_scene's root node: BSXFlags (block 1) as extra data, collision object 2, BSGeometry 4 as its child."""
    return node(children, coll=coll, extra=(1,), **av)


def box_scene(center=(0, 0, 0.5)):
    """The matching box fixture as a NifFile: 0 root NiNode, 1 BSXFlags, 2 bhkNPCollisionObject (target 0, system 3),
    3 bhkPhysicsSystem, 4 BSGeometry (collision ref @72, skin @116), 5 its NiIntegerExtraData, 6 its shader."""
    box = sfcollision.box_blob(fake_template(), center, (0.4, 0.4, 0.5))
    return nif.parse(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box))


def two_body_blob():
    """One physics system holding two convex bodies: a 0.1 m cube (body 0) inside the 0.8 x 0.8 x 1 m box (body 1)."""
    w = TagWriter()
    body_types(w, "hknpConvexShape")
    add_bodies(w, [(add_convex(w, *cube(lo, hi)), (0, 0, 0), (0, 0, 0, 1))
                   for lo, hi in (((-0.05, -0.05, 0), (0.05, 0.05, 0.1)), ((-0.4, -0.4, 0), (0.4, 0.4, 1)))])
    return w.build()


def geometry(f, i, **fields):
    """Rewrite BSGeometry block i with some fields changed."""
    f.blocks[i] = sfnif.build_bsgeometry(dataclasses.replace(sfnif.parse_bsgeometry(f.blocks[i]), **fields))


def two_piece_scene(second, collision):
    """build_static_nif with a 0.8 x 0.8 x 1 m piece at the origin (BSGeometry 4) and a `second` box (BSGeometry 7)."""
    return nif.parse(nif.serialize(sfnif.build_static_nif(
        b"Prop", [shape((0, 0, 0.5, 0.4, 0.4, 0.5)), shape(second, b"Prop:1")], collision_blob=collision)))


def scene_graph_cases():
    """{name: (NifFile, error)}. nif.world_transforms composed the geometry and the root's collision alike in each, so
    the boxes matched and the report was clean."""
    cases = {}
    f = box_scene()                                    # the engine reparents a child it attaches twice
    f.blocks[0] = root((4, f.add_block("NiNode", node((4,), t=(5, 0, 0)))))
    cases["two parents"] = f, "block 4: listed as a child by nodes [0, 7]"
    f = box_scene()                                    # the first parent is an unattached node
    f.add_block("NiNode", node((4,)))
    f.blocks[0] = root((f.add_block("NiNode", node((4,), t=(5, 0, 0))),))
    cases["first parent outside the graph"] = f, "block 4: listed as a child by nodes [7, 8]"
    f = box_scene()                                    # never attached, so never drawn: it sat at the origin
    f.blocks[0] = root(())
    cases["geometry outside the graph"] = f, "BSGeometry 4: not in the scene graph below root 0"
    f = box_scene()
    f.blocks[0] = root((4, f.add_block("NiNode", node((0,)))))
    cases["root in a cycle"] = f, "root 0: listed as a child by nodes [7]"
    for footer in (struct.pack("<II", 1, 99), struct.pack("<II", 1, 1), struct.pack("<I", 0), b"\x01\x00"):
        f = box_scene()
        f.footer = footer
        cases[f"footer {footer.hex()}"] = f, f"footer ({len(footer)} bytes) does not name a scene root"
    f = box_scene()                                    # world_transforms dropped the top 5 levels, x = 5 among them
    chain = [f.add_block("NiNode", b"") for _ in range(70)]
    for k, i in enumerate(chain):
        f.blocks[i] = node(chain[k + 1:k + 2] or (4,), t=(0, 0, 0) if k else (5, 0, 0))
    f.blocks[0] = root(chain[:1])
    cases["70 levels"] = f, "scene graph deeper than 64 levels below root 0"
    f = box_scene()                                    # 5 marker positions (8 + 5 * 20 bytes) read as a child table
    f.add_block("BSFurnitureMarkerNode", node((4,), extra=(0,) * 5) + bytes(8))
    f.blocks[0] = root((f.add_block("NiNode", node((4,), t=(5, 0, 0))),))
    cases["furniture marker"] = f, "block 4: world transform follows parent 7, scene parent 8"
    f = box_scene()                                    # world_transforms gives BSFaceGenNiNode's children no parent
    f.blocks[0] = root((f.add_block("BSFaceGenNiNode", node((4,), t=(5, 0, 0))),))
    cases["face gen node"] = f, "block 7: BSFaceGenNiNode is not a plain NiNode / BSFadeNode"
    f = box_scene()                                    # turns its children to the camera at run time
    f.blocks[0] = root((f.add_block("NiBillboardNode", node((4,)) + struct.pack("<H", 0)),))
    cases["billboard node"] = f, "block 7: NiBillboardNode is not a plain NiNode / BSFadeNode"
    return cases


def collision_ownership_cases():
    """{name: (NifFile, error)}. The oracle measured every bhkNPCollisionObject at its target, whether or not the
    collision ref of a loaded block named it."""
    cases = {}
    f = box_scene()                                    # nothing loads it, yet its box matched
    f.blocks[0] = root(coll=-1)
    cases["named by no block"] = f, "collision object 2: named by the collision refs of blocks [] below root 0"
    f = box_scene()
    f.blocks[0] = root((4, f.add_block("NiNode", node(coll=2))))
    cases["named by two blocks"] = f, "collision object 2: named by the collision refs of blocks [0, 7]"
    f = box_scene()                                    # the block that names it is not attached
    f.blocks[2] = struct.pack("<iHiI", f.add_block("NiNode", node(coll=2)), 0x80, 3, 0)
    f.blocks[0] = root(coll=-1)
    cases["named outside the graph"] = f, "collision object 2: named by the collision refs of blocks [] below root 0"
    f = box_scene()
    f.blocks[0] = root((4, f.add_block("NiNode", node())))
    f.blocks[2] = struct.pack("<iHiI", 7, 0x80, 3, 0)
    cases["target is not the naming block"] = f, "collision object 2: target 7 is not block 0, which references it"
    f = box_scene()                                    # the BSGeometry's own collision ref names its extra data
    f.blocks[4] = f.blocks[4][:72] + struct.pack("<i", 5) + f.blocks[4][76:]
    cases["collision ref to extra data"] = f, "block 4: collision ref 5 is not a bhkNPCollisionObject"
    return cases


def collision_body_cases():
    """{name: (NifFile, error)}. The oracle read a 10-byte header and every body of a system for each object."""
    cases = {}
    f = box_scene()                                    # a body the one-body system does not have
    f.blocks[2] = struct.pack("<iHiI", 0, 0x80, 3, 1)
    cases["body id 1"] = f, "collision object 2: body id 1, not 0"
    f = box_scene()
    f.blocks[2] = f.blocks[2][:12]
    cases["12-byte header"] = f, "collision object 2: truncated header (12 bytes)"
    f = box_scene()
    f.blocks[2] += bytes(4)
    cases["18-byte header"] = f, "collision object 2: trailing bytes after its header (18 bytes)"
    f = box_scene()
    f.blocks[3] += bytes(4)
    cases["bytes after the blob"] = f, (f"collision object 2: physics system 3 has 4 bytes after its "
                                        f"{sfcollision.BLOB_SIZE}-byte blob")
    box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
    hull = convex_blob(*cube((-0.4, -0.4, 0), (0.4, 0.4, 1)))
    f = nif.parse(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box, children=[hull]))
    f.blocks[8] = struct.pack("<iHiI", 7, 0x80, 3, 0)   # the child node's object takes the root's system instead
    cases["shared physics system"] = f, "collision object 8: physics system 3 is also collision object 2's"
    f = nif.parse(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), children=[two_body_blob()]))
    cases["two bodies"] = f, "collision object 6: physics system 7 holds 2 bodies, not 1"
    return cases


def transform_cases():
    """{name: (NifFile, error)}. Transforms composed for a box that the engine does not apply as the oracle did."""
    cases = {}
    for name, av, error in (("root scale 0", {"scale": 0.0}, "block 0: scale 0.0 is not positive"),
                            ("root matrix 0", {"rot": (0,) * 9}, "block 0: matrix is not a rotation")):
        f = box_scene((8, 0, 0.5))                     # an offset box: both boxes shrank below MIN_EXTENT
        f.blocks[0] = root(**av)
        cases[name] = f, error
    f = box_scene()
    f.blocks[0] = root(controller=5)
    cases["root controller"] = f, "block 0: controller 5 can move its transform"
    f = box_scene()
    f.blocks[4] = f.blocks[4][:116] + struct.pack("<i", 5) + f.blocks[4][120:]
    cases["skinned geometry"] = f, "BSGeometry 4: skin 5 places it by bones"
    hull = convex_blob(*cube((1.6, -0.4, 0), (2.4, 0.4, 1)))      # mirrored onto the mesh at x = -2; Havok cannot
    f = nif.parse(nif_bytes((-2, 0, 0.5, 0.4, 0.4, 0.5), children=[(hull, (0, 0, 0), (-1, 0, 0, 0, 1, 0, 0, 0, 1))]))
    cases["mirrored collision node"] = f, "block 5: matrix is not a rotation"
    return cases


class CollisionBoundsOracleTests(unittest.TestCase):
    def assert_unreadable_cases(self, cases):
        for name, (f, error) in cases.items():
            report = oracle.audit(nif.serialize(f), path=f"{name}.nif")
            self.assertIn("unreadable", report["flags"], msg=name)
            self.assertTrue(any(e.startswith(error) for e in report["errors"]), msg=(name, report["errors"]))
            self.assertTrue(oracle.failed([report]), msg=name)
            json.dumps(report, allow_nan=False)

    def test_matching_box_is_clean(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        report = oracle.audit(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box), path="match.nif")
        self.assertEqual(report["flags"], [])
        self.assertEqual(report["collision"]["bodies"], 1)
        self.assertEqual(report["collision"]["per_body"][0]["shape"], "hknpBoxShape")

    def test_missing_collision_is_flagged(self):
        report = oracle.audit(nif_bytes((0, 0, 1, 1, 1, 1)), path="empty.nif")
        self.assertEqual(report["flags"], ["missing"])
        self.assertEqual(report["collision"]["bodies"], 0)

    def test_tiny_collision_is_much_smaller(self):
        tiny = sfcollision.box_blob(fake_template(), (0, 0, 0.01), (0.02, 0.02, 0.01))
        report = oracle.audit(nif_bytes((0, 0, 1, 2, 2, 2), tiny))
        self.assertIn("much_smaller", report["flags"])

    def test_collision_short_on_any_mesh_axis_is_much_smaller(self):
        # Only the longest axis was compared: a 10 x 10 x 1 m mesh on a centred 10 x 0.1 x 1 m box was clean.
        thin = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (5, 0.05, 0.5))
        report = oracle.audit(nif_bytes((0, 0, 0.5, 5, 5, 0.5), thin), path="thin.nif")
        self.assertEqual(report["flags"], ["much_smaller"])
        full = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (5, 5, 0.5))
        self.assertEqual(oracle.audit(nif_bytes((0, 0, 0.5, 5, 5, 0.5), full))["flags"], [])
        plane = sfcollision.box_blob(fake_template(), (0, 0, 0), (5, 5, 0.001))    # a 2 cm mesh axis is still ignored
        self.assertEqual(oracle.audit(nif_bytes((0, 0, 0, 5, 5, 0.01), plane))["flags"], [])

    def test_offset_collision_is_flagged(self):
        far = sfcollision.box_blob(fake_template(), (8, 0, 0.5), (0.4, 0.4, 0.5))
        report = oracle.audit(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), far))
        self.assertIn("offset", report["flags"])

    def test_refr_scale_scales_printed_bounds_not_the_ratio(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        a = oracle.audit(data, scale=1.0)
        b = oracle.audit(data, scale=0.75)
        self.assertEqual(a["flags"], [])
        self.assertEqual(b["flags"], [])
        self.assertAlmostEqual(b["mesh"]["extent"][0], 0.75 * a["mesh"]["extent"][0], places=4)
        self.assertAlmostEqual(b["collision"]["extent"][2], 0.75 * a["collision"]["extent"][2], places=4)

    def test_three_native_bodies_union(self):
        v, f = cube((0, 0, 0), (1, 1, 1))
        blobs = [convex_blob(v, f), convex_blob(*cube((2, 0, 0), (3, 1, 1))),
                 convex_blob(*cube((0, 0, 4), (1, 1, 5)))]
        report = oracle.audit(nif_bytes((1.5, 0.5, 2.5, 1.5, 0.5, 2.5), children=blobs))
        self.assertEqual(report["collision"]["bodies"], 3)
        self.assertEqual(report["collision"]["min"][0], 0.0)
        self.assertEqual(report["collision"]["max"][2], 5.0)
        self.assertEqual(report["flags"], [])

    def test_compressed_mesh_body_is_read_via_sfbodies(self):
        packed = [(0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 100, 0)]
        blob = mesh_blob(packed, [(0, 1, 2, 3)], section_off=(0, 0, 0))
        report = oracle.audit(nif_bytes((0.5, 0.5, 0.0, 0.5, 0.5, 0.01), children=[blob]))
        self.assertEqual(report["collision"]["bodies"], 1)
        self.assertEqual(report["collision"]["per_body"][0]["shape"], "hknpCompressedMeshShape")
        self.assertEqual(report["collision"]["min"][:2], [0.0, 0.0])
        self.assertEqual(report["collision"]["max"][:2], [1.0, 1.0])

    def test_sfcollision_rejects_compressed_mesh_tagfile(self):
        blob = mesh_blob([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2, 2)])
        with self.assertRaises(sfcollision.CollisionError):
            sfcollision.check_template(blob)
        self.assertIn(b"hknpCompressedMeshShape", blob)

    def test_fo4collision_rejects_starfield_box_blob(self):
        blob = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        self.assertEqual(blob[:8], b"\x00\x00\x18\x18TAG0")
        center, half = sfcollision.read_box(blob)
        self.assertAlmostEqual(center[2], 0.5, places=5)
        self.assertAlmostEqual(half[0], 0.4, places=5)
        with self.assertRaises(fo4collision.hkpackfile.PackfileError) as ctx:
            fo4collision.decode(blob)
        self.assertIn("packfile", str(ctx.exception).lower())
        ev = oracle.research_box_vs_packfile(blob)
        self.assertIsInstance(ev["sfcollision"], list)
        self.assertTrue(str(ev["fo4collision"]).startswith("PackfileError"))

    def test_unreadable_blob_is_flagged(self):
        report = oracle.audit(nif_bytes((0, 0, 1, 1, 1, 1), collision=b"not-havok"))
        self.assertIn("unreadable", report["flags"])

    def test_cli_manifest_and_scale(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            model = staging / "meshes" / "roof" / "hatch.nif"
            model.parent.mkdir(parents=True)
            model.write_bytes(data)
            manifest = staging / "manifest.json"
            manifest.write_text(json.dumps({"items": [{"model": "roof/hatch.nif", "scale": 0.75}]}), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = oracle.main(["--manifest", str(manifest), "--staging", str(staging)])
        self.assertEqual(code, 0)

    def test_cli_flags_exit_1(self):
        data = nif_bytes((0, 0, 1, 1, 1, 1))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.nif"
            path.write_bytes(data)
            with redirect_stdout(io.StringIO()):
                code = oracle.main([str(path)])
        self.assertEqual(code, 1)

    def test_matching_body_plus_unreadable_sibling_is_unreadable(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        report = oracle.audit(
            nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box, children=[b"not-havok"]),
            path="partial.nif")
        self.assertIn("unreadable", report["flags"])
        self.assertGreaterEqual(report["collision"]["bodies"], 1)
        self.assertTrue(report.get("errors"))
        self.assertIn("unreadable", oracle.failed([report])[0]["flags"])

    def test_collision_only_nif_is_unassessed(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif.serialize(sfnif.build_static_nif(b"Prop", [], collision_blob=box))
        report = oracle.audit(data, path="collision-only.nif")
        self.assertIn("no_mesh", report["flags"])
        self.assertIsNone(report["mesh"])
        self.assertEqual(report["collision"]["bodies"], 1)
        self.assertTrue(oracle.failed([report]))

    def test_nonfinite_scale_is_rejected(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        for scale in (float("nan"), float("inf"), float("-inf")):
            report = oracle.audit(data, scale=scale, path="scale.nif")
            self.assertIn("unreadable", report["flags"], msg=scale)
            self.assertIsNone(report["scale"])
            payload = json.dumps(report, allow_nan=False)
            self.assertNotIn("NaN", payload)
            self.assertNotIn("Infinity", payload)

    def test_malformed_manifest_entries_are_reported(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            model = staging / "meshes" / "roof" / "hatch.nif"
            model.parent.mkdir(parents=True)
            model.write_bytes(data)
            reports = oracle.audit_manifest(
                {"items": [
                    {"model": "roof/hatch.nif"},
                    None,
                    {"source": "lost.nif"},
                ]},
                staging)
        self.assertEqual(len(reports), 3)
        self.assertEqual(reports[0]["flags"], [])
        self.assertIn("unreadable", reports[1]["flags"])
        self.assertIn("unreadable", reports[2]["flags"])
        self.assertEqual(len(oracle.failed(reports)), 2)

    def test_invalid_collision_target_is_unreadable(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        f = nif.parse(data)
        for i, block in enumerate(f.blocks):
            if f.type_of(i) == "bhkNPCollisionObject":
                target, flags, phys, extra = struct.unpack_from("<iHiI", block, 0)
                f.blocks[i] = struct.pack("<iHiI", -1, flags, phys, extra)
                break
        else:
            self.fail("no collision object in fixture")
        report = oracle.audit(nif.serialize(f), path="bad-target.nif")
        self.assertIn("unreadable", report["flags"])
        self.assertTrue(report.get("errors"))
        self.assertTrue(any("invalid target" in e for e in report["errors"]))
        self.assertEqual(report["collision"]["bodies"], 0)
        self.assertTrue(oracle.failed([report]))

    def test_collision_target_that_is_not_a_scene_object_is_unreadable(self):
        # The range check let a target on any block through: one whose bytes read as an identity transform placed the
        # box like the root and reported clean. BSFurnitureMarkerNode ends in "Node" but is NiExtraData.
        f = box_scene()
        targets = {t: f.add_block(t, node(coll=2)) for t in ("BogusBlock", "BSFurnitureMarkerNode", "NiNode")}
        targets["BSGeometry"] = 4
        geometry = f.blocks[4]
        for name, target in targets.items():
            control = name in ("NiNode", "BSGeometry")     # identity scene objects that name the object: clean
            f.blocks[0] = root((4, target) if name == "NiNode" else (4,), coll=-1 if control else 2)
            f.blocks[4] = geometry[:72] + struct.pack("<i", 2) + geometry[76:] if name == "BSGeometry" else geometry
            f.blocks[2] = struct.pack("<iHiI", target, 0x80, 3, 0)
            report = oracle.audit(nif.serialize(f), path=f"{name}-target.nif")
            if control:
                self.assertEqual(report["flags"], [], msg=name)
                continue
            self.assertIn("unreadable", report["flags"], msg=name)
            self.assertTrue(any("not a scene object" in e for e in report["errors"]), msg=name)
            self.assertEqual(report["collision"]["bodies"], 0, msg=name)
            self.assertTrue(oracle.failed([report]), msg=name)

    def test_truncated_bsgeometry_is_unreadable(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        f = nif.parse(data)
        for i, block in enumerate(f.blocks):
            if f.type_of(i) == "BSGeometry":
                f.blocks[i] = block[:8]
                break
        else:
            self.fail("no BSGeometry in fixture")
        report = oracle.audit(nif.serialize(f), path="truncated-geom.nif")
        self.assertIn("unreadable", report["flags"])
        self.assertTrue(report.get("errors"))
        self.assertIsNone(report["mesh"])
        self.assertTrue(oracle.failed([report]))
        payload = json.dumps(report, allow_nan=False)
        self.assertNotIn("Traceback", payload)

    def test_truncated_collision_object_header_is_unreadable(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        for size in (0, 4, 9):
            report = oracle.audit(truncate_block(data, "bhkNPCollisionObject", size), path="short-npco.nif")
            self.assertIn("unreadable", report["flags"], msg=size)
            self.assertTrue(any("truncated header" in e for e in report["errors"]), msg=size)
            self.assertEqual(report["collision"]["bodies"], 0)
            self.assertTrue(oracle.failed([report]))
            json.dumps(report, allow_nan=False)

    def test_truncated_physics_system_is_unreadable(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        for size in (0, 3):
            report = oracle.audit(truncate_block(data, "bhkPhysicsSystem", size), path="short-phys.nif")
            self.assertIn("unreadable", report["flags"], msg=size)
            self.assertTrue(any("truncated physics system" in e for e in report["errors"]), msg=size)
            self.assertEqual(report["collision"]["bodies"], 0)
            self.assertTrue(oracle.failed([report]))
            json.dumps(report, allow_nan=False)

    def test_truncated_header_keeps_sibling_bodies(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        hull = convex_blob(*cube((-0.4, -0.4, 0), (0.4, 0.4, 1)))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box, children=[hull])
        for block_type, size in (("bhkNPCollisionObject", 6), ("bhkPhysicsSystem", 2)):
            report = oracle.audit(truncate_block(data, block_type, size, nth=1), path="partial.nif")
            self.assertIn("unreadable", report["flags"], msg=block_type)
            self.assertEqual(len(report["errors"]), 1, msg=block_type)
            self.assertEqual(report["collision"]["bodies"], 1, msg=block_type)
            self.assertEqual(report["collision"]["per_body"][0]["shape"], "hknpBoxShape")

    def test_truncated_collision_target_node_is_unreadable(self):
        # The child collision object's target NiNode is cut below its transform, so placing it
        # raises inside collision_bodies; the audit boundary turns that into an unreadable report.
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        hull = convex_blob(*cube((-0.4, -0.4, 0), (0.4, 0.4, 1)))
        data = truncate_block(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box, children=[hull]),
                              "NiNode", 8, nth=1)
        report = oracle.audit(data, path="short-target.nif")
        self.assertIn("unreadable", report["flags"])
        self.assertTrue(any(e.startswith("collision: ") for e in report["errors"]))
        self.assertIsNotNone(report["mesh"])
        self.assertTrue(oracle.failed([report]))
        json.dumps(report, allow_nan=False)

    def test_malformed_node_child_table_is_unreadable(self):
        # nif.node_children reads a child table it cannot use as childless (and drops refs past the block list), so the
        # geometry and the collision node under the translated root both lost its transform alike: the bounds still
        # matched and the report was clean.
        hull = convex_blob(*cube((-0.4, -0.4, 0), (0.4, 0.4, 1)))
        f = nif.parse(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), children=[hull]))
        root = f.blocks[0]                                 # build_static_nif root: translation @20, child count @76
        root = root[:20] + struct.pack("<3f", 5, 0, 0) + root[32:]
        count, = struct.unpack_from("<I", root, 76)
        f.blocks[0] = root
        report = oracle.audit(nif.serialize(f), path="translated.nif")
        self.assertEqual(report["flags"], [])                                 # control: both sides at x = 5
        self.assertEqual((report["mesh"]["center"][0], report["collision"]["center"][0]), (5.0, 5.0))
        past = range(len(f.blocks), len(f.blocks) + count)
        cases = {"count past block": root[:76] + struct.pack("<I", count + 1) + root[80:],
                 "refs past block list": root[:80] + struct.pack(f"<{count}i", *past),
                 "cut before count": root[:76]}
        for name, block in cases.items():
            f.blocks[0] = block
            report = oracle.audit(nif.serialize(f), path=f"{name}.nif")
            self.assertIn("unreadable", report["flags"], msg=name)
            self.assertTrue(any(e.startswith("node 0: ") for e in report["errors"]), msg=(name, report.get("errors")))
            self.assertTrue(oracle.failed([report]), msg=name)
            json.dumps(report, allow_nan=False)

    def test_scene_graph_that_is_not_a_plain_tree_is_unreadable(self):
        self.assertEqual(oracle.audit(nif.serialize(box_scene()))["flags"], [])
        f = box_scene()                                # the x = 5 node most cases hid puts the geometry off the box
        f.blocks[0] = root((f.add_block("NiNode", node((4,), t=(5, 0, 0))),))
        self.assertEqual(oracle.audit(nif.serialize(f))["flags"], ["offset"])
        self.assert_unreadable_cases(scene_graph_cases())

    def test_collision_object_not_named_by_its_target_is_unreadable(self):
        f = box_scene()                                # control: an attached child node names the object it targets
        n = f.add_block("NiNode", node(coll=2))
        f.blocks[0] = root((4, n), coll=-1)
        f.blocks[2] = struct.pack("<iHiI", n, 0x80, 3, 0)
        self.assertEqual(oracle.audit(nif.serialize(f))["flags"], [])
        self.assert_unreadable_cases(collision_ownership_cases())

    def test_collision_body_selection_and_block_sizes_are_unreadable(self):
        self.assert_unreadable_cases(collision_body_cases())

    def test_degenerate_or_animated_transform_on_a_box_path_is_unreadable(self):
        self.assertEqual(oracle.audit(nif.serialize(box_scene((8, 0, 0.5))))["flags"], ["offset"])
        hull = convex_blob(*cube((1.6, -0.4, 0), (2.4, 0.4, 1)))
        self.assertEqual(oracle.audit(nif_bytes((-2, 0, 0.5, 0.4, 0.4, 0.5), children=[hull]))["flags"], ["offset"])
        f = box_scene()                                # control: a root turned 90 degrees about z, scaled 2 and moved
        f.blocks[0] = root(t=(1, 2, 3), rot=(0, -1, 0, 1, 0, 0, 0, 0, 1), scale=2.0)
        self.assertEqual(oracle.audit(nif.serialize(f))["flags"], [])
        self.assert_unreadable_cases(transform_cases())

    def test_cli_truncated_collision_headers_emit_json(self):
        script = Path(_ROOT) / "scripts" / "oracles" / "collision_bounds.py"
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        cases = {"short-npco.nif": truncate_block(data, "bhkNPCollisionObject", 6),
                 "short-phys.nif": truncate_block(data, "bhkPhysicsSystem", 2)}
        with tempfile.TemporaryDirectory() as tmp:
            for name, payload in cases.items():
                path = Path(tmp) / name
                path.write_bytes(payload)
                proc = subprocess.run([sys.executable, "-I", str(script), str(path)],
                                      capture_output=True, text=True, cwd=tmp)
                self.assertEqual(proc.returncode, 1, msg=name)
                self.assertNotIn("Traceback", proc.stderr, msg=name)
                out = json.loads(proc.stdout)
                self.assertEqual(out["flagged"], 1, msg=name)
                self.assertIn("unreadable", out["reports"][0]["flags"], msg=name)
                self.assertTrue(out["reports"][0].get("errors"), msg=name)

    def test_physics_system_shorter_than_its_declared_blob_is_unreadable(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        report = oracle.audit(truncate_block(data, "bhkPhysicsSystem", 4 + 100), path="short-blob.nif")
        self.assertIn("unreadable", report["flags"])
        self.assertTrue(any("truncated physics system" in e and f"of {len(box)} blob bytes" in e
                            for e in report["errors"]), msg=report["errors"])
        self.assertEqual(report["collision"]["bodies"], 0)

    def test_malformed_tagfiles_are_per_object_unreadable(self):
        # Each child blob broke out of collision_bodies (KeyError, RecursionError, OverflowError) or never returned
        # (a type parent cycle in size_of / all_fields); now each is one error and the good box beside it still decodes.
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        cases = {"no sections": _sec(b"TAG0", b"", leaf=False),
                 "self-referential template": raw_tagfile(b"T\0tT\0", _v(2) + _v(0) + _v(1) + _v(1) + _v(1), b"",
                                                          items=[(1, 0, 1)]),
                 "size_of parent cycle": own_parent_blob(BODY, 0),
                 "all_fields parent cycle": own_parent_blob(PSD, 16),
                 "offset past ssize_t": huge_offset_blob()}
        for name, blob in cases.items():
            report = oracle.audit(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box, children=[blob]), path=f"{name}.nif")
            self.assertIn("unreadable", report["flags"], msg=name)
            self.assertEqual(len(report["errors"]), 1, msg=(name, report["errors"]))
            self.assertTrue(report["errors"][0].startswith("collision object "), msg=name)
            self.assertEqual(report["collision"]["bodies"], 1, msg=name)
            self.assertTrue(oracle.failed([report]), msg=name)
            json.dumps(report, allow_nan=False)

    def test_nonfinite_points_are_unreadable_wherever_they_sit(self):
        # min / max skip a NaN that is not the first value, so a NaN second shape, a NaN later hull vertex and a NaN
        # body position (abs(NaN) > 1e-6 is False, so it looked like identity) all used to pass clean.
        nan = float("nan")
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        two = nif.serialize(sfnif.build_static_nif(
            b"Prop", [shape((0, 0, 0.5, 0.4, 0.4, 0.5)), shape((nan, 0, 0.5, 0.4, 0.4, 0.5), b"Prop:1")],
            collision_blob=box))
        v, f = cube((-0.4, -0.4, 0), (0.4, 0.4, 1))
        v[5] = (nan, v[5][1], v[5][2])
        bad_corner = bytearray(box)
        struct.pack_into("<f", bad_corner, 592 + 12 * 1, nan)   # corner 1 of the box template's 8
        cases = {"second shape": two,
                 "box corner": nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), bytes(bad_corner)),
                 "hull vertex": nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), children=[convex_blob(v, f)]),
                 "body position": nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), children=[
                     convex_blob(*cube((-0.4, -0.4, 0), (0.4, 0.4, 1)), pos=(nan, 0, 0))])}
        for name, data in cases.items():
            report = oracle.audit(data, path=f"{name}.nif")
            self.assertIn("unreadable", report["flags"], msg=name)
            self.assertTrue(report.get("errors"), msg=name)
            self.assertTrue(oracle.failed([report]), msg=name)
            json.dumps(report, allow_nan=False)

    def test_body_orientation_that_is_not_a_unit_quaternion_is_unreadable(self):
        # (0, 0, 0, 0) and (0, 0, 0, 2) passed the identity test, so a body with no valid orientation matched the mesh.
        hull = cube((-0.4, -0.4, 0), (0.4, 0.4, 1))
        for quat in ((0, 0, 0, 0), (0, 0, 0, 2)):
            report = oracle.audit(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), children=[convex_blob(*hull, quat=quat)]),
                                  path="quat.nif")
            self.assertIn("unreadable", report["flags"], msg=quat)
            self.assertTrue(any("not a unit quaternion" in e for e in report["errors"]), msg=report["errors"])
            self.assertTrue(oracle.failed([report]), msg=quat)
            json.dumps(report, allow_nan=False)
        clean = oracle.audit(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), children=[convex_blob(*hull)]))
        self.assertEqual(clean["flags"], [])

    def test_huge_finite_scale_never_overflows(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        far = sfcollision.box_blob(fake_template(), (5, 0, 0.5), (0.4, 0.4, 0.5))
        offset = oracle.audit(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), far), scale=1e300)
        self.assertEqual(offset["flags"], ["offset"])                    # (5e299) ** 2 raised OverflowError
        wide = sfcollision.box_blob(fake_template(), (0, 0, 0), (1, 1, 1))
        report = oracle.audit(nif_bytes((0, 0, 0, 1, 1, 1), wide), scale=1e308)
        self.assertIn("unreadable", report["flags"])                     # extent 2e308: aabb_info raised ValueError
        self.assertIn("nonfinite mesh bounds", report["errors"])
        left = sfcollision.box_blob(fake_template(), (-0.75, 0, 0), (0.25, 0.25, 0.25))
        right = convex_blob(*cube((0.5, -0.25, -0.25), (1, 0.25, 0.25)))
        report = oracle.audit(nif_bytes((0, 0, 0, 0.1, 0.1, 0.1), left, children=[right]), scale=1e308)
        self.assertIn("unreadable", report["flags"])                     # each body fits; their union does not
        self.assertEqual(report["errors"], ["collision: nonfinite combined bounds"])
        self.assertEqual(report["collision"]["bodies"], 2)
        self.assertIsNone(report["collision"]["min"])
        for r in (offset, report):
            json.dumps(r, allow_nan=False)

    def test_zero_negative_and_overflowing_scale_is_rejected(self):
        tiny = sfcollision.box_blob(fake_template(), (0, 0, 0.01), (0.02, 0.02, 0.01))
        data = nif_bytes((0, 0, 1, 2, 2, 2), tiny)
        for scale in (0, 0.0, -0.0, -1.0, 10 ** 400):       # 0 hid much_smaller; 10**400 raised OverflowError
            report = oracle.audit(data, scale=scale, path="scale.nif")
            self.assertEqual(report["flags"], ["unreadable"], msg=scale)
            self.assertIsNone(report["scale"])
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "meshes" / "a.nif"
            model.parent.mkdir(parents=True)
            model.write_bytes(data)
            reports = oracle.audit_manifest({"items": [{"model": "a.nif", "scale": 10 ** 400},
                                                       {"model": "a.nif", "scale": 0}]}, Path(tmp))
        self.assertEqual([r["flags"] for r in reports], [["unreadable"], ["unreadable"]])

    def test_cli_malformed_manifest_json_and_huge_scale_emit_json(self):
        script = Path(_ROOT) / "scripts" / "oracles" / "collision_bounds.py"
        far = sfcollision.box_blob(fake_template(), (5, 0, 0.5), (0.4, 0.4, 0.5))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "meshes").mkdir()
            (root / "meshes" / "far.nif").write_bytes(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), far))
            manifests = {"digits": '{"items": [{"model": "far.nif", "scale": ' + "1" * 5000 + "}]}",
                         "nesting": '{"items": ' + "[" * 100000 + "]" * 100000 + "}",
                         "int scale": '{"items": [{"model": "far.nif", "scale": 1' + "0" * 400 + "}]}"}
            runs = {"huge --scale": [str(root / "meshes" / "far.nif"), "--scale", "1e300"]}
            for name, text in manifests.items():
                (root / f"{name}.json").write_text(text, encoding="utf-8")
                runs[name] = ["--manifest", str(root / f"{name}.json"), "--staging", str(root)]
            for name, args in runs.items():
                proc = subprocess.run([sys.executable, "-I", str(script), *args],
                                      capture_output=True, text=True, cwd=tmp)
                self.assertEqual(proc.returncode, 1, msg=name)
                self.assertNotIn("Traceback", proc.stderr, msg=name)
                out = json.loads(proc.stdout)
                self.assertEqual(out["flagged"], 1, msg=name)
                flag = "offset" if name == "huge --scale" else "unreadable"
                self.assertIn(flag, out["reports"][0]["flags"], msg=name)

    def test_cli_codex_fail_open_controls(self):
        script = Path(_ROOT) / "scripts" / "oracles" / "collision_bounds.py"
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        match = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        sibling = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box, children=[b"not-havok"])
        collision_only = nif.serialize(sfnif.build_static_nif(b"Prop", [], collision_blob=box))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "match.nif").write_bytes(match)
            (root / "sibling.nif").write_bytes(sibling)
            (root / "collision-only.nif").write_bytes(collision_only)
            staging = root / "stage"
            model = staging / "meshes" / "roof" / "hatch.nif"
            model.parent.mkdir(parents=True)
            model.write_bytes(match)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "items": [
                    {"model": "roof/hatch.nif"},
                    None,
                    {"source": "lost.nif"},
                ]}), encoding="utf-8")

            def run(*args):
                return subprocess.run(
                    [sys.executable, "-I", str(script), *args],
                    capture_output=True, text=True, cwd=str(root))

            sibling_proc = run(str(root / "sibling.nif"))
            self.assertNotEqual(sibling_proc.returncode, 0)
            sibling_out = json.loads(sibling_proc.stdout)
            self.assertIn("unreadable", sibling_out["reports"][0]["flags"])
            self.assertGreaterEqual(sibling_out["reports"][0]["collision"]["bodies"], 1)
            self.assertTrue(sibling_out["reports"][0].get("errors"))

            meshless = run(str(root / "collision-only.nif"))
            self.assertNotEqual(meshless.returncode, 0)
            meshless_out = json.loads(meshless.stdout)
            self.assertIn("no_mesh", meshless_out["reports"][0]["flags"])
            self.assertIsNone(meshless_out["reports"][0]["mesh"])

            for flag in ("nan", "inf", "-inf"):
                proc = run("--scale", flag, str(root / "match.nif"))
                self.assertNotEqual(proc.returncode, 0, msg=flag)
                self.assertNotIn("NaN", proc.stdout)
                self.assertNotIn("Infinity", proc.stdout)

            man = run("--manifest", str(manifest), "--staging", str(staging))
            self.assertNotEqual(man.returncode, 0)
            man_out = json.loads(man.stdout)
            self.assertEqual(man_out["models"], 3)
            self.assertGreaterEqual(man_out["flagged"], 2)
            self.assertEqual(man_out["reports"][0]["flags"], [])
            self.assertIn("unreadable", man_out["reports"][1]["flags"])
            self.assertIn("unreadable", man_out["reports"][2]["flags"])

            ok = run(str(root / "match.nif"))
            self.assertEqual(ok.returncode, 0)
            ok_out = json.loads(ok.stdout)
            self.assertEqual(ok_out["flagged"], 0)
            json.dumps(ok_out, allow_nan=False)

    def test_flags_do_not_depend_on_refr_scale(self):
        # MIN_EXTENT gated the scaled boxes: at scale 0.02 the 8 m offset box, and at 0.01 the 4 cm box on a 4 m mesh,
        # had every axis under 5 cm and were clean (a 4 m x 4 cm pipe on a 6 mm hull was much_smaller from scale 2),
        # though a uniform scale about the origin moves both boxes alike.
        far = nif.serialize(box_scene((8, 0, 0.5)))
        tiny = nif_bytes((0, 0, 1, 2, 2, 2), sfcollision.box_blob(fake_template(), (0, 0, 0.01), (0.02, 0.02, 0.01)))
        pipe = nif_bytes((0, 0, 0, 2, 0.02, 0.02), children=[convex_blob(*cube((-2, -0.003, -0.003), (2, 0.003, 0.003)))])
        for scale in (1.0, 0.02, 0.01, 2.0, 100.0):
            self.assertEqual(oracle.audit(far, scale=scale)["flags"], ["offset"], msg=scale)
            self.assertEqual(oracle.audit(tiny, scale=scale)["flags"], ["much_smaller"], msg=scale)
            self.assertEqual(oracle.audit(pipe, scale=scale)["flags"], [], msg=scale)                 # control
            self.assertEqual(oracle.audit(nif.serialize(box_scene()), scale=scale)["flags"], [], msg=scale)
        report = oracle.audit(far, scale=0.02)
        self.assertEqual((report["mesh"]["extent"], report["collision"]["center"]), ([0.016, 0.016, 0.02], [0.16, 0.0, 0.01]))
        script = Path(_ROOT) / "scripts" / "oracles" / "collision_bounds.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "meshes").mkdir()
            (root / "meshes" / "far.nif").write_bytes(far)
            (root / "meshes" / "tiny.nif").write_bytes(tiny)
            reports = oracle.audit_manifest({"items": [{"model": "far.nif", "scale": 0.02},
                                                       {"model": "tiny.nif", "scale": 0.01}]}, root)
            self.assertEqual([r["flags"] for r in reports], [["offset"], ["much_smaller"]])
            proc = subprocess.run([sys.executable, "-I", str(script), str(root / "meshes" / "far.nif"), "--scale", "0.02"],
                                  capture_output=True, text=True, cwd=tmp)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["reports"][0]["flags"], ["offset"])

    def test_small_item_with_its_collision_off_it_is_offset(self):
        # offset (the no-overlap test too) was skipped on a mesh diagonal under 5 cm: a 3 x 3 x 1 cm item's body 1 m or
        # 100 m away, or a hull 0.7 m away, was clean.
        mesh = (0, 0, 0.005, 0.015, 0.015, 0.005)
        far = {x: sfcollision.box_blob(fake_template(), (x, 0, 0.005), (0.015, 0.015, 0.005)) for x in (0.01, 1, 100)}
        self.assertEqual(oracle.audit(nif_bytes(mesh, far[0.01]))["flags"], [])     # control: 1 cm over, overlapping
        hull = convex_blob(*cube((0.5, 0.5, 0), (0.53, 0.53, 0.01)))
        for name, data in (("box 1 m away", nif_bytes(mesh, far[1])), ("box 100 m away", nif_bytes(mesh, far[100])),
                           ("hull 0.7 m away", nif_bytes(mesh, children=[hull]))):
            self.assertEqual(oracle.audit(data)["flags"], ["offset"], msg=name)

    def test_collision_beside_the_mesh_on_a_thin_axis_is_offset(self):
        # offset compared the centres with the 3-D diagonal and took boxes that only touch as overlapping: a slab's box
        # lifted by its thickness, a wall's box beside it and a 4 m block standing on a floor were clean.
        cases = {"slab, box lifted by its thickness": ((0, 0, 0.5, 5, 5, 0.5), (0, 0, 1.5), (5, 5, 0.5)),
                 "wall, box beside it": ((0, 0, 1.5, 5, 0.15, 1.5), (0, 0.3, 1.5), (5, 0.15, 1.5)),
                 "floor, tall box on it": ((0, 0, 0.1, 5, 5, 0.1), (0, 0, 2.2), (5, 5, 2.0))}
        for name, (mesh, centre, half) in cases.items():
            report = oracle.audit(nif_bytes(mesh, sfcollision.box_blob(fake_template(), centre, half)))
            self.assertEqual(report["flags"], ["offset"], msg=name)
        lifted = sfcollision.box_blob(fake_template(), (0, 0, 1.0), (5, 5, 0.5))     # control: half its thickness
        self.assertEqual(oracle.audit(nif_bytes((0, 0, 0.5, 5, 5, 0.5), lifted))["flags"], [])

    def test_cli_rejects_a_nif_and_a_manifest_together(self):
        # main() took the --manifest branch and never read the NIF: an offset far.nif beside a clean manifest exited 0.
        script = Path(_ROOT) / "scripts" / "oracles" / "collision_bounds.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "far.nif").write_bytes(nif.serialize(box_scene((8, 0, 0.5))))
            (root / "stage" / "meshes").mkdir(parents=True)
            (root / "stage" / "meshes" / "ok.nif").write_bytes(nif.serialize(box_scene()))
            (root / "m.json").write_text(json.dumps({"items": [{"model": "ok.nif"}]}), encoding="utf-8")
            manifest = ["--manifest", str(root / "m.json"), "--staging", str(root / "stage")]

            def run(*args):
                return subprocess.run([sys.executable, "-I", str(script), *args], capture_output=True, text=True, cwd=tmp)
            self.assertEqual((run(str(root / "far.nif")).returncode, run(*manifest).returncode), (1, 0))    # control
            both = run(str(root / "far.nif"), *manifest)
            self.assertEqual(both.returncode, 2)
            self.assertIn("not both", both.stderr)

    def test_geometry_that_draws_nothing_is_left_out(self):
        # mesh_aabb took every BSGeometry.box: a piece with no mesh in any LOD slot, over the collision, hid that the
        # collision missed the only drawn piece, and a NIF that draws nothing was clean, not no_mesh.
        box = sfcollision.box_blob(fake_template(), (6, 0, 0.5), (2.4, 0.4, 0.5))     # over the second piece only
        f = two_piece_scene((4, 0, 0.5, 4.4, 0.4, 0.5), box)
        self.assertEqual(oracle.audit(nif.serialize(f))["flags"], [])                 # control: both pieces drawn
        lod1 = sfnif.parse_bsgeometry(f.blocks[7]).meshes[0]
        for name, meshes, flags in (("no mesh", [None] * 4, ["offset"]),
                                    ("0-vertex mesh", [dataclasses.replace(lod1, num_verts=0), None, None, None],
                                     ["offset"]),
                                    ("mesh in LOD1 only", [None, lod1, None, None], [])):
            geometry(f, 7, meshes=meshes)
            self.assertEqual(oracle.audit(nif.serialize(f))["flags"], flags, msg=name)
        f = box_scene()
        geometry(f, 4, meshes=[None] * 4)
        report = oracle.audit(nif.serialize(f))
        self.assertEqual((report["flags"], report["mesh"]), (["no_mesh"], None))

    def test_drawn_geometry_with_unset_bounds_is_unreadable(self):
        # An all-zero box was skipped as "no geometry" though the piece still draws its mesh: collision covering only the
        # other piece was clean.
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))     # over the first piece only
        f = two_piece_scene((5, 0, 0.5, 0.4, 0.4, 0.5), box)
        self.assertEqual(oracle.audit(nif.serialize(f))["flags"], ["much_smaller"])   # control: both pieces measured
        lod0 = sfnif.parse_bsgeometry(f.blocks[7]).meshes[0]
        for name, fields in (("box", {"box": (0,) * 6}), ("box and sphere", {"box": (0,) * 6, "sphere": (0,) * 4}),
                             ("box, mesh in LOD1", {"box": (0,) * 6, "meshes": [None, lod0, None, None]})):
            g = two_piece_scene((5, 0, 0.5, 0.4, 0.4, 0.5), box)
            geometry(g, 7, **fields)
            report = oracle.audit(nif.serialize(g))
            self.assertIn("unreadable", report["flags"], msg=name)
            self.assertIn("BSGeometry 7: draws a mesh but its bounds are not set", report["errors"], msg=name)
        geometry(f, 7, box=(0,) * 6, meshes=[None] * 4)                               # control: draws nothing
        self.assertEqual(oracle.audit(nif.serialize(f))["flags"], [])

    def test_compressed_mesh_the_decoder_rejects_is_unreadable(self):
        # sfbodies reads FO4's primitive rule: primitives Starfield's decoder asserts on (special types other than 3 / 4,
        # an index past the section's vertices) read as triangles over the quad or were skipped, and a mesh without a
        # SIMD tree or key was read as well; each report was clean.
        packed = [(0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 100, 0)]
        mesh = (0.5, 0.5, 0.0, 0.5, 0.5, 0.01)
        self.assertEqual(oracle.audit(nif_bytes(mesh, children=[mesh_blob(packed, [(0, 1, 2, 3), (0, 2, 3, 3)])]))[
            "flags"], [])                                                             # control: a quad and a triangle
        cases = {"FO4 specials": mesh_blob(packed, [(0, 2, 2, 2), (3, 1, 1, 1)]),
                 "indices[1] == indices[3]": mesh_blob(packed, [(0, 1, 2, 1), (2, 3, 0, 3)]),
                 "index past the section": mesh_blob(packed, [(0, 1, 2, 3), (0, 1, 2, 200)]),
                 "no SIMD tree": mesh_blob(packed, [(0, 1, 2, 3)], has_simd=0),
                 "primitive without a SIMD key": mesh_blob(packed, [(0, 1, 2, 3), (0, 2, 3, 3)], keys=[0])}
        for name, blob in cases.items():
            report = oracle.audit(nif_bytes(mesh, children=[blob]))
            self.assertIn("unreadable", report["flags"], msg=name)
            self.assertTrue(any(e.startswith("collision object 6: compressed mesh ") for e in report["errors"]),
                            msg=(name, report["errors"]))

    def test_template_sized_blob_is_read_as_its_tagfile(self):
        # The 6,168-byte path checked the template's bytes and read the corners at 592 without parsing the tagfile, so
        # the body's pose and shape were never read: a box moved 50 m or turned off the wall, a body with no valid
        # orientation, a hull 8 m off, two bodies, or no tagfile at all read clean.
        wall = (0, 0, 1.5, 5, 0.15, 1.5)

        def on_body(pos=(0, 0, 0), quat=(0, 0, 0, 1), n=1):
            return sfcollision.box_blob(template_tagfile(lambda w, box: [(box, pos, quat)] * n), wall[:3], wall[3:])
        self.assertEqual(oracle.audit(nif_bytes(wall, on_body()))["flags"], [])      # control: the identity body
        h = math.sqrt(0.5)
        hull = template_tagfile(lambda w, box: [(add_convex(w, *cube((7.6, -0.4, 0), (8.4, 0.4, 1))), (0, 0, 0),
                                                 (0, 0, 0, 1))])
        cases = {"moved 50 m": (wall, on_body(pos=(50, 0, 0)), ["offset"]),
                 "turned 90 degrees about z": (wall, on_body(quat=(0, 0, h, h)), ["much_smaller"]),
                 "orientation 0": (wall, on_body(quat=(0, 0, 0, 0)), ["unreadable", "missing"]),
                 "orientation (0, 0, 0, 5)": (wall, on_body(quat=(0, 0, 0, 5)), ["unreadable", "missing"]),
                 "NaN position": (wall, on_body(pos=(math.nan, 0, 0)), ["unreadable", "missing"]),
                 "two bodies": (wall, on_body(n=2), ["unreadable", "missing"]),
                 "hull body 8 m off": ((0, 0, 0.5, 0.4, 0.4, 0.5),
                                       sfcollision.box_blob(hull, (0, 0, 0.5), (0.4, 0.4, 0.5)), ["offset"]),
                 "not a tagfile": (wall, sfcollision.box_blob(untagged_template(), wall[:3], wall[3:]),
                                   ["unreadable", "missing"])}
        for name, (mesh, blob, flags) in cases.items():
            sfcollision.check_template(blob)
            self.assertEqual(oracle.audit(nif_bytes(mesh, blob))["flags"], flags, msg=name)

    def test_node_subclasses_without_the_node_suffix_are_parents(self):
        # Only "...Node" child tables were read: a BSDamageStage or BSMasterParticleSystem (NiNode subclasses in nif.xml)
        # listing the geometry, or the collision node, a second time at x = 5 was never seen and the boxes matched.
        tails = {"BSDamageStage": bytes([0, 1, 0]), "BSMasterParticleSystem": struct.pack("<HI", 0, 0)}
        cases = {}
        for t, tail in tails.items():
            f = box_scene()
            f.blocks[0] = root((4, f.add_block(t, node((4,), t=(5, 0, 0)) + tail)))
            cases[t] = f, "block 4: listed as a child by nodes [0, 7]"
        f = box_scene()
        n = f.add_block("NiNode", node(coll=2))
        f.blocks[0] = root((4, n, f.add_block("BSDamageStage", node((n,), t=(5, 0, 0)) + tails["BSDamageStage"])), coll=-1)
        f.blocks[2] = struct.pack("<iHiI", n, 0x80, 3, 0)
        cases["collision node"] = f, "block 7: listed as a child by nodes [0, 8]"
        self.assert_unreadable_cases(cases)
        f = box_scene()                                # control: a particle system off every box path
        ps = f.add_block("NiParticleSystem", b"")
        f.blocks[0] = root((4, f.add_block("BSMasterParticleSystem", node((ps,)) + tails["BSMasterParticleSystem"])))
        self.assertEqual(oracle.audit(nif.serialize(f))["flags"], [])

    def test_controller_anywhere_is_unreadable(self):
        # Only the controller slots on a box's path were read, but a controller updates its own Target: one hung on a
        # sibling node or on the geometry's shader, or linked from nowhere, aimed at BSGeometry 4 left the report clean.
        self.assertEqual(oracle.audit(nif.serialize(box_scene()))["flags"], [])      # control
        cases = {}
        for slot in ("sibling node", "shader property", "nothing"):
            f = box_scene()
            interp = f.add_block("NiTransformInterpolator", struct.pack("<3f4ffi", 5, 0, 0, 1, 0, 0, 0, 1.0, -1))
            ctrl = f.add_block("NiTransformController", struct.pack("<iHffffii", -1, 0x48, 1, 0, 0, 0, 4, interp))
            if slot == "sibling node":
                f.blocks[0] = root((4, f.add_block("NiNode", node(controller=ctrl))))
            elif slot == "shader property":                # BSLightingShaderProperty: name, extra refs, controller
                f.blocks[6] = f.blocks[6][:8] + struct.pack("<i", ctrl)
            cases[slot] = f, "block 8: NiTransformController can animate the scene"
        self.assert_unreadable_cases(cases)


if __name__ == "__main__":
    unittest.main()
