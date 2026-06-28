# Makefile for Spanish ROM reproduction (pointer-based pipeline)
#
# Usage:
#   make pipeline    - Verify ROMs, extract, diff, build, validate
#   make extract     - Extract pointer-based texts from both ROMs
#   make diff        - Build pointer diff + offset map
#   make build-es    - Build Spanish ROM from reference + offset map
#   make validate-es - Byte-level validation against Spanish ROM

PYTHON ?= python3
BUILD_NUMBER ?= 0

ROM_DIR := input/roms
ENGLISH_ROM := $(ROM_DIR)/englishrom.gba
SPANISH_ROM := $(ROM_DIR)/spanishrom.gba

ROM_BASELINE := docs/roms_baseline.json
VERIFY_SCRIPT := scripts/verify_roms.py
EXTRACT_SCRIPT := src/extractors/pointer_text_extractor.py
DIFF_SCRIPT := src/analyzers/11_pointer_text_diff.py
BUILD_SCRIPT := src/translators/19_build_translated_rom_generic.py
VALIDATE_SCRIPT := src/validators/text_range_validator.py
TRILINGUAL_SCRIPT := src/translators/28_export_trilingual_csv.py
PATCH_FONT_FR_SCRIPT := scripts/patch_font_fr.py
INLINE_FR_SCRIPT := scripts/apply_inline_overrides_fr.py
REPAIR_LZ77_SCRIPT := scripts/repair_stable_lz77_blocks.py
REPAIR_LOCALIZED_LZ77_SCRIPT := scripts/repair_localized_lz77_blocks.py
REPOINT_STALE_SCRIPT := scripts/repoint_stale_text_pointers.py
PATCH_RITUAL_SCRIPT := scripts/patch_legendary_ritual_fr.py
PATCH_FIXED_NAMES_SCRIPT := scripts/patch_fixed_table_names.py
PATCH_ITEM_NAMES_SCRIPT := scripts/patch_item_names_fr.py
PATCH_TIME_FORMAT_SCRIPT := scripts/patch_time_format_fr.py
PATCH_BATTLE_PREFIX_SCRIPT := scripts/patch_battle_prefix_fr.py
PATCH_VERSION_SCRIPT := scripts/patch_version_fr.py
PATCH_POKEDEX_FR_SCRIPT := scripts/patch_pokedex_fr.py
PATCH_POKEDEX_METRICS_FR_SCRIPT := scripts/patch_pokedex_metrics_fr.py
PATCH_POKEDEX_CATEGORIES_FR_SCRIPT := scripts/patch_pokedex_categories_fr.py
PATCH_POKEDEX_CATEGORY_ORDER_FR_SCRIPT := scripts/patch_pokedex_category_order_fr.py
PATCH_MOVE_DESC_FR_SCRIPT := scripts/patch_move_descriptions_fr.py
PATCH_DUP_MOVE_DESC_FR_SCRIPT := scripts/patch_dup_move_descriptions_fr.py
PATCH_TM_ITEM_DESC_FR_SCRIPT := scripts/patch_tm_item_descriptions_fr.py
PATCH_METEORITE_DIALOGUE_FR_SCRIPT := scripts/patch_meteorite_dialogue_fr.py
PATCH_WORLDMAP_JUNCTION_FR_SCRIPT := scripts/patch_worldmap_junction_panels_fr.py
PATCH_SUMMARY_LABELS_SCRIPT := scripts/patch_summary_labels_fr.py
PATCH_CFRU_TYPE_NAMES_SCRIPT := scripts/patch_cfru_type_names_fr.py
PATCH_STATUS_ABBREVS_SCRIPT := scripts/patch_status_abbrevs_fr.py
PATCH_STATUS_BADGES_SCRIPT := scripts/patch_status_badges_fr.py
PATCH_TYPE_ICONS_SCRIPT := scripts/patch_type_icons_fr.py
PATCH_SHOP_FR_SCRIPT := scripts/patch_shop_fr.py
PATCH_MISSION_DESC_FR_SCRIPT := scripts/patch_mission_descriptions_fr.py
PATCH_ZONE_NAMES_FR_SCRIPT := scripts/patch_zone_names_fr.py
PATCH_WORLDMAP_LABELS_FR_SCRIPT := scripts/patch_worldmap_labels_fr.py
PATCH_GENDERED_BUFFERS_SCRIPT := scripts/patch_gendered_buffers_fr.py
PATCH_BATTLE_STRING_TEMPLATES_SCRIPT := scripts/patch_battle_string_templates_fr.py
PATCH_BATTLE_RECALL_STRINGS_SCRIPT := scripts/patch_battle_recall_strings_fr.py
PREPARE_FR_SCRIPT := scripts/prepare_fr_json.py

