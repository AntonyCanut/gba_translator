# Patterns interdits

L'agent ne doit **jamais** recourir à ces pratiques dans ce dépôt.

## Structure & fichiers
- ❌ Script Python (`.py`) à la racine.
- ❌ Markdown à la racine autre que `README.md`.
- ❌ Document non numéroté dans `docs/` (hors `docs/recaps/`).
- ❌ Fichier de travail/temporaire à la racine.

## Code
- ❌ Duplication / copier-coller de fonctions → factoriser dans `src/core/`.
- ❌ Code procédural long, fonction monolithique → classes.
- ❌ Signature sans type hints, méthode publique sans docstring.
- ❌ Chemins en chaînes concaténées → `pathlib.Path`.
- ❌ Offsets décimaux magiques → hexadécimal.
- ❌ Nouvelle dépendance tierce sans nécessité (rester quasi-stdlib).

## Entrées / sorties
- ❌ Modifier un fichier de `input/roms/` (lecture seule).
- ❌ Écrire un artefact ailleurs que dans `output/`.
- ❌ Écraser une ROM sans backup `.bak` ni validation d'offset.

## Encodage
- ❌ Traiter le texte comme de l'ASCII (c'est du Gen III).
- ❌ Décoder un control code (`FC/FD/F8/F9/F7`) octet par octet.
- ❌ Réordonner les tokens/placeholders positionnels.
- ❌ Injecter un glyphe absent de la police cible.
- ❌ Régénérer le CSV trilingue avec `csv.writer`.

## Tests & qualité
- ❌ Skip d'un test pour masquer un échec.
- ❌ Fix hardcodé sur un offset spécifique (`if offset == 0x...`).
- ❌ Accepter < 100 % de réussite.

## Git
- ❌ `--no-verify` / `HUSKY=0` / désactivation du hook pre-commit.
- ❌ `git merge` / `git pull` sans `--rebase` (historique linéaire only).
- ❌ Trailer `Co-Authored-By` dans un commit.
- ❌ Sauvegarder en jeu pendant une sonde mGBA (écrase la fixture `.sav`).
