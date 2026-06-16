import json
import struct
import unittest
from pathlib import Path

import pytest

from src.core.text_codec import TextEncoder, TextDecoder

EN_EXTRACT = Path('output/extracted/extracted_texts/englishrom_texts.json')
ES_EXTRACT = Path('output/extracted/extracted_texts/spanishrom_texts.json')
EN_ROM = Path('input/roms/englishrom.gba')
ES_ROM = Path('input/roms/spanishrom.gba')
FR_ROM = Path('output/roms/GenedRom-fr.gba')


def _load_texts(path: Path):
    data = json.loads(path.read_text(encoding='utf-8'))
    return data, {item['offset']: item for item in data.get('texts', [])}


def _read_pointer_text(rom_data: bytes, pointer_offset: int, limit: int = 400) -> str:
    if pointer_offset + 4 > len(rom_data):
        return ''
    ptr_value = struct.unpack_from('<I', rom_data, pointer_offset)[0]
    if ptr_value < 0x08000000:
        return ''
    target = ptr_value - 0x08000000
    if target < 0 or target >= len(rom_data):
        return ''
    chunk = rom_data[target:target + limit]
    end = chunk.find(b'\xFF')
    raw = chunk if end == -1 else chunk[:end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


@pytest.mark.rom
class RegressionTextTests(unittest.TestCase):
    @unittest.skipUnless(EN_EXTRACT.exists() and ES_EXTRACT.exists(), 'Extraction JSON missing')
    def test_jacket_and_character_texts_present(self):
        en_data, _ = _load_texts(EN_EXTRACT)
        es_data, _ = _load_texts(ES_EXTRACT)

        if en_data.get('pointer_scan_hits') is None or es_data.get('pointer_scan_hits') is None:
            self.skipTest('Pointer scan not enabled in extraction output')

        def find_text(data, needle):
            for item in data.get('texts', []):
                text = item.get('decoded_text') or item.get('text') or ''
                if needle in text:
                    return item
            return None

        en_character = find_text(en_data, 'Choose a character.')
        en_jacket = find_text(en_data, 'Choose a jacket colour.')
        es_character = find_text(es_data, 'Elige un personaje.')
        es_jacket = find_text(es_data, 'Elige un color de chaqueta.')

        self.assertIsNotNone(en_character, 'Missing English: Choose a character.')
        self.assertIsNotNone(en_jacket, 'Missing English: Choose a jacket colour.')
        self.assertIsNotNone(es_character, 'Missing Spanish: Elige un personaje.')
        self.assertIsNotNone(es_jacket, 'Missing Spanish: Elige un color de chaqueta.')

        for item in (es_character, es_jacket):
            offsets = item.get('pointer_offsets') or item.get('table_offsets')
            self.assertTrue(offsets, 'Expected pointer or table offsets for Spanish text entry')

    @unittest.skipUnless(ES_ROM.exists() and ES_EXTRACT.exists(), 'ROM or extraction missing')
    def test_spanish_rom_has_pointer_to_jacket_text(self):
        es_data, _ = _load_texts(ES_EXTRACT)
        jacket_entry = None
        for item in es_data.get('texts', []):
            text = item.get('decoded_text') or item.get('text') or ''
            if 'Elige un color de chaqueta.' in text:
                jacket_entry = item
                break

        if not jacket_entry:
            self.skipTest('Spanish jacket text not found in extraction')

        offset = jacket_entry['offset']
        ptr_value = 0x08000000 + offset
        needle = struct.pack('<I', ptr_value)
        rom = ES_ROM.read_bytes()
        occurrences = rom.count(needle)

        self.assertGreaterEqual(occurrences, 1, 'Expected at least one pointer to jacket text')

    @unittest.skipUnless(EN_ROM.exists() and ES_ROM.exists(), 'ROMs missing')
    def test_war_continued_inline_text_copied(self):
        phrase = 'The war continued to rage in the'
        encoded = TextEncoder.encode_pokemon(phrase)[:-1]

        english_data = EN_ROM.read_bytes()
        spanish_data = ES_ROM.read_bytes()

        offset = english_data.find(encoded)
        if offset == -1:
            self.skipTest('War intro text not found in English ROM')

        def read_text(data, offset, limit=600):
            chunk = data[offset:offset + limit]
            end = chunk.find(b'\\xFF')
            raw = chunk if end == -1 else chunk[:end + 1]
            return TextDecoder.decode_pokemon(raw, preserve_unknown=True)

        english_text = read_text(english_data, offset)
        spanish_text = read_text(spanish_data, offset)

        output_rom = Path('output/roms/GenedRom-es.gba')
        if not output_rom.exists():
            self.skipTest('Built ROM not found')

        built_text = read_text(output_rom.read_bytes(), offset)

        self.assertNotEqual(english_text, spanish_text, 'Expected ES text to differ from EN')
        self.assertEqual(built_text, spanish_text, 'Built ROM should match Spanish text')

    @unittest.skipUnless(EN_ROM.exists() and FR_ROM.exists(), 'ROMs missing')
    def test_inline_hate_text_translated_in_french(self):
        phrase = 'you can see they hate'
        encoded = TextEncoder.encode_pokemon(phrase)[:-1]

        english_data = EN_ROM.read_bytes()
        french_data = FR_ROM.read_bytes()

        hit = english_data.find(encoded)
        if hit == -1:
            self.skipTest('Inline hate text not found in English ROM')

        start = english_data.rfind(b'\xFF', 0, hit)
        start = 0 if start == -1 else start + 1

        def read_text(data, offset, limit=600):
            chunk = data[offset:offset + limit]
            end = chunk.find(b'\xFF')
            raw = chunk if end == -1 else chunk[:end + 1]
            return TextDecoder.decode_pokemon(raw, preserve_unknown=True)

        english_text = read_text(english_data, start)
        french_text = read_text(french_data, start)

        self.assertNotEqual(english_text, french_text, 'Expected inline text to be translated in FR ROM')

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_battle_sent_out_messages_translated(self):
        french_data = FR_ROM.read_bytes()

        double_text = _read_pointer_text(french_data, 0x009BDE0C)
        self.assertIn('envoient', double_text)
        self.assertNotIn('sent out', double_text)

        single_text = _read_pointer_text(french_data, 0x009BDE14)
        self.assertIn('envoie', single_text)
        self.assertNotIn('sent out', single_text)

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_dynamic_placeholders_resolved(self):
        french_data = FR_ROM.read_bytes()
        text = _read_pointer_text(french_data, 0x00115190)

        self.assertIn('<0xF7>', text)
        self.assertNotIn('DYNAMIC', text)

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_antigel_item_description_cures_freeze(self):
        # Regression: the Antigel (Ice Heal) item description used to point at a
        # Potion-style string ("Un spray qui soigne les blessures. Restaure 20
        # PV...") — text describing a completely different item. It must describe
        # de-freezing, like its sibling status-heal items (Réveil, Anti-Para).
        ITEM_TABLE_BASE = 0x876074
        ITEM_STRIDE = 44
        DESC_PTR_OFF = 0x14
        ANTIGEL_ITEM_ID = 0x19

        french_data = FR_ROM.read_bytes()
        entry_off = ITEM_TABLE_BASE + ANTIGEL_ITEM_ID * ITEM_STRIDE
        text = _read_pointer_text(french_data, entry_off + DESC_PTR_OFF)

        self.assertIn('Décongèle', text)
        self.assertIn('gelé', text)
        # The wrong Potion-style description must be gone.
        self.assertNotIn('Restaure 20', text)
        self.assertNotIn('blessures', text)

    @unittest.skipUnless(EN_ROM.exists() and FR_ROM.exists(), 'ROMs missing')
    def test_inline_my_name_parents_translated(self):
        phrase = "I'm looking for my parents"
        encoded = TextEncoder.encode_pokemon(phrase)[:-1]

        english_data = EN_ROM.read_bytes()
        french_data = FR_ROM.read_bytes()

        def read_text(data, offset, limit=800):
            chunk = data[offset:offset + limit]
            end = chunk.find(b'\xFF')
            raw = chunk if end == -1 else chunk[:end + 1]
            return TextDecoder.decode_pokemon(raw, preserve_unknown=True)

        start = None
        english_text = ''
        search_from = 0
        while True:
            hit = english_data.find(encoded, search_from)
            if hit == -1:
                break
            candidate_start = english_data.rfind(b'\xFF', 0, hit)
            candidate_start = 0 if candidate_start == -1 else candidate_start + 1
            candidate_text = read_text(english_data, candidate_start)
            if phrase in candidate_text:
                start = candidate_start
                english_text = candidate_text
                break
            search_from = hit + 1

        if start is None:
            self.skipTest("Parents inline text not found in English ROM")

        french_text = read_text(french_data, start)

        self.assertIn('parents', english_text)
        self.assertNotIn(phrase, french_text)
        self.assertIn("Je m'appelle", french_text)
        self.assertIn('parents', french_text)

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_repel_descriptions_count_steps_not_stages(self):
        # Repel item descriptions count footsteps ("pas"), not stages ("étapes").
        # Regression for ticket P-37 "Description repousse": the Max Repel desc
        # used to read "...d'apparaître pendant 250 étapes." which is wrong.
        french_data = FR_ROM.read_bytes()
        # Super Repel (200), Max Repel (250), Repel (100) description offsets.
        for offset in (0x3D62DF, 0x3D6318, 0x3D639C):
            end = french_data.find(b'\xFF', offset)
            raw = french_data[offset:end + 1]
            text = TextDecoder.decode_pokemon(raw, preserve_unknown=True)
            self.assertIn('pas', text, f'Repel desc at {offset:#x} should mention "pas"')
            self.assertNotIn('étape', text, f'Repel desc at {offset:#x} must not say "étape(s)"')


if __name__ == '__main__':
    unittest.main()
