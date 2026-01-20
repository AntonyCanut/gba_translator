#!/usr/bin/env python3
"""
Text Validator - Validation et filtrage des textes

Fournit des utilitaires pour valider et filtrer les textes,
notamment pour détecter les données corrompues ou invalides.
"""

from typing import Tuple


class TextValidator:
    """
    Validation et filtrage des textes extraits de ROM.

    Détecte:
    - Données corrompues
    - Caractères invalides
    - Textes non décodables
    - Faux positifs
    """

    # Caractères suspects qui indiquent souvent des données corrompues
    SUSPICIOUS_CHARS = {'?', '\x00', '\xff', '\xfe', '\xfd'}

    # Caractères répétitifs suspects (souvent données binaires/test)
    TEST_DATA_CHARS = {'f', 'p', 'w', 'z', 'v', '&', '"', 'A', 'R', 'D'}

    # Seuil de caractères suspects pour considérer le texte comme corrompu
    SUSPICIOUS_THRESHOLD = 0.5  # 50% ou plus de caractères suspects

    # Seuil pour données de test (caractères répétitifs)
    TEST_DATA_THRESHOLD = 0.7  # 70% ou plus de caractères répétitifs

    # Longueur minimum pour un texte valide
    MIN_VALID_LENGTH = 1

    # Longueur maximum réaliste pour un texte de jeu Pokemon
    MAX_REALISTIC_LENGTH = 150  # Les dialogues ne dépassent pas ~150 caractères

    @staticmethod
    def is_corrupted(text: str) -> Tuple[bool, str]:
        """
        Vérifie si un texte contient des données corrompues.

        Args:
            text: Texte à vérifier

        Returns:
            Tuple[bool, str]: (is_corrupted, reason)
        """
        if not text:
            return True, "empty_text"

        # Compter caractères suspects
        suspicious_count = sum(1 for c in text if c in TextValidator.SUSPICIOUS_CHARS)
        suspicious_ratio = suspicious_count / len(text)

        # Trop de caractères suspects
        if suspicious_ratio >= TextValidator.SUSPICIOUS_THRESHOLD:
            return True, f"high_suspicious_ratio_{suspicious_ratio:.1%}"

        # Longueur irréaliste
        if len(text) > TextValidator.MAX_REALISTIC_LENGTH:
            return True, f"unrealistic_length_{len(text)}"

        # Patterns spécifiques de corruption
        # Exemple: "????????????????????????..." (beaucoup de ? consécutifs)
        if '????????' in text:
            return True, "repeated_question_marks"

        # Texte ne contenant QUE des caractères non-ASCII suspects
        # (sauf espaces, newlines, et caractères Pokemon valides)
        # Compter les caractères imprimables Unicode (accepte accents, ¡, ¿, etc.)
        printable_count = sum(1 for c in text if c.isprintable() and ord(c) >= 32)
        if len(text) > 5 and printable_count == 0:
            return True, "no_printable_characters"

        # Détecter données de test (beaucoup de caractères répétitifs)
        # Exemples: "fffffffff", "wwwwwww", "&&&&", etc.
        test_data_count = sum(1 for c in text if c in TextValidator.TEST_DATA_CHARS or c == ' ')
        test_data_ratio = test_data_count / len(text) if len(text) > 0 else 0

        if len(text) > 10 and test_data_ratio >= TextValidator.TEST_DATA_THRESHOLD:
            # Vérifier si c'est vraiment répétitif (pas juste par hasard)
            unique_chars = len(set(text.replace(' ', '').replace('?', '')))
            if unique_chars <= 5:  # Très peu de caractères uniques
                return True, f"test_data_pattern_{unique_chars}_unique_chars"

        # Détecter patterns binaires mal décodés
        # Exemples: "p??qp??qp??q", "&\"f&?&fbb", etc.
        if len(text) > 5:
            # Compter les séquences suspectes (char + ??)
            suspicious_patterns = ['??', '?&', '?\"', '?f', '?p', '?w']
            pattern_count = sum(text.count(p) for p in suspicious_patterns)
            if pattern_count >= 3:  # 3+ patterns suspects
                return True, f"binary_pattern_{pattern_count}_occurrences"

        return False, ""

    @staticmethod
    def is_valid_game_text(text: str, encoding: str = 'ascii') -> Tuple[bool, str]:
        """
        Vérifie si un texte est un texte de jeu valide.

        Args:
            text: Texte à vérifier
            encoding: Encodage du texte

        Returns:
            Tuple[bool, str]: (is_valid, reason)
        """
        # Vérifier corruption
        is_corrupt, reason = TextValidator.is_corrupted(text)
        if is_corrupt:
            return False, f"corrupted_{reason}"

        # Vérifier longueur
        if len(text) < TextValidator.MIN_VALID_LENGTH:
            return False, "too_short"

        # Vérifier que le texte contient au moins QUELQUES caractères normaux
        # (lettres, chiffres, ponctuation standard)
        normal_chars = sum(1 for c in text if c.isalnum() or c in ' .,!?-\'\"')
        if len(text) > 3 and normal_chars < 2:
            return False, "no_normal_characters"

        # Vérifier qu'il n'y a pas trop de caractères étranges consécutifs
        # Exemple: "p??qp??qp??q" (pattern binaire)
        strange_pairs = 0
        for i in range(len(text) - 1):
            if text[i] in ['?', '&', '\\'] and text[i+1] in ['?', '&', '\\', '"']:
                strange_pairs += 1

        if len(text) > 5 and strange_pairs >= len(text) * 0.3:  # 30%+ de pairs étranges
            return False, "too_many_strange_pairs"

        # Détecter patterns spécifiques de données binaires/debug
        # Exemples: "?5p", "??1", "??V", "?! " ?5p", etc.
        if '?' in text and len(text) >= 4:
            # Compter les "?" suivis de caractères isolés non-alphabétiques normaux
            weird_char_count = 0
            for i in range(len(text) - 1):
                if text[i] == '?':
                    next_char = text[i+1]
                    # Caractères suspects après ?
                    if next_char in ['!', '"', '5', '1', '\\', 'V', 'p'] or next_char.isdigit():
                        weird_char_count += 1

            # Si plus de 30% du texte contient ces patterns
            if weird_char_count >= len(text) * 0.2:  # 20%+
                return False, "binary_debug_pattern"

        # Détecter patterns type "6 v 6/Est?ndar" qui pourraient être valides MAIS
        # si le texte anglais est simple et court, c'est suspect
        # (Ce cas spécifique sera géré dans should_skip_test avec ratio)

        return True, ""

    @staticmethod
    def should_skip_test(english_text: str, spanish_text: str) -> Tuple[bool, str]:
        """
        Détermine si un test doit être ignoré (faux positif).

        Args:
            english_text: Texte anglais
            spanish_text: Texte espagnol

        Returns:
            Tuple[bool, str]: (should_skip, reason)
        """
        # Vérifier texte anglais
        is_valid_en, reason_en = TextValidator.is_valid_game_text(english_text)
        if not is_valid_en:
            return True, f"invalid_english_{reason_en}"

        # Vérifier texte espagnol
        is_valid_es, reason_es = TextValidator.is_valid_game_text(spanish_text)
        if not is_valid_es:
            return True, f"invalid_spanish_{reason_es}"

        # Vérifier que les textes ont une longueur cohérente
        # (traduction espagnole ne devrait pas être 10x plus longue)
        if len(spanish_text) > len(english_text) * 5:
            return True, "unrealistic_length_ratio"

        # Cas spécial: textes fusionnés dans la ROM espagnole
        # Exemple: "6 v 6" (EN) → "6 v 6/Estándar" (ES)
        # La ROM espagnole a fusionné "6 v 6" + "Standard" en un seul texte
        # Détection: texte anglais très court qui est le préfixe du texte espagnol
        # ET le texte espagnol contient "/" (fusion visible)
        if len(english_text) <= 10 and '/' in spanish_text:
            # Vérifier si le texte anglais est un préfixe du texte espagnol
            if spanish_text.startswith(english_text):
                # C'est probablement une fusion de textes
                return True, "merged_texts_in_spanish_rom"

        # Cas spécial: texte anglais très court (≤5 chars) avec texte espagnol 2x+ plus long
        # ET contenant "?" → probablement pas un vrai texte de jeu
        if len(english_text) <= 5 and len(spanish_text) >= len(english_text) * 2:
            if '?' in spanish_text and spanish_text.count('?') >= 2:
                return True, "short_english_suspicious_spanish"

        return False, ""

    @staticmethod
    def sanitize_text_for_display(text: str, max_length: int = 60) -> str:
        """
        Nettoie un texte pour l'affichage.

        Args:
            text: Texte à nettoyer
            max_length: Longueur maximum

        Returns:
            str: Texte nettoyé
        """
        # Remplacer caractères non imprimables
        sanitized = ''.join(c if 32 <= ord(c) <= 126 or c in '\n\r' else '?' for c in text)

        # Tronquer si trop long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."

        return sanitized
