"""
Build-independent guard for the end-of-battle VICTORY-announcement.

Context (ticket "Combats & Dialogues", follow-up)
-------------------------------------------------
At the end of a trainer battle the in-battle sequence is:

    "Tu as battu <classe> <nom> !"   (0x3FD1C7, STRINGID_PLAYERDEFEATEDTRAINER)
    "Tu gagnes ¥<X> !"               (0x00A4C670, prize money)

Two user reports drove the current wording AND the current pause:

1. Wording — the terse "Vaincu <Dresseur> !" read poorly. The user asked for a
   natural sentence "du style « Tu as battu <Dresseur> »". So the announce now
   reads "Tu as battu {classe}\\n{nom} !".

2. Timing — "juste après le texte vaincu xxx, ça passe trop vite". A first fix
   appended a TIMED pause <0xFC><0x08><0x7F> (127 frames ≈ 2.1 s); the user
   reported it STILL flashed by. A fixed timer is subjective and was not enough.

Why FC 09 (wait-for-button), not the timed pause
------------------------------------------------
The sibling prize line 0xA4C670 ("Tu gagnes ¥<X> !") ends with the
wait-for-button code <0xFC><0x09> (PAUSE_UNTIL_PRESS): the player presses A to
continue, so the line is *guaranteed* readable regardless of timer length. That
line ships in the build the user is already playing and does NOT freeze, which
proves FC 09 is handled safely by the battle message system. The victory
announce now mirrors that ending: it holds until the player presses a button,
the strongest possible fix for "passes too fast". No page break is needed
(the prize sibling has none either — the battle engine clears the box).

Why the RAW token form (and not {PAUSE_UNTIL_PRESS})
----------------------------------------------------
The reinsertion encoder only expands raw ``<0xXX>`` control tokens. A brace form
({PAUSE_UNTIL_PRESS}/{FC09}) is positionally mapped by apply_combined_fr onto an
English FC sequence that does not exist here, so it would be written literally
or mis-consume a buffer code. The pause is therefore the raw bytes
``<0xFC><0x09>`` (2 bytes).

Byte budget (in place, slot = 21 bytes incl. terminator; 3 pointers
0xD776C/0x3FE410/0x9BE104 are NOT repointed by the pipeline):
    "Tu as battu"(11) + sp(1) + FD1C(2) + FE/\\n(1) + FD1D(2) + "!"(1)
    + FC09(2) = 20 bytes, + terminator FF = 21. Fits exactly.

Why a source-level test (no ROM required)
-----------------------------------------
``combined_fr.txt`` is volatile — bulk rewrites by other tooling can silently
revert a surgical edit. Reading the source of truth catches a revert in the fast
unit profile, before any rebuild.

Run standalone:  pytest tests/test_battle_victory_pause_fr.py -v
"""

import re
from pathlib import Path

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

VICTORY_OFFSET = 0x3FD1C7
# Raw wait-for-button control token (FC 09 = PAUSE_UNTIL_PRESS): the player
# presses A to continue, so the announce is readable no matter the timer.
_RAW_FC09 = "<0xFC><0x09>"
# The superseded timed pause: a fixed timer the user reported as still too fast.
_RAW_TIMED = "<0xFC><0x08>"
# Brace forms the encoder does NOT expand for an added pause (would be written
# literally, or mis-mapped positionally onto an absent English FC sequence).
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


def test_victory_message_uses_requested_wording():
    """The announce must read the natural sentence the user asked for, not the
    terse 'Vaincu <Dresseur>'."""
    text = _load_last_wins()[VICTORY_OFFSET]
    assert text.startswith("Tu as battu"), (
        "0x3FD1C7 must read 'Tu as battu <classe> <nom> !' (user request), "
        f"not the terse 'Vaincu ...'; got: {text!r}"
    )
    assert "Vaincu" not in text, f"0x3FD1C7 still uses 'Vaincu': {text!r}"


def test_victory_message_ends_with_wait_for_button():
    """The announce must end with the raw FC09 wait-for-button token so the
    player controls advancement — the definitive fix for 'passes too fast'."""
    text = _load_last_wins()[VICTORY_OFFSET].rstrip("\\n").rstrip()
    assert text.endswith(_RAW_FC09), (
        "0x3FD1C7 must end with the raw wait token <0xFC><0x09> so the "
        f"'Tu as battu <Dresseur> !' announce waits for a press; got: {text!r}"
    )


def test_victory_message_drops_superseded_timed_pause():
    """The timed pause <0xFC><0x08><0x7F> the user reported as still too fast
    must be gone (replaced by the wait-for-button code)."""
    text = _load_last_wins()[VICTORY_OFFSET]
    assert _RAW_TIMED not in text, (
        "0x3FD1C7 must NOT keep the timed pause <0xFC><0x08>..; it was reported "
        f"as still flashing by — use the wait-for-button code instead: {text!r}"
    )


def test_victory_message_has_no_page_break():
    """Mirror the prize sibling 0xA4C670: end on FC 09, no page break — the
    battle engine clears the box after the press."""
    text = _load_last_wins()[VICTORY_OFFSET]
    assert _PAGE not in text, (
        "0x3FD1C7 must not carry a page break: it ends on the FC09 wait like the "
        f"prize line; the engine clears the box: {text!r}"
    )


def test_victory_message_uses_raw_not_brace_pause():
    """Guard the positional-mapping gotcha: a brace pause has no English FC
    sequence to map onto and would be written literally / mis-consume a code."""
    text = _load_last_wins()[VICTORY_OFFSET]
    assert not _BRACE_PAUSE_RE.search(text), (
        "0x3FD1C7 must use the RAW token <0xFC><0x09>, not a brace form "
        f"({{PAUSE}}/{{FC09}}...) which the encoder does not expand here: {text!r}"
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
