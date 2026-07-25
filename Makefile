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
# Clean vanilla base — used by build-es, the generic multi-language driver
# (build-it/build-de/build-indie/build-lang) and all shared extraction/diff
# tooling. NOT used for build-fr — see FRENCH_ROM below.
ENGLISH_ROM := $(ROM_DIR)/englishrom.gba
SPANISH_ROM := $(ROM_DIR)/spanishrom.gba
# French-patched base (baked-in official French across move/item/Pokédex
# tables). build-fr is the ONLY consumer — its combined_fr.txt and dedicated
# patch scripts were tuned against this exact ROM's byte layout.
FRENCH_ROM := $(ROM_DIR)/patchedfrenchrom.gba

ROM_BASELINE := docs/roms_baseline.json
VERIFY_SCRIPT := scripts/verify_roms.py
EXTRACT_SCRIPT := src/extractors/pointer_text_extractor.py
DIFF_SCRIPT := src/analyzers/11_pointer_text_diff.py
BUILD_SCRIPT := src/translators/19_build_translated_rom_generic.py
VALIDATE_SCRIPT := src/validators/text_range_validator.py
TRILINGUAL_SCRIPT := src/translators/28_export_trilingual_csv.py
PATCH_FONT_FR_SCRIPT := languages/fr/patches/font.py
INLINE_FR_SCRIPT := scripts/apply_inline_overrides_fr.py
REPAIR_LZ77_SCRIPT := scripts/repair_stable_lz77_blocks.py
REPAIR_LOCALIZED_LZ77_SCRIPT := scripts/repair_localized_lz77_blocks.py
REPOINT_STALE_SCRIPT := scripts/repoint_stale_text_pointers.py
PATCH_RITUAL_SCRIPT := languages/fr/patches/legendary_ritual.py
PATCH_FIXED_NAMES_SCRIPT := languages/fr/patches/fixed_table_names.py
PATCH_ABILITY_NAMES_SCRIPT := languages/fr/patches/ability_names.py
PATCH_ITEM_NAMES_SCRIPT := languages/fr/patches/item_names.py
PATCH_TIME_FORMAT_SCRIPT := languages/fr/patches/time_format.py
PATCH_BATTLE_PREFIX_SCRIPT := languages/fr/patches/battle_prefix.py
PATCH_VERSION_SCRIPT := languages/fr/patches/version.py
PATCH_POKEDEX_FR_SCRIPT := languages/fr/patches/pokedex.py
PATCH_POKEDEX_METRICS_FR_SCRIPT := languages/fr/patches/pokedex_metrics.py
PATCH_POKEDEX_CATEGORIES_FR_SCRIPT := languages/fr/patches/pokedex_categories.py
PATCH_POKEDEX_CATEGORY_ORDER_FR_SCRIPT := languages/fr/patches/pokedex_category_order.py
PATCH_MOVE_DESC_FR_SCRIPT := languages/fr/patches/move_descriptions.py
PATCH_DUP_MOVE_DESC_FR_SCRIPT := languages/fr/patches/dup_move_descriptions.py
PATCH_TM_ITEM_DESC_FR_SCRIPT := languages/fr/patches/tm_item_descriptions.py
PATCH_GIVECS_GIFT_ITEM_FR_SCRIPT := languages/fr/patches/givecs_gift_item.py
PATCH_METEORITE_DIALOGUE_FR_SCRIPT := languages/fr/patches/meteorite_dialogue.py
PATCH_WORLDMAP_JUNCTION_FR_SCRIPT := languages/fr/patches/worldmap_junction_panels.py
PATCH_CUBE_TV_DIALOGUES_FR_SCRIPT := languages/fr/patches/cube_tv_dialogues.py
PATCH_CUBE_SORT_MENU_SCRIPT := languages/fr/patches/cube_sort_menu.py
PATCH_SUMMARY_LABELS_SCRIPT := languages/fr/patches/summary_labels.py
PATCH_SUMMARY_LV_LABELS_SCRIPT := languages/fr/patches/summary_lv_labels.py
PATCH_CFRU_TYPE_NAMES_SCRIPT := languages/fr/patches/cfru_type_names.py
PATCH_OPTIONS_FOOTER_SCRIPT := languages/fr/patches/options_footer.py
PATCH_STATUS_ABBREVS_SCRIPT := languages/fr/patches/status_abbrevs.py
PATCH_STATUS_BADGES_SCRIPT := languages/fr/patches/status_badges.py
PATCH_HP_LABELS_SCRIPT := languages/fr/patches/hp_labels.py
PATCH_PARTY_LV_LABEL_SCRIPT := languages/fr/patches/party_lv_label.py
PATCH_MON_ICON_REPAIR_SCRIPT := languages/fr/patches/mon_icon_repair.py
PATCH_PARTY_CANCEL_BUTTON_SCRIPT := languages/fr/patches/party_cancel_button.py
PATCH_PC_MOVE_LABELS_SCRIPT := languages/fr/patches/pc_move_labels.py
PATCH_WORLD_MAP_ACTION_LABELS_SCRIPT := languages/fr/patches/world_map_action_labels.py
PATCH_FLOOR_INDICATORS_FR_SCRIPT := languages/fr/patches/floor_indicators.py
PATCH_POKEDEX_STAT_LABELS_FR_SCRIPT := languages/fr/patches/pokedex_stat_labels.py
PATCH_TYPE_ICONS_SCRIPT := languages/fr/patches/type_icons.py
PATCH_DEXNAV_HEADERS_SCRIPT := languages/fr/patches/dexnav_headers.py
PATCH_SHOP_FR_SCRIPT := languages/fr/patches/shop.py
PATCH_MISSION_DESC_FR_SCRIPT := languages/fr/patches/mission_descriptions.py
PATCH_MISSION_TAB_LABELS_FR_SCRIPT := languages/fr/patches/mission_tab_labels.py
PATCH_ZONE_NAMES_FR_SCRIPT := languages/fr/patches/zone_names.py
PATCH_WORLDMAP_LABELS_FR_SCRIPT := languages/fr/patches/worldmap_labels.py
PATCH_TRAINER_CARD_DATE_FR_SCRIPT := languages/fr/patches/trainer_card_date.py
PATCH_MONEY_AMOUNT_ORDER_FR_SCRIPT := languages/fr/patches/money_amount_order.py
PATCH_TRAINER_CLASS_NAMES_FR_SCRIPT := languages/fr/patches/trainer_class_names.py
PATCH_GENDERED_BUFFERS_SCRIPT := languages/fr/patches/gendered_buffers.py
PATCH_BATTLE_STRING_TEMPLATES_SCRIPT := languages/fr/patches/battle_string_templates.py
PATCH_BATTLE_RECALL_STRINGS_SCRIPT := languages/fr/patches/battle_recall_strings.py
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
# Recursively-expanded (=, not :=): must be re-evaluated after ensure-fr-translation
# runs prepare-fr, otherwise a fresh checkout with no output/translation/ yet would
# freeze this to empty at parse time, before prepare-fr had a chance to create it.
FR_TRANSLATION = $(shell ls -t $(OUTPUT_DIR)/translation/[0-9]*_translation_ready.json 2>/dev/null | head -n 1)

