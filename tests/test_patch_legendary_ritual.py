"""Tests pour patch_legendary_ritual_fr.

B-56 ("Oh oh") : la passe repoint_stale_text_pointers.py a faux-positivé une
fenêtre de 4 octets du script du rituel Ho-Oh/Lugia (une suite `setflag` dont la
lecture little-endian vaut 0x09F62908 = l'adresse anglaise de "I swam, of
course!") et l'a réécrite avec l'adresse de la chaîne française relocalisée
(0x08C277E1). Le script corrompu n'atteint plus `setwildbattle` : le combat de
légendaire ne se lance jamais. Ce patch restaure les octets canoniques depuis la
ROM anglaise aux trois sites (Ho-Oh 0x1E8C677, Lugia 0x1E8C782, Groudon/Orbe
Rouge 0x1E59D1F — même faux-positif, même pointeur corrompu 0x08C277E1).
"""

import unittest

from scripts import patch_legendary_ritual_fr as patch

CANON = bytes([0x08, 0x29, 0xF6, 0x09])          # setflag 0x08E2 / setflag 0x09F6
CORRUPT = (0x08C277E1).to_bytes(4, "little")     # -> "J'ai nagé, bien sûr !"
SIZE = 0x1E8C800


def _blank():
    return bytearray(b"\x00" * SIZE)


class PatchLegendaryRitualTests(unittest.TestCase):
    def _source(self):
        src = _blank()
        for off, _ in patch.RITUAL_SCRIPT_FIXES:
            src[off:off + 4] = CANON
        return bytes(src)

    def test_restores_both_corrupted_sites(self):
        source = self._source()
        rom = bytearray(source)
        for off, _ in patch.RITUAL_SCRIPT_FIXES:
            rom[off:off + 4] = CORRUPT
        fixed = patch.patch(rom, source)
        self.assertEqual(fixed, len(patch.RITUAL_SCRIPT_FIXES))
        for off, _ in patch.RITUAL_SCRIPT_FIXES:
            self.assertEqual(bytes(rom[off:off + 4]), CANON)

    def test_idempotent_on_clean_rom(self):
        source = self._source()
        rom = bytearray(source)  # already canonical
        fixed = patch.patch(rom, source)
        self.assertEqual(fixed, 0)
        for off, _ in patch.RITUAL_SCRIPT_FIXES:
            self.assertEqual(bytes(rom[off:off + 4]), CANON)

    def test_refuses_unexpected_bytes(self):
        source = self._source()
        rom = bytearray(source)
        off = patch.RITUAL_SCRIPT_FIXES[0][0]
        rom[off:off + 4] = b"\xde\xad\xbe\xef"  # neither canonical nor the known corruption
        with self.assertRaises(SystemExit):
            patch.patch(rom, source)

    def test_discovers_unlisted_setflag_chain_site(self):
        # A clobbered site NOT in the named list must still be repaired when it
        # carries the signature: FR holds the corrupt pointer, English holds the
        # canonical window, preceded by a `setflag` opcode (0x29).
        src = bytearray(self._source())
        site = 0x1000
        src[site - 2] = 0x29              # `setflag` opcode before the window
        src[site:site + 4] = CANON        # canonical 08 29 F6 09 window
        source = bytes(src)
        rom = bytearray(source)
        rom[site:site + 4] = CORRUPT      # clobbered in the FR build
        fixed = patch.patch(rom, source)
        self.assertEqual(bytes(rom[site:site + 4]), CANON)
        self.assertGreaterEqual(fixed, 1)

    def test_legit_relocated_pointer_not_reverted(self):
        # Same canonical bytes, but NOT preceded by a setflag opcode: this is a
        # genuine relocated French text pointer (e.g. 0x1E8738D) and must be left
        # exactly as the build produced it.
        src = bytearray(self._source())
        site = 0x2000
        src[site - 2] = 0xF6              # pointer context, not a setflag opcode
        src[site:site + 4] = CANON
        source = bytes(src)
        rom = bytearray(source)
        rom[site:site + 4] = CORRUPT      # correctly relocated FR pointer
        fixed = patch.patch(rom, source)
        self.assertEqual(bytes(rom[site:site + 4]), CORRUPT)  # untouched
        self.assertEqual(fixed, 0)


if __name__ == "__main__":
    unittest.main()
