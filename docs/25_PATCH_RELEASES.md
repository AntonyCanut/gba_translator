# Audit et conception des releases BPS

## Conclusion

Le dépôt peut adopter le même principe que `Simopich/unbound-translator` : les
ROMs restent des entrées privées du build, mais aucune ROM source ou générée
n'est versionnée, téléversée comme artefact CI ou publiée dans une release.
Seuls des patchs BPS sont distribués.

Le format IPS historique n'est pas adapté : son champ d'offset sur 24 bits ne
peut pas atteindre les modifications situées au-delà de `0xFFFFFF`, tandis que
Pokémon Unbound et ses traductions occupent 32 Mio. BPS adresse toute la ROM,
embarque les tailles ainsi que les CRC32 source/cible/patch, et permet donc de
refuser une mauvaise ROM source.

## État audité

- Avant cette migration, `.github/workflows/release.yml` téléversait les ROMs
  générées en artefacts GitHub Actions puis publiait les fichiers `.gba` dans
  une release mutable `latest`.
- Avant cette migration, `scripts/package_release.py` copiait les ROMs
  complètes, les compressait en ZIP et inscrivait leurs empreintes dans le
  manifeste local.
- Avant cette migration, `input/roms/*.gba` et
  `output/roms/GenedRom-fr.gba` étaient suivis par Git.
- Le build FR dépend de `patchedfrenchrom.gba` et de la référence espagnole ;
  les builds génériques dépendent de `englishrom.gba` et de la référence
  espagnole. Supprimer toute ROM du calcul imposerait une refonte du moteur,
  mais les conserver comme entrées privées et éphémères suffit à ne plus les
  distribuer.

## Architecture retenue

1. Chaque descripteur de langue buildable déclare explicitement la ROM anglaise
   propre comme source de patch. La base française dédiée reste un intrant du
   builder FR, mais n'est pas demandée à l'utilisateur final.
2. Le packager génère un BPS déterministe, le réapplique en mémoire et refuse
   la livraison si le résultat ne reproduit pas exactement la ROM construite.
3. Le manifeste contient les noms, tailles et SHA-256 de la source, de la cible
   et du patch. Aucun `.gba` ni ZIP de ROM n'entre dans `output/release/`.
4. La CI télécharge les trois ROMs depuis des secrets URL, exécute
   `make verify-roms`, construit chaque langue, crée son BPS puis supprime la
   cible `.gba` avant l'upload de l'artefact.
5. Chaque build publie une release persistante `v2.1.<numéro>` et remplace la
   release roulante `latest` avec les mêmes patchs. Les quatre langues sont
   requises avant toute publication ; leurs manifests sont agrégés et vérifiés
   dans `RELEASE_MANIFEST.json` et `SHA256SUMS.txt`.
6. Un rerun ne modifie jamais une version existante : il compare son commit et
   tous ses assets, puis reprend uniquement le remplacement de `latest`.

## Configuration CI requise

Les secrets GitHub suivants doivent pointer vers des téléchargements privés :

- `UNBOUND_ENGLISH_ROM_URL`
- `UNBOUND_PATCHED_FRENCH_ROM_URL`
- `UNBOUND_SPANISH_ROM_URL`

Le workflow vérifie ensuite les tailles et SHA-256 déclarés dans
`docs/roms_baseline.json`. Une URL absente, une ROM erronée ou une génération
BPS non reproductible bloque la publication.

## Limite historique

Retirer les ROMs du nouvel état Git empêche toute nouvelle distribution, mais
ne les efface pas des anciens commits ni des anciennes releases. Une purge de
l'historique Git et des assets historiques demanderait une opération distante
destructive et coordonnée ; elle est volontairement hors de cette migration.
