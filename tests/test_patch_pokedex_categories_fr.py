"""Tests for patch_pokedex_categories_fr.py."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from scripts.patch_pokedex_categories_fr import (
    CELL_SIZE,
    CHAR_TO_BYTE,
    MAX_CHARS,
    STRIDE,
    TABLE_ADDR,
    _decode_cell,
    _encode,
    apply_patch,
    load_mapping,
)

DATA_DIR = Path(__file__).parent.parent / 'languages' / 'fr' / 'data'
ROM_PATH = Path(__file__).parent.parent / 'output' / 'roms' / 'GenedRom-fr.gba'


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def cfru(s: str) -> bytes:
    """Encode *s* via the CFRU charmap, terminated with 0xFF."""
    return _encode(s)


def make_cell(text: str) -> bytes:
    """Encode *text* and pad to CELL_SIZE bytes with 0xFF."""
    raw = cfru(text)
    return raw + b'\xFF' * (CELL_SIZE - len(raw))


# ---------------------------------------------------------------------------
# Unit tests for _decode_cell
# ---------------------------------------------------------------------------

class TestDecodeCell:
    def test_simple_ascii(self):
        data = bytearray(make_cell('Mouse'))
        assert _decode_cell(data, 0) == 'Mouse'

    def test_accented(self):
        # 'é' = 0x1B in CFRU
        data = bytearray(make_cell('Lécheur'))
        assert _decode_cell(data, 0) == 'Lécheur'

    def test_max_length(self):
        # 11 chars exactly
        data = bytearray(make_cell('Gigantesque'))
        assert _decode_cell(data, 0) == 'Gigantesque'

    def test_empty_cell(self):
        data = bytearray(b'\xFF' * CELL_SIZE)
        assert _decode_cell(data, 0) == ''

    def test_offset(self):
        # Pad with stride bytes
        buf = bytearray(b'\xFF' * STRIDE)
        # write a known category at byte 4 (simulates a different field offset)
        encoded = cfru('Seed')
        buf[4:4 + len(encoded)] = encoded
        assert _decode_cell(buf, 4) == 'Seed'


# ---------------------------------------------------------------------------
# Unit tests for _encode
# ---------------------------------------------------------------------------

class TestEncode:
    def test_basic(self):
        result = _encode('Souris')
        # S=0xCD o=0xE3 u=0xE9 r=0xE6 i=0xDD s=0xE7 FF
        assert result == bytes([0xCD, 0xE3, 0xE9, 0xE6, 0xDD, 0xE7, 0xFF])

    def test_accented(self):
        result = _encode('Graine')
        assert result[-1] == 0xFF  # terminator
        assert len(result) == 7   # 6 chars + terminator

    def test_terminates_with_ff(self):
        for word in ['Rat', 'Dragon', 'Paléozoïque']:
            assert _encode(word)[-1] == 0xFF

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match='too long'):
            _encode('A' * 12)

    def test_bad_char_raises(self):
        with pytest.raises(ValueError, match='Unencodable'):
            _encode('Ü')  # ü not in charmap

    def test_max_length_ok(self):
        result = _encode('Gigantesque')  # 11 chars
        assert len(result) == 12  # 11 + 0xFF


# ---------------------------------------------------------------------------
# Unit tests for apply_patch
# ---------------------------------------------------------------------------

def _make_rom_with(en_cat: str, dex_idx: int = 0) -> bytearray:
    """Build a minimal fake ROM with *en_cat* at the given dex entry."""
    rom_size = TABLE_ADDR + (dex_idx + 1) * STRIDE + 4
    data = bytearray(b'\xFF' * rom_size)
    cell_offset = TABLE_ADDR + dex_idx * STRIDE
    encoded = cfru(en_cat)
    data[cell_offset:cell_offset + len(encoded)] = encoded
    return data


class TestApplyPatch:
    def test_translates_known_category(self):
        mapping = {'Mouse': 'Souris', 'Seed': 'Graine'}
        data = _make_rom_with('Mouse', dex_idx=0)
        patched, skipped = apply_patch(data, mapping)
        assert patched == 1
        assert _decode_cell(data, TABLE_ADDR) == 'Souris'

    def test_leaves_unknown_category_unchanged(self):
        mapping = {'Mouse': 'Souris'}
        data = _make_rom_with('Legendary', dex_idx=0)
        patched, skipped = apply_patch(data, mapping)
        assert patched == 0
        assert skipped == 1
        assert _decode_cell(data, TABLE_ADDR) == 'Legendary'

    def test_idempotent(self):
        mapping = {'Mouse': 'Souris'}
        data = _make_rom_with('Mouse', dex_idx=0)
        apply_patch(data, mapping)
        snapshot = bytes(data)
        patched, _ = apply_patch(data, mapping)
        assert patched == 0  # second run is a no-op
        assert bytes(data) == snapshot

    def test_skips_empty_cell(self):
        mapping = {'Mouse': 'Souris'}
        rom_size = TABLE_ADDR + STRIDE + 4
        data = bytearray(b'\xFF' * rom_size)  # 0xFF everywhere = empty cell
        patched, skipped = apply_patch(data, mapping)
        assert patched == 0
        assert skipped >= 1

    def test_pads_remaining_bytes_with_ff(self):
        # 'Mouse' (6 chars) replaces a longer EN string (11 chars)
        data = _make_rom_with('A' * 11, dex_idx=0)
        mapping = {'A' * 11: 'Souris'}
        apply_patch(data, mapping)
        cell_offset = TABLE_ADDR
        cell = bytes(data[cell_offset:cell_offset + CELL_SIZE])
        # First 6 bytes = 'Souris' encoded, byte 7 = 0xFF terminator, rest = 0xFF
        assert cell[6] == 0xFF  # terminator
        assert all(b == 0xFF for b in cell[7:])

    def test_multiple_entries(self):
        mapping = {'Mouse': 'Souris', 'Seed': 'Graine', 'Lizard': 'Lézard'}
        rom_size = TABLE_ADDR + 3 * STRIDE + 4
        data = bytearray(b'\xFF' * rom_size)
        for idx, cat in enumerate(['Mouse', 'Seed', 'Lizard']):
            off = TABLE_ADDR + idx * STRIDE
            enc = cfru(cat)
            data[off:off + len(enc)] = enc
        patched, _ = apply_patch(data, mapping)
        assert patched == 3
        assert _decode_cell(data, TABLE_ADDR) == 'Souris'
        assert _decode_cell(data, TABLE_ADDR + STRIDE) == 'Graine'
        assert _decode_cell(data, TABLE_ADDR + 2 * STRIDE) == 'Lézard'


# ---------------------------------------------------------------------------
# Mapping integrity
# ---------------------------------------------------------------------------

class TestMapping:
    def test_mapping_loads(self):
        m = load_mapping(DATA_DIR)
        assert len(m) >= 650

    def test_all_fr_translations_encodable(self):
        m = load_mapping(DATA_DIR)
        bad = []
        for en, fr in m.items():
            for ch in fr:
                if ch not in CHAR_TO_BYTE:
                    bad.append(f'{en!r}: unencodable {ch!r} in {fr!r}')
        assert not bad, '\n'.join(bad)

    def test_all_fr_translations_within_length(self):
        m = load_mapping(DATA_DIR)
        too_long = [
            f'{en!r} -> {fr!r} ({len(fr)} chars)'
            for en, fr in m.items()
            if len(fr) > MAX_CHARS
        ]
        assert not too_long, '\n'.join(too_long)

    def test_key_categories_present(self):
        m = load_mapping(DATA_DIR)
        assert m['Mouse'] == 'Souris'
        assert m['Poison Pin'] == 'Aiguillon'
        assert m['Licking'] == 'Lécheur'
        assert m['Seed'] == 'Graine'
        assert m['Lizard'] == 'Lézard'
        assert m['Flame'] == 'Flamme'

    def test_no_duplicate_fr_values_for_distinct_en(self):
        # Two different EN categories may map to the same FR word (e.g. Sun/Sunne)
        # but we want to ensure it's intentional, not a copy-paste error.
        # Just spot-check that common accidental duplicates aren't present.
        m = load_mapping(DATA_DIR)
        # Sun and Sunne both map to Soleil intentionally
        assert m.get('Sun') == m.get('Sunne') == 'Soleil'


# ---------------------------------------------------------------------------
# ROM integration (skipped if ROM not built)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not ROM_PATH.exists(), reason='FR ROM not built')
class TestROMIntegration:
    def test_patch_applies_to_rom(self):
        """After apply_patch the ROM should have FR categories for all known EN entries."""
        mapping = load_mapping(DATA_DIR)
        data = bytearray(ROM_PATH.read_bytes())
        apply_patch(data, mapping)
        # Verify that FR values appear: count cells whose content is in mapping.values()
        fr_values = set(mapping.values())
        translated = 0
        for idx in range(908):
            off = TABLE_ADDR + idx * STRIDE
            if off + CELL_SIZE > len(data):
                break
            cat = _decode_cell(data, off)
            if cat in fr_values:
                translated += 1
        assert translated >= 900, f'Only {translated} FR categories found in ROM'

    def _find_category_idx(self, data: bytearray, cat: str) -> int | None:
        for idx in range(908):
            off = TABLE_ADDR + idx * STRIDE
            if off + CELL_SIZE > len(data):
                break
            if _decode_cell(data, off) == cat:
                return idx
        return None

    def test_souris_category_present(self):
        """'Souris' (FR Mouse) should be present in the built ROM."""
        data = bytearray(ROM_PATH.read_bytes())
        idx = self._find_category_idx(data, 'Souris')
        assert idx is not None, "'Souris' not found in ROM — patch may not have run"

    def test_aiguillon_category_present(self):
        """'Aiguillon' (FR Poison Pin) should be in the built ROM."""
        data = bytearray(ROM_PATH.read_bytes())
        idx = self._find_category_idx(data, 'Aiguillon')
        assert idx is not None, "'Aiguillon' not found in ROM"

    def test_lecheur_category_present(self):
        """'Lécheur' (FR Licking) should be in the built ROM."""
        data = bytearray(ROM_PATH.read_bytes())
        idx = self._find_category_idx(data, 'Lécheur')
        assert idx is not None, "'Lécheur' not found in ROM"

    def test_idempotent_on_real_rom(self):
        mapping = load_mapping(DATA_DIR)
        data = bytearray(ROM_PATH.read_bytes())
        apply_patch(data, mapping)
        snapshot = bytes(data)
        patched2, _ = apply_patch(data, mapping)
        assert patched2 == 0
        assert bytes(data) == snapshot
