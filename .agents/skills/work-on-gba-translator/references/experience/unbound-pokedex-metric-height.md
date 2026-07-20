---
name: unbound-pokedex-metric-height
description: "Pokédex hauteur métrique (PrintMonHeight 0x1058C4) — ABI des helpers div/mod + vérifier le rendu, pas les octets"
metadata:
  node_type: memory
  type: project
  originSessionId: 4e18cb30-487f-4af7-a3b6-434bd08bbaee
---

Conversion impériale→métrique de la taille Pokédex (FR). Routine = `PrintMonHeight` @ `0x081058C4`. La taille stockée est en **décimètres** dans r4 (jamais détruit : les helpers font seulement push/pop r4). Affichage voulu : `X.Ym` (` X.Ym` sur 1 chiffre, `XY.Zm` à partir de 10 m → Wailord 14.5 m).

**Patch correct** (`gba_translator/scripts/patch_pokedex_metrics_fr.py`, commit 8518bf4) : bloc propre de 38 octets à `0x10592E` → `metres = dm÷10`, `decimal = dm − 10·metres` calculés directement depuis r4, sans registre de reste. Littéral 10000→1 (0x10597C), diviseur 254→10 (0x105926), `.`/`m`/blanc/labels Ta/Po/kg conservés. La branche ≥10 m (0x105980) reste **l'original anglais** (ones via le helper modulo en r0).

**Piège ABI des helpers de division** (cause de 4 échecs « encore ko ») :
- `0x1E460C` = division non signée → **quotient en r0** ; sur le chemin rapide dividende<diviseur, **r1 reste = diviseur intact (10)**, ce n'est PAS un reste.
- `0x1E4684` = modulo → **reste en r0**.
- `0x1E4018` = division signée → quotient en r0.
Lire le décimal depuis r1 donnait toujours 10 → glyphe `0xAB` (chaque Pokémon). Un bloc d'arrondi pieds/pouces résiduel ajoutait 10 aux mètres si le chiffre des mètres ≥5 (dm=99 → « 1?.?m »).

**POIDS (PrintMonWeight @0x08105A3C)** : poids stocké en **hectogrammes** (hg), kg = hg÷10. La routine anglaise convertit hg→livres : `r6 = hg × 100000 / 4536` = livres×100, puis un formateur base-10 générique imprime `r6÷100` avec 1 décimale. Le 1er run avait SEULEMENT renommé « lbs. »→« kg » sans toucher au calcul → la **valeur en livres** restait affichée sous un label kg (≈2,2× trop élevé : Bulbizarre « 15.2 kg » au lieu de « 6.9 kg »). **Fix = 1 seul littéral** : diviseur `4536`→`10000` à `0x105AD4` → `r6 = hg×100000/10000 = hg×10 = kg×100`, le formateur affiche alors les kg. Ne PAS toucher le multiplicateur 100000 (@0x105AD0) : il est réutilisé comme 1er diviseur d'extraction de chiffres. hg×10 multiple de 10 → le bloc d'arrondi (0x105AA0) ne se déclenche jamais. Overflow 32-bit du `×100000` à hg≥42949 (~4295 kg, hors-jeu) déjà présent en anglais, pas une régression.

**LEÇON CAPITALE** : pour une valeur affichée en jeu, « octets patchés corrects » ≠ « affichage correct ». Et **renommer une unité ne convertit pas la valeur** — vérifier le **rendu** en exécutant la vraie routine Thumb sous **unicorn** (mapper la ROM @0x08000000 + pile IWRAM @0x03000000 ; taille PC=0x08105922|1 r4=dm lire sp+0xC ; poids PC=0x08105A92|1 r4=hg lire sp+0xB). Une simulation à la main re-fige les mauvaises hypothèses. Tests : `TestPatchedRoutineRenders`/`TestPatchedWeightRenders` dans `tests/e2e/test_pokedex_metrics.py` et `gba_translator/tests/test_patch_pokedex_metrics_fr.py`.

Voir [[unbound-fr-build-lives-in-gba-translator]], [[unbound-datetime-code-patches]], [[unbound-pokedex-entries]].
