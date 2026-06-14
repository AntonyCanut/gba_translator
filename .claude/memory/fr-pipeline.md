---
name: fr-pipeline
description: Step-by-step FR ROM build pipeline, patch script order, output files, and data flow
metadata:
  type: project
---

**The FR pipeline produces `output/roms/GenedRom-fr.gba` from the English ROM + translation data.**

**Why:** Multiple post-processing scripts must run in order; skipping any produces a broken ROM.

**How to apply:** Always use `make build-fr` rather than invoking scripts individually. If debugging a specific step, reproduce the full sequence.

## Data flow

```
input/roms/englishrom.gba          (never modified)
input/roms/spanishrom.gba          (reference / pointer-proof)
output/translation/*_translation_ready.json  (input to build engine)
combined_fr.txt                    (inline overrides, 2 MB)
    ↓
make build-fr
    ↓
output/roms/GenedRom-fr.gba        (final French ROM)
```

## Build-fr step sequence

1. **`19_build_translated_rom_generic.py`** (`src/translators/`)
   - Reads English ROM, applies translations from `translation_ready.json`
   - Handles text relocation (--allow-relocate) and fallback (--allow-fallback)
   - Uses Spanish ROM as pointer-proof reference (`--pointer-proof-rom`)
   - Outputs initial `GenedRom-fr.gba`

2. **`patch_font_fr.py`** (`scripts/`)
   - Patches the ROM font table to add FR-specific glyph mappings
   - Must run before any text injection that uses FR glyphs

3. **`patch_fixed_table_names.py`** (`scripts/`)
   - Patches hardcoded fixed-table strings: city/route names, NPC names
   - Uses entries from `combined_fr.txt` filtered to fixed-table offsets

4. **`patch_time_format_fr.py`** (`scripts/`)
   - Patches Thumb ASM code for date/time: DD/MM/YYYY, 24h, Dim..Sam, "Jamais"
   - Post-build Thumb code patch — NOT text injection

5. **`apply_inline_overrides_fr.py`** (`scripts/`)
   - Injects non-pointer inline text overrides from `combined_fr.txt`
   - Needs reference text data from Spanish extraction

6. **`repair_stable_lz77_blocks.py`** (`scripts/`)
   - Restores LZ77-compressed image blocks that regressed during injection

7. **`repair_localized_lz77_blocks.py`** (`scripts/`)
   - Restores LZ77 blocks that contain localized (translated) image text
   - Only repairs blocks with a valid pointer (--require-pointer)

8. **`repoint_stale_text_pointers.py`** (`scripts/`)
   - Updates any pointers still pointing to old addresses after relocation

## Translation data sources

| Source | Contents | Format |
|---|---|---|
| `combined_fr.txt` | ~9k entries, offset→FR text | plain text, one entry per line |
| `output/translation/*_translation_ready.json` | structured translation map | JSON |
| `output/extracted/extracted_texts/` | EN + ES text corpora | JSON |
| `output/differences/pointer_offset_map.json` | EN→ES offset map | JSON |

## Validation

After `make build-fr`, validate with:
```bash
python3 scripts/audit_translation_fr.py     # GOOD/ACCEPTABLE/BAD quality
python3 scripts/verify_roms.py --baseline docs/roms_baseline.json
make test-playwright                          # emulator gameplay verification
```

**Links:** [[project-overview]] [[commands]] [[gotchas]] [[domain-glossary]]
