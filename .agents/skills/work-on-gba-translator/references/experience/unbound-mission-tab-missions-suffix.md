---
name: unbound-mission-tab-missions-suffix
description: "Menu Missions onglets (#114) — le suffixe partagé « Missions » est ajouté au runtime; le retirer = patch class-3, pas combined_fr.txt"
metadata:
  node_type: memory
  type: project
  originSessionId: bbb19aac-17d1-42e2-bd1e-d8a599dcc77c
---

Issue #114 : les onglets du menu Missions s'affichaient `ToutesMissions`,
`InactivesMissions`, etc. Les **noms de catégorie** (Toutes/Actives/Inactives/
Terminées) étaient déjà corrects — relogés en free-space et repointés (cf.
[[unbound-mission-menu-labels-live-pointer-false-negative]] pour #46). Le mot-valise
venait d'un **suffixe partagé « Missions » que le moteur ajoute au moment de
l'affichage** à chaque nom de catégorie. Le run #114 précédent n'avait touché que les
catégories → « toujours pas corrigé ».

Le suffixe : chaîne à `0x1F56040` (`" Missions"` avec espace en tête dans l'EN ; l'espace
a sauté au build FR → juste `"Missions"`), pointée par le mot **vivant** `0x1EBE988` dans
le tableau de pointeurs UI du menu (voisins : `0x1EBE978`→catégorie « All », `0x1EBE990`
→tri « A-Z »). `0x1F56040` n'a **aucune** référence-pointeur directe alignée sur le mot
« Missions » lui-même — d'où la fausse piste « 0 refs » ; le pointeur vise l'octet-espace
en tête, pas le M.

**Le vider = patch class-3 obligatoire**, pas `combined_fr.txt` : on veut une chaîne
**vide**, et `apply_combined_fr.py` ignore les overrides vides pour un offset déjà présent
dans le CSV (garde `if text:`). Solution livrée : `languages/fr/patches/mission_tab_labels.py`
(suit le pointeur vivant `0x1EBE988`, écrit `0xFF` sur toute la chaîne → suffixe vide),
câblé dans `make build-fr` après `mission_descriptions.py`, + test
`tests/test_patch_mission_tab_labels_fr.py`. Résultat vérifié dans la ROM : chaque onglet
décode exactement « Toutes / Actives / Inactives / Terminées ».

À noter : #116 avait raccourci « Actives »→« Active » à cause de la largeur du mot-valise ;
suffixe supprimé, la largeur n'est plus un souci (le pluriel « Actives » tient seul). Ce
commit #116 (`9128406b`) était **orphelin** — absent de l'ancêtre du worktree (Pattern C
concurrent), cf. [[singularity-parent-merge-orphaned-by-child-ticket]].
