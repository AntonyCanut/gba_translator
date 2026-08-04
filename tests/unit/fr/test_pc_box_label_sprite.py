"""Régressions de l'asset éditable des libellés de boîtes PC (#163)."""

from __future__ import annotations

import shutil
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest

from languages.fr.patches.font import lz77_compress, lz77_decompress
from languages.fr.sprites import SPRITES
from src.graphics.sprite_image import read_indexed_image
from src.graphics.sprite_rom import extract_block, grid_to_tiles

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROM = ROOT / "input" / "roms" / "englishrom.gba"
ASSET = ROOT / "languages" / "fr" / "sprites" / "pc_box_labels.png"
BUILT_ROM = ROOT / "output" / "roms" / "GenedRom-fr.gba"
CONTRIBUTED_GRID_SHA256 = (
    "3e8856cdfc9e605b732905e923ec42f950462a6156bef0a971db10b3dea28c9d"
)


def test_pc_box_labels_registry_targets_the_live_tilesheet() -> None:
    """Une mauvaise adresse, palette ou grille rendrait le PNG non éditable."""
    sprite = SPRITES["pc_box_labels"]

    assert sprite.blocks == (0x00E9C438,)
    assert sprite.block_pointers == ((0x0008F034,),)
    assert sprite.palette == 0x003CE5DC
    assert (sprite.tiles_wide, sprite.tiles_tall) == (16, 9)


def test_pc_box_labels_asset_is_a_128_by_72_indexed_image() -> None:
    """Un PNG true-colour ou recadré ne pourrait pas être réinjecté tel quel."""
    width, height, _ = read_indexed_image(ASSET)

    assert (width, height) == (128, 72)


def test_pc_box_labels_asset_matches_the_contributed_drawing() -> None:
    """Une ré-extraction anglaise ne doit pas écraser le dessin français."""
    _, _, grid = read_indexed_image(ASSET)

    digest = sha256(bytes(pixel for row in grid for pixel in row)).hexdigest()

    assert digest == CONTRIBUTED_GRID_SHA256


@pytest.mark.rom
def test_pc_box_labels_asset_differs_from_the_english_tilesheet() -> None:
    """Le dessin versionné doit bien remplacer les libellés anglais."""
    sprite = SPRITES["pc_box_labels"]
    _, _, asset_grid = read_indexed_image(ASSET)
    source_grid, _, _ = extract_block(
        SOURCE_ROM.read_bytes(),
        sprite.blocks[0],
        sprite.tiles_wide,
        sprite.tiles_tall,
    )

    assert asset_grid != source_grid


def test_insert_sprite_cli_relocates_pc_labels_through_declared_pointer(
    tmp_path: Path,
) -> None:
    """Le CLI doit transmettre au cœur les pointeurs déclarés du registre."""
    # Arrange
    sprite = SPRITES["pc_box_labels"]
    _, _, asset_grid = read_indexed_image(ASSET)
    expected = grid_to_tiles(asset_grid, sprite.tiles_wide, sprite.tiles_tall)
    compact = lz77_compress(b"\x00" * len(expected))
    rom_size = sprite.blocks[0] + len(compact) + 0x2000
    rom = bytearray(b"\xAA" * rom_size)
    rom[sprite.blocks[0]:sprite.blocks[0] + len(compact)] = compact
    pointer_offset = sprite.block_pointers[0][0]
    rom[pointer_offset:pointer_offset + 4] = (
        0x08000000 + sprite.blocks[0]
    ).to_bytes(4, "little")
    rom[-0x1000:] = b"\xFF" * 0x1000
    rom_path = tmp_path / "synthetic.gba"
    rom_path.write_bytes(rom)
    before = bytes(rom)

    # Act
    subprocess.run(
        [
            "python3",
            "scripts/insert_sprite.py",
            "--rom",
            str(rom_path),
            "--lang",
            "fr",
            "--sprite",
            "pc_box_labels",
            "--image",
            str(ASSET),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    # Assert
    patched = rom_path.read_bytes()
    relocated_offset = (
        int.from_bytes(patched[pointer_offset:pointer_offset + 4], "little")
        - 0x08000000
    )
    result = lz77_decompress(patched, relocated_offset)
    assert relocated_offset != sprite.blocks[0]
    assert result is not None
    assert result[0] == expected
    assert Path(f"{rom_path}.bak").read_bytes() == before


@pytest.mark.rom
def test_insert_sprite_cli_round_trips_pc_labels_and_creates_backup(
    tmp_path: Path,
) -> None:
    """Le CLI doit injecter les 4 608 octets FR et préserver l'original."""
    # Arrange
    sprite = SPRITES["pc_box_labels"]
    source = SOURCE_ROM.read_bytes()
    source_result = lz77_decompress(source, sprite.blocks[0])
    assert source_result is not None
    source_payload, _ = source_result
    _, _, asset_grid = read_indexed_image(ASSET)
    expected_payload = grid_to_tiles(
        asset_grid,
        sprite.tiles_wide,
        sprite.tiles_tall,
    )
    rom_path = tmp_path / "englishrom-copy.gba"
    shutil.copy2(SOURCE_ROM, rom_path)

    # Act
    subprocess.run(
        [
            "python3",
            "scripts/insert_sprite.py",
            "--rom",
            str(rom_path),
            "--lang",
            "fr",
            "--sprite",
            "pc_box_labels",
            "--image",
            str(ASSET),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    # Assert
    patched = rom_path.read_bytes()
    live_offset = (
        int.from_bytes(
            patched[
                sprite.block_pointers[0][0]:sprite.block_pointers[0][0] + 4
            ],
            "little",
        )
        - 0x08000000
    )
    patched_result = lz77_decompress(patched, live_offset)
    assert len(source_payload) == 4_608
    assert patched_result is not None
    assert patched_result[0] == expected_payload
    assert patched_result[0] != source_payload
    assert Path(f"{rom_path}.bak").read_bytes() == source


def test_french_build_inserts_translated_pc_box_labels() -> None:
    """La recette FR doit consommer la planche retouchée."""
    result = subprocess.run(
        ["make", "-n", "build-fr"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    expected_command = (
        "python3 scripts/insert_sprite.py --rom output/roms/GenedRom-fr.gba "
        "--lang fr --sprite pc_box_labels --image "
        "languages/fr/sprites/pc_box_labels.png"
    )
    assert expected_command in result.stdout


@pytest.mark.rom
def test_built_french_rom_contains_contributed_pc_box_labels() -> None:
    """Le bloc pointé livré doit correspondre pixel par pixel au PNG."""
    sprite = SPRITES["pc_box_labels"]
    rom = BUILT_ROM.read_bytes()
    live_offset = (
        int.from_bytes(
            rom[
                sprite.block_pointers[0][0]:sprite.block_pointers[0][0] + 4
            ],
            "little",
        )
        - 0x08000000
    )
    expected = read_indexed_image(ASSET)[2]

    actual, _, _ = extract_block(
        rom,
        live_offset,
        sprite.tiles_wide,
        sprite.tiles_tall,
    )

    assert actual == expected
