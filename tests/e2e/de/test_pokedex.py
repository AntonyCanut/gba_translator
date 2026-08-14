"""Audit exhaustif du Pokédex dans la ROM allemande construite."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from languages.de.patches import pokedex as dex_patch
from languages.de.patches import pokedex_categories as categories
from languages.de.patches import pokedex_category_order as category_order
from languages.de.patches import pokedex_metrics as metrics
from languages.de.patches import pokedex_stat_labels as stat_labels
from src.core import pokedex
from src.core.dialogue_linewrap import line_width
from src.core.text_codec import GERMAN_UMLAUT_CHARS, TextDecoder, TextEncoder

pytestmark = pytest.mark.rom

ROOT = Path(os.environ.get("GBA_PROJECT_ROOT", Path(__file__).resolve().parents[3]))
DE_ROM = ROOT / "output/roms/GenedRom-de.gba"
EN_ROM = ROOT / "input/roms/englishrom.gba"
TRANSLATIONS = ROOT / "output/translation/de_translation_ready.json"
COMBINED = ROOT / "languages/de/combined_de.txt"
OVERRIDES = ROOT / "languages/de/data/pokedex_de_overrides.json"


@pytest.fixture(scope="module")
def roms() -> tuple[bytes, bytes]:
    if not DE_ROM.exists() or not TRANSLATIONS.exists():
        pytest.skip("ROM DE non construite — lancer make build-de")
    return EN_ROM.read_bytes(), DE_ROM.read_bytes()


def _decode_terminated(rom: bytes, offset: int, limit: int = 400) -> str:
    end = rom.find(b"\xff", offset, min(offset + limit + 1, len(rom)))
    assert end >= offset, f"chaîne non terminée à 0x{offset:X}"
    return TextDecoder.decode_pokemon(rom[offset:end], preserve_unknown=True)


def _codec_roundtrip(text: str) -> str:
    encoded = TextEncoder.encode_pokemon(text, skip_aliases=GERMAN_UMLAUT_CHARS)
    return TextDecoder.decode_pokemon(encoded[:-1], preserve_unknown=True)


def test_all_896_descriptions_are_exact_german_and_fit_the_real_window(roms) -> None:
    english, german = roms
    text_map = dex_patch.load_text_map(TRANSLATIONS, COMBINED)
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    entries = list(pokedex.iter_entries(english))

    assert len(entries) == 896
    for entry in entries:
        pointer = int.from_bytes(
            german[entry.struct_offset:entry.struct_offset + 4], "little"
        ) - dex_patch.ROM_POINTER_BASE
        assert 0 <= pointer < len(german), entry.index
        actual = _decode_terminated(german, pointer)
        source = overrides.get(str(entry.text_offset), text_map.get(entry.text_offset))
        assert source and pokedex.is_description(source), entry.index
        assert actual == _codec_roundtrip(pokedex.rewrap(source)), entry.index
        lines = actual.split("\n")
        assert len(lines) <= pokedex.DEX_MAX_LINES, entry.index
        assert all(line_width(line) <= pokedex.DEX_LINE_WIDTH for line in lines), entry.index


def test_categories_labels_order_metrics_and_navigation_decode_from_rom(roms) -> None:
    english, german = roms
    mapping = categories.load_mapping(ROOT / "languages/de/data")
    translated = skipped = 0
    for index in range(categories.MAX_ENTRIES):
        offset = categories.TABLE_ADDR + index * categories.STRIDE
        source = categories._decode_cell(english, offset)
        if not source or "[" in source or source not in mapping:
            skipped += 1
            continue
        assert categories._decode_cell(german, offset) == mapping[source], index
        translated += 1
    assert (translated, skipped) == (906, 2)

    for offset, _old, expected in metrics.PATCHES:
        assert german[offset:offset + len(expected)] == expected, hex(offset)
    for offset, _old, expected in category_order.PATCHES:
        assert german[offset:offset + len(expected)] == expected, hex(offset)
    for table in stat_labels.PTR_TABLE_OFFSETS:
        for index, key in enumerate(stat_labels.STAT_ORDER):
            pointer_offset = table + index * stat_labels.PTR_STRIDE
            pointer = int.from_bytes(
                german[pointer_offset:pointer_offset + 4], "little"
            ) - stat_labels.GBA_BASE
            assert german[pointer:pointer + 7] == stat_labels.DE_ENTRIES[key]

    navigation = _decode_terminated(german, 0x415F51)
    assert "Wahl" in navigation and "Ende" in navigation
    assert "Choix" not in navigation and "Cancel" not in navigation
