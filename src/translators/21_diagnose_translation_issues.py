#!/usr/bin/env python3
"""
21 - Diagnose Translation Issues

Analyzes translation problems in detail to understand
why certain texts fail during ROM construction.

Features:
- Validates each text individually
- Encodes and tests Pokémon encoding
- Detects texts that are too long/short
- Analyzes unsupported characters
- Generates a detailed report
- Suggests corrections

Usage:
    python src/translators/21_diagnose_translation_issues.py \
        --translations output/translation/french_texts.json \
        --output output/reports/diagnosis.json
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_validator import TextValidator
from src.core.text_reinserter import TextEncoder


@dataclass
class TextIssue:
    """Represents an identified problem."""
    offset: int
    issue_type: str
    severity: str  # critical, warning, info
    message: str
    english_text: str
    french_text: str
    length: int
    suggested_fix: Optional[str] = None


class TranslationDiagnostics:
    """Diagnoses translation problems."""
    
    def __init__(self, translations_path: Path):
        self.translations_path = translations_path
        self.translations = {}
        self.issues: List[TextIssue] = []
        self.validator = TextValidator()
        self.statistics = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'too_long': 0,
            'too_short': 0,
            'encoding_error': 0,
            'empty': 0,
            'unchanged': 0,
            'special_chars': 0,
            'encoding_failed': 0,
        }
    
    def run(self) -> bool:
        """Run complete diagnostic."""
        print("="*70)
        print("🔍 TRANSLATION DIAGNOSTICS")
        print("="*70)
        
        if not self._load_translations():
            return False
        
        print(f"\n📊 Analyzing {len(self.translations)} texts...")

        for i, (offset, item) in enumerate(self.translations.items()):
            self._diagnose_single_text(offset, item)

            if (i + 1) % 5000 == 0:
                print(f"   Analyzed: {i+1}/{len(self.translations)}")
        
        self._print_summary()
        return True
    
    def _load_translations(self) -> bool:
        """Load translations."""
        try:
            with open(self.translations_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                texts_list = data.get('translations', data.get('texts', []))
                
                for item in texts_list:
                    offset = item.get('offset')
                    if offset:
                        self.translations[offset] = item
            
            print(f"✅ {len(self.translations)} translations loaded")
            self.statistics['total'] = len(self.translations)
            return True
        
        except Exception as e:
            print(f"❌ Loading error: {e}")
            return False
    
    def _diagnose_single_text(self, offset: int, item: Dict):
        """Diagnose a single text."""
        english_text = item.get('english', '')
        french_text = item.get('text', '') or item.get('french', '')
        length = item.get('length', 0)

        # Check 1: Empty text
        if not french_text or not french_text.strip():
            self.statistics['empty'] += 1
            if french_text == english_text:
                self.statistics['unchanged'] += 1
            else:
                self.issues.append(TextIssue(
                    offset=offset,
                    issue_type='empty_translation',
                    severity='warning',
                    message='Translation is empty',
                    english_text=english_text,
                    french_text=french_text,
                    length=length,
                    suggested_fix='Add French translation'
                ))
            return
        
        # Check 2: Unchanged text
        if french_text == english_text:
            self.statistics['unchanged'] += 1
            return
        
        # Check 3: Basic validity
        if not self.validator.is_valid_game_text(french_text):
            self.statistics['invalid'] += 1
            self.issues.append(TextIssue(
                offset=offset,
                issue_type='invalid_text',
                severity='critical',
                message=f'Text fails basic validation',
                english_text=english_text,
                french_text=french_text,
                length=length
            ))
            return
        
        # Check 4: Pokémon encoding
        try:
            encoded_french = TextEncoder.encode_pokemon(french_text)
            encoded_english = TextEncoder.encode_pokemon(english_text)
            
            # Check 5: Length
            if len(encoded_french) > length:
                self.statistics['too_long'] += 1
                extra = len(encoded_french) - length
                self.issues.append(TextIssue(
                    offset=offset,
                    issue_type='text_too_long',
                    severity='warning',
                    message=f'Text too long by {extra} bytes ({len(encoded_french)} vs {length})',
                    english_text=english_text,
                    french_text=french_text,
                    length=length,
                    suggested_fix='Shorten French translation or use abbreviations'
                ))
            elif len(encoded_french) < length * 0.2:
                self.statistics['too_short'] += 1
                self.issues.append(TextIssue(
                    offset=offset,
                    issue_type='text_too_short',
                    severity='info',
                    message=f'Text much shorter than allocated space',
                    english_text=english_text,
                    french_text=french_text,
                    length=length
                ))
            
            # Check 6: Special characters
            special_chars = self._find_unsupported_chars(french_text)
            if special_chars:
                self.statistics['special_chars'] += 1
                self.issues.append(TextIssue(
                    offset=offset,
                    issue_type='special_characters',
                    severity='warning',
                    message=f'Contains unsupported characters: {special_chars}',
                    english_text=english_text,
                    french_text=french_text,
                    length=length,
                    suggested_fix='Replace with supported Pokémon encoding chars'
                ))
            
            # If we get here, it's valid
            self.statistics['valid'] += 1
        
        except Exception as e:
            self.statistics['encoding_failed'] += 1
            self.issues.append(TextIssue(
                offset=offset,
                issue_type='encoding_error',
                severity='critical',
                message=f'Encoding failed: {str(e)}',
                english_text=english_text,
                french_text=french_text,
                length=length
            ))
    
    def _find_unsupported_chars(self, text: str) -> str:
        """Find unsupported characters."""
        unsupported = set()

        # Supported characters in Pokémon encoding
        supported = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -.,!?\'":;()[]{}àèéùçœæ\n')
        
        for char in text:
            if char not in supported and ord(char) > 127:  # Non-ASCII
                unsupported.add(char)
        
        return ''.join(sorted(unsupported))
    
    def _print_summary(self):
        """Print summary."""
        print("\n" + "="*70)
        print("📊 DIAGNOSTIC SUMMARY")
        print("="*70)
        
        print(f"\n✅ Valid texts: {self.statistics['valid']} ({100*self.statistics['valid']/self.statistics['total']:.1f}%)")
        print(f"❌ Invalid/Corrupted: {self.statistics['invalid']} ({100*self.statistics['invalid']/self.statistics['total']:.1f}%)")
        print(f"⚠️  Encoding errors: {self.statistics['encoding_failed']} ({100*self.statistics['encoding_failed']/self.statistics['total']:.1f}%)")
        print(f"📝 Empty translations: {self.statistics['empty']} ({100*self.statistics['empty']/self.statistics['total']:.1f}%)")
        print(f"➡️  Unchanged texts: {self.statistics['unchanged']} ({100*self.statistics['unchanged']/self.statistics['total']:.1f}%)")
        print(f"🔤 Too long: {self.statistics['too_long']} ({100*self.statistics['too_long']/self.statistics['total']:.1f}%)")
        print(f"📏 Too short: {self.statistics['too_short']} ({100*self.statistics['too_short']/self.statistics['total']:.1f}%)")
        print(f"🎭 Special chars: {self.statistics['special_chars']} ({100*self.statistics['special_chars']/self.statistics['total']:.1f}%)")
        
        print(f"\n📈 Issues found: {len(self.issues)}")
        
        # Group by type
        by_type = defaultdict(list)
        for issue in self.issues:
            by_type[issue.issue_type].append(issue)
        
        print(f"\n📋 Issues by type:")
        for issue_type, issues in sorted(by_type.items(), key=lambda x: -len(x[1])):
            print(f"   - {issue_type}: {len(issues)}")
        
        # Show top issues
        if self.issues:
            print(f"\n⚠️  Top 10 issues (Critical):")
            critical = [i for i in self.issues if i.severity == 'critical']
            for issue in critical[:10]:
                print(f"\n   Offset: 0x{issue.offset:08X}")
                print(f"   Type: {issue.issue_type}")
                print(f"   Message: {issue.message}")
                print(f"   English: {issue.english_text[:50]}...")
                print(f"   French: {issue.french_text[:50]}...")
                if issue.suggested_fix:
                    print(f"   Fix: {issue.suggested_fix}")
    
    def save_report(self, output_path: Path) -> bool:
        """Save the report."""
        print(f"\n💾 Saving detailed report...")
        
        report = {
            'analysis': 'Translation Diagnostics',
            'statistics': self.statistics,
            'issues_summary': {
                'total_issues': len(self.issues),
                'by_severity': {
                    'critical': len([i for i in self.issues if i.severity == 'critical']),
                    'warning': len([i for i in self.issues if i.severity == 'warning']),
                    'info': len([i for i in self.issues if i.severity == 'info']),
                },
                'by_type': dict(defaultdict(
                    lambda: 0,
                    {t: len(issues) for t, issues in defaultdict(
                        list,
                        {i.issue_type: i for i in self.issues}
                    ).items()}
                ))
            },
            'top_issues': [asdict(i) for i in sorted(
                self.issues, 
                key=lambda x: {'critical': 0, 'warning': 1, 'info': 2}[x.severity]
            )[:50]],
            'recommendations': self._generate_recommendations()
        }
        
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"✅ Report saved: {output_path}")
            return True
        except Exception as e:
            print(f"❌ Save error: {e}")
            return False
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations."""
        recs = []
        
        too_long_count = self.statistics['too_long']
        if too_long_count > 100:
            pct = 100 * too_long_count / self.statistics['total']
            recs.append(f"⚠️ {too_long_count} texts are too long ({pct:.1f}%). Consider using abbreviations or shorter phrasing in French.")
        
        encoding_failed = self.statistics['encoding_failed']
        if encoding_failed > 50:
            pct = 100 * encoding_failed / self.statistics['total']
            recs.append(f"❌ {encoding_failed} texts have encoding errors ({pct:.1f}%). Check for unsupported characters.")
        
        empty = self.statistics['empty']
        if empty > self.statistics['total'] * 0.2:
            pct = 100 * empty / self.statistics['total']
            recs.append(f"📝 {empty} texts are empty or unchanged ({pct:.1f}%). These need translation.")
        
        if not recs:
            recs.append("✅ Translation looks good! Most texts should build successfully.")
        
        return recs


def main():
    parser = argparse.ArgumentParser(
        description='Diagnose Translation Issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Diagnose French translations
  python 21_diagnose_translation_issues.py \\
    --translations output/translation/french_texts.json \\
    --output output/reports/french_diagnosis.json

  # Check any translation file
  python 21_diagnose_translation_issues.py \\
    --translations output/translation/german_texts.json \\
    --output output/reports/german_diagnosis.json
        """
    )
    
    parser.add_argument('--translations', type=Path, required=True,
                       help='Translations JSON file to diagnose')
    parser.add_argument('--output', type=Path,
                       help='Output report path')
    
    args = parser.parse_args()
    
    if not args.output:
        args.output = Path('output/reports') / f"{args.translations.stem}_diagnosis.json"
    
    diagnostics = TranslationDiagnostics(args.translations)
    if diagnostics.run():
        diagnostics.save_report(args.output)
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
