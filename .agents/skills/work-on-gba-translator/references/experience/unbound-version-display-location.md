---
name: unbound-version-display-location
description: "Où la version v2.1.1.1 s'affiche dans Unbound et comment patch_version_fr la corrige"
metadata:
  node_type: memory
  type: project
  originSessionId: 9b194982-9eaa-4499-9de0-e9cad22a7a7c
---

Le seul affichage de version in-game d'Unbound est sur l'écran **NOT FOR SALE**
(intro skull, ~frame 60), pas sur le titre Pokémon Unbound (PRESS START n'a
AUCUNE version). Écran NFS = BG0 seul, mode 0, charblock 0, screenblock 7
(DISPCNT=0x0140, BG0CNT=0x0700).

« v2.1.1.1 » est pré-rendu en 12 tuiles 8×8 (indices 0xE1–0xEC, grille 6×2,
lignes 18-19 cols 24-29 de la tilemap) dans le tileset LZ77 référencé par
l'UNIQUE pointeur ROM à **0xEC610** (→ 0x1FC08A0 dans englishrom). Glyphes =
traits index 4 (blanc) sur fond de tuile index 9 (noir). `patch_version_fr.py`
(via [[unbound-fr-build-lives-in-gba-translator]]) redessine ces 12 tuiles en
« FR.2.0.<build> », recompresse en free space et repointe 0xEC610 — la tilemap
n'est jamais touchée.

PIÈGE : les anciens pointeurs « title screen » 0x1413AC/0x1413B8 pointent en
fait le bandit-manchot du Game Corner (CREDIT/PAYOUT) → l'ancien code corrompait
cette machine à sous sans rien changer à la version. Un 2e bloc 0x1FBF934
(version@tile 0xEE) = variante inutilisée « Battle Frontier Demo v2.0.1 », sans
pointeur, non affichée.

Vérif manuelle : sonde mGBA `--script` qui dump VRAM 0x06000000 + palette
0x05000000 au frame voulu, puis re-render Python (tuiles+tilemap+palette).
Timing intro non-déterministe (cf [[unbound-mgba-probe-quirks]]) → dumper VRAM
dans le MÊME run que le screenshot.

Vérif automatisée (T-21) : `scripts/verify_version_display.py` décode en
aveugle la bande NFS (lit 0xEC610, décompresse, OCR des 12 tuiles → string) et
contrôle l'octet header 0xBC ; exit≠0 si ça ne dit pas FR.2.0.<build>. Couvert
par `tests/test_verify_version_display.py` (unit, sans ROM) +
`tests/e2e/test_version_display.py` (marqué `rom` : patch EN→vérif, invariant
machine-à-sous, round-trip CLI). Étape « Verify version display » dans
`release-fr.yml` garde la build avant publication.
