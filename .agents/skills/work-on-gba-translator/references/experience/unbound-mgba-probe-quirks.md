---
name: unbound-mgba-probe-quirks
description: "Pièges des sondes mGBA sur Unbound FR — noms Aaaaaaa/Fffffff = artefacts de mash, coupures de connexion sur sessions longues"
metadata:
  node_type: memory
  type: project
  originSessionId: e8cf1cf9-6166-496b-844a-eea283bf20c8
---

Sondes `scripts/probe_drive.mts` (gba_translator, voir [[unbound-fr-build-lives-in-gba-translator]]) :

- Des noms comme « Aaaaaaa », « Fffffff », « Aaaaaaaaaa » vus en jeu pendant les sondes ne sont PAS des bugs de traduction : ce sont les écrans de nommage (joueur, second perso du prologue, surnom Pokémon) remplis en aveugle par le mash de A (lettre répétée + majuscule initiale, 7 car. max). Vérifié le 2026-06-11 en lisant SaveBlock2 (nom joueur = bb d5×6 = « Aaaaaaa »).
- Le pont Lua mGBA coupe la connexion (« FRAMES failed: Connection closed ») sur les sessions longues (~3-4 min), sur n'importe quelle build — flakiness hôte, pas un crash ROM. Parade : sessions courtes reprises via savestates (save<n>/load<n>).
- Un vrai reset console est détecté par le check sb1 (pointeur SaveBlock1 hors 0x02xxxxxx) et loggé « RESET DETECTED » — c'est LE signal fiable.
- `explorei<n>` est déterministe (graine RNG fixe) : rejouer la même séquence reproduit la même marche.
- Chemin combat gardien du prologue depuis NOUVELLE PARTIE : boot,key:START,key:DOWN,key:A → mash (customisation+nom) → mash ~400 (pont, cinématiques) → explorei ~400 dans l'entrepôt (map 4.10) → sélection Pokémon → combat (le flag inBattle ne se lève pas toujours ; vérifier visuellement).
