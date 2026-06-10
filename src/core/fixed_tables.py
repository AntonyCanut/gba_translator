#!/usr/bin/env python3
"""Fixed-width name tables that text reinsertion must never rewrite.

The engine reads these tables cell by cell (``table_base + index *
stride``), stopping at the 0xFF terminator inside the cell. The text
extractor, however, sees them as a flat run of strings: the zero padding
that closes the previous cell is decoded as leading spaces of the next
entry. Writing a translation back at such an extracted offset strips
that padding, shifts the name off its cell boundary and overwrites the
neighbouring terminator — in-battle this rendered Tackle as
``hargeurPlaquage`` (two move names fused, first letter eaten).

The name tables in the source ROM already hold the official French
names (moves, species), so the correct handling is to leave every byte
of these ranges untouched. Ranges were verified structurally against
the source ROM (cells of ``stride`` bytes: name + 0xFF + zero padding).
"""

from __future__ import annotations

# (start, end, description) — offsets into the ROM file, end exclusive.
FIXED_TABLE_RANGES = (
    # 894 move-name cells of 13 bytes; already French in the source ROM.
    (0x1B2980, 0x1B56E6, 'attack names'),
    # Species info structs; each embeds a Pokédex category field whose
    # rewrite corrupted struct-adjacent bytes (all kinds became the
    # truncated word "Pokémon"). Entries observed at struct+0x12, every
    # 36 bytes, from 0x1A35812 to 0x1A3AB9A.
    (0x1A35800, 0x1A3ABB0, 'species info / Pokédex category'),
    # 1295 species-name cells of 11 bytes; already French in the source.
    (0x166A981, 0x166E126, 'species names'),
)


def in_fixed_table(offset: int) -> bool:
    """True when ``offset`` falls inside a protected fixed-width table."""
    return any(start <= offset < end for start, end, _ in FIXED_TABLE_RANGES)
