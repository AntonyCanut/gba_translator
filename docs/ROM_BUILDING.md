# ROM Building - Spanish Reproduction Pipeline

## Overview

Le builder generique reconstruit une ROM cible a partir d une ROM source et d un mapping d offsets. Il supporte trois strategies:

- COPY: copie directe des bytes depuis la ROM de reference (fidelite maximale)
- TRANSLATE: reinsertion depuis un JSON de traductions
- HYBRID: copie + ajustements locaux

Le script utilise un encodage Pokemon partage et respecte la longueur exacte des bytes quand la reference est connue.

## Script principal

`src/translators/19_build_translated_rom_generic.py`

## Usage (reproduction espagnole)

```bash
python3 src/translators/19_build_translated_rom_generic.py \
  --source input/roms/englishrom.gba \
  --reference input/roms/spanishrom.gba \
  --offset-map output/differences/pointer_offset_map.json \
  --copy-reference-texts \
  --copy-pointer-tables \
  --copy-text-pointers \
  --copy-inline-texts \
  --language spanish \
  --output output/roms/spanishrom_copy_build.gba
```

## Usage (traductions JSON)

```bash
python3 src/translators/19_build_translated_rom_generic.py \
  --source input/roms/englishrom.gba \
  --translations output/translation/french_texts.json \
  --language french \
  --output output/roms/french_build.gba
```

## Options utiles

- `--offset-map`: mapping EN/ES pour textes deplaces
- `--allow-truncate`: autoriser la troncature si un texte depasse la longueur max
- `--copy-reference-texts`: copie tous les textes de reference a leurs offsets
- `--copy-pointer-tables`: copie les tables de pointeurs texte depuis la reference
- `--copy-text-pointers`: copie les pointeurs texte (alignes ou non) depuis la reference
- `--copy-inline-texts`: copie les textes sans pointeur si alignes entre ROMs

## Validation recommande

```bash
python3 src/validators/text_range_validator.py \
  --output-rom output/roms/spanishrom_copy_build.gba \
  --reference-rom input/roms/spanishrom.gba \
  --offset-map output/differences/pointer_offset_map.json \
  --reference-texts output/extracted/extracted_texts/spanishrom_texts.json
```

## Notes

- Le JSON `output/differences/pointer_translation_pairs.json` contient les paires EN/ES avec bytes bruts.
- Les anciens scripts de build sont conserves pour reference mais ne sont plus dans le workflow canonique.
