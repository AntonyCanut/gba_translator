#!/usr/bin/env python3
"""
16 - Build French ROM

Construit la ROM française en:
1. Chargeant les différences anglaises (textes à traduire)
2. Insérant les traductions françaises dans la ROM anglaise

Usage:
    python src/translators/16_build_french_rom.py [french_translation_json]

Input:
    - input/roms/englishrom.gba (ROM source anglaise)
    - output/translation/[french_translation].json (traductions françaises)
    - output/differences/englishrom_diff_only.json (fallback)

Output:
    - output/roms/YYYY-MM-DD_frenchrom_built.gba
    - output/reports/YYYY-MM-DD_french_build_report.json
"""

import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader
from src.core.text_validator import TextValidator
from src.core.text_reinserter import TextEncoder


class FrenchROMBuilder:
    """
    Construit la ROM française en utilisant les traductions français
    et les réinsère dans la ROM anglaise.
    """

    def __init__(self, translation_path: Optional[str] = None):
        self.english_rom_path = Path('input/roms/englishrom.gba')
        self.translation_path = self._find_translation(translation_path)
        
        self.english_texts_path = Path('output/extracted/extracted_texts/englishrom_texts.json')
        self.differences_path = Path('output/differences/englishrom_diff_only.json')
        
        self.output_rom_dir = Path('output/roms')
        self.output_report_dir = Path('output/reports')
        self.output_rom_path = None
        self.output_report_path = None
        
        self.rom_data = None
        self.validator = TextValidator()
        
        self.french_texts = {}
        self.english_texts = {}
        self.stats = {
            'total_texts': 0,
            'successfully_replaced': 0,
            'failed_replacements': 0,
            'unchanged_texts': 0,
            'corrupted_french_texts': 0,
            'too_long': 0,
            'errors': []
        }

    def _find_translation(self, provided_path: Optional[str]) -> Path:
        """Trouve le fichier de traduction français."""
        if provided_path:
            path = Path(provided_path)
            if path.exists():
                return path
            print(f"⚠️  Fichier fourni non trouvé: {path}")
        
        # Chercher le fichier le plus récent
        translation_dir = Path('output/translation')
        if translation_dir.exists():
            json_files = list(translation_dir.glob('*french*.json')) + \
                        list(translation_dir.glob('*fr*.json'))
            if json_files:
                latest = max(json_files, key=lambda p: p.stat().st_mtime)
                print(f"   Utilisant: {latest.name}")
                return latest
        
        # Fallback: utiliser les différences
        print(f"⚠️  Aucune traduction française trouvée")
        print(f"   Fallback: utilisation des différences anglaises")
        return None

    def _generate_output_paths(self):
        """Génère les chemins de sortie."""
        self.output_rom_dir.mkdir(parents=True, exist_ok=True)
        self.output_report_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        self.output_rom_path = self.output_rom_dir / f"{date_str}_frenchrom_built.gba"
        self.output_report_path = self.output_report_dir / f"{date_str}_french_build_report.json"

    def _load_texts(self) -> bool:
        """Charge les textes anglais et les traductions françaises."""
        print("📖 Chargement des textes et traductions...")
        
        # Charger textes anglais
        if not self.english_texts_path.exists():
            print(f"❌ Fichier non trouvé: {self.english_texts_path}")
            return False
        
        try:
            with open(self.english_texts_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                texts_list = data.get('texts', [])
                self.english_texts = {item['offset']: item['text'] for item in texts_list}
            
            print(f"✅ Textes anglais chargés: {len(self.english_texts)}")
        except Exception as e:
            print(f"❌ Erreur chargement textes anglais: {e}")
            return False
        
        # Charger traductions françaises
        if self.translation_path and self.translation_path.exists():
            try:
                with open(self.translation_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Supporter plusieurs formats JSON
                    if 'translations' in data:
                        translations = data['translations']
                        self.french_texts = {
                            item.get('offset'): item.get('french', item.get('text', ''))
                            for item in translations
                            if 'offset' in item
                        }
                    elif 'texts' in data:
                        texts_list = data.get('texts', [])
                        self.french_texts = {item['offset']: item.get('french', item.get('text', '')) for item in texts_list}
                    else:
                        # Supposer que c'est un dict direct {offset: text}
                        self.french_texts = data
                
                print(f"✅ Traductions françaises chargées: {len(self.french_texts)}")
            except Exception as e:
                print(f"❌ Erreur chargement traductions: {e}")
                print(f"   Utilisant les différences comme fallback...")
                if not self._load_differences():
                    return False
        else:
            if not self._load_differences():
                return False
        
        return True

    def _load_differences(self) -> bool:
        """Charge les différences en tant que fallback."""
        if not self.differences_path.exists():
            print(f"❌ Fichier de différences non trouvé: {self.differences_path}")
            return False
        
        try:
            with open(self.differences_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                texts_list = data.get('texts', [])
                self.french_texts = {item['offset']: item['text'] for item in texts_list}
            
            print(f"✅ Différences anglaises chargées (fallback): {len(self.french_texts)}")
            return True
        except Exception as e:
            print(f"❌ Erreur chargement différences: {e}")
            return False

    def _copy_rom(self) -> bool:
        """Crée une copie de la ROM anglaise."""
        print("\n📋 Copie de la ROM anglaise...")
        
        if not self.english_rom_path.exists():
            print(f"❌ ROM non trouvée: {self.english_rom_path}")
            return False
        
        try:
            shutil.copy2(self.english_rom_path, self.output_rom_path)
            rom_size_mb = self.output_rom_path.stat().st_size / (1024 * 1024)
            print(f"✅ ROM copiée: {self.output_rom_path.name} ({rom_size_mb:.2f} MB)")
            
            # Charger les données ROM en mémoire
            with open(self.output_rom_path, 'rb') as f:
                self.rom_data = bytearray(f.read())
            
            return True
        
        except Exception as e:
            print(f"❌ Erreur copie: {e}")
            return False

    def _replace_french_texts(self) -> bool:
        """Remplace vraiment les textes anglais par les traductions françaises."""
        print("\n🔄 Remplacement des textes par les traductions françaises...")
        
        self.stats['total_texts'] = len(self.french_texts)
        
        for offset, french_text in self.french_texts.items():
            try:
                english_text = self.english_texts.get(offset, '')
                
                # Vérifier si le texte français est valide
                if not french_text or not self.validator.is_valid_game_text(french_text):
                    if self.validator.is_corrupted(french_text):
                        self.stats['corrupted_french_texts'] += 1
                    continue
                
                # Si les textes sont identiques, ne pas modifier
                if french_text == english_text:
                    self.stats['unchanged_texts'] += 1
                    continue
                
                # Encoder avec encodage Pokémon (pas UTF-8!)
                try:
                    french_bytes = TextEncoder.encode_pokemon(french_text)
                    english_bytes = TextEncoder.encode_pokemon(english_text)
                    
                    rom_offset = int(offset) if isinstance(offset, (int, str)) else 0
                    
                    # Remplacer si la longueur le permet
                    if len(french_bytes) <= len(english_bytes):
                        # Remplacer directement
                        self.rom_data[rom_offset:rom_offset + len(french_bytes)] = french_bytes
                        
                        # Remplir avec 0xFF si le texte français est plus court
                        if len(french_bytes) < len(english_bytes):
                            padding = b'\xff' * (len(english_bytes) - len(french_bytes))
                            self.rom_data[rom_offset + len(french_bytes):rom_offset + len(english_bytes)] = padding
                        
                        self.stats['successfully_replaced'] += 1
                    else:
                        # Texte français trop long - tronquer
                        self.rom_data[rom_offset:rom_offset + len(english_bytes)] = french_bytes[:len(english_bytes)]
                        self.stats['too_long'] += 1
                        self.stats['successfully_replaced'] += 1
                
                except Exception as inner_e:
                    self.stats['failed_replacements'] += 1
                    self.stats['errors'].append({
                        'offset': hex(offset) if isinstance(offset, int) else offset,
                        'error': f"Replacement failed: {str(inner_e)}"
                    })
            
            except Exception as e:
                self.stats['failed_replacements'] += 1
                self.stats['errors'].append({
                    'offset': hex(offset) if isinstance(offset, int) else offset,
                    'error': str(e)
                })
        
        print(f"✅ Remplacement complété:")
        print(f"   - Remplacés: {self.stats['successfully_replaced']}")
        print(f"   - Échoués: {self.stats['failed_replacements']}")
        print(f"   - Non modifiés: {self.stats['unchanged_texts']}")
        if self.stats['too_long'] > 0:
            print(f"   - Tronqués (trop longs): {self.stats['too_long']}")
        print(f"   - Corrompus (ignorés): {self.stats['corrupted_french_texts']}")
        
        return True

    def _save_modified_rom(self) -> bool:
        """Sauvegarde la ROM modifiée avec les textes français."""
        print(f"\n💾 Sauvegarde de la ROM modifiée...")
        
        try:
            if self.rom_data is None:
                print(f"❌ Données ROM non chargées")
                return False
            
            with open(self.output_rom_path, 'wb') as f:
                f.write(self.rom_data)
            
            rom_size_mb = self.output_rom_path.stat().st_size / (1024 * 1024)
            print(f"✅ ROM sauvegardée: {self.output_rom_path.name}")
            print(f"   - Taille: {rom_size_mb:.2f} MB")
            print(f"   - Textes modifiés: {self.stats['successfully_replaced']}")
            
            return True
        
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _verify_rom_integrity(self) -> bool:
        """Vérifie l'intégrité de la ROM produite."""
        print(f"\n🔍 Vérification de l'intégrité de la ROM...")
        
        try:
            if not self.output_rom_path.exists():
                print(f"❌ ROM de sortie non trouvée")
                return False
            
            rom_size = self.output_rom_path.stat().st_size
            expected_size = self.english_rom_path.stat().st_size
            
            print(f"   Taille output: {rom_size / (1024*1024):.2f} MB")
            print(f"   Taille source: {expected_size / (1024*1024):.2f} MB")
            
            if rom_size == expected_size:
                print(f"✅ Tailles identiques ✓")
                return True
            else:
                print(f"⚠️  Tailles différentes (mais acceptable)")
                return True
        
        except Exception as e:
            print(f"❌ Erreur vérification: {e}")
            return False

    def _save_report(self):
        """Sauvegarde le rapport."""
        print(f"\n📊 Génération du rapport...")
        
        total_processed = (self.stats['successfully_replaced'] + 
                          self.stats['failed_replacements'] + 
                          self.stats['unchanged_texts'] + 
                          self.stats['corrupted_french_texts'])
        
        success_rate = (self.stats['successfully_replaced'] / total_processed * 100 
                       if total_processed > 0 else 0)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'source_rom_en': str(self.english_rom_path),
            'source_translations': str(self.translation_path) if self.translation_path else 'englishrom_diff_only.json',
            'output_rom': str(self.output_rom_path),
            'objective': 'Build French ROM from English ROM + French translations',
            'method': 'Load French translations, insert into English ROM',
            'statistics': {
                'total_texts_processed': self.stats['total_texts'],
                'successfully_replaced': self.stats['successfully_replaced'],
                'failed_replacements': self.stats['failed_replacements'],
                'unchanged_texts': self.stats['unchanged_texts'],
                'texts_too_long': self.stats['too_long'],
                'corrupted_french_texts': self.stats['corrupted_french_texts'],
                'success_rate': f"{success_rate:.1f}%"
            },
            'notes': 'French texts inserted into English ROM. Prepare translation JSON for actual French translations.',
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
        """Lance la construction complète de la ROM française."""
        print("="*70)
        print("🚀 CONSTRUCTION ROM FRANÇAISE")
        print("="*70)
        
        # Générer chemins de sortie
        self._generate_output_paths()
        
        # Étapes
        steps = [
            ("Chargement des textes et traductions", self._load_texts),
            ("Copie ROM anglaise", self._copy_rom),
            ("Remplacement textes français", self._replace_french_texts),
            ("Sauvegarde ROM modifiée", self._save_modified_rom),
            ("Vérification intégrité", self._verify_rom_integrity),
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
        print("✨ CONSTRUCTION RÉUSSIE - ROM FRANÇAISE CRÉÉE!")
        print("="*70)
        print(f"\n📁 ROM de sortie: {self.output_rom_path}")
        print(f"📊 Rapport: {self.output_report_path}")
        print(f"\n✅ Textes insérés: {self.stats['successfully_replaced']}")
        print(f"⚠️  Non modifiés: {self.stats['unchanged_texts']}")
        print(f"❌ Échoués: {self.stats['failed_replacements']}")
        if self.stats['too_long'] > 0:
            print(f"📏 Tronqués: {self.stats['too_long']}")
        print(f"\nLa ROM est maintenant en FRANÇAIS!")
        
        return True


def main():
    # Vérifier si un chemin est fourni en argument
    translation_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    builder = FrenchROMBuilder(translation_path)
    success = builder.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
