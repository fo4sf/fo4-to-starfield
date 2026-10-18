"""Tests for Ba2.extension_counts and the summary CLI."""
import tempfile
from pathlib import Path

import pytest

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


def test_extension_counts_basic():
    data = general_archive({
        "meshes/foo.nif": b"nifdata",
        "textures/bar.dds": b"ddsdata",
        "textures/baz.DDS": b"more",
        "sounds/quux.xwm": b"sound",
        "noext": b"plain",
    })
    with tempfile.NamedTemporaryFile(suffix=".ba2", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        ba2 = Ba2(path)
        counts = ba2.extension_counts()
        assert counts["nif"] == 1
        assert counts["dds"] == 2
        assert counts["xwm"] == 1
        assert counts[""] == 1
        assert sum(counts.values()) == 5
    finally:
        Path(path).unlink(missing_ok=True)


def test_extension_counts_single():
    data = general_archive({"only.nif": b"data"})
    with tempfile.NamedTemporaryFile(suffix=".ba2", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        ba2 = Ba2(path)
        assert ba2.extension_counts() == {"nif": 1}
    finally:
        Path(path).unlink(missing_ok=True)
