---
name: unbound-worldmap-junction-panels
description: Panneaux Carte du monde flèche-en-tête (0x1F726xx-0x1F728xx) injoignables par la pipeline (orig_len=1) + flèches au début de ligne
metadata:
  node_type: memory
  type: project
  originSessionId: 5d9ecf84-f233-4a07-a429-629874386c7e
---

B-74 (P-68 « panneaux non traduits Frozen Heights/Crater Town/Blizzard City »). Deux familles de panneaux de route Carte du monde dans `combined_fr.txt`, cluster `0x1F70xxx`-`0x1F72xxx` :

1. **Panneaux Route** (`Route 8\n«sous-titre»\p<arrow> dest…`) : l'extracteur les dimensionne bien → pipeline normale (combined_fr → CSV → JSON → relocate+repoint). 25/33 OK.
2. **Panneaux jonction** (commencent DIRECTEMENT par un octet flèche `0x79`-`0x7C`, sans nom de route) : l'extracteur lit la flèche de tête comme une chaîne de **1 octet** (`original_length=1`, `real_max_length=3`) → FR trop long, aucune entrée d'extraction exploitable → **droppé par toutes les voies** → reste anglais en ROM. 8 cibles : `0x1F72691` (= le panneau exact signalé : Frozen Heights/Crater Town/Blizzard City), `0x1F726C0, 0x1F726FC, 0x1F72735, 0x1F7276E, 0x1F727A7, 0x1F727D0, 0x1F72808`. Chacun a 1 pointeur dans la table moteur stable `~0x1E934xx-0x1E935xx`.

**Fix** : `scripts/patch_worldmap_junction_panels_fr.py` (calqué sur [[unbound-long-dialogue-extractor-cap]] = patch_meteorite_dialogue_fr) — relocate+repoint reference-driven, idempotent. Test : `TestRoadPanelsFR` dans `tests/test_location_names_fr.py`.

**B-76 (2026-06-24) — câblage Makefile + régression combined_fr** : le patch existait mais n'avait JAMAIS été câblé dans la cible `build-fr` (`grep junction Makefile` = 0) → panneaux jonction restaient anglais, gate `pytest tests/test_location_names_fr.py` rouge en fin de build. Fix : variable `PATCH_WORLDMAP_JUNCTION_FR_SCRIPT` + step `@$(PYTHON) … --rom --source --combined --reference-rom` après le step météorite dans `build-fr`. PLUS : commit `126e437` (« Frost Mountain = Mont Givre ») avait **écrasé tout le bloc arrow-clean B-74/P-68** en bas de `combined_fr.txt` (≈39 lignes) par 7 entrées auto-trad flèches-en-milieu-de-ligne → 38 panneaux re-cassés (audit `scripts/audit_arrow_line_start_fr.py` rouge). LEÇON : toute édition d'un panneau route/jonction dans combined_fr peut droper silencieusement le bloc arrow-clean — relancer l'audit après. Fix = restaurer le bloc propre (Mont Givre déjà présent dedans) + garder le label `0x1F7108E`, puis chaîne complète apply_combined --extend → CSV → csv_to_json → make build-fr. 0x741AF1 = panneau Route normal (livré par la pipeline générique, PAS le patch jonction) ; sa flèche se corrige dans combined_fr, hors TARGETS du patch.

**Règle flèches (user)** : chaque octet flèche `0x79-0x7C` DOIT être en début de ligne = premier octet OU précédé d'un saut (`0xFE \n` / `0xFA \l` / `0xFB \p`). L'anglais respecte déjà ça (`Name\n«sub»\p<arrow> dest\n<arrow> dest`) ; l'auto-trad FR l'avait cassé (flèches en milieu de ligne, toponymes tronqués Icicle/Mont Gelé/V. Cendre). Re-traduire DEPUIS l'anglais en gardant la structure de contrôle exacte, ne traduire que les toponymes. Toponymes canon : Frozen Heights→Hauteurs Gelées, Crater Town→Bourg Cratère, Blizzard City→Ville Blizzard, Frost Mountain→Mont Givre, Bellin Town→Bellinville, Icicle Cave→Grotte Stalactite, Cinder Volcano→Volcan Cendreux, Grim Woods→Forêt Lugubre, Flower Paradise→Paradis Floral. Concerne aussi B-75 (flèches dans TOUS les dialogues).

Détection : décoder l'EN ROM aux offsets (0x79-0x7C ne sont PAS dans la charmap = glyphes flèche, jamais des lettres) ; les octets 0x79-0x7C dans le CSV décodé sont du bruit ASCII (y/z) — ne pas s'y fier. Vérité = octets ROM via pointeur vivant.
