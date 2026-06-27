#!/usr/bin/env python3
"""
21 - Diagnose Spanish ROM Failures

Analyzes the 6 texts that fail during Spanish ROM construction
to understand exactly why they fail and how to fix them.

Usage:
    python src/translators/21_diagnose_spanish_rom_failures.py
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class FailedText:
    """Represents a failed text."""
    offset: int
    length: int
    english_text: str
    spanish_text: str
    failure_reason: str
    suggestions: List[str]


class SpanishROMFailureDiagnostics:
    """Diagnoses the 6 texts that fail in the Spanish ROM."""
    
    def __init__(self):
        self.english_texts = {}
        self.spanish_texts = {}
        self.failed_texts: List[FailedText] = []
    
    def run(self) -> bool:
        """Run the diagnostic."""
        print("="*70)
        print("🔍 SPANISH ROM FAILURE DIAGNOSTICS")
        print("="*70)
        
        # Load data
        if not self._load_data():
            return False

        # Analyze all offsets to identify problems
        self._analyze_failures()

        # Display results
        self._print_results()
        
        return True
    
    def _load_data(self) -> bool:
        """Load extracted texts."""
        print("\n📥 Loading data...")
        
        english_path = Path('output/extracted/extracted_texts/englishrom_texts.json')
        spanish_path = Path('output/extracted/extracted_texts/spanishrom_texts.json')
        
        try:
            if english_path.exists():
                with open(english_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get('texts', []):
                        self.english_texts[item['offset']] = item
                print(f"✅ English texts: {len(self.english_texts)}")

            if spanish_path.exists():
                with open(spanish_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get('texts', []):
                        self.spanish_texts[item['offset']] = item
                print(f"✅ Spanish texts: {len(self.spanish_texts)}")

            return True
        except Exception as e:
            print(f"❌ Loading error: {e}")
            return False
    
    def _analyze_failures(self):
        """Analyze failure reasons."""
        print("\n🔬 Analyzing failures...")
        
        # Load English offsets
        all_offsets = list(self.english_texts.keys())
        
        print(f"Total expected texts: {len(all_offsets)}")
        print(f"Texts found in Spanish: {len(self.spanish_texts)}")
        print(f"Difference: {len(all_offsets) - len(self.spanish_texts)}")

        # Find missing offsets
        missing_offsets = []
        for offset in all_offsets:
            if offset not in self.spanish_texts:
                missing_offsets.append(offset)

        print(f"\n🔴 Offsets MISSING in Spanish: {len(missing_offsets)}")
        
        for i, offset in enumerate(missing_offsets[:20]):  # Top 20
            english = self.english_texts.get(offset, {})
            english_text = english.get('text', '')
            length = english.get('length', 0)
            
            failure = FailedText(
                offset=offset,
                length=length,
                english_text=english_text,
                spanish_text='[NOT FOUND]',
                failure_reason='Offset not found in Spanish ROM extraction',
                suggestions=[
                    'Text may be at different offset in Spanish ROM',
                    'Text may have been moved/relocated',
                    'Text may not exist in Spanish ROM',
                    'Extraction issue in Spanish ROM'
                ]
            )
            self.failed_texts.append(failure)
        
        # Analyze length issues
        print(f"\n📏 Checking lengths...")
        
        length_issues = []
        for offset in self.spanish_texts.keys():
            english = self.english_texts.get(offset, {})
            spanish = self.spanish_texts.get(offset, {})
            
            if not english or not spanish:
                continue
            
            english_len = english.get('length', 0)
            spanish_len = spanish.get('length', 0)
            
            if english_len != spanish_len:
                length_issues.append({
                    'offset': offset,
                    'english_len': english_len,
                    'spanish_len': spanish_len,
                    'diff': spanish_len - english_len
                })
        
        if length_issues:
            print(f"⚠️  Found {len(length_issues)} offsets with length mismatches")
            print("\nTop 10 length issues:")
            for issue in sorted(length_issues, key=lambda x: abs(x['diff']), reverse=True)[:10]:
                offset = issue['offset']
                english = self.english_texts.get(offset, {})
                spanish = self.spanish_texts.get(offset, {})
                print(f"\n   Offset: 0x{offset:08X}")
                print(f"   English length: {issue['english_len']}")
                print(f"   Spanish length: {issue['spanish_len']}")
                print(f"   Difference: {issue['diff']:+d}")
                print(f"   English: {english.get('text', '')[:40]}...")
                print(f"   Spanish: {spanish.get('text', '')[:40]}...")
        
        # Analyze invalid lengths
        print(f"\n🚨 Checking invalid lengths...")
        
        invalid_lengths = []
        for offset, text_info in self.english_texts.items():
            length = text_info.get('length', 0)
            if length <= 0 or length > 1000:
                invalid_lengths.append((offset, length))
        
        if invalid_lengths:
            print(f"⚠️  Found {len(invalid_lengths)} offsets with invalid lengths")
            print("Examples:")
            for offset, length in invalid_lengths[:10]:
                english = self.english_texts[offset]
                failure = FailedText(
                    offset=offset,
                    length=length,
                    english_text=english.get('text', ''),
                    spanish_text='N/A',
                    failure_reason=f'Invalid length: {length}',
                    suggestions=[
                        f'Length {length} is invalid (must be 1-1000)',
                        'This is likely an extraction error',
                        'Text should be skipped during build'
                    ]
                )
                self.failed_texts.append(failure)
                print(f"   Offset 0x{offset:08X}: length={length}")
    
    def _print_results(self):
        """Print results."""
        print("\n" + "="*70)
        print("📊 RESULTS")
        print("="*70)

        print(f"\n📌 Potential reasons for the 6 failures:")
        print("""
