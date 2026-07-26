# Description CT108 — conception

## Constat

La CT108 lit sa description via le pointeur `+0x14` de l’entrée objet
`0x1B1`. Dans la ROM FR 2.1.85, ce pointeur vise toujours `0xA38FF2`, mais
le texte vivant n’est plus que le fragment court et terminé
« nsi sa statistique de vitesse. ». Le patch actuel ne relocalise que les
descriptions dont le terminateur est absent dans les 120 octets suivants :
il confond donc « court et terminé » avec « correct ».

## Options étudiées

1. Corriger uniquement l’item CT108 : rejeté, car ce serait un cas spécial
   d’offset interdit par les règles du dépôt et les CT106/CT107 montrent déjà
   le même défaut.
2. Relocaliser toutes les descriptions CT/CS de la région packée : sûr mais
   inutilement large, avec davantage de changements binaires et un risque sur
   les consommateurs particuliers.
3. Comparer les octets vivants au texte FR canonique puis relocaliser seulement
   les divergences : retenu. Cette règle détecte aussi bien les longues fusions
   sans terminateur que les fragments courts terminés.

## Conception retenue

Pour chaque CT/CS dont le pointeur vise `0xA30000..0xA50000`, le patch charge la
dernière valeur de `combined_fr.txt`, l’encode avec les mêmes règles que
l’injection inline et compare la séquence complète, terminateur `0xFF` inclus,
aux octets vivants. Une égalité conserve le pointeur en place ; toute différence
relocalise la valeur canonique dans l’espace libre et repointe l’entrée objet.
Une traduction absente reste signalée sans écriture.

Le test unitaire utilise une ROM synthétique contenant une CT dont le pointeur
vise un fragment court terminé : il doit échouer avec l’ancienne heuristique et
prouver que la nouvelle logique repointe vers le texte complet. Un garde ROM
décode ensuite la CT108 construite et exige exactement la description canonique.

## Auto-revue

La conception ne contient ni cas spécial CT108, ni changement de traduction,
ni modification d’entrée ROM source. Elle traite la cause racine dans le patch
post-build existant et conserve son idempotence.
