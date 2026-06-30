"""E2E: hesitation/pause ellipses render as the ellipsis glyph, not a lone quote.

Ticket (R-09 follow-up #2): the user found a dialogue showing a stray lone
quote — "Bref" tu vois, ils détestent quand les gens fouinent." The English
source uses byte 0xB0 (the FireRed/CFRU ELLIPSIS glyph "…") for the pause after
"Anyway…", which had been decoded into the FR data as a straight quote and then
re-encoded as a real curly quote (0xB1/0xB2) — a stray quote with nothing inside.

The pause must instead carry byte 0xB0 (renders "…") — byte-faithful to the
English source. These tests decode the BUILT FR ROM and assert the restored
pauses carry 0xB0 and NOT a real quote glyph (0xB1/0xB2) at the pause site.
"""

import pytest

from src.core.text_codec import POKEMON_TERMINATOR, TextDecoder, TextEncoder

_ELLIPSIS_BYTE = 0xB0
_OPEN_QUOTE_BYTE = 0xB1
_CLOSE_QUOTE_BYTE = 0xB2


def _enclosing_string(rom: bytes, index: int) -> bytes:
    start = rom.rfind(POKEMON_TERMINATOR, 0, index) + 1
    end = rom.find(POKEMON_TERMINATOR, index)
    if end < 0:
        end = len(rom) - 1
    return rom[start : end + 1]


def _find_string_containing(rom: bytes, needle: str, must_have: str) -> bytes:
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


class TestEllipsisPausesInBuiltRom:
    def test_rival_snooping_dialogue_has_ellipsis_not_quote(self, fr_rom_bytes):
        """« Bref… » (0x1F2D412) — the reported lone quote — is now the ellipsis."""
        s = _find_string_containing(fr_rom_bytes, "fouinent", "Bref")
        bref = TextEncoder.encode_pokemon("Bref")[:-1]
        at = s.find(bref)
        assert at != -1
        after = s[at + len(bref)]
        assert after == _ELLIPSIS_BYTE, (
            f"« Bref » should be followed by the 0xB0 ellipsis, got {after:#x}"
        )
        assert _OPEN_QUOTE_BYTE not in s and _CLOSE_QUOTE_BYTE not in s, (
            "the snooping line is a pause, not a quotation — no 0xB1/0xB2"
        )

    def test_link_lost_message_pause(self, fr_rom_bytes):
        """« …a été interrompu… » carries the ellipsis glyph."""
        s = _find_string_containing(fr_rom_bytes, "interrompu", "COMMUNICATION")
        assert _ELLIPSIS_BYTE in s, "the link-interrupted pause lost its ellipsis"

    def test_hesitation_run_collapsed_to_single_glyph(self, fr_rom_bytes):
        """« Toi… Meurs… » (English "You………/Die………") keeps single-beat pauses."""
        s = _find_string_containing(fr_rom_bytes, "Meurs", "Toi")
        assert _ELLIPSIS_BYTE in s
        # a run of 0xB0 was collapsed: no two adjacent ellipsis bytes
        assert bytes((_ELLIPSIS_BYTE, _ELLIPSIS_BYTE)) not in s, (
            "ellipsis run not collapsed to a single pause beat"
        )
