"""Tests pour patch_legendary_ritual_fr.

B-56 / P-70 : la passe repoint_stale_text_pointers.py a faux-positivé des
fenêtres de 4 octets des scripts de rituel légendaire (une suite `setflag` dont
la lecture little-endian vaut 0x09F62908 = l'adresse anglaise de "I swam, of
course!") et les a réécrites avec l'adresse de la chaîne française relocalisée
(0x08C277E1). Le script corrompu n'atteint plus `setwildbattle` : le combat de
légendaire ne se lance jamais (la séquence Groudon « tourne en boucle »).

L'ancienne version restaurait seulement 2 offsets codés en dur (Ho-Oh/Lugia) ;
après chaque rebuild la passe re-clobberait les ~11 autres sites (dont Groudon)
qui restaient anglais/cassés. Le patch DÉCOUVRE désormais tous les sites par
signature et les restaure depuis la ROM anglaise — tout en laissant intacts les
deux vrais pointeurs relocalisés (0x1E8738D / 0x1E873B4) qui partagent les
octets mais n'ont pas l'opcode `setflag` (0x29) qui précède.
"""

import unittest

from scripts import patch_legendary_ritual_fr as patch

CANON = bytes([0x08, 0x29, 0xF6, 0x09])          # setflag 0x08E2 / setflag 0x09F6
CORRUPT = (0x08C277E1).to_bytes(4, "little")     # -> "J'ai nagé, bien sûr !"
SIZE = 0x1E8C800

# A real setflag chain: ... 29 E2 | 08 29 F6 09 | 29 F0 ...
# The window starts at the high operand byte of `setflag 0x08E2`, so the byte
# two before it (off-2) is the *previous* setflag opcode 0x29.
SETFLAG_PREFIX = bytes([0x29, 0xE2])             # written at off-2 .. off-1
SETFLAG_SUFFIX = bytes([0x29, 0xF0, 0x02])       # written at off+4 ..

# Three clobber-prone setflag-chain sites + one genuine relocated pointer that
# must survive (CANON window but preceded by a non-setflag byte, e.g. 0xF6).
CHAIN_SITES = (0x1E59D1F, 0x1E8C677, 0x1E8C782)
GENUINE_POINTER_SITE = 0x1E8738D


def _write_chain(buf, off):
    buf[off - 2:off] = SETFLAG_PREFIX
    buf[off:off + 4] = CANON
    buf[off + 4:off + 7] = SETFLAG_SUFFIX


def _write_genuine_pointer(buf, off, window):
    # Preceded by 0xF6 (not a setflag opcode) so discovery excludes it.
    buf[off - 2:off] = bytes([0xF6, 0x09])
    buf[off:off + 4] = window


class DiscoverClobberedSitesTests(unittest.TestCase):
    def test_finds_setflag_chains_excludes_genuine_pointer(self):
        src = bytearray(b"\x00" * SIZE)
        for off in CHAIN_SITES:
            _write_chain(src, off)
        _write_genuine_pointer(src, GENUINE_POINTER_SITE, CANON)

        found = patch.discover_clobbered_sites(bytes(src))
        self.assertEqual(sorted(found), sorted(CHAIN_SITES))
        self.assertNotIn(GENUINE_POINTER_SITE, found)


class PatchLegendaryRitualTests(unittest.TestCase):
    def _source(self):
        src = bytearray(b"\x00" * SIZE)
        for off in CHAIN_SITES:
            _write_chain(src, off)
        _write_genuine_pointer(src, GENUINE_POINTER_SITE, CANON)
        return bytes(src)

    def test_restores_every_clobbered_site(self):
        source = self._source()
        rom = bytearray(source)
        for off in CHAIN_SITES:
            rom[off:off + 4] = CORRUPT
        fixed = patch.patch(rom, source)
        self.assertEqual(fixed, len(CHAIN_SITES))
        for off in CHAIN_SITES:
            self.assertEqual(bytes(rom[off:off + 4]), CANON)

    def test_genuine_relocated_pointer_is_left_french(self):
        source = self._source()
        rom = bytearray(source)
        # The genuine pointer holds the relocated French pointer in the FR ROM.
        rom[GENUINE_POINTER_SITE:GENUINE_POINTER_SITE + 4] = CORRUPT
        patch.patch(rom, source)
        self.assertEqual(
            bytes(rom[GENUINE_POINTER_SITE:GENUINE_POINTER_SITE + 4]), CORRUPT
        )

    def test_idempotent_on_clean_rom(self):
        source = self._source()
        rom = bytearray(source)  # already canonical
        fixed = patch.patch(rom, source)
        self.assertEqual(fixed, 0)
        for off in CHAIN_SITES:
            self.assertEqual(bytes(rom[off:off + 4]), CANON)

    def test_refuses_unexpected_bytes(self):
        source = self._source()
        rom = bytearray(source)
        off = CHAIN_SITES[0]
        rom[off:off + 4] = b"\xde\xad\xbe\xef"  # neither canonical nor known corruption
        with self.assertRaises(SystemExit):
            patch.patch(rom, source)


if __name__ == "__main__":
    unittest.main()
