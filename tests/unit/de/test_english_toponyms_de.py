"""German-build place names stay byte-faithful to the English ROM canon."""

from __future__ import annotations

from pathlib import Path

from languages.de.toponyms import (
    DEFAULT_CATALOG,
    audit_combined,
    control_signature,
    load_catalog,
    restore_toponyms,
)
from src.core.text_codec import TextDecoder

ROOT = Path(__file__).resolve().parents[3]


def test_catalog_canonical_names_are_decoded_from_the_english_rom() -> None:
    # Arrange
    rom = (ROOT / "input/roms/englishrom.gba").read_bytes()
    records = load_catalog(DEFAULT_CATALOG)

    # Act / Assert
    for record in records:
        for offset in record.anchors:
            end = rom.find(b"\xff", offset)
            assert end != -1, f"0x{offset:08X}: missing terminator"
            decoded = TextDecoder.decode_pokemon(rom[offset : end + 1]).strip()
            assert decoded == record.canonical, (
                f"0x{offset:08X}: catalog says {record.canonical!r}, ROM has {decoded!r}"
            )


def test_catalog_contains_distinct_kbt_and_ses_expressways() -> None:
    # Arrange / Act
    records = {record.canonical: record for record in load_catalog(DEFAULT_CATALOG)}

    # Assert
    assert "KBT Expressway" in records
    assert "SES Expressway" in records
    assert records["KBT Expressway"].aliases != records["SES Expressway"].aliases


def test_restore_toponyms_is_anchored_by_the_matching_english_entry() -> None:
    # Arrange
    records = load_catalog(DEFAULT_CATALOG)

    # Act
    restored = restore_toponyms(
        "Go through Cinder Volcano, then Blizzard City.",
        "Gehe durch den Aschenvulkan, dann nach Cimistral.",
        records,
    )
    common_word = restore_toponyms(
        "The crater is deep.",
        "Der Krater ist tief.",
        records,
    )

    # Assert
    assert restored == "Gehe durch den Cinder Volcano, dann nach Blizzard City."
    assert common_word == "Der Krater ist tief."


def test_restore_toponyms_preserves_panel_controls_and_arrows() -> None:
    # Arrange
    records = load_catalog(DEFAULT_CATALOG)
    english = "Route 3\\p<0x79> Flower Paradise\\n<0x7A> Dresco Town"
    german = "Route 3\\p<0x79> Paradis Floral\\n<0x7A> Dresco"

    # Act
    restored = restore_toponyms(english, german, records)

    # Assert
    assert restored == english
    assert control_signature(restored) == control_signature(english)


def test_restore_toponym_immediately_after_literal_line_control() -> None:
    # Arrange
    records = load_catalog(DEFAULT_CATALOG)

    # Act
    restored = restore_toponyms(
        "Route 13\\p<0x79> Cinder Volcano\\nGrim Woods",
        "Route 13\\p<0x79> Cinder Volcano\\nBoissombre",
        records,
    )

    # Assert
    assert restored.endswith("\\nGrim Woods")


def test_restore_toponyms_does_not_rewrite_one_canonical_name_inside_another() -> None:
    # Arrange
    records = load_catalog(DEFAULT_CATALOG)

    # Act
    restored = restore_toponyms(
        "Magnolia Fields\\p<0x7B> Magnolia Town",
        "Magnolia-Felder\\p<0x7B> Magnolia",
        records,
    )

    # Assert
    assert restored == "Magnolia Fields\\p<0x7B> Magnolia Town"


def test_live_combined_de_contains_only_english_toponyms_at_english_offsets() -> None:
    # Arrange
    records = load_catalog(DEFAULT_CATALOG)

    # Act
    violations = audit_combined(
        ROOT / "languages/en/combined_en.txt",
        ROOT / "languages/de/combined_de.txt",
        records,
    )

    # Assert
    assert violations == []
