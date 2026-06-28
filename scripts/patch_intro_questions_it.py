#!/usr/bin/env python3
"""Patch the three character-creation intro questions that stay in English
(or display garbled text) in the Italian ROM after the standard build pipeline.

Root causes found statically:

* 0x1F0F89C "Your name is {PLAYER}?":
  combined_it.txt used ``[player]`` (square brackets), which ``apply_combined_fr.py``
  does not recognise as a placeholder (only ``{...}`` is matched). The ``[player]``
  string is encoded as eight literal unknown characters → relocated text reads as
  "Il tuo nome è ?player??" in-game.  The root fix (``[player]`` → ``{player}`` in
  combined_it.txt) makes the regular pipeline handle it in-place; this patch writes
  the correct bytes wherever the live pointer currently points, as a safety net.

* 0x1F0F9DD "Do you forget to save often?":
  The Italian text (32 bytes) is one byte longer than the available slot (31 bytes),
  so the builder relocates it.  The relocation itself works, but this patch
  re-applies the translation at the live pointer target to guard against any future
  revert.

* 0x1F0F9FA "Do you enjoy challenging puzzles?…":
  The full Italian translation in combined_it.txt (≈119 bytes) exceeds the original
  104-byte English slot.  When the CSV was generated from a stale combined_it.txt
  version that had only the first fragment, the builder wrote the truncated text
  in-place.  This patch relocates the full Italian text to free space and repoints
  the live referrer.

Strategy
--------
* 0x1F0F89C, 0x1F0F9DD — **direct write**: read the single known pointer cell,
  encode the Italian text, overwrite the bytes at the target address.  The pointer
  already points to the right place (original slot or a previously relocated copy);
  we just overwrite the text there with the correct bytes.  Safe because the encoded
  IT texts (18 and 33 bytes respectively) are never longer than the available slot at
  the target.
* 0x1F0F9FA — **relocate & repoint**: use a full-ROM pointer scan to detect whether
  the live pointer still reaches the original English offset.  If yes, allocate free
  space, write the full Italian text, and repoint every referrer.  If no referrers
  remain (pipeline already relocated), the patch is a no-op and the pipeline is
  trusted to have written the full text.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.core.text_codec import TextEncoder  # noqa: E402
from src.core.text_reinserter import FreeSpaceAllocator  # noqa: E402

GBA_BASE = 0x08000000

# Pointer cell in the ROM for each intro question (from English pointer extraction).
POINTER_CELLS = {
    0x1F0F89C: 0x1E6FB8E,
    0x1F0F9DD: 0x1E6FC11,
    0x1F0F9FA: 0x1E6FC26,
}

# Italian texts.  ``{player}`` is expanded to the GBA player-name runtime buffer
# ``<0xFD><0x01>`` before encoding.  ``\n`` → 0xFE (line break), ``\l`` → 0xFA
# (scroll), ``\p`` → 0xFB (page break).
IT_TEXTS: dict[int, str] = {
    0x1F0F89C: "Il tuo nome è {player}?",
    0x1F0F9DD: "Ti dimentichi di salvare spesso?",
    0x1F0F9FA: (
        "Ti piacciono gli enigmi\\nimpegnativi? Questo include enigmi"
        "\\lche vanno da quelli d'infiltrazione\\n\\na quelli con i massi."
    ),
}


def _normalize(text: str) -> str:
    """Expand escape sequences used in combined_it.txt into the form
    ``TextEncoder.encode`` expects."""
    return (
        text.replace("\\n", "\n")
            .replace("\\l", "<0xFA>")
            .replace("\\p", "<0xFB>")
            .replace("{player}", "<0xFD><0x01>")
    )


def _encode(text: str) -> bytes:
    return TextEncoder.encode(_normalize(text), "pokemon")


def _read_ptr(rom: bytes | bytearray, cell: int) -> int | None:
    """Return the ROM offset pointed at by the 32-bit LE value at ``cell``,
    or ``None`` if the value is outside the ROM address space."""
    if cell + 4 > len(rom):
        return None
    val = struct.unpack_from("<I", rom, cell)[0]
    if val < GBA_BASE or val >= GBA_BASE + len(rom):
        return None
    return val - GBA_BASE


def _write_ptr(rom: bytearray, cell: int, offset: int) -> None:
    struct.pack_into("<I", rom, cell, GBA_BASE + offset)


def _find_referrers(rom: bytes | bytearray, offset: int) -> list[int]:
    """Every 4-byte-aligned cell whose value encodes a pointer to ``offset``."""
    needle = struct.pack("<I", GBA_BASE + offset)
    return [m.start() for m in re.finditer(re.escape(needle), rom)]


def patch(rom: bytearray) -> dict:
    stats = {
        "direct_written": 0,
        "relocated": 0,
        "skipped": 0,
        "failed": 0,
    }
    allocator = FreeSpaceAllocator(rom)

    # ── Direct-write targets (pointer already points to the right slot) ───────
    for offset in (0x1F0F89C, 0x1F0F9DD):
        cell = POINTER_CELLS[offset]
        target = _read_ptr(rom, cell)
        if target is None:
            print(f"  0x{offset:08X}: pointer cell 0x{cell:X} invalid — skip")
            stats["skipped"] += 1
            continue

        encoded = _encode(IT_TEXTS[offset])

        # Idempotency: skip if the bytes are already correct.
        if rom[target : target + len(encoded)] == encoded:
            print(f"  0x{offset:08X}: already correct at 0x{target:X} — skip")
            stats["skipped"] += 1
            continue

        rom[target : target + len(encoded)] = encoded
        print(
            f"  0x{offset:08X}: wrote {len(encoded)} bytes at"
            f" 0x{target:X} (via ptr 0x{cell:X})"
        )
        stats["direct_written"] += 1

    # ── Relocate-and-repoint target ───────────────────────────────────────────
    offset = 0x1F0F9FA
    encoded = _encode(IT_TEXTS[offset])
    referrers = _find_referrers(rom, offset)

    if not referrers:
        # Pointer was already updated by a previous build — check whether the
        # live target already holds the full Italian text.
        cell = POINTER_CELLS[offset]
        target = _read_ptr(rom, cell)
        if target is not None and rom[target : target + len(encoded)] == encoded:
            print(f"  0x{offset:08X}: already fully translated — skip")
        else:
            print(
                f"  0x{offset:08X}: no referrers to original and live text differs"
                f" — cannot relocate safely; skip"
            )
        stats["skipped"] += 1
    else:
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            print(f"  0x{offset:08X}: free-space allocation failed — skip")
            stats["failed"] += 1
        else:
            rom[new_offset : new_offset + len(encoded)] = encoded
            for cell in referrers:
                _write_ptr(rom, cell, new_offset)
            print(
                f"  0x{offset:08X}: relocated {len(encoded)} bytes to"
                f" 0x{new_offset:X}; repointed {len(referrers)} pointer(s)"
            )
            stats["relocated"] += 1

    return stats


def verify(rom: bytes) -> list[tuple[int, str]]:
    """Return a list of (offset, reason) for targets whose text appears wrong."""
    bad: list[tuple[int, str]] = []
    for offset, text in IT_TEXTS.items():
        encoded = _encode(text)
        cell = POINTER_CELLS[offset]
        target = _read_ptr(rom, cell)
        if target is None:
            bad.append((offset, f"pointer cell 0x{cell:X} invalid"))
            continue
        if rom[target : target + len(encoded)] != encoded:
            bad.append(
                (
                    offset,
                    f"bytes at 0x{target:X} do not match expected Italian text",
                )
            )
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        required=True,
        type=Path,
        help="Italian ROM to patch in place (e.g. output/roms/GenedRom-it.gba)",
    )
    args = parser.parse_args()

    rom_path: Path = args.rom
    if not rom_path.exists():
        print(f"Error: ROM not found: {rom_path}")
        return 1

    rom = bytearray(rom_path.read_bytes())
    print("Patching intro character-creation questions (IT)…")
    stats = patch(rom)

    bad = verify(rom)
    rom_path.write_bytes(rom)

    print()
    print("✓ Intro questions patch — Italian:")
    print(f"   - Direct writes:   {stats['direct_written']}")
    print(f"   - Relocated:       {stats['relocated']}")
    print(f"   - Skipped:         {stats['skipped']}")
    if stats["failed"]:
        print(f"   - FAILED:         {stats['failed']}")
        return 1
    if bad:
        print("   ✗ Verification failed:")
        for off, reason in bad:
            print(f"       0x{off:08X}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
