"""E2E: in-battle status-condition text abbreviations are Italian.

Mirrors the FR regression guard for status abbreviations (commit
"test(e2e): status Sommeil attendu = SOM (officiel) au lieu de DOR"): the
summary/battle HUD reads 3-letter status abbreviations through a live
pointer table at 0x3DFE18 (stride 8), patched generically for every
registry language by ``patch_status_abbrevs_fr.py --lang-code it`` from
``languages/it/lang.yaml``'s ``status_abbrev`` map.

Freeze ("congelato" -> CON) is deliberately NOT asserted here: the built ROM
currently still shows the French "GEL" at that slot because the underlying
free-space cell already carries French residue in ``input/roms/englishrom.gba``
itself (the patch script only overwrites a cell that still reads the expected
English original, so it skips silently rather than clobbering unknown
content) — the same root cause tracked in the "item descriptions ship French
leftover text" follow-up ticket. This file only asserts on slots verified
clean, matching the tests/README.md convention of not encoding a known-broken
state as "expected".
"""

from __future__ import annotations

import struct

from src.text.charmap_data import BYTE_TO_CHAR

GBA_BASE = 0x08000000
PTR_TABLE_OFFSET = 0x3DFE18
PTR_STRIDE = 8

# (table index, expected Italian abbreviation) — see languages/it/lang.yaml's
# status_abbrev map. Index order is the fixed game-engine order (see
# scripts/patch_status_abbrevs_fr.py's _EN_STATUS).
SLEEP_INDEX = 0
POISON_INDEX = 1
PARALYSIS_INDEX = 2
BURN_INDEX = 3


def _decode_at(rom: bytes, offset: int, max_len: int = 8) -> str:
    result = []
    for i in range(max_len):
        b = rom[offset + i]
        if b == 0xFF:
            break
        result.append(BYTE_TO_CHAR.get(b, f"[{b:02X}]"))
    return "".join(result)


def _abbrev(rom: bytes, index: int) -> str:
    ptr_off = PTR_TABLE_OFFSET + index * PTR_STRIDE
    ptr = struct.unpack_from("<I", rom, ptr_off)[0]
    file_off = ptr - GBA_BASE
    return _decode_at(rom, file_off)


class TestStatusAbbreviationsAreItalian:
    def test_sleep_is_son(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        assert _abbrev(rom, SLEEP_INDEX) == "SON", (
            "Sleep abbreviation must read Italian 'SON' (Sonno), not the "
            "English 'SLP' or a leftover from another language."
        )

    def test_burn_is_sct(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        assert _abbrev(rom, BURN_INDEX) == "SCT", (
            "Burn abbreviation must read Italian 'SCT' (Scottatura)."
        )

    def test_poison_and_paralysis_unchanged_but_readable(self, it_rom_path):
        # Italian's official abbreviations for poison/paralysis are identical
        # to English (PSN/PAR), so lang.yaml declares no override for them —
        # this just guards that the cells still decode cleanly (not corrupted
        # by an adjacent relocation).
        rom = it_rom_path.read_bytes()
        assert _abbrev(rom, POISON_INDEX) == "PSN"
        assert _abbrev(rom, PARALYSIS_INDEX) == "PAR"
