---
name: unbound-phantom-tail-overlap-verb-buffer-corruption
description: "0x3FCB4B ('ose!') phantom extraction artifact corrupted the B-35 stat-rise verb buffer into '!ose!' once that buffer was shrunk (issue #26)"
metadata:
  node_type: memory
  type: project
  originSessionId: a9ae70f5-0834-4b2f-ae7a-804533e803a3
---

GitHub issue #26: in-battle stat-increase message rendered `"... augmente
!ose !"` / `"... augmente beaucoup !ose !"` instead of `"... augmente !"` /
`"... augmente beaucoup !"`.

**Root cause:** `combined_fr.txt` offset `0x3FCB4B` (`"ose!"`) is a dead
string-extraction artifact — binary pointer scan of `input/roms/englishrom.gba`
(search for 4-byte-LE `0x08000000+offset`) shows **zero referrers**. It exists
only because it is byte-for-byte the tail of the live string `"rose!"` at
`0x3FCB4A` (any suffix of a valid `0xFF`-terminated string is itself a
validly-terminated byte sequence, so the automated string finder picked up
both start points). Confirmed the same tail-sharing pattern in `combined_es.txt`
(`"sube"`/`"ube"`) — harmless there only by coincidence since the ES text
happens to end in the same 3 letters.

This phantom entry was harmless while `0x3FCB4A` held the full 5-byte
`"rose!"`. [[unbound-stat-change-baked-verb-b35-not-pure-buffer]] (B-35)
shrank `0x3FCB4A` to just `"!"` to fix word order — after that, the untranslated
phantom entry started writing its (still-English) text right after the `"!"`
buffer's terminator, corrupting the runtime read into `"!ose!"`.

**How to apply:** when a translated buffer/cell is intentionally shrunk (verb
baked into template, buffer reduced to 1 char), always re-check whether any
combined_fr.txt entries exist at offsets *inside or immediately after* the old
(longer) cell span — they may be phantom tail-overlap artifacts that were inert
at the old length but become live corruption once the cell shrinks. Verify with
a pointer-referrer binary scan before trusting any offset as "real", per
[[unbound-trace-live-pointer-not-original-offset]] and
[[unbound-a4c200-stat-change-pattern-c-fix]] (Pattern C zero-referrer
false-positive rule generalizes here too, just discovered the opposite way:
a zero-referrer entry causing a NEW regression instead of masking one).

Fix = delete the phantom line from `languages/fr/combined_fr.txt`, rebuild,
decode the exact byte range with `TextDecoder.decode_pokemon` to confirm.
Regression test: `tests/test_battle_stat_change_order_fr.py::test_no_phantom_entry_overlapping_rise_verb_buffer`.

Also reconfirmed: running the gba_translator worktree test suite while another
ticket's process is mid-rebuild in the main checkout causes transient
`FileNotFoundError` on ROM/JSON artifacts and flaky LZ77 pixel-diff failures —
always re-run failing tests in isolation before treating them as real; see
[[singularity-duplicate-dispatch-same-ticket-race]].
