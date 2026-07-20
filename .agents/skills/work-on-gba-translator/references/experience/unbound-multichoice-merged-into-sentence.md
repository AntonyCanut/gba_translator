---
name: unbound-multichoice-merged-into-sentence
description: "FR translation collapsed a 3-entry \n-separated multichoice list into one run-on sentence, breaking the choice box (#70)"
metadata:
  node_type: memory
  type: project
  originSessionId: 66a0c596-65c0-40c8-bf69-83b893af88a1
---

At offset `0x1F4E230` (EN `Save\nDiscard\nCancel`, the Options-menu exit
confirmation box), `combined_fr.txt` had `Sauver ou abandonner ?` — a single
merged sentence instead of 3 `\n`-separated menu entries. The game reads this
string as N separate choices split on `\n`; collapsing them into one long
"choice" broke the box rendering (truncated/overlapping, only 1 item instead
of 3), matching the screenshot in issue #70.

**Detection trick**: compare the same offset across `languages/<code>/combined_<code>.txt`
files. IT had the correct structure at this offset (`Salva\nScarta\nAnnulla`)
even though FR was broken — cross-referencing a working language is often
faster than tracing English source or ROM bytes from scratch.

**Width constraint**: multichoice box width is NOT a fixed universal value —
different boxes in the game have different pixel budgets. Measured via
`src/text/linewrap.text_width()` (Test/Unbound repo): the "Continuer\nQuitter\nPasser"
box elsewhere in-game tolerates words up to ~48px, but THIS box (options-exit)
only fits ~38-39px (same ceiling as IT's longest word "Annulla"=38px). Always
measure against the same-offset reference in another language, not an
unrelated box elsewhere in the game.

**Verification**: reading the raw byte offset `0x1F4E230` in the built ROM
after a relocate-on-overflow build still shows the OLD English text — the
injector left the original bytes untouched and repointed the live pointer
table slot (found here at file offset `0x1EBD77C`) to the new relocated
location. Same trap as [[unbound-trace-live-pointer-not-original-offset]].

Fix landed as `Sauver\nIgnorer\nAnnuler`, committed in `gba_translator`
(`output/roms/GenedRom-fr.gba` + `languages/fr/combined_fr.txt`), with a new
regression test in `tests/test_regression_texts.py` asserting the pointer
resolves to exactly 3 non-empty `\n`-separated choices.

See [[unbound-trace-live-pointer-not-original-offset]], [[unbound-fr-build-lives-in-gba-translator]].
