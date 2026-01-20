# Task 04 - Diff pipeline and offset mapping

Goal:
- Identify only the Spanish texts that differ from English.
- Build a stable mapping between English and Spanish offsets.

Steps:
- [x] Build a diff tool that compares raw bytes and decoded text side by side.
- [x] Separate cases: modified, only_in_english, only_in_spanish.
- [x] Create an offset map for relocated texts (if any), based on pointer tables.
- [x] Generate a translation dataset that contains both EN and ES raw bytes plus decoded text.

Acceptance:
- A JSON diff report exists with clear counts and per-case lists.
- Offset mapping covers all Spanish-only texts or explicitly marks unknown cases.
- The translation dataset is sufficient to rebuild ES text without data loss.
