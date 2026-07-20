---
name: unbound-make-build-fr-reuses-stale-same-day-json
description: "make build-fr silently reuses an existing same-day output/translation/[date]_translation_ready.json instead of regenerating it from a just-edited combined_fr.txt"
metadata:
  type: project
  originSessionId: f3697971-ac2b-41f6-937d-8852cf788fd0
---

Issue #80 (Zygarde cell pickup: "1 pour cent" → "1%", offset `0x791BBA`) needed
re-fixing twice in one session. First bug: the original fix (`1a3ab5e`) had no
[[unbound-protected-entries-mandatory-new-translation]] guard, so an unrelated
commit 90s later (`071c6813`, CT-box description fix) carried a stale working
copy and silently reverted the line — classic Pattern C
(docs/20_TRANSLATION_PRESERVATION.md §7, see
[[unbound-combined-fr-fixed-but-rom-never-rebuilt]]).

Second, separate bug found after re-fixing the source: `make build-fr`
(`gba_translator/Makefile`) depends on `ensure-fr-translation`, which only runs
`make prepare-fr` (regenerate `output/translation/<date>_translation_ready.json`
from `combined_fr.txt`) when **no** dated JSON exists yet or the existing one has
0 translations (`FR_TRANSLATION = $(shell ls -t .../[0-9]*_translation_ready.json | head -n1)`).
If a same-day JSON already exists (e.g. from an earlier rebuild that same day,
by this or another concurrent ticket), `make build-fr` reuses it AS-IS — even
though it predates your `combined_fr.txt` edit. The pre-commit hook's
`check_translation_integrity.py` pass only re-parses `combined_fr.txt` text and
reports green; it never decodes the actual built ROM, so this silent staleness
is invisible unless you manually decode ROM bytes (docs §5 step 6).

**Why:** the JSON filename is date-prefixed, not content-hashed, so "does a file
for today exist" is a bad proxy for "is it up to date with the latest source edit".

**How to apply:** after any `combined_fr.txt` edit, if you plan to verify or ship
the actual ROM (not just pass the manifest guard), explicitly run
`make prepare-fr && make build-fr` yourself rather than trusting a bare
`make build-fr` (or a pre-commit hook that calls it) to pick up your change —
check `ls -t output/translation/[0-9]*_translation_ready.json | head -1`'s mtime
against your edit first. Then verify the LIVE POINTER bytes in the rebuilt ROM
(trace `pointer_offsets` from `output/extracted/extracted_texts/englishrom_texts.json`
for the offset, since a too-long string is relocated — see
[[unbound-trace-live-pointer-not-original-offset]]), not just the integrity
guard's text-file report.

Also reconfirmed: this checkout is heavily concurrent (many agents share the
same `gba_translator` working tree). Before editing, `git stash push -- <files>`
any pre-existing unrelated uncommitted diff on the exact files you're about to
touch (rather than discarding it), commit your own change, then let the other
ticket's agent handle its own stash. A `git commit` that runs the slow
(~2-3 min) pre-commit hook (full pytest + fr/it/de ROM rebuilds) can still race:
in this session the commit that finished during that window landed with a
different concurrent agent's commit message while carrying MY diff content —
harmless (diff was correct and scoped), but a reminder that commit messages in
this repo aren't a fully reliable audit trail during heavy concurrency.
