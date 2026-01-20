#!/usr/bin/env python3
"""
17 - Build Spanish ROM (CORRECT using ROMTranslationManager)

Construît correctement la ROM espagnole en utilisant ROMTranslationManager
qui gère les offsets et l'encodage proprement.

Usage:
    python src/translators/17_build_spanish_rom_correct.py

Input:
    - input/roms/englishrom.gba (ROM source anglaise)
    - output/extracted/extracted_texts/spanishrom_texts.json (textes espagnols)

Output:
    - output/roms/YYYY-MM-DD_spanishrom_correct.gba
    - output/reports/YYYY-MM-DD_spanish_build_correct_report.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_reinserter import ROMTranslationManager
from src.core.text_validator import TextValidator


class SpanishROMBuilderCorrect:
    """
    Construit la ROM espagnole correctement en utilisant ROMTranslationManager.
    """

    def __init__(self):
        self.english_rom_path = Path('input/roms/englishrom.gba')
        self.spanish_texts_path = Path('output/extracted/extracted_texts/spanishrom_texts.json')
        self.english_texts_path = Path('output/extracted/extracted_texts/englishrom_texts.json')
        
        self.output_rom_dir = Path('output/roms')
        self.output_report_dir = Path('output/reports')
        self.output_rom_path = None
        self.output_report_path = None
        
        self.rom_manager = None
        self.validator = TextValidator()
        
        self.spanish_texts = {}
        self.english_texts = {}
        self.stats = {
            'total_texts': 0,
            'successfully_replaced': 0,
            'failed_replacements': 0,
            'unchanged_texts': 0,
            'corrupted_spanish_texts': 0,
            'errors': []
        }

    def _generate_output_paths(self):
        """Génère les chemins de sortie."""
        self.output_rom_dir.mkdir(parents=True, exist_ok=True)
        self.output_report_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        self.output_rom_path = self.output_rom_dir / f"{date_str}_spanishrom_correct.gba"
        self.output_report_path = self.output_report_dir / f"{date_str}_spanish_build_correct_report.json"

    def _load_texts(self) -> bool:
        """Charge les textes anglais et espagnols."""
        print("📖 Chargement des textes extraits...")
        
        if not self.spanish_texts_path.exists():
            print(f"❌ Fichier non trouvé: {self.spanish_texts_path}")
            return False
        
        if not self.english_texts_path.exists():
            print(f"❌ Fichier non trouvé: {self.english_texts_path}")
            return False
        
        try:
            # Charger JSON et convertir liste en dictionnaire {offset: item}
            with open(self.spanish_texts_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                texts_list = data.get('texts', [])
                self.spanish_texts = texts_list  # Garder comme liste pour ROMTranslationManager
            
            with open(self.english_texts_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                texts_list = data.get('texts', [])
                self.english_texts = {item['offset']: item['text'] for item in texts_list}
            
            print(f"✅ Textes chargés:")
            print(f"   - Textes anglais: {len(self.english_texts)}")
            print(f"   - Textes espagnols: {len(self.spanish_texts)}")
            
            return True
        
        except Exception as e:
            print(f"❌ Erreur lors du chargement: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _build_translations_list(self) -> List[dict]:
        """
        Construit la liste de traductions pour ROMTranslationManager.
        
        Format attendu:
        [
            {
                'offset': int,
                'english': str,
                'spanish': str,
                'encoding': 'pokemon'
            },
            ...
        ]
        """
        print("\n🔄 Préparation des traductions...")
        
        translations = []
        skipped = 0
        
        for item in self.spanish_texts:
            try:
                offset = item.get('offset')
                spanish_text = item.get('text', '')
                english_text = self.english_texts.get(offset, '')
                encoding = item.get('encoding', 'pokemon')
                
                # Vérifier si le texte espagnol est valide
                if not spanish_text or not self.validator.is_valid_game_text(spanish_text):
                    if self.validator.is_corrupted(spanish_text):
                        self.stats['corrupted_spanish_texts'] += 1
                    skipped += 1
                    continue
                
                # Si les textes sont identiques, skip
                if spanish_text == english_text:
                    self.stats['unchanged_texts'] += 1
                    continue
                
                # Ajouter à la liste de traductions
                translations.append({
                    'offset': offset,
                    'english': english_text,
                    'spanish': spanish_text,
                    'encoding': encoding
                })
                
                self.stats['successfully_replaced'] += 1
            
            except Exception as e:
                self.stats['failed_replacements'] += 1
                self.stats['errors'].append({
                    'offset': item.get('offset', 'unknown'),
                    'error': str(e)
                })
        
        print(f"✅ Traductions préparées:")
        print(f"   - Total à remplacer: {len(translations)}")
        print(f"   - Non modifiés (identiques): {self.stats['unchanged_texts']}")
        print(f"   - Corrompus (ignorés): {self.stats['corrupted_spanish_texts']}")
        print(f"   - Échoués: {self.stats['failed_replacements']}")
        
        self.stats['total_texts'] = len(self.spanish_texts)
        
        return translations

    def _build_rom(self, translations: List[dict]) -> bool:
        """Construit la ROM espagnole en réinsérant les traductions."""
        print(f"\n📋 Copie de la ROM anglaise...")
        
        if not self.english_rom_path.exists():
            print(f"❌ ROM non trouvée: {self.english_rom_path}")
            return False
        
        try:
            # Charger la ROM avec ROMTranslationManager
            print(f"📖 Chargement ROM: {self.english_rom_path}")
            self.rom_manager = ROMTranslationManager(str(self.english_rom_path))
            rom_info = self.rom_manager.get_rom_info()
            print(f"   ROM: {rom_info['title']}")
            print(f"   Taille: {rom_info['size_mb']} MB")
            
            # Convertir les traductions au format attendu par apply_translations
            translations_formatted = []
            for trans in translations:
                translations_formatted.append({
                    'offset': trans['offset'],
                    'text': trans['spanish'],
                    'encoding': trans.get('encoding', 'pokemon')
                })
            
            print(f"\n🔄 Réinsertion des textes espagnols...")
            report = self.rom_manager.apply_translations(translations_formatted)
            
            print(f"✅ Réinsertion complétée:")
            print(f"   - Traductions appliquées: {len(translations_formatted)}")
            
            # Sauvegarder la ROM
            print(f"\n💾 Sauvegarde de la ROM...")
            self.rom_manager.save_rom(str(self.output_rom_path))
            rom_size_mb = self.output_rom_path.stat().st_size / (1024 * 1024)
            print(f"✅ ROM sauvegardée: {self.output_rom_path.name} ({rom_size_mb:.2f} MB)")
            
            return True
        
        except Exception as e:
            print(f"❌ Erreur construction ROM: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _save_report(self):
        """Sauvegarde le rapport."""
        print(f"\n📊 Génération du rapport...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'source_rom': str(self.english_rom_path),
            'source_texts': str(self.spanish_texts_path),
            'output_rom': str(self.output_rom_path),
            'objective': 'Build Spanish ROM from English ROM + Spanish texts (CORRECT)',
            'method': 'Using ROMTranslationManager with proper encoding',
            'statistics': {
                'total_texts_processed': self.stats['total_texts'],
                'successfully_replaced': self.stats['successfully_replaced'],
                'failed_replacements': self.stats['failed_replacements'],
                'unchanged_texts': self.stats['unchanged_texts'],
                'corrupted_spanish_texts': self.stats['corrupted_spanish_texts']
            },
            'notes': 'Uses ROMTranslationManager for correct offset and encoding handling.',
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
        """Lance la construction complète de la ROM espagnole."""
        print("="*70)
        print("🚀 CONSTRUCTION ROM ESPAGNOLE (CORRECTE)")
        print("="*70)
        
        # Générer chemins de sortie
        self._generate_output_paths()
        
        # Charger les textes
        if not self._load_texts():
            print(f"\n❌ Échec: Chargement des textes")
            return False
        
        # Préparer les traductions
        translations = self._build_translations_list()
        if not translations:
            print(f"\n❌ Aucune traduction à appliquer")
            return False
        
        # Construire la ROM
        if not self._build_rom(translations):
            print(f"\n❌ Échec: Construction ROM")
            return False
        
        # Sauvegarder le rapport
        if not self._save_report():
            print(f"\n❌ Échec: Génération rapport")
            return False
        
        print("\n" + "="*70)
        print("✨ CONSTRUCTION RÉUSSIE - ROM ESPAGNOLE CRÉÉE!")
        print("="*70)
        print(f"\n📁 ROM de sortie: {self.output_rom_path}")
        print(f"📊 Rapport: {self.output_report_path}")
        print(f"\n✅ Textes insérés: {self.stats['successfully_replaced']}")
        print(f"⚠️  Non modifiés: {self.stats['unchanged_texts']}")
        print(f"❌ Échoués: {self.stats['failed_replacements']}")
        print(f"\nLa ROM est maintenant en ESPAGNOL!")
        
        return True


def main():
    builder = SpanishROMBuilderCorrect()
    success = builder.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
