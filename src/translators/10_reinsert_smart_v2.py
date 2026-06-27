#!/usr/bin/env python3
"""
10 - Smart Text Reinsertion (Object-Oriented Version)

Reinserts translated texts into the ROM with intelligent padding management.
Uses reusable classes from the core module.

Usage:
    python src/translators/10_reinsert_smart_v2.py [translation_json]

Input:
    - input/roms/englishrom.gba
    - output/translation/*_translation_ready.json

Output:
    - output/roms/YYYY-MM-DD_frenchrom.gba
    - output/reports/YYYY-MM-DD_reinsertion_report.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_reinserter import ROMTranslationManager


class TranslationApplicator:
    """
    Applies translations to a GBA ROM.

    Attributes:
        rom_manager (ROMTranslationManager): ROM manager
        translation_path (Path): Path to translations JSON
        output_rom_path (Path): Path to output ROM
        report_path (Path): Path to report
    """

    def __init__(
        self,
        rom_path: str = 'input/roms/englishrom.gba',
        translation_path: Path = None
    ):
        """
        Initializes the applicator.

        Args:
            rom_path: Path to the source ROM
            translation_path: Path to the JSON (None = auto-detect)
        """
        self.rom_path = rom_path
        self.translation_path = translation_path or self._find_latest_json()
        self.output_rom_path = self._generate_output_path()
        self.report_path = self._generate_report_path()
        self.rom_manager = None
        self.translations = []

    def _find_latest_json(self) -> Path:
        """
        Finds the most recent translations JSON file.

        Returns:
            Path: Path to the file

        Raises:
            FileNotFoundError: If no file is found
        """
        translation_dir = Path('output/translation')
        if not translation_dir.exists():
            raise FileNotFoundError("output/translation/ not found")

        json_files = list(translation_dir.glob('*_translation_ready.json'))

        if not json_files:
            raise FileNotFoundError("No *_translation_ready.json found")

        return max(json_files, key=lambda p: p.stat().st_mtime)

    def _generate_output_path(self) -> Path:
        """
        Generates the output path for the ROM.

        Returns:
            Path: Output ROM path
        """
        output_dir = Path('output/roms')
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        return output_dir / f"{date_str}_frenchrom.gba"

    def _generate_report_path(self) -> Path:
        """
        Generates the report path.

        Returns:
            Path: Path to the JSON report
        """
        report_dir = Path('output/reports')
        report_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime('%Y-%m-%d')
        return report_dir / f"{date_str}_reinsertion_report.json"

    def load_translations(self) -> None:
        """
        Loads translations from the JSON file.

        Raises:
            FileNotFoundError: If the file does not exist
            json.JSONDecodeError: If the JSON is invalid
        """
        print(f"📄 Loading translations: {self.translation_path.name}")

        with open(self.translation_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.translations = data['translations']
        print(f"   {len(self.translations)} translations to insert")

    def load_rom(self) -> None:
        """
        Loads the source ROM.

        Raises:
            FileNotFoundError: If the ROM does not exist
        """
        print(f"📖 Loading ROM: {self.rom_path}")

        self.rom_manager = ROMTranslationManager(self.rom_path)
        info = self.rom_manager.get_rom_info()

        print(f"   ROM: {info['title']} ({info['game_code']})")
        print(f"   Size: {info['size_mb']} MB")

    def apply_translations(self) -> dict:
        """
        Applies all translations to the ROM.

        Returns:
            dict: Reinsertion report

        Example:
            >>> applicator = TranslationApplicator()
            >>> report = applicator.apply_translations()
            >>> print(report['statistics']['successful'])
            100
        """
        print()
        print("🔄 Reinserting translations...")

        # Apply translations with progress tracking
        total = len(self.translations)
        for i in range(0, total, 1000):
            batch = self.translations[i:min(i + 1000, total)]
            self.rom_manager.reinserter.reinsert_all(batch)
            print(f"   Processed: {min(i + 1000, total)}/{total}")

        report = self.rom_manager.reinserter.get_report()

        print()
        print(f"✅ {total} texts processed")
        print()

        return report

    def save_rom(self) -> None:
        """Saves the modified ROM."""
        print(f"💾 Saving ROM: {self.output_rom_path}")
        self.rom_manager.save_rom(str(self.output_rom_path))

    def save_report(self, report: dict) -> None:
        """
        Saves the reinsertion report.

        Args:
            report: Report to save
        """
        print(f"💾 Saving report: {self.report_path}")

        with open(self.report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def print_results(self, report: dict) -> None:
        """
        Displays the reinsertion results.

        Args:
            report: Reinsertion report
        """
        print()
        print("=" * 80)
        print("REINSERTION RESULTS")
        print("=" * 80)

        stats = report['statistics']
        print(f"Total texts:          {stats['total_texts']}")
        print(f"Success:              {stats['successful']}")
        print(f"Failed:               {stats['failed']}")
        print(f"Used padding:         {stats['used_padding']}")
        print(f"Success rate:         {stats['success_rate']}")
        print()

        # Display warnings
        if report['warnings']:
            print("⚠️ WARNINGS:")
            for warning in report['warnings'][:5]:
                print(f"  {warning['offset']}: {warning['error']}")
            if len(report['warnings']) > 5:
                print(f"  ... and {len(report['warnings']) - 5} more")
            print()

    def print_success(self) -> None:
        """Displays the success message."""
        print("=" * 80)
        print("✅ REINSERTION COMPLETE")
        print("=" * 80)
        print()
        print(f"Translated ROM: {self.output_rom_path}")
        print(f"Report:         {self.report_path}")
        print()
        print("Next step:")
        print("  Test the ROM on an emulator (mGBA, VBA, etc.)")
        print()

    def run(self) -> None:
        """
        Executes the full reinsertion process.

        Example:
            >>> applicator = TranslationApplicator()
            >>> applicator.run()
        """
        try:
            # Load data
            self.load_translations()
            print()
            self.load_rom()

            # Apply translations
            report = self.apply_translations()

            # Save results
            self.save_rom()
            self.save_report(report)

            # Display results
            self.print_results(report)
            self.print_success()

        except Exception as e:
            print()
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


def main():
    """Main entry point."""
    print("=" * 80)
    print("10 - SMART TEXT REINSERTION (v2 - OOP)")
    print("=" * 80)
    print()

    # Handle optional argument
    translation_path = None
    if len(sys.argv) > 1:
        translation_path = Path(sys.argv[1])
        if not translation_path.exists():
            print(f"❌ Error: File not found: {translation_path}")
            sys.exit(1)

    # Create and run applicator
    applicator = TranslationApplicator(translation_path=translation_path)
    applicator.run()


if __name__ == "__main__":
    main()