ENGLISH_EXTRACT := $(EXTRACT_DIR)/englishrom_texts.json
SPANISH_EXTRACT := $(EXTRACT_DIR)/spanishrom_texts.json
FRENCH_EXTRACT := $(EXTRACT_DIR)/patchedfrenchrom_texts.json
DIFF_REPORT := $(DIFF_DIR)/pointer_text_differences.json
PAIRS_REPORT := $(DIFF_DIR)/pointer_translation_pairs.json
OFFSET_MAP := $(DIFF_DIR)/pointer_offset_map.json
SPANISH_BUILD := $(ROM_OUT_DIR)/GenedRom-es.gba

.DEFAULT_GOAL := pipeline

.PHONY: pipeline verify-roms extract extract-en extract-es extract-fr diff build-es build-fr verify-fr-determinism prepare-fr ensure-fr-translation validate-es trilingual-csv \
	build-it build-de build-indie build-lang build-all release-all langs \
	test test-python-fast test-python test-rom test-fr-rebuild check-translations test-vitest test-playwright test-all \
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

extract-fr: $(FRENCH_EXTRACT)

$(FRENCH_EXTRACT): $(FRENCH_ROM) $(EXTRACT_SCRIPT)
	@mkdir -p $(EXTRACT_DIR)
	@$(PYTHON) $(EXTRACT_SCRIPT) $(FRENCH_ROM) --output $(FRENCH_EXTRACT) --scan-all-pointers

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

