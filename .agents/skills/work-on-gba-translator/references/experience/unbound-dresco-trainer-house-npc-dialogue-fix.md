---
name: unbound-dresco-trainer-house-npc-dialogue-fix
description: "Dresco Trainer House NPC dialogue fix — \"Maison Dresseurs\"→\"Maison des Dresseurs\" + reworded confusing ending (issue"
metadata:
  node_type: memory
  type: project
  originSessionId: 2997b90a-8164-4566-a405-88d7cdf7c286
---

Fixed offset `0x1F0090B` in `gba_translator/languages/fr/combined_fr.txt` (single entry,
no duplicates): "Maison Dresseurs" → "Maison des Dresseurs", and reworded the confusing
ending "peuvent devenir plus forts avec toi" → "progressent en même temps que toi" to
match the EN source meaning ("I even hear the Trainers can get stronger as you do" = the
Trainers in that house scale with player progression, not "through battles" as the
reporter's own proposed wording implied).

**Why:** the user's proposed replacement text ("au fil des combats") changed the meaning
vs the EN original; checking the EN source before adopting a user's exact reformulation
prevented introducing a new, different mistranslation. See [[unbound-door-forced-shut-ambiguity-fix]]
for the same pattern (verify EN before trusting a user's phrasing).

**How to apply:** when a French dialogue fix ticket includes a user's proposed wording,
always decode/read the EN source at the same offset first (`languages/en/combined_en.txt`)
and preserve its actual meaning — improve grammar/clarity but don't silently swap meaning.
Also useful: `src/core/dialogue_linewrap.py::line_widths()` (needs real `\n` chars +
`<0xFB>`/`<0xFA>` tags, NOT the literal `\n`/`\p`/`\l` escapes used in combined_fr.txt) to
pixel-check a reworded line stays within the ~192px default box budget before committing.

Build chain used: no CSV/JSON existed in this fresh worktree, so `make prepare-fr` (not
the CSV path) regenerated `translation_ready.json` straight from `combined_fr.txt`, then
`make build-fr`. Verified via decoded ROM bytes, not screenshots. `output/roms/GenedRom-fr.gba`
is a *tracked* (not gitignored) build artifact — every text-fix ticket commits its own ROM
rebuild, so rebase conflicts on that binary are routine: `git rebase --skip` the stale
ROM-only commit, then re-run `prepare-fr && build-fr` and commit a fresh ROM after rebase.
