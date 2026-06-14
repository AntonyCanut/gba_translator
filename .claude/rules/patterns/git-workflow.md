# Workflow git

## Branches

- Branche d'intégration FR active : **`unbound`**. CI déclenchée sur `master`.
- Travail orchestré : une branche par ticket, préfixée `worktree/<slug>` (ex.
  `worktree/r-04-rebuild-ai-configuration-...`), créée et fusionnée par le moteur.
- Historique **strictement linéaire** : intégrer par `git rebase` uniquement. Jamais
  `git merge`, jamais `git pull` sans `--rebase`.

## Format de commit (Conventional Commits, en français)

```
type(scope): description courte à l'impératif
```

- **Types** observés : `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `ci`, `build`.
- **Scope** = zone touchée : `core`, `translation`, `patch`, `pokedex`, `inline`,
  `combined_fr`, `rom`, `release`, `ai`…
- **Langue** : français (tout le projet l'est).

Exemples réels :
```
feat(pokedex): refondre toutes les fiches Pokédex sur 3 lignes max
fix(patch): repointer "Use" → "Utiliser" dans le menu sac en combat
build(rom): rebuild French ROM with French date/time formats
docs(ai): refresh configuration
```

## Règles dures

- **Jamais de trailer `Co-Authored-By`** (ni Claude, ni Codex, ni co-auteur). Le message
  reste `type(scope): description` — rien d'autre. *(L'historique ancien en contient ;
  ne pas en rajouter à partir de maintenant.)*
- **Jamais contourner les hooks** : pas de `--no-verify`, `HUSKY=0`,
  `GIT_SKIP_HOOKS=1`, ni édition du hook. Si le hook échoue, le commit n'a pas eu lieu →
  corriger la cause, re-stager, recommettre.
- Commits focalisés : un changement logique par commit. Stager explicitement
  (`git add <chemins>`), pas de `git add -A` aveugle.
- En contexte worktree orchestré : ne pas créer/checkout de branche soi-même, le moteur
  gère le cycle de vie ; committer dans le worktree fourni puis laisser l'intégration
  rebaser sur la branche de base.
