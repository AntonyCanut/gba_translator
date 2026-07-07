import unittest

from src.core.dialogue_linewrap import (
    DEFAULT_MAX_LINE_WIDTH,
    _split_words,
    demote_midsentence_pages,
    is_multiline_layout,
    line_width,
    line_widths,
    normalize_breaks,
    rewrap,
    rewrap_multiline,
    rewrap_segment,
)


class SplitWordsQuoteTests(unittest.TestCase):
    """An opening quote must weld to the word it introduces, not the
    previous one — otherwise a re-wrap can orphan it at the end of a line
    (``... choisir «`` ⏎ ``Rejoindre``)."""

    def test_opening_guillemet_glues_to_following_word(self):
        words = _split_words('choisir « Rejoindre Groupe ».')
        self.assertIn('« Rejoindre', words)
        self.assertNotIn('choisir «', words)

    def test_opening_curly_quote_glues_to_following_word(self):
        words = _split_words('a dit “ bonjour ” poliment')
        self.assertNotIn('dit “', words)
        self.assertTrue(
            any(w.startswith('“ bonjour') for w in words),
            f'opening curly quote not welded to its word: {words!r}',
        )

    def test_closing_guillemet_still_glues_to_previous_word(self):
        words = _split_words('« Rejoindre Groupe »')
        self.assertIn('Groupe »', words)

    def test_straight_quote_opening_glues_forward(self):
        # The pipeline stores guillemets as straight quotes; an opening
        # one ("…) is followed by a word, so it welds forward.
        words = _split_words('choisir " Rejoindre Groupe ".')
        self.assertIn('" Rejoindre', words)
        self.assertNotIn('choisir "', words)

    def test_straight_quote_closing_glues_back(self):
        # A standalone straight quote that closes (a word precedes, then
        # punctuation/end) welds back to its word, never orphaned forward.
        words = _split_words('a renvoyé un " OK " !')
        self.assertNotIn('"', words)  # never a bare quote token
        self.assertTrue(
            any(w.startswith('" OK') for w in words),
            f'opening straight quote not welded forward: {words!r}',
        )

    def test_lone_opening_quote_is_kept(self):
        # No following word — the quote is closing here and welds back to
        # the previous word rather than being orphaned or dropped.
        self.assertEqual(_split_words('bonjour «'), ['bonjour «'])


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

    def test_opening_quote_not_orphaned_at_line_end(self):
        # An opening guillemet that the wrapper had glued to the previous
        # word could land alone at the end of a line, with the quoted word
        # on the next line. The quote now travels with the word it opens.
        # Real cases: a guillemet (0x1BD51B) and its pipeline straight-quote
        # form, which is what the build actually re-wraps.
        for text, welded in (
            ('L’autre doit ensuite\nchoisir « Rejoindre Groupe ».', '« Rejoindre'),
            ('L’autre doit ensuite\nchoisir " Rejoindre Groupe ".', '" Rejoindre'),
        ):
            result = rewrap(text)
            for line in result.replace('<0xFA>', '\n').split('\n'):
                self.assertFalse(
                    line.rstrip().endswith(('«', '“', '‹', '"')),
                    f'line ends with an orphaned opening quote: {line!r}',
                )
            self.assertIn(welded, result)

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


