"""E2E: in-game version display ("FR.2.0.<build>") on the intro screens.

Builds the version display the way the release pipeline does — by running the
production ``patch_version_fr`` over the real English ROM — and then reads the
result back with the *independent* blind decoder in
``scripts.verify_version_display`` to prove the **NOT FOR SALE** screen literally
spells ``FR.2.0.<build_number>`` and the header software-version byte matches.

Note on the title screen
------------------------
The ticket asked to verify "the title screen and NOT FOR SALE screen both
display FR.2.0.<build>".  The dependency B-19 established that Pokémon Unbound's
real title screen (PRESS START) shows **no** version string at all — the only
in-game version display is on the NOT FOR SALE screen.  The old "title screen"
pointers (0x1413AC / 0x1413B8) actually address the Game Corner slot machine,
and an earlier patch corrupted that screen.  So the title-screen guarantee here
is the *correct* one: the version patch must leave those pointers untouched
(no slot-machine regression) while the NOT FOR SALE screen carries the version.

These tests are marked ``rom`` (they need ``input/roms/englishrom.gba``) and run
in the CI "standard" job.  A separate test verifies the actually-built
``output/roms/GenedRom-fr.gba`` when it is present.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EN_ROM = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"

from scripts.patch_version_fr import (  # noqa: E402
    patch_intro_version,
    patch_version,
    version_string,
)
from scripts.verify_version_display import (  # noqa: E402
    decode_version_string,
    slot_machine_pointers,
    verify,
)

# Build numbers covering single, double, triple and quadruple digits.
_BUILD_NUMBERS = [0, 5, 42, 137, 9999]


@pytest.fixture(scope="module")
def en_rom_bytes() -> bytes:
    if not EN_ROM.exists():
        pytest.skip("englishrom.gba not found in input/roms/")
    return EN_ROM.read_bytes()


def _build_versioned_rom(en_rom_bytes: bytes, build_number: int) -> bytearray:
    """Apply the production version patches to a fresh copy of the EN ROM."""
    data = bytearray(en_rom_bytes)
    patch_version(data, build_number)
    patch_intro_version(data, build_number)
    return data


@pytest.mark.rom
class TestNotForSaleVersionDisplay:
    """The NOT FOR SALE screen must display FR.2.0.<build_number>."""

    @pytest.mark.parametrize("build", _BUILD_NUMBERS)
    def test_screen_displays_expected_version(self, en_rom_bytes, build):
        rom = _build_versioned_rom(en_rom_bytes, build)
        assert decode_version_string(rom) == version_string(build)

    @pytest.mark.parametrize("build", _BUILD_NUMBERS)
    def test_full_verification_passes(self, en_rom_bytes, build):
        rom = _build_versioned_rom(en_rom_bytes, build)
        assert verify(rom, build) == []

    def test_header_software_version_byte(self, en_rom_bytes):
        rom = _build_versioned_rom(en_rom_bytes, 42)
        assert rom[0xBC] == 42 & 0xFF

    def test_distinct_builds_render_distinct_text(self, en_rom_bytes):
        a = decode_version_string(_build_versioned_rom(en_rom_bytes, 5))
        b = decode_version_string(_build_versioned_rom(en_rom_bytes, 8))
        assert a != b
        assert a == "FR.2.0.5"
        assert b == "FR.2.0.8"


@pytest.mark.rom
class TestTitleScreenInvariant:
    """The title screen carries no version; the slot-machine must stay intact."""

    def test_slot_machine_pointers_untouched(self, en_rom_bytes):
        before = slot_machine_pointers(en_rom_bytes)
        after = slot_machine_pointers(_build_versioned_rom(en_rom_bytes, 42))
        assert before == after, (
            "version patch modified the Game Corner slot-machine pointers "
            "(0x1413AC / 0x1413B8) — the B-19 regression has returned"
        )

    def test_unpatched_en_rom_does_not_show_fr_version(self, en_rom_bytes):
        # Sanity: the stock EN ROM does not already spell an FR.2.0 string.
        assert not decode_version_string(en_rom_bytes).startswith("FR.2.0.")


@pytest.mark.rom
class TestPipelineCli:
    """End-to-end through the exact CLIs the release pipeline runs.

    Mirrors what ``make build-fr`` + the CI verify step do: stamp a build
    number into a ROM with ``patch_version_fr.py``, then prove
    ``verify_version_display.py`` accepts it (and rejects the wrong number).
    """

    def test_patch_then_verify_cli(self, en_rom_bytes, tmp_path):
        import subprocess
        import sys

        rom = tmp_path / "build_fr.gba"
        rom.write_bytes(en_rom_bytes)
        build = 77

        patch = subprocess.run(
            [sys.executable, "scripts/patch_version_fr.py",
             "--rom", str(rom), "--build-number", str(build)],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        assert patch.returncode == 0, patch.stderr

        ok = subprocess.run(
            [sys.executable, "scripts/verify_version_display.py",
             "--rom", str(rom), "--build-number", str(build)],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        assert ok.returncode == 0, ok.stderr
        assert version_string(build) in ok.stdout

        # Verifying against the wrong build number must fail the pipeline.
        bad = subprocess.run(
            [sys.executable, "scripts/verify_version_display.py",
             "--rom", str(rom), "--build-number", str(build + 1)],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        assert bad.returncode != 0
        assert "NOT FOR SALE" in bad.stderr
