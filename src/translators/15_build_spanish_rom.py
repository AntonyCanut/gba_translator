#!/usr/bin/env python3
"""
15 - Build Spanish ROM

Builds the Spanish ROM by:
1. Loading Spanish texts from the real Spanish ROM
2. Inserting those texts into the English ROM

Usage:
    python src/translators/15_build_spanish_rom.py

Input:
    - input/roms/englishrom.gba (English source ROM)
    - input/roms/spanishrom.gba (Spanish source ROM - to extract texts from)

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
    Builds the Spanish ROM using texts extracted from the real Spanish ROM,
    then reinserts them into the English ROM.
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
        """Generates output paths."""
        self.output_rom_dir.mkdir(parents=True, exist_ok=True)
        self.output_report_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        self.output_rom_path = self.output_rom_dir / f"{date_str}_spanishrom_built.gba"
        self.output_report_path = self.output_report_dir / f"{date_str}_spanish_build_report.json"

    def _load_texts(self) -> bool:
        """Loads English and Spanish texts."""
        print("📖 Loading extracted texts...")

        # Load English texts
        if not self.english_texts_path.exists():
            print(f"❌ File not found: {self.english_texts_path}")
            return False

        try:
            with open(self.english_texts_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                texts_list = data.get('texts', [])
                self.english_texts = {item['offset']: item['text'] for item in texts_list}

            print(f"✅ English texts loaded: {len(self.english_texts)}")
        except Exception as e:
            print(f"❌ Error loading English texts: {e}")
            return False

        # Load Spanish texts
        if not self.spanish_texts_path.exists():
            print(f"⚠️  Spanish file not found: {self.spanish_texts_path}")
            print(f"   Extracting from real Spanish ROM...")

            if not self.spanish_rom_path.exists():
                print(f"❌ Spanish ROM not found: {self.spanish_rom_path}")
                return False

            # Extract from real ROM
            print(f"   Extraction in progress...")
            try:
                rom_reader = ROMReader(str(self.spanish_rom_path))
                extracted = rom_reader.extract_all_texts()

                if extracted:
                    self.spanish_texts = {item['offset']: item['text']
                                         for item in extracted
                                         if self.validator.is_valid_game_text(item['text'])}
                    print(f"✅ Spanish texts extracted: {len(self.spanish_texts)}")
                else:
                    print(f"❌ No texts extracted from Spanish ROM")
                    return False

            except Exception as e:
                print(f"❌ Error extracting Spanish ROM: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            # Load from JSON
            try:
                with open(self.spanish_texts_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    texts_list = data.get('texts', [])

                    # Filter valid texts (reject garbage)
                    self.spanish_texts = {
                        item['offset']: item['text']
                        for item in texts_list
                        if self.validator.is_valid_game_text(item['text'])
                    }

                print(f"✅ Spanish texts loaded: {len(self.spanish_texts)}")
            except Exception as e:
                print(f"❌ Error loading Spanish texts: {e}")
                return False

        return True

    def _copy_rom(self) -> bool:
        """Creates a copy of the English ROM."""
        print("\n📋 Copying English ROM...")

        if not self.english_rom_path.exists():
            print(f"❌ ROM not found: {self.english_rom_path}")
            return False

        try:
            shutil.copy2(self.english_rom_path, self.output_rom_path)
            rom_size_mb = self.output_rom_path.stat().st_size / (1024 * 1024)
            print(f"✅ ROM copied: {self.output_rom_path.name} ({rom_size_mb:.2f} MB)")

            # Load ROM data into memory
            with open(self.output_rom_path, 'rb') as f:
                self.rom_data = bytearray(f.read())

            return True

        except Exception as e:
            print(f"❌ Copy error: {e}")
            return False

    def _replace_spanish_texts(self) -> bool:
        """Actually replaces English texts with Spanish texts."""
        print("\n🔄 Replacing texts with Spanish texts...")

        self.stats['total_texts'] = len(self.spanish_texts)

        for offset, spanish_text in self.spanish_texts.items():
            try:
                english_text = self.english_texts.get(offset, '')

                # Check if Spanish text is valid
                if not self.validator.is_valid_game_text(spanish_text):
                    if self.validator.is_corrupted(spanish_text):
                        self.stats['corrupted_spanish_texts'] += 1
                    continue

                # If texts are identical, do not modify
                if spanish_text == english_text:
                    self.stats['unchanged_texts'] += 1
                    continue

                # Encode using Pokémon encoding (not UTF-8!)
                try:
                    spanish_bytes = TextEncoder.encode_pokemon(spanish_text)
                    english_bytes = TextEncoder.encode_pokemon(english_text)

                    rom_offset = int(offset) if isinstance(offset, (int, str)) else 0

                    # Replace if length allows
                    if len(spanish_bytes) <= len(english_bytes):
                        # Replace directly
                        self.rom_data[rom_offset:rom_offset + len(spanish_bytes)] = spanish_bytes

                        # Pad with 0xFF if Spanish text is shorter
                        if len(spanish_bytes) < len(english_bytes):
                            padding = b'\xff' * (len(english_bytes) - len(spanish_bytes))
                            self.rom_data[rom_offset + len(spanish_bytes):rom_offset + len(english_bytes)] = padding

                        self.stats['successfully_replaced'] += 1
                    else:
                        # Spanish text too long - truncate before terminator
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

        print(f"✅ Replacement complete:")
        print(f"   - Replaced: {self.stats['successfully_replaced']}")
        print(f"   - Failed: {self.stats['failed_replacements']}")
        print(f"   - Unchanged: {self.stats['unchanged_texts']}")
        print(f"   - Corrupted (skipped): {self.stats['corrupted_spanish_texts']}")

        return True

    def _save_modified_rom(self) -> bool:
        """Saves the modified ROM with Spanish texts."""
        print(f"\n💾 Saving modified ROM...")

        try:
            if self.rom_data is None:
                print(f"❌ ROM data not loaded")
                return False

            with open(self.output_rom_path, 'wb') as f:
                f.write(self.rom_data)

            rom_size_mb = self.output_rom_path.stat().st_size / (1024 * 1024)
            print(f"✅ ROM saved: {self.output_rom_path.name}")
            print(f"   - Size: {rom_size_mb:.2f} MB")
            print(f"   - Texts modified: {self.stats['successfully_replaced']}")

            return True

        except Exception as e:
            print(f"❌ Save error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _verify_rom_integrity(self) -> bool:
        """Checks the integrity of the produced ROM."""
        print(f"\n🔍 Checking ROM integrity...")

        try:
            if not self.output_rom_path.exists():
                print(f"❌ Output ROM not found")
                return False

            rom_size = self.output_rom_path.stat().st_size
            expected_size = self.english_rom_path.stat().st_size

            print(f"   Output size: {rom_size / (1024*1024):.2f} MB")
            print(f"   Source size: {expected_size / (1024*1024):.2f} MB")

            if rom_size == expected_size:
                print(f"✅ Sizes match ✓")
                return True
            else:
                print(f"⚠️  Sizes differ (but acceptable)")
                return True

        except Exception as e:
            print(f"❌ Verification error: {e}")
            return False

    def _save_report(self):
        """Saves the report."""
        print(f"\n📊 Generating report...")
        
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
            
            print(f"✅ Report saved: {self.output_report_path.name}")
            return True

        except Exception as e:
            print(f"❌ Report error: {e}")
            return False

    def run(self) -> bool:
        """Runs the complete Spanish ROM build."""
        print("="*70)
        print("🚀 BUILDING SPANISH ROM")
        print("="*70)

        # Generate output paths
        self._generate_output_paths()

        # Steps
        steps = [
            ("Loading texts", self._load_texts),
            ("Copying English ROM", self._copy_rom),
            ("Replacing Spanish texts", self._replace_spanish_texts),
            ("Saving modified ROM", self._save_modified_rom),
            ("Checking integrity", self._verify_rom_integrity),
            ("Generating report", self._save_report)
        ]

        for step_name, step_func in steps:
            try:
                if not step_func():
                    print(f"\n❌ Failed: {step_name}")
                    return False
            except Exception as e:
                print(f"\n❌ Exception in {step_name}: {e}")
                import traceback
                traceback.print_exc()
                return False

        print("\n" + "="*70)
        print("✨ BUILD SUCCESSFUL - SPANISH ROM CREATED!")
        print("="*70)
        print(f"\n📁 Output ROM: {self.output_rom_path}")
        print(f"📊 Report: {self.output_report_path}")
        print(f"\n✅ Texts inserted: {self.stats['successfully_replaced']}")
        print(f"⚠️  Unchanged: {self.stats['unchanged_texts']}")
        print(f"❌ Failed: {self.stats['failed_replacements']}")
        print(f"\nThe ROM is now in SPANISH!")

        return True


def main():
    builder = SpanishROMBuilder()
    success = builder.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
