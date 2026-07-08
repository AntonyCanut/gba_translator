"""Regression guard for the German egg-related text entries."""

from pathlib import Path

from src.core.dialogue_linewrap import DEFAULT_MAX_LINE_WIDTH, SPACE_WIDTH, word_width

COMBINED_DE = Path(__file__).resolve().parent.parent / "languages/de/combined_de.txt"


def _load_last_wins() -> dict[int, str]:
    mapping: dict[int, str] = {}
    with COMBINED_DE.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line.startswith("0x"):
                continue
            offset_str, _, text = line.partition(":")
            mapping[int(offset_str, 16)] = text[1:] if text.startswith(" ") else text
    return mapping


def _visual_line_count(text: str, box: int = DEFAULT_MAX_LINE_WIDTH) -> int:
    total = 0
    for source_line in text.split("\\n"):
        cur = 0
        lines = 1
        for word in source_line.split(" "):
            width = word_width(word)
            add = width + (SPACE_WIDTH if cur > 0 else 0)
            if cur > 0 and cur + add > box:
                lines += 1
                cur = width
            else:
                cur += add
        total += lines
    return total


def test_bad_egg_is_renamed_and_fits():
    data = _load_last_wins()
    assert data[0x3FE868] == "Schlechtes Ei"


def test_hatching_description_uses_available_width():
    data = _load_last_wins()
    text = data[0x419B44]
    assert "schlüpft" in text
    assert text.count("\\n") == 1
    assert _visual_line_count(text) == 2
