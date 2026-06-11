import unittest

from src.core.dialogue_linewrap import (
    DEFAULT_MAX_LINE_WIDTH,
    is_multiline_layout,
    line_width,
    line_widths,
    normalize_breaks,
    rewrap,
    rewrap_multiline,
)


class NormalizeBreaksTests(unittest.TestCase):
    def test_first_break_stays_newline(self):
        self.assertEqual(normalize_breaks('A\nB'), 'A\nB')

    def test_extra_newline_becomes_scroll(self):
        self.assertEqual(normalize_breaks('A\nB\nC'), 'A\nB<0xFA>C')

    def test_newline_after_scroll_becomes_scroll(self):
        self.assertEqual(
            normalize_breaks('A\nB<0xFA>C\nD'),
            'A\nB<0xFA>C<0xFA>D',
        )

    def test_page_resets_the_box(self):
        self.assertEqual(
            normalize_breaks('A\nB\nC<0xFB>D\nE'),
            'A\nB<0xFA>C<0xFB>D\nE',
        )

    def test_idempotent(self):
        text = 'A\nB\nC<0xFA>D\nE<0xFB>F\nG'
        once = normalize_breaks(text)
        self.assertEqual(normalize_breaks(once), once)


class RewrapTests(unittest.TestCase):
    def test_merges_short_dialogue_onto_one_line(self):
        # The in-game string showed "Et" alone on the first line; the
        # whole sentence fits the box, so it now reads on a single line.
        result = rewrap("Et\nenfin, comment t'appelles-tu ?")
        self.assertEqual(result, "Et enfin, comment t'appelles-tu ?")

    def test_merges_inherited_break_with_codes(self):
        # "Non ! Mon\nSepiatop !" inherited the English break and read
        # as an incoherent mid-sentence cut.
        result = rewrap('Sbire : <0xFC><0x01><0x08>Non ! Mon Sepiatop\n!')
        self.assertEqual(
            result, 'Sbire : <0xFC><0x01><0x08>Non ! Mon Sepiatop !'
        )

    def test_keeps_two_lines_when_one_does_not_fit(self):
        text = "Maintenant,\nvoyons la meilleure façon de jouer."
        result = rewrap(text)
        self.assertEqual(result.count('\n'), 1)
        for width in line_widths(result):
            self.assertLessEqual(width, DEFAULT_MAX_LINE_WIDTH)

    def test_fills_lines_to_the_edge(self):
        # "Très captivant, si je / puis me permettre." broke at half the
        # box; no line may break while the next word still fits on it.
        result = rewrap("Très captivant, si je\npuis me permettre.")
        lines = result.replace('<0xFA>', '\n').split('\n')
        self.assertGreater(len(lines), 1)
        from src.core.dialogue_linewrap import line_width, word_width, SPACE_WIDTH
        for current, following in zip(lines, lines[1:]):
            first_next = following.split(' ')[0]
            self.assertGreater(
                line_width(current) + SPACE_WIDTH + word_width(first_next),
                DEFAULT_MAX_LINE_WIDTH,
                f'line {current!r} broke early: {first_next!r} still fits',
            )

    def test_fills_across_inherited_scroll(self):
        # In-game: "comme le type Fée" / "faible au Poison ?" both sat at
        # half the box width because the inherited <0xFA> was treated as
        # a hard boundary. Scroll positions are mechanical (the box shows
        # two lines); words must flow across them so every line fills to
        # the edge, like in a plain two-line dialogue.
        from src.core.dialogue_linewrap import SPACE_WIDTH, word_width
        text = (
            'Connais-tu les\nfaiblesses types, comme le type Fée'
            '<0xFA>faible au Poison ?'
        )
        result = rewrap(text)
        lines = result.replace('<0xFA>', '\n').split('\n')
        for current, following in zip(lines, lines[1:]):
            first_next = following.split(' ')[0]
            self.assertGreater(
                line_width(current) + SPACE_WIDTH + word_width(first_next),
                DEFAULT_MAX_LINE_WIDTH,
                f'line {current!r} broke early: {first_next!r} still fits',
            )

    def test_page_break_is_a_hard_boundary(self):
        # <0xFB> pauses and clears the window: words must never flow
        # across it, even when the page before it is nearly empty.
        result = rewrap('Oui.\nBon.<0xFB>On y va dès maintenant ?')
        self.assertIn('Bon.<0xFB>On', result)

    def test_buffer_page_keeps_scroll_boundaries(self):
        # A page with a runtime buffer keeps its conservative per-scroll
        # layout: the buffer may render wider than estimated, so words
        # must not be pulled across its scroll boundary.
        text = (
            'Le <0xFD><0x01> attaque\nsans attendre !'
            '<0xFA>Que faire ?'
        )
        result = rewrap(text)
        self.assertIn('!<0xFA>Que faire ?', result)

    def test_reduces_three_lines_to_fewest(self):
        # Three inherited breaks, content fits two lines: the extra
        # scroll disappears with the merge.
        text = "C'est\nta première partie sur\nPokémon Unbound ?"
        result = rewrap(text)
        self.assertEqual(result.count('\n') + result.count('<0xFA>'), 1)
        for width in line_widths(result):
            self.assertLessEqual(width, DEFAULT_MAX_LINE_WIDTH)

    def test_preserves_words_and_codes(self):
        text = "Maintenant,\nvoyons la meilleure façon de jouer.<0xFB>C'est ta première\npartie sur Pokémon Unbound ?"
        result = rewrap(text)
        self.assertIn('<0xFB>', result)
        # Same words, only break positions change.
        flat = result.replace('\n', ' ').replace('<0xFB>', ' ')
        flat_src = text.replace('\n', ' ').replace('<0xFB>', ' ')
        self.assertEqual(flat.split(), flat_src.split())
        for width in line_widths(result):
            self.assertLessEqual(width, DEFAULT_MAX_LINE_WIDTH)

    def test_buffer_heavy_line_spills_to_scroll(self):
        # "joined the party" string: the first line overflowed with a
        # long player name; extra lines must scroll, never draw below
        # the two-line box.
        text = (
            "Le <0xFC><0x01><0x06><0xFD><0x02><0xFC><0x01><0x02> a rejoint "
            "l'équipe de <0xFD><0x01> !\n"
            "Il a la nature <0xFC><0x01><0x06><0xFD><0x03><0xFC><0x01><0x02>."
        )
        result = rewrap(text)
        for width in line_widths(result):
            self.assertLessEqual(width, DEFAULT_MAX_LINE_WIDTH)
        # One \n then scrolls (Gen III rule).
        first_newline = result.find('\n')
        self.assertGreater(first_newline, 0)
        self.assertNotIn('\n', result[first_newline + 1:])

    def test_spaced_punctuation_never_starts_a_line(self):
        # French detached punctuation (« : », « ! », « ? ») is glued to
        # the previous word: a break may not orphan it at line start.
        result = rewrap('Il me faut :\n<0xFC><0x01><0x06><0xFD><0x02>')
        for line in result.replace('<0xFA>', '\n').split('\n'):
            self.assertFalse(
                line.startswith((':', '!', '?')),
                f'line starts with detached punctuation: {line!r}',
            )
        self.assertIn('faut :', result)

    def test_untouched_without_breaks(self):
        self.assertEqual(rewrap('PARLER'), 'PARLER')

    def test_untouched_when_one_word_per_line(self):
        self.assertEqual(rewrap('MENU\nOPTION'), 'MENU\nOPTION')

    def test_idempotent(self):
        text = "Et\nenfin, comment t'appelles-tu ?"
        once = rewrap(text)
        self.assertEqual(rewrap(once), once)


