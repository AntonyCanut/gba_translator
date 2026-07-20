---
name: unbound-build-determinism-relocation-order
description: "Build FR/IT non-déterministe = relocalisation dépendante de l'ordre d'entrée ; fix 4 sources dans text_reinserter + 19_build"
metadata:
  node_type: memory
  type: project
  originSessionId: 7375752f-3e00-452f-9fa6-6b0a5ad0ead9
---

Le build gba_translator était **non-déterministe par ordre d'entrée** (pas par hash-seed — le hash-seed était déjà OK). La JSON de traduction est régénérée par deux chemins (pipeline CSV trilingue vs `prepare_fr_json`) qui émettent les mêmes entrées dans un **ordre différent** → la couche de relocalisation free-space + tous les pointeurs repointés se reshufflaient → ~0,2 % de la ROM dérivait à chaque rebuild « sans changement ». Shuffle de la JSON = ~650 K octets de diff avant fix.

**4 sources d'ordre-dépendance (commit 4b969bb), toutes mesurées en rebuildant :**
1. `flush_relocations()` triait par longueur seule, départage = ordre d'entrée → clé totale `(len, encoded_bytes, offset)`.
2. `_infer_original_length` / `_detect_padding` lisaient la ROM **en cours d'écriture** → décision « tient en place vs trop long → relocate/fallback » variait selon l'ordre des voisins déjà écrits → lire un **snapshot pristine** `self._source_snapshot = bytes(rom_data)` pris à la construction.
3. `_plausible_pointer_sites` lisait la ROM live (une écriture in-place pouvait clobber un site candidat et inverser la décision relocate) → lit le snapshot.
4. Écritures in-place en ordre JSON : des cellules voisines écrivent des spans **qui se chevauchent** (table des noms de type : 2 cellules quasi-identiques à 1 octet d'écart, dernier écrivain gagne) → traversée triée par offset croissant dans `reinsert_all()` + helper `_reinsert_in_offset_order()` dans `19_build_translated_rom_generic.py` (les 3 boucles copy/translate/hybrid).

**Vérifié :** build core + chaîne complète 33 étapes byte-identiques sur l'ordre original + plusieurs shuffles (0 octet) ; `make prepare-fr && make build-fr` ×2 = byte-identique. IT (demande relocate > free-space) build toujours OK. 831 tests unit verts. Test : `tests/test_reinserter_determinism.py`.

**Piège ROM committée :** la première rebuild avec le code déterministe canonise la relocalisation une fois → ~673 K octets diffèrent de la ROM committée (bâtie par l'ancien build). PAS une régression de contenu (pointeurs mis à jour). Régénération + vérif émulateur = ticket suivi R-11. Voir [[unbound-e2e-tests-gate-committed-rom]] (gate sur ROM committée), [[unbound-it-relocation-packing-fix]] (best-fit packing free-space), [[combined-fr-duplicate-offsets-last-wins]].

**rtk casse `pytest`/`python3 -m pytest`** dans ce harnais (« Failed to spawn ») → lancer via `python3 -c "import sys,pytest; sys.exit(pytest.main([...]))"`.
