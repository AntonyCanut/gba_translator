"""Tests pour scripts/clean_ellipsis_fr.py (nettoyage des points de suspension)."""
import pathlib
import re
from importlib.machinery import SourceFileLoader

_SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "clean_ellipsis_fr.py"
mod = SourceFileLoader("clean_ellipsis_fr", str(_SCRIPT)).load_module()


class TestCleanBody:
    def test_ascii_dots_become_ellipsis_char(self):
        # T1 : « ... » (3 octets) -> « … » (économie de 2 octets).
        assert mod.clean_body("Et...") == "Et…"
        assert mod.clean_body("pas ça...") == "pas ça…"
        assert mod.clean_body("....?") == "…?"

    def test_collapse_run_of_ellipses(self):
        # T2 : suite de 2+ ellipses -> une seule.
        assert mod.clean_body("… … … …") == "…"
        assert mod.clean_body("……") == "…"
        assert mod.clean_body("………") == "…"
        assert mod.clean_body("… … … … … …") == "…"

    def test_collapse_keeps_surrounding_words(self):
        assert mod.clean_body("… … …Ouah !") == "…Ouah !"
        assert mod.clean_body("Dehors…… Dehors……") == "Dehors… Dehors…"

    def test_single_ellipsis_is_preserved(self):
        # Une ellipsis isolée sert le dialogue -> intacte.
        assert mod.clean_body("Non…") == "Non…"
        assert mod.clean_body("Eh bien… euh…") == "Eh bien… euh…"
        assert mod.clean_body("Trois… Deux… Un…") == "Trois… Deux… Un…"

    def test_cross_page_beats_preserved(self):
        # Les beats de pause sur des pages séparées ne sont PAS fusionnés.
        assert mod.clean_body(r"…\p…") == r"…\p…"
        assert mod.clean_body(r"\p………\p………\p") == r"\p…\p…\p"

    def test_control_codes_untouched(self):
        s = r"perd ¥{STR_VAR_1}…\p… … … …\p{PLAYER} s’évanouit !"
        assert mod.clean_body(s) == r"perd ¥{STR_VAR_1}…\p…\p{PLAYER} s’évanouit !"

    def test_never_grows(self):
        for s in ["Et...", "… … … …", "Dehors…… Dehors……", "Non…", r"…\p…"]:
            assert len(mod.clean_body(s)) <= len(s)


class TestTransformLine:
    def test_offset_prefix_preserved(self):
        line = "0x3FCC33: Et...\\l"
        assert mod.transform_line(line) == "0x3FCC33: Et…\\l"

    def test_line_without_ellipsis_unchanged(self):
        line = "0x028780: {B_ATK_NAME_WITH_PREFIX} est du même type"
        assert mod.transform_line(line) == line


class TestCombinedFrIsClean:
    """Garde-fou : après le nettoyage, combined_fr.txt ne contient plus ni
    « ... » ASCII ni rangées d'ellipses dans un même segment."""

    def test_no_residual_ascii_dots_or_runs(self):
        path = _SCRIPT.parent.parent / "combined_fr.txt"
        run = re.compile(r"…(?:[ \t]*…)+")
        ascii_dots = re.compile(r"\.{3,}")
        for line in path.read_text(encoding="utf-8").splitlines():
            body = line.split(":", 1)[1] if ":" in line else line
            assert not ascii_dots.search(body), f"ASCII '...' restant : {line[:80]}"
            assert not run.search(body), f"rangée d'ellipses restante : {line[:80]}"
