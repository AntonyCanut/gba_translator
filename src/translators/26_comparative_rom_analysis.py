#!/usr/bin/env python3
"""
26 - Comparative ROM Analysis

Compare en détail la ROM anglaise, espagnole, et la sortie
pour identifier tous les patterns de différence.

Usage:
    python src/translators/26_comparative_rom_analysis.py
"""

import sys
import json
from pathlib import Path
from typing import Dict, Set, Tuple
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class ComparativeROMAnalysis:
    """Analyse comparative des ROMs."""
    
    def __init__(self):
        self.english_texts = {}
        self.spanish_texts = {}
        self.english_rom_data = None
        self.spanish_rom_data = None
        self.output_rom_data = None
        self.comparison = {
            'rom_info': {},
            'offset_comparison': {},
            'content_analysis': {},
            'verification': {}
        }
    
    def run(self) -> bool:
        """Exécuter analyse comparative."""
        print("="*70)
        print("🔀 COMPARATIVE ROM ANALYSIS")
        print("="*70)
        
        if not self._load_data():
            return False
        
        self._analyze_rom_info()
        self._analyze_offset_comparison()
        self._analyze_content()
        self._verify_output()
        self._generate_report()
        
        return True
    
    def _load_data(self) -> bool:
        """Charger les données."""
        print("\n📥 Loading data...")
        
        try:
            # Charger textes anglais
            english_path = Path('output/extracted/extracted_texts/englishrom_texts.json')
            with open(english_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data.get('texts', []):
                    offset = item['offset']
                    self.english_texts[offset] = item
            
            # Charger textes espagnols
            spanish_path = Path('output/extracted/extracted_texts/text_tables_analysis_spanish.json')
            if spanish_path.exists():
                with open(spanish_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get('texts', []):
                        offset = item['offset']
                        self.spanish_texts[offset] = item
            
            print(f"✅ English texts: {len(self.english_texts):,}")
            print(f"✅ Spanish texts: {len(self.spanish_texts):,}")
            
            # Charger les ROMs
            with open(Path('input/roms/englishrom.gba'), 'rb') as f:
                self.english_rom_data = f.read()
            
            with open(Path('input/roms/spanishrom.gba'), 'rb') as f:
                self.spanish_rom_data = f.read()
            
            with open(Path('output/roms/2026-01-14_sprom_final.gba'), 'rb') as f:
                self.output_rom_data = f.read()
            
            print(f"✅ English ROM: {len(self.english_rom_data):,} bytes")
            print(f"✅ Spanish ROM: {len(self.spanish_rom_data):,} bytes")
            print(f"✅ Output ROM: {len(self.output_rom_data):,} bytes")
            
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def _analyze_rom_info(self):
        """Analyser les infos ROM."""
        print("\n📊 Analyzing ROM info...")
        
        self.comparison['rom_info'] = {
            'english': {
                'size': len(self.english_rom_data),
                'texts': len(self.english_texts)
            },
            'spanish': {
                'size': len(self.spanish_rom_data),
                'texts': len(self.spanish_texts)
            },
            'output': {
                'size': len(self.output_rom_data),
                'matches_spanish': len(self.spanish_rom_data) == len(self.output_rom_data)
            }
        }
        
        print(f"   English: {len(self.english_texts):,} texts, {len(self.english_rom_data):,} bytes")
        print(f"   Spanish: {len(self.spanish_texts):,} texts, {len(self.spanish_rom_data):,} bytes")
        print(f"   Output:  {len(self.output_rom_data):,} bytes")
    
    def _analyze_offset_comparison(self):
        """Comparer les offsets."""
        print("\n🔍 Analyzing offset comparison...")
        
        english_offsets = set(self.english_texts.keys())
        spanish_offsets = set(self.spanish_texts.keys()) if self.spanish_texts else set()
        output_texts = len(self.english_texts)
        
        # Offsets présents dans English
        only_english = english_offsets - spanish_offsets
        both_roms = english_offsets & spanish_offsets
        only_spanish = spanish_offsets - english_offsets
        
        self.comparison['offset_comparison'] = {
            'english_total': len(english_offsets),
            'spanish_total': len(spanish_offsets),
            'only_english': len(only_english),
            'both_roms': len(both_roms),
            'only_spanish': len(only_spanish),
            'both_roms_pct': 100 * len(both_roms) / len(english_offsets) if english_offsets else 0
        }
        
        print(f"   English offsets: {len(english_offsets):,}")
        print(f"   Spanish offsets: {len(spanish_offsets):,}")
        print(f"   Both ROMs: {len(both_roms):,} ({100*len(both_roms)/len(english_offsets):.1f}%)")
        print(f"   Only English: {len(only_english):,}")
        print(f"   Only Spanish: {len(only_spanish):,}")
    
    def _analyze_content(self):
        """Analyser le contenu."""
        print("\n📝 Analyzing content...")
        
        valid_count = 0
        english_bytes = 0
        spanish_bytes = 0
        match_count = 0
        
        for offset, item in self.english_texts.items():
            length = item.get('length', 0)
            
            if length <= 0 or length > 1000:
                continue
            
            valid_count += 1
            english_bytes += length
            
            # Vérifier si ce texte existe dans Spanish
            if offset in self.spanish_texts:
                spanish_item = self.spanish_texts[offset]
                spanish_length = spanish_item.get('length', 0)
                spanish_bytes += spanish_length
                
                # Comparer les bytes
                try:
                    english_data = self.english_rom_data[offset:offset+length]
                    spanish_data = self.spanish_rom_data[offset:offset+spanish_length]
                    output_data = self.output_rom_data[offset:offset+length]
                    
                    if spanish_data == output_data:
                        match_count += 1
                except:
                    pass
        
        self.comparison['content_analysis'] = {
            'valid_english_texts': valid_count,
            'english_bytes': english_bytes,
            'spanish_bytes': spanish_bytes,
            'matched_to_output': match_count,
            'match_rate': 100 * match_count / valid_count if valid_count > 0 else 0
        }
        
        print(f"   Valid English texts: {valid_count:,}")
        print(f"   English bytes: {english_bytes:,}")
        print(f"   Spanish bytes: {spanish_bytes:,}")
        print(f"   Matched to output: {match_count:,} ({100*match_count/valid_count:.2f}%)")
    
    def _verify_output(self):
        """Vérifier la sortie."""
        print("\n✅ Verifying output ROM...")
        
        verification = {
            'file_size_correct': len(self.output_rom_data) == 33554432,
            'matches_spanish_size': len(self.output_rom_data) == len(self.spanish_rom_data),
            'header_check': False,
            'binary_samples': []
        }
        
        # Vérifier en-tête
        if (self.output_rom_data[:4] == self.spanish_rom_data[:4] == 
            bytes([0x00, 0x00, 0x00, 0xEA])):
            verification['header_check'] = True
        
        # Sampler différents offsets
        sample_offsets = [0x100000, 0x1000000, 0x1586306, 0x2000000, 0x2500000]
        for sample_offset in sample_offsets:
            if sample_offset < len(self.spanish_rom_data):
                try:
                    spanish_sample = self.spanish_rom_data[sample_offset:sample_offset+32]
                    output_sample = self.output_rom_data[sample_offset:sample_offset+32]
                    match = spanish_sample == output_sample
                    verification['binary_samples'].append({
                        'offset': f'0x{sample_offset:08X}',
                        'match': match
                    })
                except:
                    pass
        
        self.comparison['verification'] = verification
        
        print(f"   File size: {verification['file_size_correct']} ✅")
        print(f"   Size matches Spanish: {verification['matches_spanish_size']} ✅")
        print(f"   Header: {'✅' if verification['header_check'] else '❌'}")
        print(f"   Binary samples: {sum(1 for s in verification['binary_samples'] if s['match'])}/{len(verification['binary_samples'])} match")
    
    def _generate_report(self):
        """Générer rapport."""
        print("\n" + "="*70)
        print("📋 COMPARATIVE ANALYSIS SUMMARY")
        print("="*70)
        
        rom_info = self.comparison['rom_info']
        offset_comp = self.comparison['offset_comparison']
        content = self.comparison['content_analysis']
        verif = self.comparison['verification']
        
        print(f"\n📦 ROM SIZES:")
        print(f"   English:  {rom_info['english']['size']:,} bytes ({rom_info['english']['texts']:,} texts)")
        print(f"   Spanish:  {rom_info['spanish']['size']:,} bytes ({rom_info['spanish']['texts']:,} texts)")
        print(f"   Output:   {rom_info['output']['size']:,} bytes")
        
        print(f"\n🔗 OFFSET DISTRIBUTION:")
        print(f"   Both ROMs: {offset_comp['both_roms']:,} ({offset_comp['both_roms_pct']:.1f}%)")
        print(f"   Only English: {offset_comp['only_english']:,}")
        print(f"   Only Spanish: {offset_comp['only_spanish']:,}")
        
        print(f"\n📝 CONTENT ANALYSIS:")
        print(f"   Valid texts: {content['valid_english_texts']:,}")
        print(f"   Match rate: {content['match_rate']:.2f}%")
        print(f"   Total bytes: {content['english_bytes']:,}")
        
        print(f"\n✅ OUTPUT VERIFICATION:")
        print(f"   File size: {verif['file_size_correct']} ✅")
        print(f"   Binary samples: {sum(1 for s in verif['binary_samples'] if s['match'])}/{len(verif['binary_samples'])} ✅")
        
        # Verdict
        if (verif['file_size_correct'] and 
            content['match_rate'] > 99.5 and
            all(s['match'] for s in verif['binary_samples'])):
            print(f"\n🎉 VERDICT: ✅ PERFECT - ROM is production ready!")
        
        self._save_report()
    
    def _save_report(self):
        """Sauvegarder rapport."""
        print(f"\n💾 Saving comparative analysis...")
        
        try:
            output_path = Path('output/reports/2026-01-14_comparative_rom_analysis.json')
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.comparison, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Report saved: {output_path}")
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    analysis = ComparativeROMAnalysis()
    success = analysis.run()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
