"""E2E: quotation marks render as quote glyphs, never as the ellipsis.

Ticket: in-game dialogues such as the Zygarde collection quest read
"collecter toutes les « cellules » et « noyaux » de Zygarde". The encoder
used to fold every quotation mark (« » " " " ") onto byte 0xB0 — which in
the FireRed/CFRU font is the ELLIPSIS glyph "…" — so the line rendered as
"… cellules … et … noyaux …", which the user (rightly) called "très moche".

The real double-quote glyphs are 0xB1 "“" / 0xB2 "”" (the bytes the English
ROM uses itself: <0xB1>evolution this<0xB2>). These tests decode the BUILT FR
ROM and assert the quoted dialogues now carry 0xB1/0xB2 and emit no 0xB0
ellipsis around the quoted words.
"""

import pytest

from src.core.text_codec import POKEMON_TERMINATOR, TextDecoder, TextEncoder

_ELLIPSIS_BYTE = 0xB0
_OPEN_QUOTE_BYTE = 0xB1
_CLOSE_QUOTE_BYTE = 0xB2


def _enclosing_string(rom: bytes, index: int) -> bytes:
    """Return the 0xFF-delimited string that contains ``index``."""
    start = rom.rfind(POKEMON_TERMINATOR, 0, index) + 1
    end = rom.find(POKEMON_TERMINATOR, index)
    if end < 0:
        end = len(rom) - 1
    return rom[start : end + 1]


def _find_string_containing(rom: bytes, needle: str, must_have: str) -> bytes:
    """Locate the ROM string whose decoded text contains ``must_have``.

    ``needle`` is encoded and searched as raw bytes (relocated text means we
    cannot rely on a fixed offset); ``must_have`` then disambiguates among
    the matches.
    """
    key = TextEncoder.encode_pokemon(needle)[:-1]  # drop terminator
    i = rom.find(key)
    while i != -1:
        s = _enclosing_string(rom, i)
        text = TextDecoder.decode_pokemon(s, preserve_unknown=True)
        if must_have in text:
            return s
        i = rom.find(key, i + 1)
    raise AssertionError(f"no built-ROM string for {needle!r} containing {must_have!r}")


@pytest.fixture
def fr_rom_bytes(fr_rom_path):
    return fr_rom_path.read_bytes()


class TestQuoteGlyphsInBuiltRom:
    def test_zygarde_cellules_noyaux_dialogue(self, fr_rom_bytes):
        """« cellules » / « noyaux » must be quote glyphs, not ellipses."""
        s = _find_string_containing(fr_rom_bytes, "noyaux", "cellules")
        assert _ELLIPSIS_BYTE not in s, (
            "Zygarde cells/cores dialogue still encodes the 0xB0 ellipsis "
            "glyph around the quoted words"
        )
        assert _OPEN_QUOTE_BYTE in s and _CLOSE_QUOTE_BYTE in s, (
            "Zygarde cells/cores dialogue lost its quote glyphs (0xB1/0xB2)"
        )

    def test_zygarde_ramasser_curly_quote_variant(self, fr_rom_bytes):
        """The curly-quote variant ("cellules"/"coeurs") also uses glyphs."""
        s = _find_string_containing(fr_rom_bytes, "ramasser", "Zygarde")
        assert _ELLIPSIS_BYTE not in s
        assert _OPEN_QUOTE_BYTE in s and _CLOSE_QUOTE_BYTE in s

    def test_montagne_gelee_quotation(self, fr_rom_bytes):
        """A legitimate quotation ("Qui construit…?") renders as “ … ”."""
        s = _find_string_containing(fr_rom_bytes, "Qui construit", "montagne")
        assert _ELLIPSIS_BYTE not in s
        assert _OPEN_QUOTE_BYTE in s and _CLOSE_QUOTE_BYTE in s
