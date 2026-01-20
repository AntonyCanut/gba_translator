#!/usr/bin/env python3
"""
10 - Smart Text Reinsertion (Version Orientée Objet)

Réinsère les textes traduits dans la ROM avec gestion intelligente du padding.
Utilise les classes réutilisables du module core.

Usage:
    python src/translators/10_reinsert_smart_v2.py [translation_json]

Input:
    - input/roms/englishrom.gba
    - output/translation/*_translation_ready.json

Output:
    - output/roms/YYYY-MM-DD_frenchrom.gba
    - output/reports/YYYY-MM-DD_reinsertion_report.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_reinserter import ROMTranslationManager


class TranslationApplicator:
    """
    Applique des traductions à une ROM GBA.

    Attributes:
        rom_manager (ROMTranslationManager): Gestionnaire de ROM
        translation_path (Path): Chemin du JSON de traductions
        output_rom_path (Path): Chemin de la ROM de sortie
        report_path (Path): Chemin du rapport
    """

    def __init__(
        self,
        rom_path: str = 'input/roms/englishrom.gba',
        translation_path: Path = None
    ):
        """
        Initialise l'applicateur.

        Args:
            rom_path: Chemin de la ROM source
            translation_path: Chemin du JSON (None = auto-détection)
        """
        self.rom_path = rom_path
        self.translation_path = translation_path or self._find_latest_json()
        self.output_rom_path = self._generate_output_path()
        self.report_path = self._generate_report_path()
        self.rom_manager = None
        self.translations = []

    def _find_latest_json(self) -> Path:
        """
        Trouve le fichier JSON de traductions le plus récent.

        Returns:
            Path: Chemin vers le fichier

        Raises:
            FileNotFoundError: Si aucun fichier trouvé
        """
        translation_dir = Path('output/translation')
        if not translation_dir.exists():
            raise FileNotFoundError("output/translation/ not found")

        json_files = list(translation_dir.glob('*_translation_ready.json'))

        if not json_files:
            raise FileNotFoundError("No *_translation_ready.json found")

        return max(json_files, key=lambda p: p.stat().st_mtime)

    def _generate_output_path(self) -> Path:
        """
        Génère le chemin de sortie de la ROM.

        Returns:
            Path: Chemin de la ROM de sortie
        """
        output_dir = Path('output/roms')
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        return output_dir / f"{date_str}_frenchrom.gba"

    def _generate_report_path(self) -> Path:
        """
        Génère le chemin du rapport.

        Returns:
            Path: Chemin du rapport JSON
        """
        report_dir = Path('output/reports')
        report_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        return report_dir / f"{date_str}_reinsertion_report.json"

    def load_translations(self) -> None:
        """
        Charge les traductions depuis le JSON.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            json.JSONDecodeError: Si le JSON est invalide
        """
        print(f"📄 Chargement traductions: {self.translation_path.name}")

        with open(self.translation_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.translations = data['translations']
        print(f"   {len(self.translations)} traductions à insérer")

    def load_rom(self) -> None:
        """
        Charge la ROM source.

        Raises:
            FileNotFoundError: Si la ROM n'existe pas
        """
        print(f"📖 Chargement ROM: {self.rom_path}")

        self.rom_manager = ROMTranslationManager(self.rom_path)
        info = self.rom_manager.get_rom_info()

        print(f"   ROM: {info['title']} ({info['game_code']})")
        print(f"   Taille: {info['size_mb']} MB")

    def apply_translations(self) -> dict:
        """
        Applique toutes les traductions à la ROM.

        Returns:
            dict: Rapport de réinsertion

        Example:
            >>> applicator = TranslationApplicator()
            >>> report = applicator.apply_translations()
            >>> print(report['statistics']['successful'])
            100
        """
        print()
        print("🔄 Réinsertion des traductions...")

        # Appliquer traductions avec progression
        total = len(self.translations)
        for i in range(0, total, 1000):
            batch = self.translations[i:min(i + 1000, total)]
            self.rom_manager.reinserter.reinsert_all(batch)
            print(f"   Traité: {min(i + 1000, total)}/{total}")

        report = self.rom_manager.reinserter.get_report()

        print()
        print(f"✅ {total} textes traités")
        print()

        return report

    def save_rom(self) -> None:
        """Sauvegarde la ROM modifiée."""
        print(f"💾 Sauvegarde ROM: {self.output_rom_path}")
        self.rom_manager.save_rom(str(self.output_rom_path))

    def save_report(self, report: dict) -> None:
        """
        Sauvegarde le rapport de réinsertion.

        Args:
            report: Rapport à sauvegarder
        """
        print(f"💾 Sauvegarde rapport: {self.report_path}")

        with open(self.report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def print_results(self, report: dict) -> None:
        """
        Affiche les résultats de la réinsertion.

        Args:
            report: Rapport de réinsertion
        """
        print()
        print("=" * 80)
        print("RÉSULTATS DE LA RÉINSERTION")
        print("=" * 80)

        stats = report['statistics']
        print(f"Total textes:         {stats['total_texts']}")
        print(f"Succès:               {stats['successful']}")
        print(f"Échecs:               {stats['failed']}")
        print(f"Utilisé padding:      {stats['used_padding']}")
        print(f"Taux de succès:       {stats['success_rate']}")
        print()

        # Afficher warnings
        if report['warnings']:
            print("⚠️ AVERTISSEMENTS:")
            for warning in report['warnings'][:5]:
                print(f"  {warning['offset']}: {warning['error']}")
            if len(report['warnings']) > 5:
                print(f"  ... et {len(report['warnings']) - 5} autres")
            print()

    def print_success(self) -> None:
        """Affiche le message de succès."""
        print("=" * 80)
        print("✅ RÉINSERTION TERMINÉE")
        print("=" * 80)
        print()
        print(f"ROM traduite: {self.output_rom_path}")
        print(f"Rapport:      {self.report_path}")
        print()
        print("Prochaine étape:")
        print("  Tester la ROM sur un émulateur (mGBA, VBA, etc.)")
        print()

    def run(self) -> None:
        """
        Exécute le processus complet de réinsertion.

        Example:
            >>> applicator = TranslationApplicator()
            >>> applicator.run()
        """
        try:
            # Charger données
            self.load_translations()
            print()
            self.load_rom()

            # Appliquer traductions
            report = self.apply_translations()

            # Sauvegarder résultats
            self.save_rom()
            self.save_report(report)

            # Afficher résultats
            self.print_results(report)
            self.print_success()

        except Exception as e:
            print()
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


def main():
    """Point d'entrée principal."""
    print("=" * 80)
    print("10 - SMART TEXT REINSERTION (v2 - OOP)")
    print("=" * 80)
    print()

    # Gérer argument optionnel
    translation_path = None
    if len(sys.argv) > 1:
        translation_path = Path(sys.argv[1])
        if not translation_path.exists():
            print(f"❌ Erreur: Fichier non trouvé: {translation_path}")
            sys.exit(1)

    # Créer et exécuter applicateur
    applicator = TranslationApplicator(translation_path=translation_path)
    applicator.run()


if __name__ == "__main__":
    main()
