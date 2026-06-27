#!/usr/bin/env python3
"""
09 - CSV to JSON Converter

Converts the translated CSV to a JSON for reinsertion into the ROM.

Usage:
    python src/translators/09_csv_to_json.py [csv_file]

Input:
    - output/translation/*_translation_template.csv (or specified file)

Output:
    - output/translation/YYYY-MM-DD_translation_ready.json
"""

import sys
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def find_latest_csv_file() -> Path:
    """
    Finds the most recent CSV file.

    Returns:
        Path: Path to the file
    """
    translation_dir = Path('output/translation')
    if not translation_dir.exists():
        raise FileNotFoundError("output/translation/ not found")

    # Search for CSV files
    csv_files = list(translation_dir.glob('*_translation_*.csv'))

    if not csv_files:
        raise FileNotFoundError("No CSV files found in output/translation/")

    # Return the most recent
    return max(csv_files, key=lambda p: p.stat().st_mtime)


def validate_translation(row: dict) -> tuple[bool, str]:
    """
    Validates a translation row.

    Args:
        row: CSV row

    Returns:
        tuple: (is_valid, error_message)
    """
    translation = row.get('translation', '').strip()

    # Check if translation exists
    if not translation:
        return False, "Missing translation"

    # Check length
    try:
        real_max = int(row['real_max_length'])
        trans_len = len(translation)

        if trans_len > real_max:
            return False, f"Too long: {trans_len} > {real_max} (overflow: {trans_len - real_max})"

    except (ValueError, KeyError) as e:
        return False, f"Validation error: {e}"

    return True, ""


def csv_to_json(csv_path: Path, json_path: Path) -> dict:
    """
    Converts CSV to JSON and validates translations.

    Args:
        csv_path: Path to the translated CSV
        json_path: Output path for the JSON

    Returns:
        dict: Conversion and validation statistics
    """
    translations = []
    errors = []
    warnings = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header = 1)
            translation = row.get('translation', '').strip()

            # Skip empty rows
            if not translation:
                warnings.append({
                    'row': row_num,
                    'offset': row.get('offset', 'unknown'),
                    'message': 'Missing translation'
                })
                continue

            # Validate
            is_valid, error_msg = validate_translation(row)

            if not is_valid:
                errors.append({
                    'row': row_num,
                    'offset': row.get('offset', 'unknown'),
                    'original': row.get('original_text', ''),
                    'translation': translation,
                    'error': error_msg
                })
                continue

            # Convert offset (0x12345678 → 305441400)
            offset_str = row['offset'].replace('0x', '')
            offset = int(offset_str, 16)

            # Add translation
            translations.append({
                'offset': offset,
                'original_text': row['original_text'],
                'translation': translation,
                'length': len(translation),
                'original_length': int(row['original_length']),
                'padding_used': len(translation) - int(row['original_length']),
                'encoding': row['encoding'],
                'category': row.get('category', 'unknown'),
                'notes': row.get('notes', '')
            })

    # Save JSON
    output = {
        'conversion_date': datetime.now().isoformat(),
        'source_csv': csv_path.name,
        'total_translations': len(translations),
        'total_errors': len(errors),
        'total_warnings': len(warnings),
        'translations': translations
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Statistics
    stats = {
        'total_rows': len(translations) + len(errors) + len(warnings),
        'successful': len(translations),
        'errors': errors,
        'warnings': warnings
    }

    return stats


def main():
    print("="*80)
    print("09 - CSV TO JSON CONVERTER")
    print("="*80)
    print()

    # 1. Find CSV file
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
        if not csv_path.exists():
            print(f"❌ Error: File not found: {csv_path}")
            sys.exit(1)
    else:
        try:
            csv_path = find_latest_csv_file()
            print(f"📄 File found: {csv_path.name}")
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

    print()

    # 2. Create output path
    output_dir = Path('output/translation')
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime('%Y-%m-%d')
    json_path = output_dir / f"{date_str}_translation_ready.json"

    # 3. Convert and validate
    print("🔄 Converting CSV → JSON...")
    print("🔍 Validating translations...")
    print()

    stats = csv_to_json(csv_path, json_path)

    # 4. Print results
    print("="*80)
    print("CONVERSION RESULTS")
    print("="*80)
    print(f"Total rows:             {stats['total_rows']}")
    print(f"Successful translations:{stats['successful']}")
    print(f"Errors:                 {len(stats['errors'])}")
    print(f"Warnings:               {len(stats['warnings'])}")
    print()

    # 5. Print errors
    if stats['errors']:
        print("="*80)
        print("❌ ERRORS DETECTED")
        print("="*80)
        for error in stats['errors'][:10]:  # Limit to 10
            print(f"\nRow {error['row']} - Offset {error['offset']}")
            print(f"  Original:    {error['original']}")
            print(f"  Translation: {error['translation']}")
            print(f"  Error:       {error['error']}")

        if len(stats['errors']) > 10:
            print(f"\n... and {len(stats['errors']) - 10} more errors")

        print()
        print("⚠️ Please fix these errors before continuing.")
        sys.exit(1)

    # 6. Print warnings
    if stats['warnings']:
        print("="*80)
        print("⚠️ WARNINGS")
        print("="*80)
        for warning in stats['warnings'][:5]:
            print(f"Row {warning['row']} - {warning['offset']}: {warning['message']}")

        if len(stats['warnings']) > 5:
            print(f"... and {len(stats['warnings']) - 5} more warnings")
        print()

    # 7. Success
    print("="*80)
    print("✅ CONVERSION SUCCESSFUL")
    print("="*80)
    print()
    print(f"Generated file: {json_path}")
    print()
    print("Next step:")
    print("  python src/translators/10_reinsert_smart.py")
    print()


if __name__ == "__main__":
    main()
