#!/usr/bin/env python3
"""Locate and verify the real CFRU/Unbound ability-DESCRIPTION pointer table.

Background (ticket P-171, ability-descriptions slice)
------------------------------------------------------
An earlier ticket claimed the ability descriptions lived at ``0xA37D00-0xA40000``
and proposed writing localized text there. **That address is wrong.** Direct
inspection shows ``0xA37D00`` sits *above* the ability-NAME table (0xA36398,
handled by ``languages/fr/patches/ability_names.py``) inside the generic
builder's Pokédex/move-description free-space relocation pool — writing there
corrupts whatever the free-space allocator happened to place in that build.

This module locates the *real* table with the same method that found the real
move-name table (see ``languages/fr/patches/move_names.py`` docstring): encode a
short, distinctive, exact in-game string, search the ROM for its byte pattern,
then confirm 1:1 index alignment against a reference (here the already-correct
ability-NAME table, whose order is the canonical Gen-3 ability ID order).

What the search finds
---------------------
* The ability descriptions are **pointer-referenced**, not a fixed-stride table.
* ``gAbilityDescriptionPointers`` lives at **file offset 0x96DE04**
  (VA 0x0896DE04): one 32-bit little-endian ROM pointer per ability, **indexed
  by ability ID** — entry *i* is the description for the ability whose name is
  at ``ABILITY_NAMES + i * 17``. Alignment is 1:1 with the name table.
* The description *text* itself is scattered across several free-space pools
  (0x0024Fxxx, 0x00A34F61-0x00A36395 just below the name table, 0x0092xxxx,
  0x00D1xxxx, ...) because Unbound authored/relocated blurbs over many builds —
  so the descriptions are NOT contiguous and MUST be reached through the pointer
  table, never by a fixed stride.
* Ability 0 ("-------") → "No special ability."; ability 2 (Drizzle) →
  "Summons rain in battle."; ability 26 (Levitate) → "Not hit by Ground
  attacks." — all in ability-ID order.
* A *shorter, vanilla* copy of the table also survives at file offset
  0x0024FB08 (VA 0x0824FB08): it aligns for the low IDs but holds junk past the
  ~77 FireRed-vanilla abilities, so it is NOT the live Unbound table. The
  high-index anchors below exist precisely to reject it — the live table is the
  293-entry expanded one at 0x96DE04.
* The ~30 highest-ID Unbound-custom abilities (Air Lock, Vital Spirit, and the
  brand-new "Sound Waves", "Royal Roar", ... at the very end) point into
  late/compressed pools with no authored English blurb — their description
  pointers decode as garbage. Any future localization patch must skip these,
  exactly like the move-name overflow skip.

Consequence for localization
----------------------------
``combined_it.txt`` / ``combined_fr.txt`` contain **zero** ability-description
entries today (verified: none of these blurbs appears in either file). There is
therefore nothing to "align 1:1" yet — the descriptions were simply never
authored for IT/FR. A future ``patch_ability_descriptions_<lang>.py`` would be a
relocate-and-repoint patch driven by THIS pointer table (like
``move_descriptions.py``), NOT an in-place write at the dead 0xA37D00 offset.

Usage:
    python3 languages/en/tools/locate_ability_descriptions.py \
        --rom input/roms/englishrom.gba
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE

GBA_BASE = 0x08000000

# --- Ability NAME table (reference order = canonical Gen-3 ability IDs). -------
# Same geometry as languages/fr/patches/ability_names.py.
ABILITY_NAMES_OFFSET = 0xA36398
ABILITY_NAMES_LAST = 0xA376FC
ABILITY_NAME_STRIDE = 17
ABILITY_COUNT = (ABILITY_NAMES_LAST - ABILITY_NAMES_OFFSET) // ABILITY_NAME_STRIDE + 1  # 293

# --- The real ability-DESCRIPTION pointer table (this module's finding). -------
ABILITY_DESC_POINTER_TABLE = 0x96DE04  # file offset; VA = 0x0896DE04

# The debunked address the original ticket proposed (kept as a negative anchor).
DEAD_CLAIMED_OFFSET = 0xA37D00

# A few (ability-ID, distinctive exact English blurb) anchors used to prove the
# table location by byte-search and to prove 1:1 alignment. Terse Unbound
# wording — verified present in input/roms/englishrom.gba.
ANCHORS: list[tuple[int, str, str]] = [
    (0, "-------", "No special ability."),
    (1, "Stench", "Helps repel wild Pokémon."),
    (2, "Drizzle", "Summons rain in battle."),
    (3, "Speed Boost", "Gradually boosts Speed."),
    (7, "Limber", "Prevents paralysis."),
    (15, "Insomnia", "Prevents sleep."),
    (17, "Immunity", "Prevents poisoning."),
    (26, "Levitate", "Not hit by Ground attacks."),
    (39, "Inner Focus", "Prevents flinching."),
    # High-index anchors: vanilla FireRed's ability-description table (a shorter
    # copy that still lives at 0x0024FB08) aligns for the low IDs but holds junk
    # past the ~77 vanilla abilities. These Unbound-only IDs disambiguate it
    # from the real expanded table.
    (100, "Unseen Fist", "Contact moves bypass Protect."),
    (150, "Protean", "Changes type to match move."),
    (200, "Merciless", "Critically hits poisoned foes."),
    (250, "Ice Face", "Free physical hit. Hail renews."),
]


def _encode(text: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in text)


def _decode(data: bytes, offset: int, maxlen: int = 96) -> str:
    chars: list[str] = []
    if offset < 0:
        return ""
    for i in range(maxlen):
        if offset + i >= len(data):
            break
        b = data[offset + i]
        if b == 0xFF:
            break
        chars.append(BYTE_TO_CHAR.get(b, f"<{b:02X}>"))
    return "".join(chars)


def _name(data: bytes, index: int) -> str:
    return _decode(data, ABILITY_NAMES_OFFSET + index * ABILITY_NAME_STRIDE,
                   ABILITY_NAME_STRIDE)


def _pointer(data: bytes, table: int, index: int) -> int:
    (ptr,) = struct.unpack_from("<I", data, table + index * 4)
    return ptr


def search_blurb(data: bytes, blurb: str) -> list[int]:
    """Return every file offset whose bytes encode ``blurb`` (method (a))."""
    needle = _encode(blurb)
    hits: list[int] = []
    i = data.find(needle)
    while i != -1:
        hits.append(i)
        i = data.find(needle, i + 1)
    return hits


def locate_table(data: bytes) -> int:
    """Find the pointer table by byte-searching a distinctive blurb.

    Uses Drizzle (ability 2, "Summons rain in battle.") as the probe: finds the
    text, then every 32-bit LE pointer to it, then treats each hit as ability
    index 2 and keeps the candidate table base whose anchors *all* align 1:1
    with the ability-NAME table (a raw pointer value can also occur as
    coincidental data bytes, so alignment is the disambiguator). Returns the
    file offset of the table.
    """
    idx, _name_txt, blurb = next(a for a in ANCHORS if a[0] == 2)
    text_hits = search_blurb(data, blurb)
    if not text_hits:
        raise LookupError(f"blurb {blurb!r} not found in ROM")

    candidates: list[int] = []
    for text_off in text_hits:
        ptr_bytes = struct.pack("<I", GBA_BASE + text_off)
        for i in range(0, len(data) - 3, 4):
            if data[i:i + 4] == ptr_bytes:
                base = i - idx * 4  # this hit would be ability index `idx`
                if base >= 0 and verify_alignment(data, base)[0]:
                    candidates.append(base)
    if not candidates:
        raise LookupError(
            f"no pointer table to {blurb!r} aligns with the ability-name table")
    return min(candidates)


def verify_alignment(data: bytes, table: int = ABILITY_DESC_POINTER_TABLE
                     ) -> tuple[bool, list[str]]:
    """Confirm each anchor's description sits at its ability-ID slot. """
    ok = True
    report: list[str] = []
    for index, expect_name, expect_desc in ANCHORS:
        got_name = _name(data, index)
        ptr = _pointer(data, table, index)
        got_desc = _decode(data, ptr - GBA_BASE)
        aligned = got_name == expect_name and got_desc == expect_desc
        ok = ok and aligned
        flag = "ok " if aligned else "!! "
        report.append(
            f"  {flag}#{index:<3} name={got_name!r:16} ptr=0x{ptr:08X} "
            f"desc={got_desc!r}"
        )
    return ok, report


