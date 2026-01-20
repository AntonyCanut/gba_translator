#!/usr/bin/env python3
"""
Pointer-based text extractor for GBA ROMs.

Scans pointer tables, detects text strings, and emits a stable JSON schema
with raw bytes and decoded text.
"""

from __future__ import annotations

import argparse
import json
import time
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core.rom_reader import ROMReader
from src.core.text_codec import TextDecoder, TextEncoder


@dataclass
class PointerTable:
    table_offset: int
    pointers: List[int]


class PointerTableDetector:
    def __init__(self, rom_reader: ROMReader):
        self.rom = rom_reader

    def detect_tables(self, min_entries: int = 5) -> List[PointerTable]:
        tables: List[PointerTable] = []
        size = self.rom.rom_size
        i = 0
        while i < size - 4:
            pointers: List[int] = []
            offset = i
            while offset < size - 4:
                ptr = self.rom.read_pointer(offset)
                if ptr is not None:
                    pointers.append(ptr)
                    offset += 4
                else:
                    break
            if len(pointers) >= min_entries:
                tables.append(PointerTable(i, pointers))
                i = offset
            else:
                i += 4
        return tables


class PointerTextExtractor:
    def __init__(
        self,
        rom_path: Path,
        output_dir: Path,
        min_table_entries: int = 5,
        sample_size: int = 10,
        min_text_ratio: float = 0.6,
        max_text_length: int = 1000,
        detect_scan: int = 200,
        scan_all_pointers: bool = False,
        scan_alignments: Optional[List[int]] = None,
    ) -> None:
        self.rom_path = rom_path
        self.output_dir = output_dir
        self.min_table_entries = min_table_entries
        self.sample_size = sample_size
        self.min_text_ratio = min_text_ratio
        self.max_text_length = max_text_length
        self.detect_scan = detect_scan
        self.scan_all_pointers = scan_all_pointers
        self.scan_alignments = scan_alignments or [0, 1, 2, 3]

        self.rom_reader = ROMReader(str(rom_path))
        self.rom_reader.load()
        self.rom_data = self.rom_reader.rom_data

        self.pointer_detector = PointerTableDetector(self.rom_reader)
        self.pokemon_bytes = set(TextEncoder.POKEMON_TABLE.values())
        self.pokemon_bytes.add(0xFE)

    def _read_until(self, offset: int, terminator: int) -> Optional[bytes]:
        if offset < 0 or offset >= len(self.rom_data):
            return None
        end = min(len(self.rom_data), offset + self.max_text_length)
        data = self.rom_data[offset:end]
        idx = data.find(bytes([terminator]))
        if idx == -1:
            return None
        return bytes(data[: idx + 1])

    def _ascii_ratio(self, data: bytes) -> float:
        if not data:
            return 0.0
        ascii_count = sum(1 for b in data if 32 <= b <= 126)
        return ascii_count / len(data)

    def _pokemon_ratio(self, data: bytes) -> float:
        if not data:
            return 0.0
        pokemon_count = sum(1 for b in data if b in self.pokemon_bytes)
        return pokemon_count / len(data)

    def _detect_encoding(self, offset: int) -> Optional[str]:
        if offset < 0 or offset >= len(self.rom_data):
            return None
        sample = bytes(self.rom_data[offset : offset + self.detect_scan])
        if not sample:
            return None

        idx_ff = sample.find(b'\xFF')
        idx_00 = sample.find(b'\x00')

        pokemon_slice = sample[: idx_ff] if idx_ff != -1 else sample
        ascii_slice = sample[: idx_00] if idx_00 != -1 else sample

        pokemon_ratio = self._pokemon_ratio(pokemon_slice)
        ascii_ratio = self._ascii_ratio(ascii_slice)

        if idx_ff != -1 and pokemon_ratio >= 0.5 and (idx_00 == -1 or idx_ff <= idx_00):
            return 'pokemon'
        if idx_00 != -1 and ascii_ratio >= 0.8 and (idx_ff == -1 or idx_00 < idx_ff):
            return 'ascii'

        if idx_ff == -1 and pokemon_ratio >= 0.6 and pokemon_ratio >= ascii_ratio:
            return 'pokemon'

        if idx_ff != -1 and pokemon_ratio >= ascii_ratio:
            return 'pokemon'
        if idx_00 != -1 and ascii_ratio > pokemon_ratio:
            return 'ascii'

        return None

    def _read_text(self, offset: int) -> Optional[Dict]:
        encoding = self._detect_encoding(offset)
        if not encoding:
            return None

        terminator = 0xFF if encoding == 'pokemon' else 0x00
        raw = self._read_until(offset, terminator)
        if raw is None:
            return None

        if encoding == 'ascii':
            decoded = TextDecoder.decode_ascii(raw, preserve_unknown=True)
        else:
            decoded = TextDecoder.decode_pokemon(raw, preserve_unknown=True)

        return {
            'offset': offset,
            'byte_length': len(raw),
            'length': len(raw),
            'encoding': encoding,
            'raw_bytes': raw.hex(),
            'text': decoded,
            'decoded_text': decoded,
        }

    def _is_text_offset(self, offset: int) -> bool:
        entry = self._read_text(offset)
        if not entry:
            return False
        length = entry['byte_length']
        if length < 1 or length > self.max_text_length:
            return False
        return True

    def _filter_text_tables(self, tables: List[PointerTable]) -> List[PointerTable]:
        text_tables: List[PointerTable] = []
        for table in tables:
            sample = table.pointers[: self.sample_size]
            if not sample:
                continue
            text_hits = sum(1 for off in sample if self._is_text_offset(off))
            ratio = text_hits / len(sample)
            if ratio >= self.min_text_ratio:
                text_tables.append(table)
        return text_tables

    def _scan_pointer_offsets(self, texts_by_offset: Dict[int, Dict]) -> int:
        """Scan all pointer values (all alignments) and collect text offsets."""
        pointer_hits = 0
        rom_size = self.rom_reader.rom_size
        data = self.rom_data

        for alignment in self.scan_alignments:
            if alignment < 0 or alignment > 3:
                continue
            pos = alignment
            while pos + 4 <= rom_size:
                ptr = int.from_bytes(data[pos:pos + 4], 'little')
                if self.rom_reader.is_valid_pointer(ptr):
                    offset = ptr - self.rom_reader.GBA_ROM_BASE
                    entry = texts_by_offset.get(offset)
                    if entry is None:
                        entry = self._read_text(offset)
                        if entry is not None:
                            entry['table_offsets'] = []
                            entry['pointer_offsets'] = []
                            texts_by_offset[offset] = entry
                    if entry is not None:
                        entry.setdefault('pointer_offsets', []).append(f"0x{pos:08X}")
                        pointer_hits += 1
                pos += 4

        return pointer_hits

    def extract(self) -> Dict:
        tables = self.pointer_detector.detect_tables(self.min_table_entries)
        text_tables = self._filter_text_tables(tables)

        texts_by_offset: Dict[int, Dict] = {}
        for table in text_tables:
            for offset in table.pointers:
                entry = texts_by_offset.get(offset)
                if entry is None:
                    entry = self._read_text(offset)
                    if entry is None:
                        continue
                    entry['table_offsets'] = []
                    texts_by_offset[offset] = entry
                entry['table_offsets'].append(f"0x{table.table_offset:08X}")

        pointer_hits = 0
        if self.scan_all_pointers:
            pointer_hits = self._scan_pointer_offsets(texts_by_offset)

        texts = list(texts_by_offset.values())
        texts.sort(key=lambda item: item['offset'])

        return {
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'rom_name': self.rom_path.name,
            'rom_size': self.rom_reader.rom_size,
            'text_count': len(texts),
            'tables_detected': len(tables),
            'text_tables': len(text_tables),
            'pointer_scan_hits': pointer_hits,
            'texts': texts,
        }

    def write_output(self, data: Dict, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    def run(self, output_path: Optional[Path]) -> Path:
        output_path = output_path or (self.output_dir / f"{self.rom_path.stem}_texts.json")
        data = self.extract()
        self.write_output(data, output_path)
        return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Pointer-based text extractor')
    parser.add_argument('rom', help='Path to ROM (.gba)')
    parser.add_argument('--output', help='Output JSON path')
    parser.add_argument('--min-entries', type=int, default=5, help='Min pointers per table')
    parser.add_argument('--sample-size', type=int, default=10, help='Sample size per table')
    parser.add_argument('--min-text-ratio', type=float, default=0.6, help='Min text ratio for tables')
    parser.add_argument('--max-text-length', type=int, default=1000, help='Max text length')
    parser.add_argument('--detect-scan', type=int, default=200, help='Bytes to scan for encoding detection')
    parser.add_argument('--scan-all-pointers', action='store_true',
                        help='Scan all pointer values (including unaligned) to catch singleton references')

    args = parser.parse_args()

    extractor = PointerTextExtractor(
        rom_path=Path(args.rom),
        output_dir=Path('output/extracted/extracted_texts'),
        min_table_entries=args.min_entries,
        sample_size=args.sample_size,
        min_text_ratio=args.min_text_ratio,
        max_text_length=args.max_text_length,
        detect_scan=args.detect_scan,
        scan_all_pointers=args.scan_all_pointers,
    )

    output = extractor.run(Path(args.output) if args.output else None)
    print(f"Wrote extraction: {output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
