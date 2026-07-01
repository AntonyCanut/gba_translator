"""Relocation must be deterministic and independent of input ordering.

A no-change rebuild used to drift ~0.2 % of the ROM because relocated strings
were placed in *input order* among equal-length entries: the translation JSON
can be regenerated through different paths (CSV pipeline vs ``prepare_fr_json``)
that emit the same entries in a different sequence, and that reshuffled the
free-space packing and every repointed pointer. Sorting the relocation queue by
a *total* key (length, bytes, source offset) makes the layout canonical, so the
same set of translations always produces the same bytes regardless of order.
"""

import struct
import unittest

from src.core.text_codec import TextEncoder
from src.core.text_reinserter import SmartReinserter


def _build_rom_and_translations():
    """A ROM with a large free run plus several relocate-needing strings,
    including entries that encode to the *same length* (the case whose tie was
    previously broken by input order)."""
    rom = bytearray([0xAB] * 0x400) + bytearray(b'\xff' * 0x8000) + bytearray([0xAB] * 0x400)

    # Each entry: (pointer_offset, original_string, french_overflowing_string).
    # The originals live early in the data area; the FR text is longer so every
    # entry must relocate into the free run.
    specs = [
        (0x10, 'Hi', 'Bonjour tout le monde'),
        (0x20, 'Yo', 'Salut a tous les amis'),     # same FR length as above
        (0x30, 'No', 'Court'),
        (0x40, 'Ok', 'Texte de longueur moyenne'),
        (0x50, 'Go', 'Encore un texte plus long que loriginal'),
        (0x60, 'Up', 'Court'),                       # duplicate of 0x30's FR text
        (0x70, 'Me', 'Texte de longueur moyenne X'),
        (0x80, 'We', 'Salut a tous les copains'),    # same FR length as 0x10/0x20
    ]
    translations = []
    for ptr_off, en, fr in specs:
        original = TextEncoder.encode_pokemon(en)
        str_off = ptr_off + 0x100  # store the original string in the data area
        rom[str_off:str_off + len(original)] = original
        rom[ptr_off:ptr_off + 4] = struct.pack('<I', 0x08000000 + str_off)
        translations.append({
            'offset': str_off,
            'translation': fr,
            'encoding': 'pokemon',
            'original_length': len(en),
            'padding_available': 0,
            'pointer_offsets': [ptr_off],
        })
    return rom, translations


class RelocationDeterminismTests(unittest.TestCase):
    def _run(self, translations):
        rom, base = _build_rom_and_translations()
        # Re-key the supplied (possibly reordered) translation list onto a fresh
        # ROM so each run starts from the identical initial state.
        reinserter = SmartReinserter(rom, allow_relocate=True)
        for t in translations:
            reinserter.reinsert_text(t)
        reinserter.flush_relocations()
        return bytes(rom)

    def test_relocation_is_independent_of_input_order(self):
        _, translations = _build_rom_and_translations()
        forward = self._run(list(translations))
        reverse = self._run(list(reversed(translations)))
        shuffled = self._run([translations[i] for i in (3, 0, 7, 1, 5, 2, 6, 4)])

        self.assertEqual(
            forward, reverse,
            'reversed input order produced a different ROM — relocation layout '
            'depends on input order',
        )
        self.assertEqual(
            forward, shuffled,
            'shuffled input order produced a different ROM — relocation layout '
            'depends on input order',
        )

    def test_relocation_is_repeatable(self):
        _, translations = _build_rom_and_translations()
        self.assertEqual(self._run(list(translations)), self._run(list(translations)))


if __name__ == '__main__':
    unittest.main()
