#!/usr/bin/env python3
"""
Text Reinserter - Réinsertion intelligente de textes dans ROM GBA

Gère l'encodage et l'insertion de textes traduits avec support du padding.
"""

import struct
from typing import List, Dict, Optional
from .rom_reader import ROMReader
from .text_codec import TextEncoder
from .fallback_translator import FallbackSynthesizer


class FreeSpaceAllocator:
    """Allocate free space from padding bytes inside the ROM."""

    def __init__(
        self,
        rom_data: bytearray,
        min_block: int = 16,
        padding_bytes: Optional[List[int]] = None,
        start_offset: int = 0x100,
    ):
        self.rom_data = rom_data
        self.min_block = max(1, min_block)
        self.padding_bytes = set(padding_bytes or [0xFF])
        self.start_offset = max(0, start_offset)
        self.blocks = self._scan_blocks()
        self.index = 0

    def _scan_blocks(self) -> List[List[int]]:
        blocks: List[List[int]] = []
        data = self.rom_data
        n = len(data)
        i = self.start_offset

        while i < n:
            if data[i] in self.padding_bytes:
                start = i
                i += 1
                while i < n and data[i] in self.padding_bytes:
                    i += 1
                # The first padding byte of a run is usually the terminator
                # of the preceding string: never allocate over it.
                length = i - start - 1
                if length >= self.min_block:
                    blocks.append([start + 1, length])
            else:
                i += 1
        return blocks

    def allocate(self, size: int) -> Optional[int]:
        if size <= 0:
            return None
        for idx in range(self.index, len(self.blocks)):
            start, length = self.blocks[idx]
            if length >= size:
                alloc = start
                new_start = start + size
                new_length = length - size
                if new_length >= self.min_block:
                    self.blocks[idx] = [new_start, new_length]
                    self.index = idx
                else:
                    self.index = idx + 1
                return alloc
        return None


