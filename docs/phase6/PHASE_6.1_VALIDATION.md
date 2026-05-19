# Phase 6.1 — Validation mGBA + bridge.lua sur Pokemon Unbound FR

**Date** : 2026-05-20
**Agent** : DevOps
**Statut** : ✅ **VALIDÉ — mGBA-bridge fonctionne**

## Résumé exécutif

mGBA natif (Homebrew HEAD) lance la ROM **GenedRom-fr.gba** (Pokemon Unbound FR,
32 Mio, hack FireRed BPRE) et expose un game state cohérent via le bridge.lua
sur TCP `127.0.0.1:55234`. Toutes les commandes du protocole testées renvoient
`OK`. Le screenshot confirme que l'émulateur affiche l'écran titre Pokemon
Unbound (logo + "PRESS START") — **la ROM n'est pas blanche, contrairement à
gbajs**.

La Phase 6.2 (Developer) peut démarrer en confiance.

## Environnement

| Composant | Valeur |
|---|---|
| Plateforme | macOS Darwin 25.4.0 (arm64) |
| mGBA | `0.11-9069-a2ce093c0-dirty` (Homebrew HEAD) |
| Binaire | `/opt/homebrew/Cellar/mgba/HEAD-a2ce093_2/mGBA.app/Contents/MacOS/mGBA` |
| Wrapper | `/opt/homebrew/bin/mgba` |
| `--script` supporté | ✅ oui (mGBA 0.11+) |
| bridge.lua | `emulator-web/src/lua/bridge.lua` (19 098 octets, déjà présent — pas de copie nécessaire) |
| ROM | `output/roms/GenedRom-fr.gba` (32 Mio, `Game Boy Advance ROM image: "POKEMON FIRE" (BPRE01, Rev.00)`) |

> **Note ROM** : le ticket mentionnait `/Users/akc/Projects/Test/Unbound/data/frenchrom.gba`,
> ce fichier n'existe plus. La ROM FR Phase 6.3 validée se trouve maintenant à
> `output/roms/GenedRom-fr.gba` dans le projet `gba_translator`. C'est la ROM
> utilisée pour cette validation.

## Méthode

1. Lancement mGBA en background via `open -na ... --args --script <bridge.lua> <rom>`
2. Attente du socket TCP `55234` (LISTEN)
3. Connexion via script Python (`/tmp/phase6_proof/bridge_test.py`)
4. Envoi séquentiel de chaque commande protocole + mesure latence
5. Inspection visuelle du PNG produit par `SCREENSHOT`

## Résultats par commande

| # | Commande | Réponse | Latence | OK |
|---|---|---|---|---|
| 1 | `PING` | `OK\|pong` | 19.7 ms | ✅ |
| 2 | `FRAMES\|600` | `OK\|frame=1281` | 9996.3 ms (= 600 frames @ 60 fps) | ✅ |
| 3 | `STATE` | `OK\|frame=1282\|peak=1282\|pc=00000000\|cb1=00000000\|cb2=00000000\|fade=0\|map=0.0` | 30.5 ms | ✅ |
| 4 | `SCREENSHOT\|/tmp/phase6_proof/unbound_phase6_proof.png` | `OK` | 8.1 ms | ✅ |
| 5 | `READ\|0203C040\|4` | `OK\|00 00 00 00` | 33.7 ms | ✅ |
| 6 | `READ\|02000000\|8` | `OK\|00 00 A3 A3 F0 BF 01 00` | 1.5 ms | ✅ |

### Note sur les valeurs nulles

- `READ|0203C040|4` retourne `00 00 00 00` parce qu'à frame ~1282 nous sommes
  toujours sur l'écran titre (avant "PRESS START"), donc `gSaveBlock1Ptr` et
  les structures jeu sont nulles. **Comportement attendu**, pas un bug.
- `READ|02000000|8` lit en EWRAM et retourne des bytes non-nuls (`A3 A3 F0 BF`)
  → la RAM est bien initialisée par le moteur, la communication mémoire marche.
- `cb1=00000000` et `map=0.0` → idem, on est avant l'appui sur START. Le frame
  count (`frame=1282`) prouve cependant que l'émulateur tourne réellement.