OUTPUT_DIR := output
EXTRACT_DIR := $(OUTPUT_DIR)/extracted/extracted_texts
DIFF_DIR := $(OUTPUT_DIR)/differences
REPORT_DIR := $(OUTPUT_DIR)/reports
ROM_OUT_DIR := $(OUTPUT_DIR)/roms
FR_BUILD := $(ROM_OUT_DIR)/GenedRom-fr.gba
# Only date-prefixed JSONs are French. The generic multi-language driver writes
# <code>_translation_ready.json (e.g. it_/de_), which must NEVER be picked here —
# otherwise build-fr would inject another language and the FR ROM would change.
FR_TRANSLATION := $(shell ls -t $(OUTPUT_DIR)/translation/[0-9]*_translation_ready.json 2>/dev/null | head -n 1)

ENGLISH_EXTRACT := $(EXTRACT_DIR)/englishrom_texts.json
SPANISH_EXTRACT := $(EXTRACT_DIR)/spanishrom_texts.json
DIFF_REPORT := $(DIFF_DIR)/pointer_text_differences.json
PAIRS_REPORT := $(DIFF_DIR)/pointer_translation_pairs.json
OFFSET_MAP := $(DIFF_DIR)/pointer_offset_map.json
SPANISH_BUILD := $(ROM_OUT_DIR)/GenedRom-es.gba

.DEFAULT_GOAL := pipeline

.PHONY: pipeline verify-roms extract extract-en extract-es diff build-es build-fr prepare-fr validate-es trilingual-csv \
	build-it build-de build-indie build-lang build-all release-all langs \
	test test-python-fast test-python test-rom check-translations test-vitest test-playwright test-all \
	sync-charmap sync-charmap-check install install-playwright lint tickets report \
	clean help

pipeline: verify-roms extract diff build-es validate-es
	@echo "✓ Pipeline complete."

verify-roms:
	@$(PYTHON) $(VERIFY_SCRIPT) --baseline $(ROM_BASELINE)

extract: extract-en extract-es
	@echo "✓ Extraction complete."

extract-en: $(ENGLISH_EXTRACT)

extract-es: $(SPANISH_EXTRACT)

$(ENGLISH_EXTRACT): $(ENGLISH_ROM) $(EXTRACT_SCRIPT)
	@mkdir -p $(EXTRACT_DIR)
	@$(PYTHON) $(EXTRACT_SCRIPT) $(ENGLISH_ROM) --output $(ENGLISH_EXTRACT) --scan-all-pointers

$(SPANISH_EXTRACT): $(SPANISH_ROM) $(EXTRACT_SCRIPT)
	@mkdir -p $(EXTRACT_DIR)
	@$(PYTHON) $(EXTRACT_SCRIPT) $(SPANISH_ROM) --output $(SPANISH_EXTRACT) --scan-all-pointers

diff: $(DIFF_REPORT)
	@echo "✓ Pointer diff + offset map generated."

