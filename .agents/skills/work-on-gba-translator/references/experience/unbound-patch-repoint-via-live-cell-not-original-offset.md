---
name: unbound-patch-repoint-via-live-cell-not-original-offset
description: "Post-build relocate-repoint patches must repoint via the LIVE pointer cell, not referrers to the original English offset (pipeline relocates first)"
metadata:
  node_type: memory
  type: project
  originSessionId: 90e289e8-473a-458a-9626-d859731603f6
---

Build KO it (2026-06-28): `make build-it` aborted in `scripts/patch_intro_questions_it.py`. The long intro puzzle question 0x1F0F9FA (~118 o) overflows its 104-o English slot, so the **generic build pipeline relocates it and repoints the live pointer BEFORE the post-build patch runs**. The patch scanned `_find_referrers(original_offset)`, found none (pipeline already consumed them), took the `skip` branch, and the strict `verify()` then compared the pipeline's relocated bytes vs the canonical text, mismatched, exit 1 → whole IT release skipped (FR shipped). Error surfaced only as the generic guard `::error::Italian ROM build/verify failed`; real cause was `CalledProcessError` on the patch, visible via `gh run view <id> --log` (NOT `--log-failed`, the step is `continue-on-error`).

**Rule for relocate-and-repoint patches:** repoint via the **live pointer cell** (`POINTER_CELLS[offset]`), not via referrers to the original English offset. Read live target; if it already holds the canonical encoded text → idempotent skip; else allocate free space, write canonical text, and repoint the union of {canonical cell, find_referrers(original_offset), find_referrers(live_target)}. Mismatch with the pipeline's bytes is expected (wrapper recomputes line breaks) — the patch's hardcoded text is the source of truth.

Verify END-TO-END with a real build, not just unit tests: `make extract && make build-it BUILD_NUMBER=N` (local Python 3.9; CI is 3.11). Look for `relocated N bytes to 0x… ; repointed` + `✓ Italian ROM built`. Also keep a drift guard tying the patch's hardcoded text to `languages/it/combined_it.txt` (the original break root cause was a stale combined file). See [[unbound-fr-build-lives-in-gba-translator]], [[unbound-brace-control-token-relocation-literal]], [[singularity-build-resets-worktree]].
