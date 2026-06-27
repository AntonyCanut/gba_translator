"""
Build-independent guard for the end-of-battle *defeat* messages.

Context (ticket "Combats & Dialogues" — fin de combat)
------------------------------------------------------
When the player loses a trainer battle (reported against the Karatéka Mike
fight that the provided save auto-launches), the engine shows, from the battle
string table (gBattleStringsTable):

    0x00A4C689  "You have no more Pokémon\nthat can fight!"      (STRINGID, page break)
    0x00A4C6FD  "...that can fight!{PAGE}You lost against\n<class> <name>!"  (+ FC09 wait)

Both French entries used to OVERFLOW their fixed engine-region slot
(0xA4C689: 47 > 41 bytes; 0xA4C6FD: 120 > 66 bytes). The battle-string region is
NOT repointed by the pipeline, so an overflowing entry is dropped and the slot
keeps its ENGLISH bytes — the player saw English flashing by ("rien ne
correspond / la traduction n'est pas la bonne"), and the final line lacked the
wait code so there was "pas le temps de lire la phrase de fin".

Fix: shorten the French to fit each slot IN PLACE, keep the raw wait token
``<0xFC><0x09>`` on the trainer-loss line (so it waits for a button press), and
use raw buffer tokens ``<0xFD><0x1C>`` / ``<0xFD><0x1D>`` (class / name) rather
than the brace forms the encoder does not expand.

Why a source-level test (no ROM required)
-----------------------------------------
``combined_fr.txt`` is volatile — bulk rewrites by other tooling can silently
revert a surgical edit. Reading the source of truth catches a revert in the
fast unit profile, before any rebuild. The byte-level proof lives in
``tests/e2e/test_battle_defeat_messages_fr.py``.

Sibling of test_battle_money_pause_fr.py / test_battle_victory_pause_fr.py.

Run standalone:  pytest tests/test_battle_defeat_pause_fr.py -v
"""

import re
from pathlib import Path

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

# Player whiteout line (page break, no trailing wait) and the trainer-loss line.
WHITEOUT_OFFSET = 0x00A4C689
LOST_TO_TRAINER_OFFSET = 0x00A4C6FD

_RAW_FC09 = "<0xFC><0x09>"          # raw wait-for-button control token
_BRACE_PAUSE_RE = re.compile(r"\{(?:PAUSE_UNTIL_PRESS|FC0?9)\}")
# Brace buffer tokens the encoder does NOT expand (must be raw <0xFD><0x1C>...).
_BRACE_BUFFER_RE = re.compile(r"\{(?:B_TRAINER1_CLASS|B_TRAINER1_NAME|FD1[CD])\}")
# Residual English fragments that would mean the FR entry was reverted/dropped.
_ENGLISH_MARKERS = ("You have no more", "that can fight", "You lost against")


def _load_last_wins() -> dict[int, str]:
    """Parse combined_fr.txt into {offset:int -> French text}, last entry wins."""
    mapping: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            m = _LINE_RE.match(line)
            if not m:
                continue
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def test_defeat_offsets_present():
    live = _load_last_wins()
    assert WHITEOUT_OFFSET in live, "0xA4C689 missing from combined_fr.txt"
    assert LOST_TO_TRAINER_OFFSET in live, "0xA4C6FD missing from combined_fr.txt"


def test_defeat_messages_are_french_not_english():
    """Neither defeat line may keep English fragments (would mean it was dropped)."""
    live = _load_last_wins()
    for off in (WHITEOUT_OFFSET, LOST_TO_TRAINER_OFFSET):
        text = live[off]
        for marker in _ENGLISH_MARKERS:
            assert marker not in text, (
                f"0x{off:06X} still carries English {marker!r}: {text!r}"
            )
        # A real French translation must mention "Pokémon".
        assert "Pokémon" in text, f"0x{off:06X} does not look French: {text!r}"


def test_trainer_loss_line_ends_with_raw_pause_token():
    """The trainer-loss line must end with the raw FC09 wait code so the final
    phrase pauses ("on a pas le temps de lire la phrase de fin")."""
    text = _load_last_wins()[LOST_TO_TRAINER_OFFSET].rstrip("\\n").rstrip()
    assert text.endswith(_RAW_FC09), (
        "0xA4C6FD must end with the raw wait token <0xFC><0x09> so the defeat "
        f"line waits for a button press; got: {text!r}"
    )


def test_defeat_messages_use_raw_tokens_not_brace_forms():
    """Guard the relocation gotcha: brace pause/buffer tokens are written
    literally by the encoder (e.g. '?PAUSE?UNTIL?PRESS?')."""
    live = _load_last_wins()
    for off in (WHITEOUT_OFFSET, LOST_TO_TRAINER_OFFSET):
        text = live[off]
        assert not _BRACE_PAUSE_RE.search(text), (
            f"0x{off:06X} must use raw <0xFC><0x09>, not a brace pause form: {text!r}"
        )
        assert not _BRACE_BUFFER_RE.search(text), (
            f"0x{off:06X} must use raw buffer tokens <0xFD><0x1C>/<0xFD><0x1D>, "
            f"not brace forms: {text!r}"
        )
