---
name: unbound-protected-entries-mandatory-new-translation
description: gba_translator pre-commit hook now rejects any combined_fr.txt (or other lang) edit without a matching entry in protected_entries.yaml — not just an existing-entry check
metadata:
  node_type: memory
  type: project
  originSessionId: aa20997a-a5c9-4ec1-80a9-fa2437ac7313
---

Issue #116 (Missions tab "Actives"→"Active", offset `0x1F5605C`): the pre-commit hook's
"couverture unitaire des nouvelles traductions" check now blocks **any new** translation
offset committed in `combined_fr.txt` (or `combined_<lang>.txt`) that has no corresponding
entry in `languages/<lang>/protected_entries.yaml` — this is stricter than the older
regression-only framing in [[translating-unbound-skill]] and
`docs/20_TRANSLATION_PRESERVATION.md`.

**How to apply:** whenever adding/editing a `combined_fr.txt` line, add a matching entry
`{offset, name, issue, expected, forbidden?}` to `protected_entries.yaml` in the **same
commit**, even for a brand-new fix with no prior regression history. Format: see existing
entries in that file (offset uppercase-0x hex, `expected` = target FR string, optional
`forbidden` list of strings that must never reappear).

Also confirms [[unbound-worktree-emulator-web-node-modules-gap]]: fresh worktrees still lack
`emulator-web/node_modules`, causing `vitest: command not found` — symlink it before
committing.
