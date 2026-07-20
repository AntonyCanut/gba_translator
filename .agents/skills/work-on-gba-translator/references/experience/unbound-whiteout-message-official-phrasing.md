---
name: unbound-whiteout-message-official-phrasing
description: Whiteout field messages (0x41B554/0x41B5B6) rewritten to match official FR wording (issue
metadata:
  node_type: memory
  type: project
  originSessionId: 347cbacc-c2b0-438e-afc0-5495ebe191ad
---

Issue #35 asked that hors-jeu (out-of-battle) text match the official French
localisation as closely as space allows. Fixed the two whiteout messages at
`0x41B554` ("scurried to a Pokémon Center...") and `0x41B5B6` ("scurried back
home...") in `gba_translator/languages/fr/combined_fr.txt` to use the
official RS/FRLG phrasing ("se hâte vers un centre Pokémon/la maison pour
éviter que ses Pokémon ne souffrent davantage") instead of an invented
wording. Both offsets are pointer-referenced dialogue (not a fixed-width
cell), verified via decode of the built ROM — encoded length actually came in
*shorter* than the English original (92/84 bytes vs 97/87), so there was no
budget conflict at all.

**Why:** `CLAUDE.md`/older memories say the master file is
`gba_translator/combined_fr.txt` at repo root — that path is stale. The file
moved to `languages/fr/combined_fr.txt` (multi-language registry restructure,
see [[unbound-multilang-build-registry]]). Always `find` for it rather than
trusting the documented root path.

Also: `gba_translator` ships its **own** `src/core/dialogue_linewrap.py`
(distinct from the read-only analysis copy at `Test/Unbound/src/text/linewrap.py`).
It operates on the pipeline's own decoded token form (`<0xNN>` hex codes, real
`\n`) rather than the `{FC/FD:xx}` brace syntax the Unbound copy expects, and
its `rewrap()` / `word_width()` / `line_widths()` are the right tools to
pixel-check a candidate FR translation's line width (192px budget) before
writing it into `combined_fr.txt`. Note combined_fr.txt's own convention for
this particular string used three plain `\n` breaks (no `\l`/scroll token) to
render 3 lines — matched that existing style rather than introducing a
scroll token not used elsewhere in the file.

**How to apply:** For any "make text closer to official localisation"
ticket, locate the file with `find`/`grep` first (don't assume repo root),
use `dialogue_linewrap.rewrap()`/`word_width()` from `gba_translator/src/core`
to verify pixel width before editing, then rebuild via `make prepare-fr &&
make build-fr` (bypasses the CSV step, see
[[unbound-prepare-fr-bypasses-csv-step]]) and verify by decoding the built
ROM directly with `TextDecoder.decode(bytes, 'pokemon')` — never trust the
combined_fr.txt text alone.
