# DE/IT patch-offset audit against the clean base ROM (T-38)

Follow-up to **R-17** ("Base Rom"), which replaced the shared
`input/roms/englishrom.gba` — previously a *French-patched* Unbound ROM — with
a genuinely clean vanilla base, and preserved the old file as
`input/roms/patchedfrenchrom.gba` (used only by `make build-fr`).

## Why an audit was needed

Several post-build patch scripts hard-code table offsets that were
reverse-engineered against the **old French-patched** base. That base was not
representative: the FR build had **relocated** whole fixed-width tables into
free space and **repointed** the engine's code references there. So a table the
game really reads at its stock address appeared, on the contaminated base, to
"live" at a low free-space offset. A patch that hard-codes that relocation
target writes to unreferenced free space on the clean base — a silent no-op —
while the real table keeps its English contents.

`make build-it` / `make build-de` completing without error proves nothing here:
writing to dead free space never errors.

## Method — pointer-liveness inversion

The engine reaches every fixed-width table through a 32-bit ROM pointer. If an
offset is referenced by such a pointer on the **patched** base but **not** on
the **clean** base, the table was relocated by the FR build and the hard-coded
offset is now dead. This is a mechanical, complete check:

```
scripts/audit_clean_base_offsets.py            # exits non-zero on any new inversion
```

It scans every `0x…` literal ≥ `0x100000` in `languages/{fr,it,de}/patches/*.py`
and `src/i18n/*.py` and classifies each against both ROMs:

| class | meaning | count |
|---|---|---:|
| live on clean base | table sits at its stock address → patch OK | 207 |
| dead on both bases | code/ASM site, LZ77 graphics, or a fixed-table *field* offset reached by index arithmetic — unchanged between the two bases → patch OK | 131 |
| **inverted** (live on patched, dead on clean) | relocated by the FR build → hard-coded offset is dead on the clean base | 2 |

The whole-ROM relocation map (built by diffing every word-aligned pointer
between the two ROMs) confirms the picture: **1,415** pointer sites moved, but
all except the move-name table belong to the generic builder's text-pool block
(`0x0B4xxxx` → `0x048xxxx`), which the pipeline manages itself — no patch
hard-codes those.

## Findings

### 1. `move_names.py` — BROKEN on the clean base (fixed)

- Hard-coded `MOVE_NAME_TABLE = 0x1B2980`. On the clean base that offset is
  unreferenced `0xFF` free space; the live move-name table is at its stock
  offset **0xA40A10** (41 code sites point there — the same 41 the FR build had
  repointed to 0x1B2980).
- Wired for **IT** (`languages/it/lang.yaml`). DE has no `move_names` patch.
- Symptom before the fix: IT wrote Italian move names to dead 0x1B2980 and left
  English at the live 0xA40A10 → **the whole move roster shipped in English**
  (every move menu, the Pokédex move list, the Move Relearner).
- Fix: `resolve_live_base(data)` reads the live table pointer from the ROM
  (code site `0x000308A4`) and validates the index-0 `"-"` placeholder, so the
  shared FR-core patch targets the correct cell on **either** base
  (clean → 0xA40A10, patched → 0x1B2980). Verified: patching the clean base
  with `combined_it.txt` now writes "Botta"/"Colpo Karate"/… at 0xA40A10 and
  leaves 0x1B2980 blank.
- Guards: `tests/test_patch_move_names_fr.py::TestResolveLiveBase` (unit) and
  `tests/test_move_names_clean_base.py` (rom-marked, both real bases).

### 2. `fr/item_names.py` `ITEM_DESC_OVERRIDES` `0xB40FC0` — not a DE/IT bug

- The single FR "Muscle+" item-description override at `0xB40FC0` is inverted
  the same way (item struct `0x876ECC` points there on the patched base, but to
  `0x3D604D` on the clean base).
- It is **FR-only**: `build-fr` runs against `patchedfrenchrom.gba`, where the
  offset is still live, so FR remains correct. IT's `ITEM_DESC_OVERRIDES` is
  empty and DE has no such override — so no DE/IT text is affected.
- Recorded in `REVIEWED_INVERTED` in the audit script (exit stays 0) rather
  than "fixed", because there is nothing broken. If FR item descriptions are
  ever migrated onto the clean base, revisit this entry.

## Everything else checked out

All other hard-coded offsets are either live on the clean base (their tables
never moved) or dead on both bases (code/graphics/field offsets that are
byte-identical between the two ROMs, so the patch behaves the same as it always
did). The graphics patches (`type_icons`, `status_badges`, `dexnav_headers`,
`hp_labels`, `font`), the ASM/trampoline patches (`time_format`,
`trainer_card_date`, `legendary_ritual`, `intro_questions`) and the
index-arithmetic name/description tables (`item_names` `gItems`,
`ability_names`, `nature_names`, `pokedex_categories`, `fixed_table_names`) all
target offsets that are identical on both bases.

## Reproducing / CI

```
python3 scripts/audit_clean_base_offsets.py     # 0 unreviewed inversions ⇒ exit 0
python3 -m pytest tests/test_patch_move_names_fr.py tests/test_move_names_clean_base.py
```

Run the audit after any future base-ROM swap: a non-zero exit means a patch
hard-codes an offset that is dead on the new base.
