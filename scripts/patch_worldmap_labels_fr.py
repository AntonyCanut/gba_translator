#!/usr/bin/env python3
"""Write the World-Map *label* strings that the generic FR pipeline mangles.

Root cause (found against the English ROM + the CI translation JSON):

A handful of World-Map location labels live as plain 0xFF-terminated strings in
the ``0x72xxxx`` / ``0xB5xxxx`` label region and are reached **in place** (the
zone-name pointer table at ``0x3F1xxx`` targets the original offset; the engine
also reads the bytes directly). The dev's golden build — produced from the rich
trilingual CSV — wrote the French text in place, tolerating the 1-byte overflow
into the trailing padding that follows each English label.

The CI build path (``prepare_fr_json.py`` → generic builder) does not:

* ``0xB500A0`` "Gurun Town" → "Bourg Gurun": ``prepare_fr_json`` measures the
  bare English string length (10) as the slot, marks the 11-byte French entry
  ``too_long`` and the generic relocator truncates the leading byte → the ROM
  shows "ourg Gurun".
* ``0xB535C8`` "Fullmoon Island" → "Île de la Lune": the French fits (14 ≤ 15)
  but a later restore pass leaves the English bytes in place.

Both labels are byte-for-byte deliverable in place: the English slot plus its
trailing padding run (0x00 / 0xFF bytes before the next pointer-table entry)
leaves ample room. This post-build patch — run late, after every EN-restore
pass — encodes each ``combined_fr.txt`` value and writes it in place, refusing
to overflow past the available padding so no neighbouring data is clobbered.

Idempotent (re-writing identical bytes is a no-op) and reference-driven (the
slot size is computed from the English ROM, never hard-coded).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from src.core.text_codec import TextEncoder  # noqa: E402

from apply_inline_overrides_fr import _normalize_text  # noqa: E402

DEFAULT_COMBINED = REPO_ROOT / "languages/fr/combined_fr.txt"

# In-place World-Map label offsets the generic pipeline fails to deliver.
# original English offset -> the expected decoded French (used only to prove the
# write landed; the bytes actually written come from combined_fr.txt).
TARGETS: dict[int, str] = {
    0xB500A0: "Gurenbourg",       # Gurun Town  (was "Bourg Gurun")
    0xB535C8: "Île Pleine Lune",  # Fullmoon Island  (was "Île de la Lune")
}

_OFFSET_LINE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

# Bytes that count as reusable padding immediately after an English label.
_PADDING = {0x00, 0xFF}


def load_combined(path: Path) -> dict[int, str]:
    """original ROM offset -> French text (last entry wins, per combined_fr.txt)."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _OFFSET_LINE.match(line)
        if m:
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def _english_slot(source_rom: bytes, offset: int) -> int:
    """Return the in-place capacity: English string + trailing padding run.

    The capacity is the number of bytes from ``offset`` up to (but excluding)
    the first non-padding byte that follows the English 0xFF terminator — i.e.
    the room available before the next live data / pointer-table entry.
    """
    end = source_rom.find(b"\xff", offset)
    if end == -1:
        return 0
    cursor = end + 1  # include the terminator slot, then walk the padding run
    while cursor < len(source_rom) and source_rom[cursor] in _PADDING:
        cursor += 1
    return cursor - offset


def apply(rom: bytearray, combined: dict[int, str], source_rom: bytes) -> dict:
    stats = {"written": 0, "no_source": 0, "too_long": 0, "skipped": 0}

    for offset in TARGETS:
        text = combined.get(offset)
        if not text:
            stats["no_source"] += 1
            continue
        encoded = TextEncoder.encode(_normalize_text(text), "pokemon")  # incl 0xFF
        capacity = _english_slot(source_rom, offset)
        if len(encoded) > capacity:
            stats["too_long"] += 1
            continue
        if rom[offset : offset + len(encoded)] == encoded:
            stats["skipped"] += 1
            continue
        # Clear the old slot (English may have been longer) then write FR.
        slot_end = offset + capacity
        rom[offset:slot_end] = b"\xff" * capacity
        rom[offset : offset + len(encoded)] = encoded
        stats["written"] += 1

    return stats


def verify(rom: bytes) -> list[tuple[int, str]]:
    """Return targets whose in-place bytes do not decode to the expected French."""
    from src.core.text_codec import TextDecoder

    bad: list[tuple[int, str]] = []
    for offset, expected in TARGETS.items():
        end = rom.find(b"\xff", offset)
        raw = rom[offset : end + 1] if end != -1 else rom[offset : offset + 40]
        got = TextDecoder.decode_pokemon(raw, preserve_unknown=True).strip()
        if got != expected:
            bad.append((offset, f"expected {expected!r}, got {got!r}"))
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, help="Built French ROM to patch in place")
    parser.add_argument(
        "--source",
        default=str(REPO_ROOT / "input/roms/englishrom.gba"),
        help="English ROM (source of the in-place slot size)",
    )
    parser.add_argument(
        "--combined",
        default=str(DEFAULT_COMBINED),
        help="combined_fr.txt source of truth (offset -> FR text)",
    )
    args = parser.parse_args()

    rom_path = Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    source_rom = Path(args.source).read_bytes()
    combined = load_combined(Path(args.combined))

    stats = apply(rom, combined, source_rom)
    remaining = verify(rom)
    rom_path.write_bytes(rom)

    print("✓ World-Map labels — in-place rewrite:")
    print(f"   - Written:        {stats['written']}")
    if stats["skipped"]:
        print(f"   - Already FR:     {stats['skipped']}")
    if stats["no_source"]:
        print(f"   - No FR source:   {stats['no_source']}")
    if stats["too_long"]:
        print(f"   - Too long (skip): {stats['too_long']}")
    if remaining:
        print("   - ✗ Verification failed:")
        for offset, why in remaining:
            print(f"       0x{offset:08X}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
