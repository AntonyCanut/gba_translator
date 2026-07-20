---
name: unbound-worktree-emulator-web-node-modules-gap
description: "gba_translator worktrees symlink top-level node_modules but NOT emulator-web/node_modules, so the pre-commit hook's vitest run fails with \"command not found\" in fresh worktrees"
metadata:
  node_type: memory
  type: project
  originSessionId: 632e5df3-73bd-41bf-b3b4-09a8f986e0e0
---

Fresh `gba_translator` worktrees (via `orchestration_prepare_worktree`) get a
symlinked top-level `node_modules` but `emulator-web/node_modules` is missing
entirely — the pre-commit hook runs `npm --prefix emulator-web test` (vitest),
which fails with `vitest: command not found` and blocks the commit.

**Why:** worktree setup only symlinks the repo-root `node_modules`, not nested
package `node_modules` dirs; `emulator-web` is a separate npm package.

**How to apply:** before committing DE/FR/IT changes in a fresh gba_translator
worktree, check `ls <worktree>/emulator-web/node_modules` — if missing, run
`ln -s /Users/akc/Projects/Test/gba_translator/emulator-web/node_modules <worktree>/emulator-web/node_modules`
(mirrors the existing top-level symlink convention). Never bypass the hook
with `--no-verify`; this symlink fix is the real root cause fix and is safe
(dev-dependency linking only, no source change). See [[unbound-worktree-generic-build-artifact-reuse]].
