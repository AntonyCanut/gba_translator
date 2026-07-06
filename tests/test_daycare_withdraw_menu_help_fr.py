"""
Build-independent guard: the "back to previous menu" help text (offset
0x416244) must start with a SHORT first word in EVERY built language, or
withdrawing a Pokémon from the Day-Care hard-crashes (soft-resets) the game.

Bug (all language builds, not the EN source): choosing "Oui" to
"Veux-tu reprendre ton Pokémon ?" opens the selection menu whose cursor-help
box renders this global description. With a wide leading word the fixed-size
cursor-help window overflows, corrupts adjacent memory and CRASHES the game —
mGBA terminates and the ROM soft-resets to the title (this is the "restart" the
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
    Vai          16 px   OK   (IT fix)
    Zum          18 px   OK   (DE fix)
    Aller        27 px   FREEZE
    Torna        28 px   FREEZE  (original IT)
    Retour       34 px   FREEZE
    Zurück       34 px   FREEZE  (original DE)
    Revenir      38 px   FREEZE

Line/word width elsewhere in the string is irrelevant ("précédent" at 51 px on
line 2 is fine); only the leading word matters. The fix rewords each entry so
the leading word is narrow while preserving the translation:

    FR  "Va au menu\\nprécédent."   (first word "Va", 12 px)
    IT  "Vai al menu\\nprecedente." (first word "Vai", 16 px)
    DE  "Zum vorigen\\nMenü."       (first word "Zum", 18 px)

The bug reproduces identically across FR/IT/DE builds (the fixed-size cursor-help
window is language-agnostic), so the guard runs against every built language.

Each case reads its combined_<lang>.txt (last-wins) so a future rewrite that
reintroduces a wide leading word is caught without a rebuild.
"""

from pathlib import Path

import pytest

from src.core.dialogue_linewrap import word_width

_LANG_DIR = Path(__file__).resolve().parent.parent / "languages"

# Built languages sharing the crashing cursor-help cell. ES is a reference
# source (not a maintained translation build) and indie has no entry, so they
# are out of scope here.
COMBINED_FILES = {
    "fr": _LANG_DIR / "fr/combined_fr.txt",
    "it": _LANG_DIR / "it/combined_it.txt",
    "de": _LANG_DIR / "de/combined_de.txt",
}

# Offset of the Day-Care/selection-menu "go back" cursor-help description.
MENU_HELP_OFFSET = 0x416244

# "Va"/"Au"/"Go" are 12 px and safe; "Aller"/"Torna" (27-28 px) already freeze,
# so keep a margin well under that.
MAX_FIRST_WORD_WIDTH = 20


def _load_last_wins(path):
    mapping = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
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


@pytest.mark.parametrize("lang", sorted(COMBINED_FILES))
def test_daycare_menu_help_first_word_is_short(lang):
    path = COMBINED_FILES[lang]
    entry = _load_last_wins(path).get(MENU_HELP_OFFSET)
    assert entry is not None, (
        f"{path.name} is missing 0x{MENU_HELP_OFFSET:X} "
        "(Day-Care withdraw menu help text)"
    )
    # First visual token, before any space or the \n line break.
    first_word = entry.replace("\\n", " ").split(" ", 1)[0]
    width = word_width(first_word)
    assert width <= MAX_FIRST_WORD_WIDTH, (
        f"[{lang}] 0x{MENU_HELP_OFFSET:X} help text {entry!r} starts with "
        f"{first_word!r} ({width} px > {MAX_FIRST_WORD_WIDTH} px) — a wide "
        "leading word here overflows the cursor-help window and hard-crashes / "
        "soft-resets the Day-Care withdraw menu. Use a short first word "
        '(e.g. "Va au menu\\nprécédent.").'
    )
