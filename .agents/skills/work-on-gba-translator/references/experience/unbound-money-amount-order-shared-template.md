---
name: unbound-money-amount-order-shared-template
description: "POKEDOLLAR symbol position (Trainer Card, shop, PC, bag…) is one shared rodata template at 0x41697A, not per-screen text"
metadata:
  node_type: memory
  type: project
  originSessionId: e98a84e7-c129-4893-a170-45baef425ca9
---

Every on-screen money string (Trainer Card wallet, shop, PC, mart, bag…) is built by the
engine from a **single shared template string** at file offset `0x41697A`: bytes
`B7 FD 02 FF` = `"¥" + {STR_VAR_1} + terminator` (English order: `¥1234`). Confirmed by
scanning the ROM for `0xB7 0xFD ?? 0xFF` (exactly one hit) and finding 4 pointer references
to it (`0x9b490`, `0x9fec0`, `0x9ff44`, `0x9f3e58`) — i.e. reused across call sites.

This offset is **below** the main text region (`0x1F00000-0x1F80000`), so it's absent from
`combined_fr.txt`, the injection JSON, and the Spanish extract — no translation pass ever
touches it. Official French Pokémon games print the amount *before* the currency glyph
(`1234¥`), unlike English. Fixed with a class-3 post-build patch
(`languages/fr/patches/money_amount_order.py`, wired into `make build-fr` right after
`trainer_card_date`): swap the 4 bytes to `FD 02 B7 FF` (`{STR_VAR_1}¥`) — same length as the
original, so **no pointer relocation needed**, just a byte permutation.

Byte `0xB7` = `'¥'` in this project's charmap (`src/core/text_codec.py`), rendered in-game as
the pokedollar/₽-look glyph. `STR_VAR_1` encodes as `0xFD 0x02` (`VARIABLE` prefix + index 2).

See also [[unbound-trainer-card-date-builder]] (same screen, different bug: the date order,
fixed via an ASM trampoline because that one needs reordering of variable-length pieces —
this one didn't, because both orders are byte-identical length).

**Separately**, the Trainer Card wallet *label* "Portefeuille" (wrong term, official is
"Argent") lived at TWO offsets in `combined_fr.txt`: `0x1F81E52` (the actual card label,
next to Nom/Anniversaire/Pokédex/Temps/Début de l'aventure at `0x1F81E44`+) and `0x1F21C78`
(a second identical copy, likely the Cube/quick-menu money display) — both are normal
class-1 pointer text, just needed a plain edit + full build chain (#47).
