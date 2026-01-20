# Task 05 - Generic reinsertion pipeline

Goal:
- Reinsert Spanish texts into the English ROM with fidelity.
- Prefer copy-from-reference when available, fall back to translation + padding.

Steps:
- [x] Update `SmartReinserter` to enforce max length and padding limits.
- [x] Add a safe mode: refuse to truncate unless explicitly allowed.
- [x] Implement a generic builder that supports COPY / TRANSLATE / HYBRID correctly.
- [x] Use the offset mapping to handle Spanish-only or relocated texts.
- [x] Emit a detailed report with failures, truncations, and padding use.

Acceptance:
- Reproduced ROM matches reference for all mapped text ranges.
- Failures are limited to known, documented cases with clear reasons.
- No silent truncation by default.
