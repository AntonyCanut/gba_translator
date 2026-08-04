"""Unit tests for the no-pointer ROM-based fallback in prepare_fr_json.py.

Entries in combined_fr.txt that are absent from the English extraction JSON
were previously skipped silently.  The fix reads the English ROM directly at
those offsets: if the French text fits in the original byte slot the entry is
included with ``notes: 'no-pointer: in-place only'``.

Tests use synthetic (in-memory) data so no actual ROM is required.
"""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Reuse the helpers from the module under test.
from scripts.prepare_fr_json import _encoded_length, _load_combined, _normalize_text


def _build_fake_rom(strings: dict[int, bytes], rom_size: int = 0x200) -> bytes:
    """Build a byte buffer with CFRU strings placed at the given offsets."""
    buf = bytearray(b"\xFF" * rom_size)
    for offset, data in strings.items():
        buf[offset : offset + len(data)] = data
    return bytes(buf)


def _en_extraction(entries: list[dict]) -> dict:
    return {"texts": entries}


def _run_prepare(
    combined_lines: list[str],
    en_json: dict,
    rom_bytes: bytes,
) -> dict:
    """Run main() with synthetic inputs; return the output JSON."""
    import importlib
    import io
    import contextlib

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        combined_path = td / "combined_fr.txt"
        combined_path.write_text("\n".join(combined_lines), encoding="utf-8")

        en_path = td / "en.json"
        en_path.write_text(json.dumps(en_json), encoding="utf-8")

        rom_path = td / "rom.gba"
        rom_path.write_bytes(rom_bytes)

        out_path = td / "out.json"

        # Patch sys.argv and run main
        old_argv = sys.argv
        sys.argv = [
            "prepare_fr_json.py",
            "--combined", str(combined_path),
            "--english", str(en_path),
            "--english-rom", str(rom_path),
            "--output", str(out_path),
        ]
        try:
            # Suppress stdout noise
            with contextlib.redirect_stdout(io.StringIO()):
                import scripts.prepare_fr_json as module
                import importlib
                importlib.reload(module)
                module.main()
        finally:
            sys.argv = old_argv

        return json.loads(out_path.read_text(encoding="utf-8"))


