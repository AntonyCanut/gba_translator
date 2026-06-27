"""
Build-independent unit tests guarding the "his son/daughter" speeches against
the re-introduction of a gender buffer (son/daughter, he/she).

Context (ticket "Variable de genre")
-------------------------------------
At the start of the game, Prof. Log told the female player::

    "Il est logique que son fille suive ses traces."

"son fille" is ungrammatical: the engine fills a child-gender buffer
(``<0xFD><0x02>`` / ``<0xFD><0x03>``) with the French word *fils* / *fille*,
but French needs the possessive to agree with the noun, which a runtime
buffer cannot do. The same buffer appears in three sibling lines.

The fix drops the gender buffer entirely and hard-codes the neutral noun
*enfant* (matching the already-fixed precedent at ``0x77F1E3`` →
"Tu es son enfant !").

How the buffer is dropped
-------------------------
``19_build_translated_rom_generic._replace_placeholders`` maps each ``{...}``
placeholder (except ``{COLOR}``) *positionally* onto the English control codes,
in order; any English control code left unconsumed is silently dropped. By
removing the ``{STR_VAR_2}`` placeholder (and the raw ``<0xFD><0x03>`` token in
the lowercase variant), the trailing son/daughter buffer is never emitted.

Why a *source-level* test (no ROM required)
-------------------------------------------
``combined_fr.txt`` is volatile — bulk rewrites by other tooling can silently
revert a surgical edit. This test reads the source of truth directly (last
entry wins, exactly like the build) so a revert is caught in the fast unit
profile, before any rebuild.

Run standalone:  pytest tests/test_gender_neutral_child_fr.py -v
"""

import re
from pathlib import Path

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

# Tokens that render the player/child gender buffer the engine cannot localise.
_FORBIDDEN_TOKENS = ("{STR_VAR_2}", "<0xFD><0x02>", "<0xFD><0x03>")

# Offsets of the four "his son/daughter" speeches, with the neutral wording that
# must replace the gender buffer.
CHILD_BUFFER_OFFSETS = {
    0x1F2ECD5: "son enfant",   # Prof. Log intro ("Il est logique que son enfant…")
    0x1F012BD: "son enfant",   # "Tu es son enfant !" (FD03 variant of 0x77F1E3)
    0x1F01267: "l'enfant",     # "Es-tu l'enfant du légendaire Dresseur Aros ?"
    0x1EEAD3D: "mon enfant",   # "Je suis sûre que mon enfant va adorer cette tarte."
}


def _load_last_wins() -> dict[int, str]:
    """Parse combined_fr.txt into {offset:int -> French text}, last entry wins."""
    mapping: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            m = _LINE_RE.match(line)
            if m:
                mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def test_child_offsets_present():
    live = _load_last_wins()
    for off in CHILD_BUFFER_OFFSETS:
        assert off in live, f"0x{off:X} missing from combined_fr.txt"


def test_no_gender_buffer():
    """None of the four lines may carry a son/daughter (or he/she) buffer."""
    live = _load_last_wins()
    for off in CHILD_BUFFER_OFFSETS:
        text = live[off]
        for tok in _FORBIDDEN_TOKENS:
            assert tok not in text, (
                f"0x{off:X} still contains the gender buffer {tok!r}: {text!r}"
            )


def test_neutral_wording_present():
    """The reworked, gender-free wording must be the live value."""
    live = _load_last_wins()
    for off, expected in CHILD_BUFFER_OFFSETS.items():
        assert expected in live[off], (
            f"0x{off:X} lost the gender-neutral rework {expected!r}: {live[off]!r}"
        )


def test_no_son_fille_clash():
    """Guard the specific bug shown in the ticket screenshot ('son fille')."""
    live = _load_last_wins()
    assert "son enfant" in live[0x1F2ECD5]
    assert "son {STR_VAR_2}" not in live[0x1F2ECD5]
