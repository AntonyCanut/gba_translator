"""
Build-independent unit tests guarding the Aklove/Hoopa speeches against the
re-introduction of a player-gender pronoun variable.

Context (ticket "Cohérence dialogue")
--------------------------------------
Aklove's confrontation speech existed in two script variants:

* ``0x1F3A6F8`` — "En réalité, Hoopa agissait de son propre chef…" (the one
  seen in-game: "Une fois {STR_VAR_2} parti, Hoopa devra m'accepter, MOI…")
* ``0x7D4DD8``  — "Aklove : En fait, c'était Hoopa…" (a sibling variant)

Both referenced ``{STR_VAR_2}`` (English control code ``<0xFD><0x03>``), a buffer
that the engine fills with the player's gender pronoun *he/she* → *il/elle*.
French has no clean way to render that buffer (the project's own
``patch_gendered_buffers_fr.py`` notes "she/She → elle/Elle … don't fit;
left as-is"), so the line rendered ungrammatically ("Une fois il parti…").

The fix reworks both lines to drop the pronoun entirely — referring to the
player by name (``{PLAYER}`` = ``<0xFD><0x01>``) or by a gender-neutral verb
phrase ("m'en débarrasser", "Une fois cela fait").

Why a *source-level* test (no ROM required)
-------------------------------------------
``combined_fr.txt`` is volatile — bulk rewrites by other tooling can silently
revert a surgical edit. This test reads the source of truth directly so a
revert is caught in the fast unit profile, before any rebuild, with no ROM.

Placeholder-count guard
-----------------------
The build maps each ``{...}`` placeholder (except ``{COLOR}``) *positionally*
onto the English control codes, in order. For these offsets the English order
places an ``<0xFD><0x03>`` (gender pronoun) that must NOT be consumed by any
placeholder. Keeping ``{STR_VAR_2}`` out of the line is the durable guarantee;
we also assert ``{STR_VAR_2}`` never reappears.

Run standalone:  pytest tests/test_gender_neutral_aklove_fr.py -v
"""

import re
from pathlib import Path

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


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


# Offsets of the two Aklove/Hoopa speech variants.
AKLOVE_OFFSETS = (0x1F3A6F8, 0x7D4DD8)


def test_aklove_offsets_present():
    live = _load_last_wins()
    for off in AKLOVE_OFFSETS:
        assert off in live, f"0x{off:X} missing from combined_fr.txt"


def test_no_gender_pronoun_variable():
    """Neither Aklove line may carry {STR_VAR_2} (the he/she buffer <0xFD><0x03>)."""
    live = _load_last_wins()
    for off in AKLOVE_OFFSETS:
        text = live[off]
        assert "{STR_VAR_2}" not in text, (
            f"0x{off:X} still contains the gender pronoun variable {{STR_VAR_2}}: {text!r}"
        )


def test_gender_neutral_wording_present():
    """The reworked, gender-free phrasing must be the live value."""
    live = _load_last_wins()
    for off in AKLOVE_OFFSETS:
        text = live[off]
        assert "m'en débarrasser" in text, (
            f"0x{off:X} lost the gender-neutral rework 'm'en débarrasser': {text!r}"
        )
        assert "cela fait" in text, (
            f"0x{off:X} lost the gender-neutral rework 'Une fois cela fait': {text!r}"
        )


def test_player_name_still_referenced():
    """The player is still named via {PLAYER} (<0xFD><0x01>), not a pronoun."""
    live = _load_last_wins()
    for off in AKLOVE_OFFSETS:
        assert "{PLAYER}" in live[off], f"0x{off:X} dropped the {{PLAYER}} reference"
