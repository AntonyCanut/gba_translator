# Task 07 - Docs, Makefile, and cleanup

Goal:
- Make the repository runnable from a single, correct workflow.
- Remove confusion between legacy and current scripts.

Steps:
- [x] Update `Makefile` to use the new folder layout and current scripts.
- [x] Mark legacy scripts as deprecated or move them under a clear archive path.
- [x] Update README and docs to reflect the Spanish reproduction goal and pipeline.
- [x] Add a top-level "quick start" that calls the new pipeline end-to-end.

Acceptance:
- `make` targets run without path errors.
- Docs reference only the current pipeline and correct file paths.
- One canonical entry point is documented (CLI or Makefile).
