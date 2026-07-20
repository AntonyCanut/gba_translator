---
name: unbound-trainer-class-collecteur-chineur-width-fix
description: "Issue #121 asked for Collecteur→Collectionneur (Volcan Cendré trainer class); shipped as Collecteur→Chineur instead because Collectionneur overflows the fixed 13-byte cell"
metadata:
  node_type: memory
  type: project
  originSessionId: 23a9a5eb-a5ed-41a7-8236-4e813efb08a9
---

Issue #121 requested the trainer class name at `0x23E787` (Volcan Cendré) go from
"Collecteur" to "Collectionneur". That word is 15 bytes encoded; the trainer-class
name table there is a raw fixed-width cell capped at 13 bytes (same table family as
[[unbound-trainer-vs-screen-name-raw-table]]). `build-fr`'s own overflow guard
silently leaves the cell untouched when a translation doesn't fit — so a naive
`combined_fr.txt` edit to "Collectionneur" commits fine, passes review, but the
ROM byte-for-byte keeps the OLD value forever, with only a build-log warning
("N trainer classes overflow the 13-byte cell") as a trace.

**Why:** shipped "Chineur" (7 bytes) instead — same "seeks out/hunts for items"
connotation as "collector", fits the cell, verified by direct byte-decode of the
built ROM at that offset (not by trusting the build log or the source-file diff).

**How to apply:** for ANY trainer-class / fixed-cell name fix in this table
family, after editing `combined_fr.txt`, rebuild and grep the build log for
"trainer classes overflow the 13-byte cell" — if the target offset is listed,
the fix did not land; pick a shorter synonym and re-verify by decoding the
actual ROM bytes at that offset, not just re-reading the source file. Never
trust "the commit changed the text" as proof the ROM changed — see also
[[unbound-nopointer-inplace-budget]] for the general in-place-cell pattern, and
[[singularity-binary-rom-rebase-deadlock-merge-ours-driver]] for a related trap
(a stray `merge=ours` driver on the ROM path can *also* silently discard a
correct fix during rebase, with zero conflict reported).
