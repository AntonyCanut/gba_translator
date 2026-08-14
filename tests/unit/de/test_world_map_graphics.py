"""Régressions DE des labels/actions de carte du monde (F-605)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from languages.de.patches import world_map_action_labels, worldmap_labels
from languages.fr.patches.worldmap_junction_panels import (
    TARGETS as JUNCTION_TARGETS,
)
from languages.fr.patches.worldmap_junction_panels import (
    encode_relocated,
    find_referrers,
    load_combined,
)
from src.core.text_codec import TextDecoder, TextEncoder
from src.i18n import load_registry

ROOT = Path(__file__).resolve().parents[3]
BUILT_ROM = ROOT / "output/roms/GenedRom-de.gba"
SOURCE_ROM = ROOT / "input/roms/englishrom.gba"
COMBINED_DE = ROOT / "languages/de/combined_de.txt"


def _decode_at(rom: bytes, offset: int) -> str:
    end = rom.index(0xFF, offset)
    return TextDecoder.decode_pokemon(rom[offset : end + 1], preserve_unknown=True)


def test_world_map_actions_write_german_cells_and_known_pointers() -> None:
    """Une relocation générique ne doit pas laisser les actions FR/EN actives."""
    rom = bytearray(b"\xff" * (0x418F20))

    changed = world_map_action_labels.apply(rom)

    assert changed == 7
    hint = world_map_action_labels.WORLD_MAP_HINT_BYTES
    assert rom[
        world_map_action_labels.WORLD_MAP_HINT_OFFSET:
        world_map_action_labels.WORLD_MAP_HINT_OFFSET + len(hint)
    ] == hint
    for offset in world_map_action_labels.WORLD_MAP_CANCEL_OFFSETS:
        cancel = world_map_action_labels.WORLD_MAP_CANCEL_BYTES
        assert rom[offset : offset + len(cancel)] == cancel
    for pointer, target in world_map_action_labels.WORLD_MAP_CANCEL_POINTER_TARGETS:
        assert struct.unpack_from("<I", rom, pointer)[0] == 0x08000000 + target


def test_world_map_actions_are_idempotent() -> None:
    """Réappliquer le patch ne doit changer ni cellule ni pointeur."""
    rom = bytearray(b"\xff" * (0x418F20))
    world_map_action_labels.apply(rom)
    expected = bytes(rom)

    changed = world_map_action_labels.apply(rom)

    assert changed == 0
    assert bytes(rom) == expected


def test_world_map_labels_restore_original_proper_names() -> None:
    """Le port DE doit conserver les noms de lieux originaux du parent F-595."""
    size = 0xB53620
    source = bytearray(b"\x00" * size)
    target = bytearray(b"\x00" * size)
    expected = {
        0xB500A0: "Gurun Town",
        0xB535C8: "Fullmoon Island",
    }
    for offset, text in expected.items():
        encoded = TextEncoder.encode(text, "pokemon")
        source[offset : offset + len(encoded)] = encoded
        target[offset : offset + len(encoded)] = b"\xbb" * len(encoded)

    changed = worldmap_labels.apply(target, bytes(source))

    assert changed == 2
    assert {_offset: _decode_at(target, _offset) for _offset in expected} == expected


def test_world_map_steps_run_after_repairs_and_junctions_stay_enabled() -> None:
    """L'ordre DE doit protéger labels, actions et dix panneaux de jonction."""
    patches = load_registry().get("de").patches

    for step in ("worldmap_labels", "world_map_action_labels"):
        assert patches.index(step) > patches.index("repair_localized_lz77")
    assert "worldmap_junction_panels" in patches


@pytest.mark.rom
def test_built_german_rom_contains_original_map_names_and_german_actions() -> None:
    """Le produit livré doit décoder les cellules réellement consommées."""
    if not BUILT_ROM.exists():
        pytest.skip("ROM DE non construite")
    rom = BUILT_ROM.read_bytes()

    assert _decode_at(rom, 0xB500A0) == "Gurun Town"
    assert _decode_at(rom, 0xB535C8) == "Fullmoon Island"
    hint = world_map_action_labels.WORLD_MAP_HINT_BYTES
    assert rom[
        world_map_action_labels.WORLD_MAP_HINT_OFFSET:
        world_map_action_labels.WORLD_MAP_HINT_OFFSET + len(hint)
    ] == hint


@pytest.mark.rom
def test_built_german_rom_contains_all_ten_localized_junction_panels() -> None:
    """Les dix panneaux doivent être relogés, pointés et encodés depuis DE."""
    if not BUILT_ROM.exists():
        pytest.skip("ROM DE non construite")
    rom = BUILT_ROM.read_bytes()
    source = SOURCE_ROM.read_bytes()
    combined = load_combined(COMBINED_DE)

    assert set(JUNCTION_TARGETS) <= set(combined)
    for offset in JUNCTION_TARGETS:
        assert not find_referrers(rom, offset), f"0x{offset:X} pointe encore l'anglais"
        expected = encode_relocated(combined[offset], source, offset)
        assert expected in rom, f"panneau DE 0x{offset:X} absent de la ROM"
