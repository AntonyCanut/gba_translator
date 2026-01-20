#!/usr/bin/env python3
"""
Extract English texts only at offsets where differences exist.
Creates a filtered JSON file containing only texts that differ from Spanish version.
"""

import sys
import json
from pathlib import Path


def extract_english_differences(english_json, differences_json, output_json):
    """
    Extract only English texts at offsets where differences exist.

    Args:
        english_json: Path to full English texts JSON
        differences_json: Path to differences JSON
        output_json: Path to output filtered JSON
    """
    # Load English texts
    with open(english_json, 'r', encoding='utf-8') as f:
        english_data = json.load(f)

    # Load differences
    with open(differences_json, 'r', encoding='utf-8') as f:
        diff_data = json.load(f)

    print(f"Loaded {len(english_data['texts'])} English texts")
    print(f"Loaded {len(diff_data['differences'])} differences")

    # Get all offsets where differences exist
    diff_offsets = set()
    for diff in diff_data['differences']:
        diff_offsets.add(diff['offset'])

    print(f"Found {len(diff_offsets)} unique offsets with differences")

    # Create mapping of offset to English text
    english_by_offset = {entry['offset']: entry for entry in english_data['texts']}

    # Extract only texts at different offsets
    filtered_texts = []
    for offset in sorted(diff_offsets):
        if offset in english_by_offset:
            filtered_texts.append(english_by_offset[offset])

    # Create filtered output
    output_data = {
        'rom_name': english_data['rom_name'],
        'rom_size': english_data['rom_size'],
        'original_text_count': len(english_data['texts']),
        'filtered_text_count': len(filtered_texts),
        'description': 'English texts only at offsets where differences exist with Spanish version',
        'texts': filtered_texts
    }

    # Save filtered JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\nFiltered extraction complete!")
    print(f"Original texts: {len(english_data['texts'])}")
    print(f"Filtered texts: {len(filtered_texts)}")
    print(f"Reduction: {100 * (1 - len(filtered_texts) / len(english_data['texts'])):.1f}%")
    print(f"Output: {output_json}")

    # Also create a readable TXT version
    txt_output = Path(output_json).with_suffix('.txt')
    with open(txt_output, 'w', encoding='utf-8') as f:
        f.write(f"English Texts at Different Offsets\n")
        f.write(f"ROM: {english_data['rom_name']}\n")
        f.write(f"Filtered texts: {len(filtered_texts)} / {len(english_data['texts'])}\n")
        f.write("=" * 80 + "\n\n")

        for entry in filtered_texts:
            f.write(f"Offset: 0x{entry['offset']:08X} | ")
            f.write(f"Length: {entry['length']} | ")
            f.write(f"Encoding: {entry['encoding']}\n")
            f.write(f"Text: {entry['text']}\n")
            f.write("-" * 80 + "\n")

    print(f"Readable version: {txt_output}")


def main():
    if len(sys.argv) != 4:
        print("Usage: python extract_english_diff.py <english_texts.json> <differences.json> <output.json>")
        print("\nExample:")
        print("  python extract_english_diff.py extracted_texts/englishrom_texts.json differences/differences.json differences/englishrom_diff_only.json")
        sys.exit(1)

    english_json = Path(sys.argv[1])
    differences_json = Path(sys.argv[2])
    output_json = Path(sys.argv[3])

    # Verify input files exist
    if not english_json.exists():
        print(f"Error: English texts file '{english_json}' not found")
        sys.exit(1)

    if not differences_json.exists():
        print(f"Error: Differences file '{differences_json}' not found")
        sys.exit(1)

    # Create output directory if needed
    output_json.parent.mkdir(parents=True, exist_ok=True)

    # Extract filtered texts
    extract_english_differences(english_json, differences_json, output_json)


if __name__ == "__main__":
    main()
