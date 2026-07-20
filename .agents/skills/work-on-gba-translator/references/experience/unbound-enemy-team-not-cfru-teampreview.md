---
name: unbound-enemy-team-not-cfru-teampreview
description: Issue
metadata:
  node_type: memory
  type: project
  originSessionId: a3edb01b-5f68-4839-8fdb-66c70e4e0e91
---

GitHub issue #75 (gba_translator) reports an untranslated "ENEMY TEAM" label in a small
72×74px in-battle window. Confirmed NOT CFRU pointer-text: encoded "ENEMY TEAM"/"YOUR TEAM"/
"TEAM" with `src/text/encoder.encode_string` and searched the full `englishrom.gba` (32MB,
not just the extracted main-text region) — zero matches for the phrases (bare "TEAM" hits
twice, unrelated). It's a baked graphic, as the issue reporter and maintainer both suspected.

**CFRU's actual "in-battle Team Preview" (upstream `Complete-Fire-Red-Upgrade` src, GitHub
Skeli789/Complete-Fire-Red-Upgrade) was captured live via mGBA VRAM dump this session — and
does NOT match the issue's asset.** It renders the dynamic trainer name being typed out
(`gText_TeamPreviewSingleDoubleText` = "[Trainer]'s Team", e.g. "Admin Ombre Ivory") over a
240x112 two-bar background (`graphics/Battle_UI/Team_Preview/TeamPreviewInBattleBg.png`, no
baked text) — not a static "ENEMY TEAM" label. Screenshot proof:
`gba_translator/output/proofs/enemy-team-final/06-k032.png` (+ matching VRAM/palette .bin
dumps in that dir).

**How to reach and open this overlay (fully reproducible, proven this session):**
1. Copy `tests/fixtures/saves/post-zeph-pre-cs.srm` to `output/roms/GenedRom-fr.sav`, boot,
   Continue.
2. START -> 6x RIGHT (lands on "Options" icon) -> A -> 2x R (cycles to "Options de combat"
   page) -> 6x DOWN (lands on "Aperçu équipe"/Team Preview row) -> RIGHT (sets
   "Zone Combat seul." i.e. Frontier Only -> "Toujours"/Always) -> B (opens
   Sauver/Ignorer/Annuler) -> A (confirms Sauver/Save) -> 3x B (closes menu to overworld).
   **This step is mandatory** — without it, `CantLoadTeamPreviewTrigger()` (upstream
   `src/battle_indicators.c`) blocks the L-button overlay outside Battle Frontier, so L does
   nothing and every earlier probe attempt silently failed.
3. Walk DOWN repeatedly (+A) to trigger the Zeph/"Admin Ombre Ivory" battle cutscene.
4. At the action-selection screen, **press L BEFORE A each step** (pressing A first always
   advances past the action-select screen before L gets a chance — this ordering bug wasted
   several failed attempts before being found) to open the overlay.

See `gba_translator/scripts/probe_enemy_team_preview.mts` for the full working script.

**Leading unresolved hypothesis**: Unbound may render the literal "ENEMY TEAM"/"YOUR TEAM"
graphic only in the `BATTLE_TYPE_MULTI` branch (`gText_TeamPreviewMultiText`, i.e. a genuine
2-trainer Multi Battle with a partner), as a simplification instead of listing two trainer
names/classes at once. **Still untested (follow-up session, 2026-07-08) — genuinely blocked,
not just "no savestate on hand":**

- Unbound's ONLY `BATTLE_TYPE_MULTI` fights are in Daherapolis' postgame facilities — Tour de
  Combat ("Salle Multi", `combined_fr.txt` `0x1F8F690`-`0x1F9419A`) and Cirque de Combat
  (`0x1F8A917`-`0x1F8ADD8`). Both require talking to the guide NPC then picking/linking a
  partner in a "Salon de Combat" before the fight starts — this is deep postgame content, not
  reachable from a fresh save in any reasonable number of automated key-presses.
- Exhaustively searched (2026-07-08): every `.sav`/`.srm`/`.ss1-9` in `gba_translator`
  (all early/mid-game, see `tests/fixtures/saves/README.md`), no debug menu / warp tool /
  GameShark code anywhere in the repo, and the only `writeMemory()` cheat
  (`scripts/repro_give_cs.mts`'s HP-pin) is documented unsafe (corrupts RAM → black screen) —
  do not repurpose it to fake progress flags.
- **Conclusion: producing this fixture needs an actual playthrough** (manual, ~15-30min from a
  late save, is far faster than any automated approach) to Daherapolis with a partner chosen,
  saved right before entering the Salle Multi. Tracked in follow-up ticket **T-39**.
- Both `probe_enemy_team_multi_battle.mts` and `probe_enemy_team_preview.mts` are NOW genuinely
  on the mainline `unbound` branch (commit `980703f`, 2026-07-08). Earlier note here claimed
  they were on `unbound` but they were actually stranded on the unmerged F-116 worktree branch
  (`worktree/f-116-…`) and NOT in `unbound` HEAD — that gap is closed.
- The multi-battle probe's walk-to-facility `TODO` is COMPLETE, done the only correct way while
  the fixture is still absent: the fixture-specific button path (save landing spot → first Multi
  Battle turn) is now supplied at RUNTIME as data, not hard-coded — via `$MULTI_WALK` or a
  `<fixture>.walk.txt` sidecar (syntax `KEY [repeat] [holdFrames] [advanceFrames]` per line,
  `#` comments, `;`/newline separators). Probe is runnable-on-arrival: drop the `.srm` (+ optional
  walk sidecar) and rerun, no code edit. Fixture-guard exits 3 when the save is absent (verified).

**Why:** Whoever picks this up next should NOT re-derive the option/L-press sequence (that
cost most of a session), should not re-test the 1v1 CFRU overlay (proven not it), and should
NOT attempt a blind automated playthrough to Daherapolis (impractically long, high freeze risk
per `diagnosing-unbound-freezes`) — get a human-provided save instead (T-39), then just fill in
the `TODO` walk section of `probe_enemy_team_multi_battle.mts` and rerun it.

**How to apply:** Once T-39 delivers `tests/fixtures/saves/pre-multi-battle-daherapolis.srm`,
run `probe_enemy_team_multi_battle.mts`. If the overlay still doesn't match, the graphic is
likely wholly custom Unbound code with no upstream CFRU analog, requiring a byte-level VRAM
diff sweep across many battle types rather than reasoning from CFRU source.

See also [[unbound-hp-pv-label-graphics-blocks]], [[unbound-type-icons-are-graphics]],
[[translating-unbound-skill]].
