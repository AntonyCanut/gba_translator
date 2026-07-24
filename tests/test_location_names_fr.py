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

import re
import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder, TextEncoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")

# Pre-encoded byte sequences (CFRU charmap, no terminator)
_THUNDERCAP_BYTES = bytes.fromhex("cedce9e2d8d9e6d7d5e4")  # "Thundercap"

_ENC = TextEncoder()


def _encode_no_term(s: str) -> bytes:
    """Encode ``s`` with the CFRU charmap, dropping the trailing 0xFF."""
    b = _ENC.encode_pokemon(s)
    return b[:-1] if b and b[-1] == 0xFF else b


def _string_containing(rom: bytes, anchor: str) -> str:
    """Decode the full ROM string whose bytes contain ``anchor``.

    Follows relocation transparently: whatever free-space address the
    reinserter moved the string to, the anchor bytes are searched ROM-wide
    and the enclosing 0xFF-terminated string is decoded.
    """
    ab = _encode_no_term(anchor)
    i = rom.find(ab)
    if i == -1:
        return ""
    start = rom.rfind(b"\xff", 0, i) + 1
    end = rom.find(b"\xff", i)
    end = end if end != -1 else i + 400
    return TextDecoder.decode_pokemon(rom[start:end], preserve_unknown=True)


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
    (0xB500A0, "Gurenbourg",       "ourg Gurun (was off-by-1)"),
    (0x721304, "Gouffre Gelé",        "Icy Hole"),
    (0x7214E8, "Île Scintillante",  "Glimmer Isle"),
    (0x721968, "Épidia",   "Epidimy Town"),
    (0xB50214, "Égouts d'Antésia",  "Antisis Sewers"),
    (0xB5026C, "Mont Foudroyant",   "Thundercap Mt."),
    (0xB503CC, "Volcan Cendré",   "Cinder Volcano"),
    (0xB514E4, "Daherapolis",            "Dehara City"),
    (0xB52274, "Pension Pokémon",   "Pokemon Day Care"),
    (0xB522A4, "Polderive",      "Polder Town"),
    (0xB531D8, "Île Nouvellune",  "Newmoon Island"),
    (0xB535C8, "Île Pleinelune",    "Fullmoon Island"),
    (0xB537AC, "Rougebois",         "Redwood Village"),
    (0x720E74, "Rivapolis",         "Fallshore City"),
    # Nouveaux noms traduits (follow-up 2026-06-17)
    (0x3EEF2D, "Grotte Faille",        "Rift Cave"),
    (0xB500F0, "Naville",          "Seaport City"),
    (0x3EEFEA, "Grotte de l'Être",     "Cave of Being"),
    # Renommage Dresco Town → Dresco (follow-up 2026-06-18)
    (0x71CA60, "Dresco",               "Dresco Town"),
]

