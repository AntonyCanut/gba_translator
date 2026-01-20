# Task 02 - Encoding and decoding table (Pokemon ES)

Goal:
- Build a complete encode/decode table for the Spanish FireRed ROM.
- Use the same table everywhere (extract, diff, reinsert, validate).

Steps:
- [x] Create a `TextDecoder` in `src/core/` and move tables to a single module.
- [x] Include Spanish chars (a/e/i/o/u, n, inverted punctuation) and control codes (newline, placeholders, etc).
- [x] Add a round-trip test: encode -> decode -> encode must preserve bytes for known samples.
- [x] Update all scripts to use the shared encoder/decoder instead of local tables.

Acceptance:
- A single source of truth for encoding and decoding exists in `src/core/`.
- Spanish accents no longer appear as `?` in extracted texts.
- Unit tests cover at least 10 Spanish-specific samples and control codes.