class ZeroBreakOverflowTests(unittest.TestCase):
    """A hand-edited correction can arrive with no source ``\n`` at all;
    it must still be wrapped when it overflows the box on its own.
    Regression for the German in-game bug where a long, unbroken
    correction rendered as one overflowing line that visually overlapped
    the next page's text and continue arrow."""

    def test_rewrap_segment_wraps_single_line_overflow(self):
        segment = (
            "Die Macht von Borrius wurde vor sehr langer Zeit versiegelt "
            "und niemand hat sie seither je wieder gesehen."
        )
        result = rewrap_segment(segment)
        self.assertIn('\n', result)
        for width in line_widths(result):
            self.assertLessEqual(width, DEFAULT_MAX_LINE_WIDTH)
        self.assertEqual(result.replace('\n', ' ').split(), segment.split())

    def test_page_with_zero_breaks_no_longer_overflows_into_next_page(self):
        # A <0xFB>-delimited page whose own text has no \n/scroll must
        # still get wrapped, otherwise it overflows onto the box's
        # second line where the next page's text/continue arrow is
        # drawn -- the visual overlap reported in-game.
        text = (
            "Ausgezeichnet. Die Macht von Borrius wurde vor langer Zeit "
            "versiegelt.<0xFB>Man sagt, dass die drei Pokémon wieder "
            "vereint werden."
        )
        result = rewrap(text)
        self.assertIn('<0xFB>', result)
        first_page = result.split('<0xFB>')[0]
        for width in line_widths(first_page):
            self.assertLessEqual(width, DEFAULT_MAX_LINE_WIDTH)
        flat = result.replace('\n', ' ').replace('<0xFA>', ' ').replace('<0xFB>', ' ')
        flat_src = text.replace('<0xFB>', ' ')
        self.assertEqual(flat.split(), flat_src.split())

    def test_short_single_line_still_untouched(self):
        self.assertEqual(rewrap('Salut !'), 'Salut !')

    def test_idempotent(self):
        text = (
            "Die Macht von Borrius wurde vor sehr langer Zeit versiegelt "
            "und niemand hat sie seither je wieder gesehen."
        )
        once = rewrap(text)
        self.assertEqual(rewrap(once), once)


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


class DemoteMidsentencePagesTests(unittest.TestCase):
    """A <0xFB> page clears the screen; doing so mid-sentence is a bug."""

    def test_midsentence_page_becomes_scroll(self):
        # The sentence continues past the page break (next page starts
        # lowercase): clearing the screen here is gratuitous, so the
        # page is demoted to a scroll.
        self.assertEqual(
            demote_midsentence_pages('comment marche<0xFB>le Système.'),
            'comment marche<0xFA>le Système.',
        )

    def test_keeps_page_after_sentence_end(self):
        # "Bon." ends a sentence: the screen clear is a deliberate beat.
        text = 'Bon.<0xFB>On y va ?'
        self.assertEqual(demote_midsentence_pages(text), text)

    def test_keeps_page_before_new_sentence(self):
        # Next page starts with a capital — a fresh utterance or a label
        # (sign, location name): the page stays a hard boundary.
        text = 'Marché du Dresseur<0xFB>PLATEAU INDIGO'
        self.assertEqual(demote_midsentence_pages(text), text)

    def test_keeps_page_ending_with_buffer(self):
        # A trailing runtime buffer completes the utterance dynamically;
        # its content is unknown, so the page is left untouched.
        text = "C'est <0xFD><0x01><0xFB>Voici la suite."
        self.assertEqual(demote_midsentence_pages(text), text)

    def test_demotes_through_trailing_control_codes(self):
        # Colour codes at the page tail must not hide the real last
        # character ("que") from the sentence-boundary test.
        self.assertEqual(
            demote_midsentence_pages('tu veux que<0xFC><0x01><0x02><0xFB>jouer.'),
            'tu veux que<0xFC><0x01><0x02><0xFA>jouer.',
        )

    def test_leading_codes_on_next_page_dont_hide_lowercase(self):
        self.assertEqual(
            demote_midsentence_pages('marche<0xFB><0xFC><0x01><0x02>le jeu.'),
            'marche<0xFA><0xFC><0x01><0x02>le jeu.',
        )

    def test_no_page_untouched(self):
        self.assertEqual(demote_midsentence_pages('A\nB<0xFA>C'), 'A\nB<0xFA>C')

    def test_idempotent(self):
        text = 'comment marche<0xFB>le Système.'
        once = demote_midsentence_pages(text)
        self.assertEqual(demote_midsentence_pages(once), once)

    def test_rewrap_merges_midsentence_page_fluidly(self):
        # End-to-end: a mid-sentence screen clear no longer survives the
        # full rewrap — the continuation flows as a scroll instead.
        text = 'Je vais te montrer comment marche<0xFB>le Système.'
        result = rewrap(text)
        self.assertNotIn('<0xFB>', result)
        # Wording preserved.
        flat = result.replace('\n', ' ').replace('<0xFA>', ' ')
        self.assertEqual(flat.split(), text.replace('<0xFB>', ' ').split())

    def test_rewrap_keeps_paced_page(self):
        # A page after a finished sentence is still a hard boundary.
        result = rewrap('Oui.\nBon.<0xFB>On y va dès maintenant ?')
        self.assertIn('Bon.<0xFB>On', result)


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
