---
name: singularity-zombie-run-stale-complete
description: orchestration_complete can replay a STALE merge-failure error forever when the ticket was already completed by a concurrent run — check ticket status + engine log before debugging git
metadata:
  node_type: memory
  type: feedback
  originSessionId: 91fdff27-cc8b-4284-9c70-2725e3657df3
---

On a reopened/bounced ticket, the Singularity scheduler can auto-relaunch a NEW run
of the SAME task while older bounced runs keep executing as zombies. The new run can
complete and merge the ticket (status → done) while a zombie run's
`orchestration_complete` keeps failing with the SAME byte-identical
"finalizeWorktree: 1 uncommitted change(s): M output/roms/GenedRom-fr.gba" error —
replayed from recorded state, with NO new `[merge-back]` entry in the engine log.

**Why:** the error looks like a real git problem (phantom dirty file) and sends you
chasing racily-clean index entries ([[singularity-build-resets-worktree]]) when the
worktree is verifiably clean. 6 identical bounces despite a clean
`git diff-index HEAD` = the engine isn't re-running finalize at all.

**How to apply:** after 2 identical merge-failure bounces with a provably clean
worktree, STOP retrying and check:
1. `orchestration_get_current_ticket` → if `status: "done"`, another run already
   landed the work; your completes are no-ops replaying stale state.
2. Engine log `~/Library/Logs/Singularity/singularity-main.log` (JSON lines): grep
   the taskId / feature branch. A `[merge-back] per-project success` +
   "Workspace-scope run completed" for your branch means merged. Your attempts are
   absent → stale replay.
3. Then just verify the deliverable in the merged base branch (tests + decoded ROM
   bytes), report in the final message, and stop — do NOT call orchestration_fail
   (work isn't failed) and don't spam complete.
Also: the installed Singularity.app may lack the B-630 refreshIndex fix (source has
it in git-ops.ts; `grep -c update-index out/main/index.js` = 0 on the old build), so
genuine racily-clean bounces on 32MB ROMs are ALSO possible — distinguish via the
engine log (real attempts get logged).

**Same pattern on github-issue tickets (2026-07-08, #79/B-267):** follow-up said
"tu as oublié de répondre/clore l'issue" but `github_issues_get`/`_get_comments`
showed the issue already `state:"closed", stateReason:"completed"` with an
auto-posted completion comment (body starts "✅ Ticket B-XXX — ... — is done.").
The orchestration engine posts that comment + closes the linked issue itself right
after `orchestration_complete` on a ticket tagged `github-issue` (uses the ticket's
`shortResolution` as the comment body) — do NOT manually re-comment/re-close on a
reopen before checking `github_issues_get_comments` first, or you'll double-post.

**Repeat, #80/B-268 (2026-07-08):** identical follow-up wording, identical outcome —
issue already `closed`/`completed` with a human-style fix comment + the engine's
auto-posted "✅ Ticket ... is done." comment, both already present. Worktree was
clean, nothing to commit. Confirms this is a recurring reopen-race, not a one-off:
always check `github_issues_get_comments` before touching the issue on ANY reopened
github-issue ticket whose complaint is "you forgot to answer/close the issue".
