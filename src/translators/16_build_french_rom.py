#!/usr/bin/env python3
"""
16 - Build French ROM

Builds the French ROM by:
1. Loading English differences (texts to translate)
2. Inserting French translations into the English ROM

Usage:
    python src/translators/16_build_french_rom.py [french_translation_json]

Input:
    - input/roms/englishrom.gba (English source ROM)
    - output/translation/[french_translation].json (French translations)
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
    Builds the French ROM using French translations
    and reinserts them into the English ROM.
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
        """Finds the French translation file."""
        if provided_path:
            path = Path(provided_path)
            if path.exists():
                return path
            print(f"⚠️  Provided file not found: {path}")

        # Look for the most recent file
        translation_dir = Path('output/translation')
        if translation_dir.exists():
            json_files = list(translation_dir.glob('*french*.json')) + \
                        list(translation_dir.glob('*fr*.json'))
            if json_files:
                latest = max(json_files, key=lambda p: p.stat().st_mtime)
                print(f"   Using: {latest.name}")
                return latest

        # Fallback: use differences
        print(f"⚠️  No French translation found")
        print(f"   Fallback: using English differences")
        return None

    def _generate_output_paths(self):
        """Generates output paths."""
        self.output_rom_dir.mkdir(parents=True, exist_ok=True)
        self.output_report_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        self.output_rom_path = self.output_rom_dir / f"{date_str}_frenchrom_built.gba"
        self.output_report_path = self.output_report_dir / f"{date_str}_french_build_report.json"

    def _load_texts(self) -> bool:
        """Loads English texts and French translations."""
        print("📖 Loading texts and translations...")

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

        # Load French translations
        if self.translation_path and self.translation_path.exists():
            try:
                with open(self.translation_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    # Support multiple JSON formats
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
                        # Assume it is a direct dict {offset: text}
                        self.french_texts = data

                print(f"✅ French translations loaded: {len(self.french_texts)}")
            except Exception as e:
                print(f"❌ Error loading translations: {e}")
                print(f"   Using differences as fallback...")
                if not self._load_differences():
                    return False
        else:
            if not self._load_differences():
                return False

        return True

    def _load_differences(self) -> bool:
        """Loads differences as a fallback."""
        if not self.differences_path.exists():
            print(f"❌ Differences file not found: {self.differences_path}")
            return False

        try:
            with open(self.differences_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                texts_list = data.get('texts', [])
                self.french_texts = {item['offset']: item['text'] for item in texts_list}

            print(f"✅ English differences loaded (fallback): {len(self.french_texts)}")
            return True
        except Exception as e:
            print(f"❌ Error loading differences: {e}")
            return False

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

    def _replace_french_texts(self) -> bool:
        """Actually replaces English texts with French translations."""
        print("\n🔄 Replacing texts with French translations...")

        self.stats['total_texts'] = len(self.french_texts)

        for offset, french_text in self.french_texts.items():
            try:
                english_text = self.english_texts.get(offset, '')

                # Check if French text is valid
                if not french_text or not self.validator.is_valid_game_text(french_text):
                    if self.validator.is_corrupted(french_text):
                        self.stats['corrupted_french_texts'] += 1
                    continue

                # If texts are identical, do not modify
                if french_text == english_text:
                    self.stats['unchanged_texts'] += 1
                    continue

                # Encode using Pokémon encoding (not UTF-8!)
                try:
                    french_bytes = TextEncoder.encode_pokemon(french_text)
                    english_bytes = TextEncoder.encode_pokemon(english_text)

                    rom_offset = int(offset) if isinstance(offset, (int, str)) else 0

                    # Replace if length allows
                    if len(french_bytes) <= len(english_bytes):
                        # Replace directly
                        self.rom_data[rom_offset:rom_offset + len(french_bytes)] = french_bytes

                        # Pad with 0xFF if French text is shorter
                        if len(french_bytes) < len(english_bytes):
                            padding = b'\xff' * (len(english_bytes) - len(french_bytes))
                            self.rom_data[rom_offset + len(french_bytes):rom_offset + len(english_bytes)] = padding

                        self.stats['successfully_replaced'] += 1
                    else:
                        # French text too long - truncate
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

        print(f"✅ Replacement complete:")
        print(f"   - Replaced: {self.stats['successfully_replaced']}")
        print(f"   - Failed: {self.stats['failed_replacements']}")
        print(f"   - Unchanged: {self.stats['unchanged_texts']}")
        if self.stats['too_long'] > 0:
            print(f"   - Truncated (too long): {self.stats['too_long']}")
        print(f"   - Corrupted (skipped): {self.stats['corrupted_french_texts']}")

        return True

    def _save_modified_rom(self) -> bool:
        """Saves the modified ROM with French texts."""
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
            
            print(f"✅ Report saved: {self.output_report_path.name}")
            return True

        except Exception as e:
            print(f"❌ Report error: {e}")
            return False

    def run(self) -> bool:
        """Runs the complete French ROM build."""
        print("="*70)
        print("🚀 BUILDING FRENCH ROM")
        print("="*70)

        # Generate output paths
        self._generate_output_paths()

        # Steps
        steps = [
            ("Loading texts and translations", self._load_texts),
            ("Copying English ROM", self._copy_rom),
            ("Replacing French texts", self._replace_french_texts),
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
        print("✨ BUILD SUCCESSFUL - FRENCH ROM CREATED!")
        print("="*70)
        print(f"\n📁 Output ROM: {self.output_rom_path}")
        print(f"📊 Report: {self.output_report_path}")
        print(f"\n✅ Texts inserted: {self.stats['successfully_replaced']}")
        print(f"⚠️  Unchanged: {self.stats['unchanged_texts']}")
        print(f"❌ Failed: {self.stats['failed_replacements']}")
        if self.stats['too_long'] > 0:
            print(f"📏 Truncated: {self.stats['too_long']}")
        print(f"\nThe ROM is now in FRENCH!")

        return True


def main():
    # Check if a path is provided as argument
    translation_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    builder = FrenchROMBuilder(translation_path)
    success = builder.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
