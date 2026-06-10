#!/usr/bin/env python3
"""
Text Converter - Classes pour conversion de formats

Fournit des convertisseurs réutilisables entre différents formats
de données de traduction (JSON, CSV, etc.)
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from .text_codec import TextEncoder


class TextEntry:
    """
    Représente une entrée de texte à traduire.

    Attributes:
        offset (int): Position dans la ROM
        text (str): Texte original
        length (int): Longueur du texte
        encoding (str): Type d'encodage (ascii/pokemon)
        padding_available (int): Padding disponible
        real_max_length (int): Longueur max réelle
        category (str): Catégorie du texte
        translation (str): Traduction (optionnel)
        notes (str): Notes du traducteur
    """

    def __init__(
        self,
        offset: int,
        text: str,
        length: int,
        encoding: str,
        padding_available: int = 0,
        category: str = "other",
        translation: str = "",
        notes: str = "",
        too_long: bool = False
    ):
        self.offset = offset
        self.text = text
        self.length = length
        self.encoding = encoding
        self.padding_available = padding_available
        self.real_max_length = length + padding_available
        self.category = category
        self.translation = translation
        self.notes = notes
        self.too_long = too_long

    @classmethod
    def from_dict(cls, data: dict) -> 'TextEntry':
        """
        Crée une TextEntry depuis un dictionnaire.

        Args:
            data: Dictionnaire avec les données

        Returns:
            TextEntry: Instance créée
        """
        return cls(
            offset=data.get('offset', 0),
            text=data.get('text', ''),
            length=data.get('length', 0),
            encoding=data.get('encoding', 'pokemon'),
            padding_available=data.get('padding_available', 0),
            category=data.get('category', 'other'),
            translation=data.get('translation', ''),
            notes=data.get('notes', ''),
            too_long=data.get('too_long', False)
        )

    def to_dict(self) -> dict:
        """
        Convertit en dictionnaire.

        Returns:
            dict: Données de l'entry
        """
        return {
            'offset': self.offset,
            'text': self.text,
            'length': self.length,
            'encoding': self.encoding,
            'padding_available': self.padding_available,
            'real_max_length': self.real_max_length,
            'category': self.category,
            'translation': self.translation,
            'notes': self.notes,
            'too_long': self.too_long,
        }

    def to_csv_row(self) -> dict:
        """
        Convertit en ligne CSV.

        Returns:
            dict: Ligne CSV formatée
        """
        return {
            'offset': f"0x{self.offset:08X}",
            'original_text': self.text,
            'original_length': self.length,
            'padding_available': self.padding_available,
            'real_max_length': self.real_max_length,
            'encoding': self.encoding,
            'category': self.category,
            'translation': self.translation,
            'notes': self.notes
        }

    def validate_translation(self) -> tuple[bool, str]:
        """
        Valide que la traduction respecte les contraintes.

        Returns:
            tuple: (is_valid, error_message)
        """
        if not self.translation:
            return False, "Traduction manquante"

        trans_len = self.encoded_length()
        if trans_len > self.real_max_length:
            overflow = trans_len - self.real_max_length
            return False, f"Trop long: {trans_len} > {self.real_max_length} (débordement: {overflow})"

        return True, ""

    def encoded_length(self) -> int:
        """
        Calcule la longueur encodée (sans terminateur).

        Permet de compter correctement les tokens <0x??> et
        les codes de contrôle comme \\n.
        """
        if not self.translation:
            return 0
        try:
            encoded = TextEncoder.encode(self.translation, self.encoding)
        except ValueError:
            return len(self.translation)
        return max(len(encoded) - 1, 0)

    def __repr__(self) -> str:
        return f"TextEntry(offset=0x{self.offset:08X}, text='{self.text[:20]}...', length={self.length})"


class JSONToCSVConverter:
    """
    Convertit un JSON de textes enrichis vers CSV pour traduction.

    Attributes:
        entries (List[TextEntry]): Liste des entrées de texte
        metadata (dict): Métadonnées du fichier source
    """

    CSV_FIELDNAMES = [
        'offset',
        'original_text',
        'original_length',
        'padding_available',
        'real_max_length',
        'encoding',
        'category',
        'translation',
        'notes'
    ]

    def __init__(self):
        self.entries: List[TextEntry] = []
        self.metadata: dict = {}

    def load_from_json(self, json_path: Path) -> None:
        """
        Charge les données depuis un fichier JSON.

        Args:
            json_path: Chemin vers le fichier JSON
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.metadata = {
            'rom_name': data.get('rom_name', ''),
            'rom_size': data.get('rom_size', 0),
            'analysis_date': data.get('analysis_date', ''),
            'text_count': data.get('text_count', 0)
        }

        self.entries = [
            TextEntry.from_dict(text_data)
            for text_data in data.get('texts', [])
        ]

    def categorize_text(self, text: str, offset: int) -> str:
        """
        Catégorise un texte basé sur son contenu.

        Args:
            text: Le texte à catégoriser
            offset: L'offset du texte

        Returns:
            str: Catégorie du texte
        """
        text_lower = text.lower()

        # Dialogues
        if any(marker in text_lower for marker in ['!', '?', '...', 'you', 'your', 'my', 'i ']):
            return "dialogue"

        # Noms de lieux
        if text and text[0].isupper() and ' ' in text and len(text.split()) <= 3:
            return "location"

        # Messages système
        if any(word in text_lower for word in ['saved', 'loaded', 'menu', 'cancel', 'select']):
            return "system"

        # Descriptions
        if len(text) > 30:
            return "description"

        return "other"

    def categorize_all(self) -> None:
        """Catégorise tous les textes."""
        for entry in self.entries:
            entry.category = self.categorize_text(entry.text, entry.offset)

    def save_to_csv(self, csv_path: Path) -> None:
        """
        Sauvegarde les données vers un fichier CSV.

        Args:
            csv_path: Chemin vers le fichier CSV de sortie
        """
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_FIELDNAMES)
            writer.writeheader()

            for entry in self.entries:
                writer.writerow(entry.to_csv_row())

    def get_statistics(self) -> dict:
        """
        Calcule des statistiques sur les textes.

        Returns:
            dict: Statistiques par catégorie
        """
        stats = {
            'total_texts': len(self.entries),
            'categories': {}
        }

        for entry in self.entries:
            cat = entry.category
            stats['categories'][cat] = stats['categories'].get(cat, 0) + 1

        return stats


