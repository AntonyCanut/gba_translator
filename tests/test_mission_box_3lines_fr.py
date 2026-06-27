"""
Build-independent guard: bounty/mission descriptions must fit the 3-line box.

The Unbound bounty board renders a mission's description in a narrow,
**non-scrolling** window that shows at most **three lines**. The window
auto-wraps any source line wider than the box; if the wrapped text spills onto
a 4th line, that tail is simply **invisible in-game** (the player never sees it).

French is longer than the English source, so several descriptions used to
overflow — e.g. the cells mission lost its trailing ``Borrius !`` and the food
thief mission lost ``récupérez ce qui a été volé``. The fix re-wrapped 47
descriptions (rebalanced ``\\n`` breaks, shortening wording only where the
content could not fit three lines).

This test reads the **source of truth** (``combined_fr.txt``, last-wins) and
simulates the box wrap, asserting every mission description renders in ≤ 3
visual lines. It needs no ROM and no mGBA, so a silent revert (another agent
rewriting the file, or a future over-long edit) is caught in the fast unit
profile before a rebuild ever happens.

Width metrics come from ``src.core.dialogue_linewrap`` (the same FireRed glyph
advances the build uses). ``BOX_WIDTH`` is set to the conservative low end of
the measured window: in-game evidence shows a 170 px line fits while a 188 px
line wraps, so wrapping at 176 px is a safe, slightly-strict guard.

Run standalone:  pytest tests/test_mission_box_3lines_fr.py -v
"""

import re
from pathlib import Path

from src.core.dialogue_linewrap import word_width, SPACE_WIDTH

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

# Conservative usable width of the 3-line bounty box, in pixels (see module
# docstring). A line wider than this auto-wraps and can push content out of view.
BOX_WIDTH = 176
MAX_LINES = 3

# Every bounty-mission *description* string, enumerated from the English ROM by
# following the bounty handler call (``call 0x09EAF584``) back to each mission's
# title pointer, then to the adjacent description pointer. Offsets absent from
# combined_fr.txt (a few missions are translated elsewhere / not yet present)
# are skipped at runtime rather than failing.
MISSION_DESC_OFFSETS = [
    0x1EE55DE, 0x1EE71A0, 0x1EEA8A9, 0x1EEA909, 0x1EEC79B, 0x1EEDAA2, 0x1EF1137,
    0x1EF155B, 0x1EF7E52, 0x1EFA8B3, 0x1F016FD, 0x1F06B1D, 0x1F073B6, 0x1F07861,
    0x1F07E7E, 0x1F082A1, 0x1F08659, 0x1F08A80, 0x1F08DF7, 0x1F0921E, 0x1F0A086,
    0x1F0CA95, 0x1F0E744, 0x1F1206E, 0x1F13071, 0x1F1425C, 0x1F14CE2, 0x1F1F8B7,
    0x1F2319E, 0x1F231F2, 0x1F260AE, 0x1F26B63, 0x1F2817A, 0x1F581E2, 0x1F5949B,
    0x1F60F39, 0x1F63D8E, 0x1F65E97, 0x1F6AF07, 0x1F6C9EC, 0x1F6CA22, 0x1F6CA57,
    0x1F7BE70, 0x1F7D066, 0x1F7E1EC, 0x1F8284C, 0x1F855FF, 0x1F87B73, 0x1F93CB0,
    0x1F9C853, 0x1F9CE03, 0x1F9D369, 0x1F9EAF1, 0x1F9F08F, 0x1F9FBCD, 0x1FA0D55,
    0x1FA4E1F, 0x1FA58E6, 0x1FA64EE, 0x1FA76B4, 0x1FA92F7, 0x1FA9BCF, 0x1FAAD67,
    0x1FADF4A, 0x1FAE718,
]


def _load_last_wins() -> dict[int, str]:
    mapping: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            m = _LINE_RE.match(raw.rstrip("\r\n"))
            if m:
                mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def _visual_line_count(text: str, box: int = BOX_WIDTH) -> int:
    """Visual lines after the box auto-wraps each ``\\n``-delimited source line."""
    total = 0
    for source_line in text.split("\\n"):
        cur = 0
        lines = 1
        for word in source_line.split(" "):
            w = word_width(word)
            add = w + (SPACE_WIDTH if cur > 0 else 0)
            if cur > 0 and cur + add > box:
                lines += 1
                cur = w
            else:
                cur += add
        total += lines
    return total


def test_all_mission_descriptions_fit_three_lines():
    data = _load_last_wins()
    offenders = []
    checked = 0
    for off in MISSION_DESC_OFFSETS:
        fr = data.get(off)
        if fr is None:
            continue  # translated elsewhere / not present yet
        # Paged dialogue ({PAGE}/{SCROLL} or \\p/\\l) is not the 3-line box.
        if any(tok in fr for tok in ("\\p", "\\l", "{PAGE}", "{SCROLL}")):
            continue
        checked += 1
        vlines = _visual_line_count(fr)
        if vlines > MAX_LINES:
            offenders.append(f"0x{off:07X}: {vlines} lines -> {fr!r}")
    assert checked >= 40, f"expected to check most missions, only {checked} found"
    assert not offenders, (
        "mission descriptions overflow the 3-line bounty box "
        f"(box={BOX_WIDTH}px):\n" + "\n".join(offenders)
    )


def test_reported_missions_are_complete():
    """The three user-reported missions keep their full text in <= 3 lines."""
    data = _load_last_wins()
    # cells: must still end with 'Borrius !'; food thief: must recover the loot.
    cells = data[0x1F87B73]
    assert "Borrius !" in cells
    assert _visual_line_count(cells) <= MAX_LINES
    food = data[0x1FA4E1F]
    assert "Traquez" in food and _visual_line_count(food) <= MAX_LINES
    pikachu = data[0x1F9CE03]
    assert "Route 8" in pikachu and _visual_line_count(pikachu) <= MAX_LINES
