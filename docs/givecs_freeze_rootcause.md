# Give-CS freeze — root cause and fix

Ticket: **« Problème pas de gain d'objet »** (T-23). After beating Zeph the
player is handed a field-move CS (Coupe/Cut) by an NPC; on the French build the
game **freezes** during the give-CS box and ignores all input, so the player
never gains the item. English never freezes.

## How it was found (in-engine, deterministically)

A savestate taken just before the post-Zeph cutscene
(`tests/fixtures/saves/givecs_freeze.ss9`) is loaded into the playable build and
the cutscene is mashed through with A. The freeze is judged by **screen hash**:
the rendered frame stays pixel-identical for many consecutive A-presses.

> **Why screen hash, not position or PC.** The player stands still during the
> whole conversation, so map/pos staying at `46.0:22,9` is *not* a freeze
> signal — a healthy multi-box dialogue looks identical to a hang by position.
> The bridge's `REGISTERS` reads the CPU inside the per-frame VBlank IRQ, so the
> PC is always BIOS `0x000001C4` whether or not the main loop is spinning — also
> useless. Only a pixel-static screen across many A-presses is a reliable freeze
> signal. Earlier passes that trusted position/PC "verified" fixes that never
> held; this is why the bug survived nine attempts.

At the genuine freeze, `gStringVar4` (`0x02021D18`) holds an **unterminated**
string (no `0xFF` within 1000+ bytes) that decodes to fused move descriptions:

> *« Une attaque de base. Elle peut être utilisée pour abattre des arb**Frappe
> l'ennemi avec une rafale de vent fouetté**… »*

i.e. the Cut description (`0x00482BD5`) run together with the next move's
description. The engine word-wraps this via CFRU's routine, which calls
`GetStringWidth` to scan byte-by-byte for the `0xFF` terminator; with no
terminator in range the scan never ends → infinite loop → freeze.

## The defect

The Cut description lives at `0x00482BD5` — an **empty `0xFF` slot in English**,
but the build writes a long French sentence there. The longer French text
overruns its slot and destroys the next entry's `0xFF`, fusing a multi-hundred
byte run with no terminator. That description is read on the give-CS path
through the **field-move structs** `0x083DEA80` and `0x0887AD30`, and the same
overflow class affects the move-info description tables `0x08488708` and
`0x08904000`. `patch_move_descriptions_fr.py` only relocates the *summary*
table `0x0899F190`, so every other consumer still pointed into the corrupted
in-place pool.

A previous fix repointed **only** table `0x08488708`, leaving the field-move
structs (the give-CS path) pointing at the unterminated run — so the rebuild
still froze. A still-earlier region-blind repoint corrupted the font table
(`0x489A08`) and a data struct (`0x489F74`) that also hold pool-range values,
and was reverted.

## The fix

`scripts/patch_dup_move_descriptions_fr.py` (run last in `make build-fr`) is
**reference-driven and strictly guarded** so no consumer is missed and no
code/data is corrupted:

1. Scan the whole ROM for word-aligned pointers into the description pool
   (`0x482000–0x48A000`).
2. Keep only those whose target is a **genuine, overflowing French description**
   — a strict text filter (letter ratio, word spacing, French vowel density, no
   single dominant glyph) that rejects the font/data tables and Thumb code that
   also point into the region.
3. Relocate one `0xFF`-terminated copy of the authoritative `combined_fr.txt`
   text per target and repoint **every** referrer to it.

A handful of pool offsets with no authoritative text are referenced only by
isolated code/data singletons (English carries the identical pointers and never
freezes), so they are left untouched — terminating them would mean relocating an
unknown-length blob, and they are not on any word-wrapped path.

## Verification

- **In-engine, both directions.** `scripts/verify_givecs_no_freeze.mts` replays
  `.ss9` and judges by screen hash. On the rebuilt ROM the cutscene completes
  (`verdict=0`, no freeze). On a ROM whose give-CS structs are repointed back to
  `0x482BD5`, it freezes (`verdict=1`) — proving the verifier catches the real
  bug and the fix resolves it.
- **`make build-fr`** runs the patch in the real pipeline: give-CS structs
  `0x083DEA80`/`0x0887AD30` resolve to a terminated copy of the Cut description.
- **Deterministic CI guard** — `tests/e2e/fr/test_givecs_move_desc_freeze.py`: no
  *clustered* pointer (table / struct array) into the pool reaches an
  unterminated French description. Red on the buggy build (the 4 give-CS struct
  cells), green on the fixed build; English satisfies it as a sanity anchor.
- **In-engine replay guard** — `tests/e2e/fr/test_givecs_freeze_replay.py` drives
  the verifier headlessly and skips cleanly when mGBA is unavailable.
