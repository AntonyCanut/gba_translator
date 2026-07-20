---
name: unbound-ability-description-accrue-plus-convention
description: "FR ability descriptions use combined_fr.txt pointer-based text (class 1, not the class-2 fixed name table) — 'accrue' -> '+' is an established shortening convention (issue #95 Voile Sable, issue #113 Rivalité/Peau Miracle)"
metadata:
  node_type: memory
  type: project
  originSessionId: a2b892c6-1edf-4652-87a6-8fdf24fb8ede
---

Contrary to `docs/ability_descriptions_table.md` (written for an earlier ticket, P-171),
`combined_fr.txt` NO LONGER has "zero ability-description entries" — FR ability
descriptions are now authored there like any other class-1 pointer-based text (see
[[translating-unbound-skill]]) and flow through the normal `apply_combined_fr.py --extend`
→ `09_csv_to_json_v2.py` → `make build-fr` chain, no dedicated
`patch_ability_descriptions_fr.py` needed. Verify via the live pointer table at file
0x96DE04 (`gAbilityDescriptionPointers`, indexed by ability ID, 1:1 with the name table at
0xA36398 stride 17) — decode the text at `pointer - 0x08000000`, not the original
`combined_fr.txt` offset, since text can relocate on rebuild even at similar lengths.

**"accrue" → "+" is an established convention**, not a one-off wording pick: issue #95
(Voile Sable/Sand Veil, `0x24F481`: "Esquive + sous tempêtesable.") set the precedent;
issue #113 extended it to Rivalité (`0xA3510F` → "Puissance + contre même sexe.") and Peau
Miracle/Shield Dust (`0xA356E4` → "Esquive + vs cap. statut."). Regression guard:
`tests/unit/fr/test_summary_ability_descriptions.py` (source-level `combined_fr.txt`
assertions, one function per issue). Other "accrue"/"accru" occurrences in the file
(dialogue, DexNav help, move descriptions) are NOT ability descriptions — don't touch them
when a ticket scopes the ask to "talents" (abilities) specifically.
