"""E2E: Italian ROM build pipeline integrity.

Validates that the Italian ROM built by `scripts/build_language.py it`
is structurally sound, contains translated text, and meets minimum
quality thresholds.

These tests are language-specific: they accept Italian linguistic
markers (accented vowels, common words) and the known build stats for
the IT pipeline.

Run against the pre-built ROM:
    pytest tests/e2e/test_italian_build.py -v
"""

import json
import os
import pathlib
import re
import struct
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))


def _resolve_project_root() -> pathlib.Path:
    """Return the main project root, even when running from a git worktree.

    Git worktrees live under .singularity-worktrees/ inside the main project;
    output files (ROMs, reports) stay in the main project and are not duplicated
    into worktrees.  Callers can also set GBA_PROJECT_ROOT to override.
    """
    env_root = os.environ.get("GBA_PROJECT_ROOT")
    if env_root:
        return pathlib.Path(env_root)
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == ".singularity-worktrees":
            return parent.parent
    return here.parent.parent.parent


PROJECT_ROOT = _resolve_project_root()

IT_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-it.gba"
EN_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"
IT_JSON_PATH = PROJECT_ROOT / "output" / "translation" / "it_translation_ready.json"
IT_REPORT_GLOB = "output/reports/*_itrom_build_report.json"

GBA_ROM_SIZE = 0x2000000
GAME_CODE = "BPRE"


@pytest.fixture(scope="module")
def it_rom_data():
    if not IT_ROM_PATH.exists():
        pytest.skip(
            "GenedRom-it.gba not found — run: python3 scripts/build_language.py it"
        )
    return IT_ROM_PATH.read_bytes()


@pytest.fixture(scope="module")
def en_rom_data():
    if not EN_ROM_PATH.exists():
        pytest.skip("englishrom.gba not found in input/roms/")
    return EN_ROM_PATH.read_bytes()


