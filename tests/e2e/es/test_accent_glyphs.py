"""E2E: Spanish-specific glyphs (ñ, ¿, ¡, accented vowels) decode cleanly.

``languages/es/combined_es.txt`` is a direct-offset extraction of
``spanishrom.gba`` (see its ``lang.yaml``). This guards that the CFRU charmap
still round-trips Spanish-specific characters between the reference text file
and the live ROM bytes — if a charmap regression ever remapped ``ñ``/``¿``/``¡``
to the wrong codepoint, entries would silently lose those characters on
decode without changing length or crashing anything.
"""

from src.core.text_codec import TextDecoder

SPANISH_MARKERS = "ñÑ¡¿"

# Baseline measured against the current combined_es.txt (991 entries contain
# at least one of ñ/¡/¿). Guards against the reference extraction silently
# losing most of its Spanish-specific content in a future regeneration.
MIN_ACCENTED_ENTRIES = 500


def _decode_at(rom_data: bytes, offset: int, limit: int = 500) -> str:
    chunk = rom_data[offset:offset + limit]
    end = chunk.find(b"\xFF")
    raw = chunk if end == -1 else chunk[:end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


class TestSpanishAccentedGlyphs:
    def test_reference_extraction_has_spanish_markers(self, es_combined_entries):
        marked = [
            text for text in es_combined_entries.values()
            if any(c in text for c in SPANISH_MARKERS)
        ]
        assert len(marked) >= MIN_ACCENTED_ENTRIES, (
            f"Only {len(marked)} entries contain ñ/¡/¿ — expected at least "
            f"{MIN_ACCENTED_ENTRIES}. combined_es.txt may have lost Spanish content."
        )

    def test_markers_survive_rom_round_trip(self, es_combined_entries, es_rom_path):
        """Every ñ/¡/¿ character present in the reference text must still be
        present after decoding the corresponding bytes straight from the ROM."""
        rom_data = es_rom_path.read_bytes()
        marked = {
            off: text for off, text in es_combined_entries.items()
            if any(c in text for c in SPANISH_MARKERS)
        }
        assert marked, "no ñ/¡/¿ entries found in combined_es.txt to check"

        lost = []
        for off, text in marked.items():
            decoded = _decode_at(rom_data, off)
            expected_chars = {c for c in SPANISH_MARKERS if c in text}
            missing_chars = {c for c in expected_chars if c not in decoded}
            if missing_chars:
                lost.append((off, missing_chars))

        assert not lost, (
            f"{len(lost)} entries lost Spanish marker characters on ROM decode "
            f"(offset -> missing chars): {lost[:10]}"
        )
