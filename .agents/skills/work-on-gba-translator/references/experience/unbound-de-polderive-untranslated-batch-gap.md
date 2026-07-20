---
name: unbound-de-polderive-untranslated-batch-gap
description: "DE Polderive NPCs speaking English (#91) — whole 16-string dialogue block simply absent from combined_de.txt, not corrupted/regressed"
metadata:
  type: project
  originSessionId: 3fef068f-c5d6-47f0-9de5-48de1d7c73ad
---

Issue #91 "DE 2.1.53 Polderive — some NPCs still speak English": the 4
screenshotted lines (town intro, mud/Tessy flavor text, TM-Master sidequest)
all fell in one contiguous ROM range 0x1F52A9C–0x1F5454C, East Borrius/Polder
Town cluster. `grep` for the offsets in `languages/de/combined_de.txt` found
**zero** matches — this wasn't a translation bug, the 16 strings had simply
never been added (matches the known batch 10–12 gap from the
[[unbound-de-species-and-move-names-fixed-table-gap]]-era DE audit,
`AUDIT_DE_ROM_REPORT.md`: ~952 untranslated-English strings expected).

Workflow used, repeatable for similar "NPC speaks English" DE/IT reports:
1. Download the issue screenshots immediately (GitHub's private-user-images
   JWT URLs expire ~300s after being served — refetch the issue right before
   curl'ing, don't reuse URLs from an earlier tool call).
2. `grep` the exact English phrase (not the offset) in `languages/en/combined_en.txt`
   to get the ROM offset + neighboring entries (same NPC's other pages cluster
   at adjacent offsets — translate the whole cluster, not just the reported line).
3. `grep` that offset in `languages/de/combined_de.txt` — if absent, it's a
   missing-batch gap, not a corruption; check `languages/it/combined_it.txt` for
   an already-translated reference (IT was further along in these batches) to
   confirm the string is real, sanity-check tone, and reuse established DE
   terminology (e.g. "TM-Meister" already existed at a different offset,
   0x1F54459).
4. DE line-wrap convention in combined_de.txt: `\n`=0xFE newline, `\p`=0xFB
   page-break/clear, `\l`=0xFA scroll (documented in the file's own header
   comment, line 4). Validate width with
   `src.core.dialogue_linewrap.line_width()` (DEFAULT_MAX_LINE_WIDTH=192px)
   before inserting — don't guess wrapping by eye.
5. Insert new `0xOFFSET: text` lines in hex-ascending order (file convention,
   not required by the parser but keeps it navigable) at the correct spot
   between existing entries.
6. `make build-de` (→ `scripts/build_language.py de`) auto-relocates any
   translation longer than the original English cell to free space and
   repoints the pointer table — no manual placement needed.
7. **Verify via live pointer, not raw offset bytes**: after build, the
   original offset may still hold stale English bytes (now orphaned/dead) if
   relocated elsewhere. Find the pointer site in `englishrom.gba` (4-byte LE
   `offset+0x08000000` scan), then check what pointer value the built
   `GenedRom-de.gba` has at that exact site, decode the string at *that*
   target. This is the same pitfall as [[unbound-trace-live-pointer-not-original-offset]]
   but for freshly-added (not pre-existing) entries.

Result: 16/16 strings confirmed live-pointer-verified German in the rebuilt
ROM, 982 DE-tagged tests green, issue closed. See
[[unbound-fr-build-lives-in-gba-translator]] for why edits must land in
`gba_translator`, never in this toolkit repo.