INTRO_EN = (
    'Welcome to Pokémon Unbound!\n\n'
    'Before you begin playing, please\n'
    'be aware that this is a non-profit\n'
    'fan game.\n\n'
    'If you paid for this game, reclaim\n'
    'your money immediately!'
)

CREDITS_EN = '\n\n Skeli\n Lich-Lord-F\n Criminon\n\n'


class MultilineLayoutTests(unittest.TestCase):
    def test_intro_is_multiline(self):
        self.assertTrue(is_multiline_layout(INTRO_EN))

    def test_credits_are_multiline(self):
        self.assertTrue(is_multiline_layout(CREDITS_EN))

    def test_two_line_dialogue_is_not(self):
        self.assertFalse(is_multiline_layout('Hello!\nHow are you?'))

    def test_scroll_code_means_dialogue(self):
        self.assertFalse(
            is_multiline_layout('a\nb<0xFA>c\nd<0xFB>e\nf')
        )


class RewrapMultilineTests(unittest.TestCase):
    def test_never_introduces_scroll_codes(self):
        fr = (
            "Bienvenue\ndans\nPokémon\nUnbound\n! Avant de jouer,\n"
            "sache que c'est un jeu de fans sans\nbut lucratif."
        )
        result = rewrap_multiline(fr, INTRO_EN)
        self.assertNotIn('<0xFA>', result)
        self.assertNotIn('<0xFB>', result)

    def test_preserves_blank_line_runs(self):
        fr = 'Bienvenue dans Pokémon Unbound !\n\nUn jeu de fans.\n\nMerci !'
        self.assertEqual(rewrap_multiline(fr, INTRO_EN), fr)

    def test_credits_layout_untouched(self):
        # Names and their centring blanks/indent must stay verbatim.
        self.assertEqual(rewrap_multiline(CREDITS_EN, CREDITS_EN), CREDITS_EN)

    def test_overflowing_line_is_rebalanced_within_reference_width(self):
        en = 'Speak to people, and check things\nwherever you go, be it towns,\nroads, or caves.'
        cap = max(line_width(line) for line in en.split('\n'))
        fr = 'Parle aux gens et examine absolument tout ce qui se trouve sur ton chemin,\nvilles, routes\nou grottes.'
        result = rewrap_multiline(fr, en)
        self.assertNotIn('<0xFA>', result)
        for line in result.split('\n'):
            self.assertLessEqual(line_width(line), cap)
        # Wording is preserved.
        self.assertEqual(
            result.replace('\n', ' ').split(),
            fr.replace('\n', ' ').split(),
        )

    def test_idempotent(self):
        fr = 'Un texte avec une ligne vraiment beaucoup trop longue pour la fenêtre,\npuis la suite.'
        once = rewrap_multiline(fr, INTRO_EN)
        self.assertEqual(rewrap_multiline(once, INTRO_EN), once)


