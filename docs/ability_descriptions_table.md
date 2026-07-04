# Ability descriptions: the real table (CFRU/Unbound)

_Investigation output for ticket P-171 (ability-descriptions slice)._

## TL;DR

| | Address (file offset) | VA | Notes |
|---|---|---|---|
| **Ability-DESCRIPTION pointer table** | **`0x96DE04`** | `0x0896DE04` | 293 × 4-byte LE pointers, **indexed by ability ID**, 1:1 with the name table |
| Ability-NAME table (reference order) | `0xA36398` | `0x08A36398` | stride 17, index 0 = `-------`, last = `Royal Roar` (see `ability_names.py`) |
| ❌ Originally-claimed desc offset | `0xA37D00-0xA40000` | — | **Wrong.** Free-space relocation pool *above* the name table |
| Vanilla (short) copy of the desc table | `0x24FB08` | `0x0824FB08` | Aligns for low IDs, junk past ~77 vanilla abilities — **not** the live table |

## Why `0xA37D00` is wrong

`0xA37D00` sits **above** the ability-name table (which ends at `0xA376FC`).
That whole region is the generic builder's free-space pool where the injector
relocates Pokédex flavour text and move descriptions. Decoding it in both
`input/roms/englishrom.gba` and any built ROM shows the same relocated
move/Pokédex fragments — writing localized ability text there corrupts whatever
the free-space allocator happened to place in that build. There is **no**
ability-description data at `0xA37D00`.

## The real table

Ability descriptions are **pointer-referenced**, not a fixed-stride block:

```
gAbilityDescriptionPointers @ file 0x96DE04 (VA 0x0896DE04)
  [ability_id] -> 32-bit LE ROM pointer -> 0xFF-terminated description text
```

Entry *i* is the description for the ability whose name is at
`0xA36398 + i*17`, so the table is **1:1 index-aligned with the ability-name
table in canonical Gen-3 ability-ID order**. Verified anchors:

| ID | Name | Description | Text VA |
|---|---|---|---|
| 0 | `-------` | `No special ability.` | `0x0824F3C4` |
| 2 | Drizzle | `Summons rain in battle.` | `0x0824F3F2` |
| 26 | Levitate | `Not hit by Ground attacks.` | `0x0824F61F` |
| 100 | Unseen Fist | `Contact moves bypass Protect.` | `0x08A3623A` |
| 250 | Ice Face | `Free physical hit. Hail renews.` | `0x08A360FB` |

The description **text** is scattered across several free-space pools
(`0x0024Fxxx`, `0x00A34F61-0x00A36395` just below the name table, `0x0092xxxx`,
`0x00D1xxxx`, …) — consecutive abilities' pointers jump between pools. This is
why the descriptions can only be reached through the pointer table and a
stride-based patch is impossible.

## Coverage

~255 / 293 abilities carry a real English blurb. The ~30 highest-ID
Unbound-custom abilities (Air Lock, Vital Spirit, and the brand-new
`Sound Waves`, `Icy Skin`, `Dusty Scales`, `Crabby Tactics`, `Face Shield`,
`Royal Roar`, …) point into late/compressed pools with **no authored English
description** — their pointers decode as garbage. Any future localization patch
must skip these (same policy as the move-name overflow skip).

## Localization status

`combined_it.txt` and `combined_fr.txt` contain **zero** ability-description
entries today — the blurbs were never authored for IT/FR, so there is nothing to
"align 1:1" yet. The parent ticket's assumption that IT already has
ability-description text recorded (at the wrong offset) is **false**.

A future `patch_ability_descriptions_<lang>.py` would be a **relocate-and-repoint
patch driven by the `0x96DE04` pointer table** (like `move_descriptions.py`),
NOT an in-place write at the dead `0xA37D00` offset.

## Reproduce / verify

```bash
python3 languages/en/tools/locate_ability_descriptions.py --rom input/roms/englishrom.gba
```

Regression guard: `tests/unit/en/test_ability_description_table.py` (ROM-gated).
