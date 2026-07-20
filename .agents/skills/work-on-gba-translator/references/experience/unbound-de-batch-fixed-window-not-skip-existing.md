---
name: unbound-de-batch-fixed-window-not-skip-existing
description: "German translation batches (F-71/72/73…) use FIXED combined_fr windows, NOT the ticket's --skip-existing command which silently shifts boundaries and creates gaps"
metadata:
  node_type: memory
  type: project
  originSessionId: 49ad3920-9568-4d47-bfc7-466dce34a5ff
---

The 12-batch DE translation (`languages/de/combined_de.txt`, tickets F-71 batch1 …
F-73 batch3 …) must use **fixed windows**: batch N = `list_fr_entries_batch.py N`
= dedup'd sorted combined_fr offsets `[(N-1)*2000 : N*2000]`, run WITHOUT
`--skip-existing`.

**Trap:** the ticket text says to run `list_fr_entries_batch.py 3 --skip-existing
languages/de/combined_de.txt`, but the script recomputes batch boundaries AFTER
the skip filter. With batches 1-2 already in combined_de, `--skip-existing`
shifts batch 3's start from 0x41EC12 to 0x7FB9A1 (past even fixed batch 4),
leaving 0x41EC12–0x7FB99F uncovered. Verified batches 1 & 2 actually landed the
FIXED windows (batch1 done=1871 of window[0:2000]; batch2 done=1767 of
[2000:4000]), so mirror that. Confirm 0 overlap with combined_de before appending.

**Why:** run-order-independent, gap-free, non-overlapping coverage across the 12
tickets — the docstring's own stated goal, which `--skip-existing` violates.

**How to apply (batches 5-12):** `python3 scripts/list_fr_entries_batch.py N`
(no skip), assert extracted offsets ∩ combined_de == ∅, translate FR→DE, then
validate token parity per offset ({...}, `<0xNN>`, `\n`/`\l`/`\p` counts, the
glyph glued after `{COLOR}`) and full coverage (each offset translated OR
excluded, none dropped) before appending under a `# --- batch N/12 ---` marker.
Build gate: `python3 scripts/build_language.py de`. Move-description offsets
(~0x484xxx) stay in the file but are NOT injected yet — DE has no dedicated
move-desc table pass (see [[unbound-move-descriptions]]); expected, not a defect.
rtk breaks pytest → run via `rtk proxy python3 -m pytest`. See
[[unbound-multilang-build-registry]], [[unbound-fr-toponym-canon]] (DE toponyms
deferred to a dedicated pass).

**Batch 4 (F-74, 2026-07-03) — escape-drift is the norm, budget a fix pass:**
10 parallel 200-entry subagents reliably drift `\n`/`\l` counts UP vs FR (German
verbosity → they add extra mid-paragraph line breaks; `\p` page-break count stays
correct). Batch 4 measured 30/1956 translated entries drifted (+1 to +5 escapes)
and 1 entry got a spurious extra `{COLOR}` pair around an untranslated-in-source
badge name. Fix recipe that worked: write a single Python validator (regex count
`{...}`/`<0xNN>`/`\n\l\p` per offset, diff FR vs DE) right after the translate
pass, dump every mismatch to one file, dispatch ONE dedicated fix-agent (not one
per chunk) with explicit per-entry FR/DE/target-count context and the rule
"merge excess `\n`/`\l` into a space, never touch `\p` or tokens" — it hit the
exact FR count on 30/30 in one pass. Re-run the same validator after merging
fixes back before appending; expect 0 problems only after this second pass, not
the first.

**Batch 9 (F-79, 2026-07-04) — do NOT "normalize" `\n`/`\l`, match FR verbatim:**
same 10×200 recipe. Post-translate validator flagged 11/2000 real mismatches:
4 were `{COLOR}` closing-glyph drift (agents wrote color `Ç` where FR has reset
`Ë`) — fix deterministically by copying FR's glyph sequence positionally onto the
DE `{COLOR}` tokens when the `{COLOR}` count matches (pure control selector, never
content). 7 were `\n`/`\l` drift. TRAP I hit: I "normalized" breaks assuming the
Gen III rule "first break per page = `\n`, rest = `\l`" — WRONG, it corrupted 87
previously-correct entries. FR freely uses `\n\n` (two newlines, no scroll) in
3-line boxes; `\l` is only for actual scrolling. FR is the authority — match its
break-token sequence position-for-position, never derive it. Fix the few drifted
entries by hand (single `\n`↔`\l` swaps or minor re-split so DE's per-page break
sequence equals FR's). Validator profile per offset: sorted `{...}` multiset,
sorted `<0xNN>` multiset, `\n`/`\l`/`\p` counts, and `{COLOR}` glyphs IN ORDER.
Do NOT check the glyph after `{PAUSE}` — it's just the next word's first letter
(false positive). Batch 9 window = fixed `combined_fr` sorted-offset `[16000:18000]`
= offsets 0x1EF11A0–0x1F21F21, 0 overlap with combined_de, all 2000 translatable
(0 excluded, all dialogue/sign/mission text). Build gate passed (11422→ replaced,
0 failed, 0 collisions); nature_names no longer blocks (B-158 fix in base). Pull
conflicted at file tail with a concurrent "FR-leftover item/TM descriptions"
ticket (offsets 0x7b/0xb ranges, disjoint) → resolve as a clean union (strip the
3 conflict-marker lines, keep both blocks), rebuild to confirm.

**Don't trust `too_long: true` in the translation JSON or a raw byte-offset ROM
read as a failure signal** — almost every DE entry gets flagged `too_long`
(German > French/English length) and the generic builder auto-relocates via
`--allow-relocate`; reading the *original* offset in the built ROM then shows
stale English (the string moved, the pointer was updated, nothing overwrote the
old bytes). This reproduces [[unbound-trace-live-pointer-not-original-offset]]
inside the DE pipeline specifically — to verify injection, find the pointer
referrer site(s) in the EN rom (`scan for 4-byte LE pointer == offset+0x08000000`),
read the same site in the DE rom, and decode at *its* target, not the reported
offset. Also: ä/ö/ü are silently transliterated to a/o/u in the built ROM
(charmap has no umlauts) — this is a known DE-track limitation, not a bug to fix
here.
