"""Safety checks for the manual sprite insertion command."""

from pathlib import Path

import pytest

from scripts.insert_sprite import ROOT_DIR, _validate_writable_rom, _write_rom_safely


def test_validate_writable_rom_rejects_source_rom() -> None:
    source_rom = ROOT_DIR / "input" / "roms" / "englishrom.gba"

    with pytest.raises(ValueError, match=r"input/roms"):
        _validate_writable_rom(source_rom)


def test_write_rom_safely_preserves_previous_rom_as_backup(tmp_path: Path) -> None:
    rom_path = tmp_path / "edited.gba"
    rom_path.write_bytes(b"before")

    _write_rom_safely(rom_path, b"after")

    assert rom_path.read_bytes() == b"after"
    assert Path(f"{rom_path}.bak").read_bytes() == b"before"
