"""Unit tests for src/fo4sf/ba2.py across BTDX versions 1, 2, 3, 7, and 8 (GNRL and DX10)."""
import os
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from ba2_fixture import general_archive, texture_archive  # noqa: E402
from fo4sf.ba2 import HEADER_EXTRA_BYTES, Ba2, Ba2Error, _dds_header_dx10  # noqa: E402


def make_dx10_dds(width=4, height=4, mips=2, dxgi=71, cubemap=False, fill=b"\xAB"):
    faces = 6 if cubemap else 1
    body_len = max(16, width * height * faces)
    return _dds_header_dx10(width, height, mips, dxgi, cubemap) + (fill * body_len)


class Ba2VersionTests(unittest.TestCase):
    def _write_temp(self, data: bytes) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".ba2", delete=False)
        tmp.write(data)
        tmp.close()
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.remove(tmp.name))
        return tmp.name

    def test_header_extra_bytes_table(self):
        self.assertEqual(HEADER_EXTRA_BYTES, {1: 0, 2: 8, 3: 12, 7: 0, 8: 0})

    def test_gnrl_versions_1_2_3_7_8_compressed_and_uncompressed(self):
        entries = {
            r"Meshes\Props\Box01.nif": b"NIF-PAYLOAD-" * 40,
            r"Materials\Props\Box01.bgsm": b"BGSM-DATA-" * 15,
            r"Scripts\FO4SF_Test.pex": b"\xFA\x57\xC0\xDE" * 32,
        }
        for version in (1, 2, 3, 7, 8):
            for compressed in (False, True):
                with self.subTest(version=version, compressed=compressed):
                    raw = general_archive(entries, compressed=compressed, version=version, compression=0)
                    a = Ba2(self._write_temp(raw))
                    self.assertEqual(a.version, version)
                    self.assertEqual(a.kind, "GNRL")
                    self.assertEqual(len(a.entries), 3)
                    # Verify algebraic entry table start offset
                    expected_first_off = 24 + HEADER_EXTRA_BYTES[version] + 36 * 3
                    self.assertEqual(a.entries[0].offset, expected_first_off)
                    # Lookup is case-insensitive and slash-agnostic
                    self.assertEqual(a.find("meshes/props/box01.nif"), 0)
                    self.assertEqual(a.find(r"\MATERIALS\PROPS\BOX01.BGSM"), 1)
                    for name, expected in entries.items():
                        self.assertEqual(a.read(name), expected)
                    est = a.size_estimates()
                    self.assertEqual(est["unpacked_bytes"], sum(len(v) for v in entries.values()))
                    if compressed:
                        self.assertLess(est["packed_bytes"], est["unpacked_bytes"])
                    else:
                        self.assertEqual(est["packed_bytes"], est["unpacked_bytes"])

    def test_dx10_versions_1_2_3_7_8_compressed_and_uncompressed_and_cubemap(self):
        dds_2d = make_dx10_dds(width=8, height=8, mips=3, dxgi=71, cubemap=False, fill=b"\x3C")
        dds_cube = make_dx10_dds(width=4, height=4, mips=1, dxgi=87, cubemap=True, fill=b"\x7E")
        entries = {
            r"Textures\Props\Crate_d.dds": dds_2d,
            r"Textures\Cubemaps\Shiny_e.dds": dds_cube,
        }
        for version in (1, 2, 3, 7, 8):
            for compressed in (False, True):
                with self.subTest(version=version, compressed=compressed):
                    raw = texture_archive(entries, version=version, compressed=compressed, compression=0)
                    a = Ba2(self._write_temp(raw))
                    self.assertEqual(a.version, version)
                    self.assertEqual(a.kind, "DX10")
                    self.assertEqual(a.summary()["textures"], 2)
                    expected_first_off = 24 + HEADER_EXTRA_BYTES[version] + (24 + 24) * 2
                    self.assertEqual(a.entries[0].chunks[0][0], expected_first_off)
                    self.assertFalse(a.entries[0].cubemap)
                    self.assertTrue(a.entries[1].cubemap)
                    self.assertEqual(a.read("textures/props/crate_d.dds"), dds_2d)
                    self.assertEqual(a.read("textures/cubemaps/shiny_e.dds"), dds_cube)

    def test_multi_chunk_dx10_v7_and_v8(self):
        hdr = _dds_header_dx10(16, 16, 4, 71, False)
        mip01 = b"\x11" * 256
        mip23 = b"\x22" * 64
        for version in (7, 8):
            c0 = zlib.compress(mip01)
            c1 = zlib.compress(mip23)
            rec_off = 24
            data_off0 = rec_off + 24 + 48
            data_off1 = data_off0 + len(c0)
            name_off = data_off1 + len(c1)
            name_bytes = b"Textures\\MultiMip.dds"
            blob = (
                struct.pack("<4sI4sIQ", b"BTDX", version, b"DX10", 1, name_off)
                + struct.pack("<I4sIBBHHHBBBB", 0, b"dds\0", 0, 0, 2, 24, 16, 16, 4, 71, 0, 8)
                + struct.pack("<QIIHHI", data_off0, len(c0), len(mip01), 0, 1, 0xBAADF00D)
                + struct.pack("<QIIHHI", data_off1, len(c1), len(mip23), 2, 3, 0xBAADF00D)
                + c0
                + c1
                + struct.pack("<H", len(name_bytes))
                + name_bytes
            )
            a = Ba2(self._write_temp(blob))
            self.assertEqual(a.version, version)
            self.assertEqual(a.read(0), hdr + mip01 + mip23)

    def test_unsupported_versions_magic_kind_and_lz4_controls(self):
        base = bytearray(general_archive({"a.nif": b"data" * 10}, compressed=True, version=7))
        for bad_ver in (0, 4, 5, 6, 9, 99):
            mutated = bytearray(base)
            struct.pack_into("<I", mutated, 4, bad_ver)
            with self.assertRaises(Ba2Error):
                Ba2(self._write_temp(bytes(mutated)))

        bad_magic = bytearray(base)
        bad_magic[:4] = b"BSA\x00"
        with self.assertRaises(Ba2Error):
            Ba2(self._write_temp(bytes(bad_magic)))

        bad_kind = bytearray(base)
        bad_kind[8:12] = b"GNMF"
        with self.assertRaises(Ba2Error):
            Ba2(self._write_temp(bytes(bad_kind)))

        # v3 LZ4 (compression=3) refused on compressed GNRL and DX10, allowed when stored uncompressed
        lz4_gnrl = general_archive({"a.nif": b"hello" * 20}, compressed=True, version=3, compression=3)
        a_gnrl = Ba2(self._write_temp(lz4_gnrl))
        with self.assertRaises(Ba2Error):
            a_gnrl.read(0)

        stored_v3 = general_archive({"a.nif": b"raw"}, compressed=False, version=3, compression=3)
        self.assertEqual(Ba2(self._write_temp(stored_v3)).read(0), b"raw")

        dds = make_dx10_dds()
        lz4_dx10 = texture_archive({"t.dds": dds}, version=3, compressed=True, compression=3)
        a_dx10 = Ba2(self._write_temp(lz4_dx10))
        with self.assertRaises(Ba2Error):
            a_dx10.read(0)

    def test_truncated_and_corrupt_zlib_raise_ba2error(self):
        with self.assertRaises(Ba2Error):
            Ba2(self._write_temp(b"BTDX\x08\x00"))

        valid = bytearray(general_archive({"a.nif": b"payload" * 20}, compressed=True, version=8))
        # Corrupt compressed bytes at offset 60
        valid[60] ^= 0xFF
        valid[61] ^= 0xFF
        a = Ba2(self._write_temp(bytes(valid)))
        with self.assertRaises(Ba2Error):
            a.read(0)


if __name__ == "__main__":
    unittest.main()
