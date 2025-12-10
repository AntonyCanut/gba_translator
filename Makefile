.PHONY: extract build-fr clean venv

# Utilise le venv s'il existe, sinon python3 du système
PY := $(shell if [ -x .venv/bin/python3 ]; then echo .venv/bin/python3; else command -v python3; fi)
ROM := totranslate.gba
CHARMAP := charmap_firered.txt
EXTRACTED := extracted_text.txt
ROM_USAGE := rom_usage.txt
CHUNK_DIR := origin_chuncks
FR_CHUNK_DIR := fr_chunks
COMBINED_FR := combined_fr.txt
OUT_FR := totranslate_fr.gba

venv:
	@test -x .venv/bin/python3 || (python3 -m venv .venv && .venv/bin/pip install -r requirements.txt >/dev/null 2>&1 || true)

extract:
	@mkdir -p $(CHUNK_DIR) $(FR_CHUNK_DIR)
	@$(PY) scripts/extract_text.py --rom $(ROM) --charmap $(CHARMAP) --output extracted_full.txt
	@$(PY) scripts/filter_by_pointers.py --input extracted_full.txt --rom $(ROM) --output $(EXTRACTED)
	@rm extracted_full.txt
	@$(PY) scripts/split_into_chunks.py --input $(EXTRACTED) --out-dir $(CHUNK_DIR) --size 250
	@if [ -z "$$(ls -A $(FR_CHUNK_DIR))" ]; then cp $(CHUNK_DIR)/chunk_*.txt $(FR_CHUNK_DIR)/; fi
	@$(PY) scripts/dump_rom_usage.py --rom $(ROM) --out $(ROM_USAGE)
	@echo "Extraction terminée : chunks créés dans $(CHUNK_DIR) et copiés dans $(FR_CHUNK_DIR) si vide."

chunk-clean:
	@echo "Combinaison des chunks FR existants..."
	@$(PY) scripts/combine_chunks.py --dir $(FR_CHUNK_DIR) --output combined_fr_temp.txt
	@echo "Filtrage des textes sans pointeurs..."
	@$(PY) scripts/filter_by_pointers.py --input combined_fr_temp.txt --rom $(ROM) --output combined_fr_clean.txt
	@rm combined_fr_temp.txt
	@echo "Redécoupage en chunks..."
	@rm -rf $(FR_CHUNK_DIR)/*
	@$(PY) scripts/split_into_chunks.py --input combined_fr_clean.txt --out-dir $(FR_CHUNK_DIR) --size 250
	@rm combined_fr_clean.txt
	@echo "Nettoyage terminé : chunks FR régénérés dans $(FR_CHUNK_DIR)."

build-fr:
	@ls $(FR_CHUNK_DIR)/chunk_*.txt >/dev/null
	@$(PY) scripts/combine_chunks.py --dir $(FR_CHUNK_DIR) --output $(COMBINED_FR)
	@[ -f $(ROM_USAGE) ] || $(PY) scripts/dump_rom_usage.py --rom $(ROM) --out $(ROM_USAGE)
	@$(PY) scripts/inject_translations.py --text $(COMBINED_FR) --out $(OUT_FR) --use-holes --free-map $(ROM_USAGE) --allow-append
	@echo "ROM générée : $(OUT_FR)"

.PHONY: quality
quality:
	@test -n "$(chunkfr)" || (echo "chunkfr manquant (ex: chunkfr=fr_chunks/chunk_62.txt)" && exit 1)
	@test -n "$(chunkorigin)" || (echo "chunkorigin manquant (ex: chunkorigin=origin_chuncks/chunk_62.txt)" && exit 1)
	@$(PY) scripts/check_breaks.py --fr "$(chunkfr)" --origin "$(chunkorigin)"
	@echo "Rapport généré dans quality_reports."

clean:
	@rm -f $(EXTRACTED) $(COMBINED_FR) $(OUT_FR) $(ROM_USAGE) extracted_full.txt combined_fr_clean.txt
	@rm -rf $(CHUNK_DIR)
	@echo "Nettoyage terminé."
