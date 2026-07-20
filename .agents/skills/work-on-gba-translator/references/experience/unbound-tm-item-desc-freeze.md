---
name: unbound-tm-item-desc-freeze
description: "Freeze en ramassant une CT/CS (Volcan Cendre) — les descriptions d'objets TM/HM débordent en place dans 0xA3xxxx ; consommateur table d'objets oublié par le patch move-desc"
metadata:
  node_type: memory
  type: project
  originSessionId: 2af46471-6134-4680-baf3-0a6467f27b2d
---

Freeze « Volcan Cendre » en ramassant la CT à gauche (CT94 Calcination) — RÉSOLU (commit 1610afd, gba_translator@unbound).

La description sac de chaque CT/CS se lit via le pointeur **+0x14** de l'entrée objet (table `0x876074`, stride 44). Ces pointeurs visent la région move-desc packée **0xA3xxxx** dont les slots EN sont minuscules/vides (`0xFF` seul). `apply_inline_overrides_fr` écrit le texte FR (combined_fr) **en place** → débordement, terminateur `0xFF` détruit, 17 descriptions fusionnées en runs non terminés (CT94 → Vampigraine → Suc Digestif…). `GetStringWidth` boucle → écran figé au ramassage. Les patchs move-desc (`patch_move_descriptions_fr`/`patch_dup_…`) ne corrigeaient que la **table des attaques** (0x99F190 → 0x48xxxx), pas ce consommateur table d'objets → LEÇON = tracer TOUS les consommateurs (cf. [[unbound-give-cs-object-gain-crash]]).

Fix : `scripts/patch_tm_item_descriptions_fr.py` (post-build, après les move-desc dans `make build-fr`, idempotent). Relocalise en free space **uniquement** les CT/CS dont le run jusqu'au `0xFF` dépasse 120 o (texte sain max = 107 o ; fusionnés ≥ 133), repointe +0x14. Les courtes saines restent identiques à l'EN (dont le don give-CS 0x1B5 dont la boîte d'obtention affiche le NOM, pas la desc — épinglé par `test_object_gain_sequence`). 2 pools distincts : `0xA3xxxx` (objets TM, ce fix) vs `0x48xxxx` (résumé attaques, déjà géré, budget overflow 160).

Détection = hash d'écran (jamais position/PC). Garde : `tests/e2e/test_tm_item_desc_freeze.py` (RED 15 offenders avant, GREEN après). Repro : `scripts/probe_volcan_freeze.mts <rom>` (charge la save batterie, route vers la ball, mash A, verdict screen-hash). Voir skill [[diagnosing-unbound-freezes-skill]] et [[unbound-fr-build-lives-in-gba-translator]].
