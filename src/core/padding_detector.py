#!/usr/bin/env python3
"""
Padding Detector - Détection du padding disponible

Implémente la stratégie découverte dans la ROM espagnole :
utiliser le padding (0x00/0xFF) disponible entre les textes.
"""

from typing import List, Dict, Optional
from .rom_reader import ROMReader


class PaddingDetector:
    """
    Détecte le padding disponible après les textes.

    Le padding est constitué de bytes 0x00 ou 0xFF utilisés
    pour l'alignement mémoire. La ROM espagnole utilise ce
    padding pour permettre des textes plus longs.

    Attributes:
        PADDING_BYTES (list): Bytes considérés comme padding
        rom (ROMReader): Instance de lecteur ROM
        stats (dict): Statistiques de détection
    """

    PADDING_BYTES = [0x00, 0xFF]

    def __init__(self, rom_reader: ROMReader):
        """
        Initialise le détecteur de padding.

        Args:
            rom_reader: Instance de ROMReader chargée
        """
        self.rom = rom_reader
        self.stats = {
            'total_analyzed': 0,
            'with_padding': 0,
            'without_padding': 0,
            'total_padding': 0,
            'avg_padding': 0.0,
            'max_padding': 0,
            'min_padding': 9999,
            'distribution': {}  # padding_size → count
        }

    def detect_padding(self, offset: int, length: int, extended_search: bool = False) -> int:
        """
        Détecte le padding disponible après un texte.

        Compte les bytes consécutifs 0x00 ou 0xFF après le texte.

        Args:
            offset: Offset du texte dans la ROM
            length: Longueur du texte original
            extended_search: Si True, cherche dans une zone plus large (max 10 bytes)

        Returns:
            int: Nombre de bytes de padding disponibles

        Example:
            >>> detector = PaddingDetector(rom)
            >>> padding = detector.detect_padding(0x0023E5DA, 5)
            >>> print(padding)  # 7
        """
        end = offset + length
        padding = 0

        # Recherche standard: bytes consécutifs
        while end + padding < self.rom.rom_size:
            byte = self.rom.rom_data[end + padding]
            if byte in self.PADDING_BYTES:
                padding += 1
            else:
                break

        # Si extended_search activé et peu de padding trouvé,
        # chercher dans les 10 prochains bytes
        if extended_search and padding < 3:
            # Compter TOUS les bytes de padding dans les 10 prochains
            extended_padding = 0
            search_zone = min(10, self.rom.rom_size - end)

            for i in range(search_zone):
                byte = self.rom.rom_data[end + i]
                if byte in self.PADDING_BYTES:
                    extended_padding += 1

            # Utiliser le padding étendu s'il est meilleur
            if extended_padding > padding:
                return extended_padding

        return padding

    def analyze_text(self, text_entry: dict, extended_search: bool = False) -> dict:
        """
        Analyse un texte et enrichit avec info padding.

        Args:
            text_entry: Dictionnaire avec 'offset' et 'length'
            extended_search: Si True, utilise recherche étendue de padding

        Returns:
            dict: Entry enrichi avec:
                - padding_available: bytes de padding
                - real_max_length: longueur max réelle (original + padding)

        Example:
            >>> entry = {'offset': 0x0023E5DA, 'length': 5, 'text': 'Nurse'}
            >>> enriched = detector.analyze_text(entry)
            >>> print(enriched['real_max_length'])  # 12
        """
        offset = text_entry['offset']
        length = text_entry['length']

        padding = self.detect_padding(offset, length, extended_search=extended_search)

        # Enrichir l'entry
        enriched = text_entry.copy()
        enriched['padding_available'] = padding
        enriched['real_max_length'] = length + padding

        # Mettre à jour statistiques
        self._update_stats(padding)

        return enriched

    def analyze_all_texts(self, texts: List[dict], extended_search: bool = False) -> List[dict]:
        """
        Analyse une liste de textes.

        Args:
            texts: Liste de dictionnaires text entries
            extended_search: Si True, utilise recherche étendue de padding

        Returns:
            List[dict]: Textes enrichis avec info padding
        """
        enriched_texts = []

        for text in texts:
            enriched = self.analyze_text(text, extended_search=extended_search)
            enriched_texts.append(enriched)

        # Calculer moyennes finales
        if self.stats['total_analyzed'] > 0:
            self.stats['avg_padding'] = (
                self.stats['total_padding'] / self.stats['total_analyzed']
            )

        return enriched_texts

    def _update_stats(self, padding: int) -> None:
        """
        Met à jour les statistiques internes.

        Args:
            padding: Nombre de bytes de padding détectés
        """
        self.stats['total_analyzed'] += 1
        self.stats['total_padding'] += padding

        if padding > 0:
            self.stats['with_padding'] += 1
        else:
            self.stats['without_padding'] += 1

        self.stats['max_padding'] = max(self.stats['max_padding'], padding)

        if padding < self.stats['min_padding']:
            self.stats['min_padding'] = padding

        # Distribution
        if padding not in self.stats['distribution']:
            self.stats['distribution'][padding] = 0
        self.stats['distribution'][padding] += 1

    def generate_report(self) -> dict:
        """
        Génère un rapport statistique complet.

        Returns:
            dict: Rapport avec statistiques, distribution et recommandations
        """
        total = self.stats['total_analyzed']
        if total == 0:
            return {
                'statistics': self.stats,
                'message': 'No texts analyzed'
            }

        # Calcul percentages
        pct_with_padding = 100 * self.stats['with_padding'] / total
        pct_without = 100 * self.stats['without_padding'] / total

        # Distribution par ranges
        ranges_dist = self._calculate_range_distribution()

        report = {
            'statistics': {
                'total_analyzed': total,
                'with_padding': f"{self.stats['with_padding']} ({pct_with_padding:.1f}%)",
                'without_padding': f"{self.stats['without_padding']} ({pct_without:.1f}%)",
                'average_padding': f"{self.stats['avg_padding']:.1f} bytes",
                'max_padding': f"{self.stats['max_padding']} bytes",
                'min_padding': f"{self.stats['min_padding']} bytes",
            },
            'distribution_by_range': ranges_dist,
            'recommendations': self._generate_recommendations()
        }

        return report

    def _calculate_range_distribution(self) -> dict:
        """
        Calcule la distribution par ranges de padding.

        Returns:
            dict: Distribution (range → count et percentage)
        """
        ranges = [
            (0, 0, "No padding"),
            (1, 3, "1-3 bytes"),
            (4, 6, "4-6 bytes"),
            (7, 10, "7-10 bytes"),
            (11, 20, "11-20 bytes"),
            (21, 999, "21+ bytes")
        ]

        total = self.stats['total_analyzed']
        dist = {}

        for min_val, max_val, label in ranges:
            count = sum(
                cnt for size, cnt in self.stats['distribution'].items()
                if min_val <= size <= max_val
            )
            pct = 100 * count / total if total > 0 else 0
            dist[label] = {
                'count': count,
                'percentage': f"{pct:.1f}%"
            }

        return dist

    def _generate_recommendations(self) -> List[str]:
        """
        Génère des recommandations basées sur les statistiques.

        Returns:
            List[str]: Liste de recommandations
        """
        recommendations = []
        avg = self.stats['avg_padding']

        if avg >= 3:
            recommendations.append(
                f"✅ Padding moyen élevé ({avg:.1f} bytes). "
                "La majorité des débordements de 1-3 bytes seront gérés automatiquement."
            )
        elif avg >= 1:
            recommendations.append(
                f"⚠️ Padding moyen modéré ({avg:.1f} bytes). "
                "Certains textes nécessiteront des abréviations."
            )
        else:
            recommendations.append(
                f"❌ Padding moyen faible ({avg:.1f} bytes). "
                "La plupart des textes devront rester ≤ longueur originale."
            )

        # Vérifier distribution
        pct_no_padding = (
            100 * self.stats['without_padding'] / self.stats['total_analyzed']
            if self.stats['total_analyzed'] > 0 else 0
        )

        if pct_no_padding > 50:
            recommendations.append(
                f"⚠️ {pct_no_padding:.0f}% des textes n'ont pas de padding. "
                "Approche conservative recommandée."
            )

        return recommendations

    def __repr__(self) -> str:
        if self.stats['total_analyzed'] == 0:
            return "PaddingDetector(no analysis yet)"
        return (
            f"PaddingDetector("
            f"analyzed={self.stats['total_analyzed']}, "
            f"avg={self.stats['avg_padding']:.1f})"
        )
