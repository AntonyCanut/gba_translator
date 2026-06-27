#!/usr/bin/env python3
"""
08 - JSON to CSV Converter

Converts the padded enriched JSON file to a CSV for translation.

Usage:
    python src/translators/08_json_to_csv.py

Input:
    - output/differences/*_diff_with_padding.json

Output:
    - output/translation/YYYY-MM-DD_translation_template.csv
"""

import sys
import csv
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def find_latest_padding_file() -> Path:
    """
    Finds the most recent diff_with_padding.json file.

    Returns:
        Path: Path to the file
    """
    diff_dir = Path('output/differences')
    if not diff_dir.exists():
        raise FileNotFoundError("output/differences/ not found")

    # Search for diff_with_padding files
    padding_files = list(diff_dir.glob('*_diff_with_padding.json'))

    if not padding_files:
        raise FileNotFoundError("No *_diff_with_padding.json found in output/differences/")

    # Return the most recent
    return max(padding_files, key=lambda p: p.stat().st_mtime)


def categorize_text(text: str, offset: int) -> str:
    """
    Categorizes a text based on its content.

    Args:
        text: The text to categorize
        offset: The text offset

    Returns:
        str: Text category
    """
    text_lower = text.lower()

    # Dialogues
    if any(marker in text_lower for marker in ['!', '?', '...', 'you', 'your', 'my', 'i ']):
        return "dialogue"

    # Location names
    if text[0].isupper() and ' ' in text and len(text.split()) <= 3:
        return "location"

    # System messages
    if any(word in text_lower for word in ['saved', 'loaded', 'menu', 'cancel', 'select']):
        return "system"

    # Descriptions
    if len(text) > 30:
        return "description"

    # Other
    return "other"


def json_to_csv(json_path: Path, csv_path: Path) -> dict:
    """
    Converts JSON to CSV for translation.

    Args:
        json_path: Path to the enriched JSON
        csv_path: Output path for the CSV

    Returns:
        dict: Conversion statistics
    """
    # Load JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    texts = data['texts']

    # Create CSV
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'offset',
            'original_text',
            'original_length',
            'padding_available',
            'real_max_length',
            'encoding',
            'category',
            'translation',
            'notes'
        ])

        writer.writeheader()

        for text_entry in texts:
            offset = text_entry['offset']
            original_text = text_entry['text']
            original_length = text_entry['length']
            padding = text_entry['padding_available']
            real_max = text_entry['real_max_length']
            encoding = text_entry['encoding']

            category = categorize_text(original_text, offset)

            writer.writerow({
                'offset': f"0x{offset:08X}",
                'original_text': original_text,
                'original_length': original_length,
                'padding_available': padding,
                'real_max_length': real_max,
                'encoding': encoding,
                'category': category,
                'translation': '',  # To fill in
                'notes': ''  # For translator comments
            })

    # Statistics
    stats = {
        'total_texts': len(texts),
        'categories': {}
    }

    for text_entry in texts:
        cat = categorize_text(text_entry['text'], text_entry['offset'])
        stats['categories'][cat] = stats['categories'].get(cat, 0) + 1

    return stats


def main():
    print("="*80)
    print("08 - JSON TO CSV CONVERTER")
    print("="*80)
    print()

    # 1. Find JSON file
    try:
        json_path = find_latest_padding_file()
        print(f"📄 File found: {json_path.name}")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print()

    # 2. Create output directory
    output_dir = Path('output/translation')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 3. Generate CSV
    date_str = datetime.now().strftime('%Y-%m-%d')
    csv_path = output_dir / f"{date_str}_translation_template.csv"

    print("🔄 Converting JSON → CSV...")
    stats = json_to_csv(json_path, csv_path)

    print(f"✅ {stats['total_texts']} texts exported")
    print()

    # 4. Display statistics
    print("="*80)
    print("STATISTICS BY CATEGORY")
    print("="*80)

    for category, count in sorted(stats['categories'].items(), key=lambda x: -x[1]):
        pct = 100 * count / stats['total_texts']
        print(f"  {category:15s}: {count:5d} ({pct:5.1f}%)")

    print()

    # 5. Instructions
    print("="*80)
    print("✅ CONVERSION COMPLETE")
    print("="*80)
    print()
    print(f"Generated file: {csv_path}")
    print()
    print("Instructions for translators:")
    print("-" * 80)
    print("1. Open the CSV in Excel, Google Sheets or LibreOffice")
    print("2. Fill in the 'translation' column with your translations")
    print("3. Respect the 'real_max_length' column (max length with padding)")
    print("4. Use the 'notes' column for comments if needed")
    print("5. Save and run: python src/translators/09_csv_to_json.py")
    print()
    print("Important columns:")
    print("  - original_text: English text to translate")
    print("  - original_length: Length of the English text")
    print("  - padding_available: Available padding bytes")
    print("  - real_max_length: MAXIMUM allowed length (original + padding)")
    print("  - translation: YOUR TRANSLATION (to fill in)")
    print()


if __name__ == "__main__":
    main()
