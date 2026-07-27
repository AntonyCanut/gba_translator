"""Tests du patch dédié aux titres de mission français."""

from __future__ import annotations

import csv
from pathlib import Path

from languages.fr.patches import mission_descriptions, mission_titles
from scripts import apply_combined_fr
from scripts import apply_inline_overrides_fr
from src.core.text_codec import TextDecoder, TextEncoder
from src.core.text_converter import CSVToJSONConverter


TITLE_OFFSET = 0x1FA4E10
TITLE = "Voleur de vivres"
MAKEFILE = Path(__file__).resolve().parents[1] / "Makefile"


def test_target_is_the_live_food_thief_title() -> None:
    assert mission_titles.TARGETS == (TITLE_OFFSET,)
    assert set(mission_titles.TARGETS) <= (
        apply_inline_overrides_fr.DEDICATED_PATCH_OFFSETS
    )
    assert mission_titles.RELOCATED_NEIGHBOR_OFFSET in mission_descriptions.TARGETS
    assert TITLE_OFFSET + len(TextEncoder.encode(TITLE, "pokemon")) > (
        mission_titles.RELOCATED_NEIGHBOR_OFFSET
    )


def test_title_patch_runs_before_neighbor_relocation() -> None:
    recipe = MAKEFILE.read_text(encoding="utf-8")
    title_call = "@$(PYTHON) $(PATCH_MISSION_TITLES_FR_SCRIPT)"
    description_call = "@$(PYTHON) $(PATCH_MISSION_DESC_FR_SCRIPT)"
    assert recipe.index(title_call) < recipe.index(description_call)


def test_release_csv_excludes_and_clears_dedicated_title() -> None:
    combined = {TITLE_OFFSET: TITLE, 0x10: "Bonjour"}
    rows = [
        {"offset": f"0x{TITLE_OFFSET:08X}", "translation": "ancienne valeur"},
        {"offset": "0x00000010", "translation": ""},
    ]

    excluded = apply_combined_fr._exclude_dedicated_offsets(combined, rows)

    assert excluded == 1
    assert TITLE_OFFSET not in combined
    assert rows[0]["translation"] == ""
    assert combined == {0x10: "Bonjour"}


def test_fr_exclusions_do_not_apply_to_other_languages() -> None:
    assert apply_combined_fr._dedicated_offsets_for_combined(
        Path("languages/fr/combined_fr.txt")
    )
    assert not apply_combined_fr._dedicated_offsets_for_combined(
        Path("languages/it/combined_it.txt")
    )
    assert apply_inline_overrides_fr._dedicated_offsets_for_combined(
        Path("languages/fr/combined_fr.txt")
    )
    assert not apply_inline_overrides_fr._dedicated_offsets_for_combined(
        Path("languages/it/combined_it.txt")
    )


def test_release_csv_to_json_keeps_dedicated_title_out(tmp_path) -> None:
    fields = [
        "offset", "original_text", "spanish_text", "original_length",
        "padding_available", "real_max_length", "encoding", "category",
        "translation", "notes",
    ]
    rows = [
        {
            "offset": f"0x{TITLE_OFFSET:08X}",
            "original_text": "The Food Thief",
            "spanish_text": "Comida Robada",
            "original_length": "15",
            "padding_available": "0",
            "real_max_length": "15",
            "encoding": "pokemon",
            "category": "location",
            "translation": TITLE,
            "notes": "",
        },
        {
            "offset": "0x00000010",
            "original_text": "Hello",
            "spanish_text": "Hola",
            "original_length": "6",
            "padding_available": "8",
            "real_max_length": "14",
            "encoding": "pokemon",
            "category": "dialogue",
            "translation": "Bonjour",
            "notes": "",
        },
    ]
    combined = {TITLE_OFFSET: TITLE, 0x10: "Bonjour"}
    apply_combined_fr._exclude_dedicated_offsets(combined, rows)
    csv_path = tmp_path / "release.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    converter = CSVToJSONConverter()
    converter.allow_too_long = True
    converter.load_from_csv(csv_path)

    offsets = {entry.offset for entry in converter.entries}
    assert TITLE_OFFSET not in offsets
    assert 0x10 in offsets


def test_apply_writes_in_place_without_touching_other_bytes(monkeypatch) -> None:
    offset = 0x100
    monkeypatch.setattr(mission_titles, "TARGETS", (offset,))
    rom = bytearray(b"\xaa" * 0x200)
    encoded = TextEncoder.encode(TITLE, "pokemon")
    before = bytes(rom[:offset])
    after = bytes(rom[offset + len(encoded) :])

    stats = mission_titles.apply(rom, {offset: TITLE})

    assert stats == {"targets": 1, "failed": 0, "skipped": 0}
    assert TextDecoder.decode_pokemon(rom[offset : offset + len(encoded)]) == TITLE
    assert bytes(rom[:offset]) == before
    assert bytes(rom[offset + len(encoded) :]) == after


def test_apply_is_idempotent(monkeypatch) -> None:
    offset = 0x100
    monkeypatch.setattr(mission_titles, "TARGETS", (offset,))
    rom = bytearray(b"\xaa" * 0x200)
    mission_titles.apply(rom, {offset: TITLE})
    first = bytes(rom)

    stats = mission_titles.apply(rom, {offset: TITLE})

    assert stats == {"targets": 0, "failed": 0, "skipped": 1}
    assert bytes(rom) == first
