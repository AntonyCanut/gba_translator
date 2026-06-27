#!/usr/bin/env python3
"""
Triage the 1 710 orphan offsets in languages/it/combined_it.txt.

An "orphan" is an offset present in the IT file but absent from the EN
reference (languages/en/combined_en.txt).  They fall into two groups:

  * Corrupted / junk — GBA machine-code decoded as text, mojibake from
    a Japanese JSON dump, pure question-mark placeholders, or long binary
    runs.  These are removed from combined_it.txt.

  * Clean — legitimate Italian translations of strings that the French
    pipeline never covered.  Their English source text is extracted from
    the EN ROM and appended to combined_en.txt so the audit can track them.

Usage
-----
    # dry-run (prints what would change, touches nothing)
    python3 scripts/clean_it_orphans.py --dry-run

    # apply (modifies combined_it.txt and combined_en.txt in-place)
    python3 scripts/clean_it_orphans.py

    # apply + regenerate the audit CSV afterwards
    python3 scripts/clean_it_orphans.py --audit
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.core.text_codec import TextDecoder

IT_FILE = REPO_ROOT / "languages" / "it" / "combined_it.txt"
EN_FILE = REPO_ROOT / "languages" / "en" / "combined_en.txt"
EN_ROM = REPO_ROOT / "input" / "roms" / "englishrom.gba"

LINE_RE = re.compile(r"^(\s*0x[0-9A-Fa-f]+\s*:\s*)(.*)$")
OFFSET_RE = re.compile(r"^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$")

# GBA ROM size cap (32 MB) — offsets above this cannot point into the ROM
ROM_SIZE_CAP = 0x2000000

# ── Corruption detectors ────────────────────────────────────────────────────

_P_GBA_BYTECODE = re.compile(r"\\![0-9A-Fa-f]{2}")
_P_PLACEHOLDER = re.compile(r"^[?]+$")
_P_KUN = re.compile(r"\[kun\]")
_P_BINARY = re.compile(r"^[A-Za-z]{30,}")


def corruption_reason(text: str) -> str | None:
    """Return a short reason string if *text* looks corrupted, else None."""
    t = text.strip()
    # GBA machine-code escape sequences like \\!30, \\!7E
    if _P_GBA_BYTECODE.search(t):
        return "gba_bytecode"
    # Pure question-mark placeholders with no Italian content
    if _P_PLACEHOLDER.match(t):
        return "placeholder"
    # Mojibake from Japanese JSON dump (contains [kun] honorific)
    if _P_KUN.search(t):
        return "mojibake"
    # Binary garbage: 30+ consecutive Latin letters with no spaces
    if _P_BINARY.match(t):
        return "binary_garbage"
    return None


# ── EN ROM extraction ───────────────────────────────────────────────────────

_POKEMON_TERMINATOR = 0xFF
_MAX_STRING_LEN = 512


def _read_cfru_string(rom: bytes, offset: int) -> str | None:
    """Decode a CFRU string from *rom* at *offset*.

    Returns None if the offset is out of range or if the decoded text looks
    like binary garbage (no printable ASCII in first 8 bytes, or no 0xFF
    terminator within MAX_STRING_LEN bytes).
    """
    if offset >= len(rom):
        return None
    end = min(offset + _MAX_STRING_LEN, len(rom))
    raw = bytearray()
    pos = offset
    found_terminator = False
    while pos < end:
        b = rom[pos]
        if b == _POKEMON_TERMINATOR:
            found_terminator = True
            break
        raw.append(b)
        pos += 1

    if not found_terminator:
        return None  # no terminator → likely not a text pointer

    if not raw:
        return None  # empty string

    # Basic sanity: CFRU strings start with bytes in the charmap range or
    # common control codes.  Reject strings whose first 4 bytes are all
    # outside [0x00, 0xFE] with multiple high bytes > 0xFC (machine code).
    high_count = sum(1 for b in raw[:8] if b > 0xFC)
    if high_count >= 4:
        return None

    decoded = TextDecoder.decode_pokemon(bytes(raw), preserve_unknown=True)
    # Replace literal newlines so the line stays single-line
    return decoded.replace("\n", "\\n")


# ── Main logic ───────────────────────────────────────────────────────────────


def parse_combined(path: Path) -> "dict[int, str]":
    """Return {offset: text} for the last occurrence of each offset."""
    mapping: dict[int, str] = {}
    if not path.exists():
        return mapping
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            m = OFFSET_RE.match(raw.rstrip("\n"))
            if m:
                mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    ap.add_argument("--audit", action="store_true", help="Re-run audit after applying changes")
    args = ap.parse_args()

    if not IT_FILE.exists():
        print(f"ERROR: {IT_FILE} not found", file=sys.stderr)
        return 1
    if not EN_FILE.exists():
        print(f"ERROR: {EN_FILE} not found", file=sys.stderr)
        return 1

    # ── Load reference sets ──────────────────────────────────────────────────
    en_map = parse_combined(EN_FILE)
    en_offsets = set(en_map.keys())

    # ── Scan IT file ─────────────────────────────────────────────────────────
    it_lines: list[str] = IT_FILE.read_text(encoding="utf-8").splitlines(keepends=True)

    corrupted_lines: list[int] = []        # 1-based line numbers to remove
    clean_orphan_offsets: list[int] = []   # offsets to add to EN reference

    for lineno, raw in enumerate(it_lines, 1):
        m = OFFSET_RE.match(raw.rstrip("\n"))
        if not m:
            continue
        offset = int(m.group(1), 16)
        text = m.group(2)

        if offset in en_offsets:
            continue  # not an orphan

        reason = corruption_reason(text)
        if reason:
            corrupted_lines.append(lineno)
            print(f"  REMOVE [{reason}] line {lineno} 0x{offset:X}: {text[:60]!r}")
        else:
            clean_orphan_offsets.append(offset)

    print(f"\nCorrupted orphans to remove : {len(corrupted_lines)}")
    print(f"Clean orphans to add to EN  : {len(clean_orphan_offsets)}")

    # ── Extract EN text for clean orphans ────────────────────────────────────
    rom: bytes | None = None
    if EN_ROM.exists():
        rom = EN_ROM.read_bytes()
        print(f"ROM loaded: {len(rom):,} bytes ({EN_ROM.name})")
    else:
        print(f"WARNING: EN ROM not found at {EN_ROM} — skipping EN extraction", file=sys.stderr)

    new_en_entries: list[tuple[int, str]] = []  # (offset, decoded_text)
    skipped_no_rom = 0
    skipped_garbage = 0

    for off in clean_orphan_offsets:
        if off in en_offsets:
            continue  # already in EN reference (shouldn't happen but guard)
        if rom is None:
            skipped_no_rom += 1
            continue
        if off >= len(rom):
            skipped_garbage += 1
            continue
        decoded = _read_cfru_string(rom, off)
        if decoded is None:
            skipped_garbage += 1
        else:
            new_en_entries.append((off, decoded))

    print(f"Valid EN extractions        : {len(new_en_entries)}")
    print(f"  skipped (no ROM)          : {skipped_no_rom}")
    print(f"  skipped (garbage/no term) : {skipped_garbage}")

    if args.dry_run:
        print("\n[dry-run] No files modified.")
        return 0

    # ── Rewrite combined_it.txt (remove corrupted lines) ────────────────────
    corrupted_set = set(corrupted_lines)
    new_it_lines = [
        line for lineno, line in enumerate(it_lines, 1)
        if lineno not in corrupted_set
    ]
    IT_FILE.write_text("".join(new_it_lines), encoding="utf-8")
    print(f"\nWrote {IT_FILE.name}: removed {len(corrupted_lines)} corrupted lines "
          f"({len(new_it_lines)} lines remain)")

    # ── Append clean orphans to combined_en.txt ──────────────────────────────
    if new_en_entries:
        block = ["\n# --- Extended from IT orphan audit ---\n"]
        for off, text in sorted(new_en_entries, key=lambda x: x[0]):
            block.append(f"0x{off:06X}: {text}\n")

        with EN_FILE.open("a", encoding="utf-8") as fh:
            fh.writelines(block)
        print(f"Appended {len(new_en_entries)} entries to {EN_FILE.name}")

    # ── Optionally re-run audit ───────────────────────────────────────────────
    if args.audit:
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/audit_translation_coverage.py", "--languages", "it"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        print("\n" + result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
