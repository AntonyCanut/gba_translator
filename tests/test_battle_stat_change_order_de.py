"""Regression guards for German battle stat-change messages.

The battle engine builds the final phrase from a template and a verb buffer.
For a +/-2 or +/-3 stat change it prepends the intensity word to that buffer.
German therefore needs:

    template: "<STAT> von <NAME>\nist <BUFFER>"
    +1:      buffer = "gestiegen!"
    +2:      buffer = "stark " + "gestiegen!"
    +3:      buffer = "drastisch " + "gestiegen!"

Without explicit German verb-buffer entries the EN fallback "rose!" / "fell!"
can leak into the DE ROM.
"""

from __future__ import annotations

import re
from pathlib import Path

COMBINED = Path(__file__).resolve().parent.parent / "languages/de/combined_de.txt"

RISE_TEMPLATES = (0x3FCB5F, 0x3FCB6A)
FALL_TEMPLATES = (0x3FCB8F, 0x3FCB9A)
VERB_BUFFERS = (0x3FCB4A, 0x3FCB59)
STRONG_MODIFIERS = (0x3FCB41, 0x3FCB50)
DRASTIC_MODIFIERS = (0x883590, 0xA4C603)
SEND_OUT_TEMPLATES = (0x3FD3B1, 0x3FD3C7, 0x3FD3E4)


def _last_entries() -> dict[int, str]:
    entries: dict[int, str] = {}
    line_re = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
    for raw in COMBINED.read_text(encoding="utf-8").splitlines():
        m = line_re.match(raw)
        if m:
            entries[int(m.group(1), 16)] = m.group(2)
    return entries


def _decode_buffer(text: str) -> str:
    return text.replace("<0x00>", " ").replace("\\n", "\n")


def _render(template: str, modifier: str, verb: str) -> str:
    text = template
    text = text.replace("<0xFD><0x00>", "Verteidigung")
    text = text.replace("<0xFD><0x0F>", "Pikachu")
    text = text.replace("<0xFD><0x10>", "Pikachu")
    text = text.replace("<0xFD><0x01>", _decode_buffer(modifier) + _decode_buffer(verb))
    return text.replace("\\n", "\n")


def test_de_stat_change_buffers_are_german():
    entries = _last_entries()

    assert entries[0x3FCB4A] == "gestiegen!"
    assert entries[0x3FCB59] == "gesunken!"
    for off in STRONG_MODIFIERS:
        assert _decode_buffer(entries[off]) == "stark "
    for off in DRASTIC_MODIFIERS:
        assert _decode_buffer(entries[off]) == "drastisch "


def test_de_stat_change_templates_render_issue_phrasing():
    entries = _last_entries()

    assert _render(entries[0x3FCB5F], "", entries[0x3FCB4A]) == (
        "Verteidigung von Pikachu\nist gestiegen!"
    )
    assert _render(entries[0x3FCB5F], entries[0x3FCB41], entries[0x3FCB4A]) == (
        "Verteidigung von Pikachu\nist stark gestiegen!"
    )
    assert _render(entries[0x3FCB5F], entries[0xA4C603], entries[0x3FCB4A]) == (
        "Verteidigung von Pikachu\nist drastisch gestiegen!"
    )
    assert _render(entries[0x3FCB9A], "", entries[0x3FCB59]) == (
        "Verteidigung von Pikachu\nist gesunken!"
    )
    assert _render(entries[0x3FCB9A], entries[0x3FCB50], entries[0x3FCB59]) == (
        "Verteidigung von Pikachu\nist stark gesunken!"
    )
    assert _render(entries[0x3FCB9A], entries[0xA4C603], entries[0x3FCB59]) == (
        "Verteidigung von Pikachu\nist drastisch gesunken!"
    )


def test_de_stat_change_templates_do_not_leak_english_verbs():
    entries = _last_entries()
    battle_values = [entries[off] for off in RISE_TEMPLATES + FALL_TEMPLATES + VERB_BUFFERS]
    assert all("rose" not in value and "fell" not in value for value in battle_values)


def test_de_send_out_templates_use_control_byte_syntax():
    entries = _last_entries()
    for off in SEND_OUT_TEMPLATES:
        text = entries[off]
        assert "{FD" not in text and "{FC" not in text, (
            f"{off:#x} would encode control codes as literal text: {text!r}"
        )
        assert "<0xFD>" in text, f"{off:#x} lost battle placeholder control bytes: {text!r}"

