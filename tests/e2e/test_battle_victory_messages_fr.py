"""E2E: end-of-battle *victory* messages render in French and wait to be read.

Ticket "Combats & Dialogues" — follow-up
----------------------------------------
The defeat path is already covered by ``test_battle_defeat_messages_fr.py``.
This test is its mirror for the WIN path. When the player *wins* a trainer
battle the engine shows two strings, at fixed offsets the pipeline does NOT
repoint:

    0x003FD1C7  victory announce : "You defeated <class> <name>!"  (gBattleStringsTable)
    0x00A4C670  prize money      : "You got ¥<X> for winning!"     (0xA4xxxx region)

Both English lines flash by (the announce ends with a page break only, which in
BATTLE text auto-advances on the frame timer; the money line has no wait code at
all). The fix makes BOTH end with the wait-for-button code FC 09
(PAUSE_UNTIL_PRESS): the player presses A to continue, so each line is readable
no matter the timer.

Why FC 09 on the victory announce (and not the timed pause FC 08)
-----------------------------------------------------------------
A first attempt appended a TIMED pause <0xFC><0x08><0x7F> (~2.1 s) to the
announce; the user reported it STILL passed too fast (a fixed timer is
subjective). The sibling prize line already ships with FC 09 in the build the
user plays and does NOT freeze — proving FC 09 is handled safely by the battle
message system — so the announce now mirrors it: end on FC 09, no page break
(the battle engine clears the box after the press). The wording also changed
from the terse "Vaincu <Dresseur> !" to the natural "Tu as battu <Dresseur> !"
the user asked for.

Both English originals are shorter-bounded slots that are NOT repointed, so the
French must fit in place (FR length <= EN length) or the pipeline drops it and
the slot keeps its English bytes.

A green result means winning against Karatéka Mike shows French victory text
that waits for a button press, then a French prize line that also waits — not
English that flashes by.

Run standalone:  pytest tests/e2e/test_battle_victory_messages_fr.py -v
"""

from __future__ import annotations

import pytest

from src.core.text_codec import POKEMON_TERMINATOR, TextDecoder

VICTORY_OFFSET = 0x003FD1C7  # "You defeated <class> <name>!"  (battle string table)
MONEY_OFFSET = 0x00A4C670    # "You got ¥<X> for winning!"     (0xA4xxxx region)

_FC09_WAIT = b"\xfc\x09"       # PAUSE_UNTIL_PRESS — wait for a button press
_FC08_TIMED = b"\xfc\x08\x7f"  # timed pause, 127 frames (~2.1 s), battle convention
_PAGE_BREAK = b"\xfb"

_ENGLISH_MARKERS = ("You defeated", "You got", "for winning")


def _string_at(rom: bytes, offset: int) -> bytes:
    """Raw bytes of the FF-terminated string starting at `offset` (incl. FF)."""
    end = rom.find(POKEMON_TERMINATOR, offset)
    assert end != -1, f"no terminator after 0x{offset:06X}"
    return rom[offset : end + 1]


def _decode(raw: bytes) -> str:
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


@pytest.fixture
def en_bytes(en_rom_path):
    return en_rom_path.read_bytes()


@pytest.fixture
def fr_bytes(fr_rom_path):
    return fr_rom_path.read_bytes()


class TestEnglishReference:
    """Document the English source the ticket asked us to look at."""

    def test_english_victory_is_english_and_does_not_wait(self, en_bytes):
        raw = _string_at(en_bytes, VICTORY_OFFSET)
        text = _decode(raw)
        assert "You defeated" in text, text
        # The English announce ends with a page break only — in battle text that
        # is advanced by the frame timer, never a button press: this is exactly
        # why it flashed by and the French adds a timed pause.
        assert raw.endswith(_PAGE_BREAK + bytes([POKEMON_TERMINATOR])), raw.hex()
        assert _FC08_TIMED not in raw, raw.hex()

    def test_english_money_is_english_and_does_not_wait(self, en_bytes):
        raw = _string_at(en_bytes, MONEY_OFFSET)
        text = _decode(raw)
        assert "You got" in text and "for winning" in text, text
        # English win money line carries no wait code at all.
        assert _FC09_WAIT not in raw, raw.hex()


