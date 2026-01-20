# Task 06 - Validation and tests

Goal:
- Validate that the reproduced ROM is truly equivalent to the Spanish ROM.
- Add unit and integration tests around encoding, extraction, and reinsertion.

Steps:
- [x] Implement a validator that compares output ROM to reference (byte-level in text ranges).
- [x] Add a small test suite for encoding/decoding round-trip and sample offsets.
- [x] Add a regression test that compares a small set of offsets for exact byte match.
- [x] Report mismatches with offsets, expected bytes, and decoded text.

Acceptance:
- Validation report clearly states match percentage and list of mismatches.
- Tests can run locally without ROM modification side effects.
- The validator uses real ROM data (not only extracted JSON).