## Screenshot

**Fichier** : `output/proofs/unbound_phase6_proof.png` (15 043 octets, 240×160 RGB 8-bit non-interlaced)
**Taille** : 15 KB (> seuil 5 KB largement franchi)
**Contenu visuel** : écran titre Pokemon Unbound — logo coloré "Pokemon
Unbound", silhouette du Pokémon mascotte (Spectrum), watermark "SKELI",
texte "PRESS START" clignotant. **PAS** un écran blanc.

Voir `output/proofs/unbound_phase6_proof.png`.

## Pièges identifiés (à transmettre au Developer pour Phase 6.2)

### 🔴 PIÈGE CRITIQUE : `-C fpsTarget=0` casse mGBA-qt sur macOS

`mgba-bridge.ts` (ligne 94) passe actuellement `-C fpsTarget=0`. **Sur
mGBA-qt 0.11 macOS, cela arrête l'avancement des frames** : seule la frame 1
s'exécute, puis l'émulateur reste figé. Le bridge.lua reçoit malgré tout sa
callback `frame` au démarrage, le socket binde et passe en LISTEN, mais
aucune commande dépendant des frames (`FRAMES|N`, `STATE`, etc.) ne progresse.

**Reproduction** : lancer mGBA avec `--script bridge.lua -C fpsTarget=0 ROM` →
`PING` retourne `OK|pong` SEULEMENT si la callback `frame` est déjà passée une
fois, mais `FRAMES|600` reste bloqué indéfiniment (deferred jusqu'à atteindre
la frame cible qui ne vient jamais).

**Fix recommandé Phase 6.2** : supprimer `-C fpsTarget=0` (lignes 93-97 de
`emulator-web/src/mgba-bridge.ts`). Le tick natif 60 fps est suffisant. Si on
veut du fast-forward, utiliser `emu:runFrame()` côté Lua ou la commande
`FRAMES|N` qui appelle déjà `emu:runFrame()` en boucle synchrone.

### 🟡 Lancement : préférer `open -na`

`spawn(mgbaPath, ...)` direct fonctionne (le binaire se lance, le socket bind),
mais sur macOS la fenêtre peut ne pas avoir le focus et l'event loop Qt peut
être paresseux. Lancer via `open -na "<mGBA.app>" --args ...` produit une
fenêtre correctement intégrée à WindowServer. Pour Phase 6.2 le `spawn`
existant SUFFIT (les frames avancent sans focus une fois `fpsTarget=0`
retiré).

### 🟢 `bridge.lua` est OK tel quel

Le fichier `emulator-web/src/lua/bridge.lua` (19 098 octets) est une version
évoluée du bridge Unbound (qui fait 17 259 octets). Aucune modification
nécessaire. Toutes les commandes du protocole répondent correctement.

## Critères de succès — checklist

- [x] `mgba --help` montre `--script` supporté
- [x] `bridge.lua` présent dans `emulator-web/src/lua/bridge.lua` (présent dès le départ)
- [x] Connexion TCP `127.0.0.1:55234` réussie après lancement
- [x] `PING` répond `OK|pong`
- [x] `FRAMES|600` exécute sans erreur (`OK|frame=1281`)
- [x] `SCREENSHOT` produit un PNG > 5 KB (15 KB, écran titre Pokémon Unbound visible)
- [x] `STATE` renvoie un game state cohérent (frame counter qui avance)
- [x] Rapport markdown listant chaque commande + réponse

## Conclusion

**mGBA + bridge.lua = ✅ OUI, ça marche.**

La Phase 6.2 (Developer) peut intégrer ce stack en remplaçant `gbajs` dans
`emulator-web/src/server.ts` / `mgba-bridge.ts` avec **une seule correction
obligatoire** : retirer `-C fpsTarget=0`.

## Artefacts

- `docs/phase6/PHASE_6.1_VALIDATION.md` — ce rapport
- `output/proofs/unbound_phase6_proof.png` — screenshot écran titre Unbound (preuve visuelle)
- `/tmp/phase6_proof/bridge_test.py` — script de test reproductible (transient)
- `/tmp/phase6_proof/bridge_test.out` — sortie brute du test (transient)
