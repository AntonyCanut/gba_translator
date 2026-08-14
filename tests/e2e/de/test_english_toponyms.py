"""E2E: English place names are live and safe in the built German ROM."""

from __future__ import annotations

from pathlib import Path

import pytest

from languages.de.toponyms import load_combined
from scripts.audit_english_toponyms_de import audit_rom

ROOT = Path(__file__).resolve().parents[3]
EN_ROM = ROOT / "input/roms/englishrom.gba"
DE_ROM = ROOT / "output/roms/GenedRom-de.gba"

pytestmark = pytest.mark.rom


def test_live_de_surfaces_use_terminated_english_toponyms_and_safe_arrows() -> None:
    if not DE_ROM.exists():
        pytest.skip("GenedRom-de.gba not built — run: make build-de")

    violations = audit_rom(
        EN_ROM.read_bytes(),
        DE_ROM.read_bytes(),
        load_combined(ROOT / "languages/en/combined_en.txt"),
        load_combined(ROOT / "languages/de/combined_de.txt"),
    )

    assert violations == []