1. INVALID LENGTHS (0 or > 1000)
   - These offsets have an invalid length
   - Cannot copy/validate
   - Probable reason: extraction error

2. MISSING OFFSETS IN SPANISH
   - Offset exists in English but not in Spanish
   - Spanish ROM has a different structure
   - Probable reason: local ROM does not contain this text

3. DIFFERENT LENGTHS
   - Same offset but different lengths
   - Cannot copy directly (incompatible format)
   - Probable reason: texts stored differently

4. DATA CORRUPTION
   - Data corrupted during extraction
   - Cannot validate
   - Probable reason: issue in the source ROM
""")
        
        if self.failed_texts:
            print(f"\n🔍 Details of {len(self.failed_texts)} identified problems:\n")

            for i, failure in enumerate(self.failed_texts[:10], 1):
                print(f"{i}. Offset 0x{failure.offset:08X} (length={failure.length})")
                print(f"   Reason: {failure.failure_reason}")
                print(f"   English: {failure.english_text[:50]}...")
                if failure.spanish_text != '[NOT FOUND]':
                    print(f"   Spanish: {failure.spanish_text[:50]}...")
                print(f"   Possible fixes:")
                for sugg in failure.suggestions:
                    print(f"     - {sugg}")
                print()
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        print("""
✅ Current Spanish ROM: 99.98% success (339,815/339,821)

The 6 failing texts are probably:
1. Invalid offsets (length 0 or > 1000)
2. Texts that don't exist in the Spanish ROM
3. Data corrupted during extraction

💡 NEXT STEPS:

1. Check exact details of the 6 failures
   └─ See output/reports/2026-01-14_sprom_build_report.json

2. Analyze if this is acceptable (0.02% loss)
   └─ Generally acceptable for ROM building

3. Fix options:
   ├─ Leave as-is (0.02% = 6 texts/339K)
   ├─ Pre-process extraction to validate lengths
   └─ Add fallback to English ROM for these cases

4. For other languages:
   └─ Use TRANSLATE strategy + strict validation
""")


def main():
    diagnostics = SpanishROMFailureDiagnostics()
    diagnostics.run()


if __name__ == '__main__':
    main()
