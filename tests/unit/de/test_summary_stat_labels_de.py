"""Régressions des images-mots de statistiques du résumé allemand."""

from __future__ import annotations

from pathlib import Path

import pytest

from languages.de.patches.summary_stat_labels import (
    BLOCK,
    LABELS,
    SLOT_LEN,
    apply_patches,
    fits,
    label_pixels,
    patch_sheet,
    px_get,
    read_label,
)
from languages.fr.patches.font import lz77_decompress

ROOT = Path(__file__).resolve().parents[3]
ENGLISH_ROM = ROOT / "input" / "roms" / "englishrom.gba"
BUILT_DE_ROM = ROOT / "output" / "roms" / "GenedRom-de.gba"
EXPECTED = (
    (54, "ATTACK", "ANGRIFF"),
    (66, "DEFENSE", "VERT."),
    (78, "SP.ATK", "SP.-ANG."),
    (90, "SP.DEF", "SP.-VERT."),
    (102, "SPEED", "INIT."),
    (114, "EXP.", "EP."),
)


def _sheet(path: Path) -> bytearray:
    result = lz77_decompress(bytearray(path.read_bytes()), BLOCK)
    assert result is not None
    return bytearray(result[0])


def test_labels_use_the_bounded_official_german_forms() -> None:
    assert LABELS == EXPECTED
    assert all(fits(german) for _, _, german in LABELS)
    assert all(
        token not in german for _, _, german in LABELS for token in ("HP", "PS", "PV")
    )


@pytest.mark.rom
def test_model_matches_every_english_capsule() -> None:
    if not ENGLISH_ROM.exists():
        pytest.skip("englishrom.gba absent")
    tiles = _sheet(ENGLISH_ROM)
    for y0, english, _german in LABELS:
        assert read_label(tiles, y0) == label_pixels(english)


@pytest.mark.rom
def test_patch_translates_all_labels_and_preserves_the_kp_area() -> None:
    if not ENGLISH_ROM.exists():
        pytest.skip("englishrom.gba absent")
    english = _sheet(ENGLISH_ROM)
    tiles = bytearray(english)
    before_kp = [[px_get(tiles, x, y) for x in range(32, 48)] for y in range(48, 64)]

    patched, _messages = patch_sheet(tiles)

    assert patched == len(LABELS)
    assert [
        [px_get(tiles, x, y) for x in range(32, 48)] for y in range(48, 64)
    ] == before_kp
    for y0, _english, german in LABELS:
        assert read_label(tiles, y0) == label_pixels(german)
    first = bytes(tiles)
    assert patch_sheet(tiles)[0] == 0
    assert bytes(tiles) == first


@pytest.mark.rom
def test_built_de_rom_contains_every_german_capsule() -> None:
    if not BUILT_DE_ROM.exists():
        pytest.skip("GenedRom-de.gba non construite")
    tiles = _sheet(BUILT_DE_ROM)
    for y0, _english, german in LABELS:
        assert read_label(tiles, y0) == label_pixels(german)
    result = lz77_decompress(bytearray(BUILT_DE_ROM.read_bytes()), BLOCK)
    assert result is not None and result[1] <= SLOT_LEN


@pytest.mark.rom
def test_apply_patches_is_idempotent_on_a_rom_copy(tmp_path: Path) -> None:
    if not ENGLISH_ROM.exists():
        pytest.skip("englishrom.gba absent")
    copy = tmp_path / "de.gba"
    copy.write_bytes(ENGLISH_ROM.read_bytes())
    assert apply_patches(copy) == len(LABELS)
    first = copy.read_bytes()
    assert apply_patches(copy) == 0
    assert copy.read_bytes() == first
