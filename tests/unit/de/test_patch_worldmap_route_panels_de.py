"""DE route panels keep the exact English break/arrow control topology."""

from __future__ import annotations

import struct

from languages.de.patches import worldmap_route_panels as patch


class _Allocator:
    def __init__(self, _rom: bytearray, reserved_rom: bytes | None = None):
        pass

    def allocate(self, _size: int) -> int:
        return 0x200


def test_repoints_generic_panel_to_exact_combined_controls(monkeypatch) -> None:
    source = bytearray(b"\x00" * 0x400)
    source[0x100:0x109] = b"A\xfeB\xfb\x79 C\xff"
    struct.pack_into("<I", source, 0x20, 0x08000100)

    built = bytearray(source)
    built[0x180:0x188] = b"A B\xfb\x79 C\xff"
    struct.pack_into("<I", built, 0x20, 0x08000180)
    monkeypatch.setattr(patch, "FreeSpaceAllocator", _Allocator)

    stats = patch.apply(
        built,
        {0x100: r"A\nB\p<0x79> C"},
        bytes(source),
        panel_offsets=(0x100,),
    )

    assert stats == {"relocated": 1, "repointed": 1, "skipped": 0, "failed": 0}
    assert struct.unpack_from("<I", built, 0x20)[0] == 0x08000200
    expected = patch.encode_relocated(r"A\nB\p<0x79> C", bytes(source), 0x100)
    assert built[0x200 : 0x200 + len(expected)] == expected
    assert patch.verify(
        bytes(built),
        {0x100: r"A\nB\p<0x79> C"},
        bytes(source),
        panel_offsets=(0x100,),
    ) == []
