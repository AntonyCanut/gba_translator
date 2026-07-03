"""E2E: Italian/German item & move descriptions in the built ROM.

Two complementary guards live here:

* ``TestItemDescriptions`` / ``TestMoveDescriptions`` — decode a handful of
  known-clean live CFRU pointers (items table 0x876074, stride 44;
  move-description table 0x99F190, mirroring ``src.core.moves``) and assert the
  text is proper Italian. These are *positive* assertions on entries verified to
  already carry clean Italian (Fresh Water / "Acqua Fresca", moves
  Pound/Tackle/Bite/Rock Throw).

* ``test_no_french_leftover_item_descriptions`` — a *negative* regression guard
  covering the whole item table for both IT and DE. The git-tracked
  ``input/roms/englishrom.gba`` is not pristine English: a large part of the
  CFRU item table ships **French** text baked into free-space cells. The
  dedicated FR build looks correct by accident — the base already holds French —
  but the generic ``build_language.py`` pipeline inherits that French for any
  offset not covered by ``combined_<code>.txt``. This guard reads the built
  ``GenedRom-it.gba`` / ``GenedRom-de.gba`` and asserts no item's live
  description pointer still resolves to an untranslated French cell (a cell is a
  French leftover when the built description is byte-identical to the base
  ROM's *and* the text is French rather than English — English-untranslated
  cells are the normal backlog and out of scope). It rebuilds nothing and skips
  cleanly when the relevant ROM is absent, so it is a no-op in headless CI.

Marks: rom
"""

from __future__ import annotations

import os
import pathlib
import struct
from typing import Optional

import pytest

from src.core.text_codec import TextDecoder
from src.text.charmap_data import BYTE_TO_CHAR

ITEMS_TABLE = 0x876074
ITEM_STRIDE = 44
ITEM_NAME_FIELD = 14
ITEM_DESC_PTR_OFFSET = 0x14

MOVE_DESCRIPTION_TABLE = 0x99F190

GBA_BASE = 0x08000000

ITEM_FRESH_WATER = 0x23

MOVE_POUND = 1
MOVE_TACKLE = 33
MOVE_BITE = 44
MOVE_ROCK_THROW = 88


def _follow_ptr(rom: bytes, ptr_offset: int) -> Optional[int]:
    ptr = struct.unpack_from("<I", rom, ptr_offset)[0]
    if ptr < GBA_BASE:
        return None
    return ptr - GBA_BASE


def _decode(rom: bytes, offset: int, max_len: int = 300) -> str:
    result = []
    i = offset
    limit = min(offset + max_len, len(rom))
    while i < limit:
        b = rom[i]
        if b == 0xFF:
            break
        if b == 0xFE:
            result.append("\n")
            i += 1
        elif b in (0xFC, 0xFD):
            i += 2
        elif b in BYTE_TO_CHAR:
            result.append(BYTE_TO_CHAR[b])
            i += 1
        else:
            i += 1
    return "".join(result)


def _item_name(rom: bytes, item_id: int) -> str:
    offset = ITEMS_TABLE + item_id * ITEM_STRIDE
    return _decode(rom, offset, max_len=ITEM_NAME_FIELD)


def _item_description(rom: bytes, item_id: int) -> Optional[str]:
    offset = ITEMS_TABLE + item_id * ITEM_STRIDE + ITEM_DESC_PTR_OFFSET
    desc_offset = _follow_ptr(rom, offset)
    if desc_offset is None:
        return None
    return _decode(rom, desc_offset)


def _move_description(rom: bytes, move_id: int) -> Optional[str]:
    offset = MOVE_DESCRIPTION_TABLE + move_id * 4
    desc_offset = _follow_ptr(rom, offset)
    if desc_offset is None:
        return None
    return _decode(rom, desc_offset)