class TestNoPointerFallback(unittest.TestCase):
    """The ROM-based fallback must recover in-place entries missing from the extraction."""

    # CFRU-encoded "Oui" + 0xFF terminator.
    # Verified: TextEncoder.encode("Oui", "pokemon") == b"\xC9\xE9\xDD\xFF" (3 content bytes).
    # 3 content bytes = en_len 3, which meets the minimum-length guard (en_len >= 3).
    EN_BYTES = b"\xC9\xE9\xDD\xFF"      # "Oui" + 0xFF  (3 content bytes)
    EN_OFFSET = 0x50

    def setUp(self) -> None:
        # ROM: only the EN string; everything else 0xFF (acts as empty/terminator).
        self.rom = _build_fake_rom({self.EN_OFFSET: self.EN_BYTES})
        # EN extraction deliberately omits EN_OFFSET.
        self.en_json = _en_extraction([
            {"offset": 0x10, "byte_length": 5, "length": 5,
             "encoding": "pokemon", "decoded_text": "Hello", "text": "Hello"},
        ])

    def _make_combined(self, fr_text: str) -> list[str]:
        return [
            f"0x{self.EN_OFFSET:08X}: {fr_text}",
            "0x00000010: Bonjour",   # normal EN-extraction entry for comparison
        ]

    def test_fits_inplace_is_included(self) -> None:
        """FR that fits in the EN slot must appear with no-pointer notes."""
        result = _run_prepare(
            self._make_combined("Oui"),  # same 3-byte length as EN "Oui"
            self.en_json,
            self.rom,
        )
        offsets = {t["offset"]: t for t in result["translations"]}
        self.assertIn(self.EN_OFFSET, offsets,
                      "no-pointer entry missing from output")
        entry = offsets[self.EN_OFFSET]
        self.assertEqual(entry["notes"], "no-pointer: in-place only")
        self.assertFalse(entry["too_long"])
        self.assertLessEqual(entry["length"], entry["original_length"])

    def test_too_long_is_excluded(self) -> None:
        """FR that exceeds the EN slot must be excluded from the output."""
        # "Bonjour" encodes to 7 bytes, exceeds the 3-byte EN slot.
        result = _run_prepare(
            self._make_combined("Bonjour"),
            self.en_json,
            self.rom,
        )
        offsets = {t["offset"] for t in result["translations"]}
        self.assertNotIn(self.EN_OFFSET, offsets,
                         "too-long no-pointer entry must not appear in output")

    def test_normal_en_entry_still_included(self) -> None:
        """Entries present in EN extraction must still be produced."""
        result = _run_prepare(
            self._make_combined("OK"),
            self.en_json,
            self.rom,
        )
        offsets = {t["offset"] for t in result["translations"]}
        self.assertIn(0x10, offsets,
                      "normal EN extraction entry must still be present")

    def test_no_rom_skips_gracefully(self) -> None:
        """When the ROM file does not exist the script completes without crashing."""
        import contextlib, io, tempfile, sys
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            combined_path = td / "combined_fr.txt"
            combined_path.write_text(f"0x{self.EN_OFFSET:08X}: Oui\n0x00000010: Bonjour",
                                     encoding="utf-8")
            en_path = td / "en.json"
            en_path.write_text(json.dumps(self.en_json), encoding="utf-8")
            out_path = td / "out.json"

            old_argv = sys.argv
            sys.argv = [
                "prepare_fr_json.py",
                "--combined", str(combined_path),
                "--english", str(en_path),
                "--english-rom", str(td / "nonexistent.gba"),
                "--output", str(out_path),
            ]
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    import scripts.prepare_fr_json as module
                    import importlib
                    importlib.reload(module)
                    ret = module.main()
            finally:
                sys.argv = old_argv

            self.assertEqual(ret, 0, "script must succeed even when ROM is absent")
            result = json.loads(out_path.read_text())
            offsets = {t["offset"] for t in result["translations"]}
            self.assertIn(0x10, offsets)
            self.assertNotIn(self.EN_OFFSET, offsets,
                             "without ROM no-pointer entry must not be synthesized")

    def test_garbage_zero_length_slot_excluded(self) -> None:
        """Offsets where the ROM has a 0xFF immediately (empty slot) must be skipped."""
        # Place a 0xFF at the target offset → 0 content bytes, must not be emitted.
        rom = _build_fake_rom({self.EN_OFFSET: b"\xFF"})
        result = _run_prepare(
            self._make_combined("OK"),
            self.en_json,
            rom,
        )
        offsets = {t["offset"] for t in result["translations"]}
        self.assertNotIn(self.EN_OFFSET, offsets,
                         "zero-length EN slot must not produce a translation entry")

    def test_original_length_matches_rom(self) -> None:
        """original_length must equal the EN byte count read from the ROM."""
        result = _run_prepare(
            self._make_combined("Oui"),
            self.en_json,
            self.rom,
        )
        offsets = {t["offset"]: t for t in result["translations"]}
        entry = offsets.get(self.EN_OFFSET)
        self.assertIsNotNone(entry)
        # EN_BYTES has 3 content bytes before the 0xFF terminator.
        self.assertEqual(entry["original_length"], 3)

    def test_english_raw_bytes_populated_for_inplace_entry(self) -> None:
        """No-pointer entries must carry the raw EN bytes for control-code extraction.

        Without this, the generic builder's _extract_control_sequences had no
        raw_bytes_hex to fall back to and parsed FC 01 NN macros out of the
        *decoded* text, where the argument bytes render as plain glyphs
        (e.g. 0x08 -> 'E with diaeresis') instead of <0xNN> tokens — leaving
        {COLOR}X macros unresolved (literal '?COLOR?' in the built ROM).
        """
        result = _run_prepare(
            self._make_combined("Oui"),
            self.en_json,
            self.rom,
        )
        offsets = {t["offset"]: t for t in result["translations"]}
        entry = offsets.get(self.EN_OFFSET)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.get("english_raw_bytes"), self.EN_BYTES.hex())


