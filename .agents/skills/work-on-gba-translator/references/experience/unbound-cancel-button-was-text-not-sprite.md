---
name: unbound-cancel-button-was-text-not-sprite
description: "F-108/109/110/111 'Cancel .bmp sprite' chain resolue : CANCEL etait du texte CFRU normal deja traduit dans combined_fr.txt mais jamais rebuild — pas un sprite du tout"
metadata:
  node_type: memory
  type: project
  originSessionId: 26708e0a-a38b-496b-b447-185cdb5acbaf
---

Quatre tickets d'affilée (F-108 → F-109 → F-110 → F-111) ont cherché en vain l'offset ROM du sprite "Cancel 32x16.bmp" (bouton ANNUL.) en supposant que c'était un graphisme OBJ comme `status_badges`/`selection` — sonde mGBA sur l'écran de nommage/surnom Pokémon (jamais atteint, cul-de-sac map 4.10, voir [[unbound-mgba-tap-vs-move-and-warehouse-deadend]]), puis scan structurel statique de tous les blocs LZ77/bruts de la ROM (`scripts/scan_sprite_region.py`, zéro résultat fiable).

**Résolution réelle** : "CANCEL" n'est PAS un sprite — c'est du texte CFRU normal. Encoder `"CANCEL"` via `src.text.encoder.encode_string(..., terminate=False)` (Test/Unbound toolkit) et chercher ces octets bruts (`rom.find`, sans exiger le terminateur 0xFF juste après — le texte peut être suivi d'un control code plutôt que d'une fin de chaîne) trouve exactement **une** instance vivante dans `output/roms/GenedRom-fr.gba`, à `0x41ee2b` : `"DEL. ALL<FC:1357>CANCEL<FC:13A4>OK"` (barre de confirmation suppression/tout, probablement PC Box ou Sac).

`languages/fr/combined_fr.txt` avait déjà la traduction à cet offset (`0x41EE2B: SUPR. TOUT{CLEAR_TO}ANNULER{CLEAR_TO}3OK`, posée par un travail de traduction antérieur totalement indépendant de la chaîne de tickets sprite) — elle n'avait simplement jamais atteint la ROM buildée. `make prepare-fr && make build-fr` (gba_translator) suffit : le pointeur vivant à `0x1024bc` (pointait vers `0x0841ee2b`) est repointé vers `0x081679ca` qui contient bien `"SUPR. TOUT{FC:1357}ANNULER{FC:13A4}OK"` après rebuild.

**Piège découvert au passage** : un `make build-fr` (rebuild complet depuis `patchedfrenchrom.gba` + traductions) **efface silencieusement** tout sprite posé hors-pipeline via `scripts/insert_sprite.py` (le sprite `selection` de F-109 redevenait anglais après rebuild) — contrairement à `status_badges` qui a son propre script de patch dédié appelé dans le Makefile. Fix : ajouter `insert_sprite.py --sprite selection` comme étape du `build-fr` target (`Makefile`), au même niveau que les autres `PATCH_*_SCRIPT` — pattern à répliquer pour toute future entrée du registre `languages/fr/sprites.py` qui n'a pas encore son propre script de patch dédié.

**Leçon générale** : avant de chasser un `.bmp` UI comme un sprite OBJ, chercher d'abord si le mot qu'il contient existe comme **texte encodé CFRU** dans la ROM (`encode_string` + `rom.find`, sans emulateur) — beaucoup de libellés de bouton FRLG/CFRU (party menu CANCEL, etc.) sont dessinés par le moteur de texte, pas stockés en tuiles. Voir aussi [[unbound-f109-orphaned-branch-recovery]] (le travail F-108/F-109 existait sur une branche orpheline) et [[unbound-mgba-tap-vs-move-and-warehouse-deadend]] (l'exploration mGBA qui s'est avérée être une fausse piste).
