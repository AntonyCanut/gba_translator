import struct
import unittest

from src.core.text_codec import TextEncoder
from src.core.text_reinserter import SmartReinserter


class ReinserterRelocationTests(unittest.TestCase):
    def test_relocate_updates_pointer(self):
        # Free space must be a large 0xFF run to qualify for relocation.
        rom = bytearray([0xFF] * 0x4000)
        original_offset = 0x20
        rom[0:4] = struct.pack('<I', 0x08000000 + original_offset)

        original = TextEncoder.encode_pokemon('Hi')
        rom[original_offset:original_offset + len(original)] = original

        translation = {
            'offset': original_offset,
            'translation': 'Hello world',
            'encoding': 'pokemon',
            'original_length': 2,
            'padding_available': 0,
            'pointer_offsets': [0],
        }

        reinserter = SmartReinserter(rom, allow_relocate=True)
        success = reinserter.reinsert_text(translation)
        self.assertTrue(success)
        reinserter.flush_relocations()

        new_pointer = struct.unpack('<I', rom[0:4])[0] - 0x08000000
        self.assertNotEqual(new_pointer, original_offset)

        expected = TextEncoder.encode_pokemon('Hello world')
        actual = bytes(rom[new_pointer:new_pointer + len(expected)])
        self.assertEqual(expected, actual)

    def test_short_padding_runs_are_never_allocated(self):
        """Short 0xFF/0x00 runs are live data (sentinel arrays, zero-valued
        struct fields); allocating from them corrupted the battle engine."""
        from src.core.text_reinserter import FreeSpaceAllocator

        rom = bytearray([0xAB] * 0x2000)  # 8KB of non-padding data
        rom[0x900:0xA00] = b'\xff' * 0x100   # 256B FF run (sentinel array)
        rom[0xC00:0xD00] = b'\x00' * 0x100   # 256B zero run (struct fields)

        allocator = FreeSpaceAllocator(rom)
        self.assertEqual(allocator.blocks, [])
        self.assertIsNone(allocator.allocate(16))

    def test_large_run_allocated_with_margins(self):
        from src.core.text_reinserter import FreeSpaceAllocator

        rom = bytearray([0xAB] * 0x1000)  # 4KB data (no 0xFF/0x00 bytes)
        rom += b'\xff' * 0x2000           # 8KB free run at 0x1000
        rom += bytearray([0xAB] * 0x1000)

        allocator = FreeSpaceAllocator(rom)
        self.assertEqual(len(allocator.blocks), 1)
        start, length = allocator.blocks[0]
        self.assertEqual(start, 0x1000 + FreeSpaceAllocator.RUN_MARGIN)
        self.assertEqual(length, 0x2000 - 2 * FreeSpaceAllocator.RUN_MARGIN)
        alloc = allocator.allocate(64)
        self.assertEqual(alloc, 0x1000 + FreeSpaceAllocator.RUN_MARGIN)

    def test_reserved_rom_bytes_are_never_allocated(self):
        """Runs that are free here but populated in the reserved ROM (the
        Spanish layout mirrored later by the inline-overrides pass) must be
        skipped: a string relocated there was clobbered by the mirror write
        (Shadow Base door showed a move-description tail)."""
        from src.core.text_reinserter import FreeSpaceAllocator

        rom = bytearray([0xAB] * 0x1000)
        rom += b'\xff' * 0x4000           # 16KB free at 0x1000
        rom += bytearray([0xAB] * 0x1000)

        reserved = bytearray(rom)
        # The reserved ROM populates the first 8KB of the run with text.
        reserved[0x1000:0x3000] = b'\xD5' * 0x2000

        allocator = FreeSpaceAllocator(bytearray(rom), reserved_rom=bytes(reserved))
        self.assertEqual(len(allocator.blocks), 1)
        start, length = allocator.blocks[0]
        self.assertEqual(start, 0x3000 + FreeSpaceAllocator.RUN_MARGIN)
        self.assertEqual(length, 0x2000 - 2 * FreeSpaceAllocator.RUN_MARGIN)
        alloc = allocator.allocate(64)
        self.assertGreaterEqual(alloc, 0x3000)


