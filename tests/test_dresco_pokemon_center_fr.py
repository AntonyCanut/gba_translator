"""Régression de l'issue #172 : conseil du Centre Pokémon de Dresco."""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from src.core.dialogue_linewrap import DEFAULT_MAX_LINE_WIDTH, line_width
from src.core.text_codec import TextDecoder


ROOT = Path(__file__).resolve().parent.parent
COMBINED_FR = ROOT / "languages/fr/combined_fr.txt"
COMBINED_EN = ROOT / "languages/en/combined_en.txt"
EN_ROM = ROOT / "input/roms/englishrom.gba"
FR_ROM = ROOT / "output/roms/GenedRom-fr.gba"
OFFSET = 0x1F02DD8
LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
EXPECTED_PARAGRAPH = (
    r"\pÀ la Route 2, Picassaut et\n"
    r"Hoothoot ont {COLOR}ÉRegard Vif{COLOR}Ë.\l"
    r"Attrape-les tous."
)
EXPECTED_ROM_TAIL = (
    "À la Route 2, Picassaut et\n"
    "Hoothoot ont <0xFC>ÀÉRegard Vif<0xFC>ÀË.<0xFA>"
    "Attrape-les tous."
)


def _last_value(path: Path, offset: int) -> str:
    value = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = LINE_RE.match(raw)
        if match and int(match.group(1), 16) == offset:
            value = match.group(2)
    assert value, f"0x{offset:X} absent de {path}"
    return value


def test_dresco_advice_uses_precise_three_line_wording() -> None:
    french = _last_value(COMBINED_FR, OFFSET)
    assert french.endswith(EXPECTED_PARAGRAPH)


def test_dresco_advice_highlights_keen_eye_in_green() -> None:
    french = _last_value(COMBINED_FR, OFFSET)
    english = _last_value(COMBINED_EN, OFFSET)
    builder = importlib.import_module(
        "src.translators.19_build_translated_rom_generic"
    ).TranslatedROMBuilder
    rom = EN_ROM.read_bytes()
    end = rom.index(0xFF, OFFSET)
    english_raw = rom[OFFSET:end].hex()

    resolved = builder._apply_control_placeholders(french, english, english_raw)

    assert (
        "<0xFC><0x01><0x06>Regard Vif<0xFC><0x01><0x08>."
        in resolved
    )


def test_dresco_advice_lines_fit_the_dialogue_box() -> None:
    visible_lines = (
        "À la Route 2, Picassaut et",
        "Hoothoot ont Regard Vif.",
        "Attrape-les tous.",
    )
    assert all(line_width(line) <= DEFAULT_MAX_LINE_WIDTH for line in visible_lines)


@pytest.mark.rom
def test_built_rom_contains_the_final_dresco_advice() -> None:
    rom = FR_ROM.read_bytes()
    end = rom.index(0xFF, OFFSET)
    raw = rom[OFFSET:end]
    decoded = TextDecoder.decode_pokemon(raw + b"\xff", preserve_unknown=True)

    assert decoded.endswith(EXPECTED_ROM_TAIL)
    assert b"\xfc\x01\x06" in raw
    assert b"\xfc\x01\x08" in raw
