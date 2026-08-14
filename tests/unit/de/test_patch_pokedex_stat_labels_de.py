"""Gardes des six libellés statistiques pointés du Pokédex allemand."""

from __future__ import annotations

import importlib
import struct

import pytest


def _module():
    try:
        return importlib.import_module("languages.de.patches.pokedex_stat_labels")
    except ModuleNotFoundError:
        pytest.fail("le patch languages/de/patches/pokedex_stat_labels.py manque")


def _synthetic_rom(mod, entries: dict[str, bytes]) -> bytearray:
    table = mod.PTR_TABLE_OFFSETS[0]
    entry_len = len(next(iter(entries.values())))
    strings = table + len(mod.STAT_ORDER) * mod.PTR_STRIDE
    rom = bytearray(strings + len(entries) * entry_len + 0x10)
    for index, key in enumerate(mod.STAT_ORDER):
        offset = strings + index * entry_len
        rom[offset:offset + entry_len] = entries[key]
        struct.pack_into("<I", rom, table + index * mod.PTR_STRIDE, mod.GBA_BASE + offset)
    return rom


def _read_entry(mod, rom: bytes, index: int) -> bytes:
    table = mod.PTR_TABLE_OFFSETS[0]
    pointer = struct.unpack_from("<I", rom, table + index * mod.PTR_STRIDE)[0]
    offset = pointer - mod.GBA_BASE
    return bytes(rom[offset:offset + 7])


def test_uses_bounded_german_stat_abbreviations() -> None:
    mod = _module()
    assert mod.DE_LABELS == {
        "hp": "KP",
        "atk": "Ang",
        "def": "Ver",
        "spe": "Init",
        "spa": "SpA",
        "spd": "SpV",
    }
    assert set(mod.DE_LABELS) == set(mod.STAT_ORDER)
    assert all(len(entry) == 7 for entry in mod.DE_ENTRIES.values())
    assert all(entry[-3:] == bytes([0xFD, 0x02, 0xFF]) for entry in mod.DE_ENTRIES.values())


def test_rewrites_all_pointed_entries_and_is_idempotent() -> None:
    mod = _module()
    rom = _synthetic_rom(mod, mod.EN_ENTRIES)

    expected_changes = sum(
        mod.EN_ENTRIES[key] != mod.DE_ENTRIES[key] for key in mod.STAT_ORDER
    )
    assert mod.apply_to_rom(rom) == expected_changes
    for index, key in enumerate(mod.STAT_ORDER):
        assert _read_entry(mod, rom, index) == mod.DE_ENTRIES[key]
    assert mod.apply_to_rom(rom) == 0
