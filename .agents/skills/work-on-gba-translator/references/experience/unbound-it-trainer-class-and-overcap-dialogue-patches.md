---
name: unbound-it-trainer-class-and-overcap-dialogue-patches
description: "IT no-pointer trainer-class name table + over-cap long dialogues — dedicated patches, offsets, hard limits"
metadata:
  node_type: memory
  type: project
  originSessionId: 04c3f0f7-4544-4a52-81ad-2726e44a2be4
---

Two no-pointer IT content buckets that the generic pipeline skips, now shipped by dedicated post-build patches (ticket ce272c31, commit f893500).

**Trainer-class names (`gTrainerClassNames`)** — fixed-width table, base `0x23E558`, **107 cells × 13 bytes**, read by index arithmetic (`base + class_id*13`), NO pointers to cells → generic pipeline never touches it. Base pointer lives at file offsets `0xD80A0` / `0x11B4B4`. Index 0 = blank; classes are 1..106. `scripts/patch_trainer_class_names_it.py` writes IT names from `combined_it.txt` in place (wired in it/lang.yaml as `trainer_class_names_it`). Hard limit: name ≤12 bytes + `0xFF`. Initially **67 fit, 32 overflow (Italian longer than EN), 7 unauthored**. The 32 overflow were then **abbreviated to ≤12 B in `combined_it.txt` by child task 7b2789da** (commit `feat(it): abbreviate 32 overflowing trainer-class names`), so the patch now writes all authored classes and **F-100 (table relocation) is superseded/obsolete** — see [[unbound-it-trainer-class-fixed-cell-and-builtin-dispatch]]. New IT-specific elif dispatch steps must also join `_BUILTIN_STEPS` in `build_language.py` (registration test `test_patch_it_wrappers.py`). Escapes in combined for these cells: `\pk`→0x53, `\mn`→0x54 (PK/MN glyphs), `\sm`→♂(0xB5), `\sf`→♀(0xB6).

**Over-cap long dialogues** — the pointer extractor drops strings >`max_text_length` (1000 B, `src/extractors/pointer_text_extractor.py`), so ~5 huge dialogues (New Game+, Battle Circus/Sands/Tower, champion congrats) ship English despite having live pointers. `scripts/patch_long_dialogues_it.py` (step `long_dialogues_it`) discovers them dynamically (combined offset in `0x1F00000+` whose EN source >1000 B), encodes the full IT text, allocates free space, and repoints the live referrer — same relocate+repoint mechanism as the RELOCATE branch of `patch_intro_questions_it.py`. Freeze-safe (always 0xFF-terminated). Cross-language: FR/DE have the same gap, unpatched.

See [[unbound-long-dialogue-extractor-cap]], [[unbound-pipeline-unreachable-name-cells]], [[unbound-multilang-build-registry]], [[combined-fr-duplicate-offsets-last-wins]].
