"""Tests for languages/it/patches/pokedex_categories.py (mirrors the FR/DE test suites)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from languages.it.patches.pokedex_categories import (  # noqa: E402
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

DATA_DIR = ROOT / "languages" / "it" / "data"
FR_DATA_DIR = ROOT / "languages" / "fr" / "data"
ROM_PATH = ROOT / "output" / "roms" / "GenedRom-it.gba"


def cfru(s: str) -> bytes:
    return _encode(s)


def make_cell(text: str) -> bytes:
    raw = cfru(text)
    return raw + b'\xFF' * (CELL_SIZE - len(raw))


class TestDecodeCell:
    def test_simple_ascii(self):
        data = bytearray(make_cell('Topo'))
        assert _decode_cell(data, 0) == 'Topo'

    def test_accented_char(self):
        data = bytearray(make_cell('Perché'))
        assert _decode_cell(data, 0) == 'Perché'

    def test_empty_cell(self):
        data = bytearray(b'\xFF' * CELL_SIZE)
        assert _decode_cell(data, 0) == ''


class TestEncode:
    def test_terminates_with_ff(self):
        for word in ['Seme', 'Fiamma', 'Lucertola']:
            assert _encode(word)[-1] == 0xFF

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            _encode('A' * 12)

    def test_max_length_ok(self):
        result = _encode('A' * MAX_CHARS)
        assert len(result) == MAX_CHARS + 1


def _make_rom_with(en_cat: str, dex_idx: int = 0) -> bytearray:
    rom_size = TABLE_ADDR + (dex_idx + 1) * STRIDE + 4
    data = bytearray(b'\xFF' * rom_size)
    cell_offset = TABLE_ADDR + dex_idx * STRIDE
    encoded = cfru(en_cat)
    data[cell_offset:cell_offset + len(encoded)] = encoded
    return data


class TestApplyPatch:
    def test_translates_known_category(self):
        mapping = {'Mouse': 'Topo'}
        data = _make_rom_with('Mouse', dex_idx=0)
        patched, skipped = apply_patch(data, mapping)
        assert patched == 1
        assert _decode_cell(data, TABLE_ADDR) == 'Topo'

    def test_leaves_unknown_category_unchanged(self):
        mapping = {'Mouse': 'Topo'}
        data = _make_rom_with('Legendary', dex_idx=0)
        patched, skipped = apply_patch(data, mapping)
        assert patched == 0
        assert skipped == 1

    def test_idempotent(self):
        mapping = {'Mouse': 'Topo'}
        data = _make_rom_with('Mouse', dex_idx=0)
        apply_patch(data, mapping)
        snapshot = bytes(data)
        patched, _ = apply_patch(data, mapping)
        assert patched == 0
        assert bytes(data) == snapshot


class TestMapping:
    def test_mapping_loads(self):
        m = load_mapping(DATA_DIR)
        assert len(m) >= 500

    def test_all_it_translations_encodable(self):
        m = load_mapping(DATA_DIR)
        bad = []
        for en, it in m.items():
            for ch in it:
                if ch not in CHAR_TO_BYTE:
                    bad.append(f'{en!r}: unencodable {ch!r} in {it!r}')
        assert not bad, '\n'.join(bad)

    def test_all_it_translations_within_length(self):
        m = load_mapping(DATA_DIR)
        too_long = [
            f'{en!r} -> {it!r} ({len(it)} chars)'
            for en, it in m.items()
            if len(it) > MAX_CHARS
        ]
        assert not too_long, '\n'.join(too_long)

    def test_same_key_set_as_fr(self):
        """No species should be silently left in English: IT must cover
        exactly the same 653 EN category keys as the FR mapping."""
        it_json = json.loads((DATA_DIR / 'pokedex_categories_it.json').read_text(encoding='utf-8'))
        fr_json = json.loads((FR_DATA_DIR / 'pokedex_categories_fr.json').read_text(encoding='utf-8'))
        assert set(it_json.keys()) == set(fr_json.keys())


@pytest.mark.skipif(not ROM_PATH.exists(), reason='IT ROM not built')
class TestROMIntegration:
    def test_patch_applies_to_rom(self):
        mapping = load_mapping(DATA_DIR)
        data = bytearray(ROM_PATH.read_bytes())
        apply_patch(data, mapping)
        it_values = set(mapping.values())
        translated = sum(
            1 for idx in range(908)
            if TABLE_ADDR + idx * STRIDE + CELL_SIZE <= len(data)
            and _decode_cell(data, TABLE_ADDR + idx * STRIDE) in it_values
        )
        assert translated >= 400, f'Only {translated} IT categories found in ROM'
