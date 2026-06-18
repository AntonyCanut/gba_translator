"""
Regression guard: the in-battle "super effective" messages must render in
French after every ``make build-fr`` rebuild.

Why this regressed
------------------
The combined_fr.txt entry for the targeted message ("It's super effective on
<name>!") was keyed to the WRONG offset 0xA4A8DD — three bytes before the real
string start. The string the engine actually reads begins at 0xA4A8E0 (the only
offset present in the English extraction), so ``apply_combined_fr.py --extend``
could never add it to the trilingual CSV ("missing in English extraction") and
the translation was silently dropped — the battle kept showing English.

Fix: add the correct offset 0xA4A8E0 to combined_fr.txt's living block. The FR
string is longer than the EN original, so the injector relocates it to free
space and repoints the battle-string-table slot. These tests follow that slot
(fixed ROM data, stable across builds) so they catch a re-drop immediately.

Run standalone:   pytest tests/test_battle_super_effective_fr.py -v
"""

import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")

# Battle-string-table pointer slots (fixed ROM data — never relocated).
# Each slot stores the GBA pointer the battle engine dereferences to print the
# message, so following it is the engine's real read path.
PTR_SLOT_SUPER_EFFECTIVE_ON = 0x9EB8F4   # "It's super effective on <name>!" (orig string @0xA4A8E0)
PTR_SLOT_SUPER_EFFECTIVE = 0x3FE284      # "It's super effective!"           (orig string @0x3FCC74)


def _read_at(rom: bytes, offset: int, limit: int = 400) -> str:
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xff")
    raw = chunk if end == -1 else chunk[: end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def _follow_ptr(rom: bytes, ptr_offset: int, limit: int = 400) -> str:
    """Return decoded text at the GBA pointer stored at ptr_offset."""
    base = 0x08000000
    ptr = struct.unpack_from("<I", rom, ptr_offset)[0]
    if ptr < base or ptr >= base + len(rom):
        return ""
    return _read_at(rom, ptr - base, limit)


@pytest.mark.skipif(not FR_ROM.exists(), reason="FR ROM not built")
class TestBattleSuperEffectiveFr(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = FR_ROM.read_bytes()

    def test_super_effective_on_target_is_french(self):
        text = _follow_ptr(self.rom, PTR_SLOT_SUPER_EFFECTIVE_ON)
        self.assertIn("super efficace", text, f"expected French, got: {text!r}")
        self.assertNotIn("super effective", text, f"English leaked: {text!r}")

    def test_super_effective_is_french(self):
        text = _follow_ptr(self.rom, PTR_SLOT_SUPER_EFFECTIVE)
        self.assertIn("super efficace", text, f"expected French, got: {text!r}")
        self.assertNotIn("super effective", text, f"English leaked: {text!r}")


if __name__ == "__main__":
    unittest.main()
