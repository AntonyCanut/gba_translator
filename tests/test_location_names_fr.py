"""
Regression guard: all 14 World Map location names must survive every
``make build-fr`` rebuild and remain in French.

Why translations disappear
--------------------------
The build pipeline rewrites the JSON translation from scratch on every run.
An entry in ``combined_fr.txt`` can be silently dropped when:
  - ``apply_combined_fr.py --extend`` is skipped (new offsets not added to CSV)
  - A fix script regenerates combined_fr.txt or large CSV blocks, erasing
    inline label entries that are absent from the trilingual CSV (happened in
    c7c1ede: fixing one dialogue entry wiped 11 World Map labels)
  - The inline-overrides pass skips an offset it can't locate in the EN/ES diff

These tests catch any such regression immediately after ``make build-fr``.

Run standalone:   pytest tests/test_location_names_fr.py -v
Run via Makefile: make test-rom
"""

import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")

# Pre-encoded byte sequences (CFRU charmap, no terminator)
_THUNDERCAP_BYTES = bytes.fromhex("cedce9e2d8d9e6d7d5e4")  # "Thundercap"


def _read_at(rom: bytes, offset: int, limit: int = 200) -> str:
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xff")
    raw = chunk if end == -1 else chunk[: end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def _follow_ptr(rom: bytes, ptr_offset: int, limit: int = 400) -> str:
    """Return decoded text at the GBA pointer stored at ptr_offset."""
    base = 0x08000000
    if ptr_offset + 4 > len(rom):
        return ""
    ptr = struct.unpack_from("<I", rom, ptr_offset)[0]
    if ptr < base or ptr >= base + len(rom):
        return ""
    return _read_at(rom, ptr - base, limit)


# (offset, expected_fr_text, english_name)
# All 14 location names committed in feat(toponyms) 3824f11, recovered from
# the regression introduced by c7c1ede.
WORLD_MAP_LABELS = [
    (0xB500A0, "Bourg Gurun",       "ourg Gurun (was off-by-1)"),
    (0x721304, "Trou Glacé",        "Icy Hole"),
    (0x7214E8, "Île Scintillante",  "Glimmer Isle"),
    (0x721968, "Ville d'Epidimy",   "Epidimy Town"),
    (0xB50214, "Égouts d'Antisis",  "Antisis Sewers"),
    (0xB5026C, "Mont Foudroyant",   "Thundercap Mt."),
    (0xB503CC, "Volcan Cendreux",   "Cinder Volcano"),
    (0xB514E4, "Dehara",            "Dehara City"),
    (0xB52274, "Pension Pokémon",   "Pokemon Day Care"),
    (0xB522A4, "Bourg Polder",      "Polder Town"),
    (0xB531D8, "Île du Croissant",  "Newmoon Island"),
    (0xB535C8, "Île de la Lune",    "Fullmoon Island"),
    (0xB537AC, "Bois-Rouge",         "Redwood Village"),
    (0x720E74, "Fallshore",         "Fallshore City"),
    # Nouveaux noms traduits (follow-up 2026-06-17)
    (0x3EEF2D, "Grotte Faille",        "Rift Cave"),
    (0xB500F0, "Port-en-mer",          "Seaport City"),
    (0x3EEFEA, "Grotte de l'Être",     "Cave of Being"),
]


@pytest.mark.rom
class TestLocationNamesFR(unittest.TestCase):
    """All 14 World Map location names must survive each make build-fr rebuild."""

    @classmethod
    def setUpClass(cls):
        if not FR_ROM.exists():
            raise unittest.SkipTest(f"FR ROM not found: {FR_ROM}")
        cls.rom = FR_ROM.read_bytes()

    # ── World Map label tests (one per location) ──────────────────────────────

    def _assert_label(self, offset: int, expected_fr: str, en_name: str) -> None:
        text = _read_at(self.rom, offset).strip()
        self.assertEqual(
            text,
            expected_fr,
            f"World Map label at 0x{offset:08X} [{en_name}]: "
            f"expected {repr(expected_fr)}, got {repr(text)}",
        )

    def test_bourg_gurun(self):
        """0xB500A0: 'Bourg Gurun' (off-by-1 byte fix, was 'ourg Gurun')."""
        self._assert_label(0xB500A0, "Bourg Gurun", "ourg Gurun")

    def test_trou_glace(self):
        """0x721304: 'Trou Glacé' (was 'Icy Hole')."""
        self._assert_label(0x721304, "Trou Glacé", "Icy Hole")

    def test_ile_scintillante(self):
        """0x7214E8: 'Île Scintillante' (was 'Glimmer Isle')."""
        self._assert_label(0x7214E8, "Île Scintillante", "Glimmer Isle")

    def test_ville_epidimy(self):
        """0x721968: 'Ville d'Epidimy' (was 'Epidimy Town')."""
        self._assert_label(0x721968, "Ville d'Epidimy", "Epidimy Town")

    def test_egouts_antisis(self):
        """0xB50214: 'Égouts d'Antisis' (was 'Antisis Sewers')."""
        self._assert_label(0xB50214, "Égouts d'Antisis", "Antisis Sewers")

    def test_mont_foudroyant_worldmap(self):
        """0xB5026C: 'Mont Foudroyant' (was 'Thundercap Mt.', formerly 'Mont Foudre')."""
        self._assert_label(0xB5026C, "Mont Foudroyant", "Thundercap Mt.")

    def test_volcan_cendreux(self):
        """0xB503CC: 'Volcan Cendreux' (was 'Cinder Volcano')."""
        self._assert_label(0xB503CC, "Volcan Cendreux", "Cinder Volcano")

    def test_dehara(self):
        """0xB514E4: 'Dehara' (was 'Dehara City')."""
        self._assert_label(0xB514E4, "Dehara", "Dehara City")

    def test_pension_pokemon(self):
        """0xB52274: 'Pension Pokémon' (was 'Pokémon Day Care')."""
        self._assert_label(0xB52274, "Pension Pokémon", "Pokemon Day Care")

    def test_bourg_polder(self):
        """0xB522A4: 'Bourg Polder' (was 'Polder Town')."""
        self._assert_label(0xB522A4, "Bourg Polder", "Polder Town")

    def test_ile_du_croissant(self):
        """0xB531D8: 'Île du Croissant' (was 'Newmoon Island')."""
        self._assert_label(0xB531D8, "Île du Croissant", "Newmoon Island")

    def test_ile_de_la_lune(self):
        """0xB535C8: 'Île de la Lune' (was 'Fullmoon Island')."""
        self._assert_label(0xB535C8, "Île de la Lune", "Fullmoon Island")

    def test_bois_rouge(self):
        """0xB537AC: 'Bois-Rouge' (was 'Redwood Village', formerly 'Village Redwood')."""
        self._assert_label(0xB537AC, "Bois-Rouge", "Redwood Village")

    def test_fallshore(self):
        """0x720E74: 'Fallshore' (was 'Ville de Fallshore' / 'Fallshore City')."""
        self._assert_label(0x720E74, "Fallshore", "Fallshore City")

    def test_grotte_faille_worldmap(self):
        """0x3EEF2D: 'Grotte Faille' (was 'Rift Cave')."""
        self._assert_label(0x3EEF2D, "Grotte Faille", "Rift Cave")

    def test_port_en_mer_worldmap(self):
        """0xB500F0: 'Port-en-mer' (was 'Seaport City', formerly 'Ville Portuaire')."""
        self._assert_label(0xB500F0, "Port-en-mer", "Seaport City")

    def test_grotte_de_letre_worldmap(self):
        """0x3EEFEA: 'Grotte de l'Être' (was 'Cave of Being')."""
        self._assert_label(0x3EEFEA, "Grotte de l'Être", "Cave of Being")

    def test_grotte_de_letre_worldmap2_via_pointer(self):
        """0x1EEB8C0 label relocated to free space — follow ptr@0x1FB3E4C.

        The original 'Cave of Being' bytes remain at 0x1EEB8C0 (text too long
        to fit in place); the engine reads via a GBA pointer that now targets
        the relocated 'Grotte de l'Être' string in free space.
        """
        text = _follow_ptr(self.rom, 0x1FB3E4C)
        self.assertTrue(text, "Pointer at 0x1FB3E4C is invalid or points outside ROM")
        self.assertIn(
            "Grotte de l'Être",
            text,
            f"Expected \"Grotte de l'Être\" via ptr@0x1FB3E4C, got: {repr(text[:60])}",
        )

    def test_bourg_po_via_pointer(self):
        """0x1F84FEF bonus text relocated — follow ptr@0x1FB3D8C.

        'Bonus: Po Town' was identical in EN and ES (no inline diff), so the
        engine accesses it via a GBA pointer.  The relocated FR string reads
        'Bonus : Bourg-Pô'.
        """
        text = _follow_ptr(self.rom, 0x1FB3D8C)
        self.assertTrue(text, "Pointer at 0x1FB3D8C is invalid or points outside ROM")
        self.assertIn(
            "Bourg-Pô",
            text,
            f"Expected 'Bourg-Pô' via ptr@0x1FB3D8C, got: {repr(text[:60])}",
        )

    # ── Mont Foudre: pointer-based NPC dialogue ───────────────────────────────

    def test_mont_foudroyant_npc_dialogue_pointer(self):
        """Pointer at 0x7C252E must lead to French NPC dialogue (contains 'Foudroyant').

        The pipeline relocates the translated string to free space and repoints
        0x7C252E.  The original English bytes at 0x7C2540 remain but are
        unreachable — this test follows the live pointer so a silent revert is
        caught even if the original address still looks untouched.
        """
        text = _follow_ptr(self.rom, 0x7C252E)
        self.assertTrue(text, "Pointer at 0x7C252E is invalid or points outside ROM")
        self.assertIn(
            "Foudroyant",
            text,
            f"Expected 'Foudroyant' via ptr@0x7C252E, got: {repr(text[:60])}",
        )
        self.assertNotIn(
            "Thundercap",
            text,
            f"'Thundercap' still in NPC dialogue via ptr@0x7C252E: {repr(text[:60])}",
        )

    def test_no_active_pointer_to_thundercap(self):
        """No GBA pointer in the ROM should point to a 'Thundercap' string.

        Orphaned English bytes are left in place after pointer relocation but
        must not be reachable via any active ROM pointer.
        """
        base = 0x08000000
        rom = self.rom
        live: list = []
        pos = 0
        while True:
            p = rom.find(_THUNDERCAP_BYTES, pos)
            if p == -1:
                break
            ptr_val = struct.pack("<I", p + base)
            count = rom.count(ptr_val)
            if count > 0:
                end = rom.find(b"\xff", p)
                txt = TextDecoder.decode_pokemon(rom[p : end + 1])
                live.append((hex(p), count, txt[:60]))
            pos = p + 1
        self.assertEqual(
            live,
            [],
            f"Found {len(live)} live pointer(s) to 'Thundercap' string(s): {live}",
        )


if __name__ == "__main__":
    unittest.main()
