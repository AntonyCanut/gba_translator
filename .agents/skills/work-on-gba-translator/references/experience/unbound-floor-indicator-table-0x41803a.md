---
name: unbound-floor-indicator-table-0x41803a
description: "Floor-indicator popup (1F/2F/B1F...) untranslated — table at 0x41803A-0x418069, class-1 pipeline fix (issue"
metadata:
  node_type: memory
  type: project
  originSessionId: e9fffe42-f6e5-4fd7-80a4-f52bfd1e55d5
---

The small floor-change popup shown in caves/buildings (1F, 2F, B1F...) was rendering in
English (GitHub issue #27, `gba_translator`). Root cause: a 15-entry pointer-based string
table at EN ROM offsets `0x41803A`-`0x418069` (`1F,2F,...,11F,B1F,B2F,B3F,B4F`, each reached
by its own 4-byte pointer — several duplicate pointer tables exist for ascending/descending
lookups) was simply **never extracted** into `combined_fr.txt` — absent entirely, not
commented out or misclassified. Confirmed class 1 (pipeline-reachable) because the very next
cell at `0x41806D` ("ROOFTOP"→"TOIT") was already translated via the normal pipeline.

Fix: added the 15 offsets directly to `languages/fr/combined_fr.txt` (lowercase living
block) — `1F`→`RDC`, `2F..11F`→`1E..10E` (n → (n-1)E, per the issue's requested pattern),
`B1F..B4F`→`-1..-4` (French elevator convention for basement levels, generalizing the
issue's "-1" suggestion over "SS"). Ran the full build chain
(`apply_combined_fr.py --extend` → `09_csv_to_json_v2.py --allow-too-long` → `make build-fr`)
and verified by decoding the built ROM's pointer tables at `0x3F5B44`-`0x3F5B7C` (and the
mirrored descending/legendary-ritual-adjacent tables at `0x3F5BFC`+, `0x3DFEC0`, `0x3E0228`,
`0x3E0230`, `0x3E0238`) — all resolve to the French text now.

**Why this matters beyond this ticket:** a fresh worktree from `orchestration_prepare_worktree`
has no generated build artifacts (`output/translation/*.csv/json`, `output/extracted/`,
`output/differences/`) since they're gitignored. `apply_combined_fr.py --extend` needs the
dated trilingual CSV and the English/Spanish extraction JSON to exist. Fix: copy the dated
CSV from the main checkout (`output/translation/2026-01-15_trilingual_translation.csv` at
time of writing) into the worktree, and **symlink** (not copy — they're ~700MB/650MB)
`output/extracted` and `output/differences` from the main checkout, matching
[[unbound-worktree-generic-build-artifact-reuse]]. Verify the worktree's base commit matches
the main checkout's HEAD first (`git log --oneline -3` in both) so the copied CSV state is
compatible with the worktree's `combined_fr.txt`.

Added a regression test `tests/test_regression_texts.py::test_floor_indicators_translated_fr`
that decodes the built-ROM pointers directly (pattern: read pointer → follow to string →
decode with CFRU charmap), matching the file's existing convention for pipeline-driven
(class-1) fixes — as opposed to the dedicated-patch-script tests used for class-2/3 fixes.

Also note: this project's `make test` (`test-python-fast`) filters
`-m "not slow and not stress and not emulator and not rom"` — running bare
`pytest tests/ --ignore=... --ignore=...` without that marker filter picks up
`tests/stress/test_soak.py` (100k-frame mGBA emulator soak test), which gets SIGKILLed in
this sandboxed environment regardless of any code change. Always run the exact Makefile
`test-python-fast` command, not a hand-rolled pytest invocation, to avoid a false regression
signal from that stress test.

**Correction after a rebase-conflict rebuild:** the CSV-copy approach above is stale advice —
[[unbound-prepare-fr-bypasses-csv-step]] is right, use `make prepare-fr && make build-fr`
directly (no CSV needed at all). Only symlink `output/extracted/extracted_texts/*.json`
(EN/ES/FR-base extractions) from the main checkout into the worktree; `make prepare-fr`
regenerates `output/translation/<date>_translation_ready.json` straight from
`combined_fr.txt`. Re-extraction writes *through* the symlink into the main checkout's real
file (same ROM bytes -> same content, harmless, but don't be surprised by the main checkout's
mtime changing).

**Reopen (#100, 2026-07-17) — build non-determinism was the "lost translation":** the
floor strings at `0x41803A-0x418069` are reached by **six** duplicate pointer tables
(EN pointer slots at `0x3dfeb8`, `0x3e0228`, `0x3f5b44`, `0x3f5bfc`, `0x3f5c5c`, `0x3f5cec`;
42 slots total). Because every FR label is longer than EN, the build relocates + repoints all
six. That relocation was fragile: walking every ROM-build commit showed the floor popup
flip-flopping FR↔English across consecutive same-day rebuilds (07-06), and one build
(`d40dbc31`, 07-14) merged `RDC`+`1E` → `RDC1E` (dropped `0xFF` terminator) at 3 of the RDC
slots. Diffing two consecutive builds = ~9,200 differing regions → the whole free-space layout
reshuffles each rebuild; floors (short, deduped, packed) are the fragile victim. The
`201eee4d` deterministic-rebuild fix stabilized it; current HEAD has all 42 slots French.
Also: the `0x3FE9A9` inline "1F/2F/…" table (referenced by ZERO 32-bit pointers, count 0) is a
**dead copy** — the earlier #100 "fix" wrote combined_fr entries there but they never reach the
ROM (still English `1F`), and it is NOT the displayed table. Guards added: a pure-unit test
`tests/unit/fr/test_floor_indicators_fr.py` pinning the 15 living-block entries in
`combined_fr.txt` (runs in the fast suite, catches source drops + `RDC1E` merge), and a new
`test_regression_texts.py::test_floor_indicators_translated_all_pointer_tables` walking all six
pointer tables (catches per-table repoint drops the single-table smoke check missed).
Note: this repo's `.githooks/pre-commit` **rebuilds all 3 ROMs (fr/it/de)** on every commit
(>5min) — run `git commit` in the background, then `git checkout -- output/roms/` to drop the
non-deterministic rebuild drift for a test-only change. Worktree also needs
`ln -s <main>/emulator-web/node_modules` (vitest gap, see [[unbound-worktree-emulator-web-node-modules-gap]]).

**Verification pitfall — decode the LIVE pointer target, not the original offset:** once
`make build-fr` relocates a string (original cell too short for the FR translation, e.g.
`1F`→`RDC` needs 1 more byte), the bytes AT `0x41803A` in the built ROM stay the stale
English `1F` forever — the pointers get repointed to a new free-space address instead. Naively
`decode_pokemon` on the original offset after a rebuild reports a false regression. Correct
check: find the pointer bytes (`08000000 + offset`, little-endian) in the pre-build source
ROM, read the (possibly different) 4-byte value at that same file position in the *built*
ROM, then decode from `value - 0x08000000`. This bit twice: once originally (verified via live
pointer, correctly), and again during a rebase-conflict ROM rebuild where re-checking the raw
offset briefly looked like a regression.
