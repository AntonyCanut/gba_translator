---
name: unbound-hoopa-farewell-pronoun-fix-issue56
description: "Hoopa farewell cutscene (issue #56) 'elle' pronoun for genderless Hoopa at 0x1F1194E — same buffer bug as Hoopa estate scene, fixed by rephrasing"
metadata:
  node_type: memory
  type: project
  originSessionId: 28d88399-5b1d-4d27-afa7-e775682b0445
---

Issue #56: intro Hoopa farewell scene ("Protège mon enfant si un jour <0xFD><0x03> est
en danger.", offset `0x1F1194E` in `gba_translator/languages/fr/combined_fr.txt`) showed
"elle" for Hoopa (genderless Mythical). Same root cause as
[[unbound-gender-pronoun-variable-removal]] / `tests/test_gender_neutral_hoopa_estate_fr.py`:
the shared player-gender pronoun buffer (`<0xFD><0x02/03/04>`, tables @ 0x789224 /
0x1FA764E) gets reused by story scripts for non-player characters and renders wrong.

**Fix pattern (reused, not novel):** delete the buffer, rephrase gender-neutrally.
"si un jour elle est en danger" → "en cas de danger". Added to the existing
`NEUTRAL_OFFSETS` dict in `tests/test_gender_neutral_hoopa_estate_fr.py` (source-level,
no ROM needed) rather than writing a new test file — this is the established home for
"genderless Hoopa cutscene" pronoun bugs.

**Build chain reminder (worked, `make prepare-fr && make build-fr`, not the stale
CSV path):** symlink main checkout's gitignored `output/extracted` + `output/differences`
into the Singularity worktree first (see [[unbound-worktree-generic-build-artifact-reuse]])
or `make prepare-fr` re-extracts the 32MB FR ROM from scratch (still fast, ~seconds,
just avoid it if possible). `output/roms/GenedRom-fr.gba` IS committed (golden ROM) —
expect **binary rebase conflicts** on it if another ticket lands a ROM rebuild on the
base branch concurrently; resolve with `git checkout --ours` (take base's ROM) then
`git rebase --continue`, then re-run `make prepare-fr && make build-fr` and commit a
fresh `build(fr): rebuild ROM ...` commit — happened twice in a row for this ticket as
two sibling tickets (#61 Dresco, #63 Lv ligature) landed on `unbound` mid-task.
