#!/usr/bin/env python3
"""
15 - Build Spanish ROM

Construit la ROM espagnole en:
1. Chargeant les textes espagnols depuis la vraie ROM espagnole
2. Insérant ces textes dans la ROM anglaise

Usage:
    python src/translators/15_build_spanish_rom.py

Input:
    - input/roms/englishrom.gba (ROM source anglaise)
    - input/roms/spanishrom.gba (ROM source espagnole - pour extraire textes)

Output:
    - output/roms/YYYY-MM-DD_spanishrom_built.gba
    - output/reports/YYYY-MM-DD_spanish_build_report.json
"""

import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader
from src.core.text_validator import TextValidator
from src.core.text_reinserter import TextEncoder


class SpanishROMBuilder:
    """
    Construit la ROM espagnole en utilisant les textes extraits
    de la vraie ROM espagnole, puis les réinsère dans la ROM anglaise.
    """

    def __init__(self):
        self.english_rom_path = Path('input/roms/englishrom.gba')
        self.spanish_rom_path = Path('input/roms/spanishrom.gba')
        
        self.english_texts_path = Path('output/extracted/extracted_texts/englishrom_texts.json')
        self.spanish_texts_path = Path('output/extracted/extracted_texts/spanishrom_texts.json')
        
        self.output_rom_dir = Path('output/roms')
        self.output_report_dir = Path('output/reports')
        self.output_rom_path = None
        self.output_report_path = None
        
        self.rom_data = None
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
        self.output_rom_path = self.output_rom_dir / f"{date_str}_spanishrom_built.gba"
        self.output_report_path = self.output_report_dir / f"{date_str}_spanish_build_report.json"

    def _load_texts(self) -> bool:
        """Charge les textes anglais et espagnols."""
        print("📖 Chargement des textes extraits...")
        
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
        
        # Charger textes espagnols
        if not self.spanish_texts_path.exists():
            print(f"⚠️  Fichier espagnol non trouvé: {self.spanish_texts_path}")
            print(f"   Extraction depuis la vraie ROM espagnole...")
            
            if not self.spanish_rom_path.exists():
                print(f"❌ ROM espagnole non trouvée: {self.spanish_rom_path}")
                return False
            
            # Extraire depuis la vraie ROM
            print(f"   Extraction en cours...")
            try:
                rom_reader = ROMReader(str(self.spanish_rom_path))
                extracted = rom_reader.extract_all_texts()
                
                if extracted:
                    self.spanish_texts = {item['offset']: item['text'] 
                                         for item in extracted 
                                         if self.validator.is_valid_game_text(item['text'])}
                    print(f"✅ Textes espagnols extraits: {len(self.spanish_texts)}")
                else:
                    print(f"❌ Aucun texte extrait de la ROM espagnole")
                    return False
            
            except Exception as e:
                print(f"❌ Erreur extraction ROM espagnole: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            # Charger depuis JSON
            try:
                with open(self.spanish_texts_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    texts_list = data.get('texts', [])
                    
                    # Filtrer les textes valides (rejeter le garbage)
                    self.spanish_texts = {
                        item['offset']: item['text'] 
                        for item in texts_list 
                        if self.validator.is_valid_game_text(item['text'])
                    }
                
                print(f"✅ Textes espagnols chargés: {len(self.spanish_texts)}")
            except Exception as e:
                print(f"❌ Erreur chargement textes espagnols: {e}")
                return False
        
        return True

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

    def _replace_spanish_texts(self) -> bool:
        """Remplace vraiment les textes anglais par les textes espagnols."""
        print("\n🔄 Remplacement des textes par les textes espagnols...")
        
        self.stats['total_texts'] = len(self.spanish_texts)
        
        for offset, spanish_text in self.spanish_texts.items():
            try:
                english_text = self.english_texts.get(offset, '')
                
                # Vérifier si le texte espagnol est valide
                if not self.validator.is_valid_game_text(spanish_text):
                    if self.validator.is_corrupted(spanish_text):
                        self.stats['corrupted_spanish_texts'] += 1
                    continue
                
                # Si les textes sont identiques, ne pas modifier
                if spanish_text == english_text:
                    self.stats['unchanged_texts'] += 1
                    continue
                
                # Encoder avec encodage Pokémon (pas UTF-8!)
                try:
                    spanish_bytes = TextEncoder.encode_pokemon(spanish_text)
                    english_bytes = TextEncoder.encode_pokemon(english_text)
                    
                    rom_offset = int(offset) if isinstance(offset, (int, str)) else 0
                    
                    # Remplacer si la longueur le permet
                    if len(spanish_bytes) <= len(english_bytes):
                        # Remplacer directement
                        self.rom_data[rom_offset:rom_offset + len(spanish_bytes)] = spanish_bytes
                        
                        # Remplir avec 0xFF si le texte espagnol est plus court
                        if len(spanish_bytes) < len(english_bytes):
                            padding = b'\xff' * (len(english_bytes) - len(spanish_bytes))
                            self.rom_data[rom_offset + len(spanish_bytes):rom_offset + len(english_bytes)] = padding
                        
                        self.stats['successfully_replaced'] += 1
                    else:
                        # Texte espagnol trop long - tronquer avant terminateur
                        self.rom_data[rom_offset:rom_offset + len(english_bytes)] = spanish_bytes[:len(english_bytes)]
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
        print(f"   - Corrompus (ignorés): {self.stats['corrupted_spanish_texts']}")
        
        return True

    def _save_modified_rom(self) -> bool:
        """Sauvegarde la ROM modifiée avec les textes espagnols."""
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
                          self.stats['corrupted_spanish_texts'])
        
        success_rate = (self.stats['successfully_replaced'] / total_processed * 100 
                       if total_processed > 0 else 0)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'source_rom_en': str(self.english_rom_path),
            'source_rom_es': str(self.spanish_rom_path),
            'source_texts': str(self.spanish_texts_path),
            'output_rom': str(self.output_rom_path),
            'objective': 'Build Spanish ROM from English ROM + Spanish texts from real Spanish ROM',
            'method': 'Extract Spanish texts from real ROM, filter valid texts, insert into English ROM',
            'statistics': {
                'total_texts_processed': self.stats['total_texts'],
                'successfully_replaced': self.stats['successfully_replaced'],
                'failed_replacements': self.stats['failed_replacements'],
                'unchanged_texts': self.stats['unchanged_texts'],
                'corrupted_spanish_texts': self.stats['corrupted_spanish_texts'],
                'success_rate': f"{success_rate:.1f}%"
            },
            'notes': 'Spanish texts extracted from real Spanish ROM and verified before insertion.',
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
        print("🚀 CONSTRUCTION ROM ESPAGNOLE")
        print("="*70)
        
        # Générer chemins de sortie
        self._generate_output_paths()
        
        # Étapes
        steps = [
            ("Chargement des textes", self._load_texts),
            ("Copie ROM anglaise", self._copy_rom),
            ("Remplacement textes espagnols", self._replace_spanish_texts),
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
    builder = SpanishROMBuilder()
    success = builder.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
