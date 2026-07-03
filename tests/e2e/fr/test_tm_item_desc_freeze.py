r"""Deterministic regression guard for the "Volcan Cendre" TM-pickup freeze.

Root cause — reproduced in-engine from the user's battery save (picking up
``CT94`` to the left of the player in the ash volcano), then confirmed
statically:

Every Technical/Hidden Machine item (``CT94``, ``CT76``, ``CS08`` …) stores its
bag description behind the pointer at ``+0x14`` of its 44-byte entry in the item
table (``0x876074``). Those pointers index a tightly packed move-description
region around ``0xA3xxxx`` whose English slots are tiny — several are empty
(a lone ``0xFF``). The inline-overrides pass writes the much longer French
description **in place**, so it overruns its slot and destroys the next entry's
``0xFF`` terminator: the whole region collapses into one multi-hundred-byte run
("…une gemme ou un\ **Une graine inquiétante**…" — Calcination fused into
Vampigraine, Suc Digestif, …). When the bag renders such a description,
``GetStringWidth`` scans for a ``0xFF`` that never comes → the CPU spins forever
→ frozen screen. English never freezes because its slots stay terminated.

``scripts/patch_tm_item_descriptions_fr`` gives every CT/CS item its own
relocated, ``0xFF``-terminated copy of the authoritative ``combined_fr.txt``
text and repoints the entry at it. This test re-derives the invariant
independently: no CT/CS item description may point into the fused region or run
on without a terminator. RED on the pre-patch build, GREEN after.
"""

from __future__ import annotations

import struct

import pytest

from src.core.text_codec import TextDecoder
from tests.e2e.conftest import FR_ROM_PATH

ROM_BASE = 0x08000000

# Item table layout (see scripts/patch_item_names_fr.py).
ITEM_TABLE_BASE = 0x876074
ITEM_STRIDE = 44
ITEM_NAME_LEN = 14
DESC_PTR_OFFSET = 0x14

# A genuine description reaches its 0xFF within this many bytes; a longer run
# means the terminator was destroyed and the slot fused into its neighbour, so
# GetStringWidth scans forever -> freeze. This matches the move-description
# pool's established overflow threshold (test_givecs_move_desc_freeze). The
# fused TM runs reach 196..693 bytes (or never terminate); the longest healthy
# description is ~146 bytes, comfortably inside the budget.
TERMINATOR_BUDGET = 160

# FR machine-item name prefixes: "CT" = Capsule Technique (TM), "CS" = Capacité
# Secrète (HM).
MACHINE_PREFIXES = ("CT", "CS")


def _deref(rom: bytes, off: int):
    if off + 4 > len(rom):
        return None
    value = struct.unpack_from("<I", rom, off)[0]
    if ROM_BASE <= value < ROM_BASE + 0x02000000:
        return value - ROM_BASE
    return None


def _machine_items(rom: bytes):
    """Yield (index, base, name, desc_offset) for every CT/CS item."""
    i = 0
    while True:
        base = ITEM_TABLE_BASE + i * ITEM_STRIDE
        if base + ITEM_STRIDE > len(rom):
            return
        i += 1
        name = TextDecoder.decode_pokemon(bytes(rom[base:base + ITEM_NAME_LEN]))
        if not name.startswith(MACHINE_PREFIXES):
            continue
        ptr = _deref(rom, base + DESC_PTR_OFFSET)
        if ptr is None:
            continue
        yield i - 1, base, name, ptr


@pytest.fixture(scope="module")
def fr_rom():
    if not FR_ROM_PATH.exists():
        pytest.skip("GenedRom-fr.gba not found in output/roms/ (run `make build-fr`)")
    return FR_ROM_PATH.read_bytes()


def test_machine_items_present(fr_rom):
    """Sanity: the CT/CS items exist (guards against a layout drift that would
    make the freeze invariant vacuously pass)."""
    machines = list(_machine_items(fr_rom))
    assert len(machines) >= 100, f"expected the full TM/HM set, found {len(machines)}"


def test_every_tm_description_is_terminated(fr_rom):
    """Each CT/CS description must terminate within budget; an over-long run is
    the missing-terminator fusion that spins GetStringWidth forever (the
    "Volcan Cendre" freeze on picking up CT94). Healthy short descriptions are
    left in place and also satisfy this; only the fused ones are relocated."""
    offenders = []
    for _, _, name, ptr in _machine_items(fr_rom):
        end = fr_rom.find(b"\xff", ptr, ptr + TERMINATOR_BUDGET + 1)
        if end < 0:
            offenders.append(f"{name} @ {ptr:#x} (no 0xFF within {TERMINATOR_BUDGET}B)")
    assert not offenders, (
        f"{len(offenders)} TM/HM description(s) are unterminated/fused -> bag "
        f"word-wrap freeze: {offenders[:8]}"
    )
