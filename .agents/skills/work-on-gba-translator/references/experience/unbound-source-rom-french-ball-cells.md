---
name: unbound-source-rom-french-ball-cells
description: "gba_translator base ROM ships the standard Poké Ball line as French inline gItems cells, so IT/DE item_names key on French not English"
metadata:
  node_type: memory
  type: project
  originSessionId: a0a70419-b93f-4be7-874f-7c3449cee991
---

The gba_translator base ROM (`input/roms/englishrom.gba`) is NOT pure English for
inline `gItems` name cells: the **standard Poké Ball line** (Poké/Great/Ultra/
Master/Safari/Net/Dive/Nest/Repeat/Timer/Luxury/Premier/Dusk/Heal/Quick/Cherish
Ball) at indices 10-21/61-71 of the table (base `0x876074`, stride 44) is shipped
**pre-localised to FRENCH** — cells decode as "Hyper Ball", "Super Ball", "Filet
Ball", "Scuba Ball", "Faiblo Ball", "Chrono Ball", "Luxe Ball", "Honor Ball",
"Mémoire Ball", "Sombre Ball", "Soin Ball", "Rapide Ball" (many general held items
too: "Orbe Vie", "Boue Noire"…). So FR is already correct; IT/DE inherit French.

Consequence for `languages/*/patches/item_names.py`: those patches rewrite a cell
only when its current string matches a dict key. For the ball line the key must be
the **French source string**, not the English name (English keys never match).
FR's `item_names.py` correctly OMITS these (its `test_french_names_differ_from_english`
forbids key==value, and the source is already French). IT/DE carry them as extra
keys FR lacks — the key-parity tests whitelist those 16 keys.

Ticket P-167's premise ("all decode as English") was wrong — verify by decoding the
built ROM, not by trusting the ticket. Fixed 2026-07-04. Park Ball (idx 61, "Parc
Ball") was left French — out of the 16-ball scope. See [[unbound-fr-build-lives-in-gba-translator]].
