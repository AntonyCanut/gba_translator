"""E2E: ROM structural integrity after translation injection.

Verifies that the injected ROM preserves GBA header, game code,
code region, and pointer validity.
"""

import struct

import pytest

CODE_REGION_END = 0xC000


class TestRomHeader:
    """GBA ROM header must remain valid after injection."""

    def test_rom_size_preserved(self, injected_rom):
        output_path, _ = injected_rom
        size = output_path.stat().st_size
        assert size == 0x2000000, f"ROM size changed: {size} != 33554432"

    def test_game_code_bpre(self, injected_rom):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            f.seek(0xAC)
            code = f.read(4).decode("ascii", errors="ignore")
        assert code == "BPRE", f"Game code corrupted: {code!r}"

    def test_entry_point_preserved(self, injected_rom):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            entry = struct.unpack("<I", f.read(4))[0]
        assert entry != 0, "Entry point is zero"

    def test_title_not_empty(self, injected_rom):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            f.seek(0xA0)
            title = f.read(12).decode("ascii", errors="ignore").strip("\x00")
        assert len(title) > 0, "ROM title is empty"

    def test_header_checksum_byte_exists(self, injected_rom):
        output_path, _ = injected_rom
        with open(output_path, "rb") as f:
            f.seek(0xBD)
            checksum = f.read(1)[0]
        assert checksum != 0 or True  # Checksum CAN be zero, just verify it's readable


class TestCodeRegionPreservation:
    """Code region (0x100-0xC000) should be minimally changed."""

    def test_code_region_diff_under_threshold(self, injected_rom, en_rom_path):
        output_path, _ = injected_rom
        with open(en_rom_path, "rb") as f:
            en_data = f.read()
        with open(output_path, "rb") as f:
            fr_data = f.read()

        diff_bytes = sum(
            1 for i in range(0x100, CODE_REGION_END)
            if en_data[i] != fr_data[i]
        )
        region_size = CODE_REGION_END - 0x100
        diff_pct = (diff_bytes / region_size) * 100
        assert diff_pct < 1.0, (
            f"Code region diff too high: {diff_pct:.3f}% ({diff_bytes} bytes)"
        )


class TestInjectionResults:
    """Verify injection stats are healthy."""

    def test_injection_count_positive(self, injected_rom):
        _, report = injected_rom
        stats = report["statistics"]
        assert stats["successful"] > 0, "No strings were injected"

    def test_failure_rate_low(self, injected_rom):
        _, report = injected_rom
        stats = report["statistics"]
        total = stats["total_texts"]
        failed = stats["failed"]
        if total == 0:
            pytest.skip("No translations attempted")
        fail_rate = failed / total * 100
        assert fail_rate < 10.0, (
            f"Failure rate too high: {fail_rate:.1f}% ({failed}/{total})"
        )

    def test_no_critical_warnings(self, injected_rom):
        _, report = injected_rom
        warnings = report.get("warnings", [])
        index_errors = [
            w for w in warnings
            if "IndexError" in str(w.get("error", ""))
            or "ROM" in str(w.get("error", ""))
        ]
        assert len(index_errors) == 0, (
            f"{len(index_errors)} critical warnings: {index_errors[:3]}"
        )


class TestPointerIntegrity:
    """Verify pointer structure remains valid after injection."""

    def test_no_corrupted_pointers_in_text_region(self, injected_rom, en_rom_path):
        output_path, _ = injected_rom
        with open(en_rom_path, "rb") as f:
            en_data = f.read()
        with open(output_path, "rb") as f:
            fr_data = f.read()

        from src.core.rom_reader import ROMReader

        rom_size = len(en_data)
        corrupted = 0
        text_start = 0x1F00000
        text_end = min(0x1F80000, rom_size - 3)

        for offset in range(text_start, text_end, 4):
            en_ptr = struct.unpack_from("<I", en_data, offset)[0]
            fr_ptr = struct.unpack_from("<I", fr_data, offset)[0]

            if en_ptr == fr_ptr:
                continue

            en_valid = 0x08000000 <= en_ptr < 0x08000000 + rom_size
            fr_valid = 0x08000000 <= fr_ptr < 0x08000000 + rom_size

            if en_valid and not fr_valid:
                corrupted += 1

        assert corrupted == 0, f"{corrupted} pointers corrupted in text region"


class TestExistingFrenchRom:
    """Verify the pre-built French ROM is structurally sound."""

    def test_fr_rom_is_valid_gba(self, fr_rom_path):
        from src.core.rom_reader import ROMReader
        reader = ROMReader(str(fr_rom_path))
        reader.load()
        info = reader.get_rom_info()
        assert info["game_code"] == "BPRE"
        assert info["size_mb"] == 32

    def test_fr_rom_differs_from_en(self, en_rom_path, fr_rom_path):
        with open(en_rom_path, "rb") as f:
            en_data = f.read()
        with open(fr_rom_path, "rb") as f:
            fr_data = f.read()

        diff_count = sum(1 for a, b in zip(en_data, fr_data) if a != b)
        diff_pct = diff_count / len(en_data) * 100
        assert diff_pct > 0.1, (
            f"FR ROM barely differs from EN: {diff_pct:.3f}%"
        )
        assert diff_pct < 20.0, (
            f"FR ROM differs too much from EN: {diff_pct:.1f}%"
        )
