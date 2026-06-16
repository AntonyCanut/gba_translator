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

## Traductions — combined_fr.txt et ROM FR

> **Contexte :** Le commit c7c1ede (Claude Haiku 4.5, 2026-06-15) a effacé 11 labels carte
> du monde en réécrivant combined_fr.txt lors d'une correction de dialogue. Ce bug peut se
> reproduire dès qu'un script touche le fichier en bulk. Les règles ci-dessous l'empêchent.

- ❌ **Réécrire `combined_fr.txt` en entier** — ni sed, ni regex globale, ni script de
  réécriture massive. Modification **chirurgicale** uniquement : insérer/corriger une entrée
  à la fois, toujours à la fin du fichier (bloc hexa minuscule, last entry wins).
- ❌ **Modifier `combined_fr.txt` sans vérifier les labels carte** — après toute modification
  du fichier, confirmer que les 13 labels 0xB5xxxx/0x72xxxx sont toujours présents :
  `grep -cE "^0x(B500A0|721304|7214[Ee]8|721968|B50214|B503[Cc][Cc]|B514[Ee]4|B52274|B522[Aa]4|B531[Dd]8|B535[Cc]8|B537[Aa][Cc]|720[Ee]74)" combined_fr.txt`
  → doit retourner **13**.
- ❌ **Committer une ROM buildée sans `make test-rom`** — `make build-fr` auto-lance les tests
  ROM, mais si le build est relancé manuellement (`python3 scripts/...`), toujours finir par
  `make test-rom` avant tout commit de la ROM.
- ❌ **`09_csv_to_json_v2.py` sans argument CSV explicite** — sans argument, le script utilise
  un CSV par défaut vide ; toujours passer :
  `python3 src/translators/09_csv_to_json_v2.py output/translation/2026-01-15_trilingual_translation.csv --allow-too-long`
- ❌ **`apply_combined_fr.py` sans `--extend`** — les offsets absents du CSV sont silencieusement
  ignorés ; `--extend` est **obligatoire** pour les labels carte (0xB5xxxx/0x72xxxx).

## Git
- ❌ `--no-verify` / `HUSKY=0` / désactivation du hook pre-commit.
- ❌ `git merge` / `git pull` sans `--rebase` (historique linéaire only).
- ❌ Trailer `Co-Authored-By` dans un commit.
- ❌ Sauvegarder en jeu pendant une sonde mGBA (écrase la fixture `.sav`).
