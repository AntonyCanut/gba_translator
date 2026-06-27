# Pokémon Unbound — Multi-language ROM Translation Toolkit

Translate Pokémon Unbound (CFRU/BPRE01) from English into several languages from
one toolkit. The Spanish reproduction below is the original reverse-engineering
foundation; on top of it the project now builds **French** (complete,
byte-perfect), **Italian** and **German** (in progress).

## Languages

```bash
make langs           # list languages declared in languages/
make build-fr        # French — dedicated, byte-perfect recipe
make build-it        # Italian — generic driver
make build-de        # German — generic driver
make build-all       # build FR + IT + DE
make release-all     # build all three + package output/release/ (ROMs, zips, checksums)
```

Each language is declared by a small descriptor in `languages/<code>/lang.yaml`
with its translations in `languages/<code>/combined_<code>.txt` (French keeps
`combined_fr.txt` at the repo root). See **[docs/21_MULTILANGUE.md](docs/21_MULTILANGUE.md)**
for the full guide, including how to add a new language.

> French is the reference translation and stays byte-perfect: it has its own
> dedicated recipe and is never rerouted through the generic driver.

## Quick start (Spanish reproduction foundation)

1. Drop ROMs here:
   - `input/roms/englishrom.gba`
   - `input/roms/spanishrom.gba`
2. Run the pipeline:
   ```bash
   make pipeline
   ```
3. Check outputs:
   - `output/roms/spanishrom_copy_build.gba`
   - `output/reports/*_text_range_validation.json`

## Pipeline overview

The canonical workflow uses pointer-based extraction and an offset map:

1. Verify ROMs against baseline metadata.
2. Extract pointer-based texts from both ROMs.
3. Diff texts and build an offset map.
4. Build the Spanish ROM (copy raw bytes from reference).
5. Validate text ranges byte-for-byte.

## Manual commands (no Makefile)

```bash
python3 scripts/verify_roms.py --baseline docs/roms_baseline.json

python3 src/extractors/pointer_text_extractor.py \
  input/roms/englishrom.gba \
  --output output/extracted/extracted_texts/englishrom_texts.json

python3 src/extractors/pointer_text_extractor.py \
  input/roms/spanishrom.gba \
  --output output/extracted/extracted_texts/spanishrom_texts.json

python3 src/analyzers/11_pointer_text_diff.py \
  --english output/extracted/extracted_texts/englishrom_texts.json \
  --spanish output/extracted/extracted_texts/spanishrom_texts.json \
  --diff-out output/differences/pointer_text_differences.json \
  --pairs-out output/differences/pointer_translation_pairs.json \
  --map-out output/differences/pointer_offset_map.json

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

python3 src/validators/text_range_validator.py \
  --output-rom output/roms/spanishrom_copy_build.gba \
  --reference-rom input/roms/spanishrom.gba \
  --offset-map output/differences/pointer_offset_map.json \
  --reference-texts output/extracted/extracted_texts/spanishrom_texts.json
```

## Outputs

- Pointer extraction: `output/extracted/extracted_texts/*_texts.json`
- Diff + mapping: `output/differences/pointer_text_differences.json`, `output/differences/pointer_translation_pairs.json`, `output/differences/pointer_offset_map.json`
- Built ROM: `output/roms/spanishrom_copy_build.gba`
- Validation report: `output/reports/*_text_range_validation.json`

## Documentation

- Pipeline details: `docs/00_README.md`
- ROM sources and baseline: `docs/ROM_SOURCES.md`, `docs/roms_baseline.json`
- Generic builder notes: `docs/ROM_BUILDING.md`

## Legacy

Older translation pipeline scripts are kept for reference only under `scripts/legacy/` and the numbered docs. The Makefile and pipeline above are the supported entry points.