class TestFrenchVictoryMessages:
    """The built FR ROM must show French victory text, in place, that pauses."""

    def test_victory_announce_is_french_in_place(self, en_bytes, fr_bytes):
        raw = _string_at(fr_bytes, VICTORY_OFFSET)
        text = _decode(raw)
        for marker in _ENGLISH_MARKERS:
            assert marker not in text, f"0x3FD1C7 still English: {text!r}"
        assert "Tu as battu" in text, (
            f"0x3FD1C7 must read 'Tu as battu ...' (user request): {text!r}"
        )
        assert "Vaincu" not in text, f"0x3FD1C7 still terse 'Vaincu': {text!r}"
        # In-place injection: FR must not exceed the English slot length.
        en_len = len(_string_at(en_bytes, VICTORY_OFFSET))
        assert len(raw) <= en_len, (
            f"0x3FD1C7 FR {len(raw)}B exceeds EN slot {en_len}B -> would be dropped"
        )

    def test_victory_announce_waits_for_button(self, fr_bytes):
        """The announce must end with the wait-for-button code FC 09 so the
        player presses to continue — the definitive fix for "passes too fast".
        Mirrors the prize sibling: end on FC 09, no page break."""
        raw = _string_at(fr_bytes, VICTORY_OFFSET)
        assert raw.endswith(_FC09_WAIT + bytes([POKEMON_TERMINATOR])), (
            f"0x3FD1C7 must end with the FC09 wait code; got {raw.hex()}"
        )
        # The superseded timed pause (reported as still too fast) must be gone.
        assert _FC08_TIMED not in raw, (
            f"0x3FD1C7 must not keep the timed pause FC 08 7F: {raw.hex()}"
        )
        # No page break — like the prize line; the battle engine clears the box.
        assert _PAGE_BREAK not in raw, (
            f"0x3FD1C7 must not carry a page break: {raw.hex()}"
        )

    def test_victory_announce_keeps_class_and_name_buffers(self, fr_bytes):
        """The <class>/<name> buffers (FD 1C / FD 1D) must survive so the line
        renders the real trainer ("Tu as battu Karatéka Mike !")."""
        raw = _string_at(fr_bytes, VICTORY_OFFSET)
        assert b"\xfd\x1c" in raw, "trainer class buffer FD1C lost"
        assert b"\xfd\x1d" in raw, "trainer name buffer FD1D lost"

    def test_money_is_french_in_place_and_waits(self, en_bytes, fr_bytes):
        raw = _string_at(fr_bytes, MONEY_OFFSET)
        text = _decode(raw)
        for marker in _ENGLISH_MARKERS:
            assert marker not in text, f"0xA4C670 still English: {text!r}"
        assert "gagnes" in text, f"0xA4C670 not French: {text!r}"
        # The prize line must wait for a button press (FC 09 right before FF).
        assert raw.endswith(_FC09_WAIT + bytes([POKEMON_TERMINATOR])), (
            f"0xA4C670 must end with the FC09 wait code; got {raw.hex()}"
        )
        en_len = len(_string_at(en_bytes, MONEY_OFFSET))
        assert len(raw) <= en_len, (
            f"0xA4C670 FR {len(raw)}B exceeds EN slot {en_len}B -> would be dropped"
        )

    def test_money_keeps_amount_buffer(self, fr_bytes):
        """The ¥ amount buffer (FD 00) must survive so the real prize renders."""
        raw = _string_at(fr_bytes, MONEY_OFFSET)
        assert b"\xfd\x00" in raw, "money amount buffer FD00 lost"
