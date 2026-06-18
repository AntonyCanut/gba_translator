"""Regression guard for the battle stat-change effect messages (ticket B-35).

In battle, the "{Pokémon}'s {Stat} rose/fell!" templates must read in correct
French word order: "[STAT] de [NOM]" (e.g. "Attaque de Pikachu"), NOT the
inverted "[NOM] de [STAT]". The buffer mapping (verified against the EN ROM)
is:

    <0xFD><0x00>  -> stat name buffer   (e.g. "Attaque")
    <0xFD><0x0F>  -> attacker name buffer
    <0xFD><0x10>  -> defender name buffer
    <0xFD><0x01>  -> verb buffer        (e.g. "augmente !")

This order regressed three times because the templates were authored with the
unsupported brace syntax ({FD00}) — which the encoder writes out as the literal
characters "{FD00}" (garbage, far too long) rather than the control byte 0xFD
0x00 — and because the two tokens were swapped. This test pins both the source
order in combined_fr.txt and the encoded byte order.

The +2/-2 intensity modifier ("beaucoup", formerly "sharply ") must keep a
trailing space so it does not run into the verb ("beaucoupaugmente !").
"""

from __future__ import annotations

import re
from pathlib import Path

from src.core.text_codec import TextEncoder

COMBINED = Path(__file__).resolve().parent.parent / "combined_fr.txt"

# attacker-name templates / defender-name templates
ATK_TEMPLATES = (0x3FCB5F, 0x3FCB8F)
DEF_TEMPLATES = (0x3FCB6A, 0x3FCB9A)
MODIFIERS = (0x3FCB41, 0x3FCB50)


def _last_entries() -> dict[int, str]:
    """Parse combined_fr.txt; for duplicate offsets the LAST entry wins."""
    entries: dict[int, str] = {}
    line_re = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
    for raw in COMBINED.read_text(encoding="utf-8").splitlines():
        m = line_re.match(raw)
        if m:
            entries[int(m.group(1), 16)] = m.group(2)
    return entries


def _encode(text: str) -> bytes:
    # combined_fr.txt uses \n as the newline escape; the encoder maps it via
    # the control table, so feed a real newline.
    return TextEncoder.encode(text.replace("\\n", "\n"), "pokemon")


def test_templates_use_control_byte_not_brace_syntax():
    """Brace tokens like {FD00} are NOT understood by the encoder and would be
    written as literal text. The templates must use <0xFD><0x..> syntax."""
    entries = _last_entries()
    for off in ATK_TEMPLATES + DEF_TEMPLATES:
        text = entries[off]
        assert "{FD" not in text, f"{off:#x} uses brace syntax (encodes as garbage): {text!r}"
        assert "<0xFD>" in text, f"{off:#x} missing control-byte tokens: {text!r}"


def test_stat_precedes_name_in_source():
    """French order: stat (<0xFD><0x00>) before name (<0xFD><0x0F>/<0x10>)."""
    entries = _last_entries()
    for off in ATK_TEMPLATES:
        text = entries[off]
        assert text.index("<0x00>") < text.index("<0x0F>"), (
            f"{off:#x} inverted — name before stat: {text!r}"
        )
    for off in DEF_TEMPLATES:
        text = entries[off]
        assert text.index("<0x00>") < text.index("<0x10>"), (
            f"{off:#x} inverted — name before stat: {text!r}"
        )


def test_encoded_byte_order_stat_then_de_then_name():
    """The encoded bytes must be FD 00 ... 'de' ... FD 0F (stat, de, name)."""
    entries = _last_entries()
    de = TextEncoder.encode("de", "pokemon")[:-1]  # drop terminator
    for off, name_byte in (
        (0x3FCB5F, 0x0F),
        (0x3FCB8F, 0x0F),
        (0x3FCB6A, 0x10),
        (0x3FCB9A, 0x10),
    ):
        enc = _encode(entries[off])
        i_stat = enc.find(b"\xfd\x00")
        i_de = enc.find(de)
        i_name = enc.find(bytes((0xFD, name_byte)))
        assert i_stat != -1 and i_de != -1 and i_name != -1, f"{off:#x}: {enc.hex()}"
        assert i_stat < i_de < i_name, (
            f"{off:#x} wrong order stat={i_stat} de={i_de} name={i_name}: {enc.hex()}"
        )


def test_modifier_keeps_trailing_space():
    """'beaucoup' must end with a space so it does not stick to the verb.

    The trailing separator is authored as the explicit space byte token
    <0x00> (literal trailing spaces get trimmed by line-based tooling)."""
    entries = _last_entries()
    for off in MODIFIERS:
        text = entries[off]
        enc = _encode(text)[:-1]  # drop terminator
        assert enc.endswith(b"\x00"), f"{off:#x} modifier lost trailing space: {text!r}"
