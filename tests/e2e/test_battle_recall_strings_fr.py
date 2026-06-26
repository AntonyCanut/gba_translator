"""E2E guard: trainer Pokémon recall messages are translated to French.

Ticket B-81 (follow-up to B-78 "Combats & Dialogues")
------------------------------------------------------
``patch_battle_string_templates_fr.py`` restores the EN cluster 0x3FB219..0x3FB264
to fix the STRINGID 0 defeat-speech template.  Side-effect: the three recall
("come back!") strings inside that cluster revert to English.

``patch_battle_recall_strings_fr.py`` (class-3, post-build) relocates French
translations of those three strings to free space and repoints the external
pointer table (0x3FE504 / 0x3FE50C / 0x3FE510) at the new locations, so
trainers calling back their Pokémon now say "reviens !" / "revenez !".

A green result proves:
- Each recall pointer no longer targets the old EN cluster body.
- The pointed-to bytes decode to the expected French text.
- The STRINGID 0 cluster is unaffected (checked by test_battle_defeat_speech_template_fr.py).

Run standalone:  pytest tests/e2e/test_battle_recall_strings_fr.py -v
"""

from __future__ import annotations

import struct

import pytest

GBA_BASE = 0x08000000

# External pointer table entries for the three recall strings.
# Format: (ptr_table_offset, old_EN_body_offset)
RECALL_PTRS = [
    (0x3FE504, 0x3FB21F),  # single-mon recall {FD06}
    (0x3FE50C, 0x3FB235),  # single-mon recall {FD08}
    (0x3FE510, 0x3FB248),  # double-mon recall  {FD06} and {FD08}
]

# Expected French byte sequences (raw CFRU-encoded, including FF terminator).
# Decoded text:
#   {FD1D}: {FD06}, reviens !
#   {FD1D}: {FD08}, reviens !
#   {FD1D}: {FD06} et\n{FD08}, revenez !
FR_RECALL_BYTES = [
    bytes.fromhex("fd1df000fd06b800e6d9eaddd9e2e700abff"),
    bytes.fromhex("fd1df000fd08b800e6d9eaddd9e2e700abff"),
    bytes.fromhex("fd1df000fd0600d9e8fefd08b800e6d9ead9e2d9ee00abff"),
]

# The EN cluster range restored by patch_battle_string_templates_fr.py.
EN_CLUSTER_START = 0x3FB219
EN_CLUSTER_END = 0x3FB265  # exclusive


@pytest.fixture
def fr_bytes(fr_rom_path):
    return fr_rom_path.read_bytes()


@pytest.mark.parametrize("ptr_off,old_body,fr_seq,label", [
    (0x3FE504, 0x3FB21F, FR_RECALL_BYTES[0], "single-mon-1"),
    (0x3FE50C, 0x3FB235, FR_RECALL_BYTES[1], "single-mon-2"),
    (0x3FE510, 0x3FB248, FR_RECALL_BYTES[2], "double-mon"),
])
def test_recall_pointer_redirected(fr_bytes, ptr_off, old_body, fr_seq, label):
    """Recall pointer must no longer target the English cluster body."""
    ptr = struct.unpack_from("<I", fr_bytes, ptr_off)[0]
    new_body = ptr - GBA_BASE
    assert ptr != GBA_BASE + old_body, (
        f"[{label}] pointer @0x{ptr_off:06X} still points at the EN cluster body "
        f"0x{old_body:06X} — patch_battle_recall_strings_fr may not have run"
    )
    assert 0 < new_body < len(fr_bytes) - len(fr_seq), (
        f"[{label}] repointed address 0x{ptr:08X} is out of ROM bounds"
    )


@pytest.mark.parametrize("ptr_off,fr_seq,label", [
    (0x3FE504, FR_RECALL_BYTES[0], "single-mon-1"),
    (0x3FE50C, FR_RECALL_BYTES[1], "single-mon-2"),
    (0x3FE510, FR_RECALL_BYTES[2], "double-mon"),
])
def test_recall_string_is_french(fr_bytes, ptr_off, fr_seq, label):
    """The bytes at the recall pointer target must match the French encoding."""
    ptr = struct.unpack_from("<I", fr_bytes, ptr_off)[0]
    body_off = ptr - GBA_BASE
    assert 0 < body_off < len(fr_bytes) - len(fr_seq), (
        f"[{label}] pointer 0x{ptr:08X} out of bounds"
    )
    actual = bytes(fr_bytes[body_off: body_off + len(fr_seq)])
    assert actual == fr_seq, (
        f"[{label}] recall string at 0x{body_off:06X}: expected {fr_seq.hex()} "
        f"('reviens/revenez'), got {actual.hex()}"
    )


@pytest.mark.parametrize("ptr_off,label", [
    (0x3FE504, "single-mon-1"),
    (0x3FE50C, "single-mon-2"),
    (0x3FE510, "double-mon"),
])
def test_recall_not_in_en_cluster(fr_bytes, ptr_off, label):
    """The recall pointer must target a location OUTSIDE the EN cluster bytes."""
    ptr = struct.unpack_from("<I", fr_bytes, ptr_off)[0]
    body_off = ptr - GBA_BASE
    assert not (EN_CLUSTER_START <= body_off < EN_CLUSTER_END), (
        f"[{label}] recall pointer 0x{ptr:08X} still points inside the EN cluster "
        f"0x{EN_CLUSTER_START:06X}..0x{EN_CLUSTER_END-1:06X}"
    )
