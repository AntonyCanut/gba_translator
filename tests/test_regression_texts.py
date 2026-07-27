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

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_hoopa_dialogues_use_dresseur_and_bouteille_prison(self):
        # Regression (Pattern C): 8fe7dddb0 had silently reverted the
        # reformulation from 9ab2b549c, bringing back franglais "Prison
        # Bottle" and "entraîneur" instead of the canon "Dresseur".
        french_data = FR_ROM.read_bytes()

        aklove_ritual = _read_pointer_text(french_data, 0x7D40BD)
        self.assertIn('Dresseur', aklove_ritual)
        self.assertNotIn('entraîneur', aklove_ritual)
        self.assertNotIn('Prison Bottle', aklove_ritual)
        self.assertIn('Bouteille', aklove_ritual)

        cube_reveal = _read_pointer_text(french_data, 0x1E8C3CE)
        self.assertIn('Dresseur', cube_reveal)
        self.assertNotIn('Prison Bottle', cube_reveal)
        self.assertIn('Bouteille Prison', cube_reveal)

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

    # EN string offset -> expected French floor label (issue #27 / #100).
    # The 15-entry table at 0x41803A-0x418069 (1F..11F then B1F..B4F) is
    # served through *six* duplicate pointer tables. Every French label is
    # longer than its English original, so the build relocates the strings
    # and repoints all six tables; a stale/non-deterministic rebuild used to
    # drop them back to English ("1F") or merge two labels ("RDC1E").
    _FLOOR_LABELS = {
        0x41803A: 'RDC', 0x41803D: '1E', 0x418040: '2E', 0x418043: '3E',
        0x418046: '4E', 0x418049: '5E', 0x41804C: '6E', 0x41804F: '7E',
        0x418052: '8E', 0x418055: '9E', 0x418059: '10E',
        0x41805D: '-1', 0x418061: '-2', 0x418065: '-3', 0x418069: '-4',
    }

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_floor_indicators_translated_fr(self):
        # Fast smoke check on the primary ascending pointer table (0x3F5B44).
        french_data = FR_ROM.read_bytes()

        expected = {
            0x3F5B44: '-4', 0x3F5B48: '-3', 0x3F5B4C: '-2', 0x3F5B50: '-1',
            0x3F5B54: 'RDC', 0x3F5B58: '1E', 0x3F5B5C: '2E', 0x3F5B60: '3E',
            0x3F5B64: '4E', 0x3F5B68: '5E', 0x3F5B6C: '6E', 0x3F5B70: '7E',
            0x3F5B74: '8E', 0x3F5B78: '9E', 0x3F5B7C: '10E',
        }
        for pointer_offset, expected_text in expected.items():
            text = _read_pointer_text(french_data, pointer_offset)
            self.assertEqual(text, expected_text, f'Floor label at pointer {pointer_offset:#x}')

    @unittest.skipUnless(FR_ROM.exists() and EN_ROM.exists(), 'ROM missing')
    def test_floor_indicators_translated_all_pointer_tables(self):
        # Issue #100 regression: the floor popup regressed to English in a
        # shipped build. The single-table check above missed it because the
        # floor strings are reached by SIX duplicate pointer tables — a build
        # could repoint one while dropping another. This walks every pointer in
        # the EN ROM that targets the floor table and asserts the FR ROM's
        # matching pointer resolves to the exact French label (no English
        # residue like "1F", no merged label like "RDC1E").
        english_data = EN_ROM.read_bytes()
        french_data = FR_ROM.read_bytes()

        floor_offsets = set(self._FLOOR_LABELS)
        slots = []
        for slot in range(0, len(english_data) - 4, 2):
            ptr = struct.unpack_from('<I', english_data, slot)[0]
            if ptr >= 0x08000000 and (ptr - 0x08000000) in floor_offsets:
                slots.append((slot, self._FLOOR_LABELS[ptr - 0x08000000]))

        # Sanity: the six duplicate tables reference all 15 labels many times.
        self.assertGreaterEqual(len(slots), 15 * 2, 'Floor pointer tables not found in EN ROM')

        for slot, expected_text in slots:
            text = _read_pointer_text(french_data, slot)
            self.assertEqual(
                text, expected_text,
                f'Floor label via EN pointer {slot:#x} should be {expected_text!r}, '
                f'got {text!r} (English residue or merged label = build regression).',
            )

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_camper_chad_kelsey_line_translated(self):
        # Issue #28 "Traduction dresseur Camper Chad": the double-battle
        # partner refusal line ("Drat!\nKelsey took up my second slot!") shipped
        # in English. Community-agreed FR text: "Zut !\nKelsey a pris ma place !"
        french_data = FR_ROM.read_bytes()
        for pointer_offset in (0x1E8728B, 0x1E872C6, 0x1E872F5, 0x1E87330):
            text = _read_pointer_text(french_data, pointer_offset)
            self.assertIn('Zut', text)
            self.assertIn('Kelsey a pris ma place', text)
            self.assertNotIn('Drat', text)
            self.assertNotIn('second slot', text)

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_item_pickup_message_uses_present_tense(self):
        # Issue #64 "Formulation objet ramassé": the pickup message read
        # "{PLAYER} a rangé {OBJET} dans la Zone Objets." (passé composé).
        # Official games use the present tense: "{PLAYER} range {OBJET}...".
        french_data = FR_ROM.read_bytes()

        # Generic item pickup template ("... range OBJET dans la POCHE.").
        item_text = _read_pointer_text(french_data, 0x001A6752)
        self.assertIn('range', item_text)
        self.assertNotIn('a rangé', item_text)

        # Coin Case pickup template ("... range les Jetons dans la Boîte Jetons.").
        coins_text = _read_pointer_text(french_data, 0x001A690C)
        self.assertIn('range les Jetons', coins_text)
        self.assertNotIn('a rangé', coins_text)

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_camper_trainer_class_translated_everywhere(self):
        # Issue #28: every appearance of the trainer class "Camper" must read
        # "Campeur" — the fixed-width class-name table cell and the two
        # standalone dialogue/description mentions of the class noun.
        french_data = FR_ROM.read_bytes()

        CLASS_TABLE_OFFSET = 0x23E871
        end = french_data.find(b'\xFF', CLASS_TABLE_OFFSET)
        class_name = TextDecoder.decode_pokemon(french_data[CLASS_TABLE_OFFSET:end + 1], preserve_unknown=True)
        self.assertEqual(class_name, 'Campeur')

        for pointer_offset in (0xA6F680, 0x1E80654):
            text = _read_pointer_text(french_data, pointer_offset)
            self.assertIn('Campeur', text)
            self.assertNotIn('Camper', text)

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_options_exit_choice_box_has_three_choices(self):
        # Issue #70 "Boite de choix sortie options": the FR translation had
        # collapsed the 3-entry multichoice list (EN "Save\nDiscard\nCancel",
        # offset 0x1F4E230) into a single run-on sentence, so the list only
        # ever showed one truncated, overlapping choice instead of three.
        french_data = FR_ROM.read_bytes()

        text = _read_pointer_text(french_data, 0x1EBD77C)
        self.assertEqual(text.count('\n'), 2, f'Expected 3 choices, got: {text!r}')
        choices = text.split('\n')
        self.assertEqual(len(choices), 3)
        for choice in choices:
            self.assertTrue(choice, 'Choice entries must not be empty')
        self.assertNotIn('abandonner ?', text)

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_options_exit_choice_box_uses_semantic_colors(self):
        # Issue #144: Save must be green, Discard red, and Cancel must restore
        # the normal black text colour instead of inheriting red.
        french_data = FR_ROM.read_bytes()
        pointer_offset = 0x1EBD77C
        target = struct.unpack_from('<I', french_data, pointer_offset)[0] - 0x08000000
        end = french_data.index(b'\xFF', target)
        raw = french_data[target:end + 1]

        expected = (
            b'\xFC\x01\x06' + TextEncoder.encode_pokemon('Sauver')[:-1]
            + b'\xFE\xFC\x01\x04' + TextEncoder.encode_pokemon('Ignorer')[:-1]
            + b'\xFE\xFC\x01\x02' + TextEncoder.encode_pokemon('Annuler')
        )
        self.assertEqual(raw, expected)

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_options_exit_help_text_uses_semantic_colors(self):
        # Issue #144 follow-up: the explanatory text below the choices uses a
        # distinct string and must colour only "Sauver" and "Ignorer".
        french_data = FR_ROM.read_bytes()
        pointer_offset = 0x1EBD064
        target = struct.unpack_from('<I', french_data, pointer_offset)[0] - 0x08000000
        end = french_data.index(b'\xFF', target)
        raw = french_data[target:end + 1]

        expected = (
            b'\xFC\x01\x06' + TextEncoder.encode_pokemon('Sauver')[:-1]
            + b'\xFC\x01\x02' + TextEncoder.encode_pokemon(' ou ')[:-1]
            + b'\xFC\x01\x04' + TextEncoder.encode_pokemon('ignorer')[:-1]
            + b'\xFC\x01\x02'
            + TextEncoder.encode_pokemon(' les options sélectionnées ?')
        )
        self.assertEqual(raw, expected)

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_battle_style_options_translated(self):
        # Issue #73 "Mode de combat - menu Options": the battle-style cycle
        # ("Shift"/"Set" at 0x419E2C/0x419E32) had "Changer" for Shift (renamed
        # to "Choix") and left "Set" fully untranslated. "Set" only fits its
        # cell via pointer relocation (its in-place budget is the 3-byte EN
        # length "Set", too tight for "Défini").
        french_data = FR_ROM.read_bytes()

        SHIFT_OFFSET = 0x419E2C
        end = french_data.find(b'\xFF', SHIFT_OFFSET)
        shift_text = TextDecoder.decode_pokemon(french_data[SHIFT_OFFSET:end + 1], preserve_unknown=True)
        self.assertEqual(shift_text, 'Choix')

        set_text = _read_pointer_text(french_data, 0x003CC348)
        self.assertEqual(set_text, 'Défini')
        self.assertNotEqual(set_text, 'Set')

    @unittest.skipUnless(FR_ROM.exists(), 'ROM missing')
    def test_semi_shift_description_translated(self):
        # Issue #73: the Semi-Shift battle-style description (0x1F4E012, EN
        # "Get nameless free switch after a KO.") read as a confusing run-on
        # sentence ("Change gratuitement et sans nom après K.O.") that the
        # reporter could not parse. Rewritten to fit the fixed 36-byte cell
        # budget while staying legible.
        french_data = FR_ROM.read_bytes()

        DESC_OFFSET = 0x1F4E012
        end = french_data.find(b'\xFF', DESC_OFFSET)
        desc_text = TextDecoder.decode_pokemon(french_data[DESC_OFFSET:end + 1], preserve_unknown=True)
        self.assertEqual(desc_text, 'Change gratuit après K.O. sans nom.')
        self.assertNotIn('nameless', desc_text)


if __name__ == '__main__':
    unittest.main()
