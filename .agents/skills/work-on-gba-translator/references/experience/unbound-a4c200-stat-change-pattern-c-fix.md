---
name: unbound-a4c200-stat-change-pattern-c-fix
description: "F-41 audit of 5 battle-string offsets flagged by Pattern C — only 0xA4C200 was a real regression, the other 4 were false positives from stale in-repo offset scanning"
metadata:
  node_type: memory
  type: project
  originSessionId: 3e2c6be6-0086-4723-9fd0-476d3d0bb179
---

Pattern C audit flagged 5 battle-string offsets as reverted by 86ed70fd6 over
cab10fa1c (14/06). Tracing the LIVE pointer (not the raw offset) in the built
FR ROM showed only **0xA4C200** was a real regression — restored to
`<0xFD><0x00> de <0xFD><0x13>\n<0xFD><0x01>` and guarded with a new
CRITICAL_LABEL entry in `scripts/check_translation_integrity.py`.

The other 4 were false positives once the live pointer was traced:
- **0x3FB7D5 / 0x3FB7EE**: dead orphan bytes (0 referrers) — the actual
  gBattleStringsTable pointers were relocated to 0x823074 / 0x16FB64, which
  already hold the correct French text.
- **0x8BD155**: dead orphan ("The wild "), byte-identical and unreferenced in
  both EN and FR ROMs — never reachable in-game (likely unused base-game
  leftover data).
- **0xA4C636**: neutralized unconditionally by `patch_battle_prefix_fr.py`
  (byte 0 forced to 0xFF post-build); the " sauvage" suffix is now appended
  AFTER the name via a Thumb code cave, so the prefix cell's source text is
  moot regardless of what combined_fr.txt says there.

**Why:** confirms [[unbound-trace-live-pointer-not-original-offset]] — a raw
offset diff against a stale commit is not proof of a live regression when the
pipeline relocates/patches strings post-build.

**How to apply:** for any future Pattern C audit hit on a battle/engine
string, decode the LIVE ROM at the offset AND search for 4-byte-LE pointer
referrers (`0x08000000 + offset`) before touching combined_fr.txt. Zero
referrers + content differs from canon = likely dead/orphaned, not a
regression. Also: rebuilding `output/roms/GenedRom-fr.gba` in a Singularity
worktree under heavy concurrent-ticket traffic can require several
prepare-fr/build-fr rebuild cycles across repeated `orchestration_pull`
rebases (binary ROM conflicts every time, `git checkout --ours` + rebuild —
see [[singularity-build-resets-worktree]]).
