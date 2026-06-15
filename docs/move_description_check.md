# Descriptions d'attaque : correction et vérification

Les descriptions d'attaque sont affichées dans l'écran « Capacités connues » sur
**5 lignes maximum**, chaque ligne devant tenir sous **~130 px** (≈ 21 caractères
de la police FRLG à chasse variable, marge de 2 caractères incluse). Au-delà, le
texte déborde :

- **horizontalement** : les mots sont coupés au bord droit de la fenêtre ;
- **verticalement** : les lignes au-delà de la 5ᵉ sont masquées.

La **plus large ligne trouvée dans la ROM espagnole de référence** atteint 142 px,
mais à ce bord un glyphe était encore rogné à l'écran (débordement d'un caractère).
Le budget garde donc une **marge de sécurité de 2 caractères (~12 px)** et s'arrête
à **130 px** — exactement la méthode employée pour la fenêtre 3 lignes du Pokédex
(`src/core/pokedex.py`).

## Correction automatique (build FR)

`scripts/patch_move_descriptions_fr.py` corrige **toutes** les descriptions au
build, après la passe de repointage, comme `patch_pokedex_fr.py` pour le Pokédex :

1. Pour chaque attaque il prend le texte FR de référence — le raccourci curé de
   `data/move_descriptions_fr_overrides.json` quand le texte est trop verbeux
   pour 5 lignes, sinon la traduction complète du JSON de build, sinon la
   description source.
2. Il **re-wrappe** ce texte en ≤ 5 lignes dans la largeur de la fenêtre et
   l'encode (le terminateur `0xFF` est toujours réécrit, donc une description
   relocalisée ne peut plus fusionner avec sa voisine).
3. Il l'écrit sur place quand le créneau le permet, sinon la **relocalise** en
   espace libre et repointe la table `gMoveDescriptionPointers` (`0x99F190`).

Le re-wrap ne change que les sauts de ligne, jamais les mots ; le raccourcissement
n'applique que les overrides relus à la main. La passe est branchée dans la cible
`build-fr` du `Makefile`.

```bash
# Appliquer la correction à une ROM déjà construite
python3 scripts/patch_move_descriptions_fr.py \
  --rom output/roms/GenedRom-fr.gba \
  --source input/roms/englishrom.gba \
  --translations output/translation/2026-06-15_translation_ready.json
```

## Vérification

```bash
# Lister les attaques qui débordent encore (lit output/roms/GenedRom-fr.gba)
python3 scripts/check_move_descriptions.py

# Détail ligne par ligne, attaques OK incluses
python3 scripts/check_move_descriptions.py --all --verbose

# Export JSON de la liste à retravailler
python3 scripts/check_move_descriptions.py --json output/reports/move_overflow.json
```

Code de sortie : `0` si tout tient, `1` si au moins une description déborde
(utilisable comme garde-fou de build).

- La logique pure est dans `src/core/move_description_check.py` (testable sans
  ROM) ; le budget (5 lignes, 130 px) et la table sont partagés avec
  `src/core/moves.py`.
- Les descriptions sont lues via la table de pointeurs `gMoveDescriptionPointers`
  à **`0x99F190`** (indexée par numéro d'attaque), les noms via la table fixe à
  `0x1B2980`. La largeur de chaque ligne est mesurée au pixel près avec les
  chasses de la police FRLG (`src/core/dialogue_linewrap.line_width`).

## Historique

Avant correction, **448 / 893** attaques débordaient. Beaucoup étaient
**tronquées et fusionnées** avec l'attaque suivante (terminateur perdu lors d'une
écriture sur place trop longue), p. ex. Morsure « …faire tressailIl grogne… » ou
Jet-Pierres qui enchaînait plusieurs descriptions. Le patch ci-dessus ramène ce
compte à **0**.

Le budget a ensuite été resserré de **142 px à 130 px** (marge de 2 caractères) :
à 142 px un glyphe débordait encore d'un caractère sur le bord droit. Ce
resserrement fait basculer 63 descriptions supplémentaires hors fenêtre, toutes
raccourcies à la main → **148 overrides curés** au total, **0 débordement**.

Le terme de combat **« tressaillir » a aussi été remplacé par « apeurer »** (terme
officiel Pokémon FR) partout dans les descriptions d'attaque et d'objets.

## Ajouter / corriger un raccourci

Si une nouvelle description ne tient pas (le patch la signale en `ÉCHEC`),
ajouter une entrée dans `data/move_descriptions_fr_overrides.json` :

1. Clé = numéro d'attaque (index `gMoveDescriptionPointers`).
2. Valeur = description FR concise **en prose** (le patch s'occupe des sauts de
   ligne). Vérifier qu'elle tient avec `src.core.moves.fits(texte)`.
3. Relancer le patch (ou `make build-fr`), puis `check_move_descriptions.py`.
