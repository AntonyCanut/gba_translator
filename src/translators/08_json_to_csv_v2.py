#!/usr/bin/env python3
"""
08 - JSON to CSV Converter (Version Orientée Objet)

Convertit le fichier JSON enrichi avec padding vers un CSV pour traduction.
Utilise les classes réutilisables du module core.

Usage:
    python src/translators/08_json_to_csv_v2.py [json_file]

Input:
    - output/differences/*_diff_with_padding.json

Output:
    - output/translation/YYYY-MM-DD_translation_template.csv
"""

import sys
from pathlib import Path
from datetime import datetime

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_converter import JSONToCSVConverter


class TranslationCSVGenerator:
    """
    Génère un CSV de traduction depuis un JSON enrichi.

    Attributes:
        converter (JSONToCSVConverter): Convertisseur JSON→CSV
        input_path (Path): Chemin du JSON source
        output_path (Path): Chemin du CSV de sortie
    """

    def __init__(self, input_path: Path = None, output_path: Path = None):
        """
        Initialise le générateur.

        Args:
            input_path: Chemin du JSON (None = auto-détection)
            output_path: Chemin du CSV (None = génération automatique)
        """
        self.converter = JSONToCSVConverter()
        self.input_path = input_path or self._find_latest_json()
        self.output_path = output_path or self._generate_output_path()

    def _find_latest_json(self) -> Path:
        """
        Trouve le fichier JSON enrichi le plus récent.

        Returns:
            Path: Chemin vers le fichier

        Raises:
            FileNotFoundError: Si aucun fichier trouvé
        """
        diff_dir = Path('output/differences')
        if not diff_dir.exists():
            raise FileNotFoundError("output/differences/ not found")

        json_files = list(diff_dir.glob('*_diff_with_padding.json'))

        if not json_files:
            raise FileNotFoundError(
                "No *_diff_with_padding.json found in output/differences/"
            )

        return max(json_files, key=lambda p: p.stat().st_mtime)

    def _generate_output_path(self) -> Path:
        """
        Génère le chemin de sortie avec date.

        Returns:
            Path: Chemin du CSV de sortie
        """
        output_dir = Path('output/translation')
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        return output_dir / f"{date_str}_translation_template.csv"

    def generate(self) -> dict:
        """
        Génère le CSV de traduction.

        Returns:
            dict: Statistiques de conversion

        Example:
            >>> generator = TranslationCSVGenerator()
            >>> stats = generator.generate()
            >>> print(stats['total_texts'])
            14436
        """
        # Charger JSON
        print(f"📄 Chargement: {self.input_path.name}")
        self.converter.load_from_json(self.input_path)

        # Catégoriser textes
        print("🔍 Catégorisation des textes...")
        self.converter.categorize_all()

        # Sauvegarder CSV
        print(f"💾 Génération CSV: {self.output_path.name}")
        self.converter.save_to_csv(self.output_path)

        # Retourner statistiques
        return self.converter.get_statistics()

    def print_statistics(self, stats: dict) -> None:
        """
        Affiche les statistiques de conversion.

        Args:
            stats: Dictionnaire de statistiques
        """
        print()
        print("=" * 80)
        print("STATISTIQUES PAR CATÉGORIE")
        print("=" * 80)

        total = stats['total_texts']
        for category, count in sorted(stats['categories'].items(), key=lambda x: -x[1]):
            pct = 100 * count / total
            print(f"  {category:15s}: {count:5d} ({pct:5.1f}%)")

        print()

    def print_instructions(self) -> None:
        """Affiche les instructions pour les traducteurs."""
        print("=" * 80)
        print("✅ CONVERSION TERMINÉE")
        print("=" * 80)
        print()
        print(f"Fichier généré: {self.output_path}")
        print()
        print("Instructions pour les traducteurs:")
        print("-" * 80)
        print("1. Ouvrir le CSV dans Excel, Google Sheets ou LibreOffice")
        print("2. Remplir la colonne 'translation' avec vos traductions")
        print("3. Respecter la colonne 'real_max_length' (longueur max avec padding)")
        print("4. Utiliser la colonne 'notes' pour commentaires si nécessaire")
        print("5. Sauvegarder et exécuter: python src/translators/09_csv_to_json_v2.py")
        print()
        print("Colonnes importantes:")
        print("  - original_text: Texte anglais à traduire")
        print("  - original_length: Longueur du texte anglais")
        print("  - padding_available: Bytes de padding disponibles")
        print("  - real_max_length: Longueur MAXIMALE autorisée (original + padding)")
        print("  - translation: VOTRE TRADUCTION (à remplir)")
        print()


def main():
    """Point d'entrée principal."""
    print("=" * 80)
    print("08 - JSON TO CSV CONVERTER (v2 - OOP)")
    print("=" * 80)
    print()

    # Gérer argument optionnel
    input_path = None
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if not input_path.exists():
            print(f"❌ Erreur: Fichier non trouvé: {input_path}")
            sys.exit(1)

    try:
        # Créer générateur
        generator = TranslationCSVGenerator(input_path=input_path)

        # Générer CSV
        stats = generator.generate()

        # Afficher résultats
        print(f"✅ {stats['total_texts']} textes exportés")
        generator.print_statistics(stats)
        generator.print_instructions()

    except FileNotFoundError as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
