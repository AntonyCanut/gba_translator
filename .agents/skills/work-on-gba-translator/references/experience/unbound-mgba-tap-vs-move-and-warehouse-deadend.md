---
name: unbound-mgba-tap-vs-move-and-warehouse-deadend
description: "mGBA bridge: 1 tap tourne le sprite, 2e tap déplace ; map 4.10 (entrepôt post-flashback Unbound) = cul-de-sac flood-fillé sans PNJ/déclencheur trouvé (F-110)"
metadata:
  node_type: memory
  type: project
  originSessionId: 26708e0a-a38b-496b-b447-185cdb5acbaf
---

Deux faits établis en creusant F-110 (recherche du sprite Cancel/ANNUL., voir [[unbound-mgba-probe-quirks]]) :

- **`pressKey(dir, 4)` (mGBA bridge, `emulator-web/src/mgba-bridge.ts`) : un seul appel ne fait que réorienter le sprite** s'il ne faisait pas déjà face à `dir` — il faut un 2e appel (généralement 2-4 taps suffisent, jusqu'à 6 par prudence) pour obtenir un vrai déplacement d'une tuile. Un script qui vérifie `getState().playerX/playerY` après un seul tap conclura à tort qu'une direction est "bloquée".
- Sur le clavier de saisie de nom (naming keyboard), **START = raccourci "OK"** (cf. panneau Selection localisé en F-109) : presser START confirme directement le nom sans naviguer jusqu'au bouton OK.
- **map 4.10** (entrepôt/conteneurs maritimes atteint après le flashback du naufrage, ~mash 400 après confirmation du nom) semble être un cul-de-sac exploratoire : un flood-fill (marcheur "préfère tuile non visitée", 500 pas cumulés sur 2 passes) sature toute la zone atteignable sans jamais changer de map ni déclencher de texte/PNJ. Une "console" et un décalque sol en forme de Poké Ball y sont visibles mais n'ont réagi à aucune interaction (A) depuis toutes les tuiles adjacentes atteignables testées.
- La règle de la main droite (`hugWall`, wall-following classique) **boucle à l'infini dans une pièce ouverte** (confirmé : gelé 180+ pas sur la même tuile alors que les 4 directions étaient en fait libres) — préférer un flood-fill (`preferUnvisited`) pour des salles non strictement labyrinthiques.

Outil réutilisable : `scripts/probe_naming_cancel.mts` (gba_translator) est un driver multi-STAGE reprenable par savestate documentant tout ce chemin (voir le docstring en tête de fichier pour le détail stage par stage). Avant de recommencer une exploration à l'aveugle sur map 4.10, lire ce docstring — il conclut que la suite nécessite soit une lecture directe de la table d'événements/warps en ROM, soit d'essayer une branche différente de l'intro (le chemin vers cette map n'est peut-être pas celui prévu par le jeu).