@pytest.fixture(scope="module")
def it_translation_json():
    if not IT_JSON_PATH.exists():
        pytest.skip("it_translation_ready.json not found in output/translation/")
    with open(IT_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def it_build_report():
    reports = sorted(PROJECT_ROOT.glob(IT_REPORT_GLOB))
    if not reports:
        pytest.skip("No Italian build report found — run build_language.py it first")
    with open(reports[-1], encoding="utf-8") as f:
        return json.load(f)


class TestRomIntegrity:
    """The Italian ROM must be a valid 32 MB GBA file."""

    def test_rom_exists(self):
        assert IT_ROM_PATH.exists(), (
            f"Italian ROM not found at {IT_ROM_PATH}. "
            "Run: python3 scripts/build_language.py it"
        )

    def test_rom_size(self, it_rom_data):
        assert len(it_rom_data) == GBA_ROM_SIZE, (
            f"ROM size {len(it_rom_data)} != {GBA_ROM_SIZE}"
        )

    def test_game_code_bpre(self, it_rom_data):
        code = it_rom_data[0xAC:0xB0].decode("ascii", errors="ignore")
        assert code == GAME_CODE, f"Game code corrupted: {code!r}"

    def test_entry_point_valid(self, it_rom_data):
        entry = struct.unpack_from("<I", it_rom_data, 0)[0]
        assert entry != 0, "Entry point is zero — ROM may be corrupted"

    def test_rom_title_present(self, it_rom_data):
        title = it_rom_data[0xA0:0xAC].decode("ascii", errors="ignore").rstrip("\x00")
        assert len(title) > 0, "ROM title is empty"

    def test_differs_from_english(self, it_rom_data, en_rom_data):
        diff_count = sum(1 for a, b in zip(it_rom_data, en_rom_data) if a != b)
        diff_pct = diff_count / len(en_rom_data) * 100
        assert diff_pct > 0.5, (
            f"IT ROM barely differs from EN: {diff_pct:.3f}% — translations not applied?"
        )
        assert diff_pct < 20.0, (
            f"IT ROM differs too much from EN: {diff_pct:.1f}% — possible corruption"
        )


class TestBuildStats:
    """Build report statistics must meet quality thresholds."""

    def test_zero_failures(self, it_build_report):
        stats = it_build_report.get("statistics", {})
        failed = stats.get("failed", 0)
        assert failed == 0, f"{failed} entries failed to inject"

    def test_replacement_rate(self, it_build_report):
        stats = it_build_report.get("statistics", {})
        total = stats.get("total_texts", 0)
        replaced = stats.get("successfully_replaced", 0)
        if total == 0:
            pytest.skip("No texts counted in build report")
        rate = replaced / total * 100
        assert rate >= 70.0, (
            f"Replacement rate too low: {rate:.1f}% ({replaced}/{total}). "
            "Fewer than 70% of texts were translated."
        )

    def test_no_corruption(self, it_build_report):
        stats = it_build_report.get("statistics", {})
        corrupted = stats.get("corrupted", 0)
        assert corrupted == 0, f"{corrupted} entries corrupted during injection"

    def test_relocation_reasonable(self, it_build_report):
        stats = it_build_report.get("statistics", {})
        relocated = stats.get("relocated", 0)
        relocation_failed = stats.get("relocation_failed", 0)
        if relocated + relocation_failed == 0:
            pytest.skip("No relocations attempted")
        fail_rate = relocation_failed / (relocated + relocation_failed) * 100
        assert fail_rate < 20.0, (
            f"Relocation failure rate too high: {fail_rate:.1f}% "
            f"({relocation_failed} failed, {relocated} succeeded). "
            "Free space may be exhausted."
        )


class TestItalianTranslationCoverage:
    """Translation JSON must contain sufficient Italian content."""

    ITALIAN_PATTERN = re.compile(
        r"[àáèéìíîòóùú]|il |la |le |gli |dei |nel |una |che |non |con |per "
    )

    def test_json_has_translations(self, it_translation_json):
        entries = it_translation_json.get("translations", [])
        assert len(entries) > 0, "Italian translation JSON is empty"

    def test_translation_count(self, it_translation_json):
        entries = it_translation_json.get("translations", [])
        with_text = [e for e in entries if e.get("translation")]
        assert len(with_text) > 15000, (
            f"Expected >15000 translated entries, got {len(with_text)}"
        )

    def test_italian_markers_present(self, it_translation_json):
        entries = it_translation_json.get("translations", [])
        italian_count = 0
        total = 0
        for entry in entries:
            text = entry.get("translation", "")
            if not text or len(text) < 5:
                continue
            total += 1
            if self.ITALIAN_PATTERN.search(text):
                italian_count += 1
        if total == 0:
            pytest.skip("No entries to check")
        pct = italian_count / total * 100
        assert pct > 5.0, (
            f"Only {pct:.1f}% of entries contain Italian indicators "
            f"({italian_count}/{total}). Translations may not be in Italian."
        )

    def test_not_all_identical_to_english(self, it_translation_json):
        entries = it_translation_json.get("translations", [])
        identical = sum(
            1 for e in entries
            if e.get("translation") and e.get("original_text")
            and e["translation"].strip() == e["original_text"].strip()
        )
        with_text = [e for e in entries if e.get("translation")]
        if not with_text:
            pytest.skip("No translated entries")
        identical_pct = identical / len(with_text) * 100
        assert identical_pct < 85.0, (
            f"{identical_pct:.1f}% of entries are identical to English "
            f"({identical}/{len(with_text)}) — most text is still English"
        )


class TestRomEncodingSpots:
    """Spot-check specific ROM regions for Italian text bytes."""

    TEXT_REGION_START = 0x1F00000
    TEXT_REGION_END = 0x1F80000

    def test_text_region_modified(self, it_rom_data, en_rom_data):
        """Text region must differ between IT and EN ROMs."""
        start = self.TEXT_REGION_START
        end = min(self.TEXT_REGION_END, len(it_rom_data))
        diff = sum(
            1 for i in range(start, end)
            if it_rom_data[i] != en_rom_data[i]
        )
        assert diff > 0, "Text region is identical to English — no translations applied"
        diff_pct = diff / (end - start) * 100
        assert diff_pct > 1.0, (
            f"Text region barely differs from EN: {diff_pct:.2f}% of bytes changed"
        )

    def test_pointer_corruption_rate_acceptable(self, it_rom_data, en_rom_data):
        """Pointer-sized values in the text region that look like valid EN pointers but
        become invalid in IT ROM.  The generic pipeline can legitimately overwrite such
        locations with text bytes (script opcodes, embedded data structures).  The FR ROM
        produced by the same pipeline has ~115 such cases; we allow up to 200 here as a
        regression guard.
        """
        rom_size = len(en_rom_data)
        start = self.TEXT_REGION_START
        end = min(self.TEXT_REGION_END, rom_size - 3)
        corrupted = 0

        for offset in range(start, end, 4):
            en_ptr = struct.unpack_from("<I", en_rom_data, offset)[0]
            it_ptr = struct.unpack_from("<I", it_rom_data, offset)[0]
            if en_ptr == it_ptr:
                continue
            en_valid = 0x08000000 <= en_ptr < 0x08000000 + rom_size
            it_valid = 0x08000000 <= it_ptr < 0x08000000 + rom_size
            if en_valid and not it_valid:
                corrupted += 1

        assert corrupted < 200, (
            f"{corrupted} pointer-sized values changed from valid EN to invalid IT. "
            "The generic pipeline baseline is ~51 for IT and ~115 for FR; >200 suggests "
            "a regression in pointer tracking."
        )


class TestVersionDisplay:
    """The NOT FOR SALE intro screen must display the IT language tag.

    This is the regression guard for the ``version`` patch step in
    ``languages/it/lang.yaml``.  If that step is accidentally removed the
    NOT FOR SALE screen reverts to the original Unbound ``v2.1.1.1`` tile
    graphics and the CI verifier rejects the ROM.
    """

    def test_not_for_sale_displays_it_prefix(self, it_rom_data):
        from scripts.verify_version_display import decode_version_string
        displayed = decode_version_string(it_rom_data)
        assert displayed.startswith("IT.2.1."), (
            f"NOT FOR SALE screen shows {displayed!r} instead of 'IT.2.1.<build>'. "
            "The 'version' patch step may be missing from languages/it/lang.yaml."
        )

    def test_verify_passes_for_actual_build_number(self, it_rom_data):
        from scripts.verify_version_display import verify
        build_number = it_rom_data[0xBC]
        problems = verify(it_rom_data, build_number, "it")
        assert problems == [], (
            f"Version verify failed (build #{build_number}): {problems}"
        )
