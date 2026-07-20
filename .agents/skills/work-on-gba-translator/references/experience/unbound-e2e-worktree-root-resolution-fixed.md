---
name: unbound-e2e-worktree-root-resolution-fixed
description: "gba_translator e2e _resolve_project_root() now defaults to the running worktree, not the main checkout (fixed 2026-07-01)"
metadata:
  node_type: memory
  type: project
  originSessionId: 26520666-d944-49c8-94b9-6a1d36d6622e
---

`tests/e2e/conftest.py`, `tests/e2e/test_italian_build.py`, and
`tests/e2e/test_it_first_battle.py` in `gba_translator` used to have a
`_resolve_project_root()` that always climbed past `.singularity-worktrees/<id>/`
to the main checkout, even when running from a worktree. Root cause turned out
to be a false premise: `output/roms/GenedRom-fr.gba` IS git-tracked, so every
worktree already has its own checked-out copy — the old code's comment
("ROMs ... are not copied to worktrees") was wrong for the FR ROM (true only
for the untracked/gitignored IT ROM and the dated translation_ready report).

**Fix landed**: all three now default to `pathlib.Path(__file__).resolve().parent.parent.parent`
(the worktree's own checkout) and only escape to a different root via the
`GBA_PROJECT_ROOT` env var override, which still works exactly as before.

**Why**: prevented silent cross-contamination — a worktree's e2e run could
read whatever ROM the main checkout happened to have at that moment (e.g.
mid-edit from a concurrent ticket), giving false green/red results unrelated
to the worktree's own changes.

**How to apply**: no special env var is needed anymore for e2e tests run
inside a worktree to see that worktree's own built/checked-out ROM — that's
now the default. Only set `GBA_PROJECT_ROOT` when you deliberately want to
validate against the shared/canonical main-checkout ROM. See
[[unbound-e2e-tests-gate-committed-rom.md]] and [[singularity-worktree-commit-early]]
for related worktree/build caveats.
