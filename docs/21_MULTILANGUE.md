# Multi-language builds (FR / IT / DE …)

Pokémon Unbound can now be translated into several languages from the same
toolkit. The pipeline is split into a **shared, language-agnostic core** and a
small amount of **per-language data**. Duplication is kept to the minimum
strictly required by each language.

> **French is the reference and stays byte-perfect.** It keeps its dedicated,
> hand-tuned recipe (`make build-fr`) and is *never* rerouted through the
> generic driver. Adding Italian or German cannot change a single byte of the
> French ROM.

## The `languages/` registry

Every target language is declared by one descriptor:

```
languages/
  fr/lang.yaml                 # French — build: dedicated (combined_fr.txt at repo root)
  it/lang.yaml                 # Italian — build: generic
  it/combined_it.txt           #   translations  <offset_hex>: <text>
  de/lang.yaml                 # German — build: generic
  de/combined_de.txt
  indie/lang.yaml              # Indie — build: generic (reuses the FR font)
  indie/combined_indie.txt
```

`lang.yaml` is the single source of truth read by the Makefile, the build
driver and the test-suite. Key fields:

| field             | meaning                                                              |
|-------------------|---------------------------------------------------------------------|
| `code`            | short code, must equal the folder name (`fr`, `it`, `de`)           |
| `name` / `native_name` | display names                                                  |
| `builder_language`| value passed to the generic ROM builder `--language`               |
| `status`          | `complete` or `in_progress`                                         |
| `build`           | `dedicated` (FR) or `generic` (everything else)                    |
| `combined`        | path to the `combined_<code>.txt` translation file                 |
| `critical`        | optional always-win override file                                  |
| `output_rom`      | `GenedRom-<code>.gba`                                               |
| `version_label`   | shown on the NOT-FOR-SALE screen                                   |
| `font_glyphs`     | accented glyphs the language needs                                 |
| `status_abbrev`   | in-game status abbreviations (poison/burn/freeze/paralysis/sleep/faint) |
| `patches`         | ordered post-build patch steps                                    |

Load it from Python with:

```python
from src.i18n import load_registry
registry = load_registry()
cfg = registry.get("it")
```

## Building

```bash
make langs           # list registered languages
make build-fr        # French — dedicated, byte-perfect recipe (unchanged)
make build-it        # Italian — generic driver
make build-de        # German — generic driver
make build-indie     # Indie — generic driver (reuses the FR font)
make build-lang LANG_CODE=it   # any generic language
make build-all       # FR + IT + DE + Indie
make release-all     # build every registered language + package output/release/
```

`release-all` writes, per language, the full `.gba`, a `.zip`, and global
`SHA256SUMS.txt` + `RELEASE_MANIFEST.json` to `output/release/`. A full ROM is
shipped (not an IPS patch) because Unbound is 32 MB and its translated text
lives above `0x1000000`, beyond the 24-bit IPS offset field.

## The generic pipeline (`scripts/build_language.py`)

For a `build: generic` language the driver runs:

1. ensure EN/ES pointer extractions exist;
2. `combined_<code>.txt` → trilingual CSV (`apply_combined_fr.py`, which is
   language-agnostic) → translation-ready JSON
   (`output/translation/<code>_translation_ready.json`);
3. generic ROM builder (`19_build_translated_rom_generic.py`,
   `--allow-relocate --allow-fallback`);
4. the post-build patch steps from the descriptor (`font`, `inline`, …).

Offsets absent from `combined_<code>.txt` keep their English text, so a
partially-translated language still produces a bootable ROM.

## Adding a new language

1. `mkdir languages/<code>` and write `languages/<code>/lang.yaml`
   (copy `languages/it/lang.yaml` as a template).
2. Create `languages/<code>/combined_<code>.txt` and start translating, using
   the same `<offset_hex>: <text>` format as `combined_fr.txt`
   (`\n` line break, `\l` = `<0xFA>` scroll, `\p` = `<0xFB>` clear).
3. `make build-<code>` (after adding a `build-<code>` alias, or
   `make build-lang LANG_CODE=<code>`).
4. `python3 -m pytest tests/test_language_registry.py` to validate the
   descriptor.

### Charmap / font caveats

* The shared CFRU charmap already encodes the French and Italian accented
  vowels (`à è é ì í î ò ó ù ú`, `ç`, `ß`, …).
* It does **not** yet contain `ä ö ü`. German therefore transliterates umlauts
  (`ae/oe/ue/ss`) until a dedicated DE charmap + font extension is added; the
  generic `font` step is disabled for German for the same reason.
* Italian reuses the French font glyphs, so its `font` step is enabled.
* Indie also reuses the French font (no `patch_font_indie.py`), so the `font`
  step falls back to `patch_font_fr.py` and the full FR accented set renders.
  It seeds with a near-empty `combined_indie.txt`, so an untranslated offset
  stays English and the build is bootable from day one.

## What stays per-language (necessary duplication)

* `combined_<code>.txt` — the translated strings (irreducibly per-language).
* `lang.yaml` — a few lines of metadata.
* Status abbreviations / font glyph set — small data in the descriptor.

Everything else — extraction, diffing, the ROM builder, the CSV/JSON chain, the
font patch, inline overrides — is shared code.
