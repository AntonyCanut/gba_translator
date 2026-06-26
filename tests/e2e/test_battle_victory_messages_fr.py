"""E2E: end-of-battle *victory* messages render in French and pause to be read.

Ticket "Combats & Dialogues" — follow-up « Et en cas de victoire ? »
-------------------------------------------------------------------
The defeat path is already covered by ``test_battle_defeat_messages_fr.py``.
This test is its mirror for the WIN path: the user asked us to look at the
English version to understand why the end-of-battle phrase had no time to be
read, then verify the French in the BUILT ROM. When the player *wins* a trainer
battle the engine shows two strings, at fixed offsets the pipeline does NOT
repoint:

    0x003FD1C7  victory announce : "You defeated <class> <name>!"  (gBattleStringsTable)
    0x00A4C670  prize money      : "You got ¥<X> for winning!"     (0xA4xxxx region)

Why each needs a *different* pause code
---------------------------------------
* 0x3FD1C7 lives in the battle string table. In BATTLE text a page break <0xFB>
  does NOT wait for a button — it is advanced by the script's frame timer
  (waitmessage), so "You defeated X!" flashed by. The game's own readable battle
  lines (e.g. "Wild <mon> appeared!{FC:08:7F}") use the TIMED pause FC 08 7F
  (~127 frames ≈ 2.1 s). The fix appends that timed pause BEFORE the page break
  so the announce is held, then the box clears and the prize money follows.
* 0xA4C670 lives in the 0xA4xxxx region whose sibling prize/loss lines use the
  wait-for-button code FC 09. The win money line had no wait code at all, so the
  fix ends it with FC 09 (like the defeat lines).

Both English originals are shorter-bounded slots that are NOT repointed, so the
French must fit in place (FR length <= EN length) or the pipeline drops it and
the slot keeps its English bytes.

A green result means winning against Karatéka Mike shows French victory text
that stays on screen long enough to read, then a French prize line that waits
for a button press — not English that flashes by.

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
        assert "Vaincu" in text, f"0x3FD1C7 not French: {text!r}"
        # In-place injection: FR must not exceed the English slot length.
        en_len = len(_string_at(en_bytes, VICTORY_OFFSET))
        assert len(raw) <= en_len, (
            f"0x3FD1C7 FR {len(raw)}B exceeds EN slot {en_len}B -> would be dropped"
        )

    def test_victory_announce_holds_with_timed_pause(self, fr_bytes):
        """The announce must carry the timed pause FC 08 7F BEFORE the page break
        so "Vaincu <Dresseur> !" stays on screen long enough to read."""
        raw = _string_at(fr_bytes, VICTORY_OFFSET)
        assert _FC08_TIMED in raw, (
            f"0x3FD1C7 must hold with the timed pause FC 08 7F; got {raw.hex()}"
        )
        # Pause holds the text, THEN the page break clears the box.
        assert raw.endswith(_PAGE_BREAK + bytes([POKEMON_TERMINATOR])), raw.hex()
        assert raw.index(_FC08_TIMED) < raw.rindex(_PAGE_BREAK), (
            f"the timed pause must precede the page break: {raw.hex()}"
        )

    def test_victory_announce_keeps_class_and_name_buffers(self, fr_bytes):
        """The <class>/<name> buffers (FD 1C / FD 1D) must survive so the line
        renders the real trainer ("Vaincu Karatéka Mike !")."""
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
