"""
Build-independent guard: PC Box main menu (DE) must not overflow its 2-line
help box, and must use the shorter official-style verbs reported in
GitHub issue #38 ("verschieben" -> "bewegen", "entnehmen" -> "nehmen",
"einlagern" -> "ablegen").

"Verschiebe getragene Items eines Pokémon aus einer Box oder dem Team."
rendered its 2nd line at ~207px, past the ~192px box edge, clipping "Team."
behind the box's scroll arrow. Shortened wording (and the verb swap) brings
every PC Box menu label/description back under the 2-line budget.

This test reads combined_de.txt (last-wins) and simulates the box wrap so a
future rewrite that reintroduces the overflow or the old verbs is caught
without a rebuild. See tests/test_pc_item_from_menu_descriptions_fr.py for
the equivalent FR guard (same offsets, same box).
"""

from pathlib import Path

from src.core.dialogue_linewrap import DEFAULT_MAX_LINE_WIDTH, SPACE_WIDTH, word_width

COMBINED_DE = Path(__file__).resolve().parent.parent / "languages/de/combined_de.txt"

MAX_LINES = 2

# PC Box main menu labels and their help-text descriptions.
MENU_LABEL_OFFSETS = {
    0x41856C: "Withdraw Pokémon label",
    0x41857D: "Deposit Pokémon label",
    0x41858D: "Move Pokémon label",
    0x41859A: "Move Items label",
}

MENU_DESC_OFFSETS = {
    0x4185AD: "Withdraw Pokémon desc",
    0x4185E2: "Deposit Pokémon desc",
    0x418611: "Move Pokémon desc",
    0x418642: "Move Items desc",
}


def _load_last_wins():
    mapping = {}
    with COMBINED_DE.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line.startswith("0x"):
                continue
            offset_str, _, text = line.partition(":")
            mapping[int(offset_str, 16)] = text[1:] if text.startswith(" ") else text
    return mapping


def _visual_line_count(text, box=DEFAULT_MAX_LINE_WIDTH):
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


def test_menu_descriptions_fit_two_lines():
    data = _load_last_wins()
    offenders = []
    for off, label in MENU_DESC_OFFSETS.items():
        de = data.get(off)
        assert de is not None, f"{label} (0x{off:X}) missing from combined_de.txt"
        vlines = _visual_line_count(de)
        if vlines > MAX_LINES:
            offenders.append(f"0x{off:X} {label}: {vlines} lines -> {de!r}")
    assert not offenders, (
        "PC Box menu descriptions overflow the 2-line help box "
        f"(box={DEFAULT_MAX_LINE_WIDTH}px):\n" + "\n".join(offenders)
    )


def test_move_items_description_shortened():
    data = _load_last_wins()
    text = data[0x418642]
    assert "einer Box oder dem Team" not in text, "overflow wording reintroduced"
    assert _visual_line_count(text) == 2


def test_menu_uses_official_style_verbs():
    data = _load_last_wins()
    for off in (*MENU_LABEL_OFFSETS, *MENU_DESC_OFFSETS):
        text = data[off]
        assert "verschieb" not in text.lower(), f"0x{off:X} still uses 'verschieben': {text!r}"
    assert "entnehmen" not in data[0x41856C].lower()
    assert "entnehmen" not in data[0x4185AD].lower()
    assert "einlagern" not in data[0x41857D].lower()
