#!/usr/bin/env python3
"""
Text Reinserter - Réinsertion intelligente de textes dans ROM GBA

Gère l'encodage et l'insertion de textes traduits avec support du padding.
"""

import bisect
import struct
from typing import List, Dict, Iterable, Optional
from .rom_reader import ROMReader
from .text_codec import TextEncoder
from .fallback_translator import FallbackSynthesizer


class FreeSpaceAllocator:
    """Allocate free space from padding bytes inside the ROM.

    Only large runs of 0xFF qualify as free space. Short 0xFF/0x00 runs are
    routinely *live data* — 0xFF sentinel arrays in code literal pools,
    zero-valued struct fields in sprite/animation tables, alignment gaps —
    and allocating from them corrupted the battle engine (strings written
    over battle-transition data caused a hard reset at battle start).
    """

    # Runs shorter than this are considered data, never free space. The
    # live 0xFF-sentinel arrays / zero-filled struct fields observed in the
    # Unbound ROM (whose corruption crashed the battle engine) all sit in
    # runs under ~256 bytes; genuine free space comes in 1KB+ runs
    # (~880KB below 0x1000000, for ~710KB of relocated text).
    MIN_FREE_RUN = 1024
    # Ranges never allocated even when they look free.
    # - 0x230000-0x500000: battle animations / sprite graphics. 0xFF runs up
    #   to several KB there are padded graphic blocks; overwriting them made
    #   the battle transition crash to a hard reset (prologue guard fight).
    # - 0x1000000-0x1FE0000: CFRU/Unbound reserves upper-ROM 0xFF gaps for
    #   its own dynamically inserted data; writing strings there blanked the
    #   post-prologue tutorial scene.
    EXCLUDE_RANGES = [(0x230000, 0x500000), (0x1000000, 0x1FE0000)]
    # Bytes kept untouched at both ends of a run: the leading 0xFF often
    # terminates the preceding structure and trailing 0xFF can be the
    # sentinel of the following one.
    RUN_MARGIN = 8
    # A block remainder smaller than this is dropped instead of reused.
    MIN_REMAINDER = 16

    def __init__(
        self,
        rom_data: bytearray,
        min_block: int = MIN_FREE_RUN,
        padding_bytes: Optional[List[int]] = None,
        start_offset: int = 0x100,
        reserved_rom: Optional[bytes] = None,
        reserved_ranges: Optional[List[tuple]] = None,
    ):
        """``reserved_rom``: same-base ROM (e.g. the Spanish translation)
        whose own relocated text claims runs that are still 0xFF here. The
        inline-overrides pass later mirrors that layout (it writes FR text
        at the Spanish addresses), so any byte populated in ``reserved_rom``
        must never be allocated — relocating a string there had it clobbered
        by the mirror write (the Shadow Base door showed a move description
        tail, "nche l'ennemi.").

        ``reserved_ranges``: explicit ``(start, end)`` byte spans to keep free
        of relocations, as a *precise* alternative to ``reserved_rom``. The
        blanket ``reserved_rom`` carve is correct but heavily over-reserves:
        it protects **every** byte the reference ROM populated, whereas only
        the handful of offsets the downstream inline-overrides pass actually
        writes can ever clobber a relocated string. Those very bytes are
        proven-safe relocation targets (the reference translation itself
        relocated text into them and shipped a working ROM), so reserving only
        the real inline-write spans frees ~34 KB of pool for the German build
        (see scripts/build_language.py's --reserve-ranges / the inline pass's
        --dump-write-ranges). ``reserved_rom`` and ``reserved_ranges`` are
        mutually exclusive in practice: FR keeps the blanket ROM carve
        (byte-identical), generic builds pass precise ranges instead.
        """
        self.rom_data = rom_data
        self.min_block = max(self.MIN_FREE_RUN, min_block)
        self.padding_bytes = set(padding_bytes or [0xFF])
        self.start_offset = max(0, start_offset)
        self.reserved_rom = reserved_rom
        self.reserved_ranges = reserved_ranges
        self.blocks = self._scan_blocks()
        self.index = 0

    def _carve_reserved(self, segments: List[tuple]) -> List[tuple]:
        """Split out the bytes that ``reserved_rom`` populates."""
        res = self.reserved_rom
        if res is None:
            return segments
        padding = self.padding_bytes
        carved: List[tuple] = []
        for s, e in segments:
            run_start = None
            for i in range(s, min(e, len(res))):
                if res[i] in padding:
                    if run_start is None:
                        run_start = i
                else:
                    if run_start is not None:
                        carved.append((run_start, i))
                        run_start = None
            if run_start is not None:
                carved.append((run_start, e))
            elif e > len(res):
                carved.append((len(res), e))
        return carved

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
                # Carve the excluded ranges out of the run, then keep the
                # remaining segments that are still large enough.
                segments = [(start, i)]
                for lo, hi in self.EXCLUDE_RANGES:
                    carved = []
                    for s, e in segments:
                        if s < lo:
                            carved.append((s, min(e, lo)))
                        if e > hi:
                            carved.append((max(s, hi), e))
                    segments = carved
                segments = self._carve_reserved(segments)
                for s, e in segments:
                    seg = e - s
                    length = seg - 2 * self.RUN_MARGIN
                    if seg >= self.min_block and length > 0:
                        blocks.append([s + self.RUN_MARGIN, length])
            else:
                i += 1

        # Precise reservation carve. Done once against the finished (few-hundred)
        # block list rather than per-0xFF-run, so a large range list (thousands
        # of inline-write spans) stays cheap instead of O(runs × ranges).
        if self.reserved_ranges:
            blocks = self._carve_ranges(blocks)
        return blocks

    def _carve_ranges(self, blocks: List[List[int]]) -> List[List[int]]:
        """Remove the ``reserved_ranges`` spans from ``blocks``.

        Splits any block that overlaps a reserved span and drops leftover
        pieces smaller than ``min_block``. Ranges are sorted once and matched to
        each block with a binary search, keeping the whole pass roughly
        ``O((blocks + ranges) log ranges)``.
        """
        ranges = sorted(
            (lo, hi) for lo, hi in self.reserved_ranges if hi > lo
        )
        if not ranges:
            return blocks
        starts = [lo for lo, _ in ranges]
        result: List[List[int]] = []
        for start, length in blocks:
            segments = [(start, start + length)]
            # Only ranges whose start is < block end can overlap; scan from the
            # first such range until ranges move past the block end.
            idx = bisect.bisect_left(starts, start)
            # A range starting before the block may still overlap it.
            while idx > 0 and ranges[idx - 1][1] > start:
                idx -= 1
            carved: List[tuple] = []
            for s, e in segments:
                pieces = [(s, e)]
                j = idx
                while j < len(ranges) and ranges[j][0] < e:
                    lo, hi = ranges[j]
                    j += 1
                    if hi <= s or lo >= e:
                        continue
                    next_pieces = []
                    for ps, pe in pieces:
                        if hi <= ps or lo >= pe:
                            next_pieces.append((ps, pe))
                            continue
                        if ps < lo:
                            next_pieces.append((ps, lo))
                        if pe > hi:
                            next_pieces.append((hi, pe))
                    pieces = next_pieces
                carved.extend(pieces)
            for s, e in carved:
                if e - s >= self.min_block:
                    result.append([s, e - s])
        return result

    def allocate(self, size: int) -> Optional[int]:
        if size <= 0:
            return None
        # Best-fit: pick the smallest block that still fits. First-fit wasted
        # large blocks on small strings and left every big block fragmented,
        # so the Italian build (whose relocation demand is close to the total
        # free space) ran out early. Best-fit keeps large blocks intact for the
        # large strings that genuinely need them and packs the leftovers far
        # more tightly. Scanning all 150-ish blocks per call is negligible.
        best_idx = -1
        best_length = None
        for idx, (start, length) in enumerate(self.blocks):
            if length >= size and (best_length is None or length < best_length):
                best_idx = idx
                best_length = length
                if length == size:
                    break
        if best_idx < 0:
            return None
        start, length = self.blocks[best_idx]
        alloc = start
        new_length = length - size
        if new_length > 0:
            self.blocks[best_idx] = [start + size, new_length]
        else:
            self.blocks.pop(best_idx)
        return alloc


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
        pointer_proof_rom: Optional[bytes] = None,
        skip_encode_aliases: frozenset = frozenset(),
        collision_guard: bool = False,
        cell_boundaries: Optional[Iterable[int]] = None,
        reserved_ranges: Optional[List[tuple]] = None,
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
            pointer_proof_rom: ROM de la même base déjà traduite par un autre
                hack (ex. la traduction espagnole). Un site dont la valeur y a
                été réécrite vers une autre adresse ROM est un pointeur prouvé
                réel: ses traducteurs l'ont repointé en relogeant ce texte.
            skip_encode_aliases: Characters whose ENCODE_ALIASES entries are
                skipped during encode_pokemon (use GERMAN_UMLAUT_CHARS for DE).
        """
        self.rom_data = rom_data
        self.allow_truncate = allow_truncate
        self.allow_relocate = allow_relocate
        self.allow_fallback = allow_fallback
        self.pointer_proof_rom = pointer_proof_rom
        # Precise relocation reservation (generic builds). When set, the
        # free-space allocator carves exactly these (start, end) spans instead
        # of the whole ``pointer_proof_rom`` — see FreeSpaceAllocator's
        # ``reserved_ranges``. FR leaves it None and keeps the blanket carve.
        self.reserved_ranges = reserved_ranges
        self.fallback = FallbackSynthesizer() if allow_fallback else None
        self.free_space_min = free_space_min
        self.skip_encode_aliases = skip_encode_aliases
        # Collision guard: never let an in-place write's terminator land at or
        # beyond the next occupied cell. In the packed description tables the
        # source strings sit back to back and the 0x00/0xFF run after a
        # terminator spills into the next cell, so the padding heuristic
        # over-counts and a longer translation overruns — fusing two strings on
        # screen or, worst case, freezing on an unterminated CFRU string (see
        # scripts/audit_translation_collisions.py). With the guard on, an entry
        # that cannot fit before its neighbour falls through to the normal
        # relocate / fallback path instead of overwriting the neighbour.
        self.collision_guard = collision_guard
        self._cell_boundaries = (
            sorted(set(cell_boundaries)) if cell_boundaries else None
        )
        # Pristine snapshot of the ROM as it was *before* any reinsertion, used
        # for original-length inference and padding detection. Reading the live
        # ``rom_data`` instead made those measurements depend on how many
        # neighbours had already been written, so the same translation could be
        # judged "fits in place" or "too long → fallback/relocate" depending on
        # input order. That flipped which strings relocated and reshuffled the
        # whole free-space layout, so a no-change rebuild from a differently
        # ordered translation JSON drifted ~0.2 % of the ROM. Measuring against
        # the immutable source makes the decision a property of the source
        # layout alone — order-independent and reproducible.
        self._source_snapshot = bytes(rom_data)
        # Relocations are deferred until all in-place writes are done:
        # the free-space scan must see the final state of the inter-string
        # padding, otherwise a relocated string can land in padding that an
        # in-place write later expands into (and vice versa), corrupting both.
        self._pending_relocations: List[tuple] = []
        # Identical encoded strings (incl. terminator) are relocated once and
        # their pointer sites all aimed at the single shared copy. Relocated
        # text is read-only, so sharing is safe and recovers a large amount of
        # free space (the IT build relocates thousands of duplicate trainer
        # class names / repeated dialogue lines).
        self._relocation_cache: Dict[bytes, int] = {}
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
            'pointer_sites_rejected': 0,
            'failures': 0,
            'warnings': []
        }

    def _next_cell_boundary(self, offset: int) -> Optional[int]:
        """Smallest known cell start strictly greater than ``offset``.

        Used by the collision guard as the hard wall an in-place write must
        terminate before. ``None`` when the guard is off, no boundaries were
        supplied, or ``offset`` is past the last known cell.
        """
        if not self.collision_guard or not self._cell_boundaries:
            return None
        idx = bisect.bisect_right(self._cell_boundaries, offset)
        if idx >= len(self._cell_boundaries):
            return None
        return self._cell_boundaries[idx]

    def _infer_original_length(self, offset: int, encoding: str, max_length: int = 1000) -> int:
        # Measured against the pristine snapshot, never the live ROM, so the
        # answer does not depend on how many neighbours were written first.
        src = self._source_snapshot
        terminator = 0x00 if encoding == 'ascii' else 0xFF
        length = 0
        for i in range(max_length):
            if offset + i >= len(src):
                break
            if src[offset + i] == terminator:
                break
            length += 1
        return length

    def _detect_padding(self, offset: int, length: int, encoding: str) -> int:
        # Padding is the inter-string gap in the *source* layout; reading the
        # live ROM made it shrink/grow with prior writes (order-dependent).
        src = self._source_snapshot
        end = offset + length
        if end >= len(src):
            return 0
        terminator = 0x00 if encoding == 'ascii' else 0xFF
        if src[end] == terminator:
            end += 1
        padding = 0
        while end + padding < len(src):
            byte = src[end + padding]
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

    def _plausible_pointer_sites(self, offset: int, sites: List[int]) -> List[int]:
        """Keep only pointer sites that can really reference this string.

        The extraction's ``pointer_offsets`` are raw 4-byte scans and contain
        massive false positives: common Thumb instruction sequences happen to
        equal ``0x08xxxxxx`` (one string had ~200 "pointers" all inside code).
        Writing relocated addresses over those sites corrupts code — battles
        crashed to a hard reset. A real text reference is either 4-byte
        aligned (literal pools, data tables) or sits right after a script
        opcode that takes a text pointer. Skipping a genuine reference is
        safe by comparison: the site keeps pointing at the original string.

        Recognized script shapes (verified against the Unbound ROM):
        - ``0F 00 <ptr>``      loadpointer, bank 0 (msgbox)
        - ``85 <buf> <ptr>``   bufferstring
        - ``67 <ptr>``         preparemsg — the pointer follows the opcode
          byte *immediately* (a ``67 00 <ptr>`` shape does not exist and
          used to wrongly reject every preparemsg dialogue)
        - ``5C ...``           trainerbattle (text pointers at +6 and +10)
        - ``<EWRAM u32> <ptr>``  battle-script ``setword``: CFRU prints
          custom battle strings via ``setword gBattleStringLoader, <text>``
          followed by ``printstring 0x184``, so the four bytes before the
          site decode to an EWRAM address (0x02000000-0x0203FFFF)
        - proof-ROM rewrite: the same site holds a *different* in-ROM
          pointer in ``pointer_proof_rom`` (another translation of the same
          base ROM relocated this very string and repointed the site)
        """
        # Verify against the pristine snapshot: a prior in-place write can
        # clobber the bytes at (or around) a candidate site, which would flip
        # the value/opcode checks and, with them, whether this string relocates
        # — making the layout depend on processing order. In the source the
        # site still holds the original pointer, so the decision is stable.
        rom = self._source_snapshot
        expected = struct.pack('<I', 0x08000000 + offset)
        kept = []
        for site in sites:
            if site < 0 or site + 4 > len(rom):
                continue
            if bytes(rom[site:site + 4]) != expected:
                continue
            plausible = (
                site % 4 == 0
                or (site >= 2 and rom[site - 2] == 0x0F and rom[site - 1] == 0x00)
                or (site >= 2 and rom[site - 2] == 0x85 and rom[site - 1] <= 0x0F)
                or (site >= 1 and rom[site - 1] == 0x67)
                or (site >= 6 and rom[site - 6] == 0x5C)
                or (site >= 10 and rom[site - 10] == 0x5C)
                or (site >= 4 and self._is_ewram_word(rom, site - 4))
                or self._proof_rom_repointed(site, expected)
            )
            if plausible:
                kept.append(site)
            else:
                self.stats['pointer_sites_rejected'] += 1
        return kept

    @staticmethod
    def _is_ewram_word(rom, pos: int) -> bool:
        value = struct.unpack_from('<I', rom, pos)[0]
        return 0x02000000 <= value < 0x02040000

    def _proof_rom_repointed(self, site: int, expected: bytes) -> bool:
        proof = self.pointer_proof_rom
        if proof is None or site + 4 > len(proof):
            return False
        word = proof[site:site + 4]
        if word == expected:
            return False
        value = struct.unpack('<I', word)[0]
        return 0x08000000 <= value < 0x08000000 + len(proof)

    def _queue_relocation(self, encoded: bytes, pointer_offsets: List[int], offset: int) -> bool:
        self._pending_relocations.append((encoded, pointer_offsets, offset))
        return True

    def flush_relocations(self) -> None:
        """Apply deferred relocations after every in-place write is done."""
        if not self._pending_relocations:
            return
        if self.free_space_allocator is None:
            # Precise ranges take precedence over the blanket proof-ROM carve:
            # generic builds reserve only the real inline-write spans and free
            # the rest of the pool; FR passes no ranges and keeps the blanket
            # carve (byte-identical).
            if self.reserved_ranges is not None:
                self.free_space_allocator = FreeSpaceAllocator(
                    self.rom_data,
                    min_block=self.free_space_min,
                    reserved_ranges=self.reserved_ranges,
                )
            else:
                self.free_space_allocator = FreeSpaceAllocator(
                    self.rom_data,
                    min_block=self.free_space_min,
                    reserved_rom=self.pointer_proof_rom,
                )
        pending, self._pending_relocations = self._pending_relocations, []
        # Place the shortest strings first. Free space is a hard budget (the
        # Italian build's relocation demand exceeds the total free space), so
        # when not everything fits we maximise the *number* of strings that get
        # their translation — leaving only the few longest ones in English
        # instead of an arbitrary offset-ordered slice.
        #
        # The tie-break is a *total* order — (encoded bytes, source offset) —
        # not the input order. The translation JSON is regenerated through
        # different paths (the trilingual-CSV pipeline vs prepare_fr_json) that
        # emit the same entries in a different sequence; a stable-by-length sort
        # then placed equal-length strings in that incoming order, so a
        # no-change rebuild reshuffled the free-space packing and every
        # repointed pointer (~0.2 % of the ROM drifted each rebuild). A canonical
        # key makes the layout depend only on the *set* of translations, so the
        # same content always yields byte-identical bytes. (item[0] is the
        # encoded string, item[2] the source offset, unique per entry.)
        pending.sort(key=lambda item: (len(item[0]), item[0], item[2]))
        for encoded, pointer_offsets, offset in pending:
            self._relocate_text(encoded, pointer_offsets, offset)

    def _relocate_text(self, encoded: bytes, pointer_offsets: List[int], offset: int) -> bool:
        if not self.free_space_allocator:
            return False

        # Reuse an already-relocated identical string instead of spending more
        # free space on a second byte-for-byte copy.
        cached = self._relocation_cache.get(encoded)
        if cached is not None:
            updated = 0
            for pointer_offset in pointer_offsets:
                if self._write_pointer(pointer_offset, cached):
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
            self.stats['relocated_deduplicated'] = (
                self.stats.get('relocated_deduplicated', 0) + 1
            )
            self.stats['success'] += 1
            return True

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

        self._relocation_cache[encoded] = new_offset
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
                encoded = TextEncoder.encode(text, encoding, skip_aliases=self.skip_encode_aliases)
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

            # Collision guard: cap the in-place budget so the terminator (the
            # last encoded byte) lands strictly before the next occupied cell,
            # i.e. offset + encoded_len < next_offset. An over-counted padding
            # run must never let this write spill into a neighbour; when the
            # capped budget no longer fits, the block below relocates or falls
            # back instead of overwriting the next cell.
            next_boundary = self._next_cell_boundary(offset)
            if next_boundary is not None:
                cap = next_boundary - offset - 1
                max_length = cap if max_length is None else min(max_length, cap)

            if max_length is not None and encoded_len > max_length:
                # Lossless first: relocate the overflowing text elsewhere and
                # repoint to it (only possible when the pointers are known).
                if self.allow_relocate and pointer_offsets:
                    safe_sites = self._plausible_pointer_sites(offset, pointer_offsets)
                    if safe_sites:
                        return self._queue_relocation(encoded, safe_sites, offset)

                # Synthesize a shorter French variant that fits in place rather
                # than leaving the English string behind. Operates on `text`,
                # so it also rescues entries whose `raw_bytes` came pre-encoded.
                if allow_fallback and self.fallback is not None and text and max_length > 0:
                    result = self.fallback.shrink_to_fit(text, encoding, max_length)
                    if result.fits:
                        encoded = TextEncoder.encode(result.text, encoding, skip_aliases=self.skip_encode_aliases)
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
        # Process in ascending offset order so the result does not depend on the
        # input sequence. Some neighbouring entries write overlapping spans (e.g.
        # the type-name table holds two near-identical cells one byte apart); the
        # last writer wins, so a fixed traversal order is what makes a no-change
        # rebuild from a differently ordered translation set byte-identical.
        for translation in sorted(translations, key=lambda t: t.get('offset', 0)):
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
                'relocated_deduplicated': self.stats.get('relocated_deduplicated', 0),
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