$(DIFF_REPORT): $(ENGLISH_EXTRACT) $(SPANISH_EXTRACT) $(DIFF_SCRIPT)
	@mkdir -p $(DIFF_DIR)
	@$(PYTHON) $(DIFF_SCRIPT) \
		--english $(ENGLISH_EXTRACT) \
		--spanish $(SPANISH_EXTRACT) \
		--diff-out $(DIFF_REPORT) \
		--pairs-out $(PAIRS_REPORT) \
		--map-out $(OFFSET_MAP)

## prepare-fr: generate translation_ready.json from combined_fr.txt + EN extraction.
## Required in CI where the trilingual CSV is not committed.  Run before build-fr.
prepare-fr: $(ENGLISH_EXTRACT) $(PREPARE_FR_SCRIPT)
	@$(PYTHON) $(PREPARE_FR_SCRIPT) \
		--combined languages/fr/combined_fr.txt \
		--english $(ENGLISH_EXTRACT) \
		--critical data/critical_strings_fr.txt \
		--english-rom $(ENGLISH_ROM)

build-es: $(OFFSET_MAP) $(BUILD_SCRIPT)
	@if [ ! -f "$(SPANISH_ROM)" ]; then \
		echo "Spanish ROM not found: $(SPANISH_ROM)"; \
		exit 1; \
	fi
	@mkdir -p $(ROM_OUT_DIR)
	@$(PYTHON) $(BUILD_SCRIPT) \
		--source $(ENGLISH_ROM) \
		--reference $(SPANISH_ROM) \
		--offset-map $(OFFSET_MAP) \
		--copy-reference-texts \
		--copy-pointer-tables \
		--copy-text-pointers \
		--copy-inline-texts \
		--language spanish \
		--output $(SPANISH_BUILD)

