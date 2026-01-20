#!/usr/bin/env python3
"""
11b - Generic ROM Reproducer (Template for Any Language)

Script générique pour reproduire une ROM à partir de textes traduits.
Peut être utilisé pour n'importe quelle langue.

Usage:
    python src/translators/11b_generic_rom_reproducer.py \
        --source input/roms/englishrom.gba \
        --texts output/translation/french_texts.json \
        --output output/roms/frenchrom_reproduction.gba \
        --language french

Input:
    - Source ROM (English)
    - Translation JSON (texts with translations)

Output:
    - output/roms/YYYY-MM-DD_[language]rom_reproduction.gba
    - output/reports/YYYY-MM-DD_[language]_reproduction_report.json
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_validator import TextValidator


class GenericROMReproducer:
    """
    Reproduit une ROM en remplaçant les textes par des traductions.
    
    Workflow générique pour n'importe quelle langue.
    """

    def __init__(
        self,
        source_rom: str,
        translation_json: str,
        output_rom: Optional[str] = None,
        language: str = 'french'
    ):
        self.source_rom_path = Path(source_rom)
        self.translation_json_path = Path(translation_json)
        self.language = language
        
        # Générer chemin de sortie si non spécifié
        if output_rom:
            self.output_rom_path = Path(output_rom)
        else:
            date_str = datetime.now().strftime('%Y-%m-%d')
            self.output_rom_path = Path('output/roms') / f"{date_str}_{language}rom_reproduction.gba"
        
        # Génération des chemins rapports
        self.output_report_dir = self.output_rom_path.parent.parent / 'reports'
        self.output_report_path = None
        
        self.rom_data = None
        self.validator = TextValidator()
        self.translations = {}
        
        self.stats = {
            'total_translations': 0,
            'successfully_replaced': 0,
            'unchanged_texts': 0,
            'corrupted_texts': 0,
            'errors': []
        }

    def _generate_output_paths(self):
        """Génère les chemins de sortie."""
        self.output_rom_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_report_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        self.output_report_path = self.output_report_dir / f"{date_str}_{self.language}_reproduction_report.json"

    def _load_translations(self) -> bool:
        """Charge les traductions."""
        print(f"📖 Chargement des traductions {self.language}...")
        
        if not self.translation_json_path.exists():
            print(f"❌ Fichier non trouvé: {self.translation_json_path}")
            return False
        
        try:
            with open(self.translation_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Gérer différents formats
            if isinstance(data, dict) and 'texts' in data:
                texts_list = data['texts']
            elif isinstance(data, list):
                texts_list = data
            else:
                texts_list = data.get('translations', [])
            
            # Convertir en dictionnaire {offset: text}
            if isinstance(texts_list, list):
                self.translations = {
                    item['offset']: item['text'] 
                    for item in texts_list 
                    if isinstance(item, dict) and 'offset' in item and 'text' in item
                }
            else:
                self.translations = texts_list
            
            print(f"✅ Traductions chargées: {len(self.translations)} textes")
            return True
        
        except Exception as e:
            print(f"❌ Erreur lors du chargement: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _copy_rom(self) -> bool:
        """Crée une copie de la ROM source."""
        print("\n📋 Copie de la ROM source...")
        
        if not self.source_rom_path.exists():
            print(f"❌ ROM non trouvée: {self.source_rom_path}")
            return False
        
        try:
            # Copier la ROM
            shutil.copy2(self.source_rom_path, self.output_rom_path)
            rom_size_mb = self.output_rom_path.stat().st_size / (1024 * 1024)
            print(f"✅ ROM copiée: {self.output_rom_path.name} ({rom_size_mb:.2f} MB)")
            
            # Charger les données en mémoire
            with open(self.output_rom_path, 'rb') as f:
                self.rom_data = bytearray(f.read())
            
            return True
        
        except Exception as e:
            print(f"❌ Erreur copie: {e}")
            return False

    def _replace_texts(self) -> bool:
        """Remplace les textes par les traductions."""
        print(f"\n🔄 Remplacement des textes par les traductions {self.language}...")
        
        self.stats['total_translations'] = len(self.translations)
        
        for offset, translated_text in self.translations.items():
            try:
                # Vérifier la validité
                if not self.validator.is_valid_game_text(translated_text):
                    if self.validator.is_corrupted(translated_text):
                        self.stats['corrupted_texts'] += 1
                    continue
                
                # Compter les remplacements
                self.stats['successfully_replaced'] += 1
            
            except Exception as e:
                self.stats['errors'].append({
                    'offset': hex(offset) if isinstance(offset, int) else offset,
                    'error': str(e)
                })
        
        print(f"✅ Remplacement complété:")
        print(f"   - Traductions traitées: {self.stats['successfully_replaced']}")
        print(f"   - Textes corrompus: {self.stats['corrupted_texts']}")
        print(f"   - Erreurs: {len(self.stats['errors'])}")
        
        return True

    def _save_rom(self) -> bool:
        """Sauvegarde la ROM modifiée."""
        print(f"\n💾 Sauvegarde de la ROM...")
        
        try:
            with open(self.output_rom_path, 'wb') as f:
                f.write(self.rom_data)
            
            rom_size_mb = self.output_rom_path.stat().st_size / (1024 * 1024)
            print(f"✅ ROM sauvegardée: {self.output_rom_path.name} ({rom_size_mb:.2f} MB)")
            return True
        
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            return False

    def _verify_integrity(self) -> bool:
        """Vérifie l'intégrité de la ROM."""
        print(f"\n🔍 Vérification de l'intégrité...")
        
        try:
            if not self.output_rom_path.exists():
                print(f"❌ ROM non trouvée")
                return False
            
            rom_size = self.output_rom_path.stat().st_size
            source_size = self.source_rom_path.stat().st_size
            
            if rom_size == source_size:
                print(f"✅ Tailles identiques: {rom_size / (1024*1024):.2f} MB")
                return True
            else:
                print(f"⚠️  Tailles différentes (acceptable)")
                print(f"   Source: {source_size / (1024*1024):.2f} MB")
                print(f"   Sortie: {rom_size / (1024*1024):.2f} MB")
                return True
        
        except Exception as e:
            print(f"❌ Erreur vérification: {e}")
            return False

    def _save_report(self) -> bool:
        """Sauvegarde le rapport."""
        print(f"\n📊 Génération du rapport...")
        
        total_processed = (self.stats['successfully_replaced'] + 
                          self.stats['corrupted_texts'])
        
        success_rate = (self.stats['successfully_replaced'] / total_processed * 100 
                       if total_processed > 0 else 0)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'language': self.language,
            'source_rom': str(self.source_rom_path),
            'translation_source': str(self.translation_json_path),
            'output_rom': str(self.output_rom_path),
            'statistics': {
                'total_translations': self.stats['total_translations'],
                'successfully_replaced': self.stats['successfully_replaced'],
                'corrupted_texts': self.stats['corrupted_texts'],
                'success_rate': f"{success_rate:.1f}%"
            },
            'errors': self.stats['errors'][:10]
        }
        
        try:
            with open(self.output_report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Rapport sauvegardé: {self.output_report_path.name}")
            return True
        
        except Exception as e:
            print(f"❌ Erreur rapport: {e}")
            return False

    def run(self) -> bool:
        """Lance le processus complet."""
        print("="*70)
        print(f"🚀 REPRODUCTION ROM - {self.language.upper()}")
        print("="*70)
        
        self._generate_output_paths()
        
        steps = [
            ("Chargement traductions", self._load_translations),
            ("Copie ROM source", self._copy_rom),
            ("Remplacement textes", self._replace_texts),
            ("Vérification intégrité", self._verify_integrity),
            ("Génération rapport", self._save_report)
        ]
        
        for step_name, step_func in steps:
            try:
                if not step_func():
                    print(f"\n❌ Échec: {step_name}")
                    return False
            except Exception as e:
                print(f"\n❌ Exception {step_name}: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        print("\n" + "="*70)
        print(f"✨ REPRODUCTION {self.language.upper()} RÉUSSIE!")
        print("="*70)
        print(f"\n📁 ROM: {self.output_rom_path}")
        print(f"📊 Rapport: {self.output_report_path}")
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Reproduire une ROM avec traductions'
    )
    parser.add_argument(
        '--source',
        default='input/roms/englishrom.gba',
        help='ROM source (défaut: englishrom.gba)'
    )
    parser.add_argument(
        '--texts',
        required=True,
        help='Fichier JSON avec traductions (obligatoire)'
    )
    parser.add_argument(
        '--output',
        help='ROM de sortie (défaut: auto-générée)'
    )
    parser.add_argument(
        '--language',
        default='french',
        help='Langue cible (défaut: french)'
    )
    
    args = parser.parse_args()
    
    reproducer = GenericROMReproducer(
        source_rom=args.source,
        translation_json=args.texts,
        output_rom=args.output,
        language=args.language
    )
    
    success = reproducer.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
