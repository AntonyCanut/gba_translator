#!/usr/bin/env python3
"""Patch status condition abbreviations from English to official French.

The Pokémon summary screen reads 3-letter status abbreviations through a
pointer table at 0x3DFE18 (stride 8 — a 4-byte pointer followed by 4 bytes of
padding). Following each live pointer lands on a 3-char, 0xFF-terminated string
(packed at 0x41790C..0x41791C in the stock EN ROM):

  idx0 → SLP (Sleep)     → SOM (Sommeil)
  idx1 → PSN (Poison)    → EMP (Empoisonné)
  idx2 → PAR (Paralysis) → PAR (no change)
  idx3 → BRN (Burn)      → BRL (Brûlure)
  idx4 → FRZ (Frozen)    → GEL (Gelé)

Why this is a class-3 *post-build* patch and not a `combined_fr.txt` entry:
these offsets never appear in the translation pipeline (absent from the
injection JSON, the Spanish extract AND `combined_fr.txt`), so no translation
pass touches them. A class-1 fix in `combined_fr.txt` would also be wiped every
time that volatile file is regenerated. Patching the bytes in place here — as
committed code wired into `make build-fr`, exactly like
`patch_cfru_type_names_fr.py` for the type names — is immune to those rewrites.

Each FR abbreviation is the same byte-length (3) as the EN original and ends
with 0xFF, so in-place replacement is exact (the pointer never moves).

The patch is idempotent and self-healing: it overwrites the EN original *or* any
previously-shipped FR variant (e.g. the old "DOR" for sleep), so re-running it
over an already-built ROM converges to the current target ("SOM", the official
French abbreviation for Sommeil) without a full rebuild.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.text_codec import POKEMON_TABLE

ENC = POKEMON_TABLE
REV = {v: k for k, v in ENC.items()}
GBA_BASE = 0x08000000

# Pointer table base and stride
PTR_TABLE_OFFSET = 0x3DFE18
PTR_STRIDE = 8  # 4-byte pointer + 4 bytes padding

# English originals at each table index (game-engine order, fixed).
# key = lang.yaml status_abbrev key, value = (table_index, EN_3char)
_EN_STATUS = {
    "sleep":     (0, "SLP"),
    "poison":    (1, "PSN"),
    "paralysis": (2, "PAR"),
    "burn":      (3, "BRN"),
    "freeze":    (4, "FRZ"),
    # "faint" → "KO" is not stored in this table; skip it.
}

# Each entry: table index, EN original, FR target, and the set of *prior* FR
# variants we are willing to overwrite (so a re-run self-heals an older build).
STATUS_PATCHES = [
    {"index": 0, "en": "SLP", "fr": "SOM", "prior": {"DOR"}},  # Sommeil
    {"index": 1, "en": "PSN", "fr": "EMP", "prior": set()},    # Empoisonné
    # index 2 = PAR, identical in FR → no entry
    {"index": 3, "en": "BRN", "fr": "BRL", "prior": set()},    # Brûlure
    {"index": 4, "en": "FRZ", "fr": "GEL", "prior": set()},    # Gelé
]


def _patches_from_registry(abbrevs: dict) -> List[dict]:
    """Build a STATUS_PATCHES-compatible list from a lang.yaml status_abbrev dict.

    Entries whose target equals the EN original are silently omitted (no-op).
    No ``prior`` healing is needed for a first-time build — the only accepted
    predecessor is the English string itself.
    """
    patches = []
    for key, (idx, en_abbrev) in _EN_STATUS.items():
        target = abbrevs.get(key, "").strip().upper()
        if not target or target == en_abbrev:
            continue  # identical to EN → skip (e.g. PAR stays PAR)
        if len(target) != 3:
            print(
                f"  WARN status_abbrev[{key!r}]={target!r}: expected 3 chars — skip",
                file=sys.stderr,
            )
            continue
        patches.append({"index": idx, "en": en_abbrev, "fr": target, "prior": set()})
    return sorted(patches, key=lambda e: e["index"])


def _encode(text: str) -> bytes:
    return bytes([ENC[c] for c in text])


def _decode_at(rom: bytes, off: int, maxlen: int = 8) -> str:
    chars = []
    for i in range(maxlen):
        b = rom[off + i]
        if b == 0xFF:
            break
        chars.append(REV.get(b, f"[{b:02X}]"))
    return "".join(chars)


def apply_to_rom(
    rom: bytearray,
    dry_run: bool = False,
    patches: List[dict] | None = None,
) -> int:
    """Patch status abbreviations in `rom` in place. Returns the change count.

    ``patches`` defaults to the module-level ``STATUS_PATCHES`` (French).
    Pass a list built by ``_patches_from_registry()`` for other languages.
    """
    if patches is None:
        patches = STATUS_PATCHES
    changes = 0

    for entry in patches:
        idx = entry["index"]
        en_text = entry["en"]
        fr_text = entry["fr"]
        accepted = {en_text} | entry["prior"]

        ptr_off = PTR_TABLE_OFFSET + idx * PTR_STRIDE
        ptr_raw = struct.unpack_from("<I", rom, ptr_off)[0]
        file_off = ptr_raw - GBA_BASE

        if not (0 < file_off < len(rom)):
            print(
                f"  WARN index={idx}: pointer 0x{ptr_raw:08X} out of range — skip",
                file=sys.stderr,
            )
            continue

        current = _decode_at(rom, file_off)
        if current == fr_text:
            continue  # already at target
        if current not in accepted:
            print(
                f"  WARN 0x{file_off:06X} (index={idx}): expected one of "
                f"{sorted(accepted)} got «{current}» — skip",
                file=sys.stderr,
            )
            continue

        fr_encoded = _encode(fr_text)
        fr_len = len(fr_encoded)
        cur_len = len(current)
        if fr_len > cur_len:
            print(
                f"  ERROR 0x{file_off:06X}: FR «{fr_text}» ({fr_len}) longer than "
                f"«{current}» ({cur_len}) — skip",
                file=sys.stderr,
            )
            continue

        if not dry_run:
            rom[file_off : file_off + fr_len] = fr_encoded
            # Keep the 0xFF terminator: pad any freed trailing bytes.
            for j in range(fr_len, cur_len):
                rom[file_off + j] = 0xFF

        print(f"  0x{file_off:06X}  «{current}» → «{fr_text}»")
        changes += 1

    return changes


def apply_patches(
    rom_path: Path,
    dry_run: bool = False,
    patches: List[dict] | None = None,
) -> int:
    rom = bytearray(rom_path.read_bytes())
    changes = apply_to_rom(rom, dry_run=dry_run, patches=patches)
    if not dry_run and changes:
        rom_path.write_bytes(rom)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--lang-code",
        default=None,
        help=(
            "Language code to read status_abbrev from the registry "
            "(e.g. 'it', 'de'). Defaults to the built-in French table."
        ),
    )
    args = parser.parse_args()

    patches = None
    if args.lang_code and args.lang_code != "fr":
        from src.i18n import load_registry
        registry = load_registry()
        config = registry.get(args.lang_code)
        patches = _patches_from_registry(config.status_abbrev)
        print(f"  Using status_abbrev from registry: {config.code} ({config.name})")

    n = apply_patches(args.rom, dry_run=args.dry_run, patches=patches)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_status_abbrevs_fr: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