if __name__ == '__main__':
    unittest.main()


class CollapseEmptyBreaksTests(unittest.TestCase):
    def test_double_scroll_collapses_to_strongest(self):
        from src.core.dialogue_linewrap import rewrap
        text = (
            "Un roux a surgi et a mis K.O. mes\n"
            "Pokémon avant que je réagisse !<0xFA><0xFA><0xFB>"
            "Je ne peux meme plus\nt'empecher de t'échapper..."
        )
        result = rewrap(text)
        self.assertNotIn('<0xFA><0xFA>', result)
        self.assertIn('réagisse !<0xFB>', result)

    def test_newline_scroll_run_keeps_scroll(self):
        from src.core.dialogue_linewrap import collapse_empty_breaks
        self.assertEqual(collapse_empty_breaks('x\n<0xFA>y'), 'x<0xFA>y')

    def test_trailing_run_collapses_to_one(self):
        from src.core.dialogue_linewrap import collapse_empty_breaks
        self.assertEqual(
            collapse_empty_breaks('fin<0xFA><0xFA>'), 'fin<0xFA>'
        )

    def test_single_breaks_untouched(self):
        from src.core.dialogue_linewrap import collapse_empty_breaks
        text = 'a\nb<0xFA>c<0xFB>d'
        self.assertEqual(collapse_empty_breaks(text), text)


class ElidedPronounBufferTests(unittest.TestCase):
    """qu'<0xFD><0xNN> holds "il"/"elle": narrow width, greedy-eligible."""

    def test_elided_buffer_uses_pronoun_width(self):
        from src.core.dialogue_linewrap import (
            PRONOUN_WIDTH, VARIABLE_WIDTH, word_width,
        )
        self.assertEqual(
            word_width("qu'<0xFD><0x03>"),
            word_width("qu'") + PRONOUN_WIDTH,
        )
        self.assertEqual(
            word_width('<0xFD><0x03>'),
            VARIABLE_WIDTH,
        )

    def test_unelided_buffer_page_keeps_scroll_positions(self):
        text = (
            'Le <0xFD><0x02> a fait savoir que\n'
            '<0xFD><0x03> est impressionné par toi.'
        )
        result = rewrap(text)
        # Wide name buffers present: the page must not collapse onto a
        # single packed line (54px estimates keep it conservative).
        self.assertGreaterEqual(
            result.count('\n') + result.count('<0xFA>'), 1
        )

    def test_elided_pronoun_page_flows_greedily(self):
        # Only elided pronoun buffers: the page re-flows greedily across
        # the inherited break instead of keeping short half-lines.
        text = "On sait\nqu'<0xFD><0x03> arrive."
        result = rewrap(text)
        self.assertEqual(result, "On sait qu'<0xFD><0x03> arrive.")

    def test_mixed_buffers_stay_conservative(self):
        text = "<0xFD><0x02> sait\nqu'<0xFD><0x03> arrive bientôt ici."
        result = rewrap(text)
        # A wide buffer shares the page: source line count is kept.
        self.assertEqual(result.count('\n'), 1)
