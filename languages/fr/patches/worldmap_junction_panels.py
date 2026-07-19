#!/usr/bin/env python3
"""Translate the World-Map *junction* panels that the generic pipeline drops.

Root cause (found statically against the English ROM + the extraction):

The World-Map sign cluster (``0x1F70xxx``–``0x1F72xxx``) is split in two shapes:

* **Route panels** start with a route name (``Route 8\\n"Frost Mountain Peak"\\p
  <arrow> …``). The pointer-text extractor sizes them correctly, so
  ``apply_combined_fr.py`` carries them into the trilingual CSV / translation
  JSON and the generic builder relocates + repoints them normally.
* **Junction panels** start *directly* with a direction arrow byte
  (``0x79``–``0x7C``) — e.g. ``<0x79> Frozen Heights\\n<0x7A> Crater Town\\l
  <0x7B> Blizzard City``. The extractor treats the leading arrow as a 1-byte
  ASCII string (``original_length == 1``, ``real_max_length == 3``), so the
  French text is far too long to write in place and there is no usable
  extraction entry to relocate from. Depending on the delivery path, the built
  ROM therefore keeps the English sign or relocates ASCII bytes that the game
  renders as garbage through its Pokémon character table.

The correct French translations already live in ``combined_fr.txt`` at the same
offsets (arrows kept at line start). This post-build patch closes the gap the
same way :mod:`patch_meteorite_dialogue_fr` does: encode each ``combined_fr.txt``
value with the shared control-code machinery, relocate one ``0xFF``-terminated
copy into free space, and repoint **every** live referrer to it.

The patch is reference-driven (it scans the whole ROM for live pointers to each
original offset) and idempotent: an offset whose original is no longer pointed
at — already relocated by the generic pass or a previous run — is skipped.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from src.core.text_codec import TextEncoder  # noqa: E402
from src.core.text_reinserter import FreeSpaceAllocator  # noqa: E402

from apply_inline_overrides_fr import (  # noqa: E402
    _apply_control_placeholders,
    _normalize_text,
    _read_raw_entry,
)

ROM_POINTER_BASE = 0x08000000
DEFAULT_COMBINED = REPO_ROOT / "languages/fr/combined_fr.txt"

# Arrow-prefixed World-Map junction panels (extractor sees them as 1-byte
# strings → undeliverable by the generic pipeline). original English offset ->
# a short, contiguous French fragment used to prove the relocation landed.
TARGETS: dict[int, str] = {
    # Route 5: the generic builder relocated this entry as ASCII because the
    # leading up-arrow byte (0x79) was extracted as the literal string "y".
    # The verification fragment stays language-neutral because the Italian and
    # German wrappers reuse this patch with their own combined translation.
    0x1F70E41: "Pokémon",
    0x1F72691: "Cimes Gelées",
    0x1F726C0: "Cimes Gelées, Cimistral",
    0x1F726FC: "Cratéris",
    0x1F72735: "Cratéris, Automnia",
    0x1F7276E: "Dresco",
    0x1F727A7: "Dresco",
    0x1F727D0: "Antésia, Naville",
    0x1F72808: "Gurenbourg",
    # Cootes Marsh mini-panel: EN starts with the ↑ arrow byte too (1-byte
    # undeliverable). FR arrow was mid-line before the line-start fix (P-68).
    0x1F72353: "Magnolia",
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
    """Encode a ``combined_fr.txt`` value to ROM bytes (incl. 0xFF terminator)."""
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
    """Return targets whose live pointer still reaches the English original."""
    bad: list[tuple[int, str]] = []
    for offset, prefix in TARGETS.items():
        if find_referrers(rom, offset):
            bad.append((offset, "still points to original"))
            continue
        encoded_prefix = TextEncoder.encode(prefix, "pokemon")[:-1]  # drop 0xFF
        if encoded_prefix not in rom:
            bad.append((offset, "French fragment not found in ROM"))
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

    print("✓ World-Map junction panels — relocation + repointing:")
    print(f"   - Targets relocated:      {stats['targets']}")
    print(f"   - Pointers repointed:     {stats['repointed']}")
    if stats["skipped"]:
        print(f"   - Already relocated (skip): {stats['skipped']}")
    if stats["no_source"]:
        print(f"   - No FR source:           {stats['no_source']}")
    if stats["failed"]:
        print(f"   - FAILED (free space):    {stats['failed']}")
        return 1
    if remaining:
        print("   - ✗ Verification failed:")
        for offset, why in remaining:
            print(f"       0x{offset:08X}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
