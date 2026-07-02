"""
Build-independent unit tests guarding eleven dialogue lines against the
re-introduction of a player-gender pronoun buffer (him/her, he/she, He/She).

Context (ticket "Suppression genre")
------------------------------------
Several scripts buffer a *player-gender pronoun* into {STR_VAR_x} and splice
it into a line. The pronoun string tables live at ``0x789224`` (him/he/He/
her/she/She) and ``0x1FA764E`` (him/her/his); the FR ROM renders them as
le/il/Il/la/elle/Elle.

In French the buffer is unrenderable in most positions the English scripts
use it in — the user reported "Elle K.O., Hoopa." (0x1F2CC7E) and "Je ne
sais pas ce que tu voulais elle faire," (0x1F2CDA7). The fix removes the
buffer from each line and rephrases gender-neutrally ("L'intrus",
neutral dative "lui", "C'est toi", "ce môme", "jeune personne", …).

Positional-mapping traps encoded here
-------------------------------------
* ``apply_combined_fr.py`` maps ``{...}`` placeholders positionally onto the
  English control tokens only when the counts match. Lines whose English
  carries exactly one FD code must therefore carry ZERO brace placeholders
  (pauses/colours written as raw ``<0xNN>`` tokens instead).
* ``19_build_translated_rom_generic.py`` pops one English control sequence
  per non-{COLOR} placeholder — unconsumed sequences (the gender FD) are
  dropped, which is exactly what we rely on.

Why a *source-level* test (no ROM required)
-------------------------------------------
``combined_fr.txt`` is volatile — bulk rewrites by other tooling can silently
revert a surgical edit. This test reads the source of truth directly so a
revert is caught in the fast unit profile, before any rebuild, with no ROM.

Run standalone:  pytest tests/test_gender_neutral_hoopa_estate_fr.py -v
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
_BRACE_RE = re.compile(r"\{[^}]+\}")


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


# offset -> (substrings the gender-free rework must keep,
#            exact number of {...} brace placeholders the line must carry —
#            chosen so the positional mapping in apply_combined_fr NEVER
#            fires against the English FD count).
NEUTRAL_OFFSETS = {
    # Hoopa warehouse scene (user screenshots): EN "{He/She} is unconscious"
    # and "what you wanted {him/her} for".
    0x1F2CC7E: (("L'intrus est K.O., Hoopa.",), 0),
    0x1F2CDA7: (("ce que tu lui", "<0xFC><0x08><0x18>"), 0),
    # Aros descendant scene: "the {son/daughter} of the legendary Aros".
    0x7527C2: (("Serais-tu l'enfant du",), 2),   # two {COLOR} tokens only
    0x77F52F: (("Bonjour, enfant du légendaire",), 0),
    # Oddish-leaves sniffer: "Hey there {him/her}…"
    0x753107: (("Salut…",), 0),
    # Officer after Mirskle bust: "{He/She} probably just fell victim…"
    0x78910F: (("C'est sans doute une victime",), 0),
    # Dresco Gym helper: "that {boy/girl} who assisted us".
    0x7BCA5F: (("C'est toi qui nous as aidés",), 0),
    # Terror Granbull boss: "NOT to underestimate {him/her}!" (twice).
    0x1FA6F85: (("sous-estimer\nce môme", "Vous l'avez\nsous-estimé"), 0),
    # Real-estate gentleman: "young {him/her}" ×3.
    0x1FA7D3B: (("jeune\\ppersonne",), 0),
    0x1FA804E: (("jeune\\ppersonne",), 0),
    0x1FA8CA1: (("jeune\\ppersonne",), 0),
}


def test_offsets_present():
    live = _load_last_wins()
    for off in NEUTRAL_OFFSETS:
        assert off in live, f"0x{off:X} missing from combined_fr.txt"


def test_no_gender_pronoun_buffer():
    """No line may carry a {STR_VAR_x} placeholder or a raw gender buffer."""
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
    for off, (needles, _) in NEUTRAL_OFFSETS.items():
        text = live[off].replace("\\n", "\n").replace("\\l", "\n")
        raw = live[off]
        for needle in needles:
            assert needle in text or needle in raw, (
                f"0x{off:X} lost the gender-neutral rework {needle!r}: {raw!r}"
            )


def test_placeholder_count_dodges_positional_mapping():
    """Each line must carry the exact brace count that keeps both positional
    mappers from consuming the English gender FD code (see module docstring)."""
    live = _load_last_wins()
    for off, (_, expected_braces) in NEUTRAL_OFFSETS.items():
        braces = _BRACE_RE.findall(live[off])
        assert len(braces) == expected_braces, (
            f"0x{off:X} must carry exactly {expected_braces} brace "
            f"placeholder(s), found {braces!r}"
        )
