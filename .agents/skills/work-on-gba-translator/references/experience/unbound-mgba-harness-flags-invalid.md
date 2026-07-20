---
name: unbound-mgba-harness-flags-invalid
description: gba_translator mGBA bridge state flags (textActive/inBattle/gBattleMons) are WRONG for Unbound; only map/pos is reliable
metadata:
  node_type: memory
  type: project
  originSessionId: 53107bd2-02bb-407d-be21-b70ed2db4987
---

Dans `gba_translator`, le harness mGBA (`emulator-web` bridge + `scripts/probe_*.mts`) lit des adresses RAM **invalides pour le build Unbound** :

- `textActive` @`0x020375c0` renvoie **false alors qu'une boîte de dialogue est visible** (vérifié : "Sbire : Vite !" lue text=false).
- `inBattle` @`0x030022C8` ne se déclenche pas de façon fiable.
- `gBattleMons[0].hp` @`0x02023C0C` (documenté dans le README des saves) est **faux** : y **écrire** (ou dans les buffers HP transitoires `0x0202_07xx–0c88`) **corrompt la RAM → écran noir figé**.

Seuls **`map` + `playerX/Y`** (via `gSaveBlock1Ptr` @`0x03005008`) sont fiables.

**Conséquences :**
- Le détecteur de reset (pointeur saveblock invalide) **ne voit PAS un freeze** : un hang garde `gSaveBlock1Ptr` valide. "Le jeu reste vivant / gSaveBlock1Ptr valide" ≠ "la boîte avance". Les conclusions "reproduit in-game, pas de crash" des runs précédents ne prouvent rien sur les freezes.
- Pour détecter un freeze : utiliser **screenshot statique + position joueur figée** (cf. `scripts/repro_give_cs.mts`), pas les flags RAM.
- Ne jamais cheater la HP via ces adresses : ça corrompt le build.

Lié : crash/freeze "pas de gain d'objet" → la séquence give-CS est byte-propre sur le build courant ([[unbound-give-cs-object-gain-crash]]) ; le blocage de repro est le combat RNG Ivory/Zeph (équipe sous-leveled, coup Normal immunisé vs Spectres). Pour un verdict in-game définitif il faut une **savestate juste avant le don de CS** (`output/roms/GenedRom-fr.ss<n>`) que `repro_give_cs.mts` peut `load<n>`.
