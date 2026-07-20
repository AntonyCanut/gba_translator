---
name: unbound-generic-pipeline-missing-pointer-offsets-relocation
description: Pipeline générique IT/DE ne propage pas pointer_offsets → relocalisation impossible même avec pointeurs vivants connus
metadata:
  node_type: memory
  type: project
  originSessionId: cad0e0c8-8ab5-4ea0-ad5c-191d4321d285
---

Fix "Cry"→"Cri" (offset `0x415FAD`, menu contextuel Liste Pokémon), issue
gba_translator#7. FR tient exactement dans la cellule fixe (3o), patché sans
relocalisation. IT ("Grido", 5o) et DE ("Schrei", 6o) partagent le même
défaut de ROM de base (Cry non traduit) mais sont plus longs que la cellule
d'origine.

**Constat** : cette entrée A des pointeurs vivants connus dans l'extraction
anglaise (`table_offsets: 0x00105FD8`, `pointer_offsets: 0x00105FE4,
0x001067B8`) — la relocalisation devrait donc être possible en théorie.
Mais `scripts/build_language.py` → `19_build_translated_rom_generic.py` →
`SmartReinserter.reinsert_text()` (`src/core/text_reinserter.py:589`)
n'attempte `_relocate_text()` que si `translation['pointer_offsets']` est
présent dans le JSON `*_translation_ready.json`. Le pipeline générique IT/DE
(csv_to_json) ne propage jamais ce champ, contrairement au pipeline FR
dédié (`prepare_fr_json.py`) — donc `make build-it`/`make build-de`
terminent verts (aucune erreur) mais l'entrée reste silencieusement
inchangée (`skipped_too_long`), même avec pointeurs connus.

Ne pas confondre avec [[unbound-generic-build-freespace-blocks-relocation-patches]]
(qui documente un manque de free-space) : ici le blocage est un manque de
plomberie (champ non transmis), pas un manque d'espace. Vérifier toujours
par décodage des octets réels dans `GenedRom-it.gba`/`GenedRom-de.gba`
après un `make build-it`/`make build-de` "successful" — le succès du build
ne garantit pas que l'entrée a été appliquée.

Ticket de suivi créé : B-188 (étendre le pipeline générique pour propager
pointer_offsets, ou patch dédié post-build type `patch_ability_names_fr.py`).

Voir aussi [[unbound-pattern-c-stale-snapshot-commit]] pour la course
concurrente : 2 rebases nécessaires en cours de ticket, la ROM FR binaire ne
se merge jamais (conflit systématique) → toujours regénérer
`make prepare-fr && make build-fr` après un `orchestration_pull` qui
rapporte un conflit sur `output/roms/GenedRom-fr.gba`, ne jamais tenter un
merge manuel du binaire.