class PostBuildHarvesterPoolTests(unittest.TestCase):
    """The blanket ``reserved_rom`` carve does double duty: besides protecting
    the inline-overrides mirror writes, it *preserves* the pool of bytes that
    are free (0xFF) in the target but populated in the reference (Spanish) ROM.
    Post-build relocation patches that run with ``reserved_rom=None`` —
    ``languages/de/patches/mission_descriptions.py`` (harvests 47 bounty
    descriptions), ``worldmap_junction_panels.py``, the Italian
    ``patch_long_dialogues_it.py`` — deliberately harvest exactly that pool.

    Regression: commit 0d89a68 (#54) let the main relocation pass consume that
    pool (it reserved only the inline-write spans instead of the whole Spanish
    footprint), so those post-build patches found no free space, exited 1, and
    broke ``make build-de`` / ``build-it`` in CI. The invariant below fails if
    the main pass is ever allowed to eat the reference-populated pool again.
    """

    # A clean 32 KB free run below the excluded graphics/upper-ROM ranges.
    RUN_START = 0x600000
    RUN_LEN = 0x8000
    # The slice that is 0xFF here but text in the reference ROM (the pool the
    # post-build harvesters need). 8 KB, centred in the run.
    RES_START = 0x604000
    RES_END = 0x606000

    def _rom_and_reference(self):
        size = self.RUN_START + self.RUN_LEN + 0x1000
        rom = bytearray([0xAB] * size)
        rom[self.RUN_START:self.RUN_START + self.RUN_LEN] = b'\xff' * self.RUN_LEN
        reference = bytearray(rom)
        reference[self.RES_START:self.RES_END] = b'\xD5' * (self.RES_END - self.RES_START)
        return rom, bytes(reference)

    def test_blanket_carve_preserves_harvester_pool(self):
        from src.core.text_reinserter import FreeSpaceAllocator

        rom, reference = self._rom_and_reference()

        # Main relocation pass: blanket carve. Drain everything it is allowed to.
        main = FreeSpaceAllocator(rom, reserved_rom=reference, min_block=1024)
        while True:
            off = main.allocate(0x200)
            if off is None:
                break
            # No allocation may land inside the reference-populated pool.
            self.assertFalse(
                self.RES_START <= off < self.RES_END,
                f"main pass allocated into the reserved pool at 0x{off:X}",
            )
            rom[off:off + 0x200] = b'\xAA' * 0x200

        # The reference-populated pool is untouched — still one clean 0xFF run.
        self.assertEqual(
            bytes(rom[self.RES_START:self.RES_END]),
            b'\xff' * (self.RES_END - self.RES_START),
        )

        # A post-build harvester (reserved_rom=None) still finds free space to
        # relocate into — the pool the main pass left untouched. Under #54 the
        # main pass would have consumed it and this allocation would fail.
        harvester = FreeSpaceAllocator(rom, reserved_rom=None, min_block=1024)
        self.assertIsNotNone(
            harvester.allocate(self.RES_END - self.RES_START - 2 * FreeSpaceAllocator.RUN_MARGIN),
            "harvester found no free space after the main relocation pass",
        )


class PlausiblePointerSiteTests(unittest.TestCase):
    """The site filter must accept every real script shape seen in Unbound
    and keep rejecting Thumb-code false positives (writing those crashed
    the battle engine)."""

    STRING_OFFSET = 0x200

    def _rom_with_site(self, before: bytes, site_align: int = 1) -> tuple:
        rom = bytearray([0xAB] * 0x400)
        site = 0x100 + site_align
        site -= (site - len(before)) % 4 == 0 and 0  # keep explicit
        rom[site - len(before):site] = before
        rom[site:site + 4] = struct.pack('<I', 0x08000000 + self.STRING_OFFSET)
        return rom, site

    def _kept(self, rom, site, **kwargs):
        reinserter = SmartReinserter(rom, allow_relocate=True, **kwargs)
        return reinserter._plausible_pointer_sites(self.STRING_OFFSET, [site])

    def test_aligned_site_accepted(self):
        rom, _ = self._rom_with_site(b'')
        site = 0x104  # aligned
        rom[site:site + 4] = struct.pack('<I', 0x08000000 + self.STRING_OFFSET)
        self.assertEqual(self._kept(rom, site), [site])

    def test_preparemsg_pointer_follows_opcode_immediately(self):
        # Script shape is `67 <ptr>` — NOT `67 00 <ptr>`. The old filter
        # required the latter and rejected every preparemsg dialogue,
        # which then got truncated in place ("Choisis une couleur de").
        rom, site = self._rom_with_site(b'\x67')
        self.assertEqual(self._kept(rom, site), [site])

    def test_loadpointer_and_bufferstring_accepted(self):
        rom, site = self._rom_with_site(b'\x0F\x00')
        self.assertEqual(self._kept(rom, site), [site])
        rom, site = self._rom_with_site(b'\x85\x01')
        self.assertEqual(self._kept(rom, site), [site])

    def test_battle_script_setword_to_ewram_accepted(self):
        # CFRU battle strings: setword gBattleStringLoader(0x0203C020), <text>
        rom, site = self._rom_with_site(struct.pack('<I', 0x0203C020))
        self.assertEqual(self._kept(rom, site), [site])

    def test_random_ewram_looking_word_outside_range_rejected(self):
        rom, site = self._rom_with_site(struct.pack('<I', 0x02080000))
        self.assertEqual(self._kept(rom, site), [])

    def test_thumb_code_false_positive_rejected(self):
        # `20 78 40 <ptr-looking bytes>` was a real false positive: code
        # whose bytes happened to equal the string address.
        rom, site = self._rom_with_site(b'\x20\x78\x40')
        self.assertEqual(self._kept(rom, site), [])

    def test_proof_rom_repointed_site_accepted(self):
        rom, site = self._rom_with_site(b'\xAA\xBB')
        self.assertEqual(self._kept(rom, site), [])  # no proof: rejected
        proof = bytes(rom[:site]) + struct.pack('<I', 0x08000300) + bytes(rom[site + 4:])
        self.assertEqual(self._kept(rom, site, pointer_proof_rom=proof), [site])

    def test_proof_rom_identical_value_is_not_proof(self):
        rom, site = self._rom_with_site(b'\xAA\xBB')
        self.assertEqual(self._kept(rom, site, pointer_proof_rom=bytes(rom)), [])

    def test_proof_rom_non_pointer_value_is_not_proof(self):
        rom, site = self._rom_with_site(b'\xAA\xBB')
        proof = bytearray(rom)
        proof[site:site + 4] = struct.pack('<I', 0x12345678)
        self.assertEqual(self._kept(rom, site, pointer_proof_rom=bytes(proof)), [])


if __name__ == '__main__':
    unittest.main()
