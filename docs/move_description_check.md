# Vérification des descriptions d'attaque

Les descriptions d'attaque sont affichées dans l'écran « Capacités connues » sur
**5 lignes maximum**, chaque ligne devant tenir sous **~120 px** (≈ 21 caractères
de la police FRLG à chasse variable). Au-delà, le texte déborde :

- **horizontalement** : les mots sont coupés au bord droit de la fenêtre ;
- **verticalement** : les lignes au-delà de la 5ᵉ sont masquées.

## Utilisation

```bash
# Lister les attaques qui débordent (lit output/roms/GenedRom-fr.gba)
python3 scripts/check_move_descriptions.py

# Détail ligne par ligne, attaques OK incluses
python3 scripts/check_move_descriptions.py --all --verbose

# Export JSON de la liste à retravailler
python3 scripts/check_move_descriptions.py --json output/reports/move_overflow.json

# Seuils personnalisés
python3 scripts/check_move_descriptions.py --max-lines 5 --max-width 120
```

Code de sortie : `0` si tout tient, `1` si au moins une description déborde
(utilisable comme garde-fou de build).

## Fonctionnement

- La logique pure est dans `src/core/move_description_check.py` (testable sans
  ROM) ; le CLI est `scripts/check_move_descriptions.py`.
- Les descriptions sont lues dans la ROM via la table de pointeurs
  `gMoveDescriptionPointers` à **`0x99F190`** (indexée par numéro d'attaque), et
  les noms via la table fixe des noms d'attaque à `0x1B2980`.
- La largeur de chaque ligne est mesurée au pixel près avec les chasses de la
  police FRLG (`src/core/dialogue_linewrap.line_width`).

## Calibrage (vérifié contre les captures du ticket)

| Attaque       | Lignes | Largeur max     | Verdict   |
| ------------- | ------ | --------------- | --------- |
| Groz'Yeux     | 4      | 110 px (20 c)   | tient     |
| Tempêtesable  | 5      | 118 px (21 c)   | tient     |
| Morsure       | 7      | 171 px (32 c)   | déborde   |
| Jet-Pierres   | 14     | 196 px (35 c)   | déborde   |

Le texte décodé pour Morsure et Jet-Pierres reproduit **exactement** celui des
captures, ce qui confirme que la table lue est bien celle de l'écran de résumé.
Le seuil de 120 px sépare proprement les descriptions correctes (≤ 118 px) des
descriptions débordantes (≥ 123 px).

## Pour retravailler une attaque

1. Repérer le nom FR et le texte fautif dans la sortie du script.
2. Corriger la dernière entrée de l'offset concerné dans
   `gba_translator/combined_fr.txt` (raccourcir le texte et/ou replacer les
   sauts de ligne `\n` pour ne pas dépasser 5 lignes de ~21 caractères).
3. Relancer la chaîne de build FR, puis relancer ce script pour vérifier.

> Note : beaucoup de descriptions débordent verticalement (> 5 lignes) ou
> contiennent du texte « fusionné » avec l'attaque suivante (terminateur mal
> placé, ex. Morsure « …tressailIl grogne… »). Ces cas demandent de revoir la
> traduction *et* parfois le découpage des sauts de ligne, pas seulement de
> raccourcir.
