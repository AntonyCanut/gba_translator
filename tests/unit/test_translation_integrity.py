"""Tests for scripts/check_translation_integrity.py — multi-language anti-regression guard.

The guard's job: ``languages/<lang>/protected_entries.yaml`` is the single
source of truth for ticket-validated translations. ``combined_<lang>.txt``
must resolve (last-wins) every protected offset to EXACTLY the manifest value
— otherwise the commit is blocked (this test runs in ``make test-python-fast``,
which the husky pre-commit executes).

Covers:
- the real repo manifests pass against the live combined files;
- the issue #67 entry (0x417396 → « Sortir ») is protected, since a stale
  snapshot (2d7f7a6) already reverted it once;
- last-wins resolution, manifest validation, regression detection, --fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_translation_integrity as cti  # noqa: E402


def _write_manifest(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


SIMPLE_MANIFEST = """\
entries:
  - offset: "0x417396"
    name: "Menu équipe (#67)"
    issue: "#67"
    expected: 'Choisis Pokémon ou Sortir.'
    forbidden: ['Choisis Pokémon ou Annuler.']
  - offset: "0xA4E047"
    name: "Doit rester absent (#76)"
    absent: true
"""


class TestRealRepo:
    """The guard must pass on the live combined files in the repo."""

    def test_photographed_french_dialogues_are_all_protected(self):
        """Every dialogue reported by the translation-photo ticket has a guard."""
        fr = [target for target in cti.discover_languages() if target[0] == "fr"]
        assert fr
        entries = cti.load_manifest(fr[0][2])
        protected_offsets = {entry.offset for entry in entries}
        photographed_offsets = {
            0x1F83EFB, 0x1F84012, 0x1F842B1, 0x1F4AA46, 0x1F4A4A1,
            0x1F4A12F, 0x1F49E7A, 0x1F49A85, 0x1F49935, 0x1F4978D,
            0x1F4948D, 0x1F49459, 0x1F4921C, 0x1F49172, 0x1F49131,
            0x1F48FBD, 0x1F48E35, 0x1F4C712, 0x1F4BC44, 0x1F4B6D9,
            0x1F51177, 0x1F50576, 0x1F50BA2, 0x1F4FF74, 0x1F4F57B,
        }
        assert photographed_offsets <= protected_offsets

    def test_every_language_with_manifest_passes(self):
        targets = cti.discover_languages()
        assert targets, "no protected_entries.yaml manifest found under languages/"
        for lang, combined, manifest in targets:
            report = cti.build_report(combined, manifest, lang)
            failures = [f"0x{r.entry.offset:06X} {r.entry.name}: {r.reason}" for r in report.failures]
            assert report.ok, f"[{lang}] regressed protected entries:\n" + "\n".join(failures)

    def test_all_built_languages_have_a_manifest(self):
        langs = {lang for lang, _, _ in cti.discover_languages()}
        assert {"fr", "it", "de"} <= langs

    def test_issue_67_sortir_is_protected(self):
        # 0x417396 was reverted once by a stale-snapshot commit (2d7f7a6);
        # it must stay in the FR manifest with the « Sortir » wording.
        fr = [t for t in cti.discover_languages() if t[0] == "fr"]
        assert fr
        entries = cti.load_manifest(fr[0][2])
        by_offset = {entry.offset: entry for entry in entries}
        assert 0x417396 in by_offset
        assert by_offset[0x417396].expected == "Choisis Pokémon ou Sortir."

    def test_issue_147_quest_title_is_protected(self):
        fr = [t for t in cti.discover_languages() if t[0] == "fr"]
        assert fr
        entries = cti.load_manifest(fr[0][2])
        by_offset = {entry.offset: entry for entry in entries}
        entry = by_offset[0x1F56313]
        assert entry.expected == "Gravis le Mont Givre et dirige-toi\\nvers Cimistral !"
        assert "Monte le Mont Givre et dirige-toi\\nvers Cimistral !" in entry.forbidden

    def test_cube_sort_prompt_stays_absent(self):
        # Issue #76: an in-budget entry at 0xA4E047 re-enables the
        # --allow-fallback corruption; the offset must be flagged absent.
        fr = [t for t in cti.discover_languages() if t[0] == "fr"]
        entries = cti.load_manifest(fr[0][2])
        by_offset = {entry.offset: entry for entry in entries}
        assert 0xA4E047 in by_offset
        assert by_offset[0xA4E047].absent

    def test_issue_80_zygarde_percent_is_protected(self):
        # 0x791BBA ("1 pour cent" -> "1%") was fixed once (1a3ab5e) then
        # silently reverted 90s later by an unrelated commit (071c6813,
        # Boîte CT description) that carried a stale snapshot of this line
        # (Pattern C, docs/20_TRANSLATION_PRESERVATION.md §7). It must stay
        # guarded so any future stale-snapshot commit is caught pre-commit.
        fr = [t for t in cti.discover_languages() if t[0] == "fr"]
        assert fr
        entries = cti.load_manifest(fr[0][2])
        by_offset = {entry.offset: entry for entry in entries}
        assert 0x791BBA in by_offset
        entry = by_offset[0x791BBA]
        assert entry.expected == "Tu as collecté {COLOR}É{STR_VAR_3}%{COLOR}Á\\nde cellules."
        assert "Tu as collecté {COLOR}É{STR_VAR_3} pour cent{COLOR}Á\\nde cellules." in entry.forbidden

    def test_issue_46_mission_active_tab_stays_plural(self):
        # 0x1F5605C a fait l'aller-retour deux fois : #46 l'avait mis au féminin
        # pluriel, #116 l'a raccourci en « Active » à cause du suffixe partagé
        # « Missions » collé par le moteur, puis #114 a vidé ce suffixe sans
        # restaurer le pluriel. Le garde doit maintenant interdire le singulier.
        fr = [t for t in cti.discover_languages() if t[0] == "fr"]
        assert fr
        entries = cti.load_manifest(fr[0][2])
        by_offset = {entry.offset: entry for entry in entries}
        assert 0x1F5605C in by_offset
        entry = by_offset[0x1F5605C]
        assert entry.expected == "Actives"
        assert "Active" in entry.forbidden

    def test_main_returns_zero_on_real_repo(self):
        assert cti.main([]) == 0


class TestLastWinsResolution:
    """When an offset appears twice, the last occurrence wins (same as the build)."""

    def test_last_entry_wins(self, tmp_path: Path):
        target = tmp_path / "combined.txt"
        target.write_text(
            "0x720E74: Ville de Fallshore\n"  # old value (top of file)
            "0x720e74: Fallshore\n",          # live value (lowercase hex block)
            encoding="utf-8",
        )
        mapping, total = cti.load_last_wins(target)
        assert total == 2
        assert mapping[0x720E74] == "Fallshore"


class TestManifestValidation:
    def test_duplicate_offset_rejected(self, tmp_path: Path):
        manifest = _write_manifest(
            tmp_path / "m.yaml",
            'entries:\n  - {offset: "0x10", expected: "a"}\n  - {offset: "0x010", expected: "b"}\n',
        )
        with pytest.raises(ValueError, match="duplicate"):
            cti.load_manifest(manifest)

    def test_absent_and_expected_rejected(self, tmp_path: Path):
        manifest = _write_manifest(
            tmp_path / "m.yaml",
            'entries:\n  - {offset: "0x10", expected: "a", absent: true}\n',
        )
        with pytest.raises(ValueError, match="both"):
            cti.load_manifest(manifest)

    def test_missing_expected_rejected(self, tmp_path: Path):
        manifest = _write_manifest(tmp_path / "m.yaml", 'entries:\n  - {offset: "0x10", name: "x"}\n')
        with pytest.raises(ValueError, match="expected"):
            cti.load_manifest(manifest)

    def test_backslash_sequences_stay_literal(self, tmp_path: Path):
        # \n in single-quoted YAML must stay two characters (backslash + n),
        # exactly as written in combined_<lang>.txt.
        manifest = _write_manifest(
            tmp_path / "m.yaml",
            "entries:\n  - offset: \"0x10\"\n    expected: 'a\\nb'\n",
        )
        (entry,) = cti.load_manifest(manifest)
        assert entry.expected == "a\\nb"


class TestRegressionDetection:
    def _report(self, tmp_path: Path, combined_body: str) -> cti.IntegrityReport:
        combined = tmp_path / "combined_fr.txt"
        combined.write_text(combined_body, encoding="utf-8")
        manifest = _write_manifest(tmp_path / "protected.yaml", SIMPLE_MANIFEST)
        return cti.build_report(combined, manifest, "fr")

    def test_exact_match_passes(self, tmp_path: Path):
        assert self._report(tmp_path, "0x417396: Choisis Pokémon ou Sortir.\n").ok

    def test_forbidden_form_fails_with_specific_reason(self, tmp_path: Path):
        report = self._report(tmp_path, "0x417396: Choisis Pokémon ou Annuler.\n")
        assert not report.ok
        assert "forbidden" in report.failures[0].reason

    def test_any_drift_fails_even_if_not_forbidden(self, tmp_path: Path):
        # Exact-match is the contract: a stale snapshot with a *new* wrong
        # wording must still be caught.
        report = self._report(tmp_path, "0x417396: Choisis Pokémon ou Quitter.\n")
        assert not report.ok
        assert "does not match" in report.failures[0].reason

    def test_stale_duplicate_at_top_is_fine(self, tmp_path: Path):
        report = self._report(
            tmp_path,
            "0x417396: Choisis Pokémon ou Annuler.\n0x417396: Choisis Pokémon ou Sortir.\n",
        )
        assert report.ok

    def test_empty_translation_fails(self, tmp_path: Path):
        report = self._report(tmp_path, "0x417396:\n")
        assert not report.ok
        assert "empty" in report.failures[0].reason

    def test_missing_offset_fails(self, tmp_path: Path):
        report = self._report(tmp_path, "0x123456: Autre chose\n")
        assert not report.ok
        assert "absent" in report.failures[0].reason

    def test_must_stay_absent_violated_fails(self, tmp_path: Path):
        report = self._report(
            tmp_path,
            "0x417396: Choisis Pokémon ou Sortir.\n0xA4E047: Comment trier ?\n",
        )
        assert not report.ok
        assert "ABSENT" in report.failures[0].reason

    def test_main_exit_codes(self, tmp_path: Path):
        combined = tmp_path / "combined.txt"
        combined.write_text("0x417396: Choisis Pokémon ou Annuler.\n", encoding="utf-8")
        manifest = _write_manifest(tmp_path / "m.yaml", SIMPLE_MANIFEST)
        assert cti.main(["--file", str(combined), "--manifest", str(manifest)]) == 1
        assert cti.main(["--file", str(combined)]) == 2  # --manifest required


class TestFixMode:
    def _paths(self, tmp_path: Path, combined_body: str) -> tuple[Path, Path]:
        combined = tmp_path / "combined_fr.txt"
        combined.write_text(combined_body, encoding="utf-8")
        manifest = _write_manifest(tmp_path / "protected.yaml", SIMPLE_MANIFEST)
        return combined, manifest

    def test_fix_rewrites_last_entry_in_place(self, tmp_path: Path):
        combined, manifest = self._paths(
            tmp_path,
            "0x100: Autre ligne\n0x417396: Choisis Pokémon ou Annuler.\n0x200: Fin\n",
        )
        assert cti.main(["--file", str(combined), "--manifest", str(manifest), "--fix"]) == 0
        lines = combined.read_text(encoding="utf-8").splitlines()
        assert lines[1] == "0x417396: Choisis Pokémon ou Sortir."
        assert lines[0] == "0x100: Autre ligne" and lines[2] == "0x200: Fin"

    def test_fix_appends_missing_offset(self, tmp_path: Path):
        combined, manifest = self._paths(tmp_path, "0x100: Autre ligne\n")
        assert cti.main(["--file", str(combined), "--manifest", str(manifest), "--fix"]) == 0
        assert combined.read_text(encoding="utf-8").splitlines()[-1] == "0x417396: Choisis Pokémon ou Sortir."

    def test_fix_comments_out_must_stay_absent(self, tmp_path: Path):
        combined, manifest = self._paths(
            tmp_path,
            "0x417396: Choisis Pokémon ou Sortir.\n0xA4E047: Comment trier ?\n",
        )
        assert cti.main(["--file", str(combined), "--manifest", str(manifest), "--fix"]) == 0
        lines = combined.read_text(encoding="utf-8").splitlines()
        assert lines[1].startswith("#")
        assert "0xA4E047: Comment trier ?" in lines[1]
