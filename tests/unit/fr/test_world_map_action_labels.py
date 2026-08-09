"""Régressions des libellés d'action partagés (#111, #131, #178)."""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

from languages.fr.patches.world_map_action_labels import apply
from src.text.charmap_data import CHAR_TO_BYTE


ROOT = Path(__file__).resolve().parents[3]
BUILT_ROM = ROOT / "output/roms/GenedRom-fr.gba"
COMBINED_FR = ROOT / "languages/fr/combined_fr.txt"
ROM_BASE = 0x08000000

# Chaînes « <bouton A> Cancel » propres aux variantes de la carte mondiale.
WORLD_MAP_CANCEL_OFFSETS = (0x418E95, 0x418E9E)
WORLD_MAP_CANCEL_POINTERS = (0xC06FC, 0xC1B28, 0xC50C0)
WORLD_MAP_CANCEL_TEXT = "{SE_SHOP}Annul."
WORLD_MAP_CANCEL_BYTES = bytes.fromhex("f800bbe2e2e9e0adff")
WORLD_MAP_CANCEL_ORIGINAL_BYTES = bytes.fromhex("f800bdbae2bdd9e0ff")
WORLD_MAP_CANCEL_FULL_BYTES = bytes.fromhex("f800bbe2e2e9e0d9e6ff")
WORLD_MAP_CANCEL_FULL_OFFSET = 0x418F20
WORLD_MAP_CANCEL_TARGETS = {
    0xC06FC: 0x418E95,
    0xC1B28: 0x418E9E,
    0xC50C0: 0x418E95,
}

# Bandeaux de déplacement affichés en haut de la carte mondiale.
WORLD_MAP_HINT_OFFSET = 0x418E77
WORLD_MAP_MOVE_OFFSET = 0x418EB5
WORLD_MAP_HINT_POINTER = 0x9FB64
WORLD_MAP_MOVE_POINTERS = (0xC05D8, 0xC12E0, 0xC283C, 0xC4FE8)
WORLD_MAP_HINT_TEXT = "{DPAD_ANY}Dépl. {SE_SHOP}OK {B_BUTTON}Annul."
WORLD_MAP_MOVE_TEXT = "{DPAD_ANY}Dépl."
WORLD_MAP_HINT_CANCEL_SLOT_SIZE = 6
WORLD_MAP_HINT_BYTES = bytes.fromhex(
    "f80cbe1be4e0ad00f800c9c500f801bbe2e2e9e0adff"
)
WORLD_MAP_HINT_WITHOUT_DOT_BYTES = bytes.fromhex(
    "f80cbe1be4e0ad00f800c9c500f801bbe2e2e9e0ff"
)
WORLD_MAP_MOVE_BYTES = bytes.fromhex("f80cbe1be4e0adff")

# Ces deux références appartiennent au menu Équipe, pas à la carte mondiale.
PARTY_CANCEL_POINTERS = (0xA6CA2C, 0xA6CA64)
ANNULER_BYTES = bytes.fromhex("bbe2e2e9e0d9e6ff")
FAKE_ROM_SIZE = WORLD_MAP_HINT_OFFSET + 0x100

_LINE_RE = re.compile(r"^\s*0x([0-9a-fA-F]+)\s*:\s*(.*)$")


def _load_last_wins(path: Path) -> dict[int, str]:
    """Charge les traductions avec la même règle « dernière occurrence gagne »."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LINE_RE.match(line)
        if match:
            mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def _read_pointed_bytes(rom: bytes, pointer_offset: int) -> bytes:
    """Retourne la chaîne terminée pointée depuis ``pointer_offset``."""
    text_pointer = struct.unpack_from("<I", rom, pointer_offset)[0]
    assert ROM_BASE <= text_pointer < ROM_BASE + len(rom)
    text_offset = text_pointer - ROM_BASE
    terminator = rom.index(0xFF, text_offset)
    return rom[text_offset:terminator + 1]


def _fake_rom(
    *,
    pointed_offset: int = WORLD_MAP_HINT_OFFSET,
    rebuilt_cancel_labels: bool = False,
) -> bytearray:
    """Construit une ROM minimale avec l'ancien libellé sans point."""
    rom = bytearray(b"\xff" * FAKE_ROM_SIZE)
    rom[WORLD_MAP_HINT_OFFSET:WORLD_MAP_HINT_OFFSET + len(
        WORLD_MAP_HINT_WITHOUT_DOT_BYTES
    )] = WORLD_MAP_HINT_WITHOUT_DOT_BYTES
    struct.pack_into(
        "<I", rom, WORLD_MAP_HINT_POINTER, ROM_BASE + pointed_offset
    )
    for offset in WORLD_MAP_CANCEL_OFFSETS:
        rom[offset:offset + len(WORLD_MAP_CANCEL_BYTES)] = (
            WORLD_MAP_CANCEL_BYTES
        )
    for pointer, target in WORLD_MAP_CANCEL_TARGETS.items():
        struct.pack_into("<I", rom, pointer, ROM_BASE + target)

    if rebuilt_cancel_labels:
        for offset in WORLD_MAP_CANCEL_OFFSETS:
            rom[offset:offset + len(WORLD_MAP_CANCEL_ORIGINAL_BYTES)] = (
                WORLD_MAP_CANCEL_ORIGINAL_BYTES
            )
        rom[
            WORLD_MAP_CANCEL_FULL_OFFSET:
            WORLD_MAP_CANCEL_FULL_OFFSET + len(WORLD_MAP_CANCEL_FULL_BYTES)
        ] = WORLD_MAP_CANCEL_FULL_BYTES
        for pointer in WORLD_MAP_CANCEL_POINTERS:
            struct.pack_into(
                "<I",
                rom,
                pointer,
                ROM_BASE + WORLD_MAP_CANCEL_FULL_OFFSET,
            )
    return rom


