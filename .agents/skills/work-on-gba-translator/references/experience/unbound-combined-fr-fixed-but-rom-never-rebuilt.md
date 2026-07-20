---
name: unbound-combined-fr-fixed-but-rom-never-rebuilt
description: "A prior agent run edited combined_fr.txt correctly but crashed before running prepare-fr/build-fr, leaving the ROM unfixed despite a \"fix\" commit already on the branch"
metadata:
  node_type: memory
  type: project
  originSessionId: 9f91c997-b298-4c51-ac7a-a2f2396c10c4
---

Issue #37 (sbire Ombre "laisser passer") had already been fixed in `languages/fr/combined_fr.txt`
by a previous agent attempt that hit an API error mid-task and never got to rebuild the ROM.
`git log -- languages/fr/combined_fr.txt` showed the fix commit already present on the base
branch, but `output/roms/GenedRom-fr.gba` still decoded the old/English text at the live pointer.

**Why:** the ticket retried after an `AGENT_ERROR` (Anthropic usage-policy false-positive) — the
first attempt's partial commit was real work, not something to redo from scratch.

**How to apply:** before starting a translation-fix ticket, always check whether the target text
is already correct in `combined_fr.txt` (`git log -- languages/fr/combined_fr.txt` for recent
commits mentioning the issue number). If the source is already fixed, the remaining work is just
`make prepare-fr && make build-fr` + live-pointer verification — don't re-edit text that's already
right. See also [[unbound-pattern-c-stale-snapshot-commit]] and [[unbound-trace-live-pointer-not-original-offset]]
(the target offset here was relocated by the builder, so the raw offset in the ROM still held the
English text — had to trace the EN pointer location and follow the FR pointer to find the live copy).

Also hit a concurrent-ticket ROM binary conflict during `orchestration_pull` (another ticket,
`ce1efe5` "door message fix", rebuilt the same `GenedRom-fr.gba` at the same time). Per
[[unbound-rom-rebase-conflict-rebuild-resolution]], resolved by rebuilding fresh from the
post-rebase merged `combined_fr.txt` rather than picking ours/theirs on the binary.
