#!/usr/bin/env python3
"""Audit English place names on every live DE surface.

The English ROM is the authority.  The audit follows the pointer cells used by
the English build at the same locations in the German build, so dead strings
do not create false confidence.  It also verifies in-place World Map labels and
the line-control/arrow topology of every real sign panel.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from languages.de.toponyms import (  # noqa: E402
    _source_spelling,
    audit_combined,
    load_catalog,
    load_combined,
)
from scripts.audit_arrow_line_start_fr import (  # noqa: E402
    ARROW_BYTES,
    LINE_BREAK_BYTES,
    audit as audit_source_arrows,
    english_is_panel,
)
from src.core.text_codec import TextDecoder, TextEncoder  # noqa: E402

GBA_BASE = 0x08000000
DEFAULT_EN_ROM = REPO_ROOT / "input/roms/englishrom.gba"
DEFAULT_DE_ROM = REPO_ROOT / "output/roms/GenedRom-de.gba"
DEFAULT_EN_COMBINED = REPO_ROOT / "languages/en/combined_en.txt"
DEFAULT_DE_COMBINED = REPO_ROOT / "languages/de/combined_de.txt"

# Representative consumers for every special delivery layer.  Generic
# dialogue pointers are discovered automatically from the English ROM below.
LIVE_SURFACES = {
    # zone table / fly banners
    0x003F1CBC: 0x071FC80,
    0x00721150: 0x071FC80,
    0x003F1E34: 0x0B51EAC,
    0x0078D809: 0x078D811,
    0x0078D849: 0x078D851,
    0x0078D7C0: 0x078D7C8,
    # in-place World Map labels
    0x003F1D34: 0x0B500A0,
    0x003F1DD8: 0x0B535C8,
    # arrow-leading junction panels
    0x01E93136: 0x1F70E41,
    0x01E93496: 0x1F72353,
    0x01E9352F: 0x1F72691,
    0x01E93538: 0x1F726C0,
    0x01E93541: 0x1F726FC,
    0x01E9354A: 0x1F72735,
    0x01E93553: 0x1F7276E,
    0x01E9355C: 0x1F727A7,
    0x01E93565: 0x1F727D0,
    0x01E9356E: 0x1F72808,
}
IN_PLACE_LABELS = (0x0B500A0, 0x0B535C8)


def _referrers(rom: bytes, offset: int) -> list[int]:
    needle = struct.pack("<I", GBA_BASE + offset)
    return [match.start() for match in re.finditer(re.escape(needle), rom)]


def _raw_at(rom: bytes, offset: int, limit: int = 2048) -> bytes | None:
    if not 0 <= offset < len(rom):
        return None
    end = rom.find(b"\xff", offset, min(len(rom), offset + limit))
    return None if end < 0 else rom[offset : end + 1]


def read_live_string(
    rom: bytes, pointer_offset: int, limit: int = 2048
) -> tuple[int | None, bytes | None]:
    """Follow one GBA pointer and require an FF terminator within ``limit``."""
    if not 0 <= pointer_offset <= len(rom) - 4:
        return None, None
    pointer = struct.unpack_from("<I", rom, pointer_offset)[0]
    target = pointer - GBA_BASE
    if not 0 <= target < len(rom):
        return None, None
    return target, _raw_at(rom, target, limit)


def _control_signature(raw: bytes) -> tuple[int, ...]:
    return tuple(byte for byte in raw if byte in ARROW_BYTES | LINE_BREAK_BYTES)


def arrows_are_at_line_start(raw: bytes) -> bool:
    """Return true when every panel arrow is first or follows a line control."""
    arrows = [index for index, byte in enumerate(raw) if byte in ARROW_BYTES]
    return bool(arrows) and all(
        index == 0 or raw[index - 1] in LINE_BREAK_BYTES for index in arrows
    )


def _contains(raw: bytes, text: str) -> bool:
    return TextEncoder.encode_pokemon(text)[:-1] in raw


def audit_rom(
    english_rom: bytes,
    german_rom: bytes,
    english_combined: dict[int, str],
    german_combined: dict[int, str],
) -> list[str]:
    """Return live-pointer, canonical-name, terminator and panel violations."""
    records = load_catalog()
    violations: list[str] = []
    checked_slots: set[int] = set()

    def check_slot(slot: int, source_offset: int) -> None:
        if slot in checked_slots:
            return
        checked_slots.add(slot)
        target, raw = read_live_string(german_rom, slot)
        if target is None:
            violations.append(f"0x{slot:08X}: invalid live pointer")
            return
        if raw is None:
            violations.append(f"0x{slot:08X} -> 0x{target:08X}: unterminated")
            return
        en_text = english_combined.get(source_offset, "")
        for record in records:
            spelling = _source_spelling(en_text, record.canonical)
            if spelling and not _contains(raw, spelling):
                violations.append(
                    f"0x{slot:08X} -> 0x{target:08X}: missing {spelling!r}"
                )
            if spelling:
                decoded = TextDecoder.decode_pokemon(raw, preserve_unknown=True).casefold()
                for alias in record.aliases:
                    if alias.casefold() in decoded:
                        violations.append(
                            f"0x{slot:08X} -> 0x{target:08X}: forbidden {alias!r}"
                        )

    # Explicit layer coverage, including names that generic extraction misses.
    for slot, source_offset in LIVE_SURFACES.items():
        check_slot(slot, source_offset)

    # All pointer-reachable literal dialogue/location surfaces grounded in EN.
    for source_offset, en_text in english_combined.items():
        if not any(_source_spelling(en_text, record.canonical) for record in records):
            continue
        for slot in _referrers(english_rom, source_offset):
            check_slot(slot, source_offset)

    # Two labels are also consumed directly in place by the World Map engine.
    for offset in IN_PLACE_LABELS:
        raw = _raw_at(german_rom, offset, 128)
        expected = german_combined.get(offset)
        if raw is None:
            violations.append(f"0x{offset:08X}: in-place label unterminated")
        elif not expected or not _contains(raw, expected):
            got = TextDecoder.decode_pokemon(raw, preserve_unknown=True)
            violations.append(
                f"0x{offset:08X}: expected in-place {expected!r}, got {got!r}"
            )

    # Every English-grounded map panel must keep identical break/arrow controls.
    for offset in range(0x1F70D00, 0x1F72950):
        if offset not in english_combined or not english_is_panel(english_rom, offset):
            continue
        en_raw = _raw_at(english_rom, offset, 512)
        for slot in _referrers(english_rom, offset):
            target, de_raw = read_live_string(german_rom, slot, 512)
            if de_raw is None:
                violations.append(f"panel 0x{offset:08X}: live target unterminated")
                continue
            if not arrows_are_at_line_start(de_raw):
                violations.append(f"panel 0x{offset:08X}: arrow is mid-line")
            if en_raw is not None and _control_signature(de_raw) != _control_signature(en_raw):
                violations.append(f"panel 0x{offset:08X}: line/arrow controls changed")
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_DE_ROM)
    parser.add_argument("--english", type=Path, default=DEFAULT_EN_ROM)
    parser.add_argument("--combined", type=Path, default=DEFAULT_DE_COMBINED)
    args = parser.parse_args(argv)

    missing = [path for path in (args.rom, args.english, args.combined) if not path.exists()]
    if missing:
        print("missing input: " + ", ".join(map(str, missing)), file=sys.stderr)
        return 2
    records = load_catalog()
    source_violations = audit_combined(DEFAULT_EN_COMBINED, args.combined, records)
    arrow_violations = audit_source_arrows(args.combined, args.english.read_bytes())
    rom_violations = audit_rom(
        args.english.read_bytes(),
        args.rom.read_bytes(),
        load_combined(DEFAULT_EN_COMBINED),
        load_combined(args.combined),
    )
    violations = source_violations + [
        f"0x{offset:08X}: source arrow misplaced (line {line})"
        for offset, line, _text, _bad in arrow_violations
    ] + rom_violations
    if violations:
        print(f"FAIL: {len(violations)} DE English-toponym violation(s)")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print("OK: DE live pointers, English toponyms, terminators and panel arrows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
