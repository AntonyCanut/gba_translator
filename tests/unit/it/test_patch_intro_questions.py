"""Tests for languages/it/patches/intro_questions.py — the Italian intro-question patch.

Regression guard for the CI failure "Italian ROM build/verify failed — FR was
still released, but IT was skipped." (ticket: Build KO it).

Root cause: ``patch()`` searched for pointers aimed at the *original* English
offset of the long puzzle question (0x1F0F9FA).  The build pipeline relocates
that overflowing string first and repoints the live pointer, so by the time the
patch ran no referrers to the original offset remained — the patch skipped, and
the strict ``verify()`` then failed because the live bytes did not match the
canonical Italian text, aborting the whole Italian build.

The fix repoints via the live pointer cell (plus any original-offset / relocated
referrers), so the canonical full text is anchored wherever the pipeline left
the pointer.  These tests synthesise the relocated-pipeline scenario on a small
ROM and assert that ``patch()`` + ``verify()`` succeed.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import patch_intro_questions_it as mod  # noqa: E402

# ── Small synthetic-ROM layout (all offsets well under the 32 KB ROM size) ──────
ROM_SIZE = 0x8000
PC_DIRECT1 = 0x100  # pointer cell for the first direct-write target
PC_DIRECT2 = 0x104
PC_RELOC = 0x108  # pointer cell for the relocate-and-repoint target
SLOT_DIRECT1 = 0x200
SLOT_DIRECT2 = 0x280
ORIG_RELOC = 0x300  # "original English" offset of the long question
PIPELINE_RELOC = 0x500  # where the pipeline relocated the long question
FREE_START = 0x1000  # 0xFF free run the allocator can carve from
FREE_LEN = 0x1000

TXT_DIRECT1 = "Il tuo nome è {player}?"
TXT_DIRECT2 = "Ti dimentichi di salvare spesso?"
TXT_RELOC = "Ti piacciono gli enigmi impegnativi e i massi che rotolano?"


def _write_ptr(rom: bytearray, cell: int, offset: int) -> None:
    struct.pack_into("<I", rom, cell, mod.GBA_BASE + offset)


def _base_rom() -> bytearray:
    """A ROM full of 0x00 data with one large 0xFF free run."""
    rom = bytearray(ROM_SIZE)
    rom[FREE_START : FREE_START + FREE_LEN] = b"\xff" * FREE_LEN
    # English/garbled placeholders so the direct-write targets need patching.
    rom[SLOT_DIRECT1 : SLOT_DIRECT1 + 16] = b"What is your nam"
    rom[SLOT_DIRECT2 : SLOT_DIRECT2 + 16] = b"Do you forget?!!"
    _write_ptr(rom, PC_DIRECT1, SLOT_DIRECT1)
    _write_ptr(rom, PC_DIRECT2, SLOT_DIRECT2)
    return rom


@pytest.mark.usefixtures("small_offsets")
class TestRelocatedScenario:
    """Synthetic-ROM tests that exercise patch()/verify() at small offsets."""

    @pytest.fixture
    def small_offsets(self, monkeypatch):
        """Point the patch at small synthetic offsets so the ROM stays tiny."""
        monkeypatch.setattr(
            mod,
            "POINTER_CELLS",
            {SLOT_DIRECT1: PC_DIRECT1, SLOT_DIRECT2: PC_DIRECT2, ORIG_RELOC: PC_RELOC},
        )
        monkeypatch.setattr(
            mod,
            "IT_TEXTS",
            {SLOT_DIRECT1: TXT_DIRECT1, SLOT_DIRECT2: TXT_DIRECT2, ORIG_RELOC: TXT_RELOC},
        )
        monkeypatch.setattr(mod, "DIRECT_WRITE_OFFSETS", (SLOT_DIRECT1, SLOT_DIRECT2))
        monkeypatch.setattr(mod, "RELOCATE_OFFSET", ORIG_RELOC)

    def test_pipeline_relocated_then_patch_verifies(self):
        """The exact CI failure: the pipeline already relocated the long question
        and its bytes differ from the canonical text; no referrer to the original
        offset remains.  ``patch()`` must repoint via the live cell and pass."""
        rom = _base_rom()
        # Pipeline relocated the long question to PIPELINE_RELOC with *different*
        # (re-wrapped / truncated) bytes, and repointed the live pointer there.
        rom[PIPELINE_RELOC : PIPELINE_RELOC + 8] = b"Ti piacc"  # not the full text
        _write_ptr(rom, PC_RELOC, PIPELINE_RELOC)

        # Pre-condition: original offset has no referrers (this is what broke).
        assert mod._find_referrers(rom, ORIG_RELOC) == []

        stats = mod.patch(rom)
        bad = mod.verify(rom)

        assert bad == [], f"verify() should pass after the fix, got: {bad}"
        assert stats["relocated"] == 1
        assert stats["failed"] == 0
        assert stats["direct_written"] == 2

        # The live pointer now reaches a copy of the canonical full text.
        target = mod._read_ptr(rom, PC_RELOC)
        assert target is not None
        assert FREE_START <= target < FREE_START + FREE_LEN
        encoded = mod._encode(TXT_RELOC)
        assert rom[target : target + len(encoded)] == encoded

    def test_idempotent_when_already_translated(self):
        """If the live pointer already reaches the canonical full text, the patch
        is a no-op and verification still passes."""
        rom = _base_rom()
        encoded = mod._encode(TXT_RELOC)
        rom[PIPELINE_RELOC : PIPELINE_RELOC + len(encoded)] = encoded
        _write_ptr(rom, PC_RELOC, PIPELINE_RELOC)
        # Direct-write slots already correct too.
        d1, d2 = mod._encode(TXT_DIRECT1), mod._encode(TXT_DIRECT2)
        rom[SLOT_DIRECT1 : SLOT_DIRECT1 + len(d1)] = d1
        rom[SLOT_DIRECT2 : SLOT_DIRECT2 + len(d2)] = d2

        stats = mod.patch(rom)
        bad = mod.verify(rom)

        assert bad == []
        assert stats["relocated"] == 0
        assert stats["direct_written"] == 0
        assert stats["failed"] == 0
        # Pointer untouched — still the pipeline's copy.
        assert mod._read_ptr(rom, PC_RELOC) == PIPELINE_RELOC

    def test_pointer_still_on_original_offset_gets_relocated(self):
        """Defensive case: the pipeline did not relocate (pointer still on the
        original offset, bytes English).  The patch must relocate and repoint."""
        rom = _base_rom()
        rom[ORIG_RELOC : ORIG_RELOC + 16] = b"Do you enjoy puz"
        _write_ptr(rom, PC_RELOC, ORIG_RELOC)

        stats = mod.patch(rom)
        bad = mod.verify(rom)

        assert bad == []
        assert stats["relocated"] == 1
        encoded = mod._encode(TXT_RELOC)
        target = mod._read_ptr(rom, PC_RELOC)
        assert FREE_START <= target < FREE_START + FREE_LEN
        assert rom[target : target + len(encoded)] == encoded

    def test_main_returns_zero_on_relocated_rom(self, tmp_path):
        """End-to-end through main(): write the patched ROM and verify → rc 0."""
        rom = _base_rom()
        rom[PIPELINE_RELOC : PIPELINE_RELOC + 8] = b"Ti piacc"
        _write_ptr(rom, PC_RELOC, PIPELINE_RELOC)
        rom_file = tmp_path / "GenedRom-it.gba"
        rom_file.write_bytes(rom)

        assert mod.main(["--rom", str(rom_file)]) == 0


# ── Drift guard: hardcoded IT texts must match the live combined_it.txt ─────────
COMBINED_IT = ROOT / "languages/it/combined_it.txt"


def _combined_entries(offsets) -> dict[int, str]:
    wanted = set(offsets)
    entries: dict[int, str] = {}
    for raw in COMBINED_IT.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")
        if not line.lower().startswith("0x") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        try:
            off = int(key, 16)
        except ValueError:
            continue
        if off in wanted:
            # ``last entry wins`` (combined_it.txt has duplicate offsets).
            entries[off] = value[1:] if value.startswith(" ") else value
    return entries


@pytest.mark.skipif(not COMBINED_IT.exists(), reason="combined_it.txt not present")
class TestCombinedDrift:
    """The patch's hardcoded Italian text is the canonical source of truth and
    must stay in sync with combined_it.txt — the original CI break came from a
    stale combined_it.txt that disagreed with the patch."""

    def test_offsets_present_in_combined(self):
        entries = _combined_entries(mod.IT_TEXTS)
        for off in mod.IT_TEXTS:
            assert off in entries, f"0x{off:07X} missing from combined_it.txt"

    def test_texts_match_combined(self):
        entries = _combined_entries(mod.IT_TEXTS)
        for off, text in mod.IT_TEXTS.items():
            assert entries[off] == text, (
                f"0x{off:07X}: patch text and combined_it.txt disagree\n"
                f"  patch:    {text!r}\n  combined: {entries[off]!r}"
            )
