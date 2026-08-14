# Plan d'implémentation des releases BPS

> **Pour les agents :** appliquer le plan avec TDD, en gardant chaque étape
> testable et le dépôt sans ROM publiée.

**Objectif :** remplacer les paquets et releases de ROM par des patchs BPS
vérifiés, persistants par version et accessibles aussi via `latest`.

**Architecture :** un codec BPS partagé crée et réapplique le patch ; le
packager résout la ROM source depuis le registre des langues et produit les
métadonnées. GitHub Actions ne transporte que les BPS et leurs manifests entre
les jobs, exige les quatre langues, puis publie deux releases pointant vers le
même commit.

**Technologies :** Python 3.11 standard library, YAML, GNU Make, GitHub Actions.

**Spécification :** `docs/25_PATCH_RELEASES.md`.

## Contraintes globales

- Aucun fichier `.gba` ou ZIP contenant une ROM dans les artefacts de release.
- Patch BPS déterministe et vérifié par round-trip avant livraison.
- Empreintes des ROMs sources contrôlées par `docs/roms_baseline.json`.
- Release `v2.1.<build>` persistante ; release `latest` remplacée.
- Aucun push distant depuis ce ticket.

## Étapes

- [x] Ajouter les tests rouges du codec BPS : format, déterminisme, round-trip,
  mauvaise source et corruption.
- [x] Implémenter le codec partagé et son CLI minimal.
- [x] Ajouter les tests rouges du registre et du packager patch-only.
- [x] Déclarer la source de patch par langue et convertir le packager en BPS.
- [x] Renforcer les gardes du workflow : téléchargement privé, artefacts BPS,
  suppression des ROMs temporaires, version persistante et alias `latest`.
- [x] Retirer les ROMs suivies du nouvel état Git et documenter la migration.
- [x] Exécuter les tests ciblés puis la suite complète, relire le diff et le
  contenu du commit.

## Suivi R-608 — flux patch-first sans ROM en CI

- [ ] Ajouter les gardes rouges d'inspection BPS et de bundle canonique sans
  charger de ROM source.
- [ ] Ajouter les gardes rouges de matérialisation locale et d'échec sur une
  mauvaise source.
- [ ] Inverser les gardes des workflows : aucun secret/téléchargement/build
  ROM, publication depuis `patches/` et version issue du manifeste.
- [ ] Implémenter la validation, la promotion locale et l'application du
  bundle BPS.
- [ ] Faire dépendre pytest ROM et Playwright de la matérialisation locale des
  ROMs éphémères.
- [ ] Versionner les quatre BPS reconstruits depuis le HEAD courant.
- [ ] Documenter le fonctionnement contributeur et mainteneur dans le README.
- [ ] Exécuter les suites ciblées, rapides, Vitest, ROM et Playwright
  applicables, puis relire et intégrer sans push.
