---
name: diagnosing-unbound-freezes-skill
description: A Claude skill captures how to diagnose Pokemon Unbound FR in-game freezes (detect by screen-hash, trace unterminated string, guarded fix, replay proof)
metadata:
  node_type: memory
  type: reference
  originSessionId: 6d4ee001-5123-4894-a088-c7df1c35de9e
---

The freeze-debugging methodology distilled from the "pas de gain d'objet" saga (see
[[unbound-give-cs-object-gain-crash]]) is captured as a Claude skill at
`Test/Unbound/.claude/skills/diagnosing-unbound-freezes/SKILL.md` (version-controlled via the
`.gitignore` exception `!.claude/skills/`). Invoke it for ANY FR-only in-game freeze.

It encodes the capital lesson: detect a freeze ONLY by screen pixel hash — never player
position (immobile in any dialogue) nor CPU PC (REGISTERS reads in VBlank IRQ → ~always BIOS
`0x1C4`). Then trace the unterminated CFRU string via `gStringVar4` (`0x02021D18`), find ALL
consumers (desc table AND field-move structs `0x083DEA80`/`0x0887AD30`), fix reference-driven
but content-guarded + clustered-only (region-blind repoints corrupt font/data/code), in the
`gba_translator` `make build-fr` pipeline (see [[translating-unbound-skill]] /
[[unbound-fr-build-lives-in-gba-translator]]), and prove it by re-break-then-fix replay. Also
links [[unbound-mgba-harness-flags-invalid]] and [[unbound-mgba-probe-quirks]] for harness traps.
