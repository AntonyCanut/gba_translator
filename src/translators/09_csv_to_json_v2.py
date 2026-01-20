#!/usr/bin/env python3
"""
09 - CSV to JSON Converter (Version Orientée Objet)

Convertit le CSV traduit vers un JSON pour réinsertion dans la ROM.
Utilise les classes réutilisables du module core.

Usage:
    python src/translators/09_csv_to_json_v2.py [csv_file]

Input:
    - output/translation/*_translation_template.csv

Output:
    - output/translation/YYYY-MM-DD_translation_ready.json
"""

import sys
from pathlib import Path
from datetime import datetime

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_converter import CSVToJSONConverter


class TranslationValidator:
    """
    Valide et convertit un CSV de traduction vers JSON.

    Attributes:
        converter (CSVToJSONConverter): Convertisseur CSV→JSON
        input_path (Path): Chemin du CSV source
        output_path (Path): Chemin du JSON de sortie
    """

    def __init__(self, input_path: Path = None, output_path: Path = None, allow_too_long: bool = False):
        """
        Initialise le validateur.

        Args:
            input_path: Chemin du CSV (None = auto-détection)
            output_path: Chemin du JSON (None = génération automatique)
        """
        self.converter = CSVToJSONConverter()
        self.converter.allow_too_long = allow_too_long
        self.input_path = input_path or self._find_latest_csv()
        self.output_path = output_path or self._generate_output_path()

    def _find_latest_csv(self) -> Path:
        """
        Trouve le fichier CSV le plus récent.

        Returns:
            Path: Chemin vers le fichier

        Raises:
            FileNotFoundError: Si aucun fichier trouvé
        """
        translation_dir = Path('output/translation')
        if not translation_dir.exists():
            raise FileNotFoundError("output/translation/ not found")

        csv_files = list(translation_dir.glob('*_translation_*.csv'))

        if not csv_files:
            raise FileNotFoundError("No CSV files found in output/translation/")

        return max(csv_files, key=lambda p: p.stat().st_mtime)

    def _generate_output_path(self) -> Path:
        """
        Génère le chemin de sortie avec date.

        Returns:
            Path: Chemin du JSON de sortie
        """
        output_dir = Path('output/translation')
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        return output_dir / f"{date_str}_translation_ready.json"

    def validate_and_convert(self) -> dict:
        """
        Valide le CSV et convertit vers JSON.

        Returns:
            dict: Statistiques de conversion

        Raises:
            ValueError: Si des erreurs de validation sont détectées

        Example:
            >>> validator = TranslationValidator()
            >>> stats = validator.validate_and_convert()
            >>> print(stats['successful'])
            100
        """
        # Charger et valider CSV
        print(f"📄 Chargement CSV: {self.input_path.name}")
        print("🔍 Validation des traductions...")
        print()

        self.converter.load_from_csv(self.input_path)

        # Vérifier erreurs
        if self.converter.has_errors():
            raise ValueError("Validation failed - see errors below")

        # Sauvegarder JSON
        print(f"💾 Génération JSON: {self.output_path.name}")
        self.converter.save_to_json(self.output_path, self.input_path.name)

        return self.converter.get_statistics()

    def print_results(self, stats: dict) -> None:
        """
        Affiche les résultats de la conversion.

        Args:
            stats: Dictionnaire de statistiques
        """
        print()
        print("=" * 80)
        print("RÉSULTATS DE LA CONVERSION")
        print("=" * 80)
        print(f"Total lignes:           {stats['total_rows']}")
        print(f"Traductions réussies:   {stats['successful']}")
        print(f"Erreurs:                {len(stats['errors'])}")
        print(f"Avertissements:         {len(stats['warnings'])}")
        print()

    def print_errors(self, errors: list, limit: int = 10) -> None:
        """
        Affiche les erreurs de validation.

        Args:
            errors: Liste des erreurs
            limit: Nombre max d'erreurs à afficher
        """
        if not errors:
            return

        print("=" * 80)
        print("❌ ERREURS DÉTECTÉES")
        print("=" * 80)

        for error in errors[:limit]:
            print(f"\nLigne {error['row']} - Offset {error['offset']}")
            print(f"  Original:    {error['original']}")
            print(f"  Traduction:  {error['translation']}")
            print(f"  Erreur:      {error['error']}")

        if len(errors) > limit:
            print(f"\n... et {len(errors) - limit} autres erreurs")

        print()
        print("⚠️ Veuillez corriger ces erreurs avant de continuer.")
        print()

    def print_warnings(self, warnings: list, limit: int = 5) -> None:
        """
        Affiche les avertissements.

        Args:
            warnings: Liste des avertissements
            limit: Nombre max d'avertissements à afficher
        """
        if not warnings:
            return

        print("=" * 80)
        print("⚠️ AVERTISSEMENTS")
        print("=" * 80)

        for warning in warnings[:limit]:
            print(f"Ligne {warning['row']} - {warning['offset']}: {warning['message']}")

        if len(warnings) > limit:
            print(f"... et {len(warnings) - limit} autres avertissements")

        print()

    def print_success(self) -> None:
        """Affiche le message de succès."""
        print("=" * 80)
        print("✅ CONVERSION RÉUSSIE")
        print("=" * 80)
        print()
        print(f"Fichier généré: {self.output_path}")
        print()
        print("Prochaine étape:")
        print("  python src/translators/10_reinsert_smart_v2.py")
        print()


def main():
    """Point d'entrée principal."""
    print("=" * 80)
    print("09 - CSV TO JSON CONVERTER (v2 - OOP)")
    print("=" * 80)
    print()

    # Gérer argument optionnel
    input_path = None
    allow_too_long = False
    args = sys.argv[1:]
    if '--allow-too-long' in args:
        allow_too_long = True
        args.remove('--allow-too-long')
    if args:
        input_path = Path(args[0])
        if not input_path.exists():
            print(f"❌ Erreur: Fichier non trouvé: {input_path}")
            sys.exit(1)

    try:
        # Créer validateur
        validator = TranslationValidator(input_path=input_path, allow_too_long=allow_too_long)

        # Valider et convertir
        stats = validator.validate_and_convert()

        # Afficher résultats
        validator.print_results(stats)
        validator.print_warnings(stats['warnings'])
        validator.print_success()

    except ValueError as e:
        # Erreurs de validation
        stats = validator.converter.get_statistics()
        validator.print_results(stats)
        validator.print_errors(stats['errors'])
        sys.exit(1)

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
