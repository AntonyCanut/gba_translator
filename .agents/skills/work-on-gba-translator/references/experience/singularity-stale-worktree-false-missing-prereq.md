---
name: singularity-stale-worktree-false-missing-prereq
description: "A prerequisite ticket's artifacts looking \"missing from base\" may just be a stale worktree behind the base tip — reset to base before concluding blocked"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 87d6d658-11db-41cb-bded-8be888fe4b03
---

F-72 (German batch 2/12) bounced twice with "blocking prerequisite F-70 not merged": the previous run inspected its worktree, saw `scripts/list_fr_entries_batch.py` absent and `combined_de.txt` at only the 30-line seed, and concluded F-70 had never merged to `unbound`. **It was wrong.** F-70 *had* merged; the worktree HEAD was simply 9 commits *behind* the current `unbound` tip (prepare_worktree returned an existing, stale worktree branch). `git rev-list --left-right --count HEAD...unbound` = `0 9`, merge-base = HEAD → HEAD is a clean ancestor of unbound.

**Why:** a reopened ticket's worktree can be created from (or left at) an older base snapshot. Reading files in it shows the base as it was *then*, not now. The batch-1 artifacts were present on real `unbound` all along.

**How to apply:** before declaring a prerequisite "not merged / missing," verify against the *live* base branch, not the worktree's current HEAD:
- `git log --oneline -1 unbound` vs your HEAD; `git rev-list --left-right --count HEAD...unbound`.
- If behind and clean (0 ahead), `git reset --hard unbound` (no local changes) or `orchestration_pull`, then re-check for the artifacts.
- `git merge-base --is-ancestor <prereq-commit> unbound` to confirm the prereq is truly on base. A `git cherry-pick` of the prereq commit that comes back **empty** ("previous cherry-pick is now empty") is proof its content is *already* on base.

Distinct from [[singularity-parent-merge-orphaned-by-child-ticket]] (there the parent genuinely never merged); here the merge happened and only the worktree view was stale. Related: [[singularity-worktree-commit-early]], [[unbound-e2e-worktree-root-resolution-fixed]].