class SmartReinserter:
    """
    Gère la réinsertion intelligente de textes avec padding.

    Attributes:
        rom_data (bytearray): Données de la ROM à modifier
        stats (dict): Statistiques de réinsertion
    """

    def __init__(
        self,
        rom_data: bytearray,
        allow_truncate: bool = False,
        allow_relocate: bool = False,
        allow_fallback: bool = False,
        free_space_min: int = 16,
    ):
        """
        Initialise le réinserteur.

        Args:
            rom_data: Données de la ROM (modifiables)
            allow_truncate: Autoriser la troncature brute si trop long
            allow_relocate: Déplacer les textes trop longs (pointeurs connus)
            allow_fallback: Synthétiser une traduction française plus courte
                qui tient en place plutôt que de laisser l'anglais en place
                (voir :class:`FallbackSynthesizer`).
        """
        self.rom_data = rom_data
        self.allow_truncate = allow_truncate
        self.allow_relocate = allow_relocate
        self.allow_fallback = allow_fallback
        self.fallback = FallbackSynthesizer() if allow_fallback else None
        self.free_space_min = free_space_min
        # Relocations are deferred until all in-place writes are done:
        # the free-space scan must see the final state of the inter-string
        # padding, otherwise a relocated string can land in padding that an
        # in-place write later expands into (and vice versa), corrupting both.
        self._pending_relocations: List[tuple] = []
        self.free_space_allocator: Optional[FreeSpaceAllocator] = None
        self.stats = {
            'total': 0,
            'success': 0,
            'padding_used': 0,
            'relocated': 0,
            'relocation_failed': 0,
            'relocated_bytes': 0,
            'truncated': 0,
            'fallback_used': 0,
            'skipped_too_long': 0,
            'failures': 0,
            'warnings': []
        }

    def _infer_original_length(self, offset: int, encoding: str, max_length: int = 1000) -> int:
        terminator = 0x00 if encoding == 'ascii' else 0xFF
        length = 0
        for i in range(max_length):
            if offset + i >= len(self.rom_data):
                break
            if self.rom_data[offset + i] == terminator:
                break
            length += 1
        return length

    def _detect_padding(self, offset: int, length: int, encoding: str) -> int:
        end = offset + length
        if end >= len(self.rom_data):
            return 0
        terminator = 0x00 if encoding == 'ascii' else 0xFF
        if self.rom_data[end] == terminator:
            end += 1
        padding = 0
        while end + padding < len(self.rom_data):
            byte = self.rom_data[end + padding]
            if byte in (0x00, 0xFF):
                padding += 1
            else:
                break
        return padding

    def _load_raw_bytes(self, raw_bytes) -> Optional[bytes]:
        if raw_bytes is None:
            return None
        if isinstance(raw_bytes, (bytes, bytearray)):
            return bytes(raw_bytes)
        if isinstance(raw_bytes, list):
            return bytes(raw_bytes)
        if isinstance(raw_bytes, str):
            return bytes.fromhex(raw_bytes)
        return None

    def _parse_pointer_offsets(self, pointer_offsets) -> List[int]:
        if not pointer_offsets:
            return []
        offsets = pointer_offsets
        if isinstance(pointer_offsets, (str, int)):
            offsets = [pointer_offsets]
        parsed = []
        for value in offsets:
            if isinstance(value, int):
                parsed.append(value)
            elif isinstance(value, str):
                text = value.strip()
                if text.lower().startswith('0x'):
                    try:
                        parsed.append(int(text, 16))
                    except ValueError:
                        continue
                else:
                    try:
                        parsed.append(int(text))
                    except ValueError:
                        continue
        return parsed

    def _write_pointer(self, pointer_offset: int, target_offset: int) -> bool:
        if pointer_offset < 0 or pointer_offset + 4 > len(self.rom_data):
            return False
        pointer_value = 0x08000000 + target_offset
        self.rom_data[pointer_offset:pointer_offset + 4] = struct.pack('<I', pointer_value)
        return True

    def _queue_relocation(self, encoded: bytes, pointer_offsets: List[int], offset: int) -> bool:
        self._pending_relocations.append((encoded, pointer_offsets, offset))
        return True

    def flush_relocations(self) -> None:
        """Apply deferred relocations after every in-place write is done."""
        if not self._pending_relocations:
            return
        if self.free_space_allocator is None:
            self.free_space_allocator = FreeSpaceAllocator(
                self.rom_data, min_block=self.free_space_min
            )
        pending, self._pending_relocations = self._pending_relocations, []
        for encoded, pointer_offsets, offset in pending:
            self._relocate_text(encoded, pointer_offsets, offset)

    def _relocate_text(self, encoded: bytes, pointer_offsets: List[int], offset: int) -> bool:
        if not self.free_space_allocator:
            return False
        new_offset = self.free_space_allocator.allocate(len(encoded))
        if new_offset is None:
            self.stats['relocation_failed'] += 1
            self.stats['warnings'].append({
                'offset': f"0x{offset:08X}",
                'text': encoded[:32].hex(),
                'error': 'relocation_failed_no_space',
            })
            return False

        for i, byte in enumerate(encoded):
            self.rom_data[new_offset + i] = byte

        updated = 0
        for pointer_offset in pointer_offsets:
            if self._write_pointer(pointer_offset, new_offset):
                updated += 1

        if updated == 0:
            self.stats['relocation_failed'] += 1
            self.stats['warnings'].append({
                'offset': f"0x{offset:08X}",
                'text': encoded[:32].hex(),
                'error': 'relocation_failed_no_pointers_updated',
            })
            return False

        self.stats['relocated'] += 1
        self.stats['relocated_bytes'] += len(encoded)
        self.stats['success'] += 1
        return True

    def reinsert_text(self, translation: dict) -> bool:
        """
        Réinsère un texte traduit dans la ROM.

        Args:
            translation: Dictionnaire avec:
                - offset: Position dans la ROM
                - translation: Texte traduit
                - encoding: Type d'encodage
                - original_length: Longueur originale
                - padding_used: Padding utilisé

        Returns:
            bool: True si succès, False sinon

        Example:
            >>> reinserter = SmartReinserter(rom_data)
            >>> success = reinserter.reinsert_text({
            ...     'offset': 0x0018D42A,
            ...     'translation': 'Prends soin de toi!',
            ...     'encoding': 'pokemon',
            ...     'original_length': 14,
            ...     'padding_used': 5
            ... })
            >>> print(success)
            True
        """
        offset = translation['offset']
        text = translation.get('translation', translation.get('text', ''))
        encoding = translation.get('encoding', 'pokemon')
        original_length = translation.get('original_length')
        padding_used = translation.get('padding_used')
        padding_available = translation.get('padding_available')
        max_length = translation.get('max_length')
        allow_truncate = translation.get('allow_truncate', self.allow_truncate)
        allow_fallback = translation.get('allow_fallback', self.allow_fallback)
        raw_bytes = self._load_raw_bytes(translation.get('raw_bytes'))
        pointer_offsets = self._parse_pointer_offsets(translation.get('pointer_offsets'))

        self.stats['total'] += 1

        try:
            # Encoder le texte
            if raw_bytes is not None:
                encoded = raw_bytes
            else:
                encoded = TextEncoder.encode(text, encoding)
            encoded_len = len(encoded)

            if original_length is None:
                original_length = self._infer_original_length(offset, encoding)

            if original_length is not None:
                detected_padding = self._detect_padding(offset, original_length, encoding)
                if padding_available is None or padding_available > detected_padding:
                    padding_available = detected_padding
                if padding_used is not None and padding_used > detected_padding:
                    padding_used = detected_padding

            if max_length is None and original_length is not None:
                if padding_available is not None:
                    max_length = original_length + padding_available + 1
                elif padding_used is not None:
                    max_length = original_length + padding_used + 1
                else:
                    max_length = original_length + 1

            if max_length is not None and encoded_len > max_length:
                # Lossless first: relocate the overflowing text elsewhere and
                # repoint to it (only possible when the pointers are known).
                if self.allow_relocate and pointer_offsets:
                    return self._queue_relocation(encoded, pointer_offsets, offset)

                # Synthesize a shorter French variant that fits in place rather
                # than leaving the English string behind. Operates on `text`,
                # so it also rescues entries whose `raw_bytes` came pre-encoded.
                if allow_fallback and self.fallback is not None and text and max_length > 0:
                    result = self.fallback.shrink_to_fit(text, encoding, max_length)
                    if result.fits:
                        encoded = TextEncoder.encode(result.text, encoding)
                        encoded_len = len(encoded)
                        self.stats['fallback_used'] += 1
                        self.stats['warnings'].append({
                            'offset': f"0x{offset:08X}",
                            'text': text,
                            'fallback_text': result.text,
                            'info': (
                                f"fallback_{result.strategy} "
                                f"({result.original_bytes} -> {result.final_bytes} bytes)"
                            ),
                        })

                if encoded_len > max_length:
                    if allow_truncate and max_length > 0:
                        terminator = 0x00 if encoding == 'ascii' else 0xFF
                        encoded = encoded[:max_length]
                        encoded = encoded[:-1] + bytes([terminator])
                        encoded_len = len(encoded)
                        self.stats['truncated'] += 1
                    else:
                        self.stats['skipped_too_long'] += 1
                        self.stats['warnings'].append({
                            'offset': f"0x{offset:08X}",
                            'text': text,
                            'error': f"text_too_long ({encoded_len} > {max_length})"
                        })
                        return False

            # Vérifier si on utilise le padding
            if original_length is not None and encoded_len > original_length + 1:  # +1 pour terminateur
                self.stats['padding_used'] += 1

            # Écrire dans la ROM
            for i, byte in enumerate(encoded):
                if offset + i >= len(self.rom_data):
                    raise IndexError("Offset dépasse la taille de la ROM")
                self.rom_data[offset + i] = byte

            self.stats['success'] += 1
            return True

        except Exception as e:
            self.stats['failures'] += 1
            self.stats['warnings'].append({
                'offset': f"0x{offset:08X}",
                'text': text,
                'error': str(e)
            })
            return False

    def reinsert_all(self, translations: List[dict]) -> None:
        """
        Réinsère tous les textes traduits.

        Args:
            translations: Liste de dictionnaires de traduction
        """
        for translation in translations:
            self.reinsert_text(translation)
        self.flush_relocations()

    def get_report(self) -> dict:
        """
        Génère un rapport de réinsertion.

        Returns:
            dict: Rapport avec statistiques et warnings

        Example:
            >>> report = reinserter.get_report()
            >>> print(report['statistics']['successful'])
            100
        """
        self.flush_relocations()
        return {
            'statistics': {
                'total_texts': self.stats['total'],
                'successful': self.stats['success'],
                'failed': self.stats['failures'],
                'used_padding': self.stats['padding_used'],
                'relocated': self.stats['relocated'],
                'relocation_failed': self.stats['relocation_failed'],
                'relocated_bytes': self.stats['relocated_bytes'],
                'truncated': self.stats['truncated'],
                'fallback_used': self.stats['fallback_used'],
                'skipped_too_long': self.stats['skipped_too_long'],
                'success_rate': f"{100 * self.stats['success'] / max(1, self.stats['total']):.1f}%"
            },
            'warnings': self.stats['warnings']
        }

    def reset_stats(self) -> None:
        """Réinitialise les statistiques."""
        self.stats = {
            'total': 0,
            'success': 0,
            'padding_used': 0,
            'relocated': 0,
            'relocation_failed': 0,
            'relocated_bytes': 0,
            'truncated': 0,
            'fallback_used': 0,
            'skipped_too_long': 0,
            'failures': 0,
            'warnings': []
        }


