"""Tests for the pre-commit coverage guard on new combined translations."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_staged_translation_tests as staged  # noqa: E402


def test_parse_added_translations_only_reads_combined_entries():
    diff = """\
diff --git a/languages/fr/combined_fr.txt b/languages/fr/combined_fr.txt
+++ b/languages/fr/combined_fr.txt
@@ -1 +1,2 @@
+0x10: Bonjour
+# commentaire
diff --git a/languages/fr/protected_entries.yaml b/languages/fr/protected_entries.yaml
+++ b/languages/fr/protected_entries.yaml
@@ -1 +1,2 @@
+entries: []
diff --git a/README.md b/README.md
+++ b/README.md
@@ -1 +1,2 @@
+0x20: Ceci n'est pas une traduction
"""

    assert staged.parse_added_translations(diff) == [
        staged.AddedTranslation("fr", 0x10, "Bonjour"),
    ]


def test_missing_manifest_entry_fails():
    additions = [staged.AddedTranslation("fr", 0x10, "Bonjour")]
    staged_files = {
        "languages/fr/combined_fr.txt": "0x10: Bonjour\n",
        "languages/fr/protected_entries.yaml": "entries: []\n",
    }

    failures = staged.validate_added_translations(additions, staged_files)

    assert failures == [
        "[fr] 0x000010: aucune entrée de test unitaire dans protected_entries.yaml",
    ]


def test_manifest_must_expect_the_resolved_last_wins_value():
    additions = [staged.AddedTranslation("fr", 0x10, "Bonjour")]
    staged_files = {
        "languages/fr/combined_fr.txt": "0x10: Ancien\n0x10: Bonjour\n",
        "languages/fr/protected_entries.yaml": """\
entries:
  - offset: "0x10"
    name: Salutation
    expected: Salut
""",
    }

    failures = staged.validate_added_translations(additions, staged_files)

    assert failures == [
        "[fr] 0x000010: le test attend « Salut », mais la valeur live est « Bonjour »",
    ]


def test_live_translation_covered_by_manifest_passes():
    additions = [staged.AddedTranslation("fr", 0x10, "Ancien")]
    staged_files = {
        "languages/fr/combined_fr.txt": "0x10: Ancien\n0x10: Bonjour\n",
        "languages/fr/protected_entries.yaml": """\
entries:
  - offset: "0x10"
    name: Salutation
    expected: Bonjour
""",
    }

    assert staged.validate_added_translations(additions, staged_files) == []
