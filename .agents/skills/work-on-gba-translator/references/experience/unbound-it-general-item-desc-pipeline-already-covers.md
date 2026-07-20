---
name: unbound-it-general-item-desc-pipeline-already-covers
description: IT general item descriptions (0x3d/0x7b/0xeb) already translated by the generic pipeline; audit gap
metadata:
  node_type: memory
  type: project
  originSessionId: 9e0c32e8-effd-40c3-8cdf-8208aa819339
---

Ticket P-167 slice "IT general item descriptions" (regions 0x3D0000 / 0x7B0000 /
0xEB0000: Poké Ball catch blurbs, Berry effects, sprays, potions). The audit
`docs/it-table-offset-coverage.md` gap #2 claimed these ship English ("66/69
byte-identical to English", "no coverage path at all").

**That was a false positive** — the classic [[unbound-trace-live-pointer-not-original-offset]]
trap. The audit compared bytes at the *original English offset*, but the generic
build relocates the item's `+0x14` desc pointer and writes the Italian text
elsewhere. Empirically, on a fresh `build_language.py it`: **225 general item
descriptions with a combined_it entry render Italian, 0 still English.** The
generic pipeline (19_build reinserter) fully covers this bucket.

I still shipped `apply_item_desc_fixes` (combined_it-driven) in
`languages/it/patches/item_names.py` as a **safety net**: keys each item on its
English desc pointer → combined_it text, rewrites only descriptions the pipeline
left byte-identical to English (in place if it fits, else relocate+repoint with
graceful no-freespace degradation). On the current build it patches **0** (clean
no-op) — verified by running it against the built ROM. Wired via the existing
`item_names` step (no lang.yaml change). Test: `tests/unit/it/test_patch_item_descriptions_it.py`.

**Lesson:** before treating an audit-flagged "uncovered table" as a real gap,
trace the LIVE pointer in the built ROM, not the authored offset. See sibling
[[combined-fr-duplicate-offsets-last-wins]] for the combined-file offset rules.