def count_authored(data: bytes, table: int = ABILITY_DESC_POINTER_TABLE) -> int:
    """How many abilities carry a real (text-like) English description."""
    authored = 0
    for i in range(ABILITY_COUNT):
        desc = _decode(data, _pointer(data, table, i) - GBA_BASE)
        if len(desc) < 4:
            continue
        printable = sum(1 for c in desc if c.isalpha() or c in " .,'-“”’()!")
        if printable / len(desc) > 0.85:
            authored += 1
    return authored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=Path,
                        default=Path("input/roms/englishrom.gba"))
    args = parser.parse_args()

    data = args.rom.read_bytes()

    print(f"ability count (from name table): {ABILITY_COUNT}")

    found = locate_table(data)
    print(f"located ability-description pointer table via byte-search: "
          f"0x{found:X} (VA 0x{GBA_BASE + found:08X})")
    print(f"documented constant ABILITY_DESC_POINTER_TABLE: "
          f"0x{ABILITY_DESC_POINTER_TABLE:X}")
    assert found == ABILITY_DESC_POINTER_TABLE, "byte-search disagrees with constant!"

    ok, report = verify_alignment(data)
    print("1:1 alignment with ability-NAME table (canonical ability-ID order):")
    print("\n".join(report))
    print(f"alignment: {'PASS' if ok else 'FAIL'}")

    print(f"abilities with authored English descriptions: "
          f"{count_authored(data)} / {ABILITY_COUNT} "
          f"(the ~30 highest-ID Unbound-custom abilities have no blurb)")

    # Negative anchor: the originally-claimed address is NOT the table.
    dead = _decode(data, DEAD_CLAIMED_OFFSET)
    print(f"debunk: claimed 0x{DEAD_CLAIMED_OFFSET:X} decodes as {dead!r} "
          f"(free-space pool, not an ability description)")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
