---
name: unbound-trainer-vs-screen-name-raw-table
description: "Trainer name shown on the battle-launch/VS screen reads a raw trainer-struct name cell, separate from dialogue text — renaming a trainer everywhere in combined_fr.txt does not fix that screen"
metadata:
  node_type: memory
  type: project
  originSessionId: 95e25b0b-43d8-4f59-96cf-378f05e7d5aa
---

Issue #62 (Champion d'Arène de Dresco): Mirskle→Sylvain had already been renamed in
every dialogue string in `combined_fr.txt` (all pointer-based text entries, e.g.
0x1F15C64 already read "Sylvain"), yet the VS/battle-launch screen still showed
"Mirskle". Byte-searching the English ROM for the encoded name found 33 raw
occurrences; 27 fell inside ranges already covered by combined_fr.txt dialogue
entries, but 6 did not — they sit in a separate raw trainer-data table
(0x23EB00–0x245C00 range, right after the trainer-CLASS-name table at
0x23E565–0x23EAF9 and before the ability-name table at 0x24F1A7), spaced exactly
0x28 bytes apart (fixed trainer struct stride). That table is never scanned by the
dialogue extractor/pointer pipeline, so no amount of combined_fr.txt editing
reaches it.

**Why:** the VS screen reads the trainer's OT name directly from the trainer
struct's embedded fixed-width name field, not from a pointer-referenced dialogue
string — same category as ability names, item names, and trainer-class names
(all documented as "fixed table" cases in existing memories:
[[unbound-ability-names-fixed-table]], [[unbound-weak-armor-nodulithe-fix]]).

**How to apply:** when a trainer/character's chosen French name still shows
English specifically on a VS/battle-intro/summary screen (but is correctly
translated in dialogue text), byte-search the base English ROM for the name's
encoded bytes and check which hits fall OUTSIDE any combined_fr.txt entry's
[offset, offset+en_length) range — those are raw table cells needing a
dedicated fix in `languages/fr/patches/fixed_table_names.py`'s `NAME_FIXES`
dict (offset, old, new, stride), applied post-build in the `build-fr` Makefile
target. If old/new names are the same byte length (as Mirskle/Sylvain, 7
chars each), stride = len(new)+1 is safe (no padding needed, no relocation).
