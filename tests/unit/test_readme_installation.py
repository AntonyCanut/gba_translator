"""Gardes de régression des instructions d'installation du README."""

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
ROM_NAME = "1636 - Pokemon Fire Red (U)(Squirrels).gba"
HACKDEX_URL = "https://www.hackdex.app/hack/pokemon-unbound"
FRENCH_PATCH_URL = (
    "https://github.com/AntonyKervazoCanut/gba_translator/releases/download/"
    "latest/pokemon_unbound_fr.bps"
)
ROM_PATCHER_URL = "https://www.marcrobledo.com/RomPatcher.js/"


def _installation_text() -> str:
    """Retourne uniquement la section d'installation multilingue."""
    readme = README.read_text(encoding="utf-8")
    return readme.split("## Install the French patch\n", maxsplit=1)[1].split(
        "\n## ", maxsplit=1
    )[0]


def _language_text(installation: str, heading: str) -> str:
    """Retourne les instructions placées sous un intertitre de langue."""
    return installation.split(f"### {heading}\n", maxsplit=1)[1].split(
        "\n### ", maxsplit=1
    )[0]


def _step_text(language: str, step: int) -> str:
    """Retourne une étape numérotée d'un bloc de langue."""
    text = language.split(f"\n{step}. ", maxsplit=1)[1]
    if step < 3:
        return text.split(f"\n{step + 1}. ", maxsplit=1)[0]
    return text


def test_readme_installation_has_exactly_the_natural_language_headings() -> None:
    """La pseudo-langue Indie ne doit pas recevoir une traduction artificielle."""
    headings = re.findall(r"^### (.+)$", _installation_text(), flags=re.MULTILINE)

    assert headings == ["English", "Français", "Italiano", "Deutsch", "Español"]


@pytest.mark.parametrize(
    (
        "heading",
        "obtain_action",
        "warning",
        "unbound_action",
        "english_rom_result",
        "french_patch_action",
        "english_rom_input",
        "download_action",
        "open_patcher_action",
    ),
    [
        (
            "English",
            "Obtain the ROM",
            "Any other version will not work.",
            "Apply the Pokémon Unbound 2.1.1.1 patch",
            "At this point, you have the English Pokémon Unbound ROM.",
            "Apply the French patch",
            "English Pokémon Unbound ROM",
            "Download the [French BPS patch]",
            "Open [Rom Patcher JS]",
        ),
        (
            "Français",
            "Procurez-vous la ROM",
            "Toute autre version ne fonctionnera pas.",
            "Appliquez le patch Pokémon Unbound 2.1.1.1",
            "À ce stade, vous disposez de la ROM Pokémon Unbound en anglais.",
            "Appliquez le patch français",
            "ROM Pokémon Unbound en anglais",
            "Téléchargez le [patch BPS français]",
            "Ouvrez [Rom Patcher JS]",
        ),
        (
            "Italiano",
            "Procurati la ROM",
            "Qualsiasi altra versione non funzionerà.",
            "Applica la patch Pokémon Unbound 2.1.1.1",
            "A questo punto avrai la ROM di Pokémon Unbound in inglese.",
            "Applica la patch francese",
            "ROM inglese di Pokémon Unbound",
            "Scarica la [patch BPS francese]",
            "Apri [Rom Patcher JS]",
        ),
        (
            "Deutsch",
            "Besorge dir die ROM",
            "Keine andere Version wird funktionieren.",
            "Wende den Pokémon-Unbound-Patch 2.1.1.1",
            "Nun hast du die englische Pokémon-Unbound-ROM.",
            "Wende den französischen Patch",
            "englische Pokémon-Unbound-ROM",
            "Lade den [französischen BPS-Patch]",
            "Öffne [Rom Patcher JS]",
        ),
        (
            "Español",
            "Consigue la ROM",
            "Ninguna otra versión funcionará.",
            "Aplica el parche Pokémon Unbound 2.1.1.1",
            "En este punto tendrás la ROM de Pokémon Unbound en inglés.",
            "Aplica el parche francés",
            "ROM inglesa de Pokémon Unbound",
            "Descarga el [parche BPS francés]",
            "Abre [Rom Patcher JS]",
        ),
    ],
)
def test_readme_documents_french_patch_installation_in_every_language(
    heading: str,
    obtain_action: str,
    warning: str,
    unbound_action: str,
    english_rom_result: str,
    french_patch_action: str,
    english_rom_input: str,
    download_action: str,
    open_patcher_action: str,
) -> None:
    """Chaque langue doit conserver les trois étapes et leurs prérequis exacts."""
    language = _language_text(_installation_text(), heading)
    obtain_rom = _step_text(language, 1)
    apply_unbound = _step_text(language, 2)
    apply_french = _step_text(language, 3)

    assert obtain_action in obtain_rom
    assert ROM_NAME in obtain_rom
    assert warning in obtain_rom
    assert unbound_action in apply_unbound
    assert ROM_NAME in apply_unbound
    assert HACKDEX_URL in apply_unbound
    assert english_rom_result in apply_unbound
    assert french_patch_action in apply_french
    assert english_rom_input in apply_french
    assert download_action in apply_french
    assert FRENCH_PATCH_URL in apply_french
    assert open_patcher_action in apply_french
    assert ROM_PATCHER_URL in apply_french
