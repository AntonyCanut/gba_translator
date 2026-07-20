---
name: unbound-dialogue-linewrap-zero-break-overflow
description: German (and any language) dialogue text visually overlapping itself in-game after a hand-written long correction with no \n at all
metadata:
  node_type: memory
  type: project
  originSessionId: 8b7cd39b-1fde-460b-8a87-c590f1570924
---

`gba_translator/src/core/dialogue_linewrap.py` (`rewrap_segment` and the top-level
`rewrap`) used to bail out and return text **unmodified** whenever a segment/page had
zero `\n` breaks, assuming a 0-break segment must already fit one box line. That
assumption holds for translations that inherit their `\n` positions from the English
source, but NOT for a hand-edited correction written as one continuous sentence with
no breaks at all — it ships to the ROM as a single unbroken line that overflows the
192px box width, visually overlapping the next page's text/continue arrow (▼) in-game.

Root cause found via `git log -S "<snippet>" -- languages/de/combined_de.txt`: commit
`f7333f6` (issue #54, "rewrite over-long dialogue as shorter, meaning-preserving
German") rewrote `0x1F2FE44` and ~78 other pages into shorter but completely unwrapped
text. 79 entries across that one commit had this same zero-break-and-too-wide shape.

**Fix** (commit `157b984` in gba_translator, branch `unbound`): both `rewrap_segment`
and `rewrap` now check the segment's actual pixel width (`line_width()`) before
bailing on "no break present" — they only skip wrapping when the text already fits.

**Why no manual edit to `combined_de.txt` was needed**: `output/translation/de_*.json`
and `de_*.csv` are gitignored and regenerated fresh from `combined_de.txt` at build
time; `rewrap` (imported as `rewrap_dialogue`) runs inside
`19_build_translated_rom_generic.py`'s `_normalize_translation_item` on that raw text
at build time. So the code fix alone corrects every affected entry on the next
`make build-de` (or build-it/build-fr/build-indie — this module is generic, all
languages share it) — no data migration needed.

**How to apply**: if a future audit finds in-game text overlapping itself /
overflowing the dialogue box, especially right after a "shortened this over-long
dialogue" correction commit, suspect this exact pattern first — grep the source
combined_*.txt entry for a `\p`-delimited page with zero `\n`/`\l` inside it that is
long (>~35 chars). Verify via `rewrap()` on the raw translation string directly
(see gba_translator commit 157b984's test additions in
`tests/test_dialogue_linewrap.py::ZeroBreakOverflowTests` for the exact repro shape).

See [[unbound-fr-build-lives-in-gba-translator]], [[unbound-pattern-c-stale-snapshot-commit]].
