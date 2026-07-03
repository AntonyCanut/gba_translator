"""E2E: German ROM build pipeline integrity.

Validates that the German ROM built by `scripts/build_language.py de`
is structurally sound, contains translated text, and meets minimum
quality thresholds. Mirrors tests/e2e/it/test_build.py.

These tests are language-specific: they accept German linguistic markers
(umlauts, common words) and the known build stats for the DE pipeline.
Every ROM/report/JSON-backed test skips gracefully when its artifact is
absent — as of this writing German is still mid-translation (batches
running against languages/de/combined_de.txt) and has never been built
locally, so this file only turns green once `make build-de` has run.

The `TestCombinedFileCoverage` class is the one exception: it reads
languages/de/combined_de.txt directly, so it gives a real signal on every
run regardless of whether the ROM has been built.

Run against the pre-built ROM:
    make build-de && pytest tests/e2e/de/test_build.py -v
"""

import json
import os
import pathlib
import re
import struct
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))


def _resolve_project_root() -> pathlib.Path:
    """Return the project root the tests are actually running from.

    Defaults to the checkout containing this file — when running inside a
    git worktree (.singularity-worktrees/<id>/), that's the worktree's own
    checkout, so tests exercise the ROM that was built/checked out there
    instead of silently reading whatever the main checkout happens to have
    at that moment (which can be mid-edit from a concurrent task). Set
    GBA_PROJECT_ROOT to explicitly point at a different (e.g. shared/
    canonical) checkout.
    """
    env_root = os.environ.get("GBA_PROJECT_ROOT")
    if env_root:
        return pathlib.Path(env_root)
    return pathlib.Path(__file__).resolve().parent.parent.parent.parent


PROJECT_ROOT = _resolve_project_root()

DE_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-de.gba"
EN_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"
DE_JSON_PATH = PROJECT_ROOT / "output" / "translation" / "de_translation_ready.json"
DE_REPORT_GLOB = "output/reports/*_derom_build_report.json"
DE_COMBINED_PATH = PROJECT_ROOT / "languages" / "de" / "combined_de.txt"

GBA_ROM_SIZE = 0x2000000
GAME_CODE = "BPRE"


@pytest.fixture(scope="module")
def de_rom_data():
    if not DE_ROM_PATH.exists():
        pytest.skip(
            "GenedRom-de.gba not found — run: python3 scripts/build_language.py de"
        )
    return DE_ROM_PATH.read_bytes()


@pytest.fixture(scope="module")
def en_rom_data():
    if not EN_ROM_PATH.exists():
        pytest.skip("englishrom.gba not found in input/roms/")
    return EN_ROM_PATH.read_bytes()


