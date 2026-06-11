#!/usr/bin/env python3
"""
19 - Generic Translated ROM Builder

Système générique et intelligent pour construire des ROMs traduites.

Features:
- Fonctionne avec n'importe quelles ROMs source/destination
- Détection automatique de la langue
- Validation complète
- Rapport détaillé
- Extensible pour d'autres projets ROM

Usage:
    # Construire ROM espagnole
    python src/translators/19_build_translated_rom_generic.py \
        --source input/roms/englishrom.gba \
        --reference input/roms/spanishrom.gba \
        --offset-map output/differences/pointer_offset_map.json \
        --language spanish \
        --output output/roms/spanishrom_final.gba

    # Construire ROM française (depuis différences)
    python src/translators/19_build_translated_rom_generic.py \
        --source input/roms/englishrom.gba \
        --translations output/translation/french_texts.json \
        --language french \
        --output output/roms/frenchrom_final.gba

Input:
    - source: ROM de base (généralement anglaise)
    - reference: ROM source à copier (optionnel si translations fourni)
    - translations: JSON avec traductions (optionnel si reference fourni)
    - offset_map: Mapping d'offsets pour textes déplacés
    - language: Code langue (es, fr, etc.)

Output:
    - output ROM file
    - Detailed JSON report
    - Statistics and validation
"""

import sys
import json
import argparse
import re
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.dialogue_linewrap import (
    collapse_empty_breaks,
    has_empty_break_run,
    is_multiline_layout,
    rewrap as rewrap_dialogue,
    rewrap_multiline,
)
from src.core.fixed_tables import in_fixed_table
from src.core.text_codec import TextDecoder
from src.core.text_reinserter import SmartReinserter
from src.extractors.pointer_text_extractor import PointerTextExtractor


def _strip_accents(ch: str) -> str:
    return unicodedata.normalize('NFD', ch)[:1]


@dataclass
class BuildConfig:
    """Configuration pour construction ROM."""
    source_rom: Path
    reference_rom: Optional[Path] = None
    translations_json: Optional[Path] = None
    offset_map: Optional[Path] = None
    allow_truncate: bool = False
    allow_relocate: bool = False
    allow_fallback: bool = False
    pointer_proof_rom: Optional[Path] = None
    copy_reference_texts: bool = False
    copy_pointer_tables: bool = False
    copy_text_pointers: bool = False
    copy_inline_texts: bool = False
    language: str = "unknown"
    output_rom: Optional[Path] = None
    output_report: Optional[Path] = None
    
    def validate(self) -> Tuple[bool, str]:
        """Valide configuration."""
        if not self.source_rom.exists():
            return False, f"Source ROM not found: {self.source_rom}"
        
        if self.reference_rom and not self.reference_rom.exists():
            return False, f"Reference ROM not found: {self.reference_rom}"
        
        if self.translations_json and not self.translations_json.exists():
            return False, f"Translations JSON not found: {self.translations_json}"

        if self.offset_map and not self.offset_map.exists():
            return False, f"Offset map not found: {self.offset_map}"

        if self.pointer_proof_rom and not self.pointer_proof_rom.exists():
            return False, f"Pointer-proof ROM not found: {self.pointer_proof_rom}"
        
        if not self.reference_rom and not self.translations_json:
            return False, "Must provide either reference ROM or translations JSON"
        
        return True, ""


