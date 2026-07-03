"""Regression guard for scripts/patch_pc_messages_de.py.

The two PC-message slots are a fixed number of bytes with no relocation
possible (see the module docstring): the raw English strings decode to 64
and 67 bytes respectively, with no slack before the next ROM content. This
test pins that budget guard — a literal translation of the English/French
wording would silently overflow both slots and corrupt the following ROM
data, which is exactly the class of bug ``apply``'s length check exists to
catch.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import patch_pc_messages_de as mod  # noqa: E402


class TestPcMessagesDe(unittest.TestCase):
    def test_every_patch_fits_its_declared_budget(self):
        for offset, _en, de, max_bytes in mod.PATCHES:
            normalized = (
                de.replace('{FD:03}', '<0xFD><0x03>')
                .replace('{FD:04}', '<0xFD><0x04>')
                .replace('{FD:02}', '<0xFD><0x02>')
                .replace('{FD:01}', '<0xFD><0x01>')
                .replace('\\p', '<0xFB>')
            )
            from src.core.text_codec import TextEncoder
            encoded = TextEncoder.encode(normalized, 'pokemon')
            self.assertLessEqual(
                len(encoded), max_bytes,
                f"0x{offset:X}: {len(encoded)} bytes exceeds the {max_bytes}-byte slot",
            )

    def test_patch_pc_messages_writes_expected_offsets(self):
        offset1, _en1, _de1, max1 = mod.PATCHES[0]
        offset2, _en2, _de2, max2 = mod.PATCHES[1]
        size = max(offset1 + max1, offset2 + max2) + 4
        with TemporaryDirectory() as d:
            p = Path(d) / "rom.gba"
            p.write_bytes(bytearray(size))
            applied = mod.patch_pc_messages(p)
            self.assertEqual(applied, 2)
            data = p.read_bytes()
            # Both slots must now be non-zero (something was written).
            self.assertNotEqual(data[offset1:offset1 + 4], b"\x00\x00\x00\x00")
            self.assertNotEqual(data[offset2:offset2 + 4], b"\x00\x00\x00\x00")


if __name__ == "__main__":
    unittest.main()
