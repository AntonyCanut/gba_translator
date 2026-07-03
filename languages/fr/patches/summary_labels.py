#!/usr/bin/env python3
"""Restore EN summary-screen tilemap and localized tileset in the FR ROM.

The summary screen (Infos Pokémon) shows label boxes for Type/OT/Item.
``repair_localized_lz77_blocks.py`` copies the Spanish tilemap (which
references charblock-1 tiles) into the FR ROM. Because the FR game
(like EN) loads those tiles into charblock 0, the wrong VRAM positions
are referenced and the labels display as "PE" / "T" / "EM" garbage.

This script:
 1. Reads the EN-source tilemap (0xE9BA30) and localized tileset
    (0xE9B598), decompresses them, and re-compresses them into free
    space in the FR ROM — then updates the two ROM pointers that the
    game reads at runtime (0x135B54 for the tilemap, 0x135B34 for the
    tileset).
 2. Fixes the corrupted "IDNo." label at 0x416104 (the translation
    pipeline mistakenly wrote "IDNo." at offset 0x416101, leaving "o."
    at the offset the code actually reads).

Run AFTER ``repair_localized_lz77_blocks.py`` so it takes precedence.

Usage::

    python3 languages/fr/patches/summary_labels.py \\
        --rom output/roms/GenedRom-fr.gba \\
        --source input/roms/englishrom.gba
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# ---------------------------------------------------------------------------
# LZ77 helpers (same implementation used in patch_version_fr.py)
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
    raise RuntimeError("Insufficient free space in FR ROM for summary-label patch")


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

# EN ROM offsets for the two LZ77 blocks that repair_localized overwrites
# with their Spanish equivalents.
_EN_TILEMAP_OFF = 0xE9BA30    # 32×32 tilemap (2048 bytes decompressed)
_EN_LOCALIZED_OFF = 0xE9B598  # Localised tileset (40×32 = 1280 bytes decompressed)

# ROM offsets of the GBA pointers the game reads to load each block.
#
# CRITICAL: each block is referenced by MULTIPLE duplicate pointers scattered
# through the summary-screen setup code. The info page ("Infos Pokémon") renders
# through the *second* pointer group (0x135D8C / 0x135DBC / 0x13B5EC), NOT the
# first. An earlier version of this patch only repointed the first group
# (0x135B54 / 0x135B34); the game kept loading the Spanish-overwritten in-place
# blocks via the un-patched duplicates, so the labels still showed "PE"/"T"/"EM"
# in-game. ALL duplicate pointers must be repointed. The full sets below were
# verified by scanning the whole ROM for pointers to 0x08E9BA30 and 0x08E9B598.
_PTRS_TILEMAP = [0x135B54, 0x135D8C]            # → 0x08E9BA30 in EN/FR
_PTRS_LOCALIZED = [0x135B34, 0x135DBC, 0x13B5EC]  # → 0x08E9B598 in EN/FR


def _patch_lz77_block(
    fr: bytearray,
    en: bytes,
    en_offset: int,
    ptr_offsets: list[int],
    label: str,
) -> bool:
    """Point every pointer in *ptr_offsets* at the EN version of the block.

    The EN block is relocated once into free space; all duplicate pointers are
    then redirected to that single relocated copy. Returns True if the ROM was
    modified.
    """
    en_result = _lz77_decompress(en, en_offset)
    if en_result is None:
        raise RuntimeError(f"Failed to decompress EN {label} at 0x{en_offset:07X}")
    en_dec, _ = en_result

    # Already fully patched? Only when EVERY pointer resolves to EN-equal data.
    def _resolves_to_en(ptr_offset: int) -> bool:
        cur = _read_gba_ptr(fr, ptr_offset)
        res = _lz77_decompress(fr, cur)
        return res is not None and res[0] == en_dec

    if all(_resolves_to_en(p) for p in ptr_offsets):
        return False

    # Reuse an existing relocated EN copy if one of the pointers already targets
    # it (avoids leaking a fresh free-space block on every rebuild).
    cursor: int | None = None
    for p in ptr_offsets:
        cur = _read_gba_ptr(fr, p)
        res = _lz77_decompress(fr, cur)
        if res is not None and res[0] == en_dec:
            cursor = cur
            break

    if cursor is None:
        compressed = _lz77_compress(en_dec)
        padded = compressed + b"\xFF" * ((-len(compressed)) & 3)
        cursor = _find_free_block(fr, len(padded))
        fr[cursor:cursor + len(padded)] = padded

    for p in ptr_offsets:
        _write_gba_ptr(fr, p, cursor)
    return True


# ---------------------------------------------------------------------------
# IDNo. label byte fix
# ---------------------------------------------------------------------------

# The translation pipeline wrote "IDNo." at ROM offset 0x416101 (missing the
# 3-space prefix present in EN). The code reads the label from 0x416104 — the
# 4th byte of "IDNo." — which yields "o." instead of the full label.
# We restore the correct EN bytes at 0x416104.
_IDNO_OFF = 0x416104
# EN: "IDNo." + terminator (C3 BE C8 E3 AD FF)
_IDNO_EN_BYTES = bytes([0xC3, 0xBE, 0xC8, 0xE3, 0xAD, 0xFF])
# FR broken state: "o." starting from the 4th byte of mistranslated entry
_IDNO_FR_BROKEN = bytes([0xE3, 0xAD, 0xFF])


def _patch_idno_label(fr: bytearray) -> bool:
    """Restore the IDNo. label at 0x416104. Returns True if modified."""
    current = bytes(fr[_IDNO_OFF:_IDNO_OFF + len(_IDNO_EN_BYTES)])
    if current == _IDNO_EN_BYTES:
        return False  # already correct
    broken = bytes(fr[_IDNO_OFF:_IDNO_OFF + len(_IDNO_FR_BROKEN)])
    if broken != _IDNO_FR_BROKEN:
        # Neither broken nor correct — unexpected state; skip rather than corrupt
        print(
            f"Warning: IDNo. bytes at 0x{_IDNO_OFF:X} are neither expected broken "
            f"({_IDNO_FR_BROKEN.hex()}) nor EN ({_IDNO_EN_BYTES.hex()}); "
            f"found {broken.hex()} — skipping"
        )
        return False
    fr[_IDNO_OFF:_IDNO_OFF + len(_IDNO_EN_BYTES)] = _IDNO_EN_BYTES
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"),
                        help="FR ROM to patch (modified in place)")
    parser.add_argument("--source", type=Path, default=Path("input/roms/englishrom.gba"),
                        help="EN source ROM")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"ROM not found: {args.rom}", file=sys.stderr)
        return 1
    if not args.source.exists():
        print(f"Source ROM not found: {args.source}", file=sys.stderr)
        return 1

    fr = bytearray(args.rom.read_bytes())
    en = args.source.read_bytes()

    if fr[0xB2] != 0x96:
        print(f"Not a valid GBA ROM: {args.rom}", file=sys.stderr)
        return 1

    changes: list[str] = []

    if _patch_lz77_block(fr, en, _EN_TILEMAP_OFF, _PTRS_TILEMAP, "tilemap"):
        changes.append("summary-screen tilemap restored from EN source (all pointers)")

    if _patch_lz77_block(fr, en, _EN_LOCALIZED_OFF, _PTRS_LOCALIZED, "localized tileset"):
        changes.append("summary-screen localized tileset restored from EN source (all pointers)")

    if _patch_idno_label(fr):
        changes.append("IDNo. label restored at 0x416104")

    if changes:
        args.rom.write_bytes(fr)
        for msg in changes:
            print(f"Patched: {msg}")
    else:
        print("Summary-label patch: already up to date — no changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
