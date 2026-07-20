---
name: unbound-cube-sort-menu-no-pointer-silent-drop
description: Cube item-pocket sort menu (issue
metadata:
  node_type: memory
  type: project
  originSessionId: 5e8b925d-77e5-4d7d-8022-c50d33892910
---

Cube "Sort this pocket's items how?" / Type / Amount / "Sort items by X?" /
"Items sorted by X!" cluster at 0xA4E047-0xA4E0AF: `combined_fr.txt` already
had French translations for all 5 offsets, but the built ROM kept shipping
English. Root cause: a live-pointer search of the built ROM found **no**
pointer to any of these 5 addresses, while the neighboring Type/Nom/Plus/Moins
cells in the *same* table (0xA4E065-0xA4E090) do have live pointers and were
already correctly French. Without a pointer to update, the reinjection pass
can't relocate a longer FR string, so it silently keeps the EN original —
same failure class as `options_footer.py`/`status_abbrevs.py`.

Fix shipped: `languages/fr/patches/cube_sort_menu.py`, a dedicated post-build
in-place patch (wired into `make build-fr`) writing byte-exact FR text that
fits the original tightly-packed slot (no free space between these strings —
verified byte budget per offset before picking words, e.g. "Amount"→"Nombre"
had to be ≤6 chars).

**Why:** `combined_fr.txt` having a translation is NOT proof it reaches the
ROM — always verify with a live-pointer search (`rom.find(struct.pack('<I',
0x08000000+offset))`) before assuming a "missing translation" bug is just an
untranslated entry. See also [[unbound-trace-live-pointer-not-original-offset]],
[[unbound-item-name-putaway-message-width]] for the same pointer-based
diagnosis method.

**How to apply:** when a reported untranslated string already has a FR entry
in `combined_fr.txt`, check for a live pointer first — if absent, write a
class-3 patch script instead of re-editing `combined_fr.txt` (which will keep
silently failing).
