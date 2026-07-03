#!/usr/bin/env python3
"""Convert Pokédex height/weight displays from imperial to metric (Italian build).

Port of ``patch_pokedex_metrics_fr.py`` — see that module's docstring for the
full reverse-engineering of ``PrintMonHeight``/``PrintMonWeight``. The Thumb
code patches (feet/inches -> metres/decimetres, pounds -> kilograms) are
entirely language-agnostic (they operate on the raw stored decimetre/hectogram
values, not on any text), so they are byte-identical to the French/German
versions. Italy uses the metric system exactly like France and Germany, so the
same conversion is needed and the same "kg" unit string applies verbatim.

Only the two-letter field labels differ:
  - "Ht"   -> "Al"  (Altezza = height)
  - "Wt"   -> "Pe"  (Peso = weight)
  - "lbs." -> "kg"  (identical to French/German — same unit word in Italian)

Every patch verifies the bytes it expects (English original) and is
idempotent (already-patched cells are skipped without error).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Clean metres/decimal block written over the English feet/inch arithmetic at
# 0x10592E (38 bytes). See patch_pokedex_metrics_fr.py module docstring, patch 3.
_HEIGHT_BLOCK_NEW = (
    bytes.fromhex("2e1c0a207043201a051c")   # adds r6,r5 / movs r0,#10 / muls r0,r6 / subs r0,r4,r0 / adds r5,r0
    + b"\xc0\x46" * 14                        # NOP padding to fill the 38-byte span
)
_HEIGHT_BLOCK_OLD = bytes.fromhex(
    "0a21def0a8fe042800d90a35281c7821def065fe061c3001801bc000281a0a21def05dfe051c"
)
assert len(_HEIGHT_BLOCK_NEW) == len(_HEIGHT_BLOCK_OLD) == 0x105954 - 0x10592E

# (offset, expected_old_bytes, replacement_new_bytes)
PATCHES: list[tuple[int, bytes, bytes]] = [
    # ── Height function at 0x1058C4 ─────────────────────────────────────────
    # 1. Literal pool: multiplier 10000 (0x00002710) → 1 (0x00000001)
    (0x10597C, b"\x10\x27\x00\x00", b"\x01\x00\x00\x00"),

    # 2. First divisor MOVS r1,#254 → MOVS r1,#10  (dm ÷ 10 = whole metres)
    (0x105926, b"\xfe\x21", b"\x0a\x21"),

    # 3. Clean metres/decimal block (replaces the feet/inch arithmetic)
    (0x10592E, _HEIGHT_BLOCK_OLD, _HEIGHT_BLOCK_NEW),

    # 4. Feet-mark character (0xB4) → period (0xAD)
    (0x10599C, b"\xb4\x20", b"\xad\x20"),

    # 5. Decimal-digit write: strip BL+shift, write r5 (decimal) directly (12 bytes)
    #    adds r0,r5,#0 / adds r0,#0xA1 / strb r0,[r4] / NOP×3
    (0x1059A4,
     b"\x28\x1c\x0a\x21\xde\xf0\x30\xfe\xa1\x30\x20\x70",
     b"\x28\x1c\xa1\x30\x20\x70\xc0\x46\xc0\x46\xc0\x46"),

    # 6. 'm' unit write: replace inch-digit BL with direct char write (14 bytes)
    #    add r4,sp,#0x10 / movs r0,#0xE1 ('m') / strb r0,[r4] / NOP×5
    (0x1059B0,
     b"\x04\xac\x28\x1c\x0a\x21\xde\xf0\x65\xfe\xa1\x30\x20\x70",
     b"\x04\xac\xe1\x20\x20\x70\xc0\x46\xc0\x46\xc0\x46\xc0\x46"),

    # 7. Inch-mark character (0xB2) → blank (0x00 = space in CFRU)
    (0x1059C2, b"\xb2\x20", b"\x00\x20"),

    # ── Weight function at 0x105A3C ──────────────────────────────────────────
    # 7b. Conversion divisor: 4536 (hg→lbs×100) → 10000 (hg→kg×100).
    (0x105AD4, b"\xb8\x11\x00\x00", b"\x10\x27\x00\x00"),

    # ── String table at 0x415F98 ─────────────────────────────────────────────
    # 8. "Ht\xFF" → "Al\xFF"  (Altezza; A=0xBB, l=0xE0)
    (0x415F98, b"\xc2\xe8\xff", b"\xbb\xe0\xff"),

    # 9. "Wt\xFF" → "Pe\xFF"  (Peso; P=0xCA, e=0xD9)
    (0x415F9B, b"\xd1\xe8\xff", b"\xca\xd9\xff"),

    # 10. "lbs.\xFF" → "kg\xFF\x00\x00"  (weight stays numeric kg; identical to French/German)
    (0x415FA0, b"\xe0\xd6\xe7\xad\xff", b"\xdf\xdb\xff\x00\x00"),
]


def apply_patches(data: bytearray, patches: list = PATCHES) -> int:
    """Apply *patches* to *data* in-place; return the number applied.

    Raises ``ValueError`` when a patch's expected bytes don't match and the
    slot does not already hold the replacement (i.e. unexpected divergence).
    """
    applied = 0
    for offset, old, new in patches:
        if len(old) != len(new):
            raise ValueError(f"0x{offset:X}: length mismatch ({len(old)} vs {len(new)})")
        current = bytes(data[offset: offset + len(old)])
        if current == new:
            continue  # already patched — idempotent
        if current != old:
            raise ValueError(
                f"0x{offset:X}: unexpected bytes {current.hex(' ')} "
                f"(expected {old.hex(' ')})"
            )
        data[offset: offset + len(new)] = new
        applied += 1
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-it.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    if applied:
        args.rom.write_bytes(data)
    print(f"Pokédex metrics patches applied: {applied} (of {len(PATCHES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
