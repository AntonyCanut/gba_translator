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
- ❌ Valider un fix touchant du code partagé (`src/core/`, `build_language.py`, script
  de patch réutilisé) avec des tests scopés à une seule langue (`tests/unit/fr/` seul) —
  voir [`multilang-regression.md`](multilang-regression.md).

## Traductions — combined_fr.txt et ROM FR

> **Contexte :** Le commit c7c1ede (2026-06-15, libellé « correct 'And' to 'Et' ») a
> silencieusement ramené **97 entrées** (dont 94 noms de lieux) à leur forme anglaise/périmée,
> en réécrivant combined_fr.txt depuis une working copy **périmée**. Les lignes existaient
> toujours — seules leurs **valeurs** avaient régressé, donc aucun `grep -c` ne l'a vu.
> Récupéré par B-52. **Doc de référence : [`docs/20_TRANSLATION_PRESERVATION.md`](../../../docs/20_TRANSLATION_PRESERVATION.md).**
> Les règles ci-dessous l'empêchent.

- ❌ **Réécrire `combined_fr.txt` en entier** — ni sed, ni regex globale, ni script de
  réécriture massive. Modification **chirurgicale** uniquement : insérer/corriger une entrée
  à la fois, toujours à la fin du fichier (bloc hexa minuscule, last entry wins).
- ❌ **Éditer `combined_fr.txt` depuis une working copy périmée** — `git status` propre +
  `git log -1 combined_fr.txt` avant toute édition ; ne jamais régénérer le fichier depuis
  une source plus ancienne que `HEAD`.
- ❌ **Modifier `combined_fr.txt` sans relancer la garde de valeur** — un `grep -c` ne suffit
  PAS (il compte des lignes, pas la valeur résolue last-wins). Après toute édition, lancer :
  `python3 scripts/check_translation_integrity.py` → doit afficher **13 [OK]** et sortir avec
  le code **0**. La garde contrôle la valeur réellement injectée des 13 labels carte
  (0xB5xxxx/0x72xxxx), absents du CSV trilingue.
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
