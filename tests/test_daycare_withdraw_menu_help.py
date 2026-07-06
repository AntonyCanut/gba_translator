"""Build-independent guard: the Day-Care "go back to the previous menu"
cursor-help string (offset 0x416244) must be an in-engine-VERIFIED-SAFE string
in EVERY built language, or withdrawing a Pokémon from the Day-Care freezes /
soft-resets the game (ticket B-187 « Freeze jeu »).

Bug: choosing "Yes" to "do you want your Pokémon back?" opens a selection menu
whose fixed-size cursor-help window renders the global description at 0x416244.
Some strings make that window's word-wrap spin forever → GetStringWidth never
finds its stop → infinite loop → the frame freezes and the ROM soft-resets to
the title (the "restart" users report). Reproduced in mGBA from the shipped
save; absent on the untouched englishrom.gba. The window is language-agnostic,
so the bug is present in every build, not just FR — hence this guard runs
against every built language.

WHY AN ALLOWLIST, NOT A WIDTH/LENGTH HEURISTIC
----------------------------------------------
An earlier fix guessed the trigger was a wide *first word* (word_width ≤ 20 px).
That model is WRONG and shipped freezing "fixes" (IT "Vai al menu…", DE "Zum
vorigen…"). Replaying candidate strings on the SAME reachable save in mGBA rules
out every simple metric — first-word width, line width, byte length, newline
presence:

    string patched at 0x416244            first word   verdict
    "Torna al menu precedente."           28 px        OK
    "Vai al menu precedente."             16 px        FREEZE   (shorter, freezes)
    "Va au menu\\nprécédent."              12 px        OK
    "Zum vorigen\\nMenü."                  18 px        FREEZE
    "Go back to the\\nprevious menu."      12 px        OK
    "Zurück." (7 chars)                    34 px        FREEZE

The trigger is a pixel-level rendering quirk with no closed-form rule, so the
only sound static guard is: the shipped string must be one that was ACTUALLY
replayed in mGBA and proven not to freeze. Any other string is unproven and
rejected. To add a new translation here, first prove it with
``tests/e2e/test_daycare_withdraw_replay.py`` (or scripts/verify_daycare_no_freeze.mts),
then add its exact text to SAFE_STRINGS below.
"""

from pathlib import Path

import pytest

_LANG_DIR = Path(__file__).resolve().parent.parent / "languages"

# Offset of the Day-Care / selection-menu "go back" cursor-help description.
MENU_HELP_OFFSET = 0x416244

# Combined files of every built language sharing this cell. indie ships no
# 0x416244 override, so it inherits the English source string (safe) — it is
# listed to document that (see INHERITS_EN_WHEN_ABSENT) and is also replayed by
# the e2e test.
COMBINED_FILES = {
    "fr": _LANG_DIR / "fr/combined_fr.txt",
    "it": _LANG_DIR / "it/combined_it.txt",
    "de": _LANG_DIR / "de/combined_de.txt",
    "indie": _LANG_DIR / "indie/combined_indie.txt",
}

# A missing 0x416244 entry means "inherit the English source string", which is
# safe. Only these languages are allowed to omit it.
INHERITS_EN_WHEN_ABSENT = {"indie"}

# Strings replayed in mGBA and proven NOT to freeze the Day-Care withdraw menu.
# Text is stored exactly as it appears in combined_<lang>.txt (literal "\n").
SAFE_STRINGS = {
    "Va au menu\\nprécédent.",          # FR
    "Torna al menu precedente.",        # IT (single line, engine auto-wraps)
    "Go back to the\\nprevious menu.",  # EN source — used by DE and inherited by indie
}

# Strings replayed in mGBA and proven TO freeze — must never ship. Kept explicit
# so a regression to any of them fails with a precise reason instead of a vague
# "not in allowlist". (No German phrasing was found that does not freeze, which
# is why DE falls back to the English source string.)
KNOWN_FREEZE = {
    "Revenir au\\nmenu précédent.",     # original FR that opened the ticket
    "Vai al menu\\nprecedente.",        # earlier IT "fix" — freezes
    "Vai al menu precedente.",
    "Zum vorigen\\nMenü.",              # earlier DE "fix" — freezes
    "Zum vorigen\\nMenu.",
    "Zuruck zum\\nvorigen Menu.",       # original DE — freezes
    "Zurück zum\\nMenü.",
    "Zurück zum vorherigen Menü.",
    "Zum vorherigen Menü.",
}


def _load_last_wins(path):
    """Return {offset: text} honouring combined_<lang>.txt's last-wins rule."""
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
def test_daycare_menu_help_is_verified_safe(lang):
    path = COMBINED_FILES[lang]
    if not path.exists():
        pytest.skip(f"{path} not present")
    entry = _load_last_wins(path).get(MENU_HELP_OFFSET)

    if entry is None:
        assert lang in INHERITS_EN_WHEN_ABSENT, (
            f"[{lang}] combined_{lang}.txt has no 0x{MENU_HELP_OFFSET:X} entry. "
            "A build with no override inherits the English source string, which "
            "is safe — but this language is not in INHERITS_EN_WHEN_ABSENT, so "
            "confirm 0x416244 really falls back to English (and not a stale "
            "translated cell) before whitelisting it here."
        )
        return

    assert entry not in KNOWN_FREEZE, (
        f"[{lang}] 0x{MENU_HELP_OFFSET:X} = {entry!r} is a string PROVEN to "
        "freeze / soft-reset the Day-Care withdraw menu in mGBA. Revert it to a "
        "SAFE_STRINGS value (FR 'Va au menu\\nprécédent.', IT 'Torna al menu "
        "precedente.', or the English source 'Go back to the\\nprevious menu.')."
    )
    assert entry in SAFE_STRINGS, (
        f"[{lang}] 0x{MENU_HELP_OFFSET:X} = {entry!r} is UNPROVEN. The freeze "
        "trigger has no width/length rule, so a new string here must be replayed "
        "in mGBA (tests/e2e/test_daycare_withdraw_replay.py) and, only if it does "
        "NOT freeze, added to SAFE_STRINGS. Do not guess."
    )
