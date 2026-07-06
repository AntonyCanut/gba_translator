"""
Build-independent guard: the "back to previous menu" help text (offset
0x416244) must start with a SHORT first word, or withdrawing a Pokémon from
the Day-Care hard-crashes (soft-resets) the game.

Bug (all language builds, not the EN source): choosing "Oui" to
"Veux-tu reprendre ton Pokémon ?" opens the selection menu whose cursor-help
box renders this global description. With the original FR wording
"Revenir au\\nmenu précédent." the wide leading word overflows the fixed-size
cursor-help window, corrupts adjacent memory and CRASHES the game — mGBA
terminates and the ROM soft-resets to the title (this is the "restart" the
user reported; it is NOT a benign GetString render loop). Reproduced in mGBA
from the shipped .sav, absent on the untouched englishrom.gba.

Isolation proof: patching ONLY these bytes of an otherwise-clean, working FR
build back to "Revenir au\\nmenu précédent." reintroduces the crash at the exact
list-open frame; restoring "Va au menu\\nprécédent." makes the withdraw complete
cleanly (both Pokémon returned, party full handled). So the crash is controlled
entirely by this one string — it is a render-overflow reset, not a pointer
clobber.

Root cause, pinned by in-engine bisection: this particular help box only
tolerates a very short *first word*. The pixel widths tell the story:

    first word   width   verdict
    Go / Va / Au 12 px   OK   (EN uses "Go")
    Aller        27 px   FREEZE
    Retour       34 px   FREEZE
    Revenir      38 px   FREEZE

Line/word width elsewhere in the string is irrelevant ("précédent" at 51 px on
line 2 is fine); only the leading word matters. The fix rewords the entry to
"Va au menu\\nprécédent." (first word "Va", 12 px) — French preserved, no freeze.

This reads combined_fr.txt (last-wins) so a future rewrite that reintroduces a
wide leading word is caught without a rebuild.
"""

from pathlib import Path

from src.core.dialogue_linewrap import word_width

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"

# Offset of the Day-Care/selection-menu "go back" cursor-help description.
MENU_HELP_OFFSET = 0x416244

# "Va"/"Au"/"Go" are 12 px and safe; "Aller" (27 px) already freezes, so keep a
# margin well under that.
MAX_FIRST_WORD_WIDTH = 20


def _load_last_wins():
    mapping = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line.startswith("0x"):
                continue
            offset_str, sep, text = line.partition(":")
            if not sep:
                continue
            try:
                offset = int(offset_str, 16)
            except ValueError:
                continue
            mapping[offset] = text[1:] if text.startswith(" ") else text
    return mapping


def test_daycare_menu_help_first_word_is_short():
    entry = _load_last_wins().get(MENU_HELP_OFFSET)
    assert entry is not None, (
        f"combined_fr.txt is missing 0x{MENU_HELP_OFFSET:X} "
        "(Day-Care withdraw menu help text)"
    )
    # First visual token, before any space or the \n line break.
    first_word = entry.replace("\\n", " ").split(" ", 1)[0]
    width = word_width(first_word)
    assert width <= MAX_FIRST_WORD_WIDTH, (
        f"0x{MENU_HELP_OFFSET:X} help text {entry!r} starts with {first_word!r} "
        f"({width} px > {MAX_FIRST_WORD_WIDTH} px) — a wide leading word here "
        "overflows the cursor-help window and hard-crashes / soft-resets the "
        "Day-Care withdraw menu. Use a short first word "
        '(e.g. "Va au menu\\nprécédent.").'
    )
