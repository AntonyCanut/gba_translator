#!/usr/bin/env python3
"""
13 - Test Simulation ROM Espagnole

Teste automatiquement 10% des traductions espagnoles pour valider
que notre système peut gérer tous les cas de débordement.

Usage:
    python src/translators/13_test_spanish_simulation.py

Input:
    - input/roms/englishrom.gba
    - input/roms/spanishrom.gba
    - output/differences/2026-01-13_diff_with_padding.json

Output:
    - output/tests/YYYY-MM-DD_spanish_simulation_report.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader
from src.core.padding_detector import PaddingDetector
from src.core.text_validator import TextValidator
from src.core.text_reinserter import SmartReinserter, ROMTranslationManager
from src.core.text_codec import TextDecoder


class SpanishSimulationTester:
    """
    Teste le système avec les traductions espagnoles réelles.

    Valide que notre système peut gérer tous les cas de débordement
    en simulant 10% des insertions espagnoles.

    Attributes:
        english_rom (ROMReader): ROM anglaise
        spanish_rom (ROMReader): ROM espagnole
        test_sample (List[dict]): Échantillon de textes à tester (1 sur 10)
        results (dict): Résultats des tests
    """

    def __init__(
        self,
        english_rom_path: str,
        spanish_rom_path: str,
        diff_with_padding_path: Path,
        sample_rate: int = 1
    ):
        """
        Initialise le testeur.

        Args:
            english_rom_path: Chemin vers ROM anglaise
            spanish_rom_path: Chemin vers ROM espagnole
            diff_with_padding_path: Chemin vers diff_with_padding.json
            sample_rate: Taux d'échantillonnage (1 = 100%, 10 = 10%, etc.)
        """
        self.english_rom = ROMReader(english_rom_path)
        self.spanish_rom = ROMReader(spanish_rom_path)
        self.diff_with_padding_path = diff_with_padding_path
        self.sample_rate = sample_rate

        self.test_sample: List[dict] = []
        self.results = {
            'total_tested': 0,
            'success': 0,
            'failed': 0,
            'cases': {
                'shorter': {'count': 0, 'success': 0},
                'same': {'count': 0, 'success': 0},
                'overflow_1_3': {'count': 0, 'success': 0},
                'overflow_4_6': {'count': 0, 'success': 0},
                'overflow_7_10': {'count': 0, 'success': 0},
                'overflow_11_plus': {'count': 0, 'success': 0},
            },
            'failures': []
        }

    def load_roms(self) -> None:
        """Charge les ROMs en mémoire."""
        print("📖 Chargement des ROMs...")
        self.english_rom.load()
        self.spanish_rom.load()
        print(f"   ROM anglaise: {self.english_rom.get_rom_info()['title']}")
        print(f"   ROM espagnole: {self.spanish_rom.get_rom_info()['title']}")

    def load_test_sample(self) -> None:
        """
        Charge les textes pour tests (avec taux d'échantillonnage).
        """
        print()
        print("📄 Chargement textes de test...")

        with open(self.diff_with_padding_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        texts = data['texts']

        # Appliquer taux d'échantillonnage
        self.test_sample = [texts[i] for i in range(0, len(texts), self.sample_rate)]

        print(f"   Total textes: {len(texts)}")
        print(f"   Textes à tester: {len(self.test_sample)} ({100//self.sample_rate}%)")

    def extract_spanish_text(self, offset: int, encoding: str) -> str:
        """
        Extrait le texte espagnol à un offset donné.

        Args:
            offset: Offset dans la ROM
            encoding: Type d'encodage ('ascii' ou 'pokemon')

        Returns:
            str: Texte espagnol décodé
        """
        text_bytes = bytearray()
        i = 0
        max_length = 200  # Sécurité

        while i < max_length:
            if offset + i >= len(self.spanish_rom.rom_data):
                break

            byte = self.spanish_rom.rom_data[offset + i]
            text_bytes.append(byte)

            # Terminateurs
            if encoding == 'ascii' and byte == 0x00:
                break
            if encoding == 'pokemon' and byte == 0xFF:
                break

            i += 1

        if encoding == 'ascii':
            return TextDecoder.decode_ascii(bytes(text_bytes))
        return TextDecoder.decode_pokemon(bytes(text_bytes))

    def categorize_overflow(self, overflow: int) -> str:
        """
        Catégorise le type de débordement.

        Args:
            overflow: Nombre de bytes de débordement

        Returns:
            str: Catégorie
        """
        if overflow < 0:
            return 'shorter'
        elif overflow == 0:
            return 'same'
        elif 1 <= overflow <= 3:
            return 'overflow_1_3'
        elif 4 <= overflow <= 6:
            return 'overflow_4_6'
        elif 7 <= overflow <= 10:
            return 'overflow_7_10'
        else:
            return 'overflow_11_plus'

    def test_text_insertion(self, text_entry: dict) -> Tuple[bool, dict]:
        """
        Teste l'insertion d'un texte espagnol.

        Args:
            text_entry: Entrée de texte avec padding info

        Returns:
            Tuple[bool, dict]: (success, test_details)
        """
        offset = text_entry['offset']
        english_text = text_entry['text']
        english_length = text_entry['length']
        encoding = text_entry['encoding']
        padding_available = text_entry['padding_available']
        real_max_length = text_entry['real_max_length']

        # Extraire texte espagnol
        spanish_text = self.extract_spanish_text(offset, encoding)
        spanish_length = len(spanish_text)

        # Calculer débordement
        overflow = spanish_length - english_length

        # Notre système peut-il gérer ce cas ?
        can_handle = spanish_length <= real_max_length

        # Catégoriser
        category = self.categorize_overflow(overflow)

        test_details = {
            'offset': f"0x{offset:08X}",
            'english_text': english_text,
            'english_length': english_length,
            'spanish_text': spanish_text,
            'spanish_length': spanish_length,
            'overflow': overflow,
            'padding_available': padding_available,
            'real_max_length': real_max_length,
            'category': category,
            'can_handle': can_handle,
            'success': can_handle
        }

        return can_handle, test_details

    def run_tests(self) -> None:
        """Exécute tous les tests sur l'échantillon."""
        print()
        print("🧪 Exécution des tests...")
        print()

        total = len(self.test_sample)
        skipped = 0

        for i, text_entry in enumerate(self.test_sample):
            if (i + 1) % 100 == 0:
                print(f"   Testé: {i + 1}/{total} (ignorés: {skipped})")

            success, details = self.test_text_insertion(text_entry)

            # Vérifier si c'est un faux positif (données corrompues)
            should_skip, skip_reason = TextValidator.should_skip_test(
                details['english_text'],
                details['spanish_text']
            )

            if should_skip:
                skipped += 1
                details['skipped'] = True
                details['skip_reason'] = skip_reason
                # Ne pas compter dans les statistiques
                continue

            self.results['total_tested'] += 1

            if success:
                self.results['success'] += 1
            else:
                self.results['failed'] += 1
                self.results['failures'].append(details)

            # Statistiques par catégorie
            category = details['category']
            self.results['cases'][category]['count'] += 1
            if success:
                self.results['cases'][category]['success'] += 1

        print(f"✅ {total} textes testés ({skipped} ignorés - données corrompues)")

    def generate_report(self) -> dict:
        """
        Génère un rapport détaillé.

        Returns:
            dict: Rapport complet
        """
        total = self.results['total_tested']
        success = self.results['success']
        failed = self.results['failed']

        success_rate = 100 * success / total if total > 0 else 0

        # Statistiques par catégorie
        cases_stats = {}
        for category, data in self.results['cases'].items():
            count = data['count']
            success_cat = data['success']
            if count > 0:
                rate = 100 * success_cat / count
                cases_stats[category] = {
                    'count': count,
                    'success': success_cat,
                    'failed': count - success_cat,
                    'success_rate': f"{rate:.1f}%"
                }

        report = {
            'test_date': datetime.now().isoformat(),
            'sample_size': '10% (1 texte sur 10)',
            'summary': {
                'total_tested': total,
                'success': success,
                'failed': failed,
                'success_rate': f"{success_rate:.1f}%"
            },
            'by_category': cases_stats,
            'failures': self.results['failures'][:20],  # Top 20 échecs
            'total_failures': len(self.results['failures'])
        }

        return report

    def print_results(self, report: dict) -> None:
        """
        Affiche les résultats des tests.

        Args:
            report: Rapport généré
        """
        print()
        print("=" * 80)
        print("RÉSULTATS DES TESTS")
        print("=" * 80)

        summary = report['summary']
        print(f"Total testé:       {summary['total_tested']}")
        print(f"Succès:            {summary['success']}")
        print(f"Échecs:            {summary['failed']}")
        print(f"Taux de succès:    {summary['success_rate']}")
        print()

        print("=" * 80)
        print("PAR CATÉGORIE")
        print("=" * 80)

        for category, stats in report['by_category'].items():
            print(f"\n{category.replace('_', ' ').title()}:")
            print(f"  Total:         {stats['count']}")
            print(f"  Succès:        {stats['success']}")
            print(f"  Échecs:        {stats['failed']}")
            print(f"  Taux:          {stats['success_rate']}")

        print()

        if report['total_failures'] > 0:
            print("=" * 80)
            print("ÉCHECS DÉTECTÉS")
            print("=" * 80)
            print()

            for i, failure in enumerate(report['failures'][:10], 1):
                print(f"{i}. Offset {failure['offset']} - {failure['category']}")
                print(f"   EN: \"{failure['english_text']}\" ({failure['english_length']})")
                print(f"   ES: \"{failure['spanish_text']}\" ({failure['spanish_length']})")
                print(f"   Débordement: {failure['overflow']} bytes")
                print(f"   Padding disponible: {failure['padding_available']}")
                print(f"   Max autorisé: {failure['real_max_length']}")
                print()

            if report['total_failures'] > 10:
                print(f"... et {report['total_failures'] - 10} autres échecs")
                print()

    def save_report(self, report: dict) -> Path:
        """
        Sauvegarde le rapport en JSON.

        Args:
            report: Rapport à sauvegarder

        Returns:
            Path: Chemin du fichier sauvegardé
        """
        output_dir = Path('output/tests')
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        report_path = output_dir / f"{date_str}_spanish_simulation_report.json"

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return report_path

    def run(self) -> dict:
        """
        Exécute le test complet.

        Returns:
            dict: Rapport final
        """
        self.load_roms()
        self.load_test_sample()
        self.run_tests()
        report = self.generate_report()
        self.print_results(report)
        report_path = self.save_report(report)

        print("=" * 80)
        print("✅ TESTS TERMINÉS")
        print("=" * 80)
        print()
        print(f"Rapport sauvegardé: {report_path}")
        print()

        return report


def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test simulation ROM espagnole",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python src/translators/13_test_spanish_simulation.py         # Teste 100%
  python src/translators/13_test_spanish_simulation.py --sample 10  # Teste 10%
        """
    )
    parser.add_argument('--sample', type=int, default=1, 
                        help='Taux d\'échantillonnage (1=100%%, 10=10%%, etc.)')
    args = parser.parse_args()
    
    print("=" * 80)
    print("13 - TEST SIMULATION ROM ESPAGNOLE")
    print("=" * 80)
    print()
    
    sample_percent = 100 // args.sample
    print(f"Test automatique de {sample_percent}% des traductions espagnoles")
    if args.sample > 1:
        print(f"(1 texte sur {args.sample} pour validation du système)")
    else:
        print("(Test complet - TOUS les textes)")
    print()

    # Chemins
    english_rom = 'input/roms/englishrom.gba'
    spanish_rom = 'input/roms/spanishrom.gba'
    diff_with_padding = Path('output/differences/2026-01-13_diff_with_padding.json')

    # Vérifier existence des fichiers
    if not Path(english_rom).exists():
        print(f"❌ Erreur: {english_rom} non trouvé")
        sys.exit(1)

    if not Path(spanish_rom).exists():
        print(f"❌ Erreur: {spanish_rom} non trouvé")
        sys.exit(1)

    if not diff_with_padding.exists():
        print(f"❌ Erreur: {diff_with_padding} non trouvé")
        print("   Exécuter d'abord: python src/translators/06_detect_padding.py")
        sys.exit(1)

    try:
        # Créer et exécuter testeur
        tester = SpanishSimulationTester(
            english_rom,
            spanish_rom,
            diff_with_padding,
            sample_rate=args.sample
        )

        report = tester.run()

        # Vérifier si des échecs
        if report['summary']['failed'] > 0:
            print("⚠️ ATTENTION: Des échecs ont été détectés")
            print("   Voir le rapport pour plus de détails")
            sys.exit(1)
        else:
            print("🎉 Tous les tests sont passés avec succès!")
            sys.exit(0)

    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
