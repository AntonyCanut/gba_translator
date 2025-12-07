# Unbound – GBA ROM translation guide

## Quick prerequisites

- Install Python 3 and create a venv (already provided in `.venv`).
- Activate the venv if needed: `source .venv/bin/activate` (macOS/Linux).
- Place the source ROM `totranslate.gba` in this folder.
- Charmap files are provided (`charmap_firered.txt`).
- Scripts live in `scripts/`.

## Key scripts

- `extract_text.py`: extracts text from the GBA ROM using the charmap.  
  Defaults: input `totranslate.gba`, charmap `charmap_firered.txt`, output `extracted_text.txt`.

- `inject_translations.py`: reinjects a text file (`offset: text`) into the ROM.  
  Handles relocation of long strings into free space and updates pointers. Options:
  - `--text <file>`: translation file (e.g., `extracted_text_fr.txt` or `partial_translated_fr.txt`).
  - `--out <rom>`: output ROM (e.g., `totranslate_fr.gba`).
  - `--use-holes` + `--free-map rom_usage.txt`: use only free 0xFF blocks listed by `dump_rom_usage.py`.
  - `--no-reuse-old-space`: skip reusing freed locations (by default they are reused).

- `dump_rom_usage.py`: maps free/used areas in the ROM (runs of 0xFF) and writes `rom_usage.txt`.

## Dependencies

Python 3.x standard libs are enough for the scripts above.

For automated translation (not required in the main flow):  
`translate_chunks_batch.py` uses `deep_translator` and `requests` (and downloads Pokémon names from the veekun repo).

## Useful commands

1) Extract ROM text (to edit/translate):
```
.venv/bin/python3 scripts/extract_text.py --rom totranslate.gba --charmap charmap_firered.txt --out extracted_text.txt
```

2) Map free space (run once):
```
.venv/bin/python3 scripts/dump_rom_usage.py --rom totranslate.gba --out rom_usage.txt
```

3) Prepare a translation file:
   - Copy `extracted_text.txt` to `extracted_text_fr.txt`.
   - Translate the right side of each line (after `: `) while keeping markers (`\n`, `\p`, `\l`, `{STR_VAR_x}`, `{COLOR}`, etc.).
   - Keep any lines that must stay in English as-is.

### Simple `make` flow

- `make extract`: extract text, split into 250-line chunks under `origin_chuncks/`, copy to `fr_chunks/` if empty, and generate `rom_usage.txt`.
- `make build-fr`: stitch chunks from `fr_chunks/` into `combined_fr.txt`, then inject into `totranslate_fr.gba` using free space from `rom_usage.txt`.

4) Injection example (partial/stable):
```
.venv/bin/python3 scripts/inject_translations.py \
  --text partial_translated_fr.txt \
  --out totranslate_partial_fr.gba \
  --use-holes \
  --free-map rom_usage.txt
```

5) Injection complète (si besoin de tout reloger) :
```
.venv/bin/python3 scripts/inject_translations.py \
  --text extracted_text_fr.txt \
  --out totranslate_fr.gba \
  --use-holes \
  --free-map rom_usage.txt
```

6) Tester la ROM générée (`totranslate_fr.gba` ou `totranslate_partial_fr.gba`) dans un émulateur GBA.

## Format du fichier de texte

Chaque ligne est `offset_hex: texte` (ex. `0x1F11888: Bonjour...\p...`).  
Les marqueurs `\n`, `\p`, `\l`, `{STR_VAR_x}`, `{COLOR}` doivent rester intacts.  
L’injecteur reloge uniquement quand le texte encodé ne tient pas à l’offset d’origine.

## Conseils pour éviter les crashs

- Ne modifiez pas les offsets : seule la partie texte après `: ` doit changer.
- Gardez les blocs sensibles en place si une scène plante (laisser en anglais ou raccourcir pour tenir sans relogement).
- Utilisez `--use-holes` + `--free-map rom_usage.txt` pour éviter d’écrire dans des zones critiques.
- Si un texte est trop long, raccourcissez-le (abréviations) plutôt que de supprimer des marqueurs.
