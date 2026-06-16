# Give-CS freeze — root cause and fix

Ticket: **« Problème pas de gain d'objet »** (T-23). After beating Zeph the
player is kidnapped, escapes, and a hillbilly NPC hands over a field-move CS; on
the French build the game **freezes** on the box « Alors, prends cette CS pour
aller le voir. » and ignores all input. English never freezes.

## How it was finally reproduced (and why earlier passes failed)

The user supplied a savestate taken **just before** the post-Zeph cutscene
(`tests/fixtures/saves/givecs_freeze.ss9`). Loading it into the built French ROM
and mashing A replays the whole kidnapping cutscene **without the RNG battle**
that had blocked every earlier headless attempt — a deterministic entry point at
last.

Mashing A reaches the give-CS box on map `46.0` and **freezes there**:

- The text printer's `currentChar` stops advancing and the screen stops changing.
- The CPU spins in the engine's **`GetStringWidth`** routine (sampled PC
  `0x08006xxx`), which walks a string one byte at a time until it reads `0xFF`.
- `gStringVar4` (the display buffer, `0x02021D18`) contains **fused, unterminated
  move descriptions** (Cut → Gust → Wing Attack → Ally Switch …) with **no `0xFF`
  in 900+ bytes**. The wrap routine at `0x089F35F8` scans forever → freeze.

This was reproduced on the *committed* "fixed" ROM, proving the earlier fix did
not hold. Earlier passes only ever inspected the give-CS box text statically
(byte-clean) or reached the box without being able to *press through* it.

## The defect (pure translation data)

The French build overwrites the move descriptions in the original English data
block at `~0x08482xxx` **in place**. A longer French description overruns its
fixed slot and destroys the next entry's `0xFF` terminator, fusing a
multi-hundred-byte run with no terminator (e.g. 720 bytes at `0x0848_2ACD`,
456 bytes at `0x0848_2BD5` = the Cut description handed out by the give-CS).

That block is referenced by **several** pointer sources:

| Reference | Used by | Earlier state |
|-----------|---------|---------------|
| `0x0899F190` | « Capacités connues » summary | relocated by `patch_move_descriptions_fr` |
| `0x08488708` | move-info table | repointed by the **first** version of `patch_dup_move_descriptions_fr` |
| `0x08904000` | a **third** move-description table | **never repointed** |
| `0x083DEA80`, `0x0887AD30` | per-field-move info structs (**give-CS path**) | **never repointed** |

The earlier fix repointed **only** `0x08488708`. The give-CS path reads the
description through the field-move struct (`0x083DEA80` → `0x0848_2BD5`), which
still pointed at the fused run — so the freeze survived a rebuild. This is the
same duplicate-pointer class as the summary-label bug: **every** copy of a
pointer must be repointed.

## The fix

`scripts/patch_dup_move_descriptions_fr.py` (run last in `make build-fr`) is now
**reference-driven** instead of table-driven:

1. Scan the whole ROM for every word-aligned pointer into the move-description
   block `[0x08482000, 0x08484000)`.
2. For each target that is *overflowing* (no `0xFF` within 160 bytes), relocate
   the authoritative French text — keyed by the entry's original ROM offset in
   `combined_fr.txt` — into free space **once** (the encoder appends `0xFF`).
3. Repoint **every** reference to that target (tables *and* field-move structs)
   to the relocated, terminated copy.

No consumer is left pointing at an unterminated string, regardless of which
table or struct reads it.

### Verification

- After `make build-fr`: **0** references into the block resolve to an
  unterminated run (>200 bytes); the give-CS structs `0x083DEA80` / `0x0887AD30`
  now point at the full, terminated French Cut description.
- **In-engine replay** from `givecs_freeze.ss9` mashes A through the entire
  cutscene and past the give-CS box with no freeze (the box closes, the player
  regains control on map `46.0`). The same replay **freezes** on the pre-fix
  build.
- Deterministic CI guard `tests/e2e/test_givecs_move_desc_freeze.py` asserts no
  block reference is unterminated — it fails on every pre-fix build (the give-CS
  struct pointed at a 456-byte fused run) and passes on the fixed build.
- Replay guard `tests/e2e/test_givecs_freeze_replay.py` exercises the real
  sequence via mGBA (skips when mGBA/toolkit unavailable).
