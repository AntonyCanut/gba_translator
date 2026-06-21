#!/usr/bin/env python3
"""Translate the long « Borrius meteorite » cutscene that the generic pipeline
can never reach.

Root cause (found statically against the English ROM + the extraction):

The Valley-City elder's meteorite monologue is a **single** 1046-byte string at
``0x007A9A75`` (« Thirty years ago, a large meteorite was hurtling towards
Borrius… »). The pointer-based extractor caps every string at
``max_text_length = 1000`` bytes (:mod:`src.extractors.pointer_text_extractor`),
so ``_read_text`` returns ``None`` for this offset and it never enters
``englishrom_texts.json``. With no extraction entry:

* ``apply_combined_fr.py --extend`` cannot add it to the trilingual CSV
  (it only extends offsets present in the English extraction), so it never
  reaches ``*_translation_ready.json`` and the generic builder never relocates
  or repoints it;
* ``apply_inline_overrides_fr.py`` also skips it — the Spanish extraction is
  capped the same way, and the French text is far longer than the slot, so an
  in-place write would be rejected as ``too_long`` anyway.

The authoritative French translation already lives in ``combined_fr.txt`` at the
same offset, but every delivery path drops it, so the built ROM still shows the
English text. This post-build patch closes that gap the same way the move /
field-move description patches do: encode the ``combined_fr.txt`` text with the
shared control-code machinery, relocate one ``0xFF``-terminated copy into free
space, and repoint **every** referrer to it.

The string is referenced by a single, 2-byte-aligned pointer at ``0x0074B0AA``;
the patch is reference-driven (it scans the whole ROM for live pointers to the
original offset) so it also covers any duplicate referrer without hard-coding
the pointer cell.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from src.core.text_codec import TextDecoder, TextEncoder
from src.core.text_reinserter import FreeSpaceAllocator

# Reuse the exact control-code / placeholder machinery the inline-override pass
# uses, so the relocated bytes are identical to what the pipeline would emit
# (FC01 colour codes, FA scroll / FB page breaks, curly-quote normalisation…).
from apply_inline_overrides_fr import (  # noqa: E402
    _apply_control_placeholders,
    _normalize_text,
    _read_raw_entry,
)

ROM_POINTER_BASE = 0x08000000
DEFAULT_COMBINED = REPO_ROOT / "combined_fr.txt"

# Oversized (> extractor cap) cutscene strings that are otherwise undeliverable.
# original English offset -> a short French prefix used to prove the relocation.
TARGETS: dict[int, str] = {
    0x7A9A75: "Il y a trente ans",  # Valley-City elder, meteorite monologue
}

_OFFSET_LINE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def load_combined(path: Path) -> dict[int, str]:
    """original ROM offset -> French text (last entry wins, per combined_fr.txt)."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _OFFSET_LINE.match(line)
        if m:
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def encode_relocated(text: str, source_rom: bytes, offset: int) -> bytes:
    """Encode a ``combined_fr.txt`` value to ROM bytes (incl. 0xFF terminator).

    The English string at ``offset`` supplies the live control sequences that the
    ``{COLOR}`` / placeholder tokens map onto, exactly like the inline pass.
    """
    english = _read_raw_entry(source_rom, offset, "pokemon")
    normalized = _normalize_text(text)
    if english:
        normalized = _apply_control_placeholders(
            normalized, english.get("decoded_text"), english.get("raw_bytes")
        )
    return TextEncoder.encode(normalized, "pokemon")


def find_referrers(rom: bytes, offset: int) -> list[int]:
    """Every ROM cell holding a 32-bit LE pointer to ``ROM_POINTER_BASE+offset``."""
    needle = struct.pack("<I", ROM_POINTER_BASE + offset)
    return [m.start() for m in re.finditer(re.escape(needle), rom)]


def apply(
    rom: bytearray,
    combined: dict[int, str],
    source_rom: bytes,
    reserved_rom: bytes | None = None,
) -> dict:
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    stats = {"targets": 0, "repointed": 0, "no_source": 0, "failed": 0, "skipped": 0}

    for offset in TARGETS:
        referrers = find_referrers(rom, offset)
        if not referrers:
            # Nothing points at the original string any more — already relocated
            # by a previous run, or the layout changed. Nothing to do.
            stats["skipped"] += 1
            continue
        text = combined.get(offset)
        if not text:
            stats["no_source"] += 1
            continue

        encoded = encode_relocated(text, source_rom, offset)
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            stats["failed"] += 1
            continue
        rom[new_offset : new_offset + len(encoded)] = encoded
        pointer = struct.pack("<I", new_offset + ROM_POINTER_BASE)
        for cell in referrers:
            rom[cell : cell + 4] = pointer
            stats["repointed"] += 1
        stats["targets"] += 1

    return stats


def verify(rom: bytes) -> list[tuple[int, str]]:
    """Return targets whose live pointer still does not reach the French prefix."""
    bad: list[tuple[int, str]] = []
    for offset, prefix in TARGETS.items():
        referrers = find_referrers(rom, offset)
        if referrers:
            # A pointer still reaches the (English) original.
            bad.append((offset, "still points to original"))
            continue
        needle = struct.pack("<I", ROM_POINTER_BASE + offset)
        # The original is gone; confirm at least one relocated copy decodes to FR.
        # We locate any pointer table that referenced it pre-patch is hard now,
        # so instead scan free-space copies: any string starting with the prefix.
        encoded_prefix = TextEncoder.encode(prefix, "pokemon")[:-1]  # drop 0xFF
        if encoded_prefix not in rom:
            bad.append((offset, "French prefix not found in ROM"))
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, help="Built French ROM to patch in place")
    parser.add_argument(
        "--source",
        default=str(REPO_ROOT / "input/roms/englishrom.gba"),
        help="English ROM (source of live control sequences)",
    )
    parser.add_argument(
        "--combined",
        default=str(DEFAULT_COMBINED),
        help="combined_fr.txt source of truth (offset -> FR text)",
    )
    parser.add_argument(
        "--reference-rom",
        default=None,
        help="Same-base ROM whose populated bytes must not be reused as free space",
    )
    args = parser.parse_args()

    rom_path = Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    source_rom = Path(args.source).read_bytes()
    combined = load_combined(Path(args.combined))
    reserved = Path(args.reference_rom).read_bytes() if args.reference_rom else None

    stats = apply(rom, combined, source_rom, reserved_rom=reserved)
    remaining = verify(rom)
    rom_path.write_bytes(rom)

    print("✓ Dialogue météorite (Borrius) — relocalisation + repointage :")
    print(f"   - Cibles relocalisées : {stats['targets']}")
    print(f"   - Pointeurs repointés : {stats['repointed']}")
    if stats["skipped"]:
        print(f"   - Déjà relocalisé (skip) : {stats['skipped']}")
    if stats["no_source"]:
        print(f"   - Sans source FR : {stats['no_source']}")
    if stats["failed"]:
        print(f"   - ÉCHECS (free space) : {stats['failed']}")
        return 1
    if remaining:
        print("   - ✗ Vérification échouée :")
        for offset, why in remaining:
            print(f"       0x{offset:08X}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
