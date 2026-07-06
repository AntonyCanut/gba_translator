# Régression multilingue (FR / IT / DE / Indie)

Le pipeline est **un seul code partagé** (`src/core/`, `scripts/*.py` non
suffixés, `scripts/build_language.py`, `19_build_translated_rom_generic.py`,
`apply_combined_fr.py`) qui sert les quatre langues enregistrées dans
`languages/<code>/lang.yaml`. Un fix qui corrige FR touche donc, la plupart du
temps, IT et DE aussi — dans un sens ou dans l'autre. Deux incidents connus
sur ce dépôt :

- Des cellules à largeur fixe (Poké Ball, certaines entrées Pokédex/moves)
  sont **déjà en français dans `englishrom.gba` lui-même** — IT et DE héritent
  silencieusement de cette fuite. « Corriger » une de ces cellules côté FR
  peut être un no-op pour FR (déjà bon) alors que le vrai bug est ailleurs, ou
  inversement laisser IT/DE afficher du français non voulu.
- Une table de noms (ability/move/item) réputée pipeline-only s'est révélée
  être une table fixe non atteignable par le pipeline générique — un correctif
  qui ne visait que FR (`patch_ability_names_fr.py`) doit exister en miroir
  pour IT/DE dès que le même offset est fixe pour ces langues aussi.

## Règle

1. **Ne jamais scoper les tests à une seule langue** après un fix touchant du
   code partagé. `tests/unit/{fr,it,de,en}` et `tests/e2e/{fr,it,de,es}` sont
   TOUS sous `tests/` — `make test` / `make test-python` les couvrent déjà.
   Lancer `pytest tests/unit/fr/` (ou un fichier `*_fr.py` isolé) et s'arrêter
   là est un test **incomplet**, pas une preuve de non-régression.
2. Si le fix touche la **génération de ROM** (pas seulement une donnée de
   traduction) — `src/core/`, le driver générique, un script de patch
   réutilisé (`apply_inline_overrides_fr.py`, `patch_font_fr.py`, etc.) —
   rebuild aussi les autres langues et confirme qu'elles produisent toujours
   une ROM valide :
   ```bash
   make build-it && make build-de
   python3 -m pytest tests/unit/it tests/unit/de tests/e2e/it tests/e2e/de -q
   ```
   Les tests unitaires utilisent des fixtures synthétiques ; seul un rebuild
   réel détecte une régression de ROM complète (LZ77, pointeurs, tables
   figées).
3. Si le bug découvert est un **quirk de la ROM de base** (offset/table figée,
   contamination française du ROM anglais source) plutôt qu'un bug du
   pipeline : vérifie si IT et DE partagent le même offset avant de clore le
   ticket — `grep <offset> languages/it/combined_it.txt languages/de/combined_de.txt`,
   puis décoder l'octet réel dans `output/roms/GenedRom-it.gba` /
   `GenedRom-de.gba` après build. Un correctif qui ne visait que FR doit être
   dupliqué (ou généralisé) pour les langues qui partagent le même défaut.
4. À l'inverse, un script **partagé** (sans suffixe `_<code>`, ou passé en
   argument `--language`) ne doit **jamais** se spécialiser pour FR en dur
   (`if language == "fr"` sauf si documenté dans `lang.yaml`). Grep `_fr` dans
   le fichier modifié si tu touches `src/core/` ou `scripts/build_language.py`
   — un hardcode FR y est presque toujours un bug pour IT/DE.
5. `make sync-charmap-check` reste obligatoire après tout changement de
   charmap — un ajout de glyphe pour FR peut aussi être nécessaire pour IT/DE
   (voir la limite `ä ö ü` documentée dans `docs/21_MULTILANGUE.md`).

## Checklist avant de clore un ticket de fix

- [ ] Suite complète lancée (`make test` / `make test-python`), pas un
  sous-dossier ciblé sur une langue.
- [ ] Si le fix touche du code partagé : `make build-it` / `make build-de` (ou
  `make build-all`) relancés et verts.
- [ ] Si le bug vient d'une table figée / d'un offset de la ROM de base :
  vérifié que IT/DE ne partagent pas (ou partagent) le même défaut, et agi en
  conséquence (patch miroir ou ticket dédié si le périmètre est large).
- [ ] Pas de `if language == "fr"` ajouté dans du code partagé sans que
  `lang.yaml` documente pourquoi FR diffère.

Voir aussi : [`testing.md`](testing.md) (profils pytest), [`forbidden.md`](forbidden.md)
(tests scopés = interdit), `docs/21_MULTILANGUE.md` (registre des langues),
`.claude/skills/multilang-regression-check/SKILL.md` (procédure pas à pas).
