---
name: singularity-parent-merge-orphaned-by-child-ticket
description: "orchestration_complete returned \"accepted\" but the parent ticket's commits never landed on the base branch — a concurrently-completing child ticket's merge-back silently orphaned them. Always verify post-completion."
metadata:
  node_type: memory
  type: project
  originSessionId: 3522c4d8-480e-47f4-b9e1-5fc6b4261357
---

Incident (ticket B-151 "Manque traduction DexNav" + its auto-created child F-71,
2026-07-03): parent ticket committed a `combined_fr.txt` fix in its worktree, ran the full
build+test chain, then called `orchestration_complete` — which returned "accepted" with no
error. The parent ticket's status later still showed `working` and the resume prompt asked
to "continue the task." Checking `git merge-base --is-ancestor <parent-commit> unbound`
showed **false**: the parent's 3 commits existed only on the orphaned worktree branch
(`worktree/b-151-...`), never merged into `unbound`. Meanwhile the child ticket F-71 (a
follow-up auto-created *during* the parent's run, auto-accepted, and completed shortly
after) had its own commits cleanly on `unbound`.

Root cause (inferred, not confirmed from engine internals): the child's worktree was very
likely prepared from an `unbound` snapshot around the same time as the parent's completion
race window. Whatever merge-back mechanism the engine used for the child ended up as the
new `unbound` tip **without** the parent's already-"accepted" commits — i.e. `orchestration_complete`
returning success is not sufficient proof the merge is durable when a child ticket is also
completing concurrently on the same branch.

**Defense**: don't trust a single `orchestration_complete` "accepted" response as the end of
the story, especially when the ticket has child tickets that may complete around the same
time. On any resumed/reopened session (or before considering work "shipped"), verify with:

```bash
git -C <project> merge-base --is-ancestor <your-commit-sha> <base-branch> && echo OK
```

If it prints nothing / fails, the commit is orphaned: re-`orchestration_prepare_worktree`
(idempotent — returns the same worktree, still holding your original commits untouched),
`orchestration_pull` to rebase onto the current base (résoudre le conflit binaire ROM
habituel en gardant `--ours`, cf. [[singularity-worktree-commit-early]]), rebuild, retest,
recommit the ROM, and call `orchestration_complete` again. The original worktree and its
commits survive this whole ordeal untouched — nothing was actually lost, just not merged.

Related: [[singularity-stale-attempt-phantom-merge-failure]] (bounce-loop despite a clean
worktree — a different, engine-respawn-attempt failure mode) and
[[singularity-worktree-commit-early]] (why to commit early and how to resolve the recurring
binary ROM conflict).
