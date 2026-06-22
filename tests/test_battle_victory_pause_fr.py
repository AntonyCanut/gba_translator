"""
Build-independent guard for the end-of-battle VICTORY-announcement pause.

Context (ticket "Phrase fin combat", clarification)
----------------------------------------------------
At the end of a trainer battle the in-battle sequence is:

    "Vaincu <classe> <nom>!"   (0x3FD1C7, STRINGID_PLAYERDEFEATEDTRAINER)
    "Tu gagnes ¥<X> !"         (0x00A4C670, prize money)

The user reported that the phrase shown *right at / just after* "Vous avez
vaincu <Dresseur>", and *just before* the pokédollar gain, flashes by with no
time to read it ("on a pas le temps de la lire"). That phrase is this victory
announcement (0x3FD1C7).

Why {PAGE} (0xFB) alone was not enough
--------------------------------------
The announcement already ended with a page-break <0xFB>. In OVERWORLD text a
page break waits for a button press, but in BATTLE text it does NOT: advance is
driven by the battle script's frame timer (waitmessage), so the message
auto-advanced. Proof in the English ROM: the battle string table has two
"Wild <mon> appeared!" variants — one ending <0xFB> (auto-advance) and one
ending <0xFC><0x08><0x7F> (a 127-frame timed pause, ~2.1 s, readable). Battle
strings in that table use the timed pause FC 08, never the wait-for-button
FC 09 (which is used by the prize/loss strings in the 0xA4xxxx region instead).

The fix therefore appends the same timed pause the game itself uses for
"Wild <mon> appeared!{FC:08:7F}" (0x3FD2AA), placed BEFORE the page break so the
text is held on screen, then the box is cleared and the prize money follows.

Why the RAW token form (and not {PAUSE})
----------------------------------------
{PAUSE} is positionally mapped by apply_combined_fr onto an English FC 08
sequence — but the English victory announcement has NO FC 08 to map onto, so a
{PAUSE} token would consume the wrong/absent sequence or be written literally.
The reinsertion encoder only expands raw ``<0xXX>`` control tokens, so the pause
is written as the raw bytes ``<0xFC><0x08><0x7F>`` (3 bytes). The FR translation
is shorter than the English original, so the 3 bytes fit in the in-place slot
(no relocation).

Why a source-level test (no ROM required)
-----------------------------------------
``combined_fr.txt`` is volatile — bulk rewrites by other tooling can silently
revert a surgical edit. Reading the source of truth catches a revert in the fast
unit profile, before any rebuild.

Run standalone:  pytest tests/test_battle_victory_pause_fr.py -v
"""

import re
from pathlib import Path

COMBINED_FR = Path(__file__).resolve().parent.parent / "combined_fr.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

VICTORY_OFFSET = 0x3FD1C7
# Raw timed-pause control token (FC 08 7F = pause 127 frames ≈ 2.1 s),
# matching the game's own readable "Wild <mon> appeared!" timing.
_RAW_PAUSE = "<0xFC><0x08><0x7F>"
# Brace forms the encoder does NOT expand for an added pause (would be written
# literally, or mis-mapped positionally onto an absent English FC 08).
_BRACE_PAUSE_RE = re.compile(r"\{(?:PAUSE|PAUSE_UNTIL_PRESS|FC0?8|FC0?9)\}")
# Page break, written literally as \p in combined_fr.txt.
_PAGE = "\\p"
_PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


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


def test_victory_offset_present():
    live = _load_last_wins()
    assert VICTORY_OFFSET in live, "0x3FD1C7 missing from combined_fr.txt"


def test_victory_message_contains_raw_timed_pause():
    """The victory announcement must carry the raw FC 08 timed-pause token."""
    text = _load_last_wins()[VICTORY_OFFSET]
    assert _RAW_PAUSE in text, (
        "0x3FD1C7 must contain the raw timed-pause token <0xFC><0x08><0x7F> so "
        "the 'Vaincu <Dresseur>!' announcement stays readable before the prize "
        f"money; got: {text!r}"
    )


def test_victory_pause_precedes_page_break():
    """Pause must come BEFORE the \\p page break: hold the text, THEN clear."""
    text = _load_last_wins()[VICTORY_OFFSET]
    assert _PAGE in text, f"0x3FD1C7 should keep its page break; got: {text!r}"
    assert text.index(_RAW_PAUSE) < text.index(_PAGE), (
        "the timed pause must precede the page break, otherwise the box is "
        f"cleared before the pause holds the text: {text!r}"
    )


def test_victory_message_uses_raw_not_brace_pause():
    """Guard the positional-mapping gotcha: a brace pause has no English FC 08
    to map onto and would be written literally / mis-consume a sequence."""
    text = _load_last_wins()[VICTORY_OFFSET]
    assert not _BRACE_PAUSE_RE.search(text), (
        "0x3FD1C7 must use the RAW token <0xFC><0x08><0x7F>, not a brace form "
        f"({{PAUSE}}/{{FC08}}...) which the encoder does not expand here: {text!r}"
    )


def test_victory_message_two_placeholders():
    """Exactly two {placeholders} (trainer class + name), matching the two
    English <0xFD> codes, so apply_combined_fr's positional mapping stays
    balanced. The raw <0x..> pause is NOT a brace token and must not count."""
    text = _load_last_wins()[VICTORY_OFFSET]
    placeholders = _PLACEHOLDER_RE.findall(text)
    assert len(placeholders) == 2, (
        "0x3FD1C7 must keep exactly two brace placeholders (trainer class and "
        f"name); got {placeholders!r} in {text!r}"
    )
