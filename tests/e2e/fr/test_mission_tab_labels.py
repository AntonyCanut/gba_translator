"""E2E : les libellés du menu Missions gardent le bon nombre (#46).

Le libellé « Actives » a déjà fait l'aller-retour deux fois : #116 l'avait
raccourci en « Active » parce que le moteur collait alors le suffixe partagé
« Missions » (« ActivesMissions » débordait), puis #114 a vidé ce suffixe sans
restaurer le pluriel. La chaîne anglaise ``Active`` a toutefois deux usages :
l'onglet blanc doit rester « Actives », tandis que le statut bleu d'une mission
doit rester « Active ». Ce garde décode les octets réellement lus par le moteur,
pas l'offset d'origine, qui garde les octets anglais périmés après relocalisation.
"""

import struct
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

SOURCE_ROM = Path("input/roms/patchedfrenchrom.gba")
FR_ROM = Path("output/roms/GenedRom-fr.gba")
GBA_BASE = 0x08000000

# Offset d'origine de chaque libellé → texte attendu en jeu.
TAB_LABELS = {
    0x1F5609F: "Toutes",
    0x1F56063: "Inactives",
    0x1F560A3: "Terminées",
}

# La chaîne source « Active » a deux consommateurs grammaticalement distincts.
# La nouvelle capture utilisateur associe le premier site aux statuts
# bleus des lignes et le second à l'onglet blanc en haut à gauche.
ACTIVE_STATUS_POINTER = 0x1EBFFC8
ACTIVE_TAB_POINTER = 0x1FB40B8

# Suffixe partagé collé à chaque catégorie par le moteur : doit rester vide (#114).
SUFFIX_OFFSET = 0x1F56040


def _decode_at(rom: bytes, offset: int, limit: int = 60) -> str:
    """Décode une chaîne CFRU terminée par 0xFF à l'offset indiqué."""
    chunk = rom[offset : offset + limit]
    end = chunk.find(b"\xff")
    raw = chunk if end == -1 else chunk[: end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def _pointer_sites(source_rom: bytes, original_offset: int) -> list[int]:
    """Liste les sites de pointeurs alignés visant la chaîne dans la ROM source."""
    needle = struct.pack("<I", original_offset + GBA_BASE)
    sites: list[int] = []
    start = 0
    while (idx := source_rom.find(needle, start)) != -1:
        if idx % 4 == 0:
            sites.append(idx)
        start = idx + 1
    return sites


@pytest.fixture(scope="module")
def source_rom_data() -> bytes:
    """ROM source, qui conserve les offsets de pointeurs d'origine."""
    assert SOURCE_ROM.exists(), f"ROM source absente : {SOURCE_ROM}"
    return SOURCE_ROM.read_bytes()


@pytest.fixture(scope="module")
def fr_rom_data() -> bytes:
    """ROM française versionnée."""
    assert FR_ROM.exists(), f"ROM FR absente : {FR_ROM}"
    return FR_ROM.read_bytes()


@pytest.mark.rom
class TestMissionTabLabelsFrench:
    """Les onglets, le statut individuel et le suffixe partagé."""

    @pytest.mark.parametrize(
        ("original_offset", "expected"), sorted(TAB_LABELS.items())
    )
    def test_every_live_pointer_reaches_the_plural_label(
        self,
        source_rom_data: bytes,
        fr_rom_data: bytes,
        original_offset: int,
        expected: str,
    ) -> None:
        sites = _pointer_sites(source_rom_data, original_offset)
        assert sites, f"aucun pointeur vers 0x{original_offset:X}"
        for site in sites:
            (target,) = struct.unpack_from("<I", fr_rom_data, site)
            assert _decode_at(fr_rom_data, target - GBA_BASE) == expected, (
                f"pointeur 0x{site:X} → 0x{target - GBA_BASE:X}"
            )

    @pytest.mark.parametrize(
        ("pointer_site", "expected"),
        (
            (ACTIVE_TAB_POINTER, "Actives"),
            (ACTIVE_STATUS_POINTER, "Active"),
        ),
    )
    def test_active_tab_is_plural_but_each_mission_status_is_singular(
        self,
        fr_rom_data: bytes,
        pointer_site: int,
        expected: str,
    ) -> None:
        """L'onglet blanc et le statut bleu ne partagent plus la même cible."""
        (target,) = struct.unpack_from("<I", fr_rom_data, pointer_site)
        assert _decode_at(fr_rom_data, target - GBA_BASE) == expected, (
            f"pointeur 0x{pointer_site:X} → 0x{target - GBA_BASE:X}"
        )

    def test_shared_missions_suffix_stays_blank(self, fr_rom_data: bytes) -> None:
        """Sans ce vidage, les onglets réafficheraient « ActivesMissions » (#114)."""
        assert _decode_at(fr_rom_data, SUFFIX_OFFSET) == ""