class TestItemDescriptions:
    """Verify a known-clean item's name and description via live ROM pointers."""

    def test_fresh_water_name_is_italian(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        name = _item_name(rom, ITEM_FRESH_WATER)
        assert name == "Acqua Fresca", f"Fresh Water name unexpected: {name!r}"

    def test_fresh_water_description_is_italian(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        text = _item_description(rom, ITEM_FRESH_WATER)
        assert text is not None, "Fresh Water: null/invalid description pointer"
        assert "PS" in text, f"expected Italian 'PS' (Punti Salute) in {text!r}"
        assert "PV" not in text, f"French 'PV' residue found: {text!r}"
        assert "HP" not in text, f"English 'HP' residue found: {text!r}"


class TestMoveDescriptions:
    """Verify known-clean move descriptions via the live gMoveDescriptionPointers table."""

    CASES = [
        (MOVE_POUND, "un attacco fisico"),
        (MOVE_TACKLE, "un attacco fisico"),
        (MOVE_BITE, "l'utente morde"),
        (MOVE_ROCK_THROW, "il bersaglio viene"),
    ]

    def test_move_descriptions_are_italian(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        for move_id, expected_prefix_lower in self.CASES:
            text = _move_description(rom, move_id)
            assert text is not None, f"move {move_id}: null/invalid description pointer"
            normalized = text.replace("\n", " ").lower()
            assert normalized.startswith(expected_prefix_lower), (
                f"move {move_id} description not the expected Italian text: {text!r}"
            )

    def test_move_descriptions_have_no_french_pronoun_residue(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        for move_id, _ in self.CASES:
            text = _move_description(rom, move_id)
            normalized = text.replace("\n", " ")
            assert " le " not in normalized and "L'ennemi" not in normalized, (
                f"move {move_id} description carries French residue: {text!r}"
            )


# ---------------------------------------------------------------------------
# Whole-table regression guard: no French leftovers in built IT/DE ROMs.
# ---------------------------------------------------------------------------

_HERE = pathlib.Path(__file__).resolve()


def _project_root() -> pathlib.Path:
    """Checkout the tests run from — the worktree's own checkout by default so
    the ROM built there is used, overridable via ``GBA_PROJECT_ROOT``."""
    env_root = os.environ.get("GBA_PROJECT_ROOT")
    if env_root:
        return pathlib.Path(env_root)
    return _HERE.parent.parent.parent.parent


PROJECT_ROOT = _project_root()
INPUT_ROMS = PROJECT_ROOT / "input" / "roms"
OUTPUT_ROMS = PROJECT_ROOT / "output" / "roms"
EN_ROM = INPUT_ROMS / "englishrom.gba"

DESC_PTR_OFFSET = 0x14
ITEM_COUNT = 0x260
GBA_POINTER_BASE = 0x08000000

# Accented letters that never appear in the English item descriptions once the
# lone loanwords "Pokémon" / "Poké" / "Café" are stripped. Their presence is a
# reliable French tell.
_ACCENTS = set("éèêëàâäçùûüîïôöœ")
# French function words that never occur in English item copy — a second,
# accent-independent tell.
_FRENCH_WORDS = (
    " les ", " une ", " des ", " pour ", " avec ", " dans ", " cette ",
    " vous ", " leur ", " aux ", " qui ", " est ", " sur ", " un ", " le ",
    " la ", " du ", "d'un", "d'une", "l'", "médic", "Soigne", "Restaure",
)


def _read(path: pathlib.Path) -> bytes:
    return path.read_bytes()


def _ptr_to_offset(pointer: int) -> Optional[int]:
    if pointer < GBA_POINTER_BASE:
        return None
    return pointer - GBA_POINTER_BASE


def _decode_at(rom: bytes, offset: Optional[int], max_len: int = 400) -> Optional[str]:
    if offset is None or offset < 0 or offset >= len(rom):
        return None
    end = offset
    while end < len(rom) and rom[end] != 0xFF and (end - offset) < max_len:
        end += 1
    return TextDecoder.decode_pokemon(rom[offset:end], preserve_unknown=True)


def _is_french(text: str) -> bool:
    """Heuristic: French rather than English. Strips the only accented English
    loanwords first, then flags remaining accents or French function words."""
    stripped = (
        text.replace("Pokémon", "Pokemon")
        .replace("Poké", "Poke")
        .replace("Café", "Cafe")
        .replace("café", "cafe")
    )
    if any(ch in _ACCENTS for ch in stripped):
        return True
    return sum(1 for word in _FRENCH_WORDS if word in text) >= 2


def _desc_pointer(rom: bytes, item_id: int) -> int:
    entry = ITEMS_TABLE + item_id * ITEM_STRIDE
    ptr_field = entry + DESC_PTR_OFFSET
    return int.from_bytes(rom[ptr_field:ptr_field + 4], "little")


def _french_leftovers(built_rom: bytes, base_rom: bytes) -> list[tuple[int, str]]:
    """Item ids whose built description is still the untranslated base French."""
    leftovers: list[tuple[int, str]] = []
    for item_id in range(ITEM_COUNT):
        base_txt = _decode_at(base_rom, _ptr_to_offset(_desc_pointer(base_rom, item_id)))
        built_txt = _decode_at(built_rom, _ptr_to_offset(_desc_pointer(built_rom, item_id)))
        if base_txt is None or built_txt is None:
            continue
        if base_txt == built_txt and _is_french(built_txt):
            leftovers.append((item_id, built_txt))
    return leftovers


@pytest.fixture(scope="module")
def base_rom() -> bytes:
    if not EN_ROM.exists():
        pytest.skip(f"base ROM not found: {EN_ROM}")
    return _read(EN_ROM)


@pytest.mark.rom
@pytest.mark.parametrize("lang", ["it", "de"])
def test_no_french_leftover_item_descriptions(lang: str, base_rom: bytes) -> None:
    rom_path = OUTPUT_ROMS / f"GenedRom-{lang}.gba"
    if not rom_path.exists():
        pytest.skip(f"{lang.upper()} ROM not built: {rom_path}")
    leftovers = _french_leftovers(_read(rom_path), base_rom)
    if leftovers:
        preview = "\n".join(
            f"  item 0x{iid:X}: {txt!r}" for iid, txt in leftovers[:15]
        )
        pytest.fail(
            f"{len(leftovers)} {lang.upper()} item/move descriptions still ship "
            f"untranslated French (should be {lang.upper()} via "
            f"combined_{lang}.txt):\n{preview}"
        )
