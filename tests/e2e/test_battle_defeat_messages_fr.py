"""E2E: end-of-battle *defeat* messages render in French and pause to be read.

Ticket "Combats & Dialogues" (fin de combat)
--------------------------------------------
The provided save auto-launches a Black Belt ("Karatéka Mike") trainer battle.
When the player loses, the engine shows two strings from the battle string table
(gBattleStringsTable), at fixed offsets in the non-repointed engine region:

    0x00A4C689  player whiteout  : "You have no more Pokémon that can fight!"
    0x00A4C6FD  trainer loss     : "...that can fight!{PAGE}You lost against <class> <name>!"  (+ FC09 wait)

Both French entries overflowed their fixed slot, so the pipeline DROPPED them and
the slots kept their English bytes — the player saw English flashing by, and the
final line had no wait code. This test reads the exact bytes the battle renderer
consumes from the BUILT FR ROM:

  * the English source is verified first (the comparison the ticket asked for);
  * the French must be in place (no English fragment), fit the English slot
    (in-place injection -> FR length <= EN length), and the trainer-loss line
    must end with the wait-for-button code FC 09 so the phrase can be read.

A green result means losing to Karatéka Mike shows French defeat text that waits
for a button press, not English that flashes by.

Run standalone:  pytest tests/e2e/test_battle_defeat_messages_fr.py -v
"""

from __future__ import annotations

import pytest

from src.core.text_codec import POKEMON_TERMINATOR, TextDecoder

WHITEOUT_OFFSET = 0x00A4C689        # "You have no more Pokémon that can fight!"
LOST_TO_TRAINER_OFFSET = 0x00A4C6FD  # "...You lost against <class> <name>!" + FC09

_FC09_WAIT = b"\xfc\x09"  # PAUSE_UNTIL_PRESS — wait for a button press

_ENGLISH_MARKERS = ("You have no more", "that can fight", "You lost against")


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

    def test_english_whiteout_is_english(self, en_bytes):
        text = _decode(_string_at(en_bytes, WHITEOUT_OFFSET))
        assert "You have no more" in text and "fight" in text, text

    def test_english_trainer_loss_is_english_and_waits(self, en_bytes):
        raw = _string_at(en_bytes, LOST_TO_TRAINER_OFFSET)
        text = _decode(raw)
        assert "You lost against" in text, text
        # English original already waits for a button press at the end.
        assert raw.endswith(_FC09_WAIT + bytes([POKEMON_TERMINATOR])), raw.hex()


class TestFrenchDefeatMessages:
    """The built FR ROM must show French defeat text, in place, that pauses."""

    def test_whiteout_is_french_in_place(self, en_bytes, fr_bytes):
        raw = _string_at(fr_bytes, WHITEOUT_OFFSET)
        text = _decode(raw)
        for marker in _ENGLISH_MARKERS:
            assert marker not in text, f"0xA4C689 still English: {text!r}"
        assert "Pokémon" in text, f"0xA4C689 not French: {text!r}"
        # In-place injection: FR must not exceed the English slot length.
        en_len = len(_string_at(en_bytes, WHITEOUT_OFFSET))
        assert len(raw) <= en_len, (
            f"0xA4C689 FR {len(raw)}B exceeds EN slot {en_len}B -> would be dropped"
        )

    def test_trainer_loss_is_french_in_place_and_waits(self, en_bytes, fr_bytes):
        raw = _string_at(fr_bytes, LOST_TO_TRAINER_OFFSET)
        text = _decode(raw)
        for marker in _ENGLISH_MARKERS:
            assert marker not in text, f"0xA4C6FD still English: {text!r}"
        assert "Pokémon" in text, f"0xA4C6FD not French: {text!r}"
        # The defeat line must wait for a button press (FC 09 right before FF),
        # otherwise the player has no time to read it.
        assert raw.endswith(_FC09_WAIT + bytes([POKEMON_TERMINATOR])), (
            f"0xA4C6FD must end with the FC09 wait code; got {raw.hex()}"
        )
        en_len = len(_string_at(en_bytes, LOST_TO_TRAINER_OFFSET))
        assert len(raw) <= en_len, (
            f"0xA4C6FD FR {len(raw)}B exceeds EN slot {en_len}B -> would be dropped"
        )

    def test_trainer_loss_keeps_class_and_name_buffers(self, fr_bytes):
        """The <class>/<name> buffers (FD 1C / FD 1D) must survive so the line
        renders the real trainer ("Tu perds face à Karatéka Mike !")."""
        raw = _string_at(fr_bytes, LOST_TO_TRAINER_OFFSET)
        assert b"\xfd\x1c" in raw, "trainer class buffer FD1C lost"
        assert b"\xfd\x1d" in raw, "trainer name buffer FD1D lost"
