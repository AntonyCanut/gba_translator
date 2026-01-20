#!/usr/bin/env python3
"""
GBA ROM Text Comparison Tool
Compares extracted texts from two ROMs and outputs only the differences.
"""

import sys
import json
from pathlib import Path
from difflib import SequenceMatcher


class TextComparator:
    def __init__(self, json1_path, json2_path):
        self.json1_path = Path(json1_path)
        self.json2_path = Path(json2_path)
        self.texts1 = None
        self.texts2 = None
        self.differences = []

    def load_texts(self):
        """Load both JSON files."""
        with open(self.json1_path, 'r', encoding='utf-8') as f:
            data1 = json.load(f)
            self.texts1 = {entry['offset']: entry for entry in data1['texts']}
            self.rom1_name = data1['rom_name']

        with open(self.json2_path, 'r', encoding='utf-8') as f:
            data2 = json.load(f)
            self.texts2 = {entry['offset']: entry for entry in data2['texts']}
            self.rom2_name = data2['rom_name']

        print(f"Loaded {len(self.texts1)} texts from {self.rom1_name}")
        print(f"Loaded {len(self.texts2)} texts from {self.rom2_name}")

    def calculate_similarity(self, text1, text2):
        """Calculate similarity ratio between two texts."""
        return SequenceMatcher(None, text1, text2).ratio()

    def compare_texts(self, min_similarity=0.3):
        """
        Compare texts from both ROMs and find differences.
        min_similarity: threshold for considering texts as "similar but different"
        """
        print("\nComparing texts...")

        # Get all unique offsets from both ROMs
        all_offsets = sorted(set(self.texts1.keys()) | set(self.texts2.keys()))

        for offset in all_offsets:
            entry1 = self.texts1.get(offset)
            entry2 = self.texts2.get(offset)

            if entry1 and entry2:
                # Both ROMs have text at this offset
                if entry1['text'] != entry2['text']:
                    similarity = self.calculate_similarity(entry1['text'], entry2['text'])

                    self.differences.append({
                        'offset': offset,
                        'type': 'modified',
                        'similarity': similarity,
                        'rom1_text': entry1['text'],
                        'rom2_text': entry2['text'],
                        'rom1_encoding': entry1['encoding'],
                        'rom2_encoding': entry2['encoding']
                    })

            elif entry1 and not entry2:
                # Only in ROM 1
                self.differences.append({
                    'offset': offset,
                    'type': 'only_in_rom1',
                    'rom1_text': entry1['text'],
                    'rom1_encoding': entry1['encoding']
                })

            elif entry2 and not entry1:
                # Only in ROM 2
                self.differences.append({
                    'offset': offset,
                    'type': 'only_in_rom2',
                    'rom2_text': entry2['text'],
                    'rom2_encoding': entry2['encoding']
                })

        print(f"Found {len(self.differences)} differences")

    def save_diff_json(self, output_path):
        """Save differences to JSON file."""
        output_data = {
            'rom1': self.rom1_name,
            'rom2': self.rom2_name,
            'total_differences': len(self.differences),
            'differences': self.differences
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"Saved differences to {output_path}")

    def save_diff_txt(self, output_path):
        """Save differences to a readable text file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"Text Comparison Report\n")
            f.write(f"ROM 1: {self.rom1_name}\n")
            f.write(f"ROM 2: {self.rom2_name}\n")
            f.write(f"Total differences: {len(self.differences)}\n")
            f.write("=" * 80 + "\n\n")

            # Group by type
            modified = [d for d in self.differences if d['type'] == 'modified']
            only_rom1 = [d for d in self.differences if d['type'] == 'only_in_rom1']
            only_rom2 = [d for d in self.differences if d['type'] == 'only_in_rom2']

            # Modified texts
            if modified:
                f.write(f"MODIFIED TEXTS ({len(modified)})\n")
                f.write("=" * 80 + "\n\n")

                for diff in modified:
                    f.write(f"Offset: 0x{diff['offset']:08X}\n")
                    f.write(f"Similarity: {diff['similarity']:.2%}\n")
                    f.write(f"\n{self.rom1_name}:\n")
                    f.write(f"  {diff['rom1_text']}\n")
                    f.write(f"\n{self.rom2_name}:\n")
                    f.write(f"  {diff['rom2_text']}\n")
                    f.write("-" * 80 + "\n\n")

            # Only in ROM 1
            if only_rom1:
                f.write(f"\nTEXTS ONLY IN {self.rom1_name} ({len(only_rom1)})\n")
                f.write("=" * 80 + "\n\n")

                for diff in only_rom1:
                    f.write(f"Offset: 0x{diff['offset']:08X}\n")
                    f.write(f"Text: {diff['rom1_text']}\n")
                    f.write("-" * 80 + "\n\n")

            # Only in ROM 2
            if only_rom2:
                f.write(f"\nTEXTS ONLY IN {self.rom2_name} ({len(only_rom2)})\n")
                f.write("=" * 80 + "\n\n")

                for diff in only_rom2:
                    f.write(f"Offset: 0x{diff['offset']:08X}\n")
                    f.write(f"Text: {diff['rom2_text']}\n")
                    f.write("-" * 80 + "\n\n")

        print(f"Saved readable comparison to {output_path}")

    def save_translation_pairs(self, output_path):
        """
        Save only modified texts as translation pairs (useful for translation work).
        """
        modified = [d for d in self.differences if d['type'] == 'modified']

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Translation Pairs\n")
            f.write(f"# {self.rom1_name} -> {self.rom2_name}\n")
            f.write(f"# Total pairs: {len(modified)}\n\n")

            for diff in modified:
                f.write(f"## 0x{diff['offset']:08X}\n")
                f.write(f"SOURCE: {diff['rom1_text']}\n")
                f.write(f"TARGET: {diff['rom2_text']}\n\n")

        print(f"Saved translation pairs to {output_path}")

    def generate_statistics(self):
        """Generate statistics about the differences."""
        modified = [d for d in self.differences if d['type'] == 'modified']
        only_rom1 = [d for d in self.differences if d['type'] == 'only_in_rom1']
        only_rom2 = [d for d in self.differences if d['type'] == 'only_in_rom2']

        print("\n" + "=" * 80)
        print("STATISTICS")
        print("=" * 80)
        print(f"Total texts in {self.rom1_name}: {len(self.texts1)}")
        print(f"Total texts in {self.rom2_name}: {len(self.texts2)}")
        print(f"\nModified texts: {len(modified)}")
        print(f"Texts only in {self.rom1_name}: {len(only_rom1)}")
        print(f"Texts only in {self.rom2_name}: {len(only_rom2)}")
        print(f"\nTotal differences: {len(self.differences)}")

        if modified:
            avg_similarity = sum(d['similarity'] for d in modified) / len(modified)
            print(f"Average similarity of modified texts: {avg_similarity:.2%}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python compare_texts.py <texts1.json> <texts2.json>")
        sys.exit(1)

    json1 = sys.argv[1]
    json2 = sys.argv[2]

    # Verify files exist
    if not Path(json1).exists():
        print(f"Error: JSON file '{json1}' not found")
        sys.exit(1)

    if not Path(json2).exists():
        print(f"Error: JSON file '{json2}' not found")
        sys.exit(1)

    # Create output directory
    output_dir = Path('differences')
    output_dir.mkdir(exist_ok=True)

    # Compare texts
    comparator = TextComparator(json1, json2)
    comparator.load_texts()
    comparator.compare_texts()

    # Save outputs
    comparator.save_diff_json(output_dir / 'differences.json')
    comparator.save_diff_txt(output_dir / 'differences.txt')
    comparator.save_translation_pairs(output_dir / 'translation_pairs.txt')

    # Show statistics
    comparator.generate_statistics()

    print(f"\nComparison complete!")
    print(f"Output directory: {output_dir}/")


if __name__ == "__main__":
    main()
