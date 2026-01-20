#!/usr/bin/env python3
"""
18 - Build Spanish ROM (SIMPLE - direct bytearray insertion with correct offsets)

Construit la ROM espagnole de manière simple en insérant directement
les bytes espagnols aux bons offsets dans la bytearray.

Usage:
    python src/translators/18_build_spanish_rom_simple.py

Input:
    - input/roms/englishrom.gba
    - input/roms/spanishrom.gba (pour extraire textes correctement encodés)
    - output/extracted/extracted_texts/englishrom_texts.json

Output:
    - output/roms/YYYY-MM-DD_spanishrom_simple.gba
    - output/reports/YYYY-MM-DD_spanish_build_simple_report.json
"""

import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_validator import TextValidator
from src.core.text_reinserter import TextEncoder


class SimpleSpanishROMBuilder:
    """
    Construit la ROM espagnole simplement:
    1. Copie la ROM anglaise
    2. Lit les bytes directement depuis la ROM espagnole
    3. Les copie aux mêmes offsets dans la ROM anglaise
    """

    def __init__(self):
        self.english_rom_path = Path('input/roms/englishrom.gba')
        self.spanish_rom_path = Path('input/roms/spanishrom.gba')
        self.english_texts_path = Path('output/extracted/extracted_texts/englishrom_texts.json')
        
        self.output_rom_dir = Path('output/roms')
        self.output_report_dir = Path('output/reports')
        self.output_rom_path = None
        self.output_report_path = None
        
        self.english_rom_data = None
        self.spanish_rom_data = None
        self.output_rom_data = None
        
        self.validator = TextValidator()
        
        self.stats = {
            'total_texts': 0,
            'successfully_copied': 0,
            'failed': 0,
            'unchanged': 0,
            'corrupted': 0,
            'errors': []
        }

    def _generate_output_paths(self):
        """Génère les chemins de sortie."""
        self.output_rom_dir.mkdir(parents=True, exist_ok=True)
        self.output_report_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        self.output_rom_path = self.output_rom_dir / f"{date_str}_spanishrom_simple.gba"
        self.output_report_path = self.output_report_dir / f"{date_str}_spanish_build_simple_report.json"

    def _load_roms(self) -> bool:
        """Charge les deux ROMs en mémoire."""
        print("📖 Chargement des ROMs...")
        
        if not self.english_rom_path.exists():
            print(f"❌ ROM anglaise non trouvée: {self.english_rom_path}")
            return False
        
        if not self.spanish_rom_path.exists():
            print(f"❌ ROM espagnole non trouvée: {self.spanish_rom_path}")
            return False
        
        try:
            with open(self.english_rom_path, 'rb') as f:
                self.english_rom_data = bytearray(f.read())
            
            with open(self.spanish_rom_path, 'rb') as f:
                self.spanish_rom_data = bytearray(f.read())
            
            # Copier la ROM anglaise pour la sortie
            self.output_rom_data = bytearray(self.english_rom_data)
            
            en_size = len(self.english_rom_data) / (1024 * 1024)
            es_size = len(self.spanish_rom_data) / (1024 * 1024)
            
            print(f"✅ ROMs chargées:")
            print(f"   - Anglaise: {en_size:.2f} MB")
            print(f"   - Espagnole: {es_size:.2f} MB")
            
            return True
        
        except Exception as e:
            print(f"❌ Erreur chargement: {e}")
            return False

    def _load_english_texts(self) -> dict:
        """Charge les textes anglais pour connaître les offsets et longueurs."""
        print("\n📖 Chargement des offsets et longueurs...")
        
        if not self.english_texts_path.exists():
            print(f"❌ Fichier non trouvé: {self.english_texts_path}")
            return {}
        
        try:
            with open(self.english_texts_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                texts_list = data.get('texts', [])
                
                # Créer un dict {offset: {text, length, encoding}}
                texts_dict = {}
                for item in texts_list:
                    offset = item['offset']
                    texts_dict[offset] = {
                        'text': item.get('text', ''),
                        'length': item.get('length', 0),
                        'encoding': item.get('encoding', 'pokemon')
                    }
                
                print(f"✅ {len(texts_dict)} offsets chargés")
                return texts_dict
        
        except Exception as e:
            print(f"❌ Erreur chargement: {e}")
            return {}

    def _copy_text_bytes(self, offset: int, length: int) -> bool:
        """
        Copie les bytes d'un texte depuis la ROM espagnole vers la ROM de sortie.
        """
        try:
            if offset < 0 or offset + length > len(self.spanish_rom_data):
                return False
            
            # Lire depuis la ROM espagnole
            spanish_bytes = self.spanish_rom_data[offset:offset + length]
            
            # Écrire dans la ROM de sortie
            self.output_rom_data[offset:offset + length] = spanish_bytes
            
            return True
        
        except Exception as e:
            self.stats['errors'].append({
                'offset': offset,
                'error': str(e)
            })
            return False

    def _build_rom(self, english_texts: dict) -> bool:
        """Copie les textes espagnols aux mêmes offsets."""
        print("\n🔄 Copie des textes espagnols...")
        
        self.stats['total_texts'] = len(english_texts)
        
        count = 0
        for offset, info in english_texts.items():
            try:
                length = info.get('length', 0)
                
                if length <= 0 or length > 1000:  # Santé check
                    self.stats['failed'] += 1
                    continue
                
                if self._copy_text_bytes(offset, length):
                    self.stats['successfully_copied'] += 1
                    count += 1
                    
                    if count % 10000 == 0:
                        print(f"   Traité: {count}/{self.stats['total_texts']}")
                else:
                    self.stats['failed'] += 1
            
            except Exception as e:
                self.stats['failed'] += 1
                self.stats['errors'].append({
                    'offset': offset,
                    'error': str(e)
                })
        
        print(f"✅ Copie complétée:")
        print(f"   - Textes copiés: {self.stats['successfully_copied']}")
        print(f"   - Échoués: {self.stats['failed']}")
        
        return True

    def _save_rom(self) -> bool:
        """Sauvegarde la ROM modifiée."""
        print(f"\n💾 Sauvegarde de la ROM...")
        
        try:
            with open(self.output_rom_path, 'wb') as f:
                f.write(self.output_rom_data)
            
            rom_size_mb = self.output_rom_path.stat().st_size / (1024 * 1024)
            print(f"✅ ROM sauvegardée: {self.output_rom_path.name} ({rom_size_mb:.2f} MB)")
            
            return True
        
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            return False

    def _save_report(self):
        """Sauvegarde le rapport."""
        print(f"\n📊 Génération du rapport...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'source_rom_en': str(self.english_rom_path),
            'source_rom_es': str(self.spanish_rom_path),
            'output_rom': str(self.output_rom_path),
            'objective': 'Build Spanish ROM by copying bytes from Spanish ROM to English ROM',
            'method': 'Direct bytearray copy at same offsets',
            'statistics': {
                'total_texts': self.stats['total_texts'],
                'successfully_copied': self.stats['successfully_copied'],
                'failed': self.stats['failed'],
                'unchanged': self.stats['unchanged'],
                'corrupted': self.stats['corrupted']
            },
            'notes': 'Copies bytes directly from Spanish ROM at the same offsets.',
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
        """Lance la construction complète."""
        print("="*70)
        print("🚀 CONSTRUCTION ROM ESPAGNOLE (SIMPLE)")
        print("="*70)
        
        self._generate_output_paths()
        
        # Charger les ROMs
        if not self._load_roms():
            return False
        
        # Charger les offsets
        english_texts = self._load_english_texts()
        if not english_texts:
            print("❌ Aucun texte à traiter")
            return False
        
        # Construire la ROM
        if not self._build_rom(english_texts):
            return False
        
        # Sauvegarder
        if not self._save_rom():
            return False
        
        if not self._save_report():
            return False
        
        print("\n" + "="*70)
        print("✨ CONSTRUCTION RÉUSSIE!")
        print("="*70)
        print(f"\n📁 ROM de sortie: {self.output_rom_path}")
        print(f"📊 Rapport: {self.output_report_path}")
        print(f"\nLa ROM est maintenant en ESPAGNOL!")
        
        return True


def main():
    builder = SimpleSpanishROMBuilder()
    success = builder.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