class TestDedicatedPatchExclusion(unittest.TestCase):
    """Offsets owned by dedicated post-build patches must never reach the JSON.

    The arrow-prefixed World-Map junction panels appear in the EN extraction as
    1-byte ASCII strings, so prepare_fr_json used to emit them as too_long
    entries that the generic builder relocated as ASCII — producing unreadable
    text when the game decoded those bytes with its Pokémon character table.
    """

    # A real junction offset owned by patch_worldmap_junction_panels_fr.
    # Panneau directionnel de la Route 5 signalé dans l'issue #128.
    JUNCTION_OFFSET = 0x1F70E41
    MISSION_TITLE_OFFSET = 0x1FA4E10

    def test_pc_labels_keep_allocator_stable_placeholders(self) -> None:
        """La source reste canonique, mais le JSON conserve l'empreinte historique."""
        requested = {
            0x41858D: "Déplacer Pokémon",
            0x41859A: "Déplacer objet",
            0x4185A5: "Salut !",
        }
        legacy = {
            0x41858D: "Dépl Pokémon",
            0x41859A: "Dépl. objet",
            0x4185A5: "À plus !",
        }
        en_json = _en_extraction([
            {
                "offset": offset,
                "byte_length": 32,
                "length": 32,
                "encoding": "pokemon",
                "decoded_text": "placeholder",
                "text": "placeholder",
            }
            for offset in requested
        ])
        result = _run_prepare(
            [f"0x{offset:X}: {text}" for offset, text in requested.items()],
            en_json,
            _build_fake_rom({}),
        )
        translations = {
            entry["offset"]: entry["translation"] for entry in result["translations"]
        }
        self.assertEqual(translations, legacy)

    def _en_json_with_arrow(self) -> dict:
        # Extractor sees the leading arrow byte (0x79) as ASCII ``y``.
        return _en_extraction([
            {"offset": 0x10, "byte_length": 5, "length": 5,
             "encoding": "pokemon", "decoded_text": "Hello", "text": "Hello"},
            {"offset": self.JUNCTION_OFFSET, "byte_length": 2, "length": 2,
             "encoding": "ascii", "decoded_text": "y", "text": "y"},
        ])

    def test_junction_offset_excluded_even_with_en_entry(self) -> None:
        """A junction offset present in EN extraction must be left out entirely."""
        combined = [
            f"0x{self.JUNCTION_OFFSET:08X}: <0x79> Hauteurs Gelees, Ville Blizzard"
            "\\n<0x7A> Bourg Cratere\\l<0x7C> Dresco",
            "0x00000010: Bonjour",
        ]
        rom = _build_fake_rom({self.JUNCTION_OFFSET: b"\x79\xFF"})
        result = _run_prepare(combined, self._en_json_with_arrow(), rom)
        offsets = {t["offset"] for t in result["translations"]}
        self.assertNotIn(
            self.JUNCTION_OFFSET, offsets,
            "junction-panel offset must be excluded so its dedicated patch owns it",
        )
        self.assertIn(0x10, offsets, "unrelated entries must still be produced")

    def test_mission_title_excluded_even_with_en_entry(self) -> None:
        """Le titre vivant est réservé au patch qui ne décale pas les relocalisations."""
        en_json = _en_extraction([
            {"offset": 0x10, "byte_length": 5, "length": 5,
             "encoding": "pokemon", "decoded_text": "Hello", "text": "Hello"},
            {"offset": self.MISSION_TITLE_OFFSET, "byte_length": 15, "length": 15,
             "encoding": "pokemon", "decoded_text": "The Food Thief",
             "text": "The Food Thief"},
        ])
        combined = [
            f"0x{self.MISSION_TITLE_OFFSET:08X}: Voleur de vivres",
            "0x00000010: Bonjour",
        ]
        result = _run_prepare(combined, en_json, _build_fake_rom({}))
        offsets = {t["offset"] for t in result["translations"]}
        self.assertNotIn(self.MISSION_TITLE_OFFSET, offsets)
        self.assertIn(0x10, offsets)

    def test_exclusion_set_matches_patch_targets(self) -> None:
        """The exclusion set must stay in sync with every dedicated patch."""
        import scripts.prepare_fr_json as module
        import importlib
        importlib.reload(module)
        sys.path.insert(0, str(ROOT / "scripts"))
        from languages.fr.patches.mission_titles import TARGETS as MISSION_TITLE_TARGETS
        from languages.fr.patches.pc_move_labels import DEDICATED_SOURCE_OFFSETS as PC_LABEL_TARGETS
        from languages.fr.patches.worldmap_junction_panels import TARGETS as JUNCTION_TARGETS
        from languages.fr.dedicated_patch_offsets import GENERIC_PLACEHOLDER_TRANSLATIONS
        self.assertEqual(
            set(module.DEDICATED_PATCH_OFFSETS) | set(GENERIC_PLACEHOLDER_TRANSLATIONS),
            set(JUNCTION_TARGETS) | set(MISSION_TITLE_TARGETS) | set(PC_LABEL_TARGETS),
            "DEDICATED_PATCH_OFFSETS must equal all dedicated patch targets",
        )


class TestPrepareFrNoiPipeline(unittest.TestCase):
    """Makefile wiring: prepare-fr must pass --english-rom."""

    MAKEFILE = ROOT / "Makefile"

    def test_prepare_fr_passes_english_rom(self) -> None:
        text = self.MAKEFILE.read_text(encoding="utf-8")
        # Find the prepare-fr recipe block.
        lines = text.splitlines()
        in_recipe = False
        recipe_lines: list[str] = []
        for line in lines:
            if line.startswith("prepare-fr:"):
                in_recipe = True
                continue
            if in_recipe:
                if line.startswith("\t"):
                    recipe_lines.append(line)
                elif line.strip():
                    break

        recipe = "\n".join(recipe_lines)
        self.assertIn(
            "--english-rom",
            recipe,
            "prepare-fr Makefile recipe must pass --english-rom to prepare_fr_json.py",
        )


if __name__ == "__main__":
    unittest.main()
