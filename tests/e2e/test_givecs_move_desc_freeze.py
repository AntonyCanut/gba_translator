"""Deterministic regression guard for the give-CS freeze (ticket « Problème pas
de gain d'objet »).

Root cause — found in-engine from the user's frozen ``.ss9`` savestate, then
confirmed statically:

When the post-Zeph cutscene hands the player a field move (Coupe/Cut), the
engine word-wraps that move's **description** for the give-CS box. The
description is read through the field-move structs (``0x083DEA80`` /
``0x0887AD30`` …) and the move-info tables (``0x08488708`` / ``0x08904000``),
all of which index the same description string pool. Cut's description lives at
``0x00482BD5`` — an **empty** ``0xFF`` slot in English, but the build writes a
long French sentence there. The longer French text overruns its slot and
destroys the next entry's ``0xFF`` terminator, fusing a multi-hundred-byte run
("Une attaque de base…abattre des arb**Frappe l'ennemi avec une rafale…**") with
no terminator at all. ``GetStringWidth`` then scans for a ``0xFF`` that never
comes → the CPU spins forever → the give-CS box freezes (the screen stops
updating) and the player never gains the item. English never freezes because
its description slots stay terminated.

``scripts/patch_dup_move_descriptions_fr`` repoints **every** consumer of an
overflowing French description to a freshly relocated, ``0xFF``-terminated copy
of the authoritative ``combined_fr.txt`` text. This test re-derives the freeze
invariant independently and asserts the built ROM satisfies it — no live
pointer into the description pool may reach an unterminated French description.
It is deterministic (no emulator) so it "holds" as a CI guard; the in-engine
counterpart is ``test_givecs_freeze_replay.py``.
"""

from __future__ import annotations

import struct

import pytest

from src.core.text_codec import TextDecoder
from tests.e2e.conftest import EN_ROM_PATH, FR_ROM_PATH

ROM_BASE = 0x08000000
# Address span of the move / field-move description string pool.
POOL_LO = 0x00482000
POOL_HI = 0x0048A000
# A genuine description word-wraps in far fewer bytes; a longer run to the next
# 0xFF means the slot lost its terminator (overflow).
OVERFLOW_BUDGET = 160
TEXT_WINDOW = 110
# The Coupe/Cut field-move struct description pointers read on the give-CS path
# (file offsets). These are *the* cells the user's savestate froze on.
GIVE_CS_STRUCT_CELLS = (0x3DEA80, 0x87AD30)


def _is_overflow(rom: bytes, off: int) -> bool:
    return rom.find(b"\xff", off, off + OVERFLOW_BUDGET + 1) < 0


def _is_french_description(rom: bytes, off: int) -> bool:
    """Independent (test-owned) guard: does ``off`` begin a real French
    description, as opposed to the font/data tables or Thumb code that also
    point into the pool?"""
    text = TextDecoder.decode_pokemon(bytes(rom[off:off + TEXT_WINDOW]), preserve_unknown=True)
    if len(text) < 20:
        return False
    letters = sum(ch.isalpha() for ch in text)
    if letters / len(text) < 0.72:
        return False
    if (text.count(" ") + text.count("\n")) < 3:
        return False
    vowels = sum(text.lower().count(v) for v in "eaiou")
    if vowels / max(letters, 1) < 0.25:
        return False
    return True


# A genuine description consumer is a pointer *table* or strided struct array:
# several pool pointers sit close together. The freeze is read through such a
# structure. Isolated singletons that happen to hold a pool address are code
# constants / unused data — English carries the identical ones and never
# freezes — so the invariant only counts *clustered* pointers.
CLUSTER_WINDOW = 0x40


def _pool_pointer_cells(rom: bytes) -> list[int]:
    return [
        cell
        for cell in range(0, len(rom) - 4, 4)
        if ROM_BASE + POOL_LO <= struct.unpack_from("<I", rom, cell)[0] < ROM_BASE + POOL_HI
    ]


def _unterminated_description_pointers(rom: bytes) -> list[tuple[int, int]]:
    """Every *clustered* word-aligned pointer into the pool whose target is a
    genuine, overflowing French description -> would freeze GetStringWidth."""
    cells = _pool_pointer_cells(rom)
    cellset = set(cells)
    bad = []
    for cell in cells:
        # Clustered = another pool pointer within CLUSTER_WINDOW bytes (a real
        # table / struct array), not an isolated code/data singleton.
        clustered = any(
            other != cell and abs(other - cell) <= CLUSTER_WINDOW and other in cellset
            for other in range(cell - CLUSTER_WINDOW, cell + CLUSTER_WINDOW + 1, 4)
        )
        if not clustered:
            continue
        target = struct.unpack_from("<I", rom, cell)[0] - ROM_BASE
        if _is_overflow(rom, target) and _is_french_description(rom, target):
            bad.append((cell, target))
    return bad


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


def test_english_pool_has_no_unterminated_description(en_rom):
    """Sanity anchor: English never freezes here — no live pointer reaches an
    unterminated description."""
    bad = _unterminated_description_pointers(en_rom)
    assert not bad, f"English unexpectedly has unterminated description pointers: {bad[:5]}"


def test_no_consumer_reaches_unterminated_description(fr_rom):
    """The freeze invariant: after the build, NO pointer into the description
    pool may reach an unterminated French description. Each such pointer is a
    word-wrap that spins forever (the exact give-CS freeze)."""
    bad = _unterminated_description_pointers(fr_rom)
    assert not bad, (
        f"{len(bad)} live pointer(s) still reach an unterminated French "
        f"description -> give-CS / move-info word-wrap freezes. "
        f"First offenders (cell -> target): "
        f"{[(hex(c + ROM_BASE), hex(t)) for c, t in bad[:8]]}"
    )


def test_give_cs_field_move_description_is_terminated(fr_rom):
    """The Coupe/Cut field-move struct pointers (the exact cells the user froze
    on) must resolve to a terminated, coherent French description."""
    for cell in GIVE_CS_STRUCT_CELLS:
        value = struct.unpack_from("<I", fr_rom, cell)[0]
        assert ROM_BASE <= value < ROM_BASE + 0x02000000, (
            f"give-CS struct cell 0x{cell + ROM_BASE:08x} is not a ROM pointer")
        target = value - ROM_BASE
        end = fr_rom.find(b"\xff", target, target + OVERFLOW_BUDGET + 1)
        assert end != -1, (
            f"give-CS struct 0x{cell + ROM_BASE:08x} -> 0x{target:08x} is "
            "unterminated -> the word-wrap freezes")
        text = TextDecoder.decode_pokemon(fr_rom[target:end], preserve_unknown=True)
        assert "attaque de base" in text and "abattre" in text, (
            f"give-CS (Coupe) description corrupted/truncated: {text!r}")
