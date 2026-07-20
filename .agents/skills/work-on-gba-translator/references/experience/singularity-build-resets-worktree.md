---
name: singularity-build-resets-worktree
description: Running make build-* (or any long build) inside a Singularity worktree can trigger a git reset --hard that wipes uncommitted edits — commit BEFORE building
metadata:
  node_type: memory
  type: feedback
  originSessionId: d257f2d8-221b-4c01-a347-7c4ba5330ede
---

In a Singularity worktree, a `git reset --hard HEAD` (checkpoint hook / concurrent
process) wiped ALL my uncommitted edits mid-task while a `make build-it` was running.
Reflog showed `reset: moving to HEAD`; the work was NOT in `git stash` (it was
unstaged working-tree changes, gone). The whole `output/` tree was also cleared.

**Why:** confirms the [[singularity-worktree-commit-early]] reset-loss pattern — long
builds and the background checkpoint hook race against unstaged edits.

**How to apply:** finish a coherent slice of edits, `git add -A && git commit`
IMMEDIATELY, and only THEN run `make build-*` / any slow command. Re-commit after
each further slice. Never leave edits uncommitted across a build. If edits vanish,
check `git reflog` for a reset-to-HEAD and just redo from conversation context
(stash won't have them). Local env here is Python 3.9 only; full `make build-it`
needs 3.11 (CI), so validate full language builds in CI, not locally.

**Escalation observed 2026-07-01 (Roi Borrius III ticket):** the entire worktree
directory can vanish mid-build (not just `reset --hard` inside it) — `ls` on the
worktree path returns "No such file or directory" a few minutes after a commit
landed there. Root cause: once a commit lands, the orchestration engine appears to
integrate it into the base branch and reclaim the worktree, even mid-session,
without waiting for `orchestration_complete`. `git worktree list` in the main repo
confirms the entry is gone, but `git log` on the main checkout shows the commit is
already HEAD — no work lost, just the workspace. **Recovery:** call
`orchestration_prepare_worktree` again (same project) — it recreates a fresh
worktree from the now-advanced base branch (which already contains your commit),
`cd` into the new path and continue (e.g. rerun the build). Verify with `ls -d
$WT` before trusting any command output from that path, especially after a
long-running background build — a `FileNotFoundError` deep in a Python traceback
for an input ROM or generated JSON is the tell, not a corrupted build. Also:
piping a build/test command through `| tail -N` masks its real exit code (the
pipeline reports `tail`'s exit status, always 0) — rerun without the pipe (or with
`echo EXIT=$?` right after) before trusting a "completed (exit code 0)" notification.

**Out-of-tree build workaround (validated 2026-07-02, ticket Suppression genre):**
when `make build-fr` in the worktree keeps getting killed/reverted by concurrent
resets (symptom: build log shows all patch stages ran, then `git status` is clean —
the patched ROM was silently reverted; or `FileNotFoundError` on `output/roms/...`
mid-write), copy the whole worktree (~120MB) to `/tmp`, `rm -f /tmp/copy/.git`
(worktree .git is a pointer file), run `make prepare-fr && make build-fr` there
(the reset may also have `git clean`-ed untracked build inputs like
`output/translation/*_translation_ready.json` — always rerun `prepare-fr` in the
copy), then `cp` the ROM back into the worktree and commit in the SAME shell
command. Build is deterministic ([[unbound-build-determinism-relocation-order]]),
so `git commit` reporting "nothing to commit" after the copy-back is a valid
success signal: another process already committed a byte-identical ROM.

**Re-confirmed 2026-07-06 (issue #12 merge-recovery run):** the reset+clean fired
mid-`make build-fr` even on a REOPENED merge-failure-recovery run (wiped the just-built
ROM, the untracked `*_translation_ready.json`, and symlinks to main-checkout
`output/extracted`). The /tmp copy workaround worked first try (symlinking
`output/extracted` + `output/differences` from the main checkout into the copy skips
the ~min-long re-extraction; keeping the worktree `.git` pointer file is harmless when
no git ops run in the copy). New engine behaviour: as soon as the worktree was clean
and the ROM commit landed, the engine auto-finalized WITHOUT `orchestration_complete` —
it added its own commit (`chore: ignore output/differences`) and fast-forwarded the
base branch `unbound` to the worktree HEAD. So after copy-back+commit, check
`git rev-parse unbound` == HEAD before assuming a rebase is still needed;
`orchestration_pull` then reports no-op and `orchestration_complete` is a formality.
