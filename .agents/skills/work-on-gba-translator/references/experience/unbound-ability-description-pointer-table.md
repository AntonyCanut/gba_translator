---
name: unbound-ability-description-pointer-table
description: "Real ability-description table = pointer array @ file 0x96DE04, NOT the claimed 0xA37D00 free-space pool"
metadata:
  node_type: memory
  type: project
  originSessionId: 0ada363c-7472-4cbc-b5c0-b065e5e39c09
---

Ability DESCRIPTIONS in Unbound/CFRU live behind `gAbilityDescriptionPointers`
at **file offset 0x96DE04** (VA 0x0896DE04): 293 × 4-byte LE ROM pointers,
**indexed by ability ID**, 1:1 aligned with the ability-NAME table at 0xA36398
(stride 17, see [[unbound-ability-names-fixed-table]]). The description *text* is
scattered across many free-space pools (0x24Fxxx, 0xA34F61-0xA36395 just below
the names, 0x92xxxx, 0xD1xxxx…) — reachable ONLY through the pointer table, no
fixed stride.

**The ticket-claimed 0xA37D00-0xA40000 is WRONG** — it's the builder's
free-space relocation pool (relocated Pokédex/move blurbs), sitting *above* the
name table. A shorter vanilla copy of the pointer table also survives at
0x0824FB08 (aligns for the ~77 FireRed IDs, junk after) — not the live table;
reject it with a high-ID anchor when locating.

~255/293 abilities have authored English blurbs; the highest-ID Unbound-custom
abilities (Sound Waves, Royal Roar, …) point to junk = no description.
`combined_it.txt`/`combined_fr.txt` author **zero** ability descriptions today,
so there's nothing to inject/align yet — a future patch would be
relocate-and-repoint driven by this table (like move_descriptions.py), never an
in-place write at 0xA37D00.

Locator + regression guard shipped in gba_translator:
`languages/en/tools/locate_ability_descriptions.py`,
`tests/unit/en/test_ability_description_table.py`, `docs/ability_descriptions_table.md`.
Method = encode a distinctive blurb ("Summons rain in battle." = Drizzle),
byte-search the ROM, walk the table, prove 1:1 vs names — same as
[[unbound-move-names-real-table-vs-legacy-offset]].