def test_hint_patch_restores_canonical_cell_and_live_pointer() -> None:
    """Le patch doit restaurer le point et le pointeur vivant."""
    relocated_offset = WORLD_MAP_HINT_OFFSET + 0x80
    rom = _fake_rom(pointed_offset=relocated_offset)
    tail_start = WORLD_MAP_HINT_OFFSET + 0x20
    untouched_tail = bytes(rom[tail_start:tail_start + 8])

    assert apply(rom) == 2
    assert _read_pointed_bytes(rom, WORLD_MAP_HINT_POINTER) == WORLD_MAP_HINT_BYTES
    assert bytes(rom[tail_start:tail_start + 8]) == untouched_tail


def test_hint_patch_is_idempotent() -> None:
    """Deux applications successives doivent produire exactement la même ROM."""
    rom = _fake_rom()

    assert apply(rom) == 1
    after_first_apply = bytes(rom)

    assert apply(rom) == 0
    assert bytes(rom) == after_first_apply


def test_cancel_patch_restores_original_cells_and_pointer_table() -> None:
    """Le rebuild ne doit pas rediriger la carte vers « Annuler »."""
    rom = _fake_rom(rebuilt_cancel_labels=True)
    full_label_before = bytes(
        rom[
            WORLD_MAP_CANCEL_FULL_OFFSET:
            WORLD_MAP_CANCEL_FULL_OFFSET + len(WORLD_MAP_CANCEL_FULL_BYTES)
        ]
    )

    assert (
        len(WORLD_MAP_CANCEL_BYTES)
        == len(WORLD_MAP_CANCEL_ORIGINAL_BYTES)
        == 9
    )
    assert apply(rom) == 6
    assert all(
        bytes(rom[offset:offset + len(WORLD_MAP_CANCEL_BYTES)])
        == WORLD_MAP_CANCEL_BYTES
        for offset in WORLD_MAP_CANCEL_OFFSETS
    )
    assert {
        pointer: struct.unpack_from("<I", rom, pointer)[0] - ROM_BASE
        for pointer in WORLD_MAP_CANCEL_POINTERS
    } == WORLD_MAP_CANCEL_TARGETS
    assert bytes(
        rom[
            WORLD_MAP_CANCEL_FULL_OFFSET:
            WORLD_MAP_CANCEL_FULL_OFFSET + len(WORLD_MAP_CANCEL_FULL_BYTES)
        ]
    ) == full_label_before
    assert apply(rom) == 0


def test_world_map_sources_use_complete_short_labels() -> None:
    """Les sources doivent contenir les formes courtes attendues."""
    mapping = _load_last_wins(COMBINED_FR)

    assert mapping[WORLD_MAP_HINT_OFFSET] == WORLD_MAP_HINT_TEXT
    assert mapping[WORLD_MAP_MOVE_OFFSET] == WORLD_MAP_MOVE_TEXT
    assert {
        offset: mapping.get(offset)
        for offset in WORLD_MAP_CANCEL_OFFSETS
    } == {
        offset: WORLD_MAP_CANCEL_TEXT
        for offset in WORLD_MAP_CANCEL_OFFSETS
    }


def test_world_map_hint_cancel_fits_its_six_glyph_slot() -> None:
    """Le libellé B du bandeau ne doit pas déborder dans la carte."""
    mapping = _load_last_wins(COMBINED_FR)
    cancel_label = mapping[WORLD_MAP_HINT_OFFSET].rsplit("{B_BUTTON}", 1)[1]
    encoded_label = bytes(CHAR_TO_BYTE[character] for character in cancel_label)

    assert len(encoded_label) <= WORLD_MAP_HINT_CANCEL_SLOT_SIZE


@pytest.mark.rom
def test_world_map_cancel_pointers_render_short_label() -> None:
    """Toutes les variantes de la carte doivent afficher « Annul. »."""
    rom = BUILT_ROM.read_bytes()

    assert all(
        _read_pointed_bytes(rom, pointer) == WORLD_MAP_CANCEL_BYTES
        for pointer in WORLD_MAP_CANCEL_POINTERS
    )


@pytest.mark.rom
def test_party_cancel_entries_keep_full_shared_label() -> None:
    """Les entrées du menu Équipe ne doivent pas être prises pour la carte."""
    rom = BUILT_ROM.read_bytes()

    assert all(
        _read_pointed_bytes(rom, pointer) == ANNULER_BYTES
        for pointer in PARTY_CANCEL_POINTERS
    )


@pytest.mark.rom
def test_world_map_move_hints_have_no_trailing_residue() -> None:
    """Le bandeau doit conserver le point final dans sa cellule."""
    rom = BUILT_ROM.read_bytes()

    assert (
        _read_pointed_bytes(rom, WORLD_MAP_HINT_POINTER)
        == WORLD_MAP_HINT_BYTES
    )
    assert all(
        _read_pointed_bytes(rom, pointer) == WORLD_MAP_MOVE_BYTES
        for pointer in WORLD_MAP_MOVE_POINTERS
    )
