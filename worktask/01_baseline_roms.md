# Task 01 - Baseline ROMs and scope

Goal:
- Define the exact input ROMs and a reproducible baseline.
- Lock the scope: reproduce the Spanish ROM from English + extracted Spanish text.

Steps:
- [x] Record SHA256 and size for `input/roms/englishrom.gba` and `input/roms/spanishrom.gba` in a small JSON report.
- [x] Add a short script to re-check those checksums before any build (fail fast if mismatch).
- [x] Capture a minimal baseline report with counts: total texts, diff counts, and current reproduction success from existing outputs.
- [x] Document the single "source of truth" paths in README or a new `docs/` page.

Acceptance:
- A report file exists with checksums and sizes for both ROMs.
- A script can verify inputs in <5s and is used by the main pipeline.
- Baseline report is committed and referenced in docs.
