#!/usr/bin/env python3
"""
10 - Smart Text Reinsertion

Reinserts translated texts into the ROM with intelligent padding management.

Usage:
    python src/translators/10_reinsert_smart.py [translation_json]

Input:
    - input/roms/englishrom.gba
    - output/translation/*_translation_ready.json

Output:
    - output/roms/YYYY-MM-DD_frenchrom.gba
    - output/reports/YYYY-MM-DD_reinsertion_report.json
"""

import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader, ROMError
from src.core.padding_detector import PaddingDetector
from src.core.text_codec import TextEncoder


def find_latest_translation_file() -> Path:
    """Finds the most recent translation_ready.json file."""
    translation_dir = Path('output/translation')
    if not translation_dir.exists():
        raise FileNotFoundError("output/translation/ not found")

    json_files = list(translation_dir.glob('*_translation_ready.json'))

    if not json_files:
        raise FileNotFoundError("No *_translation_ready.json found")

    return max(json_files, key=lambda p: p.stat().st_mtime)


def encode_text(text: str, encoding: str) -> bytes:
    """Encodes text using the specified encoding."""
    return TextEncoder.encode(text, encoding)


class SmartReinserter:
    """Manages intelligent reinsertion with padding."""

    def __init__(self, rom_data: bytearray):
        self.rom_data = rom_data
        self.stats = {
            'total': 0,
            'success': 0,
            'padding_used': 0,
            'failures': 0,
            'warnings': []
        }

    def reinsert_text(self, translation: dict) -> bool:
        """
        Reinserts a translated text.

        Args:
            translation: Dictionary with offset, translation, encoding, etc.

        Returns:
            bool: True on success, False otherwise
        """
        offset = translation['offset']
        text = translation['translation']
        encoding = translation['encoding']
        original_length = translation['original_length']
        padding_used = translation['padding_used']

        self.stats['total'] += 1

        try:
            # Encode the text
            encoded = encode_text(text, encoding)
            encoded_len = len(encoded)

            # Check if padding is needed
            if encoded_len > original_length + 1:  # +1 for terminator
                self.stats['padding_used'] += 1

            # Write to ROM
            for i, byte in enumerate(encoded):
                self.rom_data[offset + i] = byte

            self.stats['success'] += 1
            return True

        except Exception as e:
            self.stats['failures'] += 1
            self.stats['warnings'].append({
                'offset': f"0x{offset:08X}",
                'text': text,
                'error': str(e)
            })
            return False

    def get_report(self) -> dict:
        """Returns a reinsertion report."""
        return {
            'statistics': {
                'total_texts': self.stats['total'],
                'successful': self.stats['success'],
                'failed': self.stats['failures'],
                'used_padding': self.stats['padding_used']
            },
            'warnings': self.stats['warnings']
        }


def main():
    print("="*80)
    print("10 - SMART TEXT REINSERTION")
    print("="*80)
    print()

    # 1. Find translation file
    if len(sys.argv) > 1:
        translation_path = Path(sys.argv[1])
        if not translation_path.exists():
            print(f"❌ Error: File not found: {translation_path}")
            sys.exit(1)
    else:
        try:
            translation_path = find_latest_translation_file()
            print(f"📄 Translation file: {translation_path.name}")
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

    # 2. Load translations
    with open(translation_path, 'r', encoding='utf-8') as f:
        translation_data = json.load(f)

    translations = translation_data['translations']
    print(f"   Translations to insert: {len(translations)}")
    print()

    # 3. Load ROM
    rom_path = Path('input/roms/englishrom.gba')
    print(f"📖 Loading ROM: {rom_path}")

    try:
        rom = ROMReader(str(rom_path))
        rom.load()
        info = rom.get_rom_info()
        print(f"   ROM: {info['title']} ({info['game_code']})")
        print(f"   Size: {info['size_mb']} MB")
    except (FileNotFoundError, ROMError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print()

    # 4. Create ROM copy
    date_str = datetime.now().strftime('%Y-%m-%d')
    output_dir = Path('output/roms')
    output_dir.mkdir(parents=True, exist_ok=True)

    output_rom_path = output_dir / f"{date_str}_frenchrom.gba"
    print(f"💾 Creating output ROM: {output_rom_path}")

    rom_data = bytearray(rom.rom_data)

    # 5. Reinsertion
    print()
    print("🔄 Reinserting translations...")
    print()

    reinserter = SmartReinserter(rom_data)

    for i, translation in enumerate(translations):
        if (i + 1) % 1000 == 0:
            print(f"   Processed: {i + 1}/{len(translations)}")

        reinserter.reinsert_text(translation)

    print(f"✅ {len(translations)} texts processed")
    print()

    # 6. Save ROM
    with open(output_rom_path, 'wb') as f:
        f.write(rom_data)

    print(f"💾 ROM saved: {output_rom_path}")
    print()

    # 7. Generate report
    report = reinserter.get_report()

    report_dir = Path('output/reports')
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / f"{date_str}_reinsertion_report.json"

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # 8. Display results
    print("="*80)
    print("REINSERTION RESULTS")
    print("="*80)
    stats = report['statistics']
    print(f"Total texts:          {stats['total_texts']}")
    print(f"Success:              {stats['successful']}")
    print(f"Failed:               {stats['failed']}")
    print(f"Used padding:         {stats['used_padding']}")
    print()

    if report['warnings']:
        print("⚠️ WARNINGS:")
        for warning in report['warnings'][:5]:
            print(f"  {warning['offset']}: {warning['error']}")
        if len(report['warnings']) > 5:
            print(f"  ... and {len(report['warnings']) - 5} more")
        print()

    print("="*80)
    print("✅ REINSERTION COMPLETE")
    print("="*80)
    print()
    print(f"Translated ROM: {output_rom_path}")
    print(f"Report:         {report_path}")
    print()
    print("Next step:")
    print("  Test the ROM on an emulator (mGBA, VBA, etc.)")
    print()


if __name__ == "__main__":
    main()
