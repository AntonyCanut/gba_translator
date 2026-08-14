"""Byte-level guards used by the DE English-toponym ROM audit."""

from __future__ import annotations

import struct

from scripts.audit_english_toponyms_de import (
    arrows_are_at_line_start,
    read_live_string,
)


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

