# Style Python

Cible : **Python 3.11+**. Une seule dépendance runtime tierce historique (`pyyaml`) ;
le reste est stdlib. Garde-le ainsi — pas de nouvelle dépendance sans nécessité.

## Type hints

- Type hints **partout** sur les signatures publiques (args + retour).
- Utilise `from __future__ import annotations` ou les génériques natifs (`list[int]`,
  `dict[str, int]`) ; `typing.Dict`/`Optional` reste accepté car présent dans le code
  existant (`src/core/text_codec.py`).

```python
# src/core/text_codec.py — style réel
ASCII_TABLE: Dict[str, int] = {chr(i): i for i in range(32, 127)}

def read_pointer(self, offset: int) -> int:
    """Lit un pointeur 32-bit little-endian à l'offset donné."""
```

## Docstrings (obligatoires sur classes/méthodes publiques)

Format Google, en **français**, avec `Args` / `Returns` / `Example` quand pertinent
(voir `project-rules.md` §Documentation Code).

```python
def detect_padding(rom: ROMReader, offset: int, length: int) -> int:
    """Détecte le padding disponible après un texte.

    Args:
        rom: Instance de lecteur ROM.
        offset: Offset du texte dans la ROM.
        length: Longueur du texte original.

    Returns:
        Nombre de bytes de padding disponibles (0x00/0xFF).
    """
```

## Orienté objet, pas procédural

- Tout code réutilisable vit dans `src/core/` sous forme de **classes** (`ROMReader`,
  `TextEncoder`/`TextDecoder`, `PaddingDetector`, `SmartReinserter`,
  `ROMTranslationManager`…). Les scripts les importent, ils ne ré-implémentent rien.
- Charge la ROM **une fois**, réutilise les instances, mets en cache les calculs
  répétés. Voir `architecture.md` §Performance.

## Style général

- Indentation 4 espaces, `snake_case` pour fonctions/variables, `PascalCase` pour
  classes, `UPPER_SNAKE_CASE` pour constantes (`GBA_ROM_BASE = 0x08000000`).
- Chemins via `pathlib.Path`, jamais de concaténation de chaînes.
- Octets et offsets en **hexadécimal** (`0x1F00000`), jamais en décimal magique.
- f-strings pour le formatage ; pas de `%`/`.format()` dans le code neuf.
- Commentaire = **pourquoi**, pas **quoi** (le code dit déjà quoi).
- `ruff check` doit passer (voir `tooling.md`) ; pas de formateur imposé, mais respecte
  le style PEP 8 que ruff valide.
