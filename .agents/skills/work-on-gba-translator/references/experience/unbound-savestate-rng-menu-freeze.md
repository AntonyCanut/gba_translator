---
name: unbound-savestate-rng-menu-freeze
description: "Reroll de capture par save state — le RNG (gRngValue 0x03005000) est gelé aux menus, ne tourne qu'en animation/overworld"
metadata:
  node_type: memory
  type: project
  originSessionId: c80c5b82-eb7d-4677-b685-09d8deda7bcb
---

Pour rerouler une capture (ex. Ho-Oh à la RapideBall, ~2 % tour 1) via save states dans Unbound : **`gRngValue` @ `0x03005000` n'avance QUE pendant une animation**. À tout menu en attente d'input — menu d'action de combat ET sac/liste d'objets — il est **GELÉ**. Idler sur un état « curseur sur RapideBall » redonne un seed byte-identique → tous les lancers donnent le MÊME résultat (90 lancers = 90 fois le même FREE, vérifié : seed constant `0x3CFDC34B` au menu).

**Fix** : rerouler dans l'**overworld** (le RNG tourne à chaque frame — seed distinct par frame). Banker l'état sur la case du déclencheur (ici l'anneau Hoopa, case (11,6) face en haut, « Ruines du Néant B2F »), idler `k` frames pour fixer un seed de début de combat unique, puis rejouer TOUT l'encounter déterministe (trigger → intro → sac → lancer) par `k`. ~32 s/essai → lancer en tâche de fond avec driver résilient (auto-restart mGBA + reload du dernier save state sur coupure de bridge).

**Détection d'issue** (pas de BATTLE_OUTCOME fiable — `0x02022B50` reste constant 27) : décoder `gDisplayedStringBattle` `0x0202298C` (charmap CFRU). Prompt « Que doit faire <mon> ? » (`cbe9d9…`) qui réapparaît = LIBÉRÉ ; jamais réapparu = CAPTURÉ. Masher **B** (pas A) pendant la résolution : un menu qui revient n'est pas poussé dans Combat, et le prompt de surnom est refusé.

**Règle** : la manip RNG par save state ne marche que là où le RNG avance. Toujours **lire le mot RNG** et vérifier qu'il change entre essais AVANT d'attribuer des issues identiques répétées à la malchance.

Artefacts : `scripts/capture_hooh_rapideball.py`, `tests/e2e/test_hooh_rapideball_capture.py`, `tests/e2e/fixtures/hooh_ring_save.bin`. Voir aussi [[unbound-mgba-probe-quirks]], [[unbound-mgba-harness-flags-invalid]], [[diagnosing-unbound-freezes-skill]] (freeze = hash d'écran).
