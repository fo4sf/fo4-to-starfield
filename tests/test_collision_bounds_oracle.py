"""Synthetic tests for scripts/oracles/collision_bounds.py (no game assets)."""
import importlib.util
import io
import json
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
from fo4sf import fo4collision, nif, sfcollision, sfnif  # noqa: E402
from test_collision import fake_template
import test_sfbodies
from test_sfbodies import BODY, TagWriter, _sec, _v, add_body, body_types, cube, convex_blob, mesh_blob

spec = importlib.util.spec_from_file_location(
    "collision_bounds_oracle",
    Path(__file__).resolve().parents[1] / "scripts/oracles/collision_bounds.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


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


def raw_tagfile(tst, tna, tbdy):
    """TAG0 with hand-written type strings / names / bodies (TagWriter only writes well-formed types)."""
    types = _sec(b"TST1", tst) + _sec(b"TNA1", tna) + _sec(b"FST1", b"") + _sec(b"TBDY", tbdy)
    body = (_sec(b"SDKV", b"20190200") + _sec(b"DATA", bytes(16)) + _sec(b"TYPE", types, leaf=False)
            + _sec(b"INDX", _sec(b"ITEM", bytes(12)) + _sec(b"PTCH", b""), leaf=False))
    return _sec(b"TAG0", body, leaf=False)


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


class CollisionBoundsOracleTests(unittest.TestCase):
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
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        f = nif.parse(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box))
        av = struct.pack("<iIiI3f9ffiI", -1, 0, -1, 0xE, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1.0, -1, 0)
        targets = {t: f.add_block(t, av) for t in ("BogusBlock", "BSFurnitureMarkerNode", "NiNode")}
        targets["BSGeometry"] = 4
        npco = f.blocks[2]                                 # build_static_nif: the root's collision object
        for name, target in targets.items():
            f.blocks[2] = struct.pack("<i", target) + npco[4:]
            report = oracle.audit(nif.serialize(f), path=f"{name}-target.nif")
            if name in ("NiNode", "BSGeometry"):           # identity scene objects, like the root: clean controls
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
        body = BODY.encode() + b"\0"
        cases = {"no sections": _sec(b"TAG0", b"", leaf=False),
                 "self-referential template": raw_tagfile(b"T\0tT\0", _v(2) + _v(0) + _v(1) + _v(1) + _v(1), b""),
                 "size_of parent cycle": raw_tagfile(body, _v(2) + _v(0) + _v(0), _v(1) + _v(1) + _v(0)),
                 "all_fields parent cycle": raw_tagfile(body, _v(2) + _v(0) + _v(0),
                                                        _v(1) + _v(1) + _v(0x8) + _v(64) + _v(4)),
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


if __name__ == "__main__":
    unittest.main()
