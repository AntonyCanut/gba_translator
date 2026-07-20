---
name: unbound-it-relocation-packing-fix
description: IT build relocation demand exceeds ROM free space; best-fit+dedup+shortest-first packing makes it fit
metadata:
  node_type: memory
  type: project
  originSessionId: 255fe1be-ba19-4beb-b296-7d12b3511d5e
---

IT build relocation **demand (~965KB unique, ~997KB raw) exceeds total ROM free
space (~702KB with the Spanish-reservation carve, ~749KB without)**. So the build
can NEVER relocate every overflowing IT string — something must stay English. The
20% `test_relocation_reasonable` threshold is only reachable by maximising the
*number* of strings placed, not the bytes.

Fix (commit 27c10c6, `src/core/text_reinserter.py`, shared by FR/IT builds):
- `FreeSpaceAllocator.allocate` → **best-fit** (smallest block that fits), not
  first-fit. First-fit wasted big blocks on small strings.
- **Dedup**: identical encoded strings relocated once, all pointer sites aim at the
  one shared read-only copy (`_relocation_cache`).
- `flush_relocations` sorts **shortest-first** so only the few longest strings fail.

Result: IT relocation_failed 27.3% → ~5.3%. FR unchanged (0 failures, ample space;
tests follow pointers dynamically so addresses changing is harmless).

Gotchas: top-level report `statistics` is a *curated* dict built in
`SmartReinserter.get_report`, NOT the raw `self.stats` — new stat keys must be added
there too. The stress test `test_space_exhaustion.py::test_partial_batch...` used 20
identical strings; dedup made them all fit, so it now uses distinct strings.
The built FR ROM `output/roms/GenedRom-fr.gba` is git-TRACKED (IT ROM is ignored) —
don't commit a local FR rebuild. See [[unbound-multilang-build-registry]],
[[unbound-font-patch-freespace-cascade]], [[singularity-build-resets-worktree]].
