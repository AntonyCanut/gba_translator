"""
Build-independent guard for the end-of-battle prize-money message pause.

Context (ticket "Phrase fin combat")
------------------------------------
After defeating a trainer, the in-battle sequence is:

    "Vaincu <classe> <nom>!"   (0x3FD1C7, already ends with <0xFB> = wait)
    "Tu gagnes ¥<X> !"         (0x00A4C670, STRINGID_PLAYERGOTMONEY)
    -> the prize money is banked

The money line (0xA4C670) auto-advanced without any wait code, so the player
had no time to read it ("on a pas le temps de la lire"). Its sibling *loss*
messages (0xA4C6B3, 0xA4C740) already end with the wait-for-button code
(FC 09), so the fix simply aligns the win message with them.

Why the RAW token form (and not {PAUSE_UNTIL_PRESS})
----------------------------------------------------
The reinsertion/relocation encoder only recognises raw ``<0xXX>`` control
tokens (regex ``<0x([0-9A-Fa-f]{2})>``). The brace form ``{PAUSE_UNTIL_PRESS}``
has no definition in the encoder, so on a string that must be RELOCATED (the FR
text + a literally-encoded ``{PAUSE_UNTIL_PRESS}`` overflows this short slot) it
is written as literal text — verified in a build: the ROM showed
``Tu gagnes ¥ !?PAUSE?UNTIL?PRESS?``. Written as the raw byte token
``<0xFC><0x09>`` it is 2 bytes, the string stays in its 25-byte slot, and the
built ROM decodes to ``Tu gagnes ¥<buffer> !<FC09>`` (ends FC 09 FF).

Why a source-level test (no ROM required)
-----------------------------------------
``combined_fr.txt`` is volatile — bulk rewrites by other tooling can silently
revert a surgical edit. Reading the source of truth catches a revert in the
fast unit profile, before any rebuild.

Run standalone:  pytest tests/test_battle_money_pause_fr.py -v
"""

import re
from pathlib import Path

COMBINED_FR = Path(__file__).resolve().parent.parent / "combined_fr.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

MONEY_OFFSET = 0x00A4C670
# Raw wait-for-button control token (FC 09 = PAUSE_UNTIL_PRESS).
_RAW_FC09 = "<0xFC><0x09>"
# Brace forms the encoder does NOT expand (would be written as literal text on
# a relocated string).
_BRACE_PAUSE_RE = re.compile(r"\{(?:PAUSE_UNTIL_PRESS|FC0?9)\}")
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


def test_money_offset_present():
    live = _load_last_wins()
    assert MONEY_OFFSET in live, "0xA4C670 missing from combined_fr.txt"


def test_money_message_ends_with_raw_pause_token():
    """The win prize message must end with the raw FC09 wait-for-button code."""
    text = _load_last_wins()[MONEY_OFFSET].rstrip("\\n").rstrip()
    assert text.endswith(_RAW_FC09), (
        "0xA4C670 must end with the raw wait token <0xFC><0x09> so the prize "
        f"line pauses before the money is banked; got: {text!r}"
    )


def test_money_message_uses_raw_not_brace_pause():
    """Guard the relocation gotcha: the brace form would be written literally."""
    text = _load_last_wins()[MONEY_OFFSET]
    assert not _BRACE_PAUSE_RE.search(text), (
        "0xA4C670 must use the RAW token <0xFC><0x09>, not a brace form "
        f"({{PAUSE_UNTIL_PRESS}}/{{FC09}}) which is not expanded on relocation: {text!r}"
    )


def test_money_message_single_placeholder():
    """Exactly one {placeholder} (the money buffer), matching the single English
    <0xFD> code, so apply_combined_fr's positional mapping stays balanced."""
    text = _load_last_wins()[MONEY_OFFSET]
    placeholders = _PLACEHOLDER_RE.findall(text)
    assert len(placeholders) == 1, (
        f"0xA4C670 must keep exactly one brace placeholder (the money buffer); "
        f"got {placeholders!r} in {text!r}"
    )
