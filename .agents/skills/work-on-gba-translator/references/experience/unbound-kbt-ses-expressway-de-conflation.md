---
name: unbound-kbt-ses-expressway-de-conflation
description: "DE combined_de.txt conflated two distinct in-game highways (KBT Expressway and SES Expressway) under one wrong name \"RBT\"/\"Autoroute RBT\" — always cross-check the EN offset before blanket-renaming an acronym (#55)"
metadata:
  node_type: memory
  type: project
  originSessionId: 09e9ecb7-db04-4c35-8ea0-ff7295c6a430
---

Borrius has **two separate underground highways** in Unbound: "KBT Expressway"
(König Borrius der Dritte, West-Borrius) and "SES Expressway" (Crater Town ↔
Tehl Town). The German translation (`gba_translator/languages/de/combined_de.txt`)
had mistranslated **both** to the same wrong name — "RBT-Autobahn" / "Autoroute
RBT" (RBT = wrong letter, Autoroute = French leftover, also saw "RBT-Highways"
English leftover and "Route KBT" French leftover). GitHub issue #55 only
reported the KBT half (the only one explained in-game, "„RBT‟ steht für König
Borrius der Dritte" — obviously needs K not R); the SES half (12 of 61 total
occurrences) was silently the same bug and would have been mis-fixed to "KBT"
too if I'd done a naive `s/RBT/KBT/g`.

**Why:** always resolve each DE offset against `languages/en/combined_en.txt`
before a blanket acronym/name substitution across many lines — two distinct
proper nouns can be conflated under one wrong translated name, and a
global find-replace silently merges them into one (now differently) wrong name.

**How to apply:** for any "rename X to Y everywhere" translation ticket, first
build an offset→EN-source cross-reference (see script pattern: load both
combined_*.txt into offset→text dicts, grep the target string, print the EN
counterpart for every hit) rather than trusting the DE text's own wording.
Canonical fix used here: masculine "Expressweg" replacing feminine "Autobahn"
required article/case grammar fixes (der/die/den/dem/des) per sentence — see
commit `fix(de): correct KBT/SES Expressweg naming` in gba_translator.

One offset (`0x1F21C7F`, a zone-name/banner table entry) is unreachable by the
pointer-text-extractor scan (no live GBA pointer anywhere in englishrom.gba) —
same class as [[unbound-zone-name-table-vs-worldmap-labels]] and
`languages/fr/patches/zone_names.py`'s TARGETS gap; FR has the identical
untouched entry, so this is pre-existing and out of scope, not a regression.
