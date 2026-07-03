"""Fixtures for the ES reference-language e2e tests.

Spanish (``languages/es``) is a ``build: none`` / ``status: reference``
language (see ``src/i18n/registry.py``): it is the community Spanish
translation ROM used as ground truth by the pointer-based pipeline, not a
ROM this project builds. There is no ``GenedRom-es.gba`` and no boot/build
test applies — these tests instead guard the *reference extraction*
(``languages/es/combined_es.txt``) against drift versus the live
``spanishrom.gba`` bytes and versus FR's offset coverage.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.apply_combined_fr import _load_combined  # noqa: E402

ES_COMBINED_PATH = REPO_ROOT / "languages" / "es" / "combined_es.txt"
FR_COMBINED_PATH = REPO_ROOT / "languages" / "fr" / "combined_fr.txt"


@pytest.fixture(scope="module")
def es_combined_entries():
    if not ES_COMBINED_PATH.exists():
        pytest.skip(f"{ES_COMBINED_PATH} not found")
    entries, _skipped = _load_combined(ES_COMBINED_PATH)
    return entries


@pytest.fixture(scope="module")
def fr_combined_entries():
    if not FR_COMBINED_PATH.exists():
        pytest.skip(f"{FR_COMBINED_PATH} not found")
    entries, _skipped = _load_combined(FR_COMBINED_PATH)
    return entries