@dataclass
class BuildStats:
    """Statistiques de construction."""
    total_texts: int = 0
    successfully_copied: int = 0
    successfully_replaced: int = 0
    failed: int = 0
    unchanged: int = 0
    corrupted: int = 0
    used_padding: int = 0
    relocated: int = 0
    relocation_failed: int = 0
    relocated_bytes: int = 0
    truncated: int = 0
    fallback_used: int = 0
    skipped_too_long: int = 0
    skipped_fixed_table: int = 0
    skipped_only_in_spanish: int = 0
    skipped_only_in_english: int = 0
    skipped_missing_reference: int = 0
    pointer_tables_copied: int = 0
    pointer_table_bytes_copied: int = 0
    text_pointers_copied: int = 0
    text_pointer_bytes_copied: int = 0
    text_pointer_matches: int = 0
    inline_texts_matched: int = 0
    inline_texts_copied: int = 0
    errors: List[Dict] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire."""
        return asdict(self)


class TranslatedROMBuilder:
    """
    Constructeur générique de ROMs traduites.
    
    Stratégies disponibles:
    1. COPY: Copier les bytes directement depuis ROM de référence
    2. TRANSLATE: Réinsérer textes traduits depuis JSON
    3. HYBRID: Copier d'abord, puis appliquer traductions localisées
    """

    def __init__(self, config: BuildConfig):
        self.config = config
        self.stats = BuildStats()
        self.source_rom_data = None
        self.reference_rom_data = None
        self.output_rom_data = None
        self.translations = {}
        self.english_texts = None
        self.reference_texts = None
        self.translation_payload = None
        self.translation_kind = None
        self.offset_map = []
        self.offset_map_stats = {}
        self.reinserter_reports = {}
        self._pointer_proof_data = None

    def _pointer_proof_bytes(self):
        if self.config.pointer_proof_rom is None:
            return None
        if self._pointer_proof_data is None:
            self._pointer_proof_data = self.config.pointer_proof_rom.read_bytes()
        return self._pointer_proof_data

    CONTROL_TOKEN_RE = re.compile(r'<0x([0-9A-Fa-f]{2})>')
    COLOR_MARKER_RE = re.compile(r'\{COLOR\}([A-Za-zÀ-ÿ])')
    CONTROL_PREFIXES = {0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD}
    ARG_CONSUME_PREFIXES = {0xF7, 0xFC}
    RAW_ARG_PREFIXES = {0xF7: 1, 0xF8: 1, 0xF9: 1, 0xFD: 1}
    # Argument bytes per FC extended control command (Gen III ExtCtrlCode):
    # COLOR_HIGHLIGHT_SHADOW (0x04) takes 3, PLAY_BGM/PLAY_SE take a 16-bit
    # id, the other display commands take one byte or none. Truncating these
    # (the old 1-arg-only table) corrupted strings like the battle menu.
    FC_ARG_COUNTS = {
        0x01: 1, 0x02: 1, 0x03: 1, 0x04: 3, 0x05: 1, 0x06: 1,
        0x08: 1, 0x0B: 2, 0x0C: 1, 0x0D: 1, 0x0E: 1, 0x10: 2,
        0x11: 1, 0x12: 1, 0x13: 1, 0x14: 1, 0x19: 1,
    }

    @classmethod
    def _scan_control_tokens(cls, text: str) -> List[Tuple[int, int, int]]:
        return [
            (int(match.group(1), 16), match.start(), match.end())
            for match in cls.CONTROL_TOKEN_RE.finditer(text)
        ]

    @classmethod
    def _extract_control_sequences_from_raw(cls, raw_bytes: bytes) -> List[List[int]]:
        sequences: List[List[int]] = []
        i = 0
        while i < len(raw_bytes):
            value = raw_bytes[i]
            if value == 0xFF:
                break
            if value == 0xFC:
                if i + 1 < len(raw_bytes):
                    cmd = raw_bytes[i + 1]
                    arg_count = cls.FC_ARG_COUNTS.get(cmd, 0)
                    args = list(raw_bytes[i + 2:i + 2 + arg_count])
                    sequences.append([value, cmd] + args)
                    i += 2 + len(args)
                else:
                    sequences.append([value])
                    i += 1
                continue
            if value in cls.CONTROL_PREFIXES:
                seq = [value]
                arg_len = cls.RAW_ARG_PREFIXES.get(value, 0)
                if arg_len and i + 1 < len(raw_bytes):
                    seq.append(raw_bytes[i + 1])
                    i += 2
                else:
                    i += 1
                sequences.append(seq)
                continue
            i += 1
        return sequences

    @staticmethod
    def _format_sequence(tokens: List[int]) -> str:
        return ''.join(f"<0x{b:02X}>" for b in tokens)

    @classmethod
    def _extract_control_sequences(
        cls,
        text: str,
        raw_bytes_hex: Optional[str] = None,
    ) -> Tuple[List[List[int]], List[List[int]]]:
        sequences: List[List[int]] = []
        if raw_bytes_hex:
            try:
                raw_bytes = bytes.fromhex(raw_bytes_hex)
            except ValueError:
                raw_bytes = b''
            sequences = cls._extract_control_sequences_from_raw(raw_bytes)

        if not sequences:
            tokens = cls._scan_control_tokens(text)
            i = 0
            while i < len(tokens):
                value, start, end = tokens[i]
                if value not in cls.CONTROL_PREFIXES:
                    i += 1
                    continue

                if value == 0xFC:
                    seq = [value]
                    if i + 1 < len(tokens) and end == tokens[i + 1][1]:
                        seq.append(tokens[i + 1][0])
                        if i + 2 < len(tokens) and tokens[i + 1][2] == tokens[i + 2][1]:
                            seq.append(tokens[i + 2][0])
                            i += 3
                        else:
                            i += 2
                    else:
                        i += 1
                    sequences.append(seq)
                    continue

                seq = [value]
                if i + 1 < len(tokens) and end == tokens[i + 1][1]:
                    seq.append(tokens[i + 1][0])
                    i += 2
                else:
                    i += 1
                sequences.append(seq)

        color_sequences: List[List[int]] = []
        other_sequences: List[List[int]] = []
        for seq in sequences:
            if seq[0] == 0xFC and len(seq) == 3 and seq[1] == 0x01:
                color_sequences.append(seq)
            else:
                other_sequences.append(seq)
        return color_sequences, other_sequences

    @staticmethod
    def _argument_glyphs(seq: List[int]) -> List[str]:
        """Printable glyphs the decoder emitted for a sequence's arguments.

        For an FC control the command byte (``seq[1]``) never appears in
        the decoded text (it has no charmap glyph); only argument bytes
        that decode to a printable character were rendered after the
        placeholder, and only those duplicates must be consumed.
        """
        args = seq[2:] if seq[0] == 0xFC else seq[1:]
        glyphs: List[str] = []
        for byte in args:
            ch = TextDecoder.POKEMON_DECODE.get(byte)
            if not ch or len(ch) != 1 or ch.isspace():
                break
            glyphs.append(ch)
        return glyphs

    @staticmethod
    def _skip_argument_glyphs(text: str, index: int, expected: List[str]) -> int:
        """Consume the decoded argument glyphs duplicated after a placeholder.

        Skips a character only when it matches the glyph the argument
        byte decodes to (accent-insensitively, as translators sometimes
        fold the accent). A blind fixed-count skip ate the first letter
        of the following word ("sentir" became "entir").
        """
        for glyph in expected:
            if index >= len(text):
                break
            ch = text[index]
            if ch != glyph and _strip_accents(ch) != _strip_accents(glyph):
                break
            index += 1
        return index

    @classmethod
    def _replace_placeholders(cls, text: str, sequences: List[List[int]]) -> str:
        if not sequences:
            return text
        result: List[str] = []
        i = 0
        while i < len(text):
            if text[i] == '{':
                end = text.find('}', i + 1)
                if end != -1:
                    token = text[i:end + 1]
                    if token == '{COLOR}':
                        result.append(token)
                        i = end + 1
                        continue
                    if sequences:
                        seq = sequences.pop(0)
                        result.append(cls._format_sequence(seq))
                        i = end + 1
                        if seq[0] in cls.ARG_CONSUME_PREFIXES and len(seq) > 1:
                            i = cls._skip_argument_glyphs(
                                text, i, cls._argument_glyphs(seq)
                            )
                        continue
            result.append(text[i])
            i += 1
        return ''.join(result)

    @classmethod
    def _apply_control_placeholders(
        cls,
        translation: str,
        english_text: Optional[str],
        english_raw_bytes: Optional[str] = None,
    ) -> str:
        if not translation or not english_text:
            return translation
        if '{' not in translation:
            return translation
        color_sequences, other_sequences = cls._extract_control_sequences(
            english_text,
            english_raw_bytes,
        )
        if not color_sequences and not other_sequences:
            return translation

        def repl_color(match: re.Match) -> str:
            if color_sequences:
                return cls._format_sequence(color_sequences.pop(0))
            return match.group(0)

        if '{COLOR}' in translation:
            translation = cls.COLOR_MARKER_RE.sub(repl_color, translation)
            translation = re.sub(r'\{COLOR\}', repl_color, translation)

        return cls._replace_placeholders(translation, other_sequences)

    def run(self) -> bool:
        """Exécuter la construction complète."""
        print("="*70)
        print(f"🚀 GENERIC ROM BUILDER - {self.config.language.upper()}")
        print("="*70)
        
        # Validation
        valid, msg = self.config.validate()
        if not valid:
            print(f"❌ {msg}")
            return False
        
        # Générer chemins de sortie si nécessaire
        if not self.config.output_rom or not self.config.output_report:
            self._generate_output_paths()
        
        # Charger ROMs
        if not self._load_roms():
            return False
        
        # Charger textes
        if not self._load_texts():
            return False

        # Charger offset map si disponible
        if not self._load_offset_map():
            return False
        
        # Choisir stratégie
        strategy = self._choose_strategy()
        print(f"\n📋 Stratégie: {strategy.upper()}")
        
        # Exécuter stratégie
        if strategy == "copy":
            if not self._strategy_copy():
                return False
        elif strategy == "translate":
            if not self._strategy_translate():
                return False
        elif strategy == "hybrid":
            if not self._strategy_hybrid():
                return False
        else:
            print(f"❌ Unknown strategy: {strategy}")
            return False
        
        # Sauvegarder
        if not self._save_rom():
            return False
        
        # Rapport
        if not self._save_report():
            return False
        
        self._print_summary()
        return True

    def _generate_output_paths(self):
        """Générer chemins de sortie automatiques."""
        output_dir = Path('output/roms')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report_dir = Path('output/reports')
        report_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        lang_code = self.config.language[:2].lower()
        
        if not self.config.output_rom:
            self.config.output_rom = output_dir / f"{date_str}_{lang_code}rom_final.gba"
        if not self.config.output_report:
            self.config.output_report = report_dir / f"{date_str}_{lang_code}rom_build_report.json"

    @staticmethod
    def _parse_offset(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value, 0)
            except ValueError:
                return None
        return None

    @staticmethod
    def _default_texts_path(rom_path: Path) -> Path:
        return Path('output/extracted/extracted_texts') / f"{rom_path.stem}_texts.json"

    @staticmethod
    def _raw_bytes_length(raw_bytes: Any) -> Optional[int]:
        if raw_bytes is None:
            return None
        if isinstance(raw_bytes, (bytes, bytearray)):
            return len(raw_bytes)
        if isinstance(raw_bytes, list):
            return len(raw_bytes)
        if isinstance(raw_bytes, str):
            try:
                return len(bytes.fromhex(raw_bytes))
            except ValueError:
                return None
        return None

    def _load_extracted_texts(self, path: Path, label: str) -> Optional[Dict[int, Dict]]:
        if not path.exists():
            print(f"⚠️  Textes {label} introuvables: {path}")
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"⚠️  Erreur chargement textes {label}: {e}")
            return None

        texts = {}
        for item in data.get('texts', []):
            offset = self._parse_offset(item.get('offset'))
            if offset is None:
                continue
            texts[offset] = item

        print(f"✅ Textes {label}: {len(texts)}")
        return texts

    def _get_original_length(self, offset: int) -> Optional[int]:
        if not self.english_texts:
            return None
        entry = self.english_texts.get(offset)
        if not entry:
            return None
        byte_length = entry.get('byte_length') or entry.get('length')
        if byte_length is None:
            return None
        try:
            return max(0, int(byte_length) - 1)
        except (TypeError, ValueError):
            return None

    def _normalize_translation_item(self, offset: int, item: Dict) -> Dict:
        translation_text = (
            item.get('translation')
            or item.get('text')
            or item.get('spanish')
            or item.get('french')
            or item.get('decoded_text')
            or ''
        )
        encoding = item.get('encoding')
        if not encoding and self.english_texts:
            encoding = self.english_texts.get(offset, {}).get('encoding')
        if not encoding:
            encoding = 'pokemon'

        english_text = item.get('english_text') or item.get('original_text')
        english_raw_bytes = item.get('english_raw_bytes')
        if self.english_texts and (english_text is None or english_raw_bytes is None):
            english_entry = self.english_texts.get(offset, {})
            if english_text is None:
                english_text = english_entry.get('decoded_text') or english_entry.get('text')
            if english_raw_bytes is None:
                english_raw_bytes = english_entry.get('raw_bytes')

        translation_text = self._apply_control_placeholders(
            translation_text,
            english_text,
            english_raw_bytes,
        )

        # Dialogue inherits its break positions from the English source;
        # French lines are longer, so re-balance them against the real
        # FRLG font metrics (and enforce the \n / scroll rule).
        if translation_text and encoding == 'pokemon':
            try:
                # Consecutive breaks render as blank lines; collapse them
                # unless the English source has them too (credits layout).
                if not has_empty_break_run(english_text or ''):
                    translation_text = collapse_empty_breaks(translation_text)
                if item.get('category') == 'dialogue':
                    if is_multiline_layout(english_text or ''):
                        # Fullscreen layout (intro, cinematics, letters):
                        # keep pure \n breaks, never scroll codes.
                        translation_text = rewrap_multiline(
                            translation_text, english_text
                        )
                    else:
                        translation_text = rewrap_dialogue(translation_text)
            except Exception:
                pass  # never let display polish break the build

        pointer_offsets = item.get('pointer_offsets')
        if pointer_offsets is None and self.english_texts:
            pointer_offsets = self.english_texts.get(offset, {}).get('pointer_offsets')

        original_length = item.get('original_length')
        if original_length is None:
            original_length = self._get_original_length(offset)

        max_length = item.get('max_length')
        raw_length = self._raw_bytes_length(item.get('raw_bytes'))
        if max_length is None and raw_length is not None:
            max_length = raw_length

        normalized = dict(item)
        normalized.update({
            'offset': offset,
            'translation': translation_text,
            'encoding': encoding,
            'raw_bytes': item.get('raw_bytes'),
            'original_length': original_length,
            'max_length': max_length,
            'pointer_offsets': pointer_offsets,
            'modified': item.get('modified'),
            'english_text': english_text,
            'english_raw_bytes': english_raw_bytes,
        })
        return normalized

    def _build_translation_from_pair(self, offset: int, pair: Dict) -> Dict:
        english_entry = pair.get('english') or {}
        spanish_entry = pair.get('spanish') or {}

        encoding = spanish_entry.get('encoding') or english_entry.get('encoding') or 'pokemon'
        byte_length = english_entry.get('byte_length') or english_entry.get('length')
        original_length = None
        if byte_length is not None:
            try:
                original_length = max(0, int(byte_length) - 1)
            except (TypeError, ValueError):
                original_length = None
        if original_length is None:
            original_length = self._get_original_length(offset)

        reference_length = spanish_entry.get('byte_length') or spanish_entry.get('length')
        if reference_length is None:
            reference_length = self._raw_bytes_length(spanish_entry.get('raw_bytes'))
        max_length = None
        if reference_length is not None:
            try:
                max_length = int(reference_length)
            except (TypeError, ValueError):
                max_length = None

        return {
            'offset': offset,
            'translation': spanish_entry.get('decoded_text') or spanish_entry.get('text') or '',
            'encoding': encoding,
            'raw_bytes': spanish_entry.get('raw_bytes'),
            'original_length': original_length,
            'max_length': max_length,
            'modified': pair.get('modified', False),
            'english_text': english_entry.get('decoded_text') or english_entry.get('text') or '',
            'english_raw_bytes': english_entry.get('raw_bytes'),
            'spanish_text': spanish_entry.get('decoded_text') or spanish_entry.get('text') or '',
        }

    def _load_roms(self) -> bool:
        """Charger les ROMs."""
        print("\n📖 Chargement des ROMs...")
        
        try:
            with open(self.config.source_rom, 'rb') as f:
                self.source_rom_data = bytearray(f.read())
            
            source_size = len(self.source_rom_data) / (1024 * 1024)
            print(f"✅ ROM source: {self.config.source_rom.name} ({source_size:.2f} MB)")
            
            # Copier pour sortie
            self.output_rom_data = bytearray(self.source_rom_data)
            
            # Charger ROM de référence si fournie
            if self.config.reference_rom:
                with open(self.config.reference_rom, 'rb') as f:
                    self.reference_rom_data = bytearray(f.read())
                
                ref_size = len(self.reference_rom_data) / (1024 * 1024)
                print(f"✅ ROM référence: {self.config.reference_rom.name} ({ref_size:.2f} MB)")
            
            return True
        
        except Exception as e:
            print(f"❌ Erreur chargement: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _load_texts(self) -> bool:
        """Charger les textes et traductions."""
        print("\n📝 Chargement des textes...")

        source_texts_path = self._default_texts_path(self.config.source_rom)
        self.english_texts = self._load_extracted_texts(
            source_texts_path,
            f"source ({self.config.source_rom.stem})",
        )

        # Sans l'extraction source, la réinsertion ne connaît pas la longueur
        # d'origine des textes et en ignore des milliers ("trop longs").
        if self.config.translations_json and not self.english_texts:
            print("❌ Textes source requis pour réinsérer des traductions.")
            print(f"   Lancez d'abord: make extract (génère {source_texts_path})")
            return False

        if self.config.reference_rom:
            reference_texts_path = self._default_texts_path(self.config.reference_rom)
            self.reference_texts = self._load_extracted_texts(
                reference_texts_path,
                f"référence ({self.config.reference_rom.stem})",
            )

        if self.config.translations_json:
            try:
                with open(self.config.translations_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.translation_payload = data
            except Exception as e:
                print(f"❌ Erreur chargement traductions: {e}")
                return False

            if isinstance(data, dict) and 'translation_pairs' in data:
                self.translation_kind = 'pairs'
                pairs = data.get('translation_pairs', [])
                for pair in pairs:
                    offset = self._parse_offset(pair.get('offset'))
                    if offset is None:
                        continue
                    self.translations[offset] = self._build_translation_from_pair(offset, pair)
                print(f"✅ Paires de traduction: {len(self.translations)}")
            else:
                self.translation_kind = 'plain'
                if isinstance(data, dict):
                    if 'translations' in data:
                        texts_list = data['translations']
                    elif 'texts' in data:
                        texts_list = data['texts']
                    else:
                        texts_list = []
                elif isinstance(data, list):
                    texts_list = data
                else:
                    texts_list = []

                for item in texts_list:
                    offset = self._parse_offset(item.get('offset'))
                    if offset is None:
                        continue
                    self.translations[offset] = self._normalize_translation_item(offset, item)

                print(f"✅ Traductions: {len(self.translations)}")

        return True

    def _load_offset_map(self) -> bool:
        """Charger le mapping d'offsets si disponible."""
        self.offset_map = []
        self.offset_map_stats = {}

        data = None
        map_path = self.config.offset_map

        if map_path:
            try:
                with open(map_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"❌ Erreur chargement offset map: {e}")
                return False
        elif isinstance(self.translation_payload, dict) and 'offset_map' in self.translation_payload:
            data = self.translation_payload.get('offset_map')

        if data is None:
            return True

        if isinstance(data, dict) and 'offset_map' in data:
            entries = data.get('offset_map', [])
        elif isinstance(data, list):
            entries = data
        else:
            entries = []

        for entry in entries:
            english_offset = self._parse_offset(entry.get('english_offset'))
            spanish_offset = self._parse_offset(entry.get('spanish_offset'))
            status = entry.get('status') or 'unknown'
            self.offset_map.append({
                'english_offset': english_offset,
                'spanish_offset': spanish_offset,
                'status': status,
            })
            self.offset_map_stats[status] = self.offset_map_stats.get(status, 0) + 1

        if self.offset_map:
            print(f"✅ Offset map: {len(self.offset_map)}")

        return True

    def _choose_strategy(self) -> str:
        """
        Choisir intelligemment la stratégie.
        
        - COPY: ROM référence disponible → copier directement
        - TRANSLATE: Seulement traductions JSON → réinsérer
        - HYBRID: Les deux → copier puis adapter
        """
        if self.config.reference_rom and self.config.translations_json:
            return "hybrid"
        elif self.config.reference_rom:
            return "copy"
        else:
            return "translate"

    def _build_reference_translation(self, english_offset: int, spanish_offset: int) -> Optional[Dict]:
        entry = None
        if self.reference_texts:
            entry = self.reference_texts.get(spanish_offset)

        if entry is None and english_offset == spanish_offset and self.translations:
            candidate = self.translations.get(english_offset)
            if candidate and candidate.get('raw_bytes'):
                entry = {
                    'raw_bytes': candidate.get('raw_bytes'),
                    'decoded_text': candidate.get('translation'),
                    'text': candidate.get('translation'),
                    'encoding': candidate.get('encoding'),
                }

        if entry is None:
            return None

        raw_bytes = entry.get('raw_bytes')
        if raw_bytes is None:
            return None
        reference_length = entry.get('byte_length') or entry.get('length')
        if reference_length is None:
            reference_length = self._raw_bytes_length(raw_bytes)
        max_length = None
        if reference_length is not None:
            try:
                max_length = int(reference_length)
            except (TypeError, ValueError):
                max_length = None

        original_length = None
        if reference_length is not None:
            try:
                original_length = max(0, int(reference_length) - 1)
            except (TypeError, ValueError):
                original_length = None

        encoding = entry.get('encoding')
        if not encoding and self.english_texts:
            encoding = self.english_texts.get(english_offset, {}).get('encoding')
        if not encoding:
            encoding = 'pokemon'

        return {
            'offset': english_offset,
            'translation': entry.get('decoded_text') or entry.get('text') or '',
            'encoding': encoding,
            'raw_bytes': raw_bytes,
            'original_length': original_length,
            'max_length': max_length,
            'source_offset': spanish_offset,
        }

    def _build_reference_text_translations(self) -> List[Dict]:
        translations: List[Dict] = []
        if not self.reference_texts:
            return translations

        for offset, entry in self.reference_texts.items():
            raw_bytes = entry.get('raw_bytes')
            if raw_bytes is None:
                continue

            encoding = entry.get('encoding') or 'pokemon'
            byte_length = entry.get('byte_length') or entry.get('length')
            if byte_length is None:
                byte_length = self._raw_bytes_length(raw_bytes)
            if byte_length is None:
                continue
            try:
                byte_length = int(byte_length)
            except (TypeError, ValueError):
                continue

            translations.append({
                'offset': offset,
                'translation': entry.get('decoded_text') or entry.get('text') or '',
                'encoding': encoding,
                'raw_bytes': raw_bytes,
                'original_length': max(0, byte_length - 1),
                'max_length': byte_length,
            })

        return translations

    def _copy_pointer_tables(self) -> None:
        if not self.config.copy_pointer_tables:
            return
        if not self.config.reference_rom or not self.reference_rom_data:
            return

        print("\n🔁 Copie des tables de pointeurs (référence)...")

        extractor = PointerTextExtractor(
            rom_path=self.config.reference_rom,
            output_dir=Path('output/extracted/extracted_texts'),
        )
        tables = extractor.pointer_detector.detect_tables(extractor.min_table_entries)
        text_tables = extractor._filter_text_tables(tables)

        tables_copied = 0
        bytes_copied = 0
        for table in text_tables:
            length = len(table.pointers) * 4
            start = table.table_offset
            end = start + length
            if end > len(self.reference_rom_data) or end > len(self.output_rom_data):
                continue
            self.output_rom_data[start:end] = self.reference_rom_data[start:end]
            tables_copied += 1
            bytes_copied += length

        self.stats.pointer_tables_copied += tables_copied
        self.stats.pointer_table_bytes_copied += bytes_copied

        print(f"✅ Tables copiées: {tables_copied} ({bytes_copied} bytes)")

    def _copy_text_pointers(self) -> None:
        if not self.config.copy_text_pointers:
            return
        if not self.reference_rom_data or not self.output_rom_data:
            return
        if not self.reference_texts:
            return

        print("\n🔁 Copie des pointeurs texte (référence)...")

        text_offsets = set(self.reference_texts.keys())
        ref_data = self.reference_rom_data
        out_data = self.output_rom_data
        rom_size = len(ref_data)

        base = 0x08000000
        max_ptr = 0x0A000000
        matches = 0
        copied = 0
        bytes_copied = 0

        for alignment in range(4):
            pos = alignment
            while pos + 4 <= rom_size:
                ptr_value = int.from_bytes(ref_data[pos:pos + 4], 'little')
                if base <= ptr_value < max_ptr:
                    offset = ptr_value - base
                    if offset in text_offsets:
                        matches += 1
                        if out_data[pos:pos + 4] != ref_data[pos:pos + 4]:
                            out_data[pos:pos + 4] = ref_data[pos:pos + 4]
                            copied += 1
                            bytes_copied += 4
                pos += 4

        self.stats.text_pointer_matches += matches
        self.stats.text_pointers_copied += copied
        self.stats.text_pointer_bytes_copied += bytes_copied

        print(f"✅ Pointeurs texte copiés: {copied} ({bytes_copied} bytes)")

    def _copy_inline_texts(self) -> None:
        if not self.config.copy_inline_texts:
            return
        if not self.config.reference_rom or not self.config.source_rom:
            return
        if not self.reference_rom_data or not self.source_rom_data or not self.output_rom_data:
            return

        print("\n🔁 Copie des textes inline (sans pointeurs)...")

        min_length = 12
        max_length = 500
        skip_offsets = set(self.reference_texts.keys()) if self.reference_texts else set()

        ref_extractor = PointerTextExtractor(
            rom_path=self.config.reference_rom,
            output_dir=Path('output/extracted/extracted_texts'),
            max_text_length=max_length,
        )
        src_extractor = PointerTextExtractor(
            rom_path=self.config.source_rom,
            output_dir=Path('output/extracted/extracted_texts'),
            max_text_length=max_length,
        )

        ref_data = ref_extractor.rom_data
        src_data = src_extractor.rom_data
        rom_size = len(ref_data)
        terminators = {0xFF, 0x00}
        pokemon_bytes = ref_extractor.pokemon_bytes

        def candidate_offsets():
            yield 0
            for idx, byte in enumerate(ref_data[:-1]):
                if byte in terminators:
                    yield idx + 1

        for offset in candidate_offsets():
            if offset in skip_offsets:
                continue
            first = ref_data[offset]
            if first in terminators:
                if offset + 1 >= rom_size:
                    continue
                second = ref_data[offset + 1]
                if second in terminators:
                    continue
            if first not in pokemon_bytes and not (32 <= first <= 126):
                continue

            ref_entry = ref_extractor._read_text(offset)
            if not ref_entry:
                continue
            if ref_entry['byte_length'] < min_length:
                continue

            src_entry = src_extractor._read_text(offset)
            if not src_entry:
                continue
            if src_entry['byte_length'] < min_length:
                continue
            if ref_entry['encoding'] != src_entry['encoding']:
                continue

            self.stats.inline_texts_matched += 1

            if ref_entry['raw_bytes'] == src_entry['raw_bytes']:
                continue

            raw = bytes.fromhex(ref_entry['raw_bytes'])
            end = offset + len(raw)
            if end > rom_size:
                continue

            self.output_rom_data[offset:end] = raw
            self.stats.inline_texts_copied += 1

        print(f"✅ Textes inline copiés: {self.stats.inline_texts_copied}")

    def _build_copy_translations(self) -> Tuple[List[Dict], Dict[str, int]]:
        translations: List[Dict] = []
        stats = {
            'total_targets': 0,
            'skipped_only_in_spanish': 0,
            'skipped_only_in_english': 0,
            'skipped_missing_reference': 0,
            'missing_reference_offsets': [],
        }

        if self.offset_map:
            entries = self.offset_map
        elif self.english_texts:
            entries = [
                {'english_offset': offset, 'spanish_offset': offset, 'status': 'matched'}
                for offset in self.english_texts.keys()
            ]
        else:
            entries = []

        for entry in entries:
            english_offset = entry.get('english_offset')
            spanish_offset = entry.get('spanish_offset')

            if english_offset is None:
                stats['skipped_only_in_spanish'] += 1
                continue

            stats['total_targets'] += 1

            if spanish_offset is None:
                stats['skipped_only_in_english'] += 1
                continue

            translation = self._build_reference_translation(english_offset, spanish_offset)
            if translation is None:
                stats['skipped_missing_reference'] += 1
                stats['missing_reference_offsets'].append({
                    'english_offset': english_offset,
                    'spanish_offset': spanish_offset,
                })
                continue

            translations.append(translation)

        return translations, stats

    def _prepare_translations(self) -> Tuple[List[Dict], Dict[str, int]]:
        translations: List[Dict] = []
        stats = {
            'unchanged': 0,
            'missing_text': 0,
            'fixed_table': 0,
        }

        for offset, item in self.translations.items():
            if in_fixed_table(offset):
                # Fixed-stride name tables (moves, species…) are already
                # French in the source ROM; rewriting them at extracted
                # offsets breaks cell alignment and terminators.
                stats['fixed_table'] += 1
                continue

            if item.get('modified') is False:
                stats['unchanged'] += 1
                continue

            raw_bytes = item.get('raw_bytes')
            translation_text = item.get('translation') or item.get('text') or ''

            english_raw = item.get('english_raw_bytes')
            if raw_bytes and english_raw and raw_bytes == english_raw:
                stats['unchanged'] += 1
                continue

            if not translation_text and raw_bytes is None:
                stats['missing_text'] += 1
                self.stats.errors.append({
                    'offset': f"0x{offset:08X}",
                    'error': 'missing_translation',
                })
                continue

            if translation_text and self.english_texts:
                english_text = self.english_texts.get(offset, {}).get('decoded_text')
                if english_text and translation_text == english_text and raw_bytes is None:
                    stats['unchanged'] += 1
                    continue

            translations.append(item)

        return translations, stats

    def _strategy_copy(self) -> bool:
        """
        Stratégie COPY: Copier bytes depuis ROM de référence.
        
        Meilleure pour construire exactement une ROM connue.
        """
        print("\n🔄 Stratégie COPY: Copie directe des textes...")

        if not self.reference_rom_data:
            print("❌ ROM de référence requise pour stratégie COPY")
            return False

        if self.config.copy_reference_texts and self.reference_texts:
            translations = self._build_reference_text_translations()
            self.stats.total_texts = len(translations)
            if self.offset_map_stats:
                self.stats.skipped_only_in_spanish += self.offset_map_stats.get('only_in_spanish', 0)
                self.stats.skipped_only_in_english += self.offset_map_stats.get('only_in_english', 0)
        else:
            translations, copy_stats = self._build_copy_translations()
            self.stats.total_texts = copy_stats['total_targets']
            self.stats.skipped_only_in_spanish += copy_stats['skipped_only_in_spanish']
            self.stats.skipped_only_in_english += copy_stats['skipped_only_in_english']
            self.stats.skipped_missing_reference += copy_stats['skipped_missing_reference']

            for item in copy_stats['missing_reference_offsets']:
                english_offset = item.get('english_offset')
                spanish_offset = item.get('spanish_offset')
                self.stats.errors.append({
                    'english_offset': (
                        f"0x{english_offset:08X}" if isinstance(english_offset, int) else english_offset
                    ),
                    'spanish_offset': (
                        f"0x{spanish_offset:08X}" if isinstance(spanish_offset, int) else spanish_offset
                    ),
                    'error': 'missing_reference_text',
                })

        if not translations:
            if (
                self.stats.total_texts == 0
                and self.stats.skipped_only_in_spanish == 0
                and self.stats.skipped_only_in_english == 0
            ):
                print("❌ Aucun mapping de texte disponible (offset map ou extraction manquante).")
                return False
            print("⚠️  Aucun texte à copier.")
            return True

        reinserter = SmartReinserter(
            self.output_rom_data,
            allow_truncate=self.config.allow_truncate,
            allow_relocate=self.config.allow_relocate,
            allow_fallback=self.config.allow_fallback,
            pointer_proof_rom=self._pointer_proof_bytes(),
        )

        for i, translation in enumerate(translations, start=1):
            reinserter.reinsert_text(translation)
            if i % 5000 == 0:
                print(f"   Traité: {i}/{len(translations)}")

        report = reinserter.get_report()
        self.reinserter_reports['copy'] = report

        stats = report['statistics']
        self.stats.successfully_copied += stats['successful']
        self.stats.failed += stats['failed']
        self.stats.used_padding += stats['used_padding']
        self.stats.relocated += stats.get('relocated', 0)
        self.stats.relocation_failed += stats.get('relocation_failed', 0)
        self.stats.relocated_bytes += stats.get('relocated_bytes', 0)
        self.stats.truncated += stats['truncated']
        self.stats.fallback_used += stats.get('fallback_used', 0)
        self.stats.skipped_too_long += stats['skipped_too_long']
        self.stats.errors.extend(report.get('warnings', []))

        print(f"✅ Copie complétée: {self.stats.successfully_copied}/{self.stats.total_texts}")

        self._copy_pointer_tables()
        self._copy_text_pointers()
        self._copy_inline_texts()
        return True

    def _strategy_translate(self) -> bool:
        """
        Stratégie TRANSLATE: Réinsérer textes traduits.
        
        Pour traductions personnalisées depuis JSON.
        """
        print("\n🔄 Stratégie TRANSLATE: Réinsertion des traductions...")

        if not self.translations:
            print("❌ Aucune traduction fournie")
            return False

        self.stats.total_texts = len(self.translations)
        translations, prep_stats = self._prepare_translations()
        self.stats.unchanged += prep_stats['unchanged']
        self.stats.failed += prep_stats['missing_text']
        self.stats.skipped_fixed_table += prep_stats['fixed_table']

        if not translations:
            print("⚠️  Aucun texte à réinsérer.")
            return True

        reinserter = SmartReinserter(
            self.output_rom_data,
            allow_truncate=self.config.allow_truncate,
            allow_relocate=self.config.allow_relocate,
            allow_fallback=self.config.allow_fallback,
            pointer_proof_rom=self._pointer_proof_bytes(),
        )

        for i, translation in enumerate(translations, start=1):
            reinserter.reinsert_text(translation)
            if i % 5000 == 0:
                print(f"   Traité: {i}/{len(translations)}")

        report = reinserter.get_report()
        self.reinserter_reports['translate'] = report

        stats = report['statistics']
        self.stats.successfully_replaced += stats['successful']
        self.stats.failed += stats['failed']
        self.stats.used_padding += stats['used_padding']
        self.stats.relocated += stats.get('relocated', 0)
        self.stats.relocation_failed += stats.get('relocation_failed', 0)
        self.stats.relocated_bytes += stats.get('relocated_bytes', 0)
        self.stats.truncated += stats['truncated']
        self.stats.fallback_used += stats.get('fallback_used', 0)
        self.stats.skipped_too_long += stats['skipped_too_long']
        self.stats.errors.extend(report.get('warnings', []))

        print(f"✅ Traduction complétée: {self.stats.successfully_replaced}/{self.stats.total_texts}")
        return True

    def _strategy_hybrid(self) -> bool:
        """
        Stratégie HYBRID: Copier d'abord, puis appliquer traductions.
        
        Utile pour variations localisées d'une même base.
        """
        print("\n🔄 Stratégie HYBRID: Copie + traductions...")
        
        # D'abord copier depuis référence
        if not self._strategy_copy():
            return False
        
        # Puis appliquer traductions localisées
        print("\n   Puis appliquer traductions localisées...")

        if not self.translations:
            print("   Aucun ajustement local fourni.")
            return True

        translations, prep_stats = self._prepare_translations()
        self.stats.unchanged += prep_stats['unchanged']
        self.stats.failed += prep_stats['missing_text']
        self.stats.skipped_fixed_table += prep_stats['fixed_table']

        if not translations:
            print("   Aucun texte à réinsérer.")
            return True

        reinserter = SmartReinserter(
            self.output_rom_data,
            allow_truncate=self.config.allow_truncate,
            allow_relocate=self.config.allow_relocate,
            allow_fallback=self.config.allow_fallback,
            pointer_proof_rom=self._pointer_proof_bytes(),
        )

        for i, translation in enumerate(translations, start=1):
            reinserter.reinsert_text(translation)
            if i % 5000 == 0:
                print(f"   Traité: {i}/{len(translations)}")

        report = reinserter.get_report()
        self.reinserter_reports['hybrid_translate'] = report

        stats = report['statistics']
        self.stats.successfully_replaced += stats['successful']
        self.stats.failed += stats['failed']
        self.stats.used_padding += stats['used_padding']
        self.stats.relocated += stats.get('relocated', 0)
        self.stats.relocation_failed += stats.get('relocation_failed', 0)
        self.stats.relocated_bytes += stats.get('relocated_bytes', 0)
        self.stats.truncated += stats['truncated']
        self.stats.fallback_used += stats.get('fallback_used', 0)
        self.stats.skipped_too_long += stats['skipped_too_long']
        self.stats.errors.extend(report.get('warnings', []))

        print(f"   +{stats['successful']} traductions localisées appliquées")

        return True

    def _save_rom(self) -> bool:
        """Sauvegarder la ROM."""
        print(f"\n💾 Sauvegarde de la ROM...")
        
        try:
            with open(self.config.output_rom, 'wb') as f:
                f.write(self.output_rom_data)
            
            rom_size = self.config.output_rom.stat().st_size / (1024 * 1024)
            print(f"✅ ROM sauvegardée: {self.config.output_rom.name} ({rom_size:.2f} MB)")
            return True
        
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
            return False

    def _save_report(self) -> bool:
        """Sauvegarder le rapport."""
        print(f"\n📊 Génération du rapport...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'language': self.config.language,
            'source_rom': str(self.config.source_rom),
            'reference_rom': str(self.config.reference_rom) if self.config.reference_rom else None,
            'translations_json': str(self.config.translations_json) if self.config.translations_json else None,
            'offset_map': str(self.config.offset_map) if self.config.offset_map else None,
            'allow_truncate': self.config.allow_truncate,
            'allow_relocate': self.config.allow_relocate,
            'allow_fallback': self.config.allow_fallback,
            'pointer_proof_rom': str(self.config.pointer_proof_rom) if self.config.pointer_proof_rom else None,
            'copy_reference_texts': self.config.copy_reference_texts,
            'copy_pointer_tables': self.config.copy_pointer_tables,
            'copy_text_pointers': self.config.copy_text_pointers,
            'copy_inline_texts': self.config.copy_inline_texts,
            'output_rom': str(self.config.output_rom),
            'strategy': self._choose_strategy(),
            'statistics': self.stats.to_dict(),
            'translation_kind': self.translation_kind,
            'offset_map_stats': self.offset_map_stats,
            'reinserter_reports': self.reinserter_reports,
            'notes': f"Generic ROM builder for {self.config.language} translation"
        }
        
        try:
            with open(self.config.output_report, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Rapport sauvegardé: {self.config.output_report.name}")
            return True
        
        except Exception as e:
            print(f"❌ Erreur rapport: {e}")
            return False

    def _print_summary(self):
        """Afficher résumé final."""
        print("\n" + "="*70)
        print("✨ CONSTRUCTION RÉUSSIE!")
        print("="*70)
        print(f"\n📁 ROM: {self.config.output_rom}")
        print(f"📊 Rapport: {self.config.output_report}")
        print(f"\n📈 Statistiques:")
        print(f"   - Total textes: {self.stats.total_texts}")
        print(f"   - Copiés: {self.stats.successfully_copied}")
        print(f"   - Remplacés: {self.stats.successfully_replaced}")
        print(f"   - Inchangés: {self.stats.unchanged}")
        print(f"   - Échoués: {self.stats.failed}")
        if self.stats.corrupted:
            print(f"   - Corrompus: {self.stats.corrupted}")
        if self.stats.used_padding:
            print(f"   - Padding utilisé: {self.stats.used_padding}")
        if self.stats.truncated:
            print(f"   - Tronqués: {self.stats.truncated}")
        if self.stats.fallback_used:
            print(f"   - Repli FR synthétisé: {self.stats.fallback_used}")
        if self.stats.skipped_too_long:
            print(f"   - Trop longs ignorés: {self.stats.skipped_too_long}")
        if self.stats.skipped_only_in_spanish:
            print(f"   - Espagnol sans cible: {self.stats.skipped_only_in_spanish}")
        if self.stats.skipped_only_in_english:
            print(f"   - Anglais sans source: {self.stats.skipped_only_in_english}")
        if self.stats.skipped_missing_reference:
            print(f"   - Référence manquante: {self.stats.skipped_missing_reference}")
        if self.stats.pointer_tables_copied:
            print(f"   - Tables de pointeurs copiées: {self.stats.pointer_tables_copied}")
        if self.stats.text_pointers_copied:
            print(f"   - Pointeurs texte copiés: {self.stats.text_pointers_copied}")
        if self.stats.inline_texts_copied:
            print(f"   - Textes inline copiés: {self.stats.inline_texts_copied}")


def main():
    parser = argparse.ArgumentParser(
        description='Generic Translated ROM Builder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build Spanish ROM by copying from reference
  python 19_build_translated_rom_generic.py \\
    --source input/roms/englishrom.gba \\
    --reference input/roms/spanishrom.gba \\
    --offset-map output/differences/pointer_offset_map.json \\
    --language spanish

  # Build French ROM from translations JSON
  python 19_build_translated_rom_generic.py \\
    --source input/roms/englishrom.gba \\
    --translations output/translation/french_texts.json \\
    --language french

  # Hybrid: Copy Spanish reference + apply custom French translations
  python 19_build_translated_rom_generic.py \\
    --source input/roms/englishrom.gba \\
    --reference input/roms/spanishrom.gba \\
    --translations output/translation/french_variations.json \\
    --language french-es
        """
    )
    
    parser.add_argument('--source', type=Path, required=True,
                       help='Source ROM (usually English)')
    parser.add_argument('--reference', type=Path,
                       help='Reference ROM to copy from')
    parser.add_argument('--translations', type=Path,
                       help='Translations JSON file')
    parser.add_argument('--offset-map', type=Path,
                       help='Offset map JSON file')
    parser.add_argument('--language', required=True,
                       help='Language code (es, fr, de, etc.)')
    parser.add_argument('--output', type=Path,
                       help='Output ROM path (auto-generated if not provided)')
    parser.add_argument('--allow-truncate', action='store_true',
                       help='Allow truncation when text exceeds max length')
    parser.add_argument('--allow-relocate', action='store_true',
                       help='Relocate too-long texts when pointer offsets are known')
    parser.add_argument('--allow-fallback', action='store_true',
                       help='Synthesize a shorter in-place French variant for '
                            'too-long texts instead of leaving English behind')
    parser.add_argument('--pointer-proof-rom', type=Path,
                       help='Translated ROM of the same base (e.g. the Spanish '
                            'hack): pointer sites it rewrote are proven real '
                            'and accepted for relocation')
    parser.add_argument('--copy-reference-texts', action='store_true',
                       help='Copy all reference text bytes at their offsets')
    parser.add_argument('--copy-pointer-tables', action='store_true',
                       help='Copy reference pointer tables (text tables)')
    parser.add_argument('--copy-text-pointers', action='store_true',
                       help='Copy reference pointers that target extracted texts')
    parser.add_argument('--copy-inline-texts', action='store_true',
                       help='Copy unreferenced text blocks found at identical offsets')
    
    args = parser.parse_args()
    
    config = BuildConfig(
        source_rom=args.source,
        reference_rom=args.reference,
        translations_json=args.translations,
        offset_map=args.offset_map,
        allow_truncate=args.allow_truncate,
        allow_relocate=args.allow_relocate,
        allow_fallback=args.allow_fallback,
        pointer_proof_rom=args.pointer_proof_rom,
        copy_reference_texts=args.copy_reference_texts,
        copy_pointer_tables=args.copy_pointer_tables,
        copy_text_pointers=args.copy_text_pointers,
        copy_inline_texts=args.copy_inline_texts,
        language=args.language,
        output_rom=args.output
    )
    
    builder = TranslatedROMBuilder(config)
    success = builder.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