CHENAL_AUBRUN_REFERENCES = {
    0x7E5BF8: "le Chenal Aubrun",
    0x1F273CB: "au Chenal Aubrun",
    0x1F5B996: "du Chenal Aubrun",
    0x1F651CB: "au Chenal Aubrun",
}


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
        """0xB500A0: 'Gurenbourg' (off-by-1 byte fix, was 'ourg Gurun')."""
        self._assert_label(0xB500A0, "Gurenbourg", "ourg Gurun")

    def test_trou_glace(self):
        """0x721304: 'Gouffre Gelé' (was 'Icy Hole')."""
        self._assert_label(0x721304, "Gouffre Gelé", "Icy Hole")

    def test_ile_scintillante(self):
        """0x7214E8: 'Île Scintillante' (was 'Glimmer Isle')."""
        self._assert_label(0x7214E8, "Île Scintillante", "Glimmer Isle")

    def test_ville_epidimy(self):
        """0x721968: 'Épidimi' (was 'Epidimy Town')."""
        self._assert_label(0x721968, "Épidia", "Epidimy Town")

    def test_egouts_antisis(self):
        """0xB50214: 'Égouts d'Antésia' (was 'Antisis Sewers')."""
        self._assert_label(0xB50214, "Égouts d'Antésia", "Antisis Sewers")

    def test_mont_foudroyant_worldmap(self):
        """0xB5026C: 'Pic Grondant' (was 'Thundercap Mt.', formerly 'Mont Foudre')."""
        self._assert_label(0xB5026C, "Mont Foudroyant", "Thundercap Mt.")

    def test_volcan_cendreux(self):
        """0xB503CC: 'Volcan Cendré' (was 'Cinder Volcano', formerly v2 'Cendreux')."""
        self._assert_label(0xB503CC, "Volcan Cendré", "Cinder Volcano")

    def test_dehara(self):
        """0xB514E4: 'Dehara' (was 'Dehara City')."""
        self._assert_label(0xB514E4, "Daherapolis", "Dehara City")

    def test_pension_pokemon(self):
        """0xB52274: 'Pension Pokémon' (was 'Pokémon Day Care')."""
        self._assert_label(0xB52274, "Pension Pokémon", "Pokemon Day Care")

    def test_bourg_polder(self):
        """0xB522A4: 'Polder sur Rive' (was 'Polder Town')."""
        self._assert_label(0xB522A4, "Polderive", "Polder Town")

    def test_ile_du_croissant(self):
        """0xB531D8: 'Île Nouvelle Lune' (was 'Newmoon Island')."""
        self._assert_label(0xB531D8, "Île Nouvellune", "Newmoon Island")

    def test_ile_de_la_lune(self):
        """0xB535C8: 'Île Pleine Lune' (was 'Fullmoon Island')."""
        self._assert_label(0xB535C8, "Île Pleinelune", "Fullmoon Island")

    def test_bois_rouge(self):
        """0xB537AC: 'Rougebois' (was 'Redwood Village', formerly 'Village Redwood')."""
        self._assert_label(0xB537AC, "Rougebois", "Redwood Village")

    def test_fallshore(self):
        """0x720E74: 'Fallshore' (was 'Ville de Fallshore' / 'Fallshore City')."""
        self._assert_label(0x720E74, "Rivapolis", "Fallshore City")

    def test_grotte_faille_worldmap(self):
        """0x3EEF2D: 'Grotte Falaise' (was 'Rift Cave')."""
        self._assert_label(0x3EEF2D, "Grotte Faille", "Rift Cave")

    def test_port_en_mer_worldmap(self):
        """0xB500F0: 'Naville' (was 'Seaport City', formerly 'Ville Portuaire')."""
        self._assert_label(0xB500F0, "Naville", "Seaport City")

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

    # ── Dresco: renamed from "Dresco Town" (follow-up 2026-06-18) ────────────

    def test_dresco_worldmap(self):
        """0x71CA60: 'Dresco' (was 'Dresco Town')."""
        self._assert_label(0x71CA60, "Dresco", "Dresco Town")

    def test_dresco_zone_name_inline(self):
        """0x78D781: 'Dresco' in-place (was 'Dresco Town', ptr@0x78D779).

        This is the zone name string used for the in-game area popup.
        The FR text fits in-place (7 ≤ 12 bytes), so no relocation occurs.
        """
        text = _read_at(self.rom, 0x78D781).strip()
        self.assertEqual(
            text,
            "Dresco",
            f"Zone name at 0x78D781: expected 'Dresco', got {repr(text)}",
        )

    def test_dresco_zone_name_eff254(self):
        """0x1EFF254: 'Dresco' in-place (was 'Dresco Town', ptrs@0x1E93A0C + 0x1EAF944).

        This string is pointed to by two places and precedes the day/night
        label pair at 0x1EFF260 ('Dresco D') / 0x1EFF26E ('Dresco N').
        """
        text = _read_at(self.rom, 0x1EFF254).strip()
        self.assertEqual(
            text,
            "Dresco",
            f"Zone name at 0x1EFF254: expected 'Dresco', got {repr(text)}",
        )

    def test_no_active_pointer_to_dresco_town(self):
        """No GBA pointer in the ROM should point to a 'Dresco Town' string.

        Orphaned English bytes remain in place after pipeline injection but
        must not be reachable via any active ROM pointer.
        """
        base = 0x08000000
        rom = self.rom
        # Encode 'Dresco Town' (without terminator) using known EN ROM bytes
        dresco_town_bytes = bytes.fromhex("bee6d9e7d7e300cee3eb")
        live: list = []
        pos = 0
        while True:
            p = rom.find(dresco_town_bytes, pos)
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
            f"Found {len(live)} live pointer(s) to 'Dresco Town' string(s): {live}",
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


    # ── Noms de zones anglais traduits (follow-up 2026-06-27) ────────────────

    def test_ville_blizzard_zone_name(self):
        """ptr@0x3F1CBC must resolve to 'Cimistral' (was 'Blizzard City')."""
        text = _follow_ptr(self.rom, 0x3F1CBC)
        self.assertEqual(text.strip(), "Cimistral",
                         f"Zone name via ptr@0x3F1CBC: got {repr(text[:40])}")

    def test_ville_antisis_zone_name(self):
        """ptr@0x3F1D2C must resolve to ‘Ville d’Antisis’ (was ‘Antisis City’)."""
        text = _follow_ptr(self.rom, 0x3F1D2C)
        self.assertEqual(text.strip(), "Antésia",
                         f"Zone name via ptr@0x3F1D2C: got {repr(text[:40])}")

    def test_pic_cristal_zone_name(self):
        """ptr@0x3F1DC4 must resolve to 'Pic Cristal' (was 'Crystal Peak')."""
        text = _follow_ptr(self.rom, 0x3F1DC4)
        self.assertEqual(text.strip(), "Pic Cristal",
                         f"Zone name via ptr@0x3F1DC4: got {repr(text[:40])}")

    def test_grotte_cachee_zone_name(self):
        """ptr@0x3F1D4C must resolve to 'Grotte Cach\xe9e' (was 'Hidden Grotto')."""
        text = _follow_ptr(self.rom, 0x3F1D4C)
        self.assertEqual(text.strip(), "Grotte Cach\xe9e",
                         f"Zone name via ptr@0x3F1D4C: got {repr(text[:40])}")

    def test_tunnel_perdu_zone_name(self):
        """ptr@0x3F1DBC must resolve to 'Tunnel Perdu' (was 'Lost Tunnel')."""
        text = _follow_ptr(self.rom, 0x3F1DBC)
        self.assertEqual(text.strip(), "Tunnel Perdu",
                         f"Zone name via ptr@0x3F1DBC: got {repr(text[:40])}")

    def test_port_antisis_zone_name(self):
        """ptr@0x3F1E34 must resolve to 'Port d’Antisis' (was 'Antisis Port')."""
        text = _follow_ptr(self.rom, 0x3F1E34)
        self.assertEqual(text.strip(), "Port d'Antésia",
                         f"Zone name via ptr@0x3F1E34: got {repr(text[:40])}")

    def test_champs_magnolia_zone_name(self):
        """ptr@0x3F1E24 must resolve to 'Champs de Magnolia' (was 'Magnolia Fields')."""
        text = _follow_ptr(self.rom, 0x3F1E24)
        self.assertEqual(text.strip(), "Champs Magnolia",
                         f"Zone name via ptr@0x3F1E24: got {repr(text[:40])}")

    def test_zone_safari_zone_name(self):
        """ptr@0x3F1DDC must resolve to 'Zone Safari' (was 'Safari Zone')."""
        text = _follow_ptr(self.rom, 0x3F1DDC)
        self.assertEqual(text.strip(), "Zone Safari",
                         f"Zone name via ptr@0x3F1DDC: got {repr(text[:40])}")

    def test_foret_lugubre_zone_name(self):
        """ptr@0x3F1D44 must resolve to 'Bois Lugubres' (was 'Bois Lugubress' typo)."""
        text = _follow_ptr(self.rom, 0x3F1D44)
        self.assertEqual(text.strip(), "Boissombre",
                         f"Zone name via ptr@0x3F1D44: got {repr(text[:40])}")

    def test_bourg_cratere_fly_banner(self):
        """ptr@0x78D809 must resolve to 'Cratéria' (was 'Crater Town' fly banner)."""
        text = _follow_ptr(self.rom, 0x78D809)
        self.assertEqual(text.strip(), "Cratéris",
                         f"Fly banner via ptr@0x78D809: got {repr(text[:40])}")

    def test_ville_blizzard_fly_banner(self):
        """ptr@0x78D849 must resolve to 'Cimistral' (was 'Blizzard City' fly banner)."""
        text = _follow_ptr(self.rom, 0x78D849)
        self.assertEqual(text.strip(), "Cimistral",
                         f"Fly banner via ptr@0x78D849: got {repr(text[:40])}")

    def test_no_active_pointer_to_blizzard_city_zone(self):
        """ptr@0x3F1CBC must NOT point to a 'Blizzard City' string.

        The zone name table entry for Blizzard City must now be French.
        """
        text = _follow_ptr(self.rom, 0x3F1CBC)
        self.assertNotIn(
            "Blizzard City",
            text,
            f"'Blizzard City' still reachable via zone-name ptr@0x3F1CBC: {repr(text[:60])}",
        )

    def test_chenal_aubrun_references_are_masculine(self):
        """Les quatre dialogues corrigés atteignent la ROM avec l’accord masculin."""
        feminine_forms = ("la Chenal Aubrun", "de la Chenal Aubrun", "à la Chenal Aubrun")
        for offset, expected in CHENAL_AUBRUN_REFERENCES.items():
            text = _read_at(self.rom, offset, limit=300)
            normalized = re.sub(r"(?:<0x[0-9A-F]{2}>|\s)+", " ", text).strip()
            self.assertIn(expected, normalized, f"0x{offset:07X}: {text!r}")
            for forbidden in feminine_forms:
                self.assertNotIn(forbidden, normalized, f"0x{offset:07X}: {text!r}")

    # ── Volcan Cendré toponym variants (B-138, 2026-07-02) ─────────────────
    #
    # combined_fr.txt used to carry "Volcan Cinder" / "Volcan de Cinder" /
    # "Volcan Cendre" (no accent) / "Volcan de Cendres" alongside the canon
    # "Volcan Cendré" (guarded at 0xB503CC by test_volcan_cendreux). Two of
    # these offsets are too long for their original slot and get relocated
    # by the reinserter, so the *original* offset keeps holding stale
    # English bytes forever — the live text must be read through the
    # pointer site, not the original offset (see _follow_ptr usage below).

    def test_dialogue_le_volcan_est_dangereux(self):
        """Relocated dialogue (was 0x7CE471 'Le Volcan de Cendres est dangereux.')."""
        text = _follow_ptr(self.rom, 0x007B4B24)
        self.assertIn("Volcan Cendré", text, f"got {repr(text[:60])}")

    def test_sulfura_statue_description(self):
        """Relocated Pokédex/statue description (was 0x1F70BB2 'Volcan Cendre')."""
        text = _follow_ptr(self.rom, 0x01E930DC)
        self.assertIn("Volcan Cendré", text, f"got {repr(text[:80])}")

    def test_champion_speech_volcan_cendre(self):
        """0x1EE118A champion dialogue (was 'Volcan Cinder').

        The source string carries a pre-existing hard line-break (<0xFA>)
        between "Volcan" and "Cendré" — check both halves and the absence
        of the English residue rather than the joined phrase.
        """
        text = _read_at(self.rom, 0x1EE118A, limit=1000)
        self.assertIn("Volcan", text)
        self.assertIn("Cendré", text)
        self.assertNotIn("Cinder", text)

    def test_volcan_passage_sign(self):
        """0x1F70D9B sign 'Volcan Cendré\\nPassage' (was 'Volcan de Cinder')."""
        text = _read_at(self.rom, 0x1F70D9B)
        self.assertEqual(text.strip(), "Volcan Cendré\nPassage")

    def test_route13_junction_panel_daherapolis(self):
        """0x1F71962 junction panel (was 'Volcan Cendre')."""
        text = _read_at(self.rom, 0x1F71962, limit=200)
        self.assertIn("Volcan Cendré", text)

    def test_route13_junction_panel_route14(self):
        """0x1F719C0 junction panel (was 'Volcan Cendre')."""
        text = _read_at(self.rom, 0x1F719C0, limit=200)
        self.assertIn("Volcan Cendré", text)

    def test_pokemon_found_above_volcan(self):
        """Relocated catch-location blurb (was 0x1FAA781 'Volcan Cinder')."""
        text = _follow_ptr(self.rom, 0x01EACFC8, limit=200)
        self.assertIn("Volcan Cendré", text)

    def test_rival_speech_volcan_cendre(self):
        """0x1F5175B rival dialogue (was 'Volcan Cinder')."""
        text = _read_at(self.rom, 0x1F5175B, limit=1000)
        self.assertIn("Volcan Cendré", text)

    # ── B-138 follow-up (2026-07-02): regressions the first pass missed ──────
    #
    # The first B-138 sweep grepped `Volcan [A-Za-zé ]*`, which REQUIRES a
    # space after "Volcan". That pattern is blind to two living forms that
    # actually render in-game:
    #   • English word order "Cinder Volcano" ("Volcano" has no trailing space
    #     to match, and "Cinder" comes first) — 0x1F49D19 (Hoopa dialogue),
    #     0x74503F (Sulfura statue). Both relocated to free space.
    #   • The stale v2 toponym "CENDREUX" (superseded by canon "CENDRÉ" in the
    #     toponym v3 rename) — 0x7D61AD (Marlon's all-caps sentence speech),
    #     wrapped in {COLOR} codes so no plain "Volcan " prefix precedes it.
    # These tests follow the relocated strings by content, not by offset.

    def test_hoopa_dialogue_cinder_volcano_now_french(self):
        """Relocated Hoopa dialogue (was 0x1F49D19 English 'Cinder Volcano')."""
        text = _string_containing(self.rom, "vide du Volcan")
        self.assertTrue(text, "Hoopa dialogue anchor not found in ROM")
        self.assertIn("Volcan", text)
        self.assertIn("Cendré", text)
        self.assertNotIn("Cinder", text)

    def test_sulfura_statue_745_cinder_volcano_now_french(self):
        """Relocated Sulfura statue (was 0x74503F English 'Cinder Volcano')."""
        text = _string_containing(self.rom, "représente Sulfura,")
        self.assertTrue(text, "Sulfura statue anchor not found in ROM")
        self.assertIn("Volcan Cendré", text)
        self.assertNotIn("Cinder", text)
        self.assertNotIn("Volcano", text)

    def test_marlon_speech_volcan_cendre_not_cendreux(self):
        """0x7D61AD Marlon speech: stale v2 'CENDREUX' -> canon 'CENDRÉ'."""
        text = _string_containing(self.rom, "DANS LE VOLCAN")
        self.assertTrue(text, "Marlon speech anchor not found in ROM")
        self.assertIn("CENDRÉ", text)
        self.assertNotIn("CENDREUX", text)

    def test_cinder_volcano_west_map_banner_now_french(self):
        """Map-popup banner name (was 0x78D7C8 English 'Cinder Volcano West').

        This is a map-name popup: a struct at 0x78D7BC holds an *embedded*
        pointer (at 0x78D7C0) to the display name text at 0x78D7C8. The engine
        renders the name through that embedded pointer, so verification must
        follow ptr@0x78D7C0 rather than read the struct offset. patch_zone_names
        relocates the FR text and repoints 0x78D7C0.
        """
        text = _follow_ptr(self.rom, 0x78D7C0)
        self.assertEqual(
            text.strip(),
            "Volcan Cendré Ouest",
            f"Map banner via ptr@0x78D7C0: got {repr(text[:40])}",
        )

    def test_no_stale_cendreux_byte_sequence_anywhere(self):
        """The superseded v2 toponym 'Cendreux'/'CENDREUX' (in any case) must
        not appear anywhere in the built ROM — it has no legitimate use."""
        for phrase in ("Cendreux", "CENDREUX"):
            self.assertEqual(
                self.rom.count(_encode_no_term(phrase)),
                0,
                f"Stale toponym '{phrase}' still present in ROM",
            )


if __name__ == "__main__":
    unittest.main()
