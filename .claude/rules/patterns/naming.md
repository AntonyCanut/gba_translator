# Conventions de nommage

| Élément | Convention | Exemple réel |
|---------|-----------|--------------|
| Scripts d'étape | `NN_description.py` numéroté par ordre d'exécution | `11_pointer_text_diff.py`, `19_build_translated_rom_generic.py` |
| Modules core | `snake_case` descriptif, non numéroté | `rom_reader.py`, `text_codec.py`, `padding_detector.py`, `dialogue_linewrap.py` |
| Scripts outils/patchs | `verbe_objet[_lang].py` | `patch_time_format_fr.py`, `repair_stable_lz77_blocks.py`, `sync_charmap.py` |
| Documentation `docs/` | `NN_NOM.md` numéroté par importance | `00_README.md`, `02_TECHNICAL.md`, `19_DIALOGUE_DISPLAY_FIXES.md` |
| Classes | `PascalCase` | `ROMReader`, `TextEncoder`, `PaddingDetector`, `SmartReinserter`, `ROMTranslationManager` |
| Fonctions / méthodes | `snake_case` | `read_pointer()`, `detect_padding()`, `encode_pokemon_text()`, `rewrap_multiline()` |
| Constantes | `UPPER_SNAKE_CASE` | `GBA_ROM_BASE = 0x08000000`, `POKEMON_TERMINATOR = 0xFF`, `POKEMON_TABLE` |
| Artefacts générés | `YYYY-MM-DD_description.ext` dans `output/` | `2026-01-13_englishrom_texts.json` |
| ROMs de sortie | `GenedRom-<lang>.gba` | `GenedRom-fr.gba`, `GenedRom-es.gba` |

## Règles

- Les scripts dans `docs/recaps/` peuvent être non numérotés (seule exception).
- Pas de fichier `.py` ni markdown de travail à la racine.
- Identifiants en anglais (`snake_case`/`PascalCase`) ; docstrings et commentaires en
  français.
- Offsets/octets toujours en hexadécimal minuscule préfixé `0x`.
