"""Tests for patch_worldmap_labels_fr.py.

The World-Map labels at 0xB500A0 ("Gurenbourg") and 0xB535C8 ("Île Pleinelune")
must be written in place from combined_fr.txt, fitting within the English slot
plus its trailing padding run, without clobbering the next pointer-table entry.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from languages.fr.patches.worldmap_labels import (  # noqa: E402
    TARGETS,
    _english_slot,
    apply,
    load_combined,
    verify,
)
from src.core.text_codec import TextDecoder, TextEncoder  # noqa: E402


def _build_source(labels: dict[int, str], size: int = 0xC00000) -> bytes:
    """English ROM: each label as <text>0xFF, then 5 padding bytes, then a pointer."""
    rom = bytearray(b"\x00" * size)
    for offset, en_text in labels.items():
        enc = TextEncoder.encode(en_text, "pokemon")  # includes 0xFF
        rom[offset : offset + len(enc)] = enc
        # 5 padding bytes (0x00/0xFF) then a live 4-byte pointer (non-padding).
        pad_start = offset + len(enc)
        rom[pad_start : pad_start + 5] = b"\x00\xff\xff\xff\xff"
        rom[pad_start + 5 : pad_start + 9] = b"\x01\x02\x03\x08"
    return bytes(rom)


def _combined_lines() -> dict[int, str]:
    return {0xB500A0: "Gurenbourg", 0xB535C8: "Île Pleinelune"}


class TestPatchWorldmapLabelsFR(unittest.TestCase):
    EN = {0xB500A0: "Gurun Town", 0xB535C8: "Fullmoon Island"}

    def setUp(self) -> None:
        self.source = _build_source(self.EN)
        self.rom = bytearray(self.source)  # starts as the English ROM
        self.combined = _combined_lines()

    def _decode(self, rom: bytes, offset: int) -> str:
        end = rom.find(b"\xff", offset)
        raw = rom[offset : end + 1] if end != -1 else rom[offset : offset + 40]
        return TextDecoder.decode_pokemon(raw, preserve_unknown=True).strip()

    def test_writes_both_labels_in_place(self) -> None:
        stats = apply(self.rom, self.combined, self.source)
        self.assertEqual(stats["written"], 2)
        self.assertEqual(self._decode(self.rom, 0xB500A0), "Gurenbourg")
        self.assertEqual(self._decode(self.rom, 0xB535C8), "Île Pleinelune")
        self.assertEqual(verify(self.rom), [])

    def test_does_not_clobber_next_pointer(self) -> None:
        # The pointer that follows the longer label (Fullmoon Island) must survive.
        enc = TextEncoder.encode("Fullmoon Island", "pokemon")
        ptr_off = 0xB535C8 + len(enc) + 5
        before = bytes(self.source[ptr_off : ptr_off + 4])
        apply(self.rom, self.combined, self.source)
        self.assertEqual(bytes(self.rom[ptr_off : ptr_off + 4]), before)

    def test_idempotent(self) -> None:
        apply(self.rom, self.combined, self.source)
        snapshot = bytes(self.rom)
        stats = apply(self.rom, self.combined, self.source)
        self.assertEqual(bytes(self.rom), snapshot)
        self.assertEqual(stats["written"], 0)
        self.assertEqual(stats["skipped"], 2)

    def test_verify_catches_english_left_in_place(self) -> None:
        # No write performed: verify must report both targets as wrong.
        bad = verify(bytes(self.source))
        self.assertEqual(len(bad), 2)

    def test_too_long_is_skipped_not_overflowed(self) -> None:
        # A label with no padding and a French value longer than the slot must
        # be skipped, never written past the slot.
        tight_source = bytearray(b"\x01" * 0xC00000)  # no padding anywhere
        enc = TextEncoder.encode("Gurun Town", "pokemon")
        tight_source[0xB500A0 : 0xB500A0 + len(enc)] = enc
        rom = bytearray(tight_source)
        combined = {0xB500A0: "Un nom beaucoup trop long pour ce slot"}
        # Build a TARGETS-only view by reusing the module's set via monkeypatch.
        import languages.fr.patches.worldmap_labels as mod
        original = mod.TARGETS
        mod.TARGETS = {0xB500A0: "Un nom beaucoup trop long pour ce slot"}
        try:
            stats = apply(rom, combined, bytes(tight_source))
        finally:
            mod.TARGETS = original
        self.assertEqual(stats["too_long"], 1)
        self.assertEqual(stats["written"], 0)
        # The byte after the slot must be untouched.
        self.assertEqual(rom[0xB500A0 + len(enc) + 1], 0x01)

    def test_targets_present_in_combined_fr(self) -> None:
        combined = load_combined(REPO_ROOT / "languages/fr/combined_fr.txt")
        for offset, expected in TARGETS.items():
            self.assertIn(offset, combined, f"0x{offset:08X} missing from combined_fr.txt")


if __name__ == "__main__":
    unittest.main()