## prepare-fr: generate translation_ready.json from combined_fr.txt + FR-base extraction.
## Required in CI where the trilingual CSV is not committed.  Run before build-fr.
prepare-fr: $(FRENCH_EXTRACT) $(PREPARE_FR_SCRIPT)
	@$(PYTHON) $(PREPARE_FR_SCRIPT) \
		--combined languages/fr/combined_fr.txt \
		--english $(FRENCH_EXTRACT) \
		--critical languages/fr/data/critical_strings_fr.txt \
		--english-rom $(FRENCH_ROM)

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

## ensure-fr-translation: auto-run prepare-fr when no translation_ready.json
## exists yet, when the latest one is empty (0 translations), or when it predates
## combined_fr.txt. This keeps `make build-fr` from silently rebuilding with stale
## menu/dialogue text after a source correction while preserving a newer JSON
## produced by the trilingual CSV route.
## prepare-fr is a lower-fidelity CI bypass (see its own header comment) —
## for a release build, generate the curated CSV first (apply_combined_fr.py
## --extend -> 09_csv_to_json_v2.py) so this fallback never triggers.
ensure-fr-translation: $(FRENCH_EXTRACT)
	@if [ -z "$(FR_TRANSLATION)" ]; then \
		echo "No translation_ready.json found — falling back to 'make prepare-fr' (CI bypass, see docs/20_TRANSLATION_PRESERVATION.md)..."; \
		$(MAKE) prepare-fr; \
	elif [ "$$($(PYTHON) -c "import json; d=json.load(open('$(FR_TRANSLATION)')); print(len(d.get('translations', [])))")" = "0" ]; then \
		echo "$(FR_TRANSLATION) has 0 translations — falling back to 'make prepare-fr' (CI bypass, see docs/20_TRANSLATION_PRESERVATION.md)..."; \
		$(MAKE) prepare-fr; \
	elif [ languages/fr/combined_fr.txt -nt "$(FR_TRANSLATION)" ]; then \
		echo "$(FR_TRANSLATION) predates combined_fr.txt — refreshing it with 'make prepare-fr'..."; \
		$(MAKE) prepare-fr; \
	fi

