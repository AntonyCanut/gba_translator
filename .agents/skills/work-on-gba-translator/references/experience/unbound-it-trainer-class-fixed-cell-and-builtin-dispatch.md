---
name: unbound-it-trainer-class-fixed-cell-and-builtin-dispatch
description: IT trainer-class names overflow the 13-byte fixed cell → abbreviate in combined_it.txt (no relocation headless); new IT elif steps must be added to _BUILTIN_STEPS
metadata:
  node_type: memory
  type: project
  originSessionId: b562c692-1d71-4ed7-8098-09d07a9cf14d
---

**gTrainerClassNames (base 0x23E558, stride 13, no pointers)**: 32 Italian class
names overflowed the fixed 13-byte cell (name ≤12B + 0xFF) and shipped English.
The code-level fix (relocate table + patch every `index*13` code site + mGBA
verify) is **unsafe headless** — instead abbreviate the 32 names to ≤12 bytes in
`gba_translator/languages/it/combined_it.txt`, preferring real shorter Italian
class terms (Ornitologo=Bird Keeper, Montanaro=Hiker, Gitante=Picnicker,
Signorino/Signorina=Rich Boy/Girl, Ombrellina=Parasol Lady, Admin Idro/Magma).
`patch_trainer_class_names_it.py` then writes all 99 (F-100 / ticket 7b2789da).
Verify by running `patch()` on a copy of `input/roms/englishrom.gba` and decoding
each cell — no full build needed. English itself is truncated in some cells
("Black Horizo", "Ex Shadow Ad"), so abbreviation is consistent. See
[[unbound-ability-names-fixed-table]], [[unbound-pipeline-unreachable-name-cells]].

**IT patch dispatch refactor (base `unbound`)**: `build_language.py` resolves each
`lang.yaml` step via `_lang_patch_script(step,"it")` → `languages/it/patches/<name>.py`
wrapper (FR-delegating), else an `apply_patches()` elif branch. A guard test
`test_every_italian_step_is_dispatchable` (tests/unit/test_patch_it_wrappers.py)
asserts every step resolves to a wrapper OR is in the test's hardcoded
`_BUILTIN_STEPS` set. **Any new IT step dispatched by an elif branch (IT-specific,
no FR delegate) MUST be added to `_BUILTIN_STEPS` or this test fails.**

**Pre-existing base breakage found**: `combined_it.txt` has 165 multi-line entries
that fail `test_combined_it_format.py`'s normalizer guard (added without running
`normalize_combined_multiline.py`). Tracked as B-165 — not caused by text edits.
