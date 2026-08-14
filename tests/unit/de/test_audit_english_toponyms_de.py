"""Byte-level guards used by the DE English-toponym ROM audit."""

from __future__ import annotations

import struct

from scripts.audit_english_toponyms_de import (
    arrows_are_at_line_start,
    read_live_string,
    source_grounded_referrers,
)
from src.core.text_codec import TextEncoder


def test_read_live_string_follows_pointer_and_requires_terminator() -> None:
    rom = bytearray(b"\x00" * 0x200)
    struct.pack_into("<I", rom, 0x20, 0x08000100)
    rom[0x100:0x104] = b"ABC\xff"

    target, raw = read_live_string(bytes(rom), 0x20, limit=16)

    assert target == 0x100
    assert raw == b"ABC\xff"


def test_read_live_string_reports_unterminated_target() -> None:
    rom = bytearray(b"\x00" * 0x200)
    struct.pack_into("<I", rom, 0x20, 0x08000100)

    target, raw = read_live_string(bytes(rom), 0x20, limit=16)

    assert target == 0x100
    assert raw is None


def test_panel_arrows_must_begin_a_line() -> None:
    assert arrows_are_at_line_start(b"Title\xfb\x79 North\xfe\x7c East\xff")
    assert not arrows_are_at_line_start(b"Title \x79 North\xff")


def test_standalone_alias_requires_matching_english_pointer_consumer() -> None:
    english = bytearray(b"\xff" * 0x300)
    german = bytearray(english)
    alias = TextEncoder.encode_pokemon("Somnia")
    german[0x100 : 0x100 + len(alias)] = alias
    struct.pack_into("<I", english, 0x20, 0x08000100)
    struct.pack_into("<I", german, 0x20, 0x08000100)

    assert source_grounded_referrers(
        bytes(english), bytes(german), 0x100, "Tarmigan Town"
    ) == []


def test_standalone_alias_reports_matching_english_pointer_consumer() -> None:
    english = bytearray(b"\xff" * 0x300)
    german = bytearray(english)
    canonical = TextEncoder.encode_pokemon("Cliff Cave")
    alias = TextEncoder.encode_pokemon("Grotte Faille")
    english[0x180 : 0x180 + len(canonical)] = canonical
    german[0x100 : 0x100 + len(alias)] = alias
    struct.pack_into("<I", english, 0x20, 0x08000180)
    struct.pack_into("<I", german, 0x20, 0x08000100)

    assert source_grounded_referrers(
        bytes(english), bytes(german), 0x100, "Cliff Cave"
    ) == [0x20]