build-fr: check-translations-fr ensure-fr-translation $(FRENCH_EXTRACT) $(SPANISH_EXTRACT) $(BUILD_SCRIPT)
	@if [ -z "$(FR_TRANSLATION)" ]; then \
		echo "No translation_ready.json found in output/translation/"; \
		exit 1; \
	fi
	@mkdir -p $(ROM_OUT_DIR)
	@$(PYTHON) $(BUILD_SCRIPT) \
		--source $(FRENCH_ROM) \
		--translations $(FR_TRANSLATION) \
		--language french \
		--allow-relocate \
		--allow-fallback \
		--pointer-proof-rom $(SPANISH_ROM) \
		--output $(FR_BUILD)
	@$(PYTHON) $(PATCH_GENDERED_BUFFERS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_FONT_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_FIXED_NAMES_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_ABILITY_NAMES_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_ITEM_NAMES_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_TRAINER_CLASS_NAMES_FR_SCRIPT) --rom $(FR_BUILD) --combined languages/fr/combined_fr.txt
	@$(PYTHON) $(PATCH_TIME_FORMAT_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_BATTLE_PREFIX_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(INLINE_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(FRENCH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-texts $(SPANISH_EXTRACT) \
		--english-texts $(FRENCH_EXTRACT) \
		--translations $(FR_TRANSLATION)
	@$(PYTHON) $(REPAIR_LZ77_SCRIPT) \
		--target $(FR_BUILD) \
		--english $(FRENCH_ROM) \
		--spanish $(SPANISH_ROM)
	@$(PYTHON) $(REPAIR_LOCALIZED_LZ77_SCRIPT) \
		--target $(FR_BUILD) \
		--english $(FRENCH_ROM) \
		--spanish $(SPANISH_ROM) \
		--require-pointer
	@$(PYTHON) $(PATCH_SUMMARY_LABELS_SCRIPT) --rom $(FR_BUILD) --source $(FRENCH_ROM)
	@$(PYTHON) $(REPOINT_STALE_SCRIPT) \
		--target $(FR_BUILD) \
		--english-texts $(FRENCH_EXTRACT) \
		--translations $(FR_TRANSLATION) \
		--source $(FRENCH_ROM)
	@$(PYTHON) $(PATCH_RITUAL_SCRIPT) --rom $(FR_BUILD) --source $(FRENCH_ROM)
	@$(PYTHON) $(PATCH_VERSION_SCRIPT) --rom $(FR_BUILD) --build-number $(BUILD_NUMBER)
	@$(PYTHON) $(PATCH_POKEDEX_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(FRENCH_ROM) \
		--translations $(FR_TRANSLATION)
	@$(PYTHON) $(PATCH_POKEDEX_METRICS_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_POKEDEX_CATEGORIES_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_POKEDEX_CATEGORY_ORDER_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_MOVE_DESC_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(FRENCH_ROM) \
		--translations $(FR_TRANSLATION)
	@$(PYTHON) $(PATCH_DUP_MOVE_DESC_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--combined languages/fr/combined_fr.txt
	@$(PYTHON) $(PATCH_TM_ITEM_DESC_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_GIVECS_GIFT_ITEM_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(FRENCH_ROM)
	@$(PYTHON) $(PATCH_METEORITE_DIALOGUE_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(FRENCH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_WORLDMAP_JUNCTION_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(FRENCH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_CUBE_TV_DIALOGUES_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(FRENCH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_CFRU_TYPE_NAMES_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_OPTIONS_FOOTER_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_STATUS_ABBREVS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_CUBE_SORT_MENU_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_BATTLE_STRING_TEMPLATES_SCRIPT) --rom $(FR_BUILD) --source $(FRENCH_ROM)
	@$(PYTHON) $(PATCH_BATTLE_RECALL_STRINGS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_STATUS_BADGES_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_HP_LABELS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_PARTY_LV_LABEL_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_POKEDEX_STAT_LABELS_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_TYPE_ICONS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_DEXNAV_HEADERS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_SHOP_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_MISSION_DESC_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(FRENCH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_MISSION_TAB_LABELS_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_ZONE_NAMES_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(FRENCH_ROM) \
		--combined languages/fr/combined_fr.txt \
		--reference-rom $(SPANISH_ROM)
	@$(PYTHON) $(PATCH_WORLDMAP_LABELS_FR_SCRIPT) \
		--rom $(FR_BUILD) \
		--source $(FRENCH_ROM) \
		--combined languages/fr/combined_fr.txt
	@$(PYTHON) $(PATCH_TRAINER_CARD_DATE_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_MONEY_AMOUNT_ORDER_FR_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) languages/fr/patches/nature_names.py --rom $(FR_BUILD) --reference-rom $(SPANISH_ROM)
	@$(PYTHON) scripts/insert_sprite.py --rom $(FR_BUILD) --lang fr --sprite selection --bmp languages/fr/sprites/selection.bmp
	@$(PYTHON) scripts/insert_sprite.py --rom $(FR_BUILD) --lang fr --sprite start_menu_move_hint --bmp languages/fr/sprites/start_menu_move_hint.bmp
	@$(PYTHON) scripts/insert_sprite.py --rom $(FR_BUILD) --lang fr --sprite cube_sort_hint --bmp languages/fr/sprites/cube_sort_hint.bmp
	@$(PYTHON) $(PATCH_SUMMARY_LV_LABELS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_MON_ICON_REPAIR_SCRIPT) --rom $(FR_BUILD) --source $(FRENCH_ROM)
	@$(PYTHON) $(PATCH_PARTY_CANCEL_BUTTON_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_PC_MOVE_LABELS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_WORLD_MAP_ACTION_LABELS_SCRIPT) --rom $(FR_BUILD)
	@$(PYTHON) $(PATCH_FLOOR_INDICATORS_FR_SCRIPT) --rom $(FR_BUILD) --source $(ENGLISH_ROM)
	@echo "✓ FR ROM built — vérification des traductions de lieux..."
	@$(PYTHON) -m pytest tests/test_location_names_fr.py -q --tb=short
	@echo "✓ Vérification des noms de nature (pointeurs vivants)..."
	@$(PYTHON) -m pytest tests/test_nature_names_fr.py -q --tb=short
	@echo "✓ Vérification de l'écran info rencontre (pointeurs vivants)..."
	@$(PYTHON) -m pytest tests/test_encounter_info_fr.py -q --tb=short
	@$(MAKE) --no-print-directory test-fr-build-regressions

## Rebuild the dedicated FR ROM twice from the same inputs and compare every
## byte.  The temporary first artifact is deliberately outside output/ so no
## generated file can influence the second invocation or pollute the worktree.
verify-fr-determinism:
	@tmp_rom="$$(mktemp -t GenedRom-fr.XXXXXX)"; \
	trap 'rm -f "$$tmp_rom"' EXIT; \
	$(MAKE) --no-print-directory build-fr; \
	cp "$(FR_BUILD)" "$$tmp_rom"; \
	$(MAKE) --no-print-directory build-fr; \
	if ! cmp -s "$$tmp_rom" "$(FR_BUILD)"; then \
		echo "FR build is non-deterministic: differing byte offsets (first 20):"; \
		cmp -l "$$tmp_rom" "$(FR_BUILD)" | head -n 20; \
		exit 1; \
	fi; \
	echo "✓ FR build is byte-identical across consecutive rebuilds."

## --------------- Multi-language builds ---------------
# French keeps its dedicated byte-perfect recipe above (build-fr). Italian and
# German are driven generically from their languages/<code>/ descriptors.

build-it: check-translations-it
	@$(PYTHON) scripts/build_language.py it --build-number $(BUILD_NUMBER)

build-de: check-translations-de
	@$(PYTHON) scripts/build_language.py de --build-number $(BUILD_NUMBER)

build-indie: check-translations-indie
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
	@$(PYTHON) $(TRILINGUAL_SCRIPT) --auto-french-reference

## --------------- Test targets ---------------

test: test-python-fast

test-python-fast:
	@$(PYTHON) -m pytest tests/ -x --ignore=tests/benchmarks --ignore=tests/e2e \
		-m "not slow and not stress and not emulator and not rom"

test-python:
	@$(PYTHON) -m pytest tests/ -m "not emulator and not stress and not benchmark and not rom" -v

test-rom: verify-fr-determinism test-fr-rebuild
	@$(PYTHON) -m pytest tests/ -m rom -v

test-fr-rebuild:
	@$(PYTHON) -m pytest -q --tb=short \
		tests/e2e/test_ace_teamup_mechanic_fr.py \
		tests/e2e/test_dragon_cave_cutscene_fr.py \
		tests/e2e/test_east_borrius_sign_fr.py \
		tests/e2e/test_rival_battle_victory_line_fr.py \
		tests/e2e/es/test_extraction_coverage.py

test-fr-build-regressions:
	@$(PYTHON) -m pytest -q --tb=short \
		tests/e2e/fr/test_item_descriptions.py::TestItemDescriptions::test_repousse_dit_pas_pas_etapes \
		tests/e2e/fr/test_pc_selection_menu.py::TestPcSelectionMenuFrench::test_which_pc_question_is_french \
		tests/e2e/fr/test_pc_selection_menu.py::TestPcSelectionMenuFrench::test_prof_log_pc_entry_has_du \
		tests/test_patch_pc_move_labels_fr.py::TestBuiltRom::test_mail_move_to_bag \
		tests/unit/fr/test_world_map_action_labels.py::test_world_map_cancel_pointers_render_short_label \
		tests/unit/fr/test_floor_indicators_patch_fr.py::test_built_fr_rom_banner_routine_is_not_the_english_one

# Garde anti-régression des traductions (toutes langues) — source de vérité :
# languages/<lang>/protected_entries.yaml. Voir docs/20_TRANSLATION_PRESERVATION.md §7.
check-translations:
	@$(PYTHON) scripts/check_translation_integrity.py

check-translations-%:
	@$(PYTHON) scripts/check_translation_integrity.py --lang $*

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

hooks:
	@git config core.hooksPath .githooks
	@echo "✓ Hooks Git activés depuis .githooks/."

install: hooks
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
	@echo "    make test-fr-rebuild - Régressions FR/ES après reconstruction de ROM"
	@echo "    make test-vitest     - Vitest (emulator-web)"
	@echo "    make test-playwright - Playwright E2E"
	@echo "    make test-all        - test-python-fast + test-vitest + test-playwright"
	@echo ""
	@echo "  Outillage:"
	@echo "    make hooks              - Active le hook pré-commit versionné"
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
