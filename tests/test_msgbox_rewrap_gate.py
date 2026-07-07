"""The dialogue re-wrap must not depend on the fuzzy content category.

``categorize_text`` tags message-box prose without ``!``/``?``/pronouns as
"description" (anything longer than 30 chars), so those entries skipped the
dialogue re-wrap and shipped with English break positions: a longer French/
Italian/German line then runs past the box edge and is clipped mid-word
(ticket example: 0x1F099C2, "Beaucoup viennent à Rivapolis juste p…").

Scroll (<0xFA>) / page (<0xFB>) codes in the English source are structural
proof of a scrolling message box, so the builder re-wraps those entries no
matter their category.
"""

import importlib
import unittest

from src.core.dialogue_linewrap import DEFAULT_MAX_LINE_WIDTH, line_widths

builder_module = importlib.import_module('src.translators.19_build_translated_rom_generic')
TranslatedROMBuilder = builder_module.TranslatedROMBuilder


def _bare_builder():
    builder = TranslatedROMBuilder.__new__(TranslatedROMBuilder)
    builder.english_texts = None
    return builder


class MsgboxRewrapGateTests(unittest.TestCase):
    # Real FR pipeline entry (offset 0x1F099C2, Inverse Trainer House sign):
    # tagged "description" by the heuristic, yet the English source scrolls.
    ENGLISH = (
        'The <0xFC><0x01><0x06>Inverse Trainer House<0xFC><0x01><0x08>\n'
        'is famous.<0xFB>Many people come to Fallshore\n'
        'City just to battle with type<0xFA>matchups reversed.'
    )
    FRENCH = (
        'La <0xFC><0x01><0x06>Maison des Combats Inversés<0xFC><0x01><0x08>\n'
        'est célèbre.<0xFB>Beaucoup viennent à Rivapolis juste '
        'pour combattre avec<0xFA>les types inversés.'
    )

    def _normalize(self, category, english, translation):
        item = {
            'translation': translation,
            'original_text': english,
            'encoding': 'pokemon',
            'category': category,
        }
        return _bare_builder()._normalize_translation_item(0x1F099C2, item)

    def test_misclassified_msgbox_text_is_rewrapped(self):
        normalized = self._normalize('description', self.ENGLISH, self.FRENCH)
        rewrapped = normalized['translation']
        self.assertNotEqual(rewrapped, self.FRENCH)
        for width in line_widths(rewrapped):
            self.assertLessEqual(width, DEFAULT_MAX_LINE_WIDTH)
        # The wording and the page structure are untouched.
        flatten = lambda text: ' '.join(
            text.replace('<0xFA>', ' ').replace('\n', ' ').split()
        )
        self.assertEqual(flatten(rewrapped), flatten(self.FRENCH))
        self.assertEqual(rewrapped.count('<0xFB>'), 1)

    def test_break_rule_normalized_for_misclassified_entry(self):
        # Stacked \n after the box is full draw lines over each other; the
        # re-wrap must demote every break after the first one to a scroll.
        english = (
            'The first line of the message.\n'
            'The second line of the message.<0xFA>'
            'The third line of the message.'
        )
        translation = (
            'La première ligne du message de la boîte.\n'
            'La deuxième ligne du message de la boîte.\n'
            'La troisième ligne du message de la boîte.'
        )
        normalized = self._normalize('other', english, translation)
        page = normalized['translation']
        first_break = page.index('\n')
        self.assertNotIn('\n', page[first_break + 1:])
        self.assertIn('<0xFA>', page)
        for width in line_widths(page):
            self.assertLessEqual(width, DEFAULT_MAX_LINE_WIDTH)

    def test_junction_sign_list_layout_is_never_reflowed(self):
        # Junction signposts lay out one destination per line, arrow glyph
        # first. Re-flowing would weld destinations together and strand
        # arrows mid-line ("<0x7B> Automnia <0x79> Chenal Aubrun <0x7C>\n
        # Rivapolis") — the line structure must survive the msgbox gate.
        english = (
            'Route 10<0xFB><0x7B> Tehl Town\n'
            '<0x79> Auburn Waterway<0xFA><0x7C> Fallshore City'
        )
        translation = (
            'Route 10<0xFB><0x7B> Automnia\n'
            '<0x79> Chenal Aubrun<0xFA><0x7C> Rivapolis'
        )
        normalized = self._normalize('description', english, translation)
        self.assertEqual(normalized['translation'], translation)

    def test_list_layout_still_gets_break_types_normalized(self):
        # Stacked \n in a signpost list would overdraw the box; the lines
        # must stay verbatim but the breaks after the first become scrolls.
        english = 'Sign<0xFB><0x7B> One\n<0x79> Two<0xFA><0x7C> Three'
        translation = 'Panneau<0xFB><0x7B> Un\n<0x79> Deux\n<0x7C> Trois'
        normalized = self._normalize('description', english, translation)
        self.assertEqual(
            normalized['translation'],
            'Panneau<0xFB><0x7B> Un\n<0x79> Deux<0xFA><0x7C> Trois',
        )

    def test_pure_newline_description_stays_untouched(self):
        # No scroll/page code in the English source: a fixed window (item
        # description, sign, fullscreen text) — the gate must not touch it.
        english = 'A rare candy that raises the\nlevel of a Pokémon by one.'
        translation = "Un bonbon rare qui monte le\nniveau d'un Pokémon d'un cran."
        normalized = self._normalize('description', english, translation)
        self.assertEqual(normalized['translation'], translation)


if __name__ == '__main__':
    unittest.main()
