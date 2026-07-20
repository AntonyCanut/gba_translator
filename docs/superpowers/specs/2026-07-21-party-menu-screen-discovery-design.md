# Découverte de l’écran Pokémon dans les menus — conception

## Contexte

Le scénario de non-régression de l’issue #84 charge déjà la sauvegarde utilisateur et
compare l’écran du menu Pokémon à un golden 240×160. Son probe suppose cependant que
Pokémon est toujours la deuxième entrée du menu principal (`DOWN`, puis `A`). Le suivi
demande de retrouver ce même écran en parcourant les menus.

## Approches étudiées

1. Conserver le déplacement fixe et seulement vérifier le framebuffer. C’est simple,
   mais cela ne cherche pas l’écran et reste couplé à l’ordre du menu.
2. Lire un identifiant interne du menu dans la RAM. C’est rapide, mais introduit une
   adresse CFRU fragile et ne prouve pas que le bon écran est effectivement rendu.
3. Parcourir les entrées et reconnaître le framebuffer avec le golden existant. Cette
   option est retenue : elle teste le comportement visible, réutilise la preuve de
   régression et ne dépend d’aucun détail mémoire.

## Conception retenue

Après le chargement de la partie, le probe ouvre le menu principal et crée une save-state
temporaire. Pour chaque entrée, dans une limite explicite, il restaure cet état, déplace le
curseur, appuie sur `A`, attend le rendu, décode le PNG et compare ses pixels à ceux du
golden. Une correspondance copie la capture vers le chemin final et retourne le nombre
d’entrées visitées. La restauration rend la recherche indépendante de la façon dont chaque
sous-menu gère le bouton de retour.

Le test Playwright fournit le chemin du golden au probe et exige qu’au moins deux
entrées aient été visitées. Il conserve ensuite l’assertion `toMatchSnapshot` avec zéro
pixel différent ainsi que les contrôles d’intégrité de la sauvegarde. L’exploration
s’arrête dès la correspondance, bien avant l’entrée Sauvegarde, et ne déclenche donc
jamais de sauvegarde en jeu.

## Erreurs et bornes

- Le golden absent ou illisible fait échouer immédiatement le probe.
- L’exploration est limitée à huit entrées afin d’éviter toute boucle infinie.
- La save-state temporaire est distincte de la sauvegarde batterie versionnée.
- Si aucun écran ne correspond, le probe lève une erreur explicite avec le nombre
  d’entrées inspectées.
- Les trois tentatives existantes autour du pont mGBA restent inchangées.

## Vérification

Le cycle TDD fait d’abord échouer le scénario sur l’absence du compteur de recherche,
puis valide la découverte visuelle. Le contrôle TypeScript et le test E2E dédié doivent
ensuite réussir sans mise à jour du golden.