class ROMTranslationManager:
    """
    Gestionnaire de haut niveau pour la traduction de ROM.

    Coordonne le chargement de la ROM, la réinsertion et la sauvegarde.
    """

    def __init__(self, rom_path: str):
        """
        Initialise le gestionnaire.

        Args:
            rom_path: Chemin vers la ROM source
        """
        self.rom_reader = ROMReader(rom_path)
        self.rom_reader.load()
        self.rom_data = bytearray(self.rom_reader.rom_data)
        self.reinserter = SmartReinserter(self.rom_data)

    def apply_translations(self, translations: List[dict]) -> dict:
        """
        Applique une liste de traductions.

        Args:
            translations: Liste de dictionnaires de traduction

        Returns:
            dict: Rapport de réinsertion
        """
        self.reinserter.reinsert_all(translations)
        return self.reinserter.get_report()

    def save_rom(self, output_path: str) -> None:
        """
        Sauvegarde la ROM modifiée.

        Args:
            output_path: Chemin de sortie de la ROM
        """
        with open(output_path, 'wb') as f:
            f.write(self.rom_data)

    def get_rom_info(self) -> dict:
        """
        Retourne les informations de la ROM.

        Returns:
            dict: Informations (titre, code, taille, etc.)
        """
        return self.rom_reader.get_rom_info()

    def __repr__(self) -> str:
        info = self.get_rom_info()
        return f"ROMTranslationManager(rom='{info['title']}', size={info['size_mb']}MB)"
