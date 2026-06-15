"""Regression guard for the real "give-CS" freeze (ticket « Problème pas de
gain d'objet »).

Root cause — found in-engine from the user's frozen savestate, not statically:
when the give-CS sequence hands the player a field move, the engine expands
that move's **description** into a RAM buffer and word-wraps it with CFRU's
routine at ``0x089F35F8``, which scans for the ``0xFF`` terminator one byte at
a time (``GetStringWidth`` at ``0x08005Exx``). The descriptions are read
through a **second** move-description pointer table at ``0x08488708`` — a
duplicate of the summary table ``0x0899F190``. ``patch_move_descriptions_fr``
only re-wraps/relocates the summary table, so the duplicate still pointed at
the original slots, where the longer French descriptions overran their storage
and destroyed the next entry's ``0xFF`` terminator (a ~720-byte unterminated
fused run at ``0x0848_2ACD``). With no terminator in range the wrap scan never
ends → the CPU spins forever → the game freezes on the « Alors, prends cette
CS… » box and ignores all input.

English never freezes here: every English description fits its slot and stays
terminated (asserted below). ``scripts/patch_dup_move_descriptions_fr`` repoints
every overflowing duplicate-table entry to a freshly relocated, 0xFF-terminated
copy of the authoritative French text. This test re-reads the *built* French
ROM and asserts that table is clean — deterministic (no emulator) so it "holds"
as a CI regression guard.
"""

from __future__ import annotations

import struct

import pytest

from src.core.text_codec import TextDecoder
from tests.e2e.conftest import EN_ROM_PATH, FR_ROM_PATH

ROM_BASE = 0x08000000
DUP_TABLE = 0x08488708          # second (move-info / give-CS) description table
DUP_TABLE_LEN = 346             # valid ROM pointers in the table
# A genuine move description fits the move-info window in far fewer bytes; a
# longer run to the next 0xFF means the slot lost its terminator (overflow).
MAX_DESC_BYTES = 200
# The give-CS field move's description ("Coupe"/Cut), keyed by its original
# ROM offset; this is the exact entry the user's savestate froze on.
GIVE_CS_DESC_OFFSET = 0x482BD5
GIVE_CS_DESC_PREFIX = "Une attaque de base."


@pytest.fixture(scope="module")
def fr_rom():
    if not FR_ROM_PATH.exists():
        pytest.skip("GenedRom-fr.gba not found in output/roms/ (run `make build-fr`)")
    return FR_ROM_PATH.read_bytes()


@pytest.fixture(scope="module")
def en_rom():
    if not EN_ROM_PATH.exists():
        pytest.skip("englishrom.gba not found")
    return EN_ROM_PATH.read_bytes()


def _entry_pointer(rom: bytes, index: int) -> int | None:
    cell = DUP_TABLE - ROM_BASE + index * 4
    value = struct.unpack("<I", rom[cell:cell + 4])[0]
    if ROM_BASE <= value < ROM_BASE + 0x02000000:
        return value - ROM_BASE
    return None


def _bytes_to_terminator(rom: bytes, offset: int, limit: int) -> int:
    end = rom.find(b"\xff", offset, offset + limit + 1)
    return (end - offset) if end != -1 else limit + 1


def test_english_dup_table_is_clean(en_rom):
    """Sanity anchor: English never freezes here because every duplicate-table
    description is 0xFF-terminated within the window budget."""
    overflow = [
        i
        for i in range(DUP_TABLE_LEN)
        if (off := _entry_pointer(en_rom, i)) is not None
        and _bytes_to_terminator(en_rom, off, MAX_DESC_BYTES) > MAX_DESC_BYTES
    ]
    assert not overflow, f"English duplicate table unexpectedly overflows: {overflow}"


def test_dup_move_desc_table_all_terminated(fr_rom):
    """Every entry of the give-CS move-description table must be 0xFF-terminated
    within the window budget. An unterminated entry is the exact freeze this
    ticket is about: the wrap routine scans forever for a 0xFF that never comes.
    """
    overflow = []
    for i in range(DUP_TABLE_LEN):
        off = _entry_pointer(fr_rom, i)
        if off is None:
            continue
        run = _bytes_to_terminator(fr_rom, off, MAX_DESC_BYTES)
        if run > MAX_DESC_BYTES:
            ptr = struct.unpack("<I", fr_rom[DUP_TABLE - ROM_BASE + i * 4:
                                             DUP_TABLE - ROM_BASE + i * 4 + 4])[0]
            overflow.append((i, hex(ptr), run))
    assert not overflow, (
        "duplicate move-description table has unterminated/overflowing entries "
        "-> give-CS word-wrap spins forever (freeze). "
        f"{len(overflow)} bad entries: {overflow[:10]}"
    )


def test_give_cs_field_move_description_intact(fr_rom):
    """The specific description the user's savestate froze on must now be a
    terminated, correctly-decoded French string."""
    found = [
        i
        for i in range(DUP_TABLE_LEN)
        if _entry_pointer(fr_rom, i) is not None
    ]
    assert found, "duplicate table has no resolvable entries"

    # Locate the give-CS entry by its decoded text (its pointer is relocated).
    matches = []
    for i in range(DUP_TABLE_LEN):
        off = _entry_pointer(fr_rom, i)
        if off is None:
            continue
        end = fr_rom.find(b"\xff", off, off + MAX_DESC_BYTES + 1)
        if end == -1:
            continue
        text = TextDecoder.decode_pokemon(fr_rom[off:end], preserve_unknown=True)
        if text.startswith(GIVE_CS_DESC_PREFIX):
            matches.append((i, text))

    assert matches, (
        f"give-CS field-move description (starts {GIVE_CS_DESC_PREFIX!r}) not "
        "found as a terminated entry in the duplicate table"
    )
    # It must read as the full, coherent French description.
    _, text = matches[0]
    assert "abattre des arbres" in text, f"give-CS description text truncated: {text!r}"
