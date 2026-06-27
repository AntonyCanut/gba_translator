#!/usr/bin/env python3
"""
14 - Compare Padding Detection Methods

Compares standard vs enhanced detection to identify
potential gains on 7-10 byte overflow cases.

Usage:
    python src/translators/14_compare_padding_methods.py

Input:
    - input/roms/englishrom.gba
    - output/differences/*_diff_only.json

Output:
    - output/analysis/YYYY-MM-DD_padding_comparison.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader
from src.core.padding_detector import PaddingDetector
from src.core.enhanced_padding_detector import EnhancedPaddingDetector


class PaddingMethodComparator:
    """
    Compares padding detection methods.

    Compares standard PaddingDetector vs EnhancedPaddingDetector
    to identify possible improvements.
    """

    def __init__(self, rom_path: str, diff_only_path: Path):
        """
        Initializes the comparator.

        Args:
            rom_path: Path to the ROM
            diff_only_path: Path to diff_only.json
        """
        self.rom = ROMReader(rom_path)
        self.diff_only_path = diff_only_path

        self.standard_detector = None
        self.enhanced_detector = None

        self.texts = []
        self.results = {
            'standard': {},
            'enhanced': {},
            'comparison': {}
        }

    def load_rom(self) -> None:
        """Loads the ROM."""
        print("📖 Loading ROM...")
        self.rom.load()
        info = self.rom.get_rom_info()
        print(f"   ROM: {info['title']} ({info['game_code']})")
        print(f"   Size: {info['size_mb']} MB")

    def load_texts(self) -> None:
        """Loads the texts to analyze."""
        print()
        print("📄 Loading texts...")

        with open(self.diff_only_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.texts = data['texts']
        print(f"   Texts loaded: {len(self.texts)}")

    def analyze_standard(self) -> None:
        """Analysis with standard method."""
        print()
        print("🔍 Analysis with STANDARD detection...")

        self.standard_detector = PaddingDetector(self.rom)
        enriched = self.standard_detector.analyze_all_texts(self.texts)

        self.results['standard'] = {
            'enriched_texts': enriched,
            'report': self.standard_detector.generate_report()
        }

        stats = self.results['standard']['report']['statistics']
        print(f"✅ Analysis complete")
        print(f"   Average padding: {stats['average_padding']}")

    def analyze_enhanced(self) -> None:
        """Analysis with enhanced method."""
        print()
        print("🔍 Analysis with ENHANCED detection...")

        self.enhanced_detector = EnhancedPaddingDetector(
            self.rom,
            aggressive_mode=True
        )
        enriched = self.enhanced_detector.analyze_all_texts_enhanced(self.texts)

        self.results['enhanced'] = {
            'enriched_texts': enriched,
            'report': self.enhanced_detector.generate_enhanced_report()
        }

        stats = self.results['enhanced']['report']['statistics']
        print(f"✅ Analysis complete")
        print(f"   Average padding: {stats['average_padding']}")

    def compare_results(self) -> dict:
        """
        Compares the two methods.

        Returns:
            dict: Comparison report
        """
        print()
        print("📊 Comparing methods...")

        standard_texts = self.results['standard']['enriched_texts']
        enhanced_texts = self.results['enhanced']['enriched_texts']

        improvements = []
        total_gain = 0
        high_confidence_gains = 0

        for std, enh in zip(standard_texts, enhanced_texts):
            std_padding = std['padding_available']
            enh_padding = enh['padding_extended']
            gain = enh_padding - std_padding

            if gain > 0:
                confidence = enh.get('padding_confidence', 'unknown')

                improvement = {
                    'offset': f"0x{std['offset']:08X}",
                    'text': std['text'][:50],
                    'standard_padding': std_padding,
                    'extended_padding': enh_padding,
                    'gain': gain,
                    'confidence': confidence,
                    'original_length': std['length'],
                    'standard_max': std['real_max_length'],
                    'extended_max': enh['real_max_length_extended']
                }

                improvements.append(improvement)
                total_gain += gain

                if confidence == 'high':
                    high_confidence_gains += 1

        # Sort by gain
        improvements.sort(key=lambda x: x['gain'], reverse=True)

        comparison = {
            'total_texts': len(self.texts),
            'improvements_found': len(improvements),
            'total_padding_gain': total_gain,
            'average_gain': total_gain / len(improvements) if improvements else 0,
            'high_confidence_gains': high_confidence_gains,
            'high_confidence_percentage': (
                100 * high_confidence_gains / len(improvements)
                if improvements else 0
            ),
            'top_20_improvements': improvements[:20],
            'by_gain_range': self._categorize_by_gain(improvements)
        }

        self.results['comparison'] = comparison

        return comparison

    def _categorize_by_gain(self, improvements: list) -> dict:
        """
        Categorizes improvements by gain range.

        Args:
            improvements: List of improvements

        Returns:
            dict: Statistics by range
        """
        ranges = {
            '1-3 bytes': 0,
            '4-6 bytes': 0,
            '7-10 bytes': 0,
            '11+ bytes': 0
        }

        for imp in improvements:
            gain = imp['gain']
            if 1 <= gain <= 3:
                ranges['1-3 bytes'] += 1
            elif 4 <= gain <= 6:
                ranges['4-6 bytes'] += 1
            elif 7 <= gain <= 10:
                ranges['7-10 bytes'] += 1
            else:
                ranges['11+ bytes'] += 1

        return ranges

    def print_comparison(self, comparison: dict) -> None:
        """
        Prints the comparison report.

        Args:
            comparison: Comparison report
        """
        print()
        print("=" * 80)
        print("COMPARISON RESULTS")
        print("=" * 80)

        print(f"Texts analyzed:          {comparison['total_texts']}")
        print(f"Improvements found:      {comparison['improvements_found']}")
        print(f"Total padding gain:      {comparison['total_padding_gain']} bytes")
        print(f"Average gain:            {comparison['average_gain']:.1f} bytes")
        print()

        print(f"High-confidence gains:   {comparison['high_confidence_gains']}")
        print(f"Percentage:              {comparison['high_confidence_percentage']:.1f}%")
        print()

        print("=" * 80)
        print("BY GAIN RANGE")
        print("=" * 80)

        for range_name, count in comparison['by_gain_range'].items():
            pct = 100 * count / comparison['improvements_found'] if comparison['improvements_found'] else 0
            print(f"{range_name:15s}: {count:4d} ({pct:5.1f}%)")

        print()
        print("=" * 80)
        print("TOP 10 IMPROVEMENTS")
        print("=" * 80)

        for i, imp in enumerate(comparison['top_20_improvements'][:10], 1):
            print(f"\n{i}. Offset {imp['offset']} - Gain: +{imp['gain']} bytes ({imp['confidence']})")
            print(f"   Text: \"{imp['text']}\"")
            print(f"   Standard: {imp['standard_padding']} → Max {imp['standard_max']}")
            print(f"   Enhanced: {imp['extended_padding']} → Max {imp['extended_max']}")

    def save_report(self) -> Path:
        """
        Saves the complete report.

        Returns:
            Path: Path of the saved file
        """
        output_dir = Path('output/analysis')
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        report_path = output_dir / f"{date_str}_padding_comparison.json"

        report = {
            'comparison_date': date_str,
            'rom_info': self.rom.get_rom_info(),
            'standard_report': self.results['standard']['report'],
            'enhanced_report': self.results['enhanced']['report'],
            'comparison': self.results['comparison']
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return report_path

    def run(self) -> dict:
        """
        Runs the complete comparison.

        Returns:
            dict: Comparison report
        """
        self.load_rom()
        self.load_texts()
        self.analyze_standard()
        self.analyze_enhanced()
        comparison = self.compare_results()
        self.print_comparison(comparison)
        report_path = self.save_report()

        print()
        print("=" * 80)
        print("✅ COMPARISON COMPLETE")
        print("=" * 80)
        print()
        print(f"Report saved: {report_path}")
        print()

        # Recommendations
        print("RECOMMENDATIONS:")
        print("-" * 80)

        total_improvements = comparison['improvements_found']
        high_conf = comparison['high_confidence_gains']

        if high_conf > 0:
            print(f"✅ {high_conf} high-confidence improvements detected")
            print("   → Recommended to use EnhancedPaddingDetector")
        else:
            print("⚠️ No high-confidence improvements detected")
            print("   → Standard PaddingDetector is sufficient")

        print()

        return comparison


def find_latest_diff_file() -> Path:
    """Finds the most recent diff_only.json file."""
    diff_dir = Path('output/differences')
    if not diff_dir.exists():
        raise FileNotFoundError("output/differences/ not found")

    diff_files = list(diff_dir.glob('*_diff_only.json'))

    if not diff_files:
        raise FileNotFoundError("No *_diff_only.json found")

    return max(diff_files, key=lambda p: p.stat().st_mtime)


def main():
    """Main entry point."""
    print("=" * 80)
    print("14 - COMPARE PADDING DETECTION METHODS")
    print("=" * 80)
    print()

    rom_path = 'input/roms/englishrom.gba'

    # Check ROM
    if not Path(rom_path).exists():
        print(f"❌ Error: {rom_path} not found")
        sys.exit(1)

    # Find diff_only
    try:
        diff_only_path = find_latest_diff_file()
        print(f"📄 Diff file: {diff_only_path.name}")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print()

    try:
        # Create and run comparator
        comparator = PaddingMethodComparator(rom_path, diff_only_path)
        comparison = comparator.run()

        sys.exit(0)

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
