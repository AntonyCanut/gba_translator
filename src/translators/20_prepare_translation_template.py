#!/usr/bin/env python3
"""
20 - Prepare Translation Template

Creates a translation template from differences and the Spanish ROM.

Usage:
    python src/translators/20_prepare_translation_template.py \
        --output output/translation/french_texts.json \
        [--use-spanish-as-base]

Features:
- Extracts different English texts
- Can pre-fill with Spanish translation as base
- Generates template ready for translation
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TranslationTemplateGenerator:
    """Prepares a translation template."""
    
    def __init__(self):
        self.english_texts = {}
        self.spanish_texts = {}
        self.differences = {}
    
    def run(self, output_path: Path, use_spanish_base: bool = False) -> bool:
        """Generate the template."""
        print("="*70)
        print("📝 TRANSLATION TEMPLATE GENERATOR")
        print("="*70)
        
        # Load data
        if not self._load_data():
            return False

        # Prepare template
        template = self._prepare_template(use_spanish_base)

        # Save
        return self._save_template(template, output_path)
    
    def _load_data(self) -> bool:
        """Load extraction data."""
        print("\n📥 Loading data...")
        
        english_path = Path('output/extracted/extracted_texts/englishrom_texts.json')
        spanish_path = Path('output/extracted/extracted_texts/spanishrom_texts.json')
        diff_path = Path('output/differences/differences.json')
        
        try:
            # Load English
            if english_path.exists():
                with open(english_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get('texts', []):
                        self.english_texts[item['offset']] = item
                print(f"✅ English texts: {len(self.english_texts)}")

            # Load Spanish
            if spanish_path.exists():
                with open(spanish_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get('texts', []):
                        self.spanish_texts[item['offset']] = item
                print(f"✅ Spanish texts: {len(self.spanish_texts)}")

            # Load differences
            if diff_path.exists():
                with open(diff_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    diffs_list = data.get('differences', [])
                    # Convert to dict with offset as key
                    for diff in diffs_list:
                        offset = diff.get('offset')
                        if offset:
                            self.differences[offset] = diff
                print(f"✅ Differences: {len(self.differences)}")

            return True

        except Exception as e:
            print(f"❌ Loading error: {e}")
            return False
    
    def _prepare_template(self, use_spanish_base: bool = False) -> Dict:
        """Prepare the template."""
        print("\n✍️  Preparing template...")
        
        translations = []
        
        # For each found difference
        for offset, diff_info in self.differences.items():
            try:
                offset = int(offset)
            except:
                continue
            
            english = self.english_texts.get(offset, {})
            spanish = self.spanish_texts.get(offset, {})
            
            english_text = english.get('text', '')
            spanish_text = spanish.get('text', '')
            length = english.get('length', 100)
            
            # Create translation entry
            entry = {
                'offset': offset,
                'english': english_text,
                'spanish': spanish_text,
                'text': spanish_text if use_spanish_base else '',  # Pre-fill with Spanish
                'length': length,
                'encoding': 'pokemon',
                'category': self._guess_category(english_text),
                'status': 'translated' if (use_spanish_base and spanish_text) else 'needs_translation',
                'notes': ''
            }
            
            translations.append(entry)
        
        print(f"✅ Template prepared: {len(translations)} entries")
        
        template = {
            'rom_name': 'englishrom.gba',
            'language': 'french',
            'text_count': len(translations),
            'encoding': 'pokemon',
            'notes': 'French translation template - pre-filled with Spanish as base if requested',
            'translations': translations
        }
        
        return template
    
    def _guess_category(self, text: str) -> str:
        """Guess the text category."""
        text_lower = text.lower()
        
        if any(x in text_lower for x in ['wild', 'appeared', 'battle', 'trainer']):
            return 'battle'
        elif any(x in text_lower for x in ['cave', 'town', 'city', 'route', 'forest']):
            return 'location'
        elif any(x in text_lower for x in ['attack', 'move', 'power']):
            return 'move'
        elif any(x in text_lower for x in ['use', 'catch', 'item']):
            return 'item'
        elif any(x in text_lower for x in ['hello', 'hi', 'welcome', 'thank', 'hey']):
            return 'dialogue'
        else:
            return 'other'
    
    def _save_template(self, template: Dict, output_path: Path) -> bool:
        """Save the template."""
        print(f"\n💾 Saving template...")
        
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Template saved: {output_path.name}")
            return True

        except Exception as e:
            print(f"❌ Save error: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Prepare Translation Template',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create empty template (translator fills in)
  python 20_prepare_translation_template.py \\
    --output output/translation/french_texts.json

  # Pre-fill with Spanish (use as base, then translate)
  python 20_prepare_translation_template.py \\
    --output output/translation/french_texts.json \\
    --use-spanish-as-base

  # Use in pipeline
  make build-french  # Requires output/translation/french_texts.json
        """
    )
    
    parser.add_argument('--output', type=Path, 
                       default=Path('output/translation/french_texts.json'),
                       help='Output template path')
    parser.add_argument('--use-spanish-as-base', action='store_true',
                       help='Pre-fill template with Spanish translations as base')
    
    args = parser.parse_args()
    
    generator = TranslationTemplateGenerator()
    success = generator.run(args.output, args.use_spanish_as_base)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
