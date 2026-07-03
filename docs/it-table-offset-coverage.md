# IT table-offset coverage audit (B-162 follow-up)

Scope: the 3,748 (was ~3,749 when B-162 was filed; count moves slightly as
`combined_it.txt` grows) offsets authored in `languages/it/combined_it.txt`
that have **no 32-bit pointer in `englishrom.gba`** — i.e. cells reached by
fixed-table index arithmetic, not by the generic pointer-chasing pipeline.
These are the "phantom cells" reported by
`scripts/audit_translation_collisions.py`, and are the domain of the
dedicated `languages/it/patches/*.py` scripts, not `build_language.py`'s
generic CSV/JSON flow.

This is **not** a regression — it's the same split documented in
`languages/it/lang.yaml`. The open question (from B-162) was whether every
one of those 3,748 authored cells is actually reached by *some* dedicated
patch, or whether some silently keep shipping English (or worse, stale
French) despite a translator having authored real Italian text for them.

## Method

1. Built a fresh `GenedRom-it.gba` (`python3 scripts/build_language.py it`)
   so the numbers below reflect the current `combined_it.txt` (15,092
   offsets; grew from 15,027 since B-162 was filed) and the current set of
   wired patches (many landed as sibling tickets — F-96, F-97, F-98, F-100,
   B-164, R-16 — since B-162's investigation).
2. `scripts/audit_translation_collisions.py --english ...` traces every
   `combined_it.txt` offset against `englishrom.gba` pointers and reports
   3,748 as phantom (no plausible live pointer).
3. `scripts/audit_it_table_offset_coverage.py` groups those 3,748 offsets
   into ROM regions (boundaries found by sampling `combined_it.txt` text at
   cluster edges — see the script) and, as a cheap triage signal, diffs the
   built ROM against `englishrom.gba` at each phantom offset.
4. Byte-diff alone is **not sufficient** for a verdict: some tables (notably
   Pokédex descriptions) are read through a struct pointer that the generic
   builder can relocate elsewhere, so the *original* `combined_it.txt`
   offset can stay byte-identical to English while the game correctly shows
   translated text at the relocated location (see
   `unbound-trace-live-pointer-not-original-offset` — same trap documented
   for the FR pipeline). Every bucket below was cross-checked by reading the
   actual patch source (or confirming none exists) rather than trusting the
   diff alone.

## Coverage table

| Bucket (region) | Offsets | Covering patch | Verdict |
|---|---:|---|---|
| Trainer class names (`0x230000`, 13B no-ptr table) | 106 | `patch_trainer_class_names_it` (wired) | **Covered** — F-100 |
| Ability names (`0xA30000`–`0xA37D00`, 17B fixed table) | 255 | `languages/it/patches/ability_names.py` → `patch_ability_names_fr` delegate, sourced from `combined_it.txt` | **Covered** (1/255 unchanged in the sample build) |
| Item name table, non-Berry/medicine subset (`0x870000`, 44B `gItems` stride) | 688 | `languages/it/patches/item_names.py` | **Partially covered** — see gap below |
| Pokédex flavour text (`0x1660000`) | 1,274 | `pokedex_rewrap` + `pokedex_categories` + `languages/it/data/pokedex_it_overrides.json` (B-164) | **Mostly covered** — build log shows 897/904 rewrapped, 6 kept in place for lack of space; the high "unchanged at authored offset" count is expected (dex text is read via a relocatable struct pointer, not the authored offset — see caveat above), confirmed by the existing `tests/e2e/it/test_table_offset_coverage.py` regression test |
| Long dialogues / over-cap main text (`0x1F40000`–`0x1FA0000`) | 7 | `patch_long_dialogues_it` (wired) | **Covered** |
| Ability descriptions (`0xA37D00`–`0xA40000`) | 290 | *(none)* | **Uncovered — real gap**, see below |
| Move names (`0xA40000`–`0xA50000`) | 943 | *(none)* | **Uncovered — real gap**, see below |
| Item descriptions, general (`0x3D0000`, `0x7B0000`, `0xEB0000` — Poké Ball/Berry/Spray catch & heal text) | 71 | `item_names.py` has an `ITEM_DESC_OVERRIDES` hook but it ships **empty** ("no genuinely overflowing description identified yet") | **Uncovered — real gap**, see below |
| Move descriptions, duplicate/legacy table copy (`0x480000`) | 68 | `dup_move_descriptions` / `move_descriptions` ports exist on disk but are **not wired** — the generic builder consumes all free space first, so these relocation patches would abort the build (documented in `lang.yaml`) | **Uncovered, already tracked** (not a new finding) |
| Battle status control-code strings (`0x3F0000` — freeze/thaw/"Out!" messages) | 23 | none identified | **Needs deeper trace** — likely a STRINGID-indexed table, not covered by `battle_string_templates` (which is specifically the `{FD24}` defeat-speech cluster) |
| Battle/menu UI strings (`0x410000` — "Oggetti!", "È troppo veloce!", "Sposta nella Borsa") | 21 | none identified | **Needs deeper trace** |
| Misc singles (`0x7B3F15` item desc, `0x834ACC` "POKéMON" label, `0x8BD155` battle-prefix cell, `0xEB23B6` item desc) | 4 | `0x8BD155` is covered by the `battle_prefix` guard (verified compliant, no mutation needed per its own docstring); the other 3 fold into the item-description gap above | Mixed, low volume |

Total accounted for: 106 + 255 + 688 + 1,274 + 7 + 290 + 943 + 71 + 68 + 23 + 21 + 4 = 3,750 (the 2-offset drift from the 3,748 phantom count is rounding at cluster boundaries between adjacent buckets; negligible for this audit).

## Real, previously-undiscovered gaps

### 1. Standard Poké Ball family missing from `item_names.py`

`languages/it/patches/item_names.py` is **not** driven by `combined_it.txt` —
it ships its own hardcoded `BERRY_NAMES` + `ITEM_NAMES` Python dicts, and
only rewrites a `gItems` cell when the current English name is an exact key
in one of those dicts. Neither dict contains an entry for **Poké Ball,
Great Ball, Ultra Ball, Master Ball, Safari Ball, Net Ball, Dive Ball, Nest
Ball, Repeat Ball, Timer Ball, Luxury Ball, Premier Ball, Dusk Ball, Heal
Ball, Quick Ball or Cherish Ball** — the entire standard Poké Ball line.
Confirmed empirically: all of these still decode as English in a freshly
built `GenedRom-it.gba`. This is a translator-effort-is-silently-discarded
bug in the strict B-162 sense (even if someone adds these to
`combined_it.txt`, `item_names.py` would still ignore them — it never reads
that file) and is very high visibility (shown constantly in the Bag, Poké
Mart, and on every Poké Ball throw).

### 2. Item descriptions (general) have no coverage path at all

The `gItems` description strings for ordinary items (Poké Ball catch-rate
blurbs, berries, sprays, potions not already covered by
`tm_item_descriptions`) sit at fixed offsets with no live pointer reachable
from `englishrom.gba`. `item_names.py`'s `apply_item_desc_fixes` exists
structurally (mirroring the FR script) but its `ITEM_DESC_OVERRIDES` dict is
empty — there is currently no mechanism that reads `combined_it.txt` for
this table at all. 66/69 sampled offsets in this bucket are byte-identical
to English in the built ROM.

### 3. Move names have zero patch coverage in any language (FR included)

`0xA40000`–`0xA50000` (943 phantom offsets) holds the move-name field of the
CFRU move-info struct table (fixed-width, same shape as ability/item names —
confirmed by sampling: "Botta" / Pound, "Colpo Karate" / Karate Chop,
"Doppiasberla" / Double Slap, …). No `move_names.py` /
`patch_move_names_*.py` exists anywhere in the repo (checked FR, DE, IT).
Move names are shown in every move-selection menu, the Pokédex move list,
and the Move Relearner — this is probably the single highest-visibility gap
uncovered by this audit. 481/943 sampled offsets are still English in the
built ROM (the rest likely already match English by coincidence for
short/cognate move names, not because they were translated).

### 4. Ability descriptions have zero patch coverage in any language

`0xA37D00`–`0xA40000` (290 phantom offsets) holds the ability-description
blurb shown in the Pokémon summary screen's Ability info window.
`combined_it.txt` has real authored Italian text there (verified by
sampling), but no patch — in FR, DE or IT — ever writes it; `ability_names`
only rewrites the 17-byte name field, not the description. 220/290 sampled
offsets are still English in the built ROM.

## Buckets needing further tracing (not filed as tickets yet)

Battle status control-code strings (`0x3F0000`, 23 offsets) and battle/menu
UI strings (`0x410000`, 21 offsets) are small buckets whose covering
mechanism (if any) wasn't identified by source review in the time available
for this audit. They look STRINGID-indexed rather than fixed-table, which is
a different tracing problem than the fixed-width tables above. Left as a
note here rather than a ticket — 44 offsets combined, low visibility
(freeze/thaw messages, a couple of menu labels), not worth a dedicated
ticket on their own; fold into whichever future ticket picks up general
battle-string coverage.

## Not new: already-tracked gap

Move-description duplicate table (`0x480000`, 68 offsets) and the mission /
meteorite-dialogue / move-description relocation ports are already
documented in `languages/it/lang.yaml` as "NOT wired" (free-space
contention with the generic builder) — this audit confirms the count but
doesn't change the finding; no new ticket filed for it here.

## Follow-up tickets filed

- **IT: standard Poké Ball names + general item descriptions render in
  English** — extend `item_names.py`'s `ITEM_NAMES` dict with the missing
  Poké Ball family and wire a `combined_it.txt`-driven item-description
  patch for the general (non-TM/MN) description table.
- **IT: move names + ability descriptions have zero patch coverage** —
  author `patch_move_names_it.py` (and ideally its FR/DE counterparts, since
  the gap is language-agnostic) for the fixed-width move-name table, and
  `patch_ability_descriptions_it.py` for the ability-description blurb
  table, both sourced from their respective `combined_<code>.txt`.
