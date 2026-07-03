#!/usr/bin/env python3
"""Restore EN summary-screen tilemap and localized tileset in the German ROM.

Port of ``patch_summary_labels_fr.py`` — the underlying bug is entirely
language-agnostic (see that module's docstring for the full root cause):
``repair_localized_lz77_blocks.py`` copies the Spanish tilemap/tileset into
every generic-build ROM, but the game loads those tiles into a different
VRAM charblock than the source expects, so the Type/OT/Item summary-screen
labels render as garbage. This restores the EN-source tilemap/tileset (whose
layout the game's charblock-0 loading actually matches) and repoints every
duplicate pointer at it — no text is translated by this script, only pixels.

It also restores the "IDNo." label corrupted by the translation pipeline at
0x416104, exactly as in French — this is a byte-restoration of the original
label (not a translation), so the fix is identical across every language.

Usage::

    python3 languages/de/patches/summary_labels.py \\
        --rom output/roms/GenedRom-de.gba \\
        --source input/roms/englishrom.gba
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# ---------------------------------------------------------------------------
# LZ77 helpers (same implementation used in patch_summary_labels_fr.py)
# ---------------------------------------------------------------------------

_LZ77_MAGIC = 0x10


def _lz77_decompress(data: bytes | bytearray, offset: int) -> tuple[bytes, int] | None:
    if offset + 4 > len(data) or data[offset] != _LZ77_MAGIC:
        return None
    size = data[offset + 1] | (data[offset + 2] << 8) | (data[offset + 3] << 16)
    if size <= 0:
        return None
    out = bytearray()
    src = offset + 4
    while len(out) < size:
        if src >= len(data):
            return None
        flags = data[src]
        src += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                if src + 1 >= len(data):
                    return None
                b1 = data[src]
                b2 = data[src + 1]
                src += 2
                disp = ((b1 & 0x0F) << 8) | b2
                length = (b1 >> 4) + 3
                disp += 1
                if disp > len(out):
                    return None
                for _ in range(length):
                    out.append(out[-disp])
                    if len(out) >= size:
                        break
            else:
                if src >= len(data):
                    return None
                out.append(data[src])
                src += 1
    return bytes(out), src - offset


def _lz77_compress(data: bytes) -> bytes:
    size = len(data)
    out = bytearray()
    out.append(_LZ77_MAGIC)
    out.extend((size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF))
    pos = 0
    while pos < size:
        flags_pos = len(out)
        out.append(0)
        flags = 0
        for i in range(8):
            if pos >= size:
                break
            max_len = min(18, size - pos)
            window_start = max(0, pos - 0x1000)
            window = data[window_start:pos]
            best_len = 0
            best_disp = 0
            if window:
                for length in range(max_len, 2, -1):
                    idx = window.rfind(data[pos:pos + length])
                    if idx != -1:
                        best_len = length
                        best_disp = pos - (window_start + idx)
                        break
            if best_len >= 3:
                flags |= 1 << (7 - i)
                disp = best_disp - 1
                out.append(((best_len - 3) << 4) | ((disp >> 8) & 0x0F))
                out.append(disp & 0xFF)
                pos += best_len
            else:
                out.append(data[pos])
                pos += 1
        out[flags_pos] = flags
    return bytes(out)


# ---------------------------------------------------------------------------
# GBA ROM helpers
# ---------------------------------------------------------------------------

_GBA_BASE = 0x08000000


def _find_free_block(data: bytearray, size: int, min_offset: int = 0x100) -> int:
    i = min_offset
    rom_size = len(data)
    while i < rom_size:
        if data[i] != 0xFF:
            i += 1
            continue
        start = i
        while i < rom_size and data[i] == 0xFF:
            i += 1
        aligned = (start + 3) & ~3
        if i - aligned >= size:
            return aligned
    raise RuntimeError("Insufficient free space in DE ROM for summary-label patch")


def _read_gba_ptr(data: bytearray, off: int) -> int:
    val = struct.unpack_from("<I", data, off)[0]
    if val < _GBA_BASE:
        raise ValueError(f"Not a valid GBA pointer at 0x{off:07X}: 0x{val:08X}")
    return val - _GBA_BASE


def _write_gba_ptr(data: bytearray, off: int, rom_addr: int) -> None:
    struct.pack_into("<I", data, off, rom_addr + _GBA_BASE)


# ---------------------------------------------------------------------------
# Summary-screen LZ77 block addresses in EN ROM
# ---------------------------------------------------------------------------

_EN_TILEMAP_OFF = 0xE9BA30    # 32x32 tilemap (2048 bytes decompressed)
_EN_LOCALIZED_OFF = 0xE9B598  # Localised tileset (40x32 = 1280 bytes decompressed)

# ROM offsets of the GBA pointers the game reads to load each block (see
# patch_summary_labels_fr.py for how the full duplicate-pointer set was found
# by scanning the whole ROM for pointers to 0x08E9BA30 / 0x08E9B598).
_PTRS_TILEMAP = [0x135B54, 0x135D8C]            # -> 0x08E9BA30 in EN/generic builds
_PTRS_LOCALIZED = [0x135B34, 0x135DBC, 0x13B5EC]  # -> 0x08E9B598 in EN/generic builds


def _patch_lz77_block(
    de: bytearray,
    en: bytes,
    en_offset: int,
    ptr_offsets: list[int],
    label: str,
) -> bool:
    """Point every pointer in *ptr_offsets* at the EN version of the block."""
    en_result = _lz77_decompress(en, en_offset)
    if en_result is None:
        raise RuntimeError(f"Failed to decompress EN {label} at 0x{en_offset:07X}")
    en_dec, _ = en_result

    def _resolves_to_en(ptr_offset: int) -> bool:
        cur = _read_gba_ptr(de, ptr_offset)
        res = _lz77_decompress(de, cur)
        return res is not None and res[0] == en_dec

    if all(_resolves_to_en(p) for p in ptr_offsets):
        return False

    cursor: int | None = None
    for p in ptr_offsets:
        cur = _read_gba_ptr(de, p)
        res = _lz77_decompress(de, cur)
        if res is not None and res[0] == en_dec:
            cursor = cur
            break

    if cursor is None:
        compressed = _lz77_compress(en_dec)
        padded = compressed + b"\xFF" * ((-len(compressed)) & 3)
        cursor = _find_free_block(de, len(padded))
        de[cursor:cursor + len(padded)] = padded

    for p in ptr_offsets:
        _write_gba_ptr(de, p, cursor)
    return True


# ---------------------------------------------------------------------------
# IDNo. label byte fix
# ---------------------------------------------------------------------------

_IDNO_OFF = 0x416104
# EN: "IDNo." + terminator (C3 BE C8 E3 AD FF)
_IDNO_EN_BYTES = bytes([0xC3, 0xBE, 0xC8, 0xE3, 0xAD, 0xFF])
# Broken state: "o." starting from the 4th byte of a mistranslated entry
_IDNO_BROKEN = bytes([0xE3, 0xAD, 0xFF])


def _patch_idno_label(de: bytearray) -> bool:
    """Restore the IDNo. label at 0x416104. Returns True if modified."""
    current = bytes(de[_IDNO_OFF:_IDNO_OFF + len(_IDNO_EN_BYTES)])
    if current == _IDNO_EN_BYTES:
        return False  # already correct
    broken = bytes(de[_IDNO_OFF:_IDNO_OFF + len(_IDNO_BROKEN)])
    if broken != _IDNO_BROKEN:
        print(
            f"Warning: IDNo. bytes at 0x{_IDNO_OFF:X} are neither expected broken "
            f"({_IDNO_BROKEN.hex()}) nor EN ({_IDNO_EN_BYTES.hex()}); "
            f"found {broken.hex()} — skipping"
        )
        return False
    de[_IDNO_OFF:_IDNO_OFF + len(_IDNO_EN_BYTES)] = _IDNO_EN_BYTES
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-de.gba"),
                        help="DE ROM to patch (modified in place)")
    parser.add_argument("--source", type=Path, default=Path("input/roms/englishrom.gba"),
                        help="EN source ROM")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"ROM not found: {args.rom}", file=sys.stderr)
        return 1
    if not args.source.exists():
        print(f"Source ROM not found: {args.source}", file=sys.stderr)
        return 1

    de = bytearray(args.rom.read_bytes())
    en = args.source.read_bytes()

    if de[0xB2] != 0x96:
        print(f"Not a valid GBA ROM: {args.rom}", file=sys.stderr)
        return 1

    changes: list[str] = []

    if _patch_lz77_block(de, en, _EN_TILEMAP_OFF, _PTRS_TILEMAP, "tilemap"):
        changes.append("summary-screen tilemap restored from EN source (all pointers)")

    if _patch_lz77_block(de, en, _EN_LOCALIZED_OFF, _PTRS_LOCALIZED, "localized tileset"):
        changes.append("summary-screen localized tileset restored from EN source (all pointers)")

    if _patch_idno_label(de):
        changes.append("IDNo. label restored at 0x416104")

    if changes:
        args.rom.write_bytes(de)
        for msg in changes:
            print(f"Patched: {msg}")
    else:
        print("Summary-label patch: already up to date — no changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
