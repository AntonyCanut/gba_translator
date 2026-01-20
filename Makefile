# Makefile for Spanish ROM reproduction (pointer-based pipeline)
#
# Usage:
#   make pipeline    - Verify ROMs, extract, diff, build, validate
#   make extract     - Extract pointer-based texts from both ROMs
#   make diff        - Build pointer diff + offset map
#   make build-es    - Build Spanish ROM from reference + offset map
#   make validate-es - Byte-level validation against Spanish ROM

PYTHON ?= python3

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

OUTPUT_DIR := output
EXTRACT_DIR := $(OUTPUT_DIR)/extracted/extracted_texts
DIFF_DIR := $(OUTPUT_DIR)/differences
REPORT_DIR := $(OUTPUT_DIR)/reports
ROM_OUT_DIR := $(OUTPUT_DIR)/roms
FR_BUILD := $(ROM_OUT_DIR)/GenedRom-fr.gba
FR_TRANSLATION := $(shell ls -t $(OUTPUT_DIR)/translation/*_translation_ready.json 2>/dev/null | head -n 1)

ENGLISH_EXTRACT := $(EXTRACT_DIR)/englishrom_texts.json
SPANISH_EXTRACT := $(EXTRACT_DIR)/spanishrom_texts.json
DIFF_REPORT := $(DIFF_DIR)/pointer_text_differences.json
PAIRS_REPORT := $(DIFF_DIR)/pointer_translation_pairs.json
OFFSET_MAP := $(DIFF_DIR)/pointer_offset_map.json
SPANISH_BUILD := $(ROM_OUT_DIR)/GenedRom-es.gba

.DEFAULT_GOAL := pipeline

.PHONY: pipeline verify-roms extract extract-en extract-es diff build-es build-fr validate-es trilingual-csv test clean help

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

build-fr: $(BUILD_SCRIPT)
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
		--output $(FR_BUILD)
	@$(PYTHON) $(PATCH_FONT_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(INLINE_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(ENGLISH_ROM) \
		--combined combined_fr.txt \
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

validate-es: $(SPANISH_BUILD) $(VALIDATE_SCRIPT)
	@$(PYTHON) $(VALIDATE_SCRIPT) \
		--output-rom $(SPANISH_BUILD) \
		--reference-rom $(SPANISH_ROM) \
		--offset-map $(OFFSET_MAP) \
		--reference-texts $(SPANISH_EXTRACT) \
		--include-spanish-only

trilingual-csv:
	@$(PYTHON) $(TRILINGUAL_SCRIPT)

test:
	@$(PYTHON) -m unittest

clean:
	@rm -f $(ENGLISH_EXTRACT) $(SPANISH_EXTRACT) $(DIFF_REPORT) $(PAIRS_REPORT) $(OFFSET_MAP)
	@rm -f $(SPANISH_BUILD)
	@rm -f $(REPORT_DIR)/*_text_range_validation.json
	@echo "✓ Clean complete."

help:
	@echo "Make targets:"
	@echo "  make pipeline    - Verify, extract, diff, build, validate"
	@echo "  make extract     - Pointer-based extraction EN+ES"
	@echo "  make diff        - Diff + offset map"
	@echo "  make build-es    - Build Spanish ROM"
	@echo "  make build-fr    - Build French ROM (latest translation_ready.json)"
	@echo "  make validate-es - Byte-level validation"
	@echo "  make trilingual-csv - Export EN/ES/FR translation CSV"
	@echo "  make test        - Run unit tests"
	@echo "  make clean       - Clean pipeline outputs"
