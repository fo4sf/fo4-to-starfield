"""Synthetic tests for Ba2.largest_entries."""
import os
import struct
import tempfile
import unittest
import zlib

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class LargestEntriesTests(unittest.TestCase):
    def test_orders_by_unpacked_size(self):
        entries = {
            "small.txt": b"a" * 10,
            "medium.bin": b"b" * 100,
            "large.dat": b"c" * 1000,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            top = a.largest_entries(2)
            self.assertEqual(len(top), 2)
            self.assertEqual(top[0]["name"], "large.dat")
            self.assertEqual(top[0]["unpacked"], 1000)
            self.assertGreater(top[0]["packed"], 0)  # compressed
            self.assertEqual(top[1]["name"], "medium.bin")
            self.assertEqual(top[1]["unpacked"], 100)

    def test_empty_and_n_limit(self):
        data = general_archive({"only.txt": b"x"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "one.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            self.assertEqual(len(a.largest_entries(5)), 1)
            self.assertEqual(a.largest_entries(0), [])

    def test_negative_counts_refuse_without_changing_archive_or_ranking(self):
        data = general_archive({"small": b"a", "medium": b"bb", "large": b"ccc"}, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "counts.ba2")
            with open(path, "wb") as stream:
                stream.write(data)
            archive = Ba2(path)
            baseline = archive.largest_entries(99)
            for count in (-1, -3, -99):
                with self.subTest(count=count), self.assertRaisesRegex(ValueError, "nonnegative"):
                    archive.largest_entries(count)
            self.assertEqual(archive.largest_entries(0), [])
            self.assertEqual(archive.largest_entries(2), baseline[:2])
            self.assertEqual(archive.largest_entries(99), baseline)
            with open(path, "rb") as stream:
                self.assertEqual(stream.read(), data)

    def test_integer_index_count_compatibility(self):
        class Two:
            def __index__(self):
                return 2

        data = general_archive({"a": b"a", "b": b"bb", "c": b"ccc"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "index.ba2")
            with open(path, "wb") as stream:
                stream.write(data)
            archive = Ba2(path)
            self.assertEqual(archive.largest_entries(Two()), archive.largest_entries(2))
            self.assertEqual(archive.largest_entries(True), archive.largest_entries(1))
            self.assertEqual(archive.largest_entries(False), [])
            with self.assertRaises(TypeError):
                archive.largest_entries(1.5)

    def test_packed_field_counts_stored_general_payload_even_when_raw_or_empty(self):
        entries = {"empty": b"", "data": b"x" * 32}
        for compressed in (False, True):
            with self.subTest(compressed=compressed), tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "stored.ba2")
                with open(path, "wb") as stream:
                    stream.write(general_archive(entries, compressed=compressed))
                archive = Ba2(path)
                rows = {row["name"]: row for row in archive.largest_entries()}
                for name, payload in entries.items():
                    self.assertEqual(rows[name]["unpacked"], len(payload))
                    self.assertEqual(rows[name]["packed"], len(zlib.compress(payload) if compressed else payload))
                    self.assertEqual(archive.read(name), payload)

    def test_mixed_texture_chunks_exclude_dds_header_from_ranked_sizes(self):
        top, mip = b"A" * 256, b"B" * 64  # RGBA8:8x8 then4x4.
        compressed = zlib.compress(top)
        offset = 24 + 24 + 2 * 24
        name = b"textures/test.dds"
        payload = compressed + mip
        blob = (struct.pack("<4sI4sIQ", b"BTDX", 1, b"DX10", 1, offset + len(payload))
                + struct.pack("<I4sIBBHHHBBBB", 0, b"DDS\0", 0, 0, 2, 24, 8, 8, 2, 28, 0, 0)
                + struct.pack("<QIIHHI", offset, len(compressed), len(top), 0, 0, 0)
                + struct.pack("<QIIHHI", offset + len(compressed), 0, len(mip), 1, 1, 0)
                + payload + struct.pack("<H", len(name)) + name)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mixed.ba2")
            with open(path, "wb") as stream:
                stream.write(blob)
            archive = Ba2(path)
            row, = archive.largest_entries(1)
            self.assertEqual(row["unpacked"], 320)
            self.assertEqual(row["packed"], len(payload))
            self.assertEqual(archive.read(name.decode())[148:], top + mip)


if __name__ == "__main__":
    unittest.main()
