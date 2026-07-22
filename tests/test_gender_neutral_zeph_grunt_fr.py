"""
Build-independent unit tests guarding seven dialogue lines against the
re-introduction of a player-gender pronoun buffer (him/her, he/she).

Context (ticket "Dialogue Genre")
---------------------------------
Several scripts buffer a *player-gender pronoun* and splice it into a line.
The gender-pronoun string table lives at ``0x789224``:

    him -> "le"   he -> "il"   her/she -> "elle"   He/She -> "Il/Elle"

In English the buffer is used as a third-person object pronoun, e.g.
"capable of finishing <0xFD><0x02> off" ("him/her"). French has no clean way
to render that buffer in object position: the masculine "him" -> "le" is
stranded after a preposition/verb ("...avec le", "...battre le"), which is
ungrammatical. The user reported exactly this: "...venir à bout de le".

The fix removes the buffer from each line and rephrases gender-neutrally
(2nd person "toi"/"te", or simply dropping a redundant possessive that the
French "son ami" already conveys). Subject-position uses (he/she -> "il/elle")
render fine and are intentionally left untouched.

Why a *source-level* test (no ROM required)
-------------------------------------------
``combined_fr.txt`` is volatile — bulk rewrites by other tooling can silently
revert a surgical edit. This test reads the source of truth directly so a
revert is caught in the fast unit profile, before any rebuild, with no ROM.

Placeholder-count guard (1F3296E)
---------------------------------
``apply_combined_fr.py`` maps ``{...}`` placeholders *positionally* onto the
English ``<0xFD>`` codes only when ``nb placeholders == nb FD codes``. The
English of 0x1F3296E has exactly one FD code, so reducing the line to a single
``{COLOR}`` placeholder would make the mapping fire and replace ``{COLOR}`` with
the gender buffer. We therefore assert the line carries *no* brace placeholder
at all (the colour is written as the raw ``<0xFC><0x01><0x04>`` token instead).

Run standalone:  pytest tests/test_gender_neutral_zeph_grunt_fr.py -v
"""

import re
from pathlib import Path

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

# Gendered player-pronoun buffers (object him/her = FD02, subject he/she = FD03,
# capitalised He/She = FD04). FD01 (player/entity NAME) is allowed — it is not
# gendered. {PLAYER} = FD01 likewise.
_GENDER_BUFFER_RE = re.compile(r"<0xFD><0x0[234]>")
_STR_VAR_RE = re.compile(r"\{STR_VAR_\d\}")


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


# offset -> substrings the gender-free rework must keep.
NEUTRAL_OFFSETS = {
    0x1F3253B: ("Dis-moi, quel est", "ton nom ?"),
    0x1F32861: ("l'effrayer", "gagner un simple combat"),
    0x1F329AE: ("en finir avec toi",),          # Zeph: was "...avec {STR_VAR_1}" -> "le"
    0x1F3296E: ("te battre", "<0xFC><0x01><0x04>"),  # Ivory: was "battre {STR_VAR_1}"
    0x1F32A8E: ("J'aime bien ça chez toi.",),
    0x1F45482: ("rejoindre son ami !", "{PLAYER}"),  # drop redundant possessive buffer
    0x1FA6E9F: ("te frapper", "tu vas pleurer"),     # Grunt: was "frapper {STR_VAR_1}..."
}


def test_offsets_present():
    live = _load_last_wins()
    for off in NEUTRAL_OFFSETS:
        assert off in live, f"0x{off:X} missing from combined_fr.txt"


def test_no_gender_pronoun_buffer():
    """No line may carry a {STR_VAR_x} placeholder or a raw him/her/he buffer."""
    live = _load_last_wins()
    for off in NEUTRAL_OFFSETS:
        text = live[off]
        assert not _STR_VAR_RE.search(text), (
            f"0x{off:X} reintroduced a {{STR_VAR_x}} buffer placeholder: {text!r}"
        )
        assert not _GENDER_BUFFER_RE.search(text), (
            f"0x{off:X} reintroduced a raw gender pronoun buffer "
            f"(<0xFD><0x02/03/04>): {text!r}"
        )


def test_neutral_wording_present():
    """The reworked, gender-free phrasing must be the live value."""
    live = _load_last_wins()
    for off, needles in NEUTRAL_OFFSETS.items():
        text = live[off]
        for needle in needles:
            assert needle in text, (
                f"0x{off:X} lost the gender-neutral rework {needle!r}: {text!r}"
            )


def test_color_line_has_no_placeholder():
    """0x1F3296E must keep ZERO brace placeholders: a lone {COLOR} would let
    apply_combined_fr's positional mapping consume the English FD buffer."""
    live = _load_last_wins()
    text = live[0x1F3296E]
    assert "{" not in text, (
        "0x1F3296E must contain no brace placeholder (raw colour token only); "
        f"got: {text!r}"
    )
