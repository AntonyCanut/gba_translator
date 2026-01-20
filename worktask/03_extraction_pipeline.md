# Task 03 - Extraction pipeline rebuild

Goal:
- Replace legacy text extraction with a reliable, pointer-based extractor.
- Preserve raw bytes and metadata for accurate reproduction.

Steps:
- [x] Implement an extractor under `src/extractors/` that uses pointer tables and terminators.
- [x] Store per-text metadata: offset, byte_length, encoding, raw_bytes (hex), decoded_text.
- [x] Handle control codes instead of dropping them.
- [x] Write outputs to `output/extracted/extracted_texts/` in a stable JSON schema.
- [x] Add a small validation script that checks for invalid lengths and duplicates.

Acceptance:
- Extraction is reproducible and produces the same counts on repeated runs.
- Spanish accents and control codes are preserved in the JSON output.
- No dependency on `scripts/legacy/extract_text.py` for the main workflow.
