#!/usr/bin/env python3
"""
Translation Validator
Validates translation JSON files before applying them to ROM.
"""

import sys
import json
from pathlib import Path


class TranslationValidator:
    def __init__(self, translation_json):
        self.translation_json = Path(translation_json)
        self.texts_data = None
        self.errors = []
        self.warnings = []
        self.stats = {
            'total_texts': 0,
            'texts_longer': 0,
            'texts_same_size': 0,
            'texts_shorter': 0,
            'will_need_relocation': 0,
            'potential_issues': 0
        }

    def load_translation(self):
        """Load translation JSON."""
        with open(self.translation_json, 'r', encoding='utf-8') as f:
            self.texts_data = json.load(f)

        self.stats['total_texts'] = len(self.texts_data.get('texts', []))
        print(f"Loaded translation file: {self.translation_json.name}")
        print(f"Total texts: {self.stats['total_texts']}")

    def validate_structure(self):
        """Validate JSON structure."""
        print("\nValidating structure...")

        if 'texts' not in self.texts_data:
            self.errors.append("Missing 'texts' key in JSON")
            return

        if not isinstance(self.texts_data['texts'], list):
            self.errors.append("'texts' must be an array")
            return

        print("✓ Structure is valid")

    def validate_texts(self):
        """Validate each text entry."""
        print("\nValidating text entries...")

        required_fields = ['offset', 'text', 'length', 'encoding']

        for i, entry in enumerate(self.texts_data['texts']):
            # Check required fields
            for field in required_fields:
                if field not in entry:
                    self.errors.append(f"Text #{i}: Missing field '{field}'")
                    continue

            # Validate offset
            if not isinstance(entry['offset'], int) or entry['offset'] < 0:
                self.errors.append(f"Text #{i}: Invalid offset {entry['offset']}")

            # Validate text
            if not isinstance(entry['text'], str):
                self.errors.append(f"Text #{i}: Text must be a string")

            # Validate length
            if not isinstance(entry['length'], int) or entry['length'] <= 0:
                self.errors.append(f"Text #{i}: Invalid length {entry['length']}")

            # Validate encoding
            if entry['encoding'] not in ['ascii', 'pokemon']:
                self.errors.append(f"Text #{i}: Invalid encoding '{entry['encoding']}'")

            # Check text length vs original
            text = entry['text']
            original_length = entry['length']

            # Estimate encoded length (Pokemon encoding adds 1 byte for terminator)
            if entry['encoding'] == 'pokemon':
                estimated_length = len(text) + 1  # +1 for 0xFF terminator
            else:
                estimated_length = len(text)

            if estimated_length > original_length:
                self.stats['texts_longer'] += 1
                self.stats['will_need_relocation'] += 1
                self.warnings.append(
                    f"Text #{i} at 0x{entry['offset']:08X}: "
                    f"Longer than original ({estimated_length} > {original_length}) - "
                    f"will need relocation"
                )
            elif estimated_length == original_length:
                self.stats['texts_same_size'] += 1
            else:
                self.stats['texts_shorter'] += 1

            # Check for unsupported characters
            if entry['encoding'] == 'pokemon':
                unsupported = self.check_pokemon_chars(text)
                if unsupported:
                    self.stats['potential_issues'] += 1
                    self.warnings.append(
                        f"Text #{i} at 0x{entry['offset']:08X}: "
                        f"Contains unsupported characters: {unsupported}"
                    )

        print(f"✓ Validated {self.stats['total_texts']} text entries")

    def check_pokemon_chars(self, text):
        """Check for unsupported Pokemon encoding characters."""
        SUPPORTED_CHARS = set(
            ' ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            '0123456789!?.-,\':;()[]&/\n'
        )

        unsupported = []
        for char in text:
            if char not in SUPPORTED_CHARS:
                if char not in unsupported:
                    unsupported.append(char)

        return unsupported

    def generate_report(self):
        """Generate validation report."""
        print("\n" + "="*80)
        print("VALIDATION REPORT")
        print("="*80)

        # Statistics
        print("\nStatistics:")
        print(f"  Total texts: {self.stats['total_texts']}")
        print(f"  Texts longer than original: {self.stats['texts_longer']}")
        print(f"  Texts same size: {self.stats['texts_same_size']}")
        print(f"  Texts shorter: {self.stats['texts_shorter']}")

        if self.stats['will_need_relocation'] > 0:
            print(f"\n⚠️  {self.stats['will_need_relocation']} text(s) will need relocation")
            print("   Use 'translate_rom.py' for automatic relocation")

        if self.stats['potential_issues'] > 0:
            print(f"\n⚠️  {self.stats['potential_issues']} text(s) contain unsupported characters")

        # Errors
        if self.errors:
            print("\n" + "="*80)
            print(f"❌ ERRORS ({len(self.errors)}):")
            print("="*80)
            for error in self.errors:
                print(f"  • {error}")
            return False

        # Warnings
        if self.warnings:
            print("\n" + "="*80)
            print(f"⚠️  WARNINGS ({len(self.warnings)}):")
            print("="*80)
            for i, warning in enumerate(self.warnings[:20]):  # Show first 20
                print(f"  • {warning}")

            if len(self.warnings) > 20:
                print(f"  ... and {len(self.warnings) - 20} more warnings")

        # Summary
        print("\n" + "="*80)
        if not self.errors:
            print("✅ VALIDATION PASSED")
            if self.warnings:
                print(f"   ({len(self.warnings)} warnings to review)")
            else:
                print("   No issues found!")
        else:
            print("❌ VALIDATION FAILED")
            print(f"   {len(self.errors)} error(s) must be fixed")

        print("="*80)

        return len(self.errors) == 0

    def save_report(self, output_path):
        """Save detailed report to JSON."""
        report = {
            'translation_file': str(self.translation_json),
            'validation_passed': len(self.errors) == 0,
            'statistics': self.stats,
            'errors': self.errors,
            'warnings': self.warnings
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\nDetailed report saved to: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_translation.py <translation.json> [report.json]")
        print("\nValidates a translation JSON file before applying it to ROM.")
        print("\nExample:")
        print("  python validate_translation.py differences/englishrom_diff_only.json")
        sys.exit(1)

    translation_file = sys.argv[1]

    if not Path(translation_file).exists():
        print(f"Error: Translation file '{translation_file}' not found")
        sys.exit(1)

    # Validate
    validator = TranslationValidator(translation_file)
    validator.load_translation()
    validator.validate_structure()
    validator.validate_texts()
    passed = validator.generate_report()

    # Save detailed report if requested
    if len(sys.argv) >= 3:
        report_file = sys.argv[2]
        validator.save_report(report_file)

    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
