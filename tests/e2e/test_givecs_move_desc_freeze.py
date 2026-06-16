"""Regression guard for the real "give-CS" freeze (ticket « Problème pas de
gain d'objet »).

Root cause — reproduced in-engine by replaying the user's savestate through the
give-CS sequence (see ``test_givecs_freeze_replay.py``), not just statically:
when an NPC hands the player a field move, the engine expands that move's
**description** into ``gStringVar4`` and word-wraps it with CFRU's routine at
``0x089F35F8``, which scans for the ``0xFF`` terminator one byte at a time
(``GetStringWidth`` at ``0x08005Exx`` — observed PC ``0x08006xxx`` at the
freeze). The French build overwrites the descriptions in the original English
data block at ``~0x08482xxx`` in place; a longer French description overruns its
slot and destroys the next entry's ``0xFF`` terminator, fusing a multi-hundred
byte unterminated run. With no terminator in range the wrap scan never ends →
the CPU spins forever → the game freezes on the « Alors, prends cette CS pour
aller le voir. » box and ignores all input.

Why earlier fixes did not hold: that block is referenced by **several** pointer
sources — the move-info table ``0x08488708``, a *third* table ``0x08904000``,
and per-field-move info structs (``0x083DEA80`` / ``0x0887AD30``) read on the
give-CS path. An earlier patch repointed only ``0x08488708``, so the give-CS
struct still pointed at the fused entry and the freeze survived a rebuild. The
fix (``scripts/patch_dup_move_descriptions_fr``) is reference-driven: it
repoints **every** word-aligned pointer into the block whose target lost its
terminator to a freshly relocated, ``0xFF``-terminated copy.

These tests re-read the *built* French ROM and assert that **no** reference into
the move-description block points at an unterminated run — deterministic (no
emulator) so they "hold" as a CI regression guard, and they would have failed on
every pre-fix build (the give-CS struct pointed at a 456-byte fused run).
"""

from __future__ import annotations

import struct

import pytest

from src.core.text_codec import TextDecoder
from tests.e2e.conftest import EN_ROM_PATH, FR_ROM_PATH

ROM_BASE = 0x08000000
# Original English move-description data block that the FR build overwrites in
# place; pointers into this range that lost their terminator are the freeze.
MOVE_DESC_BLOCK = (0x08482000, 0x08484000)
# A genuine move description is 0xFF-terminated within the move-info window in
# far fewer bytes; a longer run means the slot lost its terminator (the freeze).
MAX_DESC_BYTES = 200
# The per-field-move info structs whose description pointer is read when an NPC
# hands the player a field move — the exact give-CS path the user froze on.
GIVE_CS_DESC_STRUCTS = (0x083DEA80, 0x0887AD30)
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


def _block_xrefs(rom: bytes) -> dict[int, list[int]]:
    """Every word-aligned pointer into the move-description block -> cell offsets.

    Mirrors ``scripts.patch_dup_move_descriptions_fr.find_block_xrefs`` so the
    guard checks exactly what the patch repoints. Pointers into ``0x0848xxxx``
    are stored little-endian as ``YY YY 48 08``.
    """
    lo, hi = MOVE_DESC_BLOCK
    refs: dict[int, list[int]] = {}
    start = 0
    while True:
        i = rom.find(b"\x48\x08", start)
        if i < 0:
            break
        start = i + 1
        cell = i - 2
        if cell < 0 or cell % 4:
            continue
        value = struct.unpack("<I", rom[cell:cell + 4])[0]
        if lo <= value < hi:
            refs.setdefault(value, []).append(cell)
    return refs


def _run_to_terminator(rom: bytes, offset: int, limit: int) -> int:
    end = rom.find(b"\xff", offset, offset + limit + 1)
    return (end - offset) if end != -1 else limit + 1


def test_english_move_desc_block_is_clean(en_rom):
    """Sanity anchor: English never freezes here — every reference into the
    move-description block resolves to a 0xFF-terminated run."""
    overflow = [
        (hex(t), run)
        for t, cells in _block_xrefs(en_rom).items()
        if (run := _run_to_terminator(en_rom, t - ROM_BASE, MAX_DESC_BYTES)) > MAX_DESC_BYTES
    ]
    assert not overflow, f"English move-desc block unexpectedly overflows: {overflow}"


def test_no_unterminated_move_desc_reference(fr_rom):
    """THE guard: no pointer into the move-description block — from any table or
    struct — may target an unterminated run. An unterminated target is the exact
    freeze: the give-CS word-wrap scans forever for a 0xFF that never comes.

    This would fail on every pre-fix build (the give-CS struct pointed at a
    456-byte fused run); it passes once the fix repoints all references.
    """
    overflow = []
    for target, cells in _block_xrefs(fr_rom).items():
        run = _run_to_terminator(fr_rom, target - ROM_BASE, MAX_DESC_BYTES)
        if run > MAX_DESC_BYTES:
            overflow.append((hex(target), [hex(ROM_BASE + c) for c in cells], run))
    assert not overflow, (
        "move-description block has references to unterminated/overflowing runs "
        "-> give-CS word-wrap spins forever (freeze). "
        f"{len(overflow)} bad targets: {overflow[:10]}"
    )


def test_give_cs_field_move_structs_terminated(fr_rom):
    """The two field-move info structs read on the give-CS path must point at a
    terminated, correctly-decoded French Cut description — this is the precise
    box the user's savestate froze on."""
    for struct_addr in GIVE_CS_DESC_STRUCTS:
        cell = struct_addr - ROM_BASE
        ptr = struct.unpack("<I", fr_rom[cell:cell + 4])[0]
        assert ROM_BASE <= ptr < ROM_BASE + 0x02000000, (
            f"give-CS struct 0x{struct_addr:08X} has a non-ROM description pointer "
            f"0x{ptr:08X}"
        )
        off = ptr - ROM_BASE
        end = fr_rom.find(b"\xff", off, off + MAX_DESC_BYTES + 1)
        assert end != -1, (
            f"give-CS struct 0x{struct_addr:08X} -> 0x{ptr:08X} description is "
            "unterminated within the window budget (freeze)"
        )
        text = TextDecoder.decode_pokemon(fr_rom[off:end], preserve_unknown=True)
        assert text.startswith(GIVE_CS_DESC_PREFIX), (
            f"give-CS struct 0x{struct_addr:08X} -> 0x{ptr:08X} decodes to "
            f"unexpected text {text!r}"
        )
        assert "abattre des arbres" in text, f"give-CS description truncated: {text!r}"
