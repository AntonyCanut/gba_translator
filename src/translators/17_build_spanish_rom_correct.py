#!/usr/bin/env python3
"""
17 - Build Spanish ROM (CORRECT using ROMTranslationManager)

Correctly builds the Spanish ROM using ROMTranslationManager
which handles offsets and encoding properly.

Usage:
    python src/translators/17_build_spanish_rom_correct.py

Input:
    - input/roms/englishrom.gba (English source ROM)
    - output/extracted/extracted_texts/spanishrom_texts.json (Spanish texts)

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
    Correctly builds the Spanish ROM using ROMTranslationManager.
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
        """Generates output paths."""
        self.output_rom_dir.mkdir(parents=True, exist_ok=True)
        self.output_report_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        self.output_rom_path = self.output_rom_dir / f"{date_str}_spanishrom_correct.gba"
        self.output_report_path = self.output_report_dir / f"{date_str}_spanish_build_correct_report.json"

    def _load_texts(self) -> bool:
        """Loads English and Spanish texts."""
        print("📖 Loading extracted texts...")

        if not self.spanish_texts_path.exists():
            print(f"❌ File not found: {self.spanish_texts_path}")
            return False

        if not self.english_texts_path.exists():
            print(f"❌ File not found: {self.english_texts_path}")
            return False

        try:
            # Load JSON and keep as list for ROMTranslationManager
            with open(self.spanish_texts_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                texts_list = data.get('texts', [])
                self.spanish_texts = texts_list  # Keep as list for ROMTranslationManager

            with open(self.english_texts_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                texts_list = data.get('texts', [])
                self.english_texts = {item['offset']: item['text'] for item in texts_list}

            print(f"✅ Texts loaded:")
            print(f"   - English texts: {len(self.english_texts)}")
            print(f"   - Spanish texts: {len(self.spanish_texts)}")

            return True

        except Exception as e:
            print(f"❌ Error loading: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _build_translations_list(self) -> List[dict]:
        """
        Builds the translations list for ROMTranslationManager.

        Expected format:
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
        print("\n🔄 Preparing translations...")

        translations = []
        skipped = 0

        for item in self.spanish_texts:
            try:
                offset = item.get('offset')
                spanish_text = item.get('text', '')
                english_text = self.english_texts.get(offset, '')
                encoding = item.get('encoding', 'pokemon')

                # Check if the Spanish text is valid
                if not spanish_text or not self.validator.is_valid_game_text(spanish_text):
                    if self.validator.is_corrupted(spanish_text):
                        self.stats['corrupted_spanish_texts'] += 1
                    skipped += 1
                    continue

                # If texts are identical, skip
                if spanish_text == english_text:
                    self.stats['unchanged_texts'] += 1
                    continue

                # Add to translations list
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

        print(f"✅ Translations prepared:")
        print(f"   - Total to replace: {len(translations)}")
        print(f"   - Unchanged (identical): {self.stats['unchanged_texts']}")
        print(f"   - Corrupted (ignored): {self.stats['corrupted_spanish_texts']}")
        print(f"   - Failed: {self.stats['failed_replacements']}")

        self.stats['total_texts'] = len(self.spanish_texts)

        return translations

    def _build_rom(self, translations: List[dict]) -> bool:
        """Builds the Spanish ROM by reinserting translations."""
        print(f"\n📋 Copying English ROM...")

        if not self.english_rom_path.exists():
            print(f"❌ ROM not found: {self.english_rom_path}")
            return False

        try:
            # Load the ROM with ROMTranslationManager
            print(f"📖 Loading ROM: {self.english_rom_path}")
            self.rom_manager = ROMTranslationManager(str(self.english_rom_path))
            rom_info = self.rom_manager.get_rom_info()
            print(f"   ROM: {rom_info['title']}")
            print(f"   Size: {rom_info['size_mb']} MB")

            # Convert translations to the format expected by apply_translations
            translations_formatted = []
            for trans in translations:
                translations_formatted.append({
                    'offset': trans['offset'],
                    'text': trans['spanish'],
                    'encoding': trans.get('encoding', 'pokemon')
                })

            print(f"\n🔄 Reinserting Spanish texts...")
            report = self.rom_manager.apply_translations(translations_formatted)

            print(f"✅ Reinsertion complete:")
            print(f"   - Translations applied: {len(translations_formatted)}")

            # Save the ROM
            print(f"\n💾 Saving ROM...")
            self.rom_manager.save_rom(str(self.output_rom_path))
            rom_size_mb = self.output_rom_path.stat().st_size / (1024 * 1024)
            print(f"✅ ROM saved: {self.output_rom_path.name} ({rom_size_mb:.2f} MB)")

            return True

        except Exception as e:
            print(f"❌ ROM build error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _save_report(self):
        """Saves the report."""
        print(f"\n📊 Generating report...")

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

            print(f"✅ Report saved: {self.output_report_path.name}")
            return True

        except Exception as e:
            print(f"❌ Report error: {e}")
            return False

    def run(self) -> bool:
        """Runs the complete Spanish ROM build."""
        print("="*70)
        print("🚀 BUILDING SPANISH ROM (CORRECT)")
        print("="*70)

        # Generate output paths
        self._generate_output_paths()

        # Load texts
        if not self._load_texts():
            print(f"\n❌ Failed: Loading texts")
            return False

        # Prepare translations
        translations = self._build_translations_list()
        if not translations:
            print(f"\n❌ No translations to apply")
            return False

        # Build the ROM
        if not self._build_rom(translations):
            print(f"\n❌ Failed: Building ROM")
            return False

        # Save the report
        if not self._save_report():
            print(f"\n❌ Failed: Generating report")
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
    builder = SpanishROMBuilderCorrect()
    success = builder.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
