"""
Build-independent guard: PC Box "Item From" submenu descriptions must fit 2 lines.

The PC storage system's "Item From" submenu (Retirer/Déposer Pokémon, Déplacer
Pokémon, Déplacer objets) shows a help text box under the menu that renders at
most **two lines**. Unlike an ordinary dialogue box, this text box shares its
confirm button with the menu's action button: if the FR wording overflows onto
a 3rd line, the box shows a scroll arrow and pressing the action button both
scrolls the text *and* triggers the currently highlighted menu action, changing
screen unexpectedly.

"Déplace les objets tenus par un Pokémon d'une Boîte ou de l'équipe." used to
overflow to 3 lines (extra "de" before "l'équipe"); shortened to "... ou
l'équipe." to fit 2 lines like its sibling descriptions.

This test reads combined_fr.txt (last-wins) and simulates the box wrap so a
future rewrite that reintroduces the overflow is caught without a rebuild.
"""

from pathlib import Path

from src.core.dialogue_linewrap import DEFAULT_MAX_LINE_WIDTH, SPACE_WIDTH, word_width

COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"

MAX_LINES = 2

# PC Box "Item From" submenu descriptions (help text under the menu list).
ITEM_FROM_DESC_OFFSETS = {
    0x4185AD: "Retirer Pokémon",
    0x4185E2: "Déposer Pokémon",
    0x418611: "Déplacer Pokémon",
    0x418642: "Déplacer objets",
}


def _load_last_wins():
    mapping = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
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


def test_item_from_descriptions_fit_two_lines():
    data = _load_last_wins()
    offenders = []
    for off, label in ITEM_FROM_DESC_OFFSETS.items():
        fr = data.get(off)
        assert fr is not None, f"{label} (0x{off:X}) missing from combined_fr.txt"
        vlines = _visual_line_count(fr)
        if vlines > MAX_LINES:
            offenders.append(f"0x{off:X} {label}: {vlines} lines -> {fr!r}")
    assert not offenders, (
        "PC Box item-from descriptions overflow the 2-line help box "
        f"(box={DEFAULT_MAX_LINE_WIDTH}px):\n" + "\n".join(offenders)
    )


def test_move_items_description_shortened():
    data = _load_last_wins()
    text = data[0x418642]
    assert "de l'équipe" not in text, "overflow wording reintroduced"
    assert "ou l'équipe" in text
    assert _visual_line_count(text) == 2