build-fr: $(ENGLISH_EXTRACT) $(SPANISH_EXTRACT) $(BUILD_SCRIPT)
	@if [ -z "$(FR_TRANSLATION)" ]; then \
		echo "No translation_ready.json found in output/translation/"; \
		exit 1; \
	fi
	@mkdir -p $(ROM_OUT_DIR)
	@$(PYTHON) $(BUILD_SCRIPT) \
		--source $(ENGLISH_ROM) \
		--translations $(FR_TRANSLATION) \
		--language french \
		--allow-relocate \
		--allow-fallback \
		--pointer-proof-rom $(SPANISH_ROM) \
		--output $(FR_BUILD)
	@$(PYTHON) $(PATCH_GENDERED_BUFFERS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_FONT_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_FIXED_NAMES_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_ITEM_NAMES_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_TIME_FORMAT_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_BATTLE_PREFIX_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(INLINE_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(ENGLISH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-texts $(SPANISH_EXTRACT) \
		--translations $(FR_TRANSLATION)
	@$(PYTHON) $(REPAIR_LZ77_SCRIPT) \
		--target $(FR_BUILD) \
		--english $(ENGLISH_ROM) \
		--spanish $(SPANISH_ROM)
	@$(PYTHON) $(REPAIR_LOCALIZED_LZ77_SCRIPT) \
		--target $(FR_BUILD) \
		--english $(ENGLISH_ROM) \
		--spanish $(SPANISH_ROM) \
		--require-pointer
	@$(PYTHON) $(PATCH_SUMMARY_LABELS_SCRIPT) --rom $(FR_BUILD) --source $(ENGLISH_ROM)
	@$(PYTHON) $(REPOINT_STALE_SCRIPT) \
		--target $(FR_BUILD) \
		--translations $(FR_TRANSLATION) \
		--source $(ENGLISH_ROM)
	@$(PYTHON) $(PATCH_RITUAL_SCRIPT) --rom $(FR_BUILD) --source $(ENGLISH_ROM)
	@$(PYTHON) $(PATCH_VERSION_SCRIPT) --rom $(FR_BUILD) --build-number $(BUILD_NUMBER)
	@$(PYTHON) $(PATCH_POKEDEX_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(ENGLISH_ROM) \
		--translations $(FR_TRANSLATION)
	@$(PYTHON) $(PATCH_POKEDEX_METRICS_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_POKEDEX_CATEGORIES_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_POKEDEX_CATEGORY_ORDER_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_MOVE_DESC_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(ENGLISH_ROM) \
		--translations $(FR_TRANSLATION)
	@$(PYTHON) $(PATCH_DUP_MOVE_DESC_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--combined languages/fr/combined_fr.txt
	@$(PYTHON) $(PATCH_TM_ITEM_DESC_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_METEORITE_DIALOGUE_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(ENGLISH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_WORLDMAP_JUNCTION_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(ENGLISH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_CFRU_TYPE_NAMES_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_STATUS_ABBREVS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_BATTLE_STRING_TEMPLATES_SCRIPT) --rom $(FR_BUILD) --source $(ENGLISH_ROM)
	@$(PYTHON) $(PATCH_BATTLE_RECALL_STRINGS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_STATUS_BADGES_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_TYPE_ICONS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_SHOP_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_MISSION_DESC_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(ENGLISH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_ZONE_NAMES_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(ENGLISH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_WORLDMAP_LABELS_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(ENGLISH_ROM) \
		--combined languages/fr/combined_fr.txt
	@echo "✓ FR ROM built — vérification des traductions de lieux..."
	@$(PYTHON) -m pytest tests/test_location_names_fr.py -q --tb=short

## --------------- Multi-language builds ---------------
# French keeps its dedicated byte-perfect recipe above (build-fr). Italian and
# German are driven generically from their languages/<code>/ descriptors.

build-it:
	@$(PYTHON) scripts/build_language.py it --build-number $(BUILD_NUMBER)

build-de:
	@$(PYTHON) scripts/build_language.py de --build-number $(BUILD_NUMBER)

build-indie:
	@$(PYTHON) scripts/build_language.py indie --build-number $(BUILD_NUMBER)

# Build any registered generic language: make build-lang LANG_CODE=it
build-lang:
	@if [ -z "$(LANG_CODE)" ]; then \
		echo "Usage: make build-lang LANG_CODE=<code>   (e.g. it, de)"; \
		echo "Registered languages:"; $(MAKE) --no-print-directory langs; \
		exit 1; \
	fi
	@$(PYTHON) scripts/build_language.py $(LANG_CODE) --build-number $(BUILD_NUMBER)

# Build every language: FR (dedicated) + IT + DE + Indie (generic).
build-all: build-fr build-it build-de build-indie
	@echo "✓ All languages built (FR, IT, DE, Indie)."

# Build all three and package them into output/release/ (ROMs + zips + checksums).
release-all: build-all
	@$(PYTHON) scripts/package_release.py --build-number $(BUILD_NUMBER)
	@echo "✓ Release ready in output/release/"

# List the languages declared in the languages/ registry.
langs:
	@$(PYTHON) -c "import sys; sys.path.insert(0, '.'); from src.i18n import load_registry; \
r = load_registry(); print('Registered languages:'); \
[print(f'  {c.code}  {c.name:9} {c.status:12} build={c.build:9} -> {c.output_rom}') for c in r.buildable()]"

validate-es: $(SPANISH_BUILD) $(VALIDATE_SCRIPT)
	@$(PYTHON) $(VALIDATE_SCRIPT) \
		--output-rom $(SPANISH_BUILD) \
		--reference-rom $(SPANISH_ROM) \
		--offset-map $(OFFSET_MAP) \
		--reference-texts $(SPANISH_EXTRACT) \
		--include-spanish-only

trilingual-csv:
	@$(PYTHON) $(TRILINGUAL_SCRIPT)

## --------------- Test targets ---------------

test: test-python-fast

test-python-fast:
	@$(PYTHON) -m pytest tests/ -x --ignore=tests/benchmarks --ignore=tests/e2e \
		-m "not slow and not stress and not emulator and not rom"

test-python:
	@$(PYTHON) -m pytest tests/ -m "not emulator and not stress and not benchmark and not rom" -v

test-rom:
	@$(PYTHON) -m pytest tests/ -m rom -v

# Garde anti-régression des traductions FR (labels carte) — voir docs/20_TRANSLATION_PRESERVATION.md
check-translations:
	@$(PYTHON) scripts/check_translation_integrity.py

test-vitest:
	@cd emulator-web && npx vitest run

test-playwright:
	@npx playwright test

test-all: test-python-fast test-vitest test-playwright

## --------------- Tooling targets ---------------

sync-charmap:
	@$(PYTHON) scripts/sync_charmap.py

sync-charmap-check:
	@$(PYTHON) scripts/sync_charmap.py --check

install:
	@pip install -e ".[dev]" && npm install && cd emulator-web && npm install

install-playwright:
	@npx playwright install chromium

lint:
	@$(PYTHON) -m pytest tests/ --collect-only -q

tickets:
	@$(PYTHON) scripts/list_tickets.py

report:
	@$(PYTHON) scripts/run_playwright_tests.py

clean:
	@rm -f $(ENGLISH_EXTRACT) $(SPANISH_EXTRACT) $(DIFF_REPORT) $(PAIRS_REPORT) $(OFFSET_MAP)
	@rm -f $(SPANISH_BUILD)
	@rm -f $(REPORT_DIR)/*_text_range_validation.json
	@echo "✓ Clean complete."

help:
	@echo "Make targets:"
	@echo ""
	@echo "  Pipeline:"
	@echo "    make pipeline        - Verify, extract, diff, build, validate"
	@echo "    make extract         - Pointer-based extraction EN+ES"
	@echo "    make diff            - Diff + offset map"
	@echo "    make build-es        - Build Spanish ROM"
	@echo "    make prepare-fr      - Generate translation JSON from combined_fr.txt (CI step)"
	@echo "    make build-fr        - Build French ROM (dedicated byte-perfect recipe)"
	@echo "    make validate-es     - Byte-level validation"
	@echo "    make trilingual-csv  - Export EN/ES/FR translation CSV"
	@echo ""
	@echo "  Multi-language (see docs/21_MULTILANGUE.md):"
	@echo "    make langs           - List languages declared in languages/"
	@echo "    make build-it        - Build Italian ROM (generic driver)"
	@echo "    make build-de        - Build German ROM (generic driver)"
	@echo "    make build-indie     - Build Indie ROM (generic driver)"
	@echo "    make build-lang LANG_CODE=it - Build any generic language"
	@echo "    make build-all       - Build FR + IT + DE + Indie"
	@echo "    make release-all     - Build all three and package output/release/"
	@echo ""
	@echo "  Tests:"
	@echo "    make test            - Alias for test-python-fast"
	@echo "    make test-python-fast - pytest rapide (unit, sans benchmarks/stress/e2e/emulator)"
	@echo "    make test-python     - pytest standard (sans emulator/stress/benchmark)"
	@echo "    make test-rom        - Vérification des traductions dans la ROM buildée (pytest -m rom)"
	@echo "    make test-vitest     - Vitest (emulator-web)"
	@echo "    make test-playwright - Playwright E2E"
	@echo "    make test-all        - test-python-fast + test-vitest + test-playwright"
	@echo ""
	@echo "  Outillage:"
	@echo "    make sync-charmap       - Sync charmap Python -> TypeScript"
	@echo "    make sync-charmap-check - Verify charmap sync (dry-run)"
	@echo "    make install            - Install Python + Node dependencies"
	@echo "    make install-playwright - Install Playwright browsers"
	@echo "    make lint               - Verify pytest collection"
	@echo "    make tickets            - List open tickets"
	@echo "    make report             - Generate Playwright test report"
	@echo ""
	@echo "  Misc:"
	@echo "    make clean           - Clean pipeline outputs"
