"""E2E: ability names render in French in the built FR ROM.

Bug report (this ticket — "Traduction Talent"):
    « Le nom des talents n'est pas traduit (ici Ice Body). »

Ability names live in a fixed-width 17-byte table at 0xA36398..0xA376FC with no
pointers — a class-2 table absent from the injection JSON and the Spanish
extraction. The build's in-place ROM fallback only writes a French name when it
is no LONGER than the English original, so every longer French name
("Ice Body" → "Corps Gel", and ~130 more) was silently dropped and shipped in
English. ``scripts/patch_ability_names_fr.py`` (wired into ``make build-fr``)
writes them straight from combined_fr.txt.

These tests decode the bytes the render engine actually reads (stronger than a
screenshot) and lock the whole table to French so a future rebuild can't regress.
"""

import re
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

REPO = Path(__file__).resolve().parents[3]
FR_ROM = REPO / "output" / "roms" / "GenedRom-fr.gba"
COMBINED_FR = REPO / "languages" / "fr" / "combined_fr.txt"
COMBINED_EN = REPO / "languages" / "en" / "combined_en.txt"

ABILITY_TABLE_OFFSET = 0xA36398
ABILITY_TABLE_LAST = 0xA376FC
ABILITY_STRIDE = 17

_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def _parse(path: Path) -> dict:
    entries = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LINE_RE.match(line)
        if m:
            entries[int(m.group(1), 16)] = m.group(2)
    return entries


def _decode_cell(rom_data: bytes, offset: int, stride: int = ABILITY_STRIDE) -> str:
    cell = rom_data[offset : offset + stride]
    end = cell.find(b"\xFF")
    raw = cell if end == -1 else cell[:end]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


@pytest.fixture(scope="module")
def rom_data():
    if not FR_ROM.exists():
        pytest.skip(f"ROM not found: {FR_ROM}")
    return FR_ROM.read_bytes()


@pytest.mark.rom
class TestAbilityNamesFrench:
    def test_ice_body_is_corps_gel(self, rom_data):
        """The reported cell: Ice Body (0xA36A91) must decode to 'Corps Gel'."""
        name = _decode_cell(rom_data, 0xA36A91)
        assert name == "Corps Gel", f"0xA36A91: got {name!r}, expected 'Corps Gel'"

    def test_sample_abilities_are_french(self, rom_data):
        expected = {
            0xA36A1A: "Peau Sèche",     # Dry Skin
            0xA36A80: "Soin Poison",    # Poison Heal
            0xA37069: "Armurouillée",   # Weak Armor
            0xA36486: "Œil Composé",    # Compound Eyes (œ ligature)
            0xA37575: "Force Alchimique",  # Alchemic Power (shortened to fit)
            0xA376C9: "Écailles Poudre",   # Dusty Scales (shortened to fit)
            0xA376FC: "Hurlement Royal",   # Royal Roar (shortened to fit, last cell)
        }
        for offset, want in expected.items():
            got = _decode_cell(rom_data, offset)
            assert got == want, f"0x{offset:X}: got {got!r}, expected {want!r}"

    def test_no_ability_cell_left_in_english(self, rom_data):
        """Every ability with an FR translation must no longer decode to its EN name."""
        fr = _parse(COMBINED_FR)
        en = _parse(COMBINED_EN)
        english_left = []
        for offset in range(ABILITY_TABLE_OFFSET, ABILITY_TABLE_LAST + 1, ABILITY_STRIDE):
            fr_name = fr.get(offset)
            en_name = en.get(offset)
            if fr_name is None or en_name is None or fr_name == en_name:
                continue  # placeholder or identical EN/FR
            decoded = _decode_cell(rom_data, offset)
            if decoded == en_name:
                english_left.append((hex(offset), en_name))
        assert not english_left, f"ability cells still in English: {english_left}"
