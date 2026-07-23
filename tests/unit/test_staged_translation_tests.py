"""Tests for the pre-commit coverage guard on new combined translations."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_staged_translation_tests as staged  # noqa: E402


def test_commit_without_unit_test_change_fails():
    staged_changes = [
        ("M", "languages/fr/combined_fr.txt"),
        ("M", "README.md"),
    ]

    failures = staged.validate_unit_test_change(staged_changes)

    assert failures == ["aucun test unitaire ajouté ou modifié dans l'index Git"]


def test_python_unit_test_change_covers_translation_change():
    staged_changes = [
        ("M", "languages/fr/combined_fr.txt"),
        ("M", "tests/unit/test_translation_integrity.py"),
    ]

    assert staged.validate_unit_test_change(staged_changes) == []


def test_root_python_test_change_covers_translation_change():
    staged_changes = [
        ("M", "languages/it/combined_it.txt"),
        ("A", "tests/test_new_italian_translation.py"),
    ]

    assert staged.validate_unit_test_change(staged_changes) == []


def test_vitest_change_covers_translation_change():
    staged_changes = [
        ("M", "languages/de/combined_de.txt"),
        ("M", "emulator-web/tests/charmap.test.ts"),
    ]

    assert staged.validate_unit_test_change(staged_changes) == []


def test_protected_entries_manifest_counts_as_data_driven_unit_test():
    staged_changes = [
        ("M", "languages/fr/combined_fr.txt"),
        ("M", "languages/fr/protected_entries.yaml"),
    ]

    assert staged.validate_unit_test_change(staged_changes) == []


def test_deleted_test_does_not_cover_translation_change():
    staged_changes = [
        ("M", "languages/fr/combined_fr.txt"),
        ("D", "tests/unit/test_translation_integrity.py"),
    ]

    assert staged.validate_unit_test_change(staged_changes)


def test_e2e_test_does_not_count_as_unit_test():
    staged_changes = [
        ("M", "languages/fr/combined_fr.txt"),
        ("M", "tests/e2e/fr/test_dialogue_replay.py"),
    ]

    assert staged.validate_unit_test_change(staged_changes)


def test_non_translation_commit_also_requires_test_change():
    staged_changes = [
        ("M", "scripts/check_staged_translation_tests.py"),
        ("M", "README.md"),
    ]

    assert staged.validate_unit_test_change(staged_changes)


def test_empty_index_does_not_trigger_the_guard():
    assert staged.validate_unit_test_change([]) == []


def test_parse_name_status_supports_renames_and_paths_with_spaces():
    output = """\
M\tlanguages/fr/combined_fr.txt
A\ttests/unit/test_translation_guard.py
R100\told name.txt\tnew name.txt
"""

    assert staged.parse_name_status(output) == [
        ("M", "languages/fr/combined_fr.txt"),
        ("A", "tests/unit/test_translation_guard.py"),
        ("R100", "new name.txt"),
    ]


def test_missing_unit_test_message_is_unambiguous_for_ai_agents():
    message = staged.MISSING_UNIT_TEST_MESSAGE

    assert "COMMIT INTERDIT" in message
    assert "AGENT IA" in message
    assert "ajouter ou modifier un test unitaire" in message
    assert "--no-verify" in message


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
