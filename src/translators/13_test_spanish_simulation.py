#!/usr/bin/env python3
"""
13 - Test Simulation Spanish ROM

Automatically tests 10% of Spanish translations to validate
that our system can handle all overflow cases.

Usage:
    python src/translators/13_test_spanish_simulation.py

Input:
    - input/roms/englishrom.gba
    - input/roms/spanishrom.gba
    - output/differences/2026-01-13_diff_with_padding.json

Output:
    - output/tests/YYYY-MM-DD_spanish_simulation_report.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader
from src.core.padding_detector import PaddingDetector
from src.core.text_validator import TextValidator
from src.core.text_reinserter import SmartReinserter, ROMTranslationManager
from src.core.text_codec import TextDecoder


class SpanishSimulationTester:
    """
    Tests the system with real Spanish translations.

    Validates that our system can handle all overflow cases
    by simulating 10% of Spanish insertions.

    Attributes:
        english_rom (ROMReader): English ROM
        spanish_rom (ROMReader): Spanish ROM
        test_sample (List[dict]): Sample of texts to test (1 in 10)
        results (dict): Test results
    """

    def __init__(
        self,
        english_rom_path: str,
        spanish_rom_path: str,
        diff_with_padding_path: Path,
        sample_rate: int = 1
    ):
        """
        Initializes the tester.

        Args:
            english_rom_path: Path to English ROM
            spanish_rom_path: Path to Spanish ROM
            diff_with_padding_path: Path to diff_with_padding.json
            sample_rate: Sampling rate (1 = 100%, 10 = 10%, etc.)
        """
        self.english_rom = ROMReader(english_rom_path)
        self.spanish_rom = ROMReader(spanish_rom_path)
        self.diff_with_padding_path = diff_with_padding_path
        self.sample_rate = sample_rate

        self.test_sample: List[dict] = []
        self.results = {
            'total_tested': 0,
            'success': 0,
            'failed': 0,
            'cases': {
                'shorter': {'count': 0, 'success': 0},
                'same': {'count': 0, 'success': 0},
                'overflow_1_3': {'count': 0, 'success': 0},
                'overflow_4_6': {'count': 0, 'success': 0},
                'overflow_7_10': {'count': 0, 'success': 0},
                'overflow_11_plus': {'count': 0, 'success': 0},
            },
            'failures': []
        }

    def load_roms(self) -> None:
        """Loads the ROMs into memory."""
        print("📖 Loading ROMs...")
        self.english_rom.load()
        self.spanish_rom.load()
        print(f"   English ROM: {self.english_rom.get_rom_info()['title']}")
        print(f"   Spanish ROM: {self.spanish_rom.get_rom_info()['title']}")

    def load_test_sample(self) -> None:
        """
        Loads texts for testing (with sampling rate applied).
        """
        print()
        print("📄 Loading test texts...")

        with open(self.diff_with_padding_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        texts = data['texts']

        # Apply sampling rate
        self.test_sample = [texts[i] for i in range(0, len(texts), self.sample_rate)]

        print(f"   Total texts: {len(texts)}")
        print(f"   Texts to test: {len(self.test_sample)} ({100//self.sample_rate}%)")

    def extract_spanish_text(self, offset: int, encoding: str) -> str:
        """
        Extracts Spanish text at a given offset.

        Args:
            offset: Offset in the ROM
            encoding: Encoding type ('ascii' or 'pokemon')

        Returns:
            str: Decoded Spanish text
        """
        text_bytes = bytearray()
        i = 0
        max_length = 200  # Safety limit

        while i < max_length:
            if offset + i >= len(self.spanish_rom.rom_data):
                break

            byte = self.spanish_rom.rom_data[offset + i]
            text_bytes.append(byte)

            # Terminators
            if encoding == 'ascii' and byte == 0x00:
                break
            if encoding == 'pokemon' and byte == 0xFF:
                break

            i += 1

        if encoding == 'ascii':
            return TextDecoder.decode_ascii(bytes(text_bytes))
        return TextDecoder.decode_pokemon(bytes(text_bytes))

    def categorize_overflow(self, overflow: int) -> str:
        """
        Categorizes the overflow type.

        Args:
            overflow: Number of overflow bytes

        Returns:
            str: Category
        """
        if overflow < 0:
            return 'shorter'
        elif overflow == 0:
            return 'same'
        elif 1 <= overflow <= 3:
            return 'overflow_1_3'
        elif 4 <= overflow <= 6:
            return 'overflow_4_6'
        elif 7 <= overflow <= 10:
            return 'overflow_7_10'
        else:
            return 'overflow_11_plus'

    def test_text_insertion(self, text_entry: dict) -> Tuple[bool, dict]:
        """
        Tests the insertion of a Spanish text.

        Args:
            text_entry: Text entry with padding info

        Returns:
            Tuple[bool, dict]: (success, test_details)
        """
        offset = text_entry['offset']
        english_text = text_entry['text']
        english_length = text_entry['length']
        encoding = text_entry['encoding']
        padding_available = text_entry['padding_available']
        real_max_length = text_entry['real_max_length']

        # Extract Spanish text
        spanish_text = self.extract_spanish_text(offset, encoding)
        spanish_length = len(spanish_text)

        # Calculate overflow
        overflow = spanish_length - english_length

        # Can our system handle this case?
        can_handle = spanish_length <= real_max_length

        # Categorize
        category = self.categorize_overflow(overflow)

        test_details = {
            'offset': f"0x{offset:08X}",
            'english_text': english_text,
            'english_length': english_length,
            'spanish_text': spanish_text,
            'spanish_length': spanish_length,
            'overflow': overflow,
            'padding_available': padding_available,
            'real_max_length': real_max_length,
            'category': category,
            'can_handle': can_handle,
            'success': can_handle
        }

        return can_handle, test_details

    def run_tests(self) -> None:
        """Runs all tests on the sample."""
        print()
        print("🧪 Running tests...")
        print()

        total = len(self.test_sample)
        skipped = 0

        for i, text_entry in enumerate(self.test_sample):
            if (i + 1) % 100 == 0:
                print(f"   Tested: {i + 1}/{total} (skipped: {skipped})")

            success, details = self.test_text_insertion(text_entry)

            # Check if this is a false positive (corrupted data)
            should_skip, skip_reason = TextValidator.should_skip_test(
                details['english_text'],
                details['spanish_text']
            )

            if should_skip:
                skipped += 1
                details['skipped'] = True
                details['skip_reason'] = skip_reason
                # Do not count in statistics
                continue

            self.results['total_tested'] += 1

            if success:
                self.results['success'] += 1
            else:
                self.results['failed'] += 1
                self.results['failures'].append(details)

            # Statistics by category
            category = details['category']
            self.results['cases'][category]['count'] += 1
            if success:
                self.results['cases'][category]['success'] += 1

        print(f"✅ {total} texts tested ({skipped} skipped - corrupted data)")

    def generate_report(self) -> dict:
        """
        Generates a detailed report.

        Returns:
            dict: Complete report
        """
        total = self.results['total_tested']
        success = self.results['success']
        failed = self.results['failed']

        success_rate = 100 * success / total if total > 0 else 0

        # Statistics by category
        cases_stats = {}
        for category, data in self.results['cases'].items():
            count = data['count']
            success_cat = data['success']
            if count > 0:
                rate = 100 * success_cat / count
                cases_stats[category] = {
                    'count': count,
                    'success': success_cat,
                    'failed': count - success_cat,
                    'success_rate': f"{rate:.1f}%"
                }

        report = {
            'test_date': datetime.now().isoformat(),
            'sample_size': '10% (1 text in 10)',
            'summary': {
                'total_tested': total,
                'success': success,
                'failed': failed,
                'success_rate': f"{success_rate:.1f}%"
            },
            'by_category': cases_stats,
            'failures': self.results['failures'][:20],  # Top 20 failures
            'total_failures': len(self.results['failures'])
        }

        return report

    def print_results(self, report: dict) -> None:
        """
        Prints the test results.

        Args:
            report: Generated report
        """
        print()
        print("=" * 80)
        print("TEST RESULTS")
        print("=" * 80)

        summary = report['summary']
        print(f"Total tested:      {summary['total_tested']}")
        print(f"Success:           {summary['success']}")
        print(f"Failed:            {summary['failed']}")
        print(f"Success rate:      {summary['success_rate']}")
        print()

        print("=" * 80)
        print("BY CATEGORY")
        print("=" * 80)

        for category, stats in report['by_category'].items():
            print(f"\n{category.replace('_', ' ').title()}:")
            print(f"  Total:         {stats['count']}")
            print(f"  Success:       {stats['success']}")
            print(f"  Failed:        {stats['failed']}")
            print(f"  Rate:          {stats['success_rate']}")

        print()

        if report['total_failures'] > 0:
            print("=" * 80)
            print("FAILURES DETECTED")
            print("=" * 80)
            print()

            for i, failure in enumerate(report['failures'][:10], 1):
                print(f"{i}. Offset {failure['offset']} - {failure['category']}")
                print(f"   EN: \"{failure['english_text']}\" ({failure['english_length']})")
                print(f"   ES: \"{failure['spanish_text']}\" ({failure['spanish_length']})")
                print(f"   Overflow: {failure['overflow']} bytes")
                print(f"   Padding available: {failure['padding_available']}")
                print(f"   Max allowed: {failure['real_max_length']}")
                print()

            if report['total_failures'] > 10:
                print(f"... and {report['total_failures'] - 10} more failures")
                print()

    def save_report(self, report: dict) -> Path:
        """
        Saves the report as JSON.

        Args:
            report: Report to save

        Returns:
            Path: Path of the saved file
        """
        output_dir = Path('output/tests')
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        report_path = output_dir / f"{date_str}_spanish_simulation_report.json"

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return report_path

    def run(self) -> dict:
        """
        Runs the complete test.

        Returns:
            dict: Final report
        """
        self.load_roms()
        self.load_test_sample()
        self.run_tests()
        report = self.generate_report()
        self.print_results(report)
        report_path = self.save_report(report)

        print("=" * 80)
        print("✅ TESTS COMPLETE")
        print("=" * 80)
        print()
        print(f"Report saved: {report_path}")
        print()

        return report


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Spanish ROM simulation test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/translators/13_test_spanish_simulation.py         # Test 100%
  python src/translators/13_test_spanish_simulation.py --sample 10  # Test 10%
        """
    )
    parser.add_argument('--sample', type=int, default=1,
                        help='Sampling rate (1=100%%, 10=10%%, etc.)')
    args = parser.parse_args()

    print("=" * 80)
    print("13 - TEST SIMULATION SPANISH ROM")
    print("=" * 80)
    print()

    sample_percent = 100 // args.sample
    print(f"Automatic test of {sample_percent}% of Spanish translations")
    if args.sample > 1:
        print(f"(1 text in {args.sample} for system validation)")
    else:
        print("(Full test - ALL texts)")
    print()

    # Paths
    english_rom = 'input/roms/englishrom.gba'
    spanish_rom = 'input/roms/spanishrom.gba'
    diff_with_padding = Path('output/differences/2026-01-13_diff_with_padding.json')

    # Check file existence
    if not Path(english_rom).exists():
        print(f"❌ Error: {english_rom} not found")
        sys.exit(1)

    if not Path(spanish_rom).exists():
        print(f"❌ Error: {spanish_rom} not found")
        sys.exit(1)

    if not diff_with_padding.exists():
        print(f"❌ Error: {diff_with_padding} not found")
        print("   Run first: python src/translators/06_detect_padding.py")
        sys.exit(1)

    try:
        # Create and run tester
        tester = SpanishSimulationTester(
            english_rom,
            spanish_rom,
            diff_with_padding,
            sample_rate=args.sample
        )

        report = tester.run()

        # Check for failures
        if report['summary']['failed'] > 0:
            print("⚠️ WARNING: Failures were detected")
            print("   See report for more details")
            sys.exit(1)
        else:
            print("🎉 All tests passed successfully!")
            sys.exit(0)

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
