#!/usr/bin/env python3
"""
08 - JSON to CSV Converter (Object-Oriented Version)

Converts the padded enriched JSON file to a CSV for translation.
Uses reusable classes from the core module.

Usage:
    python src/translators/08_json_to_csv_v2.py [json_file]

Input:
    - output/differences/*_diff_with_padding.json

Output:
    - output/translation/YYYY-MM-DD_translation_template.csv
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_converter import JSONToCSVConverter


class TranslationCSVGenerator:
    """
    Generates a translation CSV from an enriched JSON.

    Attributes:
        converter (JSONToCSVConverter): JSON→CSV converter
        input_path (Path): Path to the source JSON
        output_path (Path): Path to the output CSV
    """

    def __init__(self, input_path: Path = None, output_path: Path = None):
        """
        Initializes the generator.

        Args:
            input_path: Path to the JSON (None = auto-detect)
            output_path: Path to the CSV (None = auto-generate)
        """
        self.converter = JSONToCSVConverter()
        self.input_path = input_path or self._find_latest_json()
        self.output_path = output_path or self._generate_output_path()

    def _find_latest_json(self) -> Path:
        """
        Finds the most recent enriched JSON file.

        Returns:
            Path: Path to the file

        Raises:
            FileNotFoundError: If no file found
        """
        diff_dir = Path('output/differences')
        if not diff_dir.exists():
            raise FileNotFoundError("output/differences/ not found")

        json_files = list(diff_dir.glob('*_diff_with_padding.json'))

        if not json_files:
            raise FileNotFoundError(
                "No *_diff_with_padding.json found in output/differences/"
            )

        return max(json_files, key=lambda p: p.stat().st_mtime)

    def _generate_output_path(self) -> Path:
        """
        Generates the output path with date.

        Returns:
            Path: Path to the output CSV
        """
        output_dir = Path('output/translation')
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        return output_dir / f"{date_str}_translation_template.csv"

    def generate(self) -> dict:
        """
        Generates the translation CSV.

        Returns:
            dict: Conversion statistics

        Example:
            >>> generator = TranslationCSVGenerator()
            >>> stats = generator.generate()
            >>> print(stats['total_texts'])
            14436
        """
        # Load JSON
        print(f"📄 Loading: {self.input_path.name}")
        self.converter.load_from_json(self.input_path)

        # Categorize texts
        print("🔍 Categorizing texts...")
        self.converter.categorize_all()

        # Save CSV
        print(f"💾 Generating CSV: {self.output_path.name}")
        self.converter.save_to_csv(self.output_path)

        # Return statistics
        return self.converter.get_statistics()

    def print_statistics(self, stats: dict) -> None:
        """
        Prints conversion statistics.

        Args:
            stats: Statistics dictionary
        """
        print()
        print("=" * 80)
        print("STATISTICS BY CATEGORY")
        print("=" * 80)

        total = stats['total_texts']
        for category, count in sorted(stats['categories'].items(), key=lambda x: -x[1]):
            pct = 100 * count / total
            print(f"  {category:15s}: {count:5d} ({pct:5.1f}%)")

        print()

    def print_instructions(self) -> None:
        """Prints instructions for translators."""
        print("=" * 80)
        print("✅ CONVERSION COMPLETE")
        print("=" * 80)
        print()
        print(f"Generated file: {self.output_path}")
        print()
        print("Instructions for translators:")
        print("-" * 80)
        print("1. Open the CSV in Excel, Google Sheets or LibreOffice")
        print("2. Fill in the 'translation' column with your translations")
        print("3. Respect the 'real_max_length' column (max length with padding)")
        print("4. Use the 'notes' column for comments if needed")
        print("5. Save and run: python src/translators/09_csv_to_json_v2.py")
        print()
        print("Important columns:")
        print("  - original_text: English text to translate")
        print("  - original_length: Length of the English text")
        print("  - padding_available: Available padding bytes")
        print("  - real_max_length: MAXIMUM allowed length (original + padding)")
        print("  - translation: YOUR TRANSLATION (to fill in)")
        print()


def main():
    """Main entry point."""
    print("=" * 80)
    print("08 - JSON TO CSV CONVERTER (v2 - OOP)")
    print("=" * 80)
    print()

    # Handle optional argument
    input_path = None
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if not input_path.exists():
            print(f"❌ Error: File not found: {input_path}")
            sys.exit(1)

    try:
        # Create generator
        generator = TranslationCSVGenerator(input_path=input_path)

        # Generate CSV
        stats = generator.generate()

        # Display results
        print(f"✅ {stats['total_texts']} texts exported")
        generator.print_statistics(stats)
        generator.print_instructions()

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
