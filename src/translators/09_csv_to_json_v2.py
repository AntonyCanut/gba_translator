#!/usr/bin/env python3
"""
09 - CSV to JSON Converter (Object-Oriented Version)

Converts the translated CSV to a JSON for reinsertion into the ROM.
Uses reusable classes from the core module.

Usage:
    python src/translators/09_csv_to_json_v2.py [csv_file]

Input:
    - output/translation/*_translation_template.csv

Output:
    - output/translation/YYYY-MM-DD_translation_ready.json
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_converter import CSVToJSONConverter


class TranslationValidator:
    """
    Validates and converts a translation CSV to JSON.

    Attributes:
        converter (CSVToJSONConverter): CSV→JSON converter
        input_path (Path): Path to the source CSV
        output_path (Path): Path to the output JSON
    """

    def __init__(self, input_path: Path = None, output_path: Path = None, allow_too_long: bool = False):
        """
        Initializes the validator.

        Args:
            input_path: Path to the CSV (None = auto-detect)
            output_path: Path to the JSON (None = auto-generate)
        """
        self.converter = CSVToJSONConverter()
        self.converter.allow_too_long = allow_too_long
        self.input_path = input_path or self._find_latest_csv()
        self.output_path = output_path or self._generate_output_path()

    def _find_latest_csv(self) -> Path:
        """
        Finds the most recent CSV file.

        Returns:
            Path: Path to the file

        Raises:
            FileNotFoundError: If no file found
        """
        translation_dir = Path('output/translation')
        if not translation_dir.exists():
            raise FileNotFoundError("output/translation/ not found")

        csv_files = list(translation_dir.glob('*_translation_*.csv'))

        if not csv_files:
            raise FileNotFoundError("No CSV files found in output/translation/")

        return max(csv_files, key=lambda p: p.stat().st_mtime)

    def _generate_output_path(self) -> Path:
        """
        Generates the output path with date.

        Returns:
            Path: Path to the output JSON
        """
        output_dir = Path('output/translation')
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        return output_dir / f"{date_str}_translation_ready.json"

    def validate_and_convert(self) -> dict:
        """
        Validates the CSV and converts to JSON.

        Returns:
            dict: Conversion statistics

        Raises:
            ValueError: If validation errors are detected

        Example:
            >>> validator = TranslationValidator()
            >>> stats = validator.validate_and_convert()
            >>> print(stats['successful'])
            100
        """
        # Load and validate CSV
        print(f"📄 Loading CSV: {self.input_path.name}")
        print("🔍 Validating translations...")
        print()

        self.converter.load_from_csv(self.input_path)

        # Check for errors
        if self.converter.has_errors():
            raise ValueError("Validation failed - see errors below")

        # Save JSON
        print(f"💾 Generating JSON: {self.output_path.name}")
        self.converter.save_to_json(self.output_path, self.input_path.name)

        return self.converter.get_statistics()

    def print_results(self, stats: dict) -> None:
        """
        Prints conversion results.

        Args:
            stats: Statistics dictionary
        """
        print()
        print("=" * 80)
        print("CONVERSION RESULTS")
        print("=" * 80)
        print(f"Total rows:             {stats['total_rows']}")
        print(f"Successful translations:{stats['successful']}")
        print(f"Errors:                 {len(stats['errors'])}")
        print(f"Warnings:               {len(stats['warnings'])}")
        print()

    def print_errors(self, errors: list, limit: int = 10) -> None:
        """
        Prints validation errors.

        Args:
            errors: List of errors
            limit: Max number of errors to display
        """
        if not errors:
            return

        print("=" * 80)
        print("❌ ERRORS DETECTED")
        print("=" * 80)

        for error in errors[:limit]:
            print(f"\nRow {error['row']} - Offset {error['offset']}")
            print(f"  Original:    {error['original']}")
            print(f"  Translation: {error['translation']}")
            print(f"  Error:       {error['error']}")

        if len(errors) > limit:
            print(f"\n... and {len(errors) - limit} more errors")

        print()
        print("⚠️ Please fix these errors before continuing.")
        print()

    def print_warnings(self, warnings: list, limit: int = 5) -> None:
        """
        Prints warnings.

        Args:
            warnings: List of warnings
            limit: Max number of warnings to display
        """
        if not warnings:
            return

        print("=" * 80)
        print("⚠️ WARNINGS")
        print("=" * 80)

        for warning in warnings[:limit]:
            print(f"Row {warning['row']} - {warning['offset']}: {warning['message']}")

        if len(warnings) > limit:
            print(f"... and {len(warnings) - limit} more warnings")

        print()

    def print_success(self) -> None:
        """Prints the success message."""
        print("=" * 80)
        print("✅ CONVERSION SUCCESSFUL")
        print("=" * 80)
        print()
        print(f"Generated file: {self.output_path}")
        print()
        print("Next step:")
        print("  python src/translators/10_reinsert_smart_v2.py")
        print()


def main():
    """Main entry point."""
    print("=" * 80)
    print("09 - CSV TO JSON CONVERTER (v2 - OOP)")
    print("=" * 80)
    print()

    # Handle optional argument
    input_path = None
    allow_too_long = False
    args = sys.argv[1:]
    if '--allow-too-long' in args:
        allow_too_long = True
        args.remove('--allow-too-long')
    if args:
        input_path = Path(args[0])
        if not input_path.exists():
            print(f"❌ Error: File not found: {input_path}")
            sys.exit(1)

    try:
        # Create validator
        validator = TranslationValidator(input_path=input_path, allow_too_long=allow_too_long)

        # Validate and convert
        stats = validator.validate_and_convert()

        # Print results
        validator.print_results(stats)
        validator.print_warnings(stats['warnings'])
        validator.print_success()

    except ValueError as e:
        # Validation errors
        stats = validator.converter.get_statistics()
        validator.print_results(stats)
        validator.print_errors(stats['errors'])
        sys.exit(1)

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
