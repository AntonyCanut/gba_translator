"""
Build-independent guard for the "door forced shut" message at the exit of
the Shadow Lair (repaire Ombre).

Context (issue #36)
--------------------
The English source (0x1F0B460) is "The door has been forced shut behind
you." The original FR translation, "La porte a été forcée et s'est
refermée derrière toi.", was ambiguous: "forcée" alone usually means a door
was broken into (forced OPEN), which contradicts "et s'est refermée"
(and closed itself) right after it — a reader flagged this as unclear.

The fix keeps the "door" imagery (the very next dialogue at 0x1F0B48A says
"La porte est solidement scellée." — the door being sealed shut, not a
wall) and removes the ambiguity: "La porte s'est refermée de force
derrière toi." unambiguously means the door closed by force behind the
player.

Why a source-level test (no ROM required)
------------------------------------------
``combined_fr.txt`` is volatile — bulk rewrites by other tooling can
silently revert a surgical edit. Reading the source of truth catches a
revert in the fast unit profile, before any rebuild.

Run standalone:  pytest tests/test_shadow_lair_door_message_fr.py -v
"""

import re
from pathlib import Path

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

DOOR_OFFSET = 0x1F0B460


def _load_last_wins() -> dict:
    """Parse combined_fr.txt into {offset:int -> French text}, last entry wins."""
    mapping = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            m = _LINE_RE.match(line)
            if not m:
                continue
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def test_door_offset_present():
    live = _load_last_wins()
    assert DOOR_OFFSET in live, "0x1F0B460 missing from combined_fr.txt"


def test_door_message_mentions_door_not_wall():
    """The follow-up dialogue (0x1F0B48A) still calls it "la porte" — keep
    the same subject here, don't switch to a wall/paroi."""
    text = _load_last_wins()[DOOR_OFFSET]
    assert "porte" in text.lower(), (
        f"0x1F0B460 must still refer to 'la porte' for consistency with the "
        f"'La porte est solidement scellée.' follow-up; got: {text!r}"
    )
    assert "paroi" not in text.lower()


def test_door_message_not_ambiguous_forcee():
    """Guard against the original ambiguity: 'forcée' alone implies the door
    was broken OPEN, contradicting a closing action right after it."""
    text = _load_last_wins()[DOOR_OFFSET]
    assert "a été forcée" not in text, (
        f"0x1F0B460 must not use the ambiguous 'a été forcée' phrasing "
        f"(reads as forced open, not shut); got: {text!r}"
    )
