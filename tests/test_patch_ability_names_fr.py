"""Unit tests for scripts/patch_ability_names_fr.py.

Ability names live in a fixed-width 17-byte table (0xA36398..0xA376FC) with no
pointers. The build's in-place ROM fallback only translates a name when the
French string is no longer than the English original, so ~130 names — including
the reported "Ice Body" → "Corps Gel" — ship in English despite fitting the
cell. This patch writes them straight from combined_fr.txt.
"""

import re
import unittest
from pathlib import Path

from scripts.patch_ability_names_fr import (
    ABILITY_STRIDE,
    ABILITY_TABLE_LAST,
    ABILITY_TABLE_OFFSET,
    _encode,
    apply_to_rom,
)

REPO = Path(__file__).resolve().parents[1]
COMBINED_FR = REPO / "languages" / "fr" / "combined_fr.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def _cell_rom(entries: dict[int, str], stride: int, size: int) -> bytearray:
    """Synthetic ROM: write each name + 0xFF terminator at its offset."""
    data = bytearray(size)
    for offset, name in entries.items():
        raw = _encode(name)
        data[offset : offset + len(raw)] = raw
        data[offset + len(raw)] = 0xFF
    return data


class TestApplyToRom(unittest.TestCase):
    BASE = ABILITY_TABLE_OFFSET
    STRIDE = ABILITY_STRIDE

    def _kwargs(self, count: int):
        return {"base": self.BASE, "last": self.BASE + (count - 1) * self.STRIDE,
                "stride": self.STRIDE}

    def test_patches_still_english_cell(self):
        o = self.BASE
        data = _cell_rom({o: "Ice Body"}, self.STRIDE, o + self.STRIDE)
        fr = {o: "Corps Gel"}
        en = {o: "Ice Body"}
        patched, warnings = apply_to_rom(data, fr, en, **self._kwargs(1))
        self.assertEqual(patched, 1)
        self.assertEqual(warnings, [])
        raw = _encode("Corps Gel")
        self.assertEqual(bytes(data[o : o + len(raw)]), raw)
        self.assertEqual(data[o + len(raw)], 0xFF)
        # freed trailing bytes are zero padding
        self.assertEqual(bytes(data[o + len(raw) + 1 : o + self.STRIDE]), b"\x00" * (self.STRIDE - len(raw) - 1))

    def test_idempotent(self):
        o = self.BASE
        data = _cell_rom({o: "Ice Body"}, self.STRIDE, o + self.STRIDE)
        fr, en = {o: "Corps Gel"}, {o: "Ice Body"}
        apply_to_rom(data, fr, en, **self._kwargs(1))
        patched, _ = apply_to_rom(data, fr, en, **self._kwargs(1))
        self.assertEqual(patched, 0)

    def test_normalizes_deaccented_variant(self):
        """A cell left as 'OEil Composé' by an older build heals to 'Œil Composé'."""
        o = self.BASE
        data = _cell_rom({o: "OEil Composé"}, self.STRIDE, o + self.STRIDE)
        fr, en = {o: "Œil Composé"}, {o: "Compound Eyes"}
        patched, warnings = apply_to_rom(data, fr, en, **self._kwargs(1))
        self.assertEqual(patched, 1)
        self.assertEqual(warnings, [])
        raw = _encode("Œil Composé")
        self.assertEqual(bytes(data[o : o + len(raw)]), raw)

    def test_skips_placeholder_without_fr_entry(self):
        o = self.BASE
        data = _cell_rom({o: "-------"}, self.STRIDE, o + self.STRIDE)
        patched, warnings = apply_to_rom(data, {}, {o: "-------"}, **self._kwargs(1))
        self.assertEqual(patched, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(bytes(data[o : o + 7]), _encode("-------"))

    def test_warns_and_skips_overflowing_fr_name(self):
        o = self.BASE
        data = _cell_rom({o: "Alchemic Power"}, self.STRIDE, o + self.STRIDE)
        # 17 chars + terminator = 18 > 17-byte cell.
        fr, en = {o: "Pouvoir Alchimique"}, {o: "Alchemic Power"}
        patched, warnings = apply_to_rom(data, fr, en, **self._kwargs(1))
        self.assertEqual(patched, 0)
        self.assertEqual(len(warnings), 1)
        self.assertIn("byte cell", warnings[0])
        # cell untouched
        self.assertEqual(bytes(data[o : o + len(_encode("Alchemic Power"))]), _encode("Alchemic Power"))

    def test_warns_and_skips_unexpected_cell(self):
        o = self.BASE
        data = _cell_rom({o: "Totally Wrong"}, self.STRIDE, o + self.STRIDE)
        fr, en = {o: "Corps Gel"}, {o: "Ice Body"}
        patched, warnings = apply_to_rom(data, fr, en, **self._kwargs(1))
        self.assertEqual(patched, 0)
        self.assertEqual(len(warnings), 1)
        self.assertIn("unexpected", warnings[0])

    def test_does_not_stray_past_table_end(self):
        """Offsets past `last` must never be read/written (they hold descriptions)."""
        o = self.BASE
        past = self.BASE + 1 * self.STRIDE
        size = past + self.STRIDE
        data = _cell_rom({o: "Ice Body"}, self.STRIDE, size)
        # Leave `past` as zero bytes; provide fr/en entries there too.
        before = bytes(data[past : past + self.STRIDE])
        fr = {o: "Corps Gel", past: "Devrait Ignorer"}
        en = {o: "Ice Body", past: "Should Ignore"}
        # last = only the first cell.
        patched, _ = apply_to_rom(data, fr, en, base=self.BASE, last=self.BASE, stride=self.STRIDE)
        self.assertEqual(patched, 1)
        self.assertEqual(bytes(data[past : past + self.STRIDE]), before)


class TestCombinedFrAbilityNamesFit(unittest.TestCase):
    """Every FR ability name in combined_fr.txt must fit the 17-byte cell.

    Guards against a future combined_fr.txt edit reintroducing an overflowing
    name (which would silently ship in English again).
    """

    def _fr_entries(self) -> dict[int, str]:
        entries = {}
        for line in COMBINED_FR.read_text(encoding="utf-8").splitlines():
            m = _LINE_RE.match(line)
            if m:
                entries[int(m.group(1), 16)] = m.group(2)  # last wins
        return entries

    def test_all_ability_names_fit_cell(self):
        fr = self._fr_entries()
        for offset in range(ABILITY_TABLE_OFFSET, ABILITY_TABLE_LAST + 1, ABILITY_STRIDE):
            name = fr.get(offset)
            if name is None:
                continue  # placeholder cell
            encoded = _encode(name)
            self.assertLessEqual(
                len(encoded) + 1, ABILITY_STRIDE,
                f"0x{offset:X}: {name!r} ({len(encoded) + 1} bytes) overflows "
                f"the {ABILITY_STRIDE}-byte ability cell",
            )

    def test_ice_body_is_corps_gel(self):
        """The reported ticket: Ice Body (0xA36A91) → Corps Gel."""
        self.assertEqual(self._fr_entries().get(0xA36A91), "Corps Gel")


if __name__ == "__main__":
    unittest.main()