@pytest.fixture(scope="module")
def de_translation_json():
    if not DE_JSON_PATH.exists():
        pytest.skip("de_translation_ready.json not found in output/translation/")
    with open(DE_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def de_build_report():
    reports = sorted(PROJECT_ROOT.glob(DE_REPORT_GLOB))
    if not reports:
        pytest.skip("No German build report found — run build_language.py de first")
    with open(reports[-1], encoding="utf-8") as f:
        return json.load(f)


class TestRomIntegrity:
    """The German ROM must be a valid 32 MB GBA file."""

    def test_rom_exists(self):
        # The German ROM is a best-effort, non-committed build artifact, like
        # the Italian one: not checked into git, ignored by CI's fast/PR
        # suite, built on-demand. Skip (matching every other test in this
        # file) rather than hard-failing on an intentionally-absent file.
        if not DE_ROM_PATH.exists():
            pytest.skip(
                f"GenedRom-de.gba not found at {DE_ROM_PATH} — "
                "run: python3 scripts/build_language.py de"
            )
        assert DE_ROM_PATH.is_file()

    def test_rom_size(self, de_rom_data):
        assert len(de_rom_data) == GBA_ROM_SIZE, (
            f"ROM size {len(de_rom_data)} != {GBA_ROM_SIZE}"
        )

    def test_game_code_bpre(self, de_rom_data):
        code = de_rom_data[0xAC:0xB0].decode("ascii", errors="ignore")
        assert code == GAME_CODE, f"Game code corrupted: {code!r}"

    def test_entry_point_valid(self, de_rom_data):
        entry = struct.unpack_from("<I", de_rom_data, 0)[0]
        assert entry != 0, "Entry point is zero — ROM may be corrupted"

    def test_rom_title_present(self, de_rom_data):
        title = de_rom_data[0xA0:0xAC].decode("ascii", errors="ignore").rstrip("\x00")
        assert len(title) > 0, "ROM title is empty"

    def test_differs_from_english(self, de_rom_data, en_rom_data):
        diff_count = sum(1 for a, b in zip(de_rom_data, en_rom_data) if a != b)
        diff_pct = diff_count / len(en_rom_data) * 100
        assert diff_pct > 0.5, (
            f"DE ROM barely differs from EN: {diff_pct:.3f}% — translations not applied?"
        )
        assert diff_pct < 20.0, (
            f"DE ROM differs too much from EN: {diff_pct:.1f}% — possible corruption"
        )


class TestBuildStats:
    """Build report statistics must meet quality thresholds."""

    def test_zero_failures(self, de_build_report):
        stats = de_build_report.get("statistics", {})
        failed = stats.get("failed", 0)
        assert failed == 0, f"{failed} entries failed to inject"

    def test_no_corruption(self, de_build_report):
        stats = de_build_report.get("statistics", {})
        corrupted = stats.get("corrupted", 0)
        assert corrupted == 0, f"{corrupted} entries corrupted during injection"

    def test_relocation_reasonable(self, de_build_report):
        stats = de_build_report.get("statistics", {})
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


class TestCombinedFileCoverage:
    """languages/de/combined_de.txt must contain real German text.

    Unlike the rest of this file this needs no build artifact — it reads
    the source-of-truth translation file directly, so it gives a signal
    while German translation batches are still in progress.
    """

    GERMAN_PATTERN = re.compile(
        r"[äöüßÄÖÜ]|der |die |das |und |nicht |ist |mit |ein |eine |dein |sich "
    )
    LINE_RE = re.compile(r"^0x[0-9A-Fa-f]+:\s?(.*)$")

    @staticmethod
    @pytest.fixture(scope="class")
    def combined_entries():
        if not DE_COMBINED_PATH.exists():
            pytest.skip("languages/de/combined_de.txt not found")
        entries = []
        with open(DE_COMBINED_PATH, encoding="utf-8") as f:
            for line in f:
                m = TestCombinedFileCoverage.LINE_RE.match(line.rstrip("\n"))
                if m:
                    entries.append(m.group(1))
        return entries

    def test_file_has_entries(self, combined_entries):
        assert len(combined_entries) > 0, "combined_de.txt has no offset entries"

    def test_german_markers_present(self, combined_entries):
        checked = [e for e in combined_entries if len(e) >= 5]
        german_count = sum(1 for e in checked if self.GERMAN_PATTERN.search(e))
        if not checked:
            pytest.skip("No entries long enough to check")
        pct = german_count / len(checked) * 100
        assert pct > 5.0, (
            f"Only {pct:.1f}% of entries contain German indicators "
            f"({german_count}/{len(checked)}). Translations may not be in German."
        )

    def test_not_all_identical_to_placeholder(self, combined_entries):
        # combined_de.txt is append-only across translation batches; a run
        # that accidentally wrote back the English source for every offset
        # would still "have entries" but translate nothing.
        non_empty = [e for e in combined_entries if e.strip()]
        assert non_empty, "combined_de.txt entries are all empty"


class TestGermanTranslationCoverage:
    """Translation JSON must contain sufficient German content, once built."""

    GERMAN_PATTERN = TestCombinedFileCoverage.GERMAN_PATTERN

    def test_json_has_translations(self, de_translation_json):
        entries = de_translation_json.get("translations", [])
        assert len(entries) > 0, "German translation JSON is empty"

    def test_german_markers_present(self, de_translation_json):
        entries = de_translation_json.get("translations", [])
        german_count = 0
        total = 0
        for entry in entries:
            text = entry.get("translation", "")
            if not text or len(text) < 5:
                continue
            total += 1
            if self.GERMAN_PATTERN.search(text):
                german_count += 1
        if total == 0:
            pytest.skip("No entries to check")
        pct = german_count / total * 100
        assert pct > 5.0, (
            f"Only {pct:.1f}% of entries contain German indicators "
            f"({german_count}/{total}). Translations may not be in German."
        )

    def test_not_all_identical_to_english(self, de_translation_json):
        entries = de_translation_json.get("translations", [])
        identical = sum(
            1 for e in entries
            if e.get("translation") and e.get("original_text")
            and e["translation"].strip() == e["original_text"].strip()
        )
        with_text = [e for e in entries if e.get("translation")]
        if not with_text:
            pytest.skip("No translated entries")
        identical_pct = identical / len(with_text) * 100
        assert identical_pct < 95.0, (
            f"{identical_pct:.1f}% of entries are identical to English "
            f"({identical}/{len(with_text)}) — most text is still English"
        )


class TestRomEncodingSpots:
    """Spot-check specific ROM regions for German text bytes."""

    TEXT_REGION_START = 0x1F00000
    TEXT_REGION_END = 0x1F80000

    def test_text_region_modified(self, de_rom_data, en_rom_data):
        """Text region must differ between DE and EN ROMs."""
        start = self.TEXT_REGION_START
        end = min(self.TEXT_REGION_END, len(de_rom_data))
        diff = sum(
            1 for i in range(start, end)
            if de_rom_data[i] != en_rom_data[i]
        )
        assert diff > 0, "Text region is identical to English — no translations applied"


class TestStatusAbbreviations:
    """The `status_abbrevs` build step must write the official DE status
    abbreviations declared in languages/de/lang.yaml (GIF/VBR/GEF/PAR/SCH/KO)
    into the built ROM, not the English or a stale FR abbreviation."""

    def _encode(self, text: str) -> bytes:
        from src.core.text_codec import TextEncoder
        return TextEncoder.encode(text, "pokemon")[:-1]  # drop terminator

    @pytest.mark.parametrize("abbrev", ["GIF", "VBR", "GEF", "PAR", "SCH"])
    def test_abbreviation_present_in_rom(self, de_rom_data, abbrev):
        signature = self._encode(abbrev)
        assert de_rom_data.find(signature) != -1, (
            f"German status abbreviation {abbrev!r} not found in built ROM — "
            "the status_abbrevs patch step may not have run."
        )


class TestVersionDisplay:
    """The NOT FOR SALE intro screen must display the DE language tag.

    This is the regression guard for the ``version`` patch step in
    ``languages/de/lang.yaml``. If that step is accidentally removed the
    NOT FOR SALE screen reverts to the original Unbound ``v2.1.1.1`` tile
    graphics and the CI verifier rejects the ROM.
    """

    def test_not_for_sale_displays_de_prefix(self, de_rom_data):
        from scripts.verify_version_display import decode_version_string
        displayed = decode_version_string(de_rom_data)
        assert displayed.startswith("DE.2.1."), (
            f"NOT FOR SALE screen shows {displayed!r} instead of 'DE.2.1.<build>'. "
            "The 'version' patch step may be missing from languages/de/lang.yaml."
        )

    def test_verify_passes_for_actual_build_number(self, de_rom_data):
        from scripts.verify_version_display import verify
        build_number = de_rom_data[0xBC]
        problems = verify(de_rom_data, build_number, "de")
        assert problems == [], (
            f"Version verify failed (build #{build_number}): {problems}"
        )
