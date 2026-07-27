# Titre de mission « Voleur de vivres » — conception

## Constat

La ROM source contient le titre visible à `0x1FA4E10`, visé par trois pointeurs.
La source FR ne traduit que l'offset historique `0x1FA4E0E`, deux octets plus
tôt, qui inclut le préfixe interne `F<0x46>`. Le CSV et le JSON travaillent sur
`0x1FA4E10` : l'entrée FR existante ne peut donc jamais remplacer le titre et la
ROM conserve « The Food Thief ».

## Solution retenue

Ajouter une entrée vivante `0x1fa4e10: Voleur de vivres` dans le bloc
minuscule de `languages/fr/combined_fr.txt`. Conserver l'ancienne entrée sans
la réécrire afin de limiter le diff et de respecter la règle « dernière entrée
gagnante ».

Le titre est exclu des chaînes génériques CSV et JSON : sa relocalisation
décale plus de 2 000 octets et rend les sauvegardes de replay incompatibles.
Il est également exclu du passe inline, puis écrit en place par
`mission_titles.py`, sans
rechercher ni modifier les trois motifs de pointeur : leur repointage élargit
inutilement le diff et a également fait échouer le replay pendant le diagnostic.

Les deux octets supplémentaires chevauchent la description adjacente à
`0x1FA4E1F`. Ce voisin est déjà pris en charge par
`mission_descriptions.py`, exécuté immédiatement après : il en recrée une copie
intègre et repointe ses références actives.

## Preuve

Un test ROM part des trois motifs de la ROM source visant `0x1FA4E10`, exige
qu'ils restent inchangés et décode « Voleur de vivres » à l'adresse historique.
Des tests unitaires protègent l'exclusion des deux injecteurs, l'ordre avec la
description voisine et l'idempotence du patch.
