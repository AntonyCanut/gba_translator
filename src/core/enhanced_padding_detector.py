#!/usr/bin/env python3
"""
Enhanced Padding Detector - Détection avancée du padding

Améliore la détection de padding pour gérer tous les cas de débordement,
y compris les cas complexes (7-10 bytes et plus).
"""

from typing import List, Dict, Optional, Tuple
from .rom_reader import ROMReader
from .padding_detector import PaddingDetector


class EnhancedPaddingDetector(PaddingDetector):
    """
    Version améliorée du détecteur de padding.

    Améliore la détection en:
    1. Cherchant plus loin dans la ROM
    2. Tolérant de petits gaps de non-padding
    3. Validant la continuité des données

    Attributes:
        PADDING_BYTES (list): Bytes considérés comme padding
        rom (ROMReader): Instance de lecteur ROM
        stats (dict): Statistiques de détection
        aggressive_mode (bool): Mode agressif (plus de risques, plus de padding détecté)
    """

    def __init__(self, rom_reader: ROMReader, aggressive_mode: bool = False):
        """
        Initialise le détecteur amélioré.

        Args:
            rom_reader: Instance de ROMReader chargée
            aggressive_mode: Si True, détecte plus de padding (plus de risques)
        """
        super().__init__(rom_reader)
        self.aggressive_mode = aggressive_mode

        # Statistiques étendues
        self.stats['extended_padding_used'] = 0
        self.stats['gaps_tolerated'] = 0

    def detect_extended_padding(
        self,
        offset: int,
        length: int,
        max_search: int = 50,
        max_gap: int = 5
    ) -> Tuple[int, dict]:
        """
        Détecte le padding étendu en tolérant de petits gaps.

        Cette méthode cherche plus loin que detect_padding() standard
        et peut tolérer de petits gaps de non-padding (faux positifs).

        Args:
            offset: Offset du texte dans la ROM
            length: Longueur du texte original
            max_search: Distance maximale de recherche (bytes)
            max_gap: Nombre max de bytes non-padding consécutifs tolérés

        Returns:
            tuple: (padding_total, details_dict)
                - padding_total: Total de bytes de padding détectés
                - details_dict: Détails de la détection

        Example:
            >>> detector = EnhancedPaddingDetector(rom)
            >>> padding, details = detector.detect_extended_padding(0x0018D480, 17)
            >>> print(padding)  # Peut être > detect_padding standard
            10
            >>> print(details['confidence'])
            "medium"
        """
        end = offset + length
        padding_total = 0
        padding_continuous = 0
        non_padding_gap = 0
        gaps_found = 0

        padding_sequences = []  # Liste des séquences de padding trouvées

        for i in range(max_search):
            if end + i >= self.rom.rom_size:
                break

            byte = self.rom.rom_data[end + i]

            if byte in self.PADDING_BYTES:
                padding_total += 1
                padding_continuous += 1
                non_padding_gap = 0
            else:
                # Byte non-padding trouvé
                if padding_continuous > 0:
                    padding_sequences.append({
                        'start': i - padding_continuous,
                        'length': padding_continuous
                    })
                    padding_continuous = 0

                non_padding_gap += 1

                if non_padding_gap > max_gap:
                    # Trop de non-padding consécutifs, arrêter
                    break

                gaps_found += 1

        # Ajouter dernière séquence si elle existe
        if padding_continuous > 0:
            padding_sequences.append({
                'start': max_search - padding_continuous,
                'length': padding_continuous
            })

        # Calculer niveau de confiance
        confidence = self._calculate_confidence(
            padding_total,
            gaps_found,
            padding_sequences
        )

        details = {
            'padding_total': padding_total,
            'padding_sequences': len(padding_sequences),
            'gaps_found': gaps_found,
            'confidence': confidence,
            'sequences': padding_sequences[:5]  # Top 5 séquences
        }

        return padding_total, details

    def _calculate_confidence(
        self,
        padding_total: int,
        gaps_found: int,
        sequences: List[dict]
    ) -> str:
        """
        Calcule le niveau de confiance de la détection.

        Args:
            padding_total: Total de padding détecté
            gaps_found: Nombre de gaps tolérés
            sequences: Liste des séquences de padding

        Returns:
            str: Niveau de confiance ('high', 'medium', 'low')
        """
        if gaps_found == 0 and padding_total > 0:
            return 'high'  # Padding continu, très fiable

        if gaps_found <= 2 and len(sequences) <= 3:
            return 'medium'  # Quelques gaps, assez fiable

        return 'low'  # Beaucoup de gaps, moins fiable

    def detect_with_validation(
        self,
        offset: int,
        length: int
    ) -> Tuple[int, int, dict]:
        """
        Détecte le padding avec validation automatique.

        Utilise detect_padding() standard, puis detect_extended_padding()
        si le mode agressif est activé.

        Args:
            offset: Offset du texte
            length: Longueur originale

        Returns:
            tuple: (standard_padding, extended_padding, details)
        """
        # Détection standard
        standard_padding = self.detect_padding(offset, length)

        # Détection étendue (si mode agressif)
        if self.aggressive_mode:
            extended_padding, details = self.detect_extended_padding(
                offset,
                length,
                max_search=50,
                max_gap=5
            )
        else:
            extended_padding = standard_padding
            details = {
                'padding_total': standard_padding,
                'padding_sequences': 1,
                'gaps_found': 0,
                'confidence': 'high',
                'sequences': []
            }

        return standard_padding, extended_padding, details

    def analyze_text_enhanced(self, text_entry: dict) -> dict:
        """
        Analyse un texte avec détection améliorée.

        Args:
            text_entry: Dictionnaire avec 'offset' et 'length'

        Returns:
            dict: Entry enrichi avec padding standard ET étendu

        Example:
            >>> entry = {'offset': 0x0018D480, 'length': 17, 'text': '...'}
            >>> enriched = detector.analyze_text_enhanced(entry)
            >>> print(enriched['padding_available'])  # Standard
            1
            >>> print(enriched['padding_extended'])  # Étendu
            8
        """
        offset = text_entry['offset']
        length = text_entry['length']

        standard, extended, details = self.detect_with_validation(offset, length)

        # Enrichir l'entry
        enriched = text_entry.copy()
        enriched['padding_available'] = standard
        enriched['padding_extended'] = extended
        enriched['real_max_length'] = length + standard
        enriched['real_max_length_extended'] = length + extended
        enriched['padding_confidence'] = details['confidence']
        enriched['padding_details'] = details

        # Mettre à jour statistiques
        self._update_stats(standard)
        if extended > standard:
            self.stats['extended_padding_used'] += 1
            self.stats['gaps_tolerated'] += details['gaps_found']

        return enriched

    def analyze_all_texts_enhanced(self, texts: List[dict]) -> List[dict]:
        """
        Analyse tous les textes avec détection améliorée.

        Args:
            texts: Liste de dictionnaires text entries

        Returns:
            List[dict]: Textes enrichis avec padding standard et étendu
        """
        enriched_texts = []

        for text in texts:
            enriched = self.analyze_text_enhanced(text)
            enriched_texts.append(enriched)

        # Calculer moyennes finales
        if self.stats['total_analyzed'] > 0:
            self.stats['avg_padding'] = (
                self.stats['total_padding'] / self.stats['total_analyzed']
            )

        return enriched_texts

    def generate_enhanced_report(self) -> dict:
        """
        Génère un rapport avec statistiques étendues.

        Returns:
            dict: Rapport complet avec statistiques standard + étendues
        """
        base_report = super().generate_report()

        # Ajouter statistiques étendues
        if self.aggressive_mode:
            total = self.stats['total_analyzed']
            extended_used_pct = (
                100 * self.stats['extended_padding_used'] / total
                if total > 0 else 0
            )

            base_report['extended_statistics'] = {
                'aggressive_mode': True,
                'extended_padding_used': self.stats['extended_padding_used'],
                'extended_padding_percentage': f"{extended_used_pct:.1f}%",
                'gaps_tolerated': self.stats['gaps_tolerated'],
                'avg_gaps_per_text': (
                    self.stats['gaps_tolerated'] / max(1, self.stats['extended_padding_used'])
                )
            }

            base_report['recommendations'].append(
                f"⚠️ Mode agressif activé: {self.stats['extended_padding_used']} textes "
                f"utilisent padding étendu ({extended_used_pct:.1f}%). "
                "Vérifier attentivement ces cas."
            )
        else:
            base_report['extended_statistics'] = {
                'aggressive_mode': False,
                'note': 'Mode standard utilisé. Activer aggressive_mode=True '
                        'pour détecter plus de padding.'
            }

        return base_report

    def compare_with_standard(self, texts: List[dict]) -> dict:
        """
        Compare détection standard vs étendue.

        Args:
            texts: Liste de textes à analyser

        Returns:
            dict: Rapport de comparaison
        """
        improvements = []
        total_gain = 0

        for text in texts:
            offset = text['offset']
            length = text['length']

            standard = self.detect_padding(offset, length)
            extended, details = self.detect_extended_padding(offset, length)

            gain = extended - standard

            if gain > 0:
                improvements.append({
                    'offset': f"0x{offset:08X}",
                    'text': text.get('text', '')[:30],
                    'standard_padding': standard,
                    'extended_padding': extended,
                    'gain': gain,
                    'confidence': details['confidence']
                })
                total_gain += gain

        # Trier par gain
        improvements.sort(key=lambda x: x['gain'], reverse=True)

        return {
            'total_texts': len(texts),
            'improvements_found': len(improvements),
            'total_padding_gain': total_gain,
            'average_gain': total_gain / len(improvements) if improvements else 0,
            'top_improvements': improvements[:20]
        }

    def __repr__(self) -> str:
        mode = "aggressive" if self.aggressive_mode else "standard"
        if self.stats['total_analyzed'] == 0:
            return f"EnhancedPaddingDetector(mode={mode}, no analysis yet)"
        return (
            f"EnhancedPaddingDetector("
            f"mode={mode}, "
            f"analyzed={self.stats['total_analyzed']}, "
            f"avg={self.stats['avg_padding']:.1f}, "
            f"extended_used={self.stats['extended_padding_used']})"
        )
