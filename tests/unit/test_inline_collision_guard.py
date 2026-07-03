"""Collision guard for the generic (DE/IT) inline override writer.

Regression for the inter-cell fusion / freeze bug audited by
``scripts/audit_translation_collisions.py``: in the packed description tables
the padding run after a terminator spills straight into the next occupied cell,
so ``PaddingDetector.detect_padding`` over-counts and a longer translation would
overrun its neighbour. ``_apply_translation_at_offset`` must never write past a
supplied ``next_offset`` — the terminator has to land strictly before it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import apply_inline_overrides_fr as mod  # noqa: E402
from src.core.padding_detector import PaddingDetector  # noqa: E402
from src.core.text_codec import TextEncoder  # noqa: E402


def _detector(data: bytes) -> PaddingDetector:
    mock = MagicMock()
    mock.rom_data = bytearray(data)
    mock.rom_size = len(data)
    return PaddingDetector(mock)


# Source layout: a 4-byte EN cell, its terminator, then a long 0xFF run that
# reaches (and passes) where the next cell starts — exactly the packed-table
# shape that makes detect_padding over-count.
SOURCE = b"AAAA" + b"\xFF" * 24
REF_ENTRY = {"encoding": "pokemon", "byte_length": 5}  # 4 content + terminator


def _apply(translation: str, next_offset):
    rom = bytearray(SOURCE)
    detector = _detector(SOURCE)
    return mod._apply_translation_at_offset(
        rom, 0, translation, dict(REF_ENTRY), detector, next_offset=next_offset
    )


def test_overrun_written_without_guard():
    # Without a boundary the detector's inflated padding lets the long string
    # write in place — this is the collision the guard exists to stop.
    applied, reason = _apply("BBBBBBBBBBBB", next_offset=None)
    assert applied and reason == "applied"


def test_overrun_rejected_with_guard():
    # Next cell 8 bytes away: 12-char translation cannot terminate before it.
    applied, reason = _apply("BBBBBBBBBBBB", next_offset=8)
    assert not applied and reason == "too_long"


def test_fitting_translation_still_applied_with_guard():
    rom = bytearray(SOURCE)
    detector = _detector(SOURCE)
    applied, reason = mod._apply_translation_at_offset(
        rom, 0, "BB", dict(REF_ENTRY), detector, next_offset=8
    )
    assert applied and reason == "applied"
    encoded = TextEncoder.encode("BB", "pokemon")
    # The terminator (last written byte) must sit strictly before next_offset.
    assert len(encoded) - 1 < 8
    assert rom[len(encoded) - 1] == 0xFF  # terminator in place


def test_terminator_never_reaches_boundary():
    # The largest translation the guard accepts still terminates before the
    # boundary (offset + encoded_len < next_offset), never on/after it.
    rom = bytearray(SOURCE)
    detector = _detector(SOURCE)
    applied, _ = mod._apply_translation_at_offset(
        rom, 0, "BBBBBB", dict(REF_ENTRY), detector, next_offset=8
    )
    assert applied
    encoded = TextEncoder.encode("BBBBBB", "pokemon")
    assert 0 + (len(encoded) - 1) < 8
