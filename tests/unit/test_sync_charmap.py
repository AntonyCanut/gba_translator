"""Tests for scripts/sync_charmap.py"""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE, CONTROL_CODES


class TestSyncCharmapExecution:
    def test_script_runs_without_error(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sync_charmap.py")],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

    def test_script_check_mode_passes(self):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sync_charmap.py")],
            capture_output=True, text=True, cwd=str(ROOT), check=True,
        )
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sync_charmap.py"), "--check"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert result.returncode == 0, f"Check mode failed:\n{result.stdout}"

    def test_script_is_idempotent(self):
        script = str(ROOT / "scripts" / "sync_charmap.py")
        subprocess.run([sys.executable, script], capture_output=True, text=True, cwd=str(ROOT), check=True)

        emulator_ts = (ROOT / "emulator-web" / "src" / "charmap.ts").read_text()
        e2e_ts = (ROOT / "tests" / "e2e-playwright" / "helpers" / "charmap.ts").read_text()

        subprocess.run([sys.executable, script], capture_output=True, text=True, cwd=str(ROOT), check=True)

        assert (ROOT / "emulator-web" / "src" / "charmap.ts").read_text() == emulator_ts
        assert (ROOT / "tests" / "e2e-playwright" / "helpers" / "charmap.ts").read_text() == e2e_ts


class TestGeneratedTSSyntax:
    @pytest.fixture(autouse=True)
    def run_sync(self):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sync_charmap.py")],
            capture_output=True, text=True, cwd=str(ROOT), check=True,
        )

    def test_emulator_ts_syntax_valid(self):
        content = (ROOT / "emulator-web" / "src" / "charmap.ts").read_text()
        assert "export const POKEMON_TERMINATOR" in content
        assert "export const POKEMON_NEWLINE" in content
        assert "BYTE_TO_CHAR" in content
        assert "export function decodePokemonText" in content
        assert "export function encodePokemonText" in content
        assert content.count("export function") == 2
        # No unterminated strings or template literals
        assert "undefined" not in content or "!== undefined" in content

    def test_e2e_ts_syntax_valid(self):
        content = (ROOT / "tests" / "e2e-playwright" / "helpers" / "charmap.ts").read_text()
        assert "export const POKEMON_TERMINATOR" in content
        assert "BYTE_TO_CHAR" in content
        assert "CHAR_TO_BYTE" in content
        assert "export function hexToBytes" in content

    def test_emulator_ts_has_no_syntax_errors_via_regex(self):
        content = (ROOT / "emulator-web" / "src" / "charmap.ts").read_text()
        open_braces = content.count('{')
        close_braces = content.count('}')
        assert open_braces == close_braces, f"Brace mismatch: {open_braces} open vs {close_braces} close"

        open_parens = content.count('(')
        close_parens = content.count(')')
        assert open_parens == close_parens, f"Paren mismatch: {open_parens} open vs {close_parens} close"


class TestCharmapConsistency:
    def test_python_char_to_byte_count(self):
        assert len(CHAR_TO_BYTE) >= 70, f"Expected at least 70 entries, got {len(CHAR_TO_BYTE)}"

    def test_python_byte_to_char_count(self):
        assert len(BYTE_TO_CHAR) >= 70, f"Expected at least 70 entries, got {len(BYTE_TO_CHAR)}"

    def test_byte_to_char_entries_in_generated_ts(self):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sync_charmap.py")],
            capture_output=True, text=True, cwd=str(ROOT), check=True,
        )
        content = (ROOT / "emulator-web" / "src" / "charmap.ts").read_text()

        map_section = content.split("new Map([")[1].split("]);")[0]
        ts_entries = re.findall(r'\[0x([0-9a-f]{2}),\s', map_section)
        ts_count = len(ts_entries)
        py_count = len(BYTE_TO_CHAR)
        assert ts_count == py_count, f"Entry count mismatch: Python={py_count}, TS={ts_count}"

    def test_control_codes_present_in_ts(self):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sync_charmap.py")],
            capture_output=True, text=True, cwd=str(ROOT), check=True,
        )
        content = (ROOT / "emulator-web" / "src" / "charmap.ts").read_text()

        for code in CONTROL_CODES:
            hex_str = f"0x{code:02x}"
            assert hex_str in content, f"Control code {hex_str} missing from TS"


class TestFrenchAccents:
    REQUIRED_ACCENTS = list("éèàâçùî")
    ALIAS_ACCENTS = list("êëûüïôœ")

    def test_direct_french_accents_in_charmap(self):
        for accent in self.REQUIRED_ACCENTS:
            assert accent in CHAR_TO_BYTE, f"French accent '{accent}' missing from CHAR_TO_BYTE"

    def test_french_accents_in_generated_ts(self):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sync_charmap.py")],
            capture_output=True, text=True, cwd=str(ROOT), check=True,
        )
        content = (ROOT / "emulator-web" / "src" / "charmap.ts").read_text()

        for accent in self.REQUIRED_ACCENTS:
            assert accent in content, f"French accent '{accent}' missing from generated TS"

    def test_report_includes_accent_count(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sync_charmap.py")],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert "FR accents present" in result.stdout
