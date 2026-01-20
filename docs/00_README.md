# GBA ROM Spanish Reproduction Pipeline

Ce projet vise a reproduire une ROM GBA espagnole a partir de la ROM anglaise originale, en suivant une pipeline logique et verifiable.

## Objectif

- Extraire les textes via tables de pointeurs (stable et deterministe).
- Comparer EN/ES pour produire un mapping des offsets.
- Reconstruire la ROM ES en copiant les bytes de reference.
- Valider les ranges texte byte-par-byte.

## Entrees attendues

- `input/roms/englishrom.gba`
- `input/roms/spanishrom.gba`

## Pipeline (Makefile)

```bash
make pipeline
```

Cela execute:
1. Verification des ROMs (`scripts/verify_roms.py`).
2. Extraction pointer-based (`src/extractors/pointer_text_extractor.py`).
3. Diff + offset map (`src/analyzers/11_pointer_text_diff.py`).
4. Build generique (`src/translators/19_build_translated_rom_generic.py`).
5. Validation byte-level (`src/validators/text_range_validator.py`).

## Sorties principales

- `output/extracted/extracted_texts/englishrom_texts.json`
- `output/extracted/extracted_texts/spanishrom_texts.json`
- `output/differences/pointer_text_differences.json`
- `output/differences/pointer_translation_pairs.json`
- `output/differences/pointer_offset_map.json`
- `output/roms/spanishrom_copy_build.gba`
- `output/reports/*_text_range_validation.json`

## Validation

Le validateur compare les ranges de texte de la ROM construite avec la ROM espagnole de reference (mapping d offsets). Il reporte les mismatches avec les bytes attendus et le texte decode pour diagnostic.

## Notes sur les scripts legacy

Les anciens scripts de traduction restent disponibles dans `scripts/legacy/` pour reference. Le pipeline courant est celui decrit ci-dessus.
