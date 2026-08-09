# Ordre du titre de l’écran de surnom — conception

## Constat

L’entrée `0x418E5C` ne contient que le suffixe `: surnom ?`. Le moteur
`DrawMonTextEntryBox` construit le titre en copiant d’abord le nom d’espèce,
puis ce suffixe. Une simple traduction ne peut donc pas produire l’ordre
français demandé.

## Solution retenue

La source FR devient `Surnom de<0x00>` (espace CFRU explicite) et un patch
post-build réécrit uniquement
la routine de composition du titre à `0x9F4F0`. La routine copiera le préfixe,
ajoutera le nom d’espèce dynamique, puis écrira ` ?` et le terminateur avant
de reprendre le rendu original. Le titre complet reste sous les 128 pixels de
la fenêtre pour `Wattouat`.

Cette solution conserve toutes les espèces et les deux variantes de l’écran
(Pokémon capturé et renommage), sans modifier les ROM anglaise, italienne ou
allemande.

## Validation

Un test Unicorn exécutera les vrais octets Thumb du patch avec un nom d’espèce
de synthèse et vérifiera le tampon remis au moteur de texte. Les gardes source,
le build FR complet et le décodage de la ROM construite prouveront ensuite que
le résultat livré est exactement `Surnom de Wattouat ?` et se termine par
`0xFF`.