class CSVToJSONConverter:
    """
    Convertit un CSV traduit vers JSON pour réinsertion.

    Attributes:
        entries (List[TextEntry]): Liste des entrées traduites
        errors (List[dict]): Liste des erreurs de validation
        warnings (List[dict]): Liste des avertissements
    """

    def __init__(self):
        self.entries: List[TextEntry] = []
        self.errors: List[dict] = []
        self.warnings: List[dict] = []
        self.allow_too_long = False

    @staticmethod
    def _is_suspicious_short(entry: TextEntry) -> bool:
        encoded_len = entry.encoded_length()
        if entry.length <= 2 and encoded_len > entry.length + 6:
            return True
        if entry.length <= 3 and encoded_len > entry.length + 8:
            return True
        return False

    def load_from_csv(self, csv_path: Path) -> None:
        """
        Charge les données depuis un fichier CSV.

        Args:
            csv_path: Chemin vers le fichier CSV
        """
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header = 1)
                raw_translation = row.get('translation', '')
                translation = raw_translation.strip()

                # Les espaces de bord sont significatifs quand le texte source
                # en a (ex. préfixe de combat "The opposing " -> "L'adversaire ") :
                # ne nettoyer que les fins de ligne parasites dans ce cas.
                original_text = row.get('original_text', '')
                if translation and original_text != original_text.strip(' '):
                    translation = raw_translation.strip('\r\n')

                # Ignorer lignes sans traduction
                if not translation:
                    self.warnings.append({
                        'row': row_num,
                        'offset': row.get('offset', 'unknown'),
                        'message': 'Traduction manquante'
                    })
                    continue

                # Convertir offset
                offset_str = row['offset'].replace('0x', '')
                offset = int(offset_str, 16)

                # Créer entry
                entry = TextEntry(
                    offset=offset,
                    text=row['original_text'],
                    length=int(row['original_length']),
                    encoding=row['encoding'],
                    padding_available=int(row['padding_available']),
                    category=row.get('category', 'unknown'),
                    translation=translation,
                    notes=row.get('notes', '')
                )

                if self._is_suspicious_short(entry):
                    self.warnings.append({
                        'row': row_num,
                        'offset': row.get('offset', 'unknown'),
                        'message': (
                            'Traduction suspecte pour texte court '
                            f"(len={entry.length}, trad_len={entry.encoded_length()})"
                        )
                    })
                    continue

                # Valider
                is_valid, error_msg = entry.validate_translation()

                if not is_valid:
                    if self.allow_too_long and error_msg.startswith("Trop long"):
                        entry.too_long = True
                        self.warnings.append({
                            'row': row_num,
                            'offset': row.get('offset', 'unknown'),
                            'message': f"{error_msg} (accepted)"
                        })
                    else:
                        self.errors.append({
                            'row': row_num,
                            'offset': row.get('offset', 'unknown'),
                            'original': entry.text,
                            'translation': translation,
                            'error': error_msg
                        })
                        continue

                self.entries.append(entry)

    def save_to_json(self, json_path: Path, source_csv: str) -> None:
        """
        Sauvegarde les données vers un fichier JSON.

        Args:
            json_path: Chemin vers le fichier JSON de sortie
            source_csv: Nom du fichier CSV source
        """
        translations = []

        for entry in self.entries:
            encoded_length = entry.encoded_length()
            translations.append({
                'offset': entry.offset,
                'original_text': entry.text,
                'translation': entry.translation,
                'length': encoded_length,
                'original_length': entry.length,
                'padding_used': encoded_length - entry.length,
                'encoding': entry.encoding,
                'category': entry.category,
                'notes': entry.notes,
                'too_long': entry.too_long
            })

        output = {
            'conversion_date': datetime.now().isoformat(),
            'source_csv': source_csv,
            'total_translations': len(translations),
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings),
            'translations': translations
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    def has_errors(self) -> bool:
        """Vérifie si des erreurs ont été détectées."""
        return len(self.errors) > 0

    def get_statistics(self) -> dict:
        """
        Retourne des statistiques de conversion.

        Returns:
            dict: Statistiques complètes
        """
        too_long = sum(1 for entry in self.entries if entry.too_long)
        return {
            'total_rows': len(self.entries) + len(self.errors) + len(self.warnings),
            'successful': len(self.entries),
            'errors': self.errors,
            'warnings': self.warnings,
            'too_long': too_long
        }
