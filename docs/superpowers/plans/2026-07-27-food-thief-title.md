# Titre de mission « Voleur de vivres » — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Traduire le titre vivant « The Food Thief » en « Voleur de vivres ».

**Architecture:** Le correctif ajoute l'offset réellement consommé au fichier
maître FR, l'exclut des injecteurs à relocalisation et l'écrit en place avant le
patch dédié à la description voisine. Un test ROM garantit que les trois motifs
de pointeur restent inchangés.

**Tech Stack:** Python 3, pytest, pipeline de traduction CFRU.

## Global Constraints

- Conserver le texte visible dans `languages/fr/combined_fr.txt`.
- Exclure cet offset du JSON et du passe inline.
- Exécuter le patch de titre avant `mission_descriptions.py`.
- Vérifier les octets décodés de la ROM, pas seulement la source.

---

### Task 1: Garde ROM et correction de la source

**Files:**
- Create: `languages/fr/patches/mission_titles.py`
- Create: `tests/test_patch_mission_titles_fr.py`
- Modify: `languages/fr/combined_fr.txt`
- Modify: `scripts/apply_combined_fr.py`
- Modify: `scripts/prepare_fr_json.py`
- Modify: `scripts/apply_inline_overrides_fr.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: pointeurs sources vers `0x1FA4E10`.
- Produces: titre CFRU « Voleur de vivres » dans la ROM FR.

- [x] Écrire le test qui suit les trois motifs du titre.
- [x] Lancer le test et constater « The Food Thief ».
- [x] Ajouter `0x1fa4e10: Voleur de vivres` au bloc actif.
- [x] Exclure l'offset des deux injecteurs et ajouter le patch en place.
- [x] Régénérer le JSON et reconstruire la ROM.
- [x] Vérifier le titre décodé, le diff binaire et les tests ciblés.
