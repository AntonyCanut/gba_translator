#!/usr/bin/env python3
"""Convert Pokédex height/weight displays from imperial to metric (FR build).

The English ROM displays Pokémon height as feet/inches ("X'Y\"") and weight
as pounds ("X.Y lbs.").  For the French translation, this post-build step
patches the built ROM to show:

  - height: "X.Ym"  (X = dm÷10 = whole metres, Y = dm%10 = decimal digit;
    no floating-point required — the game already stores height in decimetres)
  - weight: "X.Y kg"  (the CFRU lookup table is an identity: value returned
    equals hg, so X.Y = hg÷10 = kg; only the unit label needs changing)

Labels in the Pokédex info panel are updated in-place:
  - "Ht"   → "Ta"  (Taille)
  - "Wt"   → "Po"  (Poids)
  - "lbs." → "kg"

Height function patches (0x1058C4 area) rewrite six small sequences:
  1. Literal pool multiplier 10000 → 1  (eliminates the inch-scaling step)
  2. First divisor 254 → 10  (feet conversion → dm÷10 = whole metres)
  3. Second divisor 120 → 10  (12-inch period → dm%10 = decimal digit)
  4. MOV r6,r0 → MOV r6,r5  (carry integer metres from r5 into r6)
  5. Inch-modulo block → dm%10 block  (r0 = dm – 10·metres = decimal digit)
  6. MOV r5,r0 → MOV r5,r1  (take decimal digit from result register)
  7. Feet-mark character (0xB4) → period (0xAD)
  8. Decimal-digit display: removes BL+shift, writes digit+0xA1 directly
  9. 'm' unit write: replaces inch-digit BL with MOVS r0,#0xE1 / STRB
  10. Inch-mark character (0xB2) → blank (0x00 = space in CFRU)

Every patch verifies the bytes it expects (English original) and is
idempotent (already-patched cells are skipped without error).

Usage:
    python3 scripts/patch_pokedex_metrics_fr.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# (offset, expected_old_bytes, replacement_new_bytes)
PATCHES: list[tuple[int, bytes, bytes]] = [
    # ── Height function at 0x1058C4 ─────────────────────────────────────────
    # 1. Literal pool: multiplier 10000 (0x00002710) → 1 (0x00000001)
    #    Old: LDR r0, [PC] loads 10000 for the inch-scaling multiply.
    #    New: loads 1, so dm × 1 = dm (no-op multiply; divisions handle rest).
    (0x10597C, b"\x10\x27\x00\x00", b"\x01\x00\x00\x00"),

    # 2. First divisor MOVS r1,#254 → MOVS r1,#10
    #    Old: dm × 10000 / 254 ≈ total tenth-inches.
    #    New: dm × 1 / 10 = whole metres.
    (0x105926, b"\xfe\x21", b"\x0a\x21"),

    # 3. Second divisor MOVS r1,#120 → MOVS r1,#10
    #    Old: total_tenth_inches / 120 = feet (12 inches × 10 tenth-inches).
    #    New: dm / 10 used only for dm%10 calculation here.
    (0x10593C, b"\x78\x21", b"\x0a\x21"),

    # 4. MOV r6,r0 → MOV r6,r5
    #    r5 already holds whole metres (dm÷10); carry that into r6 explicitly
    #    so the subsequent dm%10 block can use r6 = metres.
    (0x105942, b"\x06\x1c", b"\x2e\x1c"),

    # 5. Inch-modulo block (8 bytes) → dm%10 block
    #    Old: LSLS/SUBS/LSLS/SUBS sequence computing remaining tenth-inches.
    #    New: MOVS r0,#10 / MULS r0,r6 / SUBS r0,r4,r0 / NOP
    #         r0 = 10·metres; r4 = dm; r4−r0 = dm%10 (decimal digit, 0-9).
    (0x105944,
     b"\x30\x01\x80\x1b\xc0\x00\x28\x1a",
     b"\x0a\x20\x70\x43\x20\x1a\xc0\x46"),

    # 6. MOV r5,r0 → MOV r5,r1
    #    After the dm%10 computation r1 holds the decimal digit;
    #    store it in r5 for later use in the digit-write patches below.
    (0x105952, b"\x05\x1c", b"\x0d\x1c"),

    # 7. Feet-mark character (0xB4) → period (0xAD)
    #    MOVS r0,#0xB4 (foot apostrophe) → MOVS r0,#0xAD (decimal point).
    (0x10599C, b"\xb4\x20", b"\xad\x20"),

    # 8. Decimal-digit write: strip BL+shift, write digit directly (12 bytes)
    #    Old: MOV r0,r5 / MOVS r1,#10 / BL digit_fn / ADDS r0,#0xA1 / STRB
    #    New: MOV r0,r5 / ADDS r0,#0xA1 / STRB / NOP / NOP / NOP
    #         r5 = dm%10 ∈ [0,9]; +0xA1 maps to CFRU digit chars 0xA1-0xAA.
    (0x1059A4,
     b"\x28\x1c\x0a\x21\xde\xf0\x30\xfe\xa1\x30\x20\x70",
     b"\x28\x1c\xa1\x30\x20\x70\xc0\x46\xc0\x46\xc0\x46"),

    # 9. 'm' unit write: replace inch-digit BL with direct char write (14 bytes)
    #    Old: ADD r4,SP,#0x10 / MOV r0,r5 / MOVS r1,#10 / BL / ADDS #0xA1 / STRB
    #    New: ADD r4,SP,#0x10 / MOVS r0,#0xE1 / STRB r0,[r4] / NOP×5
    #         0xE1 = 'm' in CFRU charmap (a=0xD5, m=0xD5+12=0xE1).
    (0x1059B0,
     b"\x04\xac\x28\x1c\x0a\x21\xde\xf0\x65\xfe\xa1\x30\x20\x70",
     b"\x04\xac\xe1\x20\x20\x70\xc0\x46\xc0\x46\xc0\x46\xc0\x46"),

    # 10. Inch-mark character (0xB2) → blank (0x00 = space in CFRU)
    #     The trailing inch mark after the inch digit is replaced with a space
    #     so it renders invisibly after "X.Ym".
    (0x1059C2, b"\xb2\x20", b"\x00\x20"),

    # ── String table at 0x415F98 ─────────────────────────────────────────────
    # 11. "Ht\xFF" → "Ta\xFF"  (Taille)
    #     H=0xC2 t=0xE8 → T=0xCE a=0xD5  (same 3-byte slot, in-place)
    (0x415F98, b"\xc2\xe8\xff", b"\xce\xd5\xff"),

    # 12. "Wt\xFF" → "Po\xFF"  (Poids)
    #     W=0xD1 t=0xE8 → P=0xCA o=0xE3  (same 3-byte slot, in-place)
    (0x415F9B, b"\xd1\xe8\xff", b"\xca\xe3\xff"),

    # 13. "lbs.\xFF" → "kg\xFF\x00\x00"  (unit label, weight stays numeric kg)
    #     l=0xE0 b=0xD6 s=0xE7 .=0xAD → k=0xDF g=0xDB \xFF \x00 \x00
    #     The CFRU weight lookup table is an identity for hg ∈ [1,251], so the
    #     displayed value X.Y already equals hg÷10 = kg with no code change.
    #     Trailing bytes zeroed (still within the same 5-byte slot).
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
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    if applied:
        args.rom.write_bytes(data)
    print(f"Pokédex metrics patches applied: {applied} (of {len(PATCHES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
